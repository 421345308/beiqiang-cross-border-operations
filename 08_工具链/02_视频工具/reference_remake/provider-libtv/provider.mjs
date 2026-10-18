import { canonicalize, defineEndpointPackage } from '@hypit/hypit/endpoint-kit';
import { generationTypes, sealGeneratedVideoSet } from '@hypit/hypit/generation';
import { createHash } from 'node:crypto';
import { readFile, writeFile, mkdir, open, unlink } from 'node:fs/promises';
import { isAbsolute, join } from 'node:path';
import { createCliTransport } from './transport.mjs';

export const providerModule = { name: '@beiqiang/provider-libtv', version: '1' };
export const capability = { module: { name: '@hypit/seedance', version: '1' }, name: 'seedance-2.5' };
const allowed = new Set(['prompt', 'referenceImage', 'referenceVideo', 'resolution',
  'aspectRatio', 'duration', 'generateAudio', 'webSearch']);
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
const normalize = text => text.replace(/\r\n/gu, '\n').trimEnd();
const assert = (ok, message) => { if (!ok) throw new Error(message); };
const json = async path => JSON.parse((await readFile(path, 'utf8')).replace(/^\uFEFF/u, ''));
async function optional(path) {
  try { return await json(path); } catch (error) { if (error.code === 'ENOENT') return undefined; throw error; }
}
async function save(path, data) { await writeFile(path, JSON.stringify(data, null, 2) + '\n', { mode: 0o600, flush: true }); }

export function support(request) {
  const p = request.constraints?.ports ?? {};
  const slots = request.pendingInputs ?? [];
  const failed = Object.keys(p).some(key => !allowed.has(key)) || slots.some(slot => !allowed.has(slot.input))
    || p.duration?.length !== 1 || !Number.isInteger(p.duration[0]) || p.duration[0] < 4 || p.duration[0] > 30
    || !['480p', '720p', '1080p'].includes(p.resolution?.[0])
    || !['9:16', '16:9', '4:3', '3:4', '1:1', '21:9', 'adaptive'].includes(p.aspectRatio?.[0])
    || p.webSearch?.[0] !== false
    || (p.referenceVideo?.length ?? 0) !== 1 && !slots.some(slot => slot.input === 'referenceVideo')
    || (p.referenceImage?.length ?? 0) < 1 && !slots.some(slot => slot.input === 'referenceImage')
    || (p.referenceVideo?.length ?? 0) > 1 || (p.referenceImage?.length ?? 0) > 2
    || [...(p.referenceImage ?? []), ...(p.referenceVideo ?? [])].some(item => Object.keys(item.fields ?? {}).length > 0);
  return failed ? { status: 'unsupported', reason: 'LibTV adapter supports only one full reference video, 1–2 product images, explicit 4–30s, no web search/person classification.' }
    : { status: 'supported' };
}

export async function validatePrepared(path) {
  const bytes = await readFile(path), job = JSON.parse(bytes.toString('utf8').replace(/^\uFEFF/u, ''));
  assert(job.schema === 'reference-remake-prepared-v1', 'Unsupported prepared package.');
  for (const [file, expected] of [[job.package_path, job.package_sha256], [job.prompt_path, job.prompt_sha256],
    [job.reference_video.path, job.reference_video.sha256], ...job.reference_images.map(i => [i.path, i.sha256])])
    assert(hash(await readFile(file)) === expected, 'Prepared input changed; review and prepare again.');
  assert(job.reference_video.has_audio && job.reference_video.duration_seconds <= 30,
    'Require a whole AV reference within this adapter contract.');
  assert(job.planned_discard_windows?.length === 0, 'Do not pre-plan discarded paid footage.');
  assert(job.settings.count === 1 && job.settings.model === 'Seedance 2.5'
    && job.settings.modeType === 'mixed2video', 'Unsupported generation contract.');
  assert(job.reference_images.length >= 1 && job.reference_images.length <= 2, 'Require 1–2 product images.');
  return { job, preparedSha: hash(bytes), prompt: normalize(await readFile(job.prompt_path, 'utf8')) };
}

