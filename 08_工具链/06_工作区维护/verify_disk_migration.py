"""Read-only manifests and SHA-256 verification for local disk relocation."""
import argparse
import hashlib
import json
import os
import stat
import time
from pathlib import Path


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def inventory(root, progress, allow_git=False, allow_links=False):
    files = {}
    directories = []
    links = {}
    stack = [root]
    last = time.monotonic()
    while stack:
        directory = stack.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                info = entry.stat(follow_symlinks=False)
                if info.st_file_attributes & 0x400:
                    if not allow_links:
                        raise RuntimeError(f"Reparse point is not permitted: {entry.path}")
                    links[os.path.relpath(entry.path, root)] = os.readlink(entry.path)
                    continue
                relative = os.path.relpath(entry.path, root)
                if stat.S_ISDIR(info.st_mode):
                    if entry.name == ".git" and not allow_git:
                        raise RuntimeError(f"Git checkout requires separate review: {entry.path}")
                    directories.append(relative)
                    stack.append(entry.path)
                elif stat.S_ISREG(info.st_mode):
                    # A zero-byte file has one possible content hash. Some Codex
                    # provisioning guards deny file opens even after the app exits.
                    sha = hashlib.sha256(b"").hexdigest() if info.st_size == 0 else digest(entry.path)
                    after = entry.stat(follow_symlinks=False)
                    if (info.st_size, info.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                        raise RuntimeError(f"File changed while hashing: {entry.path}")
                    files[relative] = [info.st_size, sha]
                else:
                    raise RuntimeError(f"Unsupported file type: {entry.path}")
                if time.monotonic() - last > 20:
                    print(f"{progress}: {len(files)} files checked", flush=True)
                    last = time.monotonic()
    return {"files": files, "directories": sorted(directories), "links": links}


parser = argparse.ArgumentParser()
parser.add_argument("mode", choices=["manifest", "verify"])
parser.add_argument("root")
parser.add_argument("manifest")
parser.add_argument("--allow-git", action="store_true")
parser.add_argument("--allow-links", action="store_true")
args = parser.parse_args()
root = str(Path(args.root).absolute())
if not os.path.isdir(root) or os.lstat(root).st_file_attributes & 0x400:
    raise RuntimeError("Root must be a real directory")
scan_root = "\\\\?\\" + root if os.name == "nt" and not root.startswith("\\\\?\\") else root
actual = inventory(scan_root, args.mode, args.allow_git, args.allow_links)
if args.mode == "manifest":
    if os.path.exists(args.manifest):
        raise RuntimeError("Existing manifest must not be overwritten")
    with open(args.manifest, "x", encoding="utf-8") as stream:
        json.dump({"source": root, **actual}, stream, ensure_ascii=False)
else:
    with open(args.manifest, encoding="utf-8") as stream:
        expected = json.load(stream)
    if (actual["files"] != expected["files"] or actual["directories"] != expected["directories"]
            or actual["links"] != expected.get("links", {})):
        raise RuntimeError("Source manifest and destination differ; retain all files for recovery")
print(json.dumps({"mode": args.mode, "files": len(actual["files"]),
                  "bytes": sum(value[0] for value in actual["files"].values()),
                  "verified": args.mode == "verify"}), flush=True)
