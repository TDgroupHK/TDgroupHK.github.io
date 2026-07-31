# -*- coding: utf-8 -*-
"""复核完一篇文章后的收尾：记账，并且**只在正文真的变了**时才更新 dateModified。

这是本机制的安全阀。为了「显得新」而批量刷 dateModified 是搜索引擎明确打击的
content refresh spam：schema 说 8 月更新、正文一个字没动，被识别出来是负面信号，
比不更新更糟。所以本脚本以正文内容哈希为准，**fail-closed**：

- 正文哈希变了      → 更新 schema 的 dateModified + 页面可见的「更新于」，并记账
- 正文哈希没变      → 拒绝改日期，只记「本次已复核」（--reviewed-only 明示同意）
- 没给 --reviewed-only 又没改动 → 退出码 1，提醒你要么真去改，要么明说没得改

「已复核」记在 tools/freshness_ledger.json，freshness_audit.py 用它排队，
所以确认过无需修改的文章会自然排到后面，不会每周反复出现。

用法：
    python tools/bump_modified.py articles/us-listing-cost.html
    python tools/bump_modified.py articles/family-office.html --reviewed-only
    python tools/bump_modified.py --status
"""
import io
import os
import re
import sys
import json
import argparse
import datetime

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
sys.path.insert(0, os.path.join(REPO, 'tools'))
from freshness_audit import body_hash, dates_of, title_of, LEDGER, say  # noqa: E402

LD_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)


def cn(x):
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})', x or '')
    return '%s年%s月%s日' % (m.group(1), int(m.group(2)), int(m.group(3))) if m else None


def load():
    return json.load(io.open(LEDGER, encoding='utf-8')) if os.path.exists(LEDGER) else {}


def save(led):
    io.open(LEDGER, 'w', encoding='utf-8').write(
        json.dumps(led, ensure_ascii=False, indent=1, sort_keys=True))


def set_modified(s, new):
    """改 schema 的 dateModified，以及页面可见的「更新于」。"""
    n = [0]

    def fix_ld(m):
        blk = m.group(1)
        try:
            j = json.loads(blk)
        except ValueError:
            return m.group(0)
        changed = [False]

        def walk(o):
            if isinstance(o, dict):
                if 'dateModified' in o:
                    o['dateModified'] = new
                    changed[0] = True
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
        walk(j)
        if not changed[0]:
            return m.group(0)
        n[0] += 1
        return ('<script type="application/ld+json">'
                + json.dumps(j, ensure_ascii=False, separators=(',', ':'))
                + '</script>')

    s = LD_RE.sub(lambda m: fix_ld(m), s)

    # 可见层：pubmeta 里的「更新于 <time>」；没有就补一段
    m = re.search(r'(<div class="pubmeta".*?)(</div>)', s, re.S)
    if m:
        seg = m.group(1)
        upd = '　·　更新于 <time datetime="%s">%s</time>' % (new, cn(new))
        if '更新于' in seg:
            seg2 = re.sub(r'　·　更新于 <time datetime="[^"]*">[^<]*</time>', upd, seg)
        else:
            # 插在「发布于…</time>」之后，作者链接之前
            seg2 = re.sub(r'(发布于 <time[^>]*>[^<]*</time>)', r'\1' + upd, seg, count=1)
        s = s[:m.start(1)] + seg2 + s[m.end(1):]
    return s, n[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('paths', nargs='*')
    ap.add_argument('--reviewed-only', action='store_true',
                    help='确认已复核但内容无需修改：只记账，不动 dateModified')
    ap.add_argument('--baseline', action='store_true',
                    help='给全库建内容哈希基线。只记哈希，不写 last_reviewed——'
                         '建基线不等于复核过，写了会让 158 篇同时归零、轮换失效')
    ap.add_argument('--status', action='store_true')
    a = ap.parse_args()

    led = load()
    today = datetime.date.today().isoformat()

    if a.baseline:
        import glob
        n = 0
        for p in sorted(glob.glob('articles/*.html')):
            slug = os.path.basename(p)[:-5]
            s = io.open(p, encoding='utf-8').read()
            rec = led.setdefault(slug, {})
            if rec.get('body_hash'):
                continue
            rec['body_hash'] = body_hash(s)
            rec['title'] = title_of(s)
            rec.setdefault('last_reviewed', None)
            rec.setdefault('last_substantive', None)
            n += 1
        save(led)
        say('建立内容哈希基线：新增 %d 篇，台账共 %d 篇。'
            '未写 last_reviewed —— 排队仍按 dateModified 起算。' % (n, len(led)))
        return 0

    if a.status:
        say('复核台账 %s（%d 条）' % (LEDGER, len(led)))
        for k in sorted(led, key=lambda x: led[x].get('last_reviewed', '')):
            r = led[k]
            say('  %-40s 复核 %s  改动 %s' % (
                k[:40], r.get('last_reviewed', '-'), r.get('last_substantive', '从未')))
        return 0

    if not a.paths:
        ap.error('要么给文章路径，要么用 --status')

    rc = 0
    for p in a.paths:
        p = p.replace('\\', '/')
        if not os.path.exists(p):
            say('找不到 %s' % p)
            rc = 1
            continue
        slug = os.path.basename(p)[:-5]
        s = io.open(p, encoding='utf-8').read()
        h = body_hash(s)
        prev = led.get(slug, {}).get('body_hash')
        pub, mod = dates_of(s)

        if prev is None:
            # 首次入账：没有基线可比，只记基线，不动日期。
            led.setdefault(slug, {}).update(
                {'body_hash': h, 'last_reviewed': today,
                 'last_substantive': led.get(slug, {}).get('last_substantive'),
                 'title': title_of(s)})
            say('[基线] %s —— 首次入账，记录内容哈希，未改日期。' % slug)
            continue

        if h == prev:
            if a.reviewed_only:
                led[slug]['last_reviewed'] = today
                say('[已复核] %s —— 正文无变化，dateModified 保持 %s。' % (slug, mod))
            else:
                say('[拒绝] %s —— 正文与上次完全一致，不允许只改日期。' % slug)
                say('        要么真去改内容，要么加 --reviewed-only 明示「核过，无需改」。')
                rc = 1
            continue

        s2, k = set_modified(s, today)
        if k == 0:
            say('[跳过] %s —— schema 里没有 dateModified 字段，请先补。' % slug)
            rc = 1
            continue
        io.open(p, 'w', encoding='utf-8').write(s2)
        led.setdefault(slug, {}).update(
            {'body_hash': h, 'last_reviewed': today, 'last_substantive': today,
             'title': title_of(s)})
        say('[已更新] %s —— 正文有实质改动，dateModified %s → %s（改了 %d 段 schema）'
            % (slug, mod, today, k))

    save(led)
    return rc


if __name__ == '__main__':
    sys.exit(main())
