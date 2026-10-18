// Live read-only check. No upload, draft mutation, --run, model download or worker.
import './sdk-loader.mjs';
import { readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { createHash } from 'node:crypto';
const { validatePrepared, verifyDraft } = await import('./provider.mjs');
const { createCliTransport } = await import('./transport.mjs');
const readJson = async path => JSON.parse((await readFile(path, 'utf8')).replace(/^\uFEFF/u, ''));
const profile = await readJson(process.argv[2]);
const config = profile.endpoints['libtv.reference'].config;
const checked = await validatePrepared(config.prepared);
const stagePath = join(config.evidenceDirectory, 'stage-state.json');
const stage = await readJson(stagePath);
const transport = createCliTransport(config.executable, config.ffprobe);
const node = await transport.json(['node', checked.job.libtv.draft_node_id, '-p', checked.job.libtv.project_uuid], config.evidenceDirectory);
let draftSha, reason;
try {
  if (stage.prepared_sha256 !== checked.preparedSha) throw new Error('Stage package hash differs.');
  draftSha = verifyDraft(node, checked.job, stage, checked.prompt);
} catch (error) { reason = error.message; }
const result = { schema: 'libtv-native-inspection-v1', checked_at: new Date().toISOString(),
  prepared_sha256: checked.preparedSha, stage_sha256: createHash('sha256').update(await readFile(stagePath)).digest('hex'),
  input_count: { video: 1, images: checked.job.reference_images.length }, output_seconds: checked.job.settings.duration,
  ...(draftSha ? { draft_sha256: draftSha } : { reason }), draft_verified: Boolean(draftSha),
  paid_authorization_configured: Boolean(config.authorization), generation_submitted: false, live_generation_verified: false };
await writeFile(join(config.evidenceDirectory, 'native-inspection.json'), JSON.stringify(result, null, 2) + '\n');
console.log(JSON.stringify(result));
