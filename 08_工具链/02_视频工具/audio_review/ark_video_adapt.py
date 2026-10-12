"""Cloud-only Doubao video understanding and Seedance adaptation via official Ark Chat API.

Requires an existing ARK_API_KEY and explicit upload/call authorization. Never
activates a model, downloads weights, generates video or retries a request.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.request

ENDPOINT = 'https://ark.cn-beijing.volces.com/api/v3/chat/completions'
MODEL = 'doubao-seed-2-1-lite-260915'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('video', type=Path)
    parser.add_argument('--prompt-file', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--authorized-upload', action='store_true')
    parser.add_argument('--authorized-call', action='store_true')
    parser.add_argument('--direct', action='store_true')
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    if not args.prepare_only and not (args.authorized_upload and args.authorized_call):
        parser.error('Explicit upload and metered understanding-call authorization required.')
    if args.video.suffix.lower() != '.mp4' or args.video.stat().st_size > 25_000_000:
        parser.error('This bounded client accepts only MP4 files up to 25 MB.')
    probe = json.loads(subprocess.check_output(
        ['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(args.video)], encoding='utf-8'))
    duration = float(probe['format']['duration'])
    if duration > 30 or not all(any(s['codec_type'] == k for s in probe['streams']) for k in ['video', 'audio']):
        parser.error('This client requires a complete video with audio, at most 30 seconds.')
    if (args.output / 'manifest.json').exists():
        parser.error('Existing attempt cannot be overwritten.')
    prompt = args.prompt_file.read_text(encoding='utf-8')
    if len(prompt) > 8000:
        parser.error('Prompt exceeds bounded request size.')
    request = {
        'model': MODEL,
        'messages': [{'role': 'user', 'content': [
            {'type': 'video_url', 'video_url': {'url': 'data:video/mp4;base64,' + base64.b64encode(args.video.read_bytes()).decode('ascii'), 'fps': 2}},
            {'type': 'text', 'text': prompt}]}],
        'max_tokens': 3000,
        'thinking': {'type': 'disabled'},
        'stream': False,
    }
    metadata = json.loads(json.dumps(request))
    metadata['messages'][0]['content'][0]['video_url']['url'] = '<whole MP4 base64 omitted>'
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'request.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    manifest = {'endpoint': ENDPOINT, 'model': MODEL, 'source': str(args.video.absolute()),
                'source_sha256': hashlib.sha256(args.video.read_bytes()).hexdigest(), 'duration_seconds': duration,
                'source_bytes': args.video.stat().st_size, 'native_video_with_audio': True,
                'all_video_frames_seen': False, 'server_fps': 2, 'paid_video_generation': False,
                'understanding_call_may_be_metered': True, 'status': 'prepared',
                'upload_authorized_flag': args.authorized_upload, 'call_authorized_flag': args.authorized_call,
                'semantic_verification': 'unverified'}
    def save():
        (args.output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    save()
    if args.prepare_only:
        print('Prepared metadata only; no API contacted.')
        return
    key = os.environ.get('ARK_API_KEY', '')
    if not key or any(x in key.lower() for x in ['your_', 'placeholder', 'xxxx', 'changeme']):
        parser.error('Existing ARK_API_KEY required; never put the key in command arguments.')
    handlers = [NoRedirect()]
    if args.direct:
        handlers.append(urllib.request.ProxyHandler({}))
    opener = urllib.request.build_opener(*handlers)
    payload = json.dumps(request, ensure_ascii=False).encode('utf-8')
    api_request = urllib.request.Request(ENDPOINT, data=payload, headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key})
    start = time.monotonic()
    try:
        with opener.open(api_request, timeout=150) as response:
            raw = response.read().decode('utf-8')
            manifest['http_status'] = response.status
            manifest['request_id'] = response.headers.get('X-Request-Id')
        (args.output / 'response.json').write_text(raw, encoding='utf-8')
        result = json.loads(raw)
        text = result['choices'][0]['message'].get('content') or ''
        if not text.strip():
            raise RuntimeError('No textual adaptation returned; see untouched response.')
        (args.output / 'response.txt').write_text(text, encoding='utf-8')
        usage = result.get('usage', {})
        audio_tokens = usage.get('prompt_tokens_details', {}).get('audio_tokens')
        manifest.update(status='answered_unverified', usage=usage,
                        audio_input_metering='confirmed' if audio_tokens else 'unconfirmed',
                        model_returned=result.get('model'), finish_reason=result['choices'][0].get('finish_reason'))
        print(text)
    except urllib.error.HTTPError as error:
        # Retain the service error, never a request header or credential.
        message = error.read().decode('utf-8', errors='replace').replace(key, '<redacted>')
        (args.output / 'error.json').write_text(message, encoding='utf-8')
        manifest.update(status='failed', http_status=error.code, error='HTTPError; see saved service response')
        print('Official API rejected request:', error.code, message[:1200])
        raise SystemExit(1)
    except Exception as error:
        manifest.update(status='failed', error=f'{type(error).__name__}: {str(error).replace(key, "<redacted>")}')
        raise
    finally:
        manifest['elapsed_seconds'] = time.monotonic() - start
        save()


if __name__ == '__main__':
    main()
