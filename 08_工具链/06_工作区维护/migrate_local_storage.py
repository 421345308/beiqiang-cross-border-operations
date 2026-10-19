"""Move allowlisted local data to E:, verifying bytes and preserving Windows junctions.

Dry run by default. Never follows reparse points, moves runtimes, or removes evidence.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import time
import _winapi


ROOT = Path(__file__).resolve().parents[2]
PAIRS = {
    "project-temp": (ROOT / "99_临时区", Path("E:/贝强大文件/工作台运行资料/99_临时区")),
}


def is_junction(path):
    try:
        return path.lstat().st_reparse_tag == stat.IO_REPARSE_TAG_MOUNT_POINT
    except FileNotFoundError:
        return False


def inventory(root):
    result = {}
    pending = [root]
    while pending:
        directory = pending.pop()
        for item in directory.iterdir():
            info = item.lstat()
            relative = str(item.relative_to(root))
            if info.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                if not is_junction(item):
                    raise RuntimeError(f"Unsupported reparse point: {item}")
                result[relative] = ("junction", os.readlink(item))
            elif item.is_dir():
                result[relative] = ("dir",)
                pending.append(item)
            else:
                with item.open("rb") as stream:
                    digest = hashlib.file_digest(stream, "sha256").hexdigest()
                result[relative] = ("file", info.st_size, digest)
    return result


def junction(source, target):
    target = str(target)
    if target.startswith('\\\\?\\'):
        target = target[4:]
    _winapi.CreateJunction(target, str(source))


def migrate(name, apply, resume=False, child=None):
    source, target = PAIRS[name]
    if child:
        if Path(child).name != child or child in (".", ".."):
            raise RuntimeError("Child must be one direct directory name")
        source, target = source / child, target / child
    elif apply:
        raise RuntimeError("Whole temporary root may be active; choose --child")
    # Check absolute physical boundaries before any move/delete. Source roots
    # are fixed above; a previously migrated root is never traversed or deleted.
    if is_junction(source):
        print(json.dumps({"name": name, "already_linked": os.readlink(source)}, ensure_ascii=False))
        return
    if source.resolve() != source.absolute() or source.drive.upper() != "C:":
        raise RuntimeError("Source is redirected or outside C:")
    if target.drive.upper() != "E:" or (target.exists() and not resume):
        raise RuntimeError("Target must be a new directory on E:")
    if target.resolve() != target.absolute():
        raise RuntimeError("Destination is redirected")
    held = source.with_name(source.name + ".migration-hold")
    if held.exists():
        raise RuntimeError("A previous migration needs inspection")
    before = inventory(source)
    if apply and any((source / rel).stat().st_mtime > time.time() - 900
                     for rel, value in before.items() if value[0] == "file"):
        raise RuntimeError("Recently written files found; leave this task in place")
    size = sum(v[1] for v in before.values() if v[0] == "file")
    print(json.dumps({"name": name, "bytes": size, "entries": len(before), "target": str(target), "apply": apply}, ensure_ascii=False), flush=True)
    if not apply:
        return
    if shutil.disk_usage(target.anchor).free < size + 1024**3:
        raise RuntimeError("Insufficient destination space")
    target.mkdir(parents=True, exist_ok=resume)
    for rel, entry in ([] if resume else before.items()):
        dst = target / rel
        if entry[0] == "dir":
            dst.mkdir(parents=True, exist_ok=True)
        elif entry[0] == "junction":
            dst.parent.mkdir(parents=True, exist_ok=True)
            junction(dst, entry[1])
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / rel, dst)
    if inventory(target) != before or inventory(source) != before:
        raise RuntimeError("Content changed or verification failed; source kept intact")
    source.rename(held)
    try:
        junction(source, target)
        if inventory(source) != before:
            raise RuntimeError("Compatibility path verification failed")
    except Exception:
        if is_junction(source):
            os.rmdir(source)
        held.rename(source)
        raise
    # Remove only the exact verified original entries, without recursive deletion.
    # rmdir on a junction removes the link alone, never its external target.
    if held.resolve() != held.absolute() or held.parent != source.parent:
        raise RuntimeError("Unexpected cleanup boundary")
    if inventory(held) != before:
        raise RuntimeError("Original changed after switching; original copy kept for inspection")
    for rel, entry in sorted(before.items(), key=lambda pair: len(Path(pair[0]).parts), reverse=True):
        old = held / rel
        if entry[0] in ("junction", "dir"):
            os.rmdir(old)
        else:
            old.unlink()
    held.rmdir()
    print(json.dumps({"name": name, "verified": True, "released_bytes": size}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", choices=PAIRS)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--resume", action="store_true", help="Only verify an existing copy before switching")
    parser.add_argument("--child", help="One inactive direct child of the temporary root")
    args = parser.parse_args()
    migrate(args.name, args.apply, args.resume, args.child)
