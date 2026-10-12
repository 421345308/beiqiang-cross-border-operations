"""Offline integration tests against a supplied real, reviewed package."""
import argparse
import copy
import json
import tempfile
from pathlib import Path
from prepare import prepare


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--package', type=Path, required=True)
    ap.add_argument('--root', type=Path, required=True)
    ap.add_argument('--ffprobe', type=Path, required=True)
    a = ap.parse_args()
    source = json.loads(a.package.read_text(encoding='utf-8-sig'))
    good = prepare(a.package.resolve(), a.root.resolve(), a.ffprobe.resolve())
    assert good['reference_video']['has_audio'] and len(good['reference_images']) >= 2
    assert not good['generation_submitted']
    with tempfile.TemporaryDirectory(prefix='remake-validation-') as tmp:
        local = copy.deepcopy(source)
        local['libtv'] = None
        local_path = Path(tmp) / 'local.json'
        local_path.write_text(json.dumps(local), encoding='utf-8')
        local_result = prepare(local_path, a.root.resolve(), a.ffprobe.resolve())
        assert local_result['platform_binding_status'] == 'unbound_local_preparation'
        assert not local_result['platform_staging_ready'] and local_result['libtv'] is None
        cases = [
            ('stale video binding', {'reference_video': dict(source['reference_video'], sha256='0' * 64)}),
            ('wrong product binding', {'reference_images': [dict(source['reference_images'][0], sha256='0' * 64)]}),
            ('duplicate images', {'reference_images': [source['reference_images'][0]] * 2}),
            ('disposable paid footage', {'planned_discard_windows': [[10, 25]]}),
            ('unreviewed prompt', {'prompt_sha256': '0' * 64}),
            ('partial platform binding', {'libtv': {'project_uuid': 'borrowed'}}),
        ]
        for name, change in cases:
            bad = copy.deepcopy(source)
            bad.update(change)
            path = Path(tmp) / 'case.json'
            path.write_text(json.dumps(bad), encoding='utf-8')
            try:
                prepare(path, a.root.resolve(), a.ffprobe.resolve())
            except ValueError:
                pass
            else:
                raise AssertionError(f'Failed to reject {name}')
    print('Passed: complete AV and unbound research package; rejected stale inputs, duplicate images, planned waste and partial platform bindings.')


if __name__ == '__main__':
    main()
