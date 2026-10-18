"""Local shot workbench: playable media, candidate cuts, waveform and editable notes."""
import argparse
import array
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent


def run(args):
    return subprocess.run(args, check=True, capture_output=True)


def probe(path):
    data = json.loads(run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)]).stdout)
    v = next(s for s in data['streams'] if s['codec_type'] == 'video')
    num, den = map(float, v['avg_frame_rate'].split('/'))
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return {'sha256': h.hexdigest(), 'duration': float(data['format']['duration']),
            'fps': num / den, 'width': v['width'], 'height': v['height'],
            'hasAudio': any(s['codec_type'] == 'audio' for s in data['streams'])}


def prepare(path, label, output):
    from scenedetect import detect, AdaptiveDetector
    meta = probe(path)
    proxy = output / f'{label}.mp4'
    run(['ffmpeg', '-v', 'error', '-nostdin', '-n', '-i', str(path), '-map', '0:v:0', '-map', '0:a:0?',
         '-vf', 'scale=960:-2', '-c:v', 'libx264', '-preset', 'fast', '-crf', '19', '-pix_fmt', 'yuv420p',
         '-c:a', 'copy', '-movflags', '+faststart', str(proxy)])
    proxy_meta = probe(proxy)
    if abs(proxy_meta['duration'] - meta['duration']) > .1:
        raise ValueError('Proxy duration changed unexpectedly')
    if abs(proxy_meta['fps'] - meta['fps']) > .01:
        raise ValueError('Proxy frame rate changed unexpectedly')
    scenes = detect(str(proxy), AdaptiveDetector(min_scene_len=max(2, round(meta['fps'] * .35))))
    cuts = [{'start': a.seconds, 'end': b.seconds} for a, b in scenes]
    if not cuts:
        cuts = [{'start': 0, 'end': meta['duration']}]
    peaks = []
    if meta['hasAudio']:
        raw = run(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(path), '-vn', '-ac', '1', '-ar', '1000',
                   '-f', 'f32le', 'pipe:1']).stdout
        samples = array.array('f')
        samples.frombytes(raw)
        stride = max(1, len(samples) // 700)
        peaks = [round(max(abs(x) for x in samples[i:i + stride]), 5) for i in range(0, len(samples), stride)]
    return {**meta, 'file': proxy.name, 'sourceName': path.name, 'proxy': proxy_meta,
            'cuts': cuts, 'waveform': peaks, 'cutMethod': 'PySceneDetect AdaptiveDetector; candidates, not semantic scenes'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reference', type=Path, required=True)
    p.add_argument('--candidate', type=Path, required=True)
    p.add_argument('--shots', type=Path, help='Optional existing authored story ranges; not automatically accepted reference cuts')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--title', default='视频拆解与对照')
    a = p.parse_args()
    sources = [a.reference.resolve(strict=True), a.candidate.resolve(strict=True)]
    a.output.mkdir(parents=True, exist_ok=False)
    data = {'schema': 'shot-workbench/1', 'title': a.title, 'media': {}, 'chapters': [],
            'notes': 'Automatic cuts are candidates. Playback tools do not certify semantic or artistic understanding.'}
    for label, path in zip(('reference', 'candidate'), sources):
        print('Preparing', label, flush=True)
        data['media'][label] = prepare(path, label, a.output)
    if a.shots:
        data['chapters'] = json.loads(a.shots.read_text(encoding='utf-8'))['shots']
        for shot in data['chapters']:
            if not 0 <= shot['start'] < shot['end'] <= data['media']['reference']['duration'] + .05:
                raise ValueError('Authored range outside reference duration')
    (a.output / 'data.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    shutil.copyfile(HERE / 'workbench.html', a.output / 'index.html')
    print(json.dumps({'output': str(a.output.resolve()), 'cuts': {k: len(v['cuts']) for k, v in data['media'].items()}}, ensure_ascii=False))


if __name__ == '__main__':
    main()