async function matchNeed(context, checked) {
  const p = context.need.constraints.ports, { job, prompt } = checked;
  const supported = support(context.need); assert(supported.status === 'supported', supported.reason);
  assert(normalize(p.prompt?.[0] ?? '') === prompt, 'Hypit prompt differs from the prepared prompt.');
  const expected = { duration: job.settings.duration, resolution: job.settings.resolution,
    aspectRatio: job.settings.ratio, generateAudio: job.settings.enableSound === 'on' };
  for (const [key, value] of Object.entries(expected)) assert(p[key]?.[0] === value, `Hypit setting differs: ${key}`);
  for (const [port, references] of [['referenceVideo', [job.reference_video]], ['referenceImage', job.reference_images]]) {
    assert(p[port]?.length === references.length, `Hypit reference count differs: ${port}`);
    for (let i = 0; i < references.length; i++) {
      const input = p[port][i], bytes = await context.resources.get(input.artifact.resource);
      assert(bytes !== undefined && hash(bytes) === references[i].sha256, `Hypit artifact differs: ${port}[${i}]`);
      assert(input.role === (port === 'referenceVideo' ? 'video' : 'image'), 'Reference role differs.');
    }
  }
}

export function verifyDraft(node, job, stage, prompt) {
  const ids = [stage.reference_video_node_id, ...stage.product_image_node_ids];
  const p = node.data?.params;
  assert(node.nodeKey === job.libtv.draft_node_id && node.nodeType === 'video', 'Wrong LibTV draft.');
  assert(p?.model === 'Seedance 2.5' && p.modeType === 'mixed2video' && p.count === 1, 'Wrong LibTV model/mode/count.');
  assert(p.advancedSettings?.search_enabled === 0, 'LibTV web search must be explicitly disabled.');
  assert(JSON.stringify(p.videoList?.map(i => i.nodeId)) === JSON.stringify(ids.slice(0, 1))
    && JSON.stringify(p.imageList?.map(i => i.nodeId)) === JSON.stringify(ids.slice(1))
    && (p.audioList?.length ?? 0) === 0, 'Wrong LibTV input bindings.');
  // CLI derives mixed order from wiring (fresh drafts may group images before video).
  // Freeze the observed order, while still requiring every intended input exactly once.
  const order = stage.mixed_input_node_ids ?? ids;
  assert(Array.isArray(order) && order.length === ids.length && new Set(order).size === ids.length
    && ids.every(id => order.includes(id)), 'Invalid staged LibTV input order.');
  assert(JSON.stringify(p.mixedListOrder) === JSON.stringify(order), 'Wrong LibTV input order.');
  // A fresh CLI draft can omit this derived cache. A present cache must match exactly;
  // stale, empty or extra references are never accepted or manually overwritten.
  if (Object.hasOwn(p, 'mixedList'))
    assert(Array.isArray(p.mixedList) && JSON.stringify(p.mixedList.map(i => i.nodeId)) === JSON.stringify(order),
      'LibTV cached references differ; resolve the draft before execution.');
  for (const key of ['duration', 'ratio', 'resolution', 'enableSound'])
    assert(p.settings?.[key] === job.settings[key], `Wrong LibTV setting: ${key}`);
  let bound = prompt.replaceAll('@视频1', `{{Node ${ids[0]}}}`);
  job.reference_images.forEach((image, i) => { bound = bound.replaceAll(image.binding, `{{Node ${ids[i + 1]}}}`); });
  assert(normalize(p.prompt ?? '') === bound, 'Wrong LibTV prompt.');
  return hash(JSON.stringify({ project: job.libtv.project_uuid, node: node.nodeKey, prompt: bound,
    ids, mixedInputOrder: order, settings: job.settings, webSearch: false }));
}

