// Rasterize an editable SVG information diagram; source photographs stay intact.
const fs = require('fs');
const sharp = require('C:/Users/spq/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp');
const [input, output] = process.argv.slice(2);
if (!input || !output || !input.endsWith('.svg') || !output.endsWith('.png')) throw new Error('Exact SVG and PNG paths required');
sharp(fs.readFileSync(input), {density: 96}).png().toFile(output).catch(e => {console.error(e.message); process.exitCode = 1;});
