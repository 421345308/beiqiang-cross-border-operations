from pathlib import Path


path = Path(__file__).with_name("verify") / "frames.md5"
hashes = []
for line in path.read_text(encoding="utf-8").splitlines():
    if line.strip() and not line.startswith("#"):
        hashes.append(line.split(",")[-1].strip())
print(f"decoded_frames={len(hashes)}")
print(f"exact_consecutive_duplicates={sum(left == right for left, right in zip(hashes, hashes[1:]))}")
