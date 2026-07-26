# -*- coding: utf-8 -*-
"""用文章「结论先行」框的开头改写过短的 meta description。

背景：早期从 docx 批量转换的文章，description 是模板化重复文字（如
「反收购防御机制。反收购防御机制详解。彤鼎集团知识文库。」），只有 27-39 字，
既浪费搜索结果摘要空间，也让 AI 与站内客服的检索匹配缺少可用信息。
而每篇的 `.answer` 结论框本身就是 150-300 字的定义式摘要，是现成的高质量来源。

description 同时供三处使用，因此三处都要同步更新：
  1) <meta name="description">        —— 搜索结果摘要
  2) og:description / twitter:description —— 分享卡片
  3) Article schema 的 description     —— AI 引擎读取

用法：
    python tools/fix_descriptions.py --dry-run   # 预览将改哪些、改成什么
    python tools/fix_descriptions.py             # 实际写入
    python tools/fix_descriptions.py --min 45    # 自定义判定阈值（默认 40 字）
"""
import io
import os
import re
import sys
import json
import glob
import html as H

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)

MIN_LEN = 40        # 短于此长度的描述视为需要改写
TARGET_MIN = 60     # 改写后至少
TARGET_MAX = 135    # 改写后至多


def say(msg):
    try:
        print(msg)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or 'gb18030'
        sys.stdout.write(msg.encode(enc, 'replace').decode(enc, 'replace') + '\n')


CJK = r'　-〿一-鿿＀-￯'


def answer_text(s):
    m = re.search(r'<div class="answer">(.*?)</div>', s, re.S)
    if not m:
        return ''
    t = H.unescape(re.sub(r'<[^>]+>', '', m.group(1)))
    # 先把换行与连续空白压成单个空格
    t = re.sub(r'\s+', ' ', t)
    # 再删掉与中文相邻的空格（那是排版空白），但保留英文词之间的空格，
    # 否则 "Hostile Takeover" 会被粘成 "HostileTakeover"
    t = re.sub(r'(?<=[%s]) | (?=[%s])' % (CJK, CJK), '', t)
    return t.strip()


def make_desc(ans):
    """按句号切分，累加到 TARGET_MIN~TARGET_MAX 之间的完整句子。"""
    if not ans:
        return ''
    parts = [p for p in re.split(r'(?<=[。！？])', ans) if p]
    out = ''
    for p in parts:
        if len(out) + len(p) > TARGET_MAX:
            break
        out += p
        if len(out) >= TARGET_MIN:
            break
    if not out:                      # 首句就超长，硬截并补句号
        out = ans[:TARGET_MAX].rstrip('，、；：') + '。'
    return out


def esc(t):
    return t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def set_attr(s, pat, value):
    return re.sub(pat + r'[^"]*"', lambda m: pat.replace('\\', '') + esc(value) + '"', s, count=1)


def main():
    dry = '--dry-run' in sys.argv
    global MIN_LEN
    if '--min' in sys.argv:
        MIN_LEN = int(sys.argv[sys.argv.index('--min') + 1])

    changed, skipped, noans = [], 0, []
    for p in sorted(glob.glob('articles/*.html')):
        s = io.open(p, encoding='utf-8').read()
        m = re.search(r'<meta name="description" content="([^"]*)"', s)
        if not m:
            continue
        cur = H.unescape(m.group(1)).strip()
        if len(cur) >= MIN_LEN:
            skipped += 1
            continue
        ans = answer_text(s)
        new = make_desc(ans)
        if not new or len(new) <= len(cur):
            noans.append(p)
            continue

        changed.append((p, cur, new))
        if dry:
            continue

        s = set_attr(s, r'<meta name="description" content="', new)
        s = set_attr(s, r'<meta property="og:description" content="', new)
        s = set_attr(s, r'<meta name="twitter:description" content="', new)

        def fix_ld(mm):
            try:
                j = json.loads(mm.group(1))
            except ValueError:
                return mm.group(0)
            objs = j if isinstance(j, list) else [j]
            hit = False
            for o in objs:
                if o.get('@type') in ('Article', 'NewsArticle', 'BlogPosting'):
                    o['description'] = new
                    hit = True
            if not hit:
                return mm.group(0)
            return ('<script type="application/ld+json">'
                    + json.dumps(j, ensure_ascii=False, separators=(',', ':'))
                    + '</script>')

        s = re.sub(r'<script type="application/ld\+json">(.*?)</script>', fix_ld, s, flags=re.S)
        io.open(p, 'w', encoding='utf-8').write(s)

    say('待改写 %d 篇｜描述已达标跳过 %d 篇｜无结论框可用 %d 篇'
        % (len(changed), skipped, len(noans)))
    for p, cur, new in changed[:5]:
        say('\n  %s' % p)
        say('    旧(%d字): %s' % (len(cur), cur))
        say('    新(%d字): %s' % (len(new), new))
    if len(changed) > 5:
        say('\n  …其余 %d 篇同理' % (len(changed) - 5))
    for p in noans:
        say('  [跳过] 无可用结论框: %s' % p)
    if dry:
        say('\n--dry-run：未写盘。')
    else:
        say('\n已写入。请接着执行：python tools/rebuild_kb.py')
    return 0


if __name__ == '__main__':
    sys.exit(main())
