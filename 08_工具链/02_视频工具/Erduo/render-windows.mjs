// Windows launches the pinned .mjs CLI with Node; upstream source stays untouched.
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { runLeanRender } from './upstream/erduo-broll-loop-engineering/scripts/lean-render.mjs';
import { runCommand } from './upstream/erduo-broll-loop-engineering/scripts/shot-media-lib.mjs';

const toolRoot = path.dirname(fileURLToPath(import.meta.url));
const hyperframes = path.join(toolRoot, 'upstream/runtime/node_modules/hyperframes/bin/hyperframes.mjs');
const options = {};
try {
  const args = process.argv.slice(2);
  for (let i = 0; i < args.length; i += 2) {
    const name = args[i];
    if (!['--project', '--quality', '--shots'].includes(name) || !args[i + 1] || args[i + 1].startsWith('--')) {
      throw new Error('Usage: render-windows.mjs --project <directory> --quality draft|final [--shots S01,S02]');
    }
    const key = name.slice(2);
    if (key in options) throw new Error(`Duplicate ${name}`);
    options[key] = args[i + 1];
  }
  if (!options.project || !options.quality) throw new Error('--project and --quality are required');
  const runner = (command) => command.executable === hyperframes
    ? runCommand({ ...command, executable: process.execPath, args: [hyperframes, ...command.args] })
    : runCommand(command);
  const result = await runLeanRender({ ...options, hyperframes, runner });
  process.stdout.write(`${JSON.stringify(result)}\n`);
} catch (error) {
  process.stderr.write(`${error.message}\n`);
  process.exitCode = 1;
}
