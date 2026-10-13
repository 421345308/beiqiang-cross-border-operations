"""Validate a whole-video remake package. No network, generation or model inference."""
import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def resolve(root, value):
    path = Path(value)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def prepare(package_path, root, ffprobe):
    package = json.loads(package_path.read_text(encoding='utf-8-sig'))
    if package.get('provider') != 'LibTV' or package.get('model') != 'Seedance 2.5':
        raise ValueError('This adapter supports only the inspected LibTV Seedance 2.5 contract.')
    if package.get('task') != 'reference_generation_not_video_edit':
        raise ValueError('Video editing and reference generation have different contracts.')
    duration = package['duration_seconds']
    if not isinstance(duration, int) or isinstance(duration, bool) or not 4 <= duration <= 30:
        raise ValueError('Output duration must be 4–30 whole seconds.')
    if package.get('count') != 1:
        raise ValueError('This workflow stages exactly one whole output, not a paid batch.')
    if package.get('resolution') not in ('480p', '720p', '1080p'):
        raise ValueError('Unsupported resolution.')
    if package.get('ratio') not in ('16:9', '4:3', '1:1', '3:4', '9:16', '21:9', 'adaptive'):
        raise ValueError('Unsupported ratio.')
    video = package['reference_video']
    video_path = resolve(root, video['path'])
    raw = subprocess.run([str(ffprobe), '-v', 'error', '-show_format', '-show_streams',
                          '-of', 'json', str(video_path)], check=True, capture_output=True,
                         encoding='utf-8', timeout=30)
    probe = json.loads(raw.stdout)
    picture = next(s for s in probe['streams'] if s['codec_type'] == 'video')
    seconds = float(probe['format']['duration'])
    if not math.isfinite(seconds) or seconds <= 0 or seconds > 30:
        raise ValueError('Whole source must fit this inspected <=30s workflow; do not silently trim.')
    if abs(seconds - float(video['duration_seconds'])) > 0.1:
        raise ValueError('Reference clock changed.')
    has_audio = any(s['codec_type'] == 'audio' for s in probe['streams'])
    if not has_audio:
        raise ValueError('This AV-reference workflow requires the complete source audio track.')
    video_sha = digest(video_path)
    if not video.get('sha256') or video_sha != video['sha256']:
        raise ValueError('Reference-video hash missing or mismatched.')
    prompt_path = resolve(root, package['prompt_path'])
    prompt_sha = digest(prompt_path)
    if prompt_sha != package.get('prompt_sha256'):
        raise ValueError('Prompt changed: review and refresh its binding first.')
    prompt = prompt_path.read_text(encoding='utf-8-sig')
    images = []
    source_hashes = set()
    for i, item in enumerate(package['reference_images'], 1):
        path = resolve(root, item['path'])
        sha = digest(path)
        if sha != item.get('sha256'):
            raise ValueError(f'Product reference {i} missing or changed.')
        if sha in source_hashes:
            raise ValueError('Duplicate product images: supply useful distinct views.')
        if not item.get('status', '').startswith('visually_checked_real_same_sku'):
            raise ValueError('Every product reference needs actual same-SKU visual review.')
        if item['binding'] not in prompt:
            raise ValueError(f'Prompt omits input role {item["binding"]}.')
        source_hashes.add(sha)
        images.append(dict(item, path=str(path), sha256=sha, bytes=path.stat().st_size))
    if not images or '@视频1' not in prompt:
        raise ValueError('Need an actual video reference and product images, explicitly bound in prompt.')
    if package.get('planned_discard_windows', []) != []:
        raise ValueError('Whole-output workflow cannot pre-plan disposable paid footage.')
    # Research packages can be checked without uploading a new reference or
    # borrowing another template's account nodes. Binding happens separately.
    platform = package.get('libtv')
    if platform is not None:
        keys = ('project_uuid', 'draft_node_id', 'reference_video_node_id')
        if not isinstance(platform, dict) or any(
                not isinstance(platform.get(key), str) or not platform[key].strip()
                for key in keys):
            raise ValueError('Provide all actual LibTV bindings, or libtv=null for local preparation.')
    width, height = picture['width'], picture['height']
    return {
        'schema': 'reference-remake-prepared-v1',
        'package_path': str(package_path), 'package_sha256': digest(package_path),
        'project_root': str(root), 'product_id': package['product_id'],
        'reference_video': dict(video, path=str(video_path), sha256=video_sha,
                               bytes=video_path.stat().st_size, width=width, height=height,
                               has_audio=has_audio, duration_seconds=seconds),
        'reference_images': images, 'prompt_path': str(prompt_path), 'prompt_sha256': prompt_sha,
        'settings': dict(model='Seedance 2.5', modeType='mixed2video', count=1,
                         ratio=package['ratio'], resolution=package['resolution'],
                         duration=duration, enableSound='on' if package['sound'] else 'off'),
        'generation_authorized': False, 'generation_submitted': False,
        'planned_discard_windows': [],
        'checks': ['complete_av_source', 'source_hash', 'same_sku_image_hashes',
                   'distinct_product_views', 'prompt_role_bindings', 'single_whole_output'],
        'limits': ['input_integrity_only_not_creative_or_motion_acceptance',
                   'platform_quote_and_uploaded_readback_required',
                   'generated_result_must_be_watched_and_listened_to'],
        'platform_binding_status': 'bound_requires_readback' if platform else 'unbound_local_preparation',
        'platform_staging_ready': bool(platform),
        'libtv': platform,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--package', required=True, type=Path)
    ap.add_argument('--root', required=True, type=Path)
    ap.add_argument('--ffprobe', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    a = ap.parse_args()
    result = prepare(a.package.resolve(), a.root.resolve(), a.ffprobe.resolve())
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'input_validation': 'passed', 'images': len(result['reference_images']),
                      'source_seconds': result['reference_video']['duration_seconds'],
                      'output_seconds': result['settings']['duration'],
                      'generation_submitted': False}, ensure_ascii=False))


if __name__ == '__main__':
    main()
