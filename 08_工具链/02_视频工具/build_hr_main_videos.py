"""Build eight Alibaba main videos: exact HR product motion + real factory film.

The 16:9 factory film is placed inside a square canvas without stretching.
Segments are encoded independently with boundary fades and then stream-copied
into the final file, keeping every final under Alibaba's 45-second limit.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(r"C:\Users\spq\Desktop\贝强")
PACK = ROOT / "01_产品资产/01_原始数据包/热榜OEM概念款_2026-09-02"
FACTORY = Path(r"E:\贝强大文件\05_内容与视频\01_贝强商品视频\通用工厂视频修复_2026-09-05\factory42.mp4")
OUT = Path(r"E:\贝强大文件\05_内容与视频\01_贝强商品视频\HR热榜8款_2026-09-05\edit")


def run(args):
    subprocess.run(args, check=True)


def probe(path: Path) -> dict:
    result = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels",
        "-of", "json", str(path),
    ], check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    factory_segment = OUT / "factory_common_38s_square.mp4"
    if not factory_segment.exists():
        vf = (
            "split=2[bg][fg];"
            "[bg]scale=1080:1080:force_original_aspect_ratio=increase,crop=1080:1080,boxblur=24:12[blur];"
            "[fg]scale=1080:1080:force_original_aspect_ratio=decrease[front];"
            "[blur][front]overlay=(W-w)/2:(H-h)/2,fade=t=in:st=0:d=0.25,fade=t=out:st=38.25:d=0.25,fps=30,format=yuv420p"
        )
        run(["ffmpeg", "-y", "-ss", "0", "-t", "38.5", "-i", str(FACTORY), "-filter_complex", vf,
             "-af", "afade=t=in:st=0:d=0.03,afade=t=out:st=38.47:d=0.03,aresample=44100",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2", str(factory_segment)])

    rows = []
    for i in range(1, 9):
        model = f"HR{i:03d}"
        source = next(PACK.glob(f"{model}_*/04_视频/{model}_h3_i2va_v1.mp4"))
        product_segment = OUT / f"{model}_product_segment.mp4"
        vf = (
            "scale=1080:1080:force_original_aspect_ratio=decrease,"
            "pad=1080:1080:(ow-iw)/2:(oh-ih)/2:white,"
            "fade=t=in:st=0:d=0.20,fade=t=out:st=4.92:d=0.25,fps=30,format=yuv420p"
        )
        run(["ffmpeg", "-y", "-i", str(source), "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "5.167",
             "-vf", vf, "-af", "afade=t=in:st=0:d=0.03,afade=t=out:st=5.137:d=0.03",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2", "-shortest", str(product_segment)])
        concat_file = OUT / f"{model}_concat.txt"
        concat_file.write_text(f"file '{product_segment.as_posix()}'\nfile '{factory_segment.as_posix()}'\n", encoding="utf-8")
        final = OUT / f"{model}_Product_And_Beiqiang_Factory_44s.mp4"
        run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-c", "copy", str(final)])
        info = probe(final)
        duration = float(info["format"]["duration"])
        stream = next(s for s in info["streams"] if s["codec_type"] == "video")
        if duration > 45 or stream.get("width") != 1080 or stream.get("height") != 1080:
            raise RuntimeError(f"video gate failed: {model} {info}")
        rows.append({"model": model, "source": str(source), "final": str(final), "duration": duration, "probe": info})
        print(model, f"{duration:.3f}s", flush=True)
    (OUT / "verification.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
