"""Loopback-only static preview with byte-range support for frame seeking."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re


class Handler(SimpleHTTPRequestHandler):
    def send_head(self):
        path = Path(self.translate_path(self.path)).resolve()
        root = Path(self.directory).resolve()
        if not path.is_relative_to(root):
            self.send_error(403)
            return None
        self._remaining = None
        header = self.headers.get('Range')
        if not header or not path.is_file():
            return super().send_head()
        total = path.stat().st_size
        match = re.fullmatch(r'bytes=(\d+)-(\d*)', header)
        if not match:
            self.send_error(416)
            return None
        start = int(match[1])
        end = min(int(match[2]) if match[2] else total - 1, total - 1)
        if start > end or start >= total:
            self.send_response(416)
            self.send_header('Content-Range', f'bytes */{total}')
            self.end_headers()
            return None
        stream = path.open('rb')
        stream.seek(start)
        self._remaining = end - start + 1
        self.send_response(206)
        self.send_header('Content-Type', self.guess_type(str(path)))
        self.send_header('Content-Range', f'bytes {start}-{end}/{total}')
        self.send_header('Content-Length', str(self._remaining))
        self.send_header('Accept-Ranges', 'bytes')
        self.end_headers()
        return stream

    def copyfile(self, source, output):
        if self._remaining is None:
            return super().copyfile(source, output)
        try:
            while self._remaining:
                block = source.read(min(self._remaining, 65536))
                if not block:
                    break
                output.write(block)
                self._remaining -= len(block)
        except (ConnectionResetError, BrokenPipeError):
            pass


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--directory', type=Path, required=True)
    p.add_argument('--port', type=int, default=8796)
    a = p.parse_args()
    root = a.directory.resolve(strict=True)
    server = ThreadingHTTPServer(('127.0.0.1', a.port), partial(Handler, directory=str(root)))
    print(f'http://127.0.0.1:{a.port}', flush=True)
    server.serve_forever()