export function verifyAuthorization(auth, { preparedSha, stageSha, draftSha, job }, now = Date.now()) {
  assert(auth?.schema === 'libtv-paid-authorization-v1' && auth.confirmed_by_user === true
    && typeof auth.confirmation === 'string' && auth.confirmation.trim().length > 0, 'No explicit current paid authorization.');
  assert(auth.prepared_sha256 === preparedSha && auth.stage_sha256 === stageSha && auth.draft_sha256 === draftSha,
    'Authorization does not match the current inputs/draft.');
  assert(auth.project_uuid === job.libtv.project_uuid && auth.draft_node_id === job.libtv.draft_node_id
    && auth.count === 1 && auth.max_submissions === 1, 'Authorization scope differs.');
  const quote = auth.quote;
  assert(quote?.source === 'libtv_current_page' && Number.isFinite(quote.credits) && quote.credits > 0
    && Number.isFinite(Date.parse(quote.checked_at)) && now - Date.parse(quote.checked_at) >= 0
    && now - Date.parse(quote.checked_at) <= 24 * 3600_000, 'Require a recent actual quote, not an estimated price.');
  assert(Number.isFinite(Date.parse(auth.expires_at)) && now < Date.parse(auth.expires_at), 'Authorization expired.');
}

async function admit(context, file, job, transport) {
  const probe = await transport.probe(file);
  const stream = probe.streams?.find(s => s.codec_type === 'video');
  assert(stream && Math.abs(Number(probe.format?.duration) - job.settings.duration) <= 0.5, 'Output duration/stream differs.');
  if (job.settings.enableSound === 'on') assert(probe.streams.some(s => s.codec_type === 'audio'), 'Generated audio missing.');
  const ratio = job.settings.ratio.split(':').map(Number);
  if (ratio.length === 2) assert(Math.abs(stream.width / stream.height - ratio[0] / ratio[1]) < 0.03, 'Output ratio differs.');
  const minSide = Number.parseInt(job.settings.resolution, 10);
  assert(Math.min(stream.width, stream.height) >= minSide, 'Output resolution differs.');
  const bytes = await readFile(file);
  const artifact = await context.resources.put(new Uint8Array(bytes), 'video/mp4');
  return { fulfillment: { value: { kind: 'inline', value: canonicalize(sealGeneratedVideoSet({ videos: [artifact] })) } },
    outputSha: hash(bytes) };
}

