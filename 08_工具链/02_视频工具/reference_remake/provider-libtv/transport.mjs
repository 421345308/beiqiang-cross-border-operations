import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { isAbsolute, resolve } from 'node:path';
import { stat } from 'node:fs/promises';
const execute = promisify(execFile);

// Official CLI only. Native argv, no shell, no background job, no generation timeout/poll/retry.
export function createCliTransport(executable = 'libtv', ffprobe = 'ffprobe') {
  async function run(args, cwd) {
    try {
      const result = await execute(executable, args, {
        cwd, windowsHide: true, encoding: 'utf8', maxBuffer: 8 * 1024 * 1024,
      });
      return result.stdout;
    } catch {
      // Raw CLI errors can include signed URLs or account data. Receipts stay in private evidence.
      throw new Error('LibTV CLI failed; inspect the node before any repeat. Submission may be unknown.');
    }
  }
  return {
    async json(args, cwd) { return JSON.parse(await run(args, cwd)); },
    async download(project, node, directory) {
      const out = await run(['download', '-n', node, '-p', project, '-o', directory], directory);
      // CLI 1.1.3 prints the file path, not JSON. Its optional watermark API can fail even on exit 0.
      // Admit only an actual single MP4 under our output directory, then inspect the streams.
      const paths = out.trim().split(/\r?\n/u).filter(line => /\.mp4$/iu.test(line.trim()));
      if (paths.length !== 1) throw new Error('Expected one downloaded MP4; ZIP/multiple/unknown output rejected.');
      const file = resolve(paths[0].trim());
      if (!isAbsolute(paths[0].trim()) || !file.startsWith(resolve(directory) + (process.platform === 'win32' ? '\\' : '/')))
        throw new Error('Download path escaped the output directory.');
      if (!(await stat(file)).isFile()) throw new Error('CLI reported a missing output.');
      return file;
    },
    async probe(file) {
      const { stdout } = await execute(ffprobe, ['-v', 'error', '-show_streams', '-show_format', '-of', 'json', file],
        { windowsHide: true, encoding: 'utf8', maxBuffer: 1024 * 1024 });
      return JSON.parse(stdout);
    },
  };
}
