// Uses the actual Hypit SDK with a simulated vendor transport. Never calls paid generation.
import { pathToFileURL } from 'node:url';
import { join } from 'node:path';
import { mkdtemp, readFile, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { createHash } from 'node:crypto';
import assert from 'node:assert/strict';
const { sdkRoot: root } = await import('./sdk-loader.mjs');
const { createLibTVProvider, capability, support, verifyDraft } = await import('./provider.mjs');
const { generationTypes, verifyGeneratedVideoSet } = await import(pathToFileURL(join(root, 'packages/generation/src/index.ts')));
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const temp = await mkdtemp(join(tmpdir(), 'libtv-provider-test-'));
try {
  const refs = [];
  for (const name of ['video', 'image1', 'image2', 'prompt', 'package']) {
    const file = join(temp, name); await writeFile(file, name === 'prompt' ? '@视频1 @图片1 @图片2' : name);
    refs.push({ path: file, sha256: sha(await readFile(file)) });
  }
  const job = { schema: 'reference-remake-prepared-v1', package_path: refs[4].path, package_sha256: refs[4].sha256,
    prompt_path: refs[3].path, prompt_sha256: refs[3].sha256, reference_video: { ...refs[0], has_audio: true, duration_seconds: 28.47 },
    reference_images: refs.slice(1, 3).map((r, i) => ({ ...r, binding: `@图片${i + 1}` })), planned_discard_windows: [],
    settings: { model: 'Seedance 2.5', modeType: 'mixed2video', count: 1, duration: 28, resolution: '720p', ratio: '9:16', enableSound: 'on' },
    libtv: { project_uuid: 'test-project', draft_node_id: 'test-draft' } };
  const prepared = join(temp, 'prepared.json'); await writeFile(prepared, JSON.stringify(job));
  const preparedSha = sha(await readFile(prepared));
  const stage = { prepared_sha256: preparedSha, generation_ready: true, cached_mixed_list_matches: true,
    reference_video_node_id: 'v', product_image_node_ids: ['i1', 'i2'] };
  const stagePath = join(temp, 'stage-state.json'); await writeFile(stagePath, JSON.stringify(stage));
  const node = { nodeKey: 'test-draft', nodeType: 'video', data: { url: [], params: {
    ...job.settings, prompt: '{{Node v}} {{Node i1}} {{Node i2}}', settings: job.settings,
    videoList: [{ nodeId: 'v' }], imageList: [{ nodeId: 'i1' }, { nodeId: 'i2' }], audioList: [],
    mixedListOrder: ['v', 'i1', 'i2'], mixedList: ['v', 'i1', 'i2'].map(nodeId => ({ nodeId })) } } };
  const draftSha = verifyDraft(node, job, stage, '@视频1 @图片1 @图片2');
  const authFile = join(temp, 'authorization.json');
  const authorization = { schema: 'libtv-paid-authorization-v1', confirmed_by_user: true,
    confirmation: 'TEST FIXTURE ONLY - no real CLI attached', prepared_sha256: preparedSha,
    stage_sha256: sha(await readFile(stagePath)), draft_sha256: draftSha,
    project_uuid: 'test-project', draft_node_id: 'test-draft', count: 1, max_submissions: 1,
    quote: { source: 'libtv_current_page', credits: 100, checked_at: new Date().toISOString() },
    expires_at: new Date(Date.now() + 60_000).toISOString() };
  const resources = new Map(refs.slice(0, 3).map(r => ['res_' + r.sha256, r]));
  const media = (r, role) => ({ role, artifact: { kind: 'blob', resource: 'res_' + r.sha256,
    mediaType: role + (role === 'video' ? '/mp4' : '/jpeg'), size: role === 'video' ? 5 : 6 } });
  const need = { capability, returns: generationTypes.videoSet, constraints: { ports: {
    prompt: ['@视频1 @图片1 @图片2'], duration: [28], resolution: ['720p'], aspectRatio: ['9:16'],
    generateAudio: [true], webSearch: [false], referenceVideo: [media(refs[0], 'video')],
    referenceImage: refs.slice(1, 3).map(r => media(r, 'image')) } } };
  const context = { need, resources: { get: async id => readFile(resources.get(id).path), put: async (bytes, mediaType) =>
    ({ kind: 'blob', resource: 'res_' + sha(bytes), mediaType, size: bytes.length }) }, credentials: {} };
  const calls = [];
  const fakeOutput = join(temp, 'fixture.mp4'); await writeFile(fakeOutput, 'SIMULATED MP4 BYTES - NOT A REAL VIDEO');
  let failSubmit = false, failDownload = false;
  const transport = {
    async json(args) {
      calls.push(args);
      if (args.includes('--run')) { if (failSubmit) throw new Error('simulated connection failure'); node.data.url = ['fixture-only']; }
      return structuredClone(node);
    },
    async download() { if (failDownload) throw new Error('simulated download failure'); return fakeOutput; },
    async probe() { return { format: { duration: '28' }, streams: [{ codec_type: 'video', width: 720, height: 1280 }, { codec_type: 'audio' }] }; },
  };
  async function invoke(options = {}) {
    const endpoint = createLibTVProvider({ instance: 'test', pool: 'test', prepared, evidenceDirectory: temp, ...options }, transport);
    let handler;
    await endpoint.install({ registerImmediateEndpoint: (id, cap, type, fn) => { handler = fn; } });
    return handler(context);
  }
  assert.equal(support(need).status, 'supported');
  const textOnly = structuredClone(need); delete textOnly.constraints.ports.referenceVideo;
  delete textOnly.constraints.ports.referenceImage;
  assert.equal(support(textOnly).status, 'unsupported');
  assert.equal(support({ ...need, constraints: { ports: { ...need.constraints.ports, duration: [31] } } }).status, 'unsupported');
  assert.equal(support({ ...need, constraints: { ports: { ...need.constraints.ports, firstFrame: [media(refs[1], 'image')] } } }).status, 'unsupported');
  await assert.rejects(invoke(), /Paid generation disabled/u);
  assert.equal(calls.length, 0);
  need.constraints.ports.referenceImage[0] = media(refs[2], 'image');
  await assert.rejects(invoke(), /Hypit artifact differs/u);
  need.constraints.ports.referenceImage[0] = media(refs[1], 'image');
  await writeFile(join(temp, `operation-${preparedSha}.json.lock`), 'test-lock');
  await assert.rejects(invoke(), error => error.code === 'EEXIST');
  await rm(join(temp, `operation-${preparedSha}.json.lock`));
  await writeFile(authFile, JSON.stringify({ ...authorization, prepared_sha256: 'wrong' }));
  await assert.rejects(invoke({ authorization: authFile }), /Authorization does not match/u);
  assert.equal(calls.filter(a => a.includes('--run')).length, 0);
  await writeFile(authFile, JSON.stringify({ ...authorization, expires_at: new Date(Date.now() - 1000).toISOString() }));
  await assert.rejects(invoke({ authorization: authFile }), /Authorization expired/u);
  await writeFile(authFile, JSON.stringify(authorization));
  node.data.params.mixedList[1].nodeId = 'old-shoe';
  await assert.rejects(invoke({ authorization: authFile }), /cached references differ/u);
  node.data.params.mixedList[1].nodeId = 'i1';
  failSubmit = true;
  await assert.rejects(invoke({ authorization: authFile }), /connection failure/u);
  failSubmit = false;
  await assert.rejects(invoke({ authorization: authFile }), /automatic resubmission blocked/u);
  assert.equal(calls.filter(a => a.includes('--run')).length, 1);
  // Reset only the isolated test journal, never an actual task's unknown submission.
  await rm(join(temp, `operation-${preparedSha}.json`));
  failDownload = true;
  await assert.rejects(invoke({ authorization: authFile }), /download failure/u);
  const submitted = calls.filter(a => a.includes('--run')).length;
  failDownload = false;
  const completed = await invoke({ authorization: authFile });
  verifyGeneratedVideoSet(completed.value.value);
  await invoke(); // Collection reuse allowed without another payment scope or another --run.
  assert.equal(calls.filter(a => a.includes('--run')).length, submitted);
  await writeFile(fakeOutput, 'changed');
  await assert.rejects(invoke(), /Collected output changed/u);
  console.log(JSON.stringify({ sdk: 'Hypit 0.1.8 actual SDK', transport: 'simulated only', paid_calls: 0,
    passed: ['exact_support', 'artifact_mismatch', 'exclusive_lock', 'authorization_absent', 'authorization_mismatch', 'authorization_expired', 'stale_reference',
      'unknown_submit_no_retry', 'collect_resume_without_regeneration', 'model_result_type', 'output_integrity'] }));
} finally { await rm(temp, { recursive: true, force: true }); }
