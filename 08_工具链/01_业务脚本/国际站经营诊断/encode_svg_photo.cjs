// Lossless format compatibility only: no resize, crop, recolour or retouch.
const sharp = require('C:/Users/spq/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp');
sharp(process.argv[2]).png().toBuffer().then(b => process.stdout.write('data:image/png;base64,' + b.toString('base64'))).catch(e => {console.error(e.message);process.exitCode=1;});
