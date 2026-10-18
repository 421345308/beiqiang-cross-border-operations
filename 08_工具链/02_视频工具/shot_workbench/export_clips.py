"""Export actual playable shot clips from verified workbench proxies, not stills."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workbench', type=Path, required=True)
    p.add_argument('--kind', choices=['reference', 'candidate'], required=True)
    p.add_argument('--mode', choices=['auto', 'chapters', 'custom'], default='auto')
    p.add_argument('--notes', type=Path)
    p.add_argument('--index', type=int, help='One-based selected segment; omit for all')
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    root = a.workbench.resolve(strict=True)
    data = json.loads((root / 'data.json').read_text(encoding='utf-8'))
    media = data['media'][a.kind]
    source = root / media['file']
    if hashlib.sha256(source.read_bytes()).hexdigest() != media['proxy']['sha256']:
        raise ValueError('Proxy changed; rebuild the workbench before export')
    if a.mode == 'custom':
        if not a.notes:
            p.error('--notes required for custom segments')
        notes = json.loads(a.notes.read_text(encoding='utf-8'))
        if any(notes['sources'][k] != data['media'][k]['sha256'] for k in ('reference', 'candidate')):
            raise ValueError('Notes belong to different video versions')
        ranges = notes['custom']
        if a.kind == 'candidate':
            ranges = [dict(s, start=s['start']+notes['notes'].get(f'custom:{i}', {}).get('offset', 0),
                           end=s['end']+notes['notes'].get(f'custom:{i}', {}).get('offset', 0)) for i, s in enumerate(ranges)]
    else:
        ranges = media['cuts'] if a.mode == 'auto' else data['chapters']
    indexed = list(enumerate(ranges, 1))
    if a.index:
        if not 1 <= a.index <= len(indexed):
            p.error('--index outside available segments')
        indexed = [indexed[a.index - 1]]
    if not indexed:
        raise ValueError('No segments to export')
    fps = media['fps']
    for _, s in indexed:
        if not 0 <= s['start'] < s['end'] <= media['duration'] + .001:
            raise ValueError('Export range outside video')
    a.output.mkdir(parents=True, exist_ok=False)
    records = []
    for i, s in indexed:
        start = round(s['start'] * fps) / fps
        end = round(s['end'] * fps) / fps
        duration = end - start
        out = a.output / f'{a.kind}-{i:02}.mp4'
        command = ['ffmpeg', '-v', 'error', '-nostdin', '-n', '-i', str(source), '-ss', f'{start:.9f}',
                   '-t', f'{duration:.9f}', '-map', '0:v:0', '-map', '0:a:0?', '-c:v', 'libx264',
                   '-preset', 'fast', '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'aac']
        if media['hasAudio']:
            fade = min(.03, duration / 4)
            command += ['-af', f'afade=t=in:st=0:d={fade},afade=t=out:st={duration-fade}:d={fade}']
        subprocess.run(command + ['-movflags', '+faststart', str(out)], check=True, capture_output=True)
        records.append({'file': out.name, 'sourceStart': start, 'sourceEnd': end,
                        'requested': s, 'audioEdgeFadeSeconds': min(.03, duration/4) if media['hasAudio'] else 0})
    (a.output / 'clips.json').write_text(json.dumps({'source': media['sourceName'], 'sourceSha256': media['sha256'],
        'proxySha256': media['proxy']['sha256'], 'mode': a.mode, 'clips': records,
        'note': 'Review derivatives from proxy; frame-aligned bounds; short audio edge fades. Original unchanged.'},
        ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Exported {len(records)} complete clips')


if __name__ == '__main__':
    main()