export function createLibTVProvider(options, transport = createCliTransport(options.executable, options.ffprobe)) {
  for (const key of ['prepared', 'evidenceDirectory']) assert(isAbsolute(options[key] ?? ''), `${key} must be an absolute path.`);
  async function handler(context) {
    const checked = await validatePrepared(options.prepared);
    await matchNeed(context, checked);
    const { job, preparedSha, prompt } = checked;
    const directory = options.evidenceDirectory;
    await mkdir(directory, { recursive: true });
    const journalPath = join(directory, `operation-${preparedSha}.json`), lockPath = journalPath + '.lock';
    const lock = await open(lockPath, 'wx', 0o600); // Process/crash-safe exclusion; a stale lock requires inspection.
    try {
      const previous = await optional(journalPath);
      if (previous) {
        assert(previous.prepared_sha256 === preparedSha && previous.project_uuid === job.libtv.project_uuid
          && previous.draft_node_id === job.libtv.draft_node_id, 'Operation record belongs to another request.');
        assert(['remote_complete', 'collected'].includes(previous.phase), 'Previous submission is failed/unknown; automatic resubmission blocked.');
        let file = previous.output_file;
        if (previous.phase === 'remote_complete') {
          const stage = await json(join(directory, 'stage-state.json'));
          const current = await transport.json(['node', job.libtv.draft_node_id, '-p', job.libtv.project_uuid], directory);
          assert(verifyDraft(current, job, stage, prompt) === previous.draft_sha256
            && hash(JSON.stringify(current.data.url)) === previous.output_identity_sha256,
            'Remote completed output changed; do not collect a different task.');
          file = await transport.download(job.libtv.project_uuid, job.libtv.draft_node_id, directory);
        }
        if (previous.output_sha256) assert(hash(await readFile(file)) === previous.output_sha256, 'Collected output changed.');
        const admitted = await admit(context, file, job, transport);
        await save(journalPath, { ...previous, phase: 'collected', output_file: file, output_sha256: admitted.outputSha });
        return admitted.fulfillment;
      }
      // No paid switch is reachable without both live draft validation and explicit matching authorization.
      assert(options.authorization, 'Paid generation disabled: no current authorization configured.');
      const stagePath = join(directory, 'stage-state.json'), stageBytes = await readFile(stagePath);
      const stage = JSON.parse(stageBytes.toString('utf8').replace(/^\uFEFF/u, ''));
      assert(stage.prepared_sha256 === preparedSha && stage.generation_ready === true
        && (stage.cached_mixed_list_matches === true || stage.mixed_list_cache_state === 'absent_derived_from_typed_inputs'),
        'Draft staging/page quote verification not ready.');
      const node = await transport.json(['node', job.libtv.draft_node_id, '-p', job.libtv.project_uuid], directory);
      const draftSha = verifyDraft(node, job, stage, prompt);
      assert(node.data.url?.length === 0, 'Draft already has output; use a verified recorded result, do not overwrite.');
      verifyAuthorization(await json(options.authorization), { ...checked, stageSha: hash(stageBytes), draftSha });
      // Persist before launching. Any interruption/failure after this point blocks another paid submission.
      await save(journalPath, { schema: 'libtv-native-operation-v1', phase: 'submission_unknown',
        prepared_sha256: preparedSha, draft_sha256: draftSha, project_uuid: job.libtv.project_uuid,
        draft_node_id: job.libtv.draft_node_id, started_at: new Date().toISOString() });
      await context.reportProgress?.({ phase: 'LibTV single submission; awaiting its synchronous final result' });
      const result = await transport.json(['node', job.libtv.draft_node_id, '-p', job.libtv.project_uuid, '--run'], directory);
      await save(join(directory, `run-${preparedSha}.json`), result);
      // A final JSON alone is not success. Re-read the selected node once after CLI termination (not polling).
      const completed = await transport.json(['node', job.libtv.draft_node_id, '-p', job.libtv.project_uuid], directory);
      verifyDraft(completed, job, stage, prompt);
      assert(completed.data.url?.length === 1, 'LibTV returned no single completed video; no paid retry.');
      await save(journalPath, { schema: 'libtv-native-operation-v1', phase: 'remote_complete',
        prepared_sha256: preparedSha, draft_sha256: draftSha, output_identity_sha256: hash(JSON.stringify(completed.data.url)),
        project_uuid: job.libtv.project_uuid, draft_node_id: job.libtv.draft_node_id });
      const file = await transport.download(job.libtv.project_uuid, job.libtv.draft_node_id, directory);
      const admitted = await admit(context, file, job, transport);
      await save(journalPath, { schema: 'libtv-native-operation-v1', phase: 'collected', prepared_sha256: preparedSha,
        project_uuid: job.libtv.project_uuid, draft_node_id: job.libtv.draft_node_id,
        output_file: file, output_sha256: admitted.outputSha });
      return admitted.fulfillment;
    } finally { await lock.close(); await unlink(lockPath); }
  }
  return defineEndpointPackage({ module: providerModule, facet: 'seedance', instance: options.instance, pool: options.pool,
    defaultConcurrency: 1, pricing: { kind: 'page', url: 'https://www.liblib.tv/' },
    capabilities: [{ capability, returns: generationTypes.videoSet, lifecycle: 'immediate', supports: support, handler }] });
}
