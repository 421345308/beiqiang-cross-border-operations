// Standalone diagnostics/tests use the same pinned Distribution as Hypit, not a second SDK install.
import { dirname, resolve, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
const here = dirname(fileURLToPath(import.meta.url));
export const distribution = resolve(here, '../../Hypit/distribution');
export const sdkRoot = join(distribution, 'node_modules/@hypit/hypit');
const { register } = await import(pathToFileURL(join(distribution, 'node_modules/tsx/dist/esm/api/index.mjs')));
register();
const { installDistributionPackageResolution } = await import(pathToFileURL(join(sdkRoot, 'packages/package-loader-node/src/distribution-resolution.ts')));
installDistributionPackageResolution([sdkRoot]);
