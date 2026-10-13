// Offline validation only: no credentials are read, no API is called.
import fs from 'node:fs';
import path from 'node:path';
const filename = process.argv[2];
if (!filename) throw new Error('Pass the trial recipe JSON path.');
const recipe = JSON.parse(fs.readFileSync(filename, 'utf8'));
const base = path.dirname(path.resolve(filename));
if (recipe.model !== 'kling-video-v3') throw new Error('This validator covers Kling V3 only.');
if (recipe.settings.resolution !== '1080p' || recipe.settings.duration !== 5
  || recipe.settings.multi_shot !== false || recipe.settings.audio !== 'off')
  throw new Error('Unexpected trial settings: review the recipe.');
if (!Array.isArray(recipe.jobs) || recipe.jobs.length < 1 || recipe.jobs.length > 2
  || recipe.estimated_cost.jobs !== recipe.jobs.length
  || new Set(recipe.jobs.map(j=>j.id)).size !== recipe.jobs.length)
  throw new Error('Expected one or two distinct, cost-scoped action trials.');
for (const job of recipe.jobs) {
  if (!job.prompt || job.prompt.length > 2500) throw new Error('Invalid prompt length.');
  const images = [];
  for (const role of ['first_frame', 'last_frame']) {
    if (!job[role]) continue;
    const target = path.resolve(base, job[role]);
    if (!target.startsWith(base + path.sep)) throw new Error('Reference outside project.');
    const b = fs.readFileSync(target);
    if (b.subarray(0,8).toString('hex') !== '89504e470d0a1a0a') throw new Error('Expected PNG reference.');
    const width = b.readUInt32BE(16), height = b.readUInt32BE(20);
    if (b.length > 50 * 1024 * 1024 || Math.min(width,height) < 300
      || width/height < 1/2.5 || width/height > 2.5) throw new Error('Image outside documented limits.');
    images.push({role,file:job[role],width,height,bytes:b.length});
  }
  console.log(JSON.stringify({job:job.id,promptCharacters:job.prompt.length,images}));
}
console.log('OFFLINE_VALIDATION_OK: no generation submitted.');
