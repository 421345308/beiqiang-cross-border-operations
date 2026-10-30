"""Manually collect a private status snapshot; never upload or mutate platforms.

Usage input: {"observed_at": "ISO timestamp with timezone", "usage": <account usage tool result>}.
Only explicit allowlisted aggregate fields are exported. Credits balance is not quota.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from urllib.request import Request, urlopen

APP = Path(__file__).resolve().parent.parent
ROOT = APP.parents[1]
ALI = '02_Alibaba运营/01_店铺与全店诊断/经营复核.json'
DIAG = '02_Alibaba运营/01_店铺与全店诊断/店铺经营诊断.md'
GSC = '03_独立站/03_搜索与渠道数据/google-www-beiqiang-online.json'
RELEASE = 'https://www.beiqiang.online/release.json'


def iso(value):
    """Reject timezone-less/date-only values rather than inventing observation times."""
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return dt.astimezone(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z') if dt.tzinfo else None
    except ValueError:
        return None


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def codex_status(path=None):
    result = dict(observed_at=None, source='Codex account usage 工具人工回读', windows=[],
                  reset_credits=None, available=None, limitations=[])
    if path is None or not path.is_file():
        result['limitations'].append('未读取额度；未提供可用 usage 输入文件。')
        return result
    try:
        data = read_json(path)
        result['observed_at'] = iso(data.get('observed_at'))
        if not result['observed_at']:
            raise ValueError('observed_at must include a timezone')
        usage = data['usage']
        allowed = usage.get('ordinaryUsageAllowed')
        result['available'] = allowed if isinstance(allowed, bool) else None
        buckets = usage.get('rateLimitsByLimitId')
        if not isinstance(buckets, dict) or not buckets:
            legacy = usage.get('rateLimits') or {}
            buckets = {str(legacy.get('limitId') or 'codex'): legacy}
        omitted = 0
        for bucket, limits in buckets.items():
            if not isinstance(limits, dict):
                continue
            for key, window_label in (('primary', '主额度窗口'), ('secondary', '次额度窗口')):
                label = f'{bucket[:70]} · {window_label}'
                window = limits.get(key)
                if not isinstance(window, dict):
                    continue
                used, minutes = window.get('usedPercent'), window.get('windowDurationMins')
                if not number(used) or not 0 <= used <= 100 or not isinstance(minutes, int) or isinstance(minutes, bool) or not 0 < minutes <= 525600:
                    if len(result['limitations']) < 8:
                        result['limitations'].append(f'{label}字段无效，未导入。')
                    continue
                reset = window.get('resetsAt')
                try:
                    resets_at = datetime.fromtimestamp(reset, timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z') if number(reset) else iso(reset)
                except (ValueError, OverflowError, OSError):
                    resets_at = None
                if len(result['windows']) >= 8:
                    omitted += 1
                    continue
                result['windows'].append(dict(label=label, used_percent=used, window_minutes=minutes, resets_at=resets_at))
        if omitted:
            result['limitations'].append(f'最多展示8个独立额度窗口，另有{omitted}个窗口未展示；不同桶未合并。')
        count = (usage.get('rateLimitResetCredits') or {}).get('availableCount')
        if isinstance(count, int) and not isinstance(count, bool) and 0 <= count <= 9007199254740991:
            result['reset_credits'] = count
        result['limitations'].append('人工回读快照，不自动刷新；credits 余额不代表套餐额度。')
        if not result['windows']:
            result['limitations'].append('工具未返回可识别额度窗口。')
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        result.update(observed_at=None, windows=[], reset_credits=None, available=None)
        result['limitations'] = ['usage 输入无效，额度未知。']
    return result


def alibaba_status(root):
    result = dict(id='alibaba', title='国际站', observed_at=None, period=None, source=f'{ALI}；{DIAG}',
                  summary='未接入可核经营快照', metrics=[], limitations=['本地历史回读，不是实时平台数据；不刷新或修改商品。'])
    try:
        data = read_json(root / ALI)['summary']
        result.update(observed_at=iso(data.get('observed_at')), period=data.get('period'), summary='最近完整后台经营复核')
        labels = {'search_impressions': '搜索曝光', 'search_clicks': '搜索点击', 'visitors': '商品行访客', 'inquiries': '商品行询盘', 'tm_buyers': '商品行TM买家', 'marketing_clicks': '营销点击'}
        result['metrics'] = [{'label': label, 'value': str(data['totals'][key])} for key, label in labels.items() if number(data.get('totals', {}).get(key))]
        result['limitations'] += [str(data.get('timezone', '统计时区未记录')), str(data.get('scope', '统计范围未记录')), '询盘、TM与营销点击口径不同，不拼接为转化漏斗。']
        # Read the narrative source too; it remains the authority for interpretation.
        (root / DIAG).read_text(encoding='utf-8-sig')
    except (OSError, ValueError, KeyError, TypeError):
        result['limitations'].append('本地经营来源未完整读取，需核原档。')
    return result


def fetch_release():
    request = Request(RELEASE, headers={'Cache-Control': 'no-cache', 'User-Agent': 'Beiqiang-Status-Snapshot/1.0'})
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read(65537).decode('utf-8'))


def website_status(root, observed_at, fetcher=fetch_release):
    result = dict(id='website', title='独立站', observed_at=None, period=None, source=f'{RELEASE}；{GSC}',
                  summary='公开发布状态未接通', metrics=[], limitations=['公开发布回读只证明本次端点访问，不代表全站健康、收录或询盘。'])
    try:
        release = fetcher()
        if not isinstance(release.get('releaseId'), str) or not release['releaseId']:
            raise ValueError('missing releaseId')
        result.update(observed_at=observed_at, summary='公开发布标记已读取')
        result['metrics'].append({'label': '公开版本', 'value': release['releaseId']})
        if iso(release.get('releasedAt')):
            result['metrics'].append({'label': '版本发布时间', 'value': iso(release['releasedAt'])})
    except (OSError, ValueError, TypeError, AttributeError):
        result['limitations'].append('公开 release.json 读取失败；未使用旧版本冒充本次结果。')
    try:
        data = read_json(root / GSC)
        perf = data['performance']
        result['period'] = f"{perf['visibleChartStart']}~{perf['visibleChartEnd']} ({perf.get('dateBasis', '时区未记录')})"
        for key, label in (('impressions', 'GSC历史曝光'), ('clicks', 'GSC历史点击')):
            if number(perf.get(key)):
                result['metrics'].append({'label': label, 'value': str(perf[key])})
        result['limitations'].append(f"GSC档案观察日 {data.get('observedAt', '未知')}，不是今日搜索数据；尚未刷新订阅或接入实时统计。")
    except (OSError, ValueError, KeyError, TypeError):
        result['limitations'].append('GSC档案未接入；搜索效果未知。')
    return result


def prepare(root=ROOT, usage_file=None, fetcher=fetch_release):
    now = datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
    return dict(schema_version=1, observed_at=now,
                channels=[alibaba_status(root), website_status(root, now, fetcher)], codex=codex_status(usage_file))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--usage-file', type=Path, help='Explicit account usage tool snapshot; never read credentials')
    args = parser.parse_args()
    output = APP / '.local/status-import.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(prepare(usage_file=args.usage_file), ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'path': str(output), 'schema_version': 1, 'uploaded': False}, ensure_ascii=False))


if __name__ == '__main__':
    main()
