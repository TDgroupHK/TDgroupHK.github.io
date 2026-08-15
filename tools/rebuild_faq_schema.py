# -*- coding: utf-8 -*-
"""从 faq.html 的可见问答反向重建 FAQPage schema，保证两者永不脱节。

为什么需要：结构化数据必须与页面可见内容一致，否则属于违规。
而 FAQ 的可见答案改动（补一句话、加一个站内链接）很容易忘记同步 schema——
问题标题还对得上，答案文本已经不一样了，这种失配肉眼看不出来。

做法：以 <details><summary>问题</summary><div class="ans">答案</div></details>
为唯一真源，去标签、还原实体、压空白后生成 FAQPage。

用法：
    python tools/rebuild_faq_schema.py            # 重建（内容无变化则不写盘）
    python tools/rebuild_faq_schema.py --check    # 只检查，有差异退出码 1
"""
import io
import os
import re
import sys
import json
import html as H

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
F = 'faq.html'

PAIR_RE = re.compile(
    r'<details[^>]*><summary>(.*?)</summary><div class="ans">(.*?)</div></details>', re.S)
LD_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)


def say(msg):
    try:
        print(msg)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or 'gb18030'
        sys.stdout.write(msg.encode(enc, 'replace').decode(enc, 'replace') + '\n')


def plain(fragment):
    """标签内文本转纯文本：去标签、还原 HTML 实体、压空白。"""
    t = re.sub(r'<[^>]+>', '', fragment)
    return re.sub(r'\s+', ' ', H.unescape(t)).strip()


def build(s):
    pairs = PAIR_RE.findall(s)
    if not pairs:
        say('错误：faq.html 里没有匹配到任何 <details> 问答块，已中止。')
        sys.exit(1)
    return {
        '@context': 'https://schema.org',
        '@type': 'FAQPage',
        'mainEntity': [{
            '@type': 'Question',
            'name': plain(q),
            'acceptedAnswer': {'@type': 'Answer', 'text': plain(a)},
        } for q, a in pairs],
    }


def current(s):
    for b in LD_RE.findall(s):
        try:
            j = json.loads(b)
        except ValueError:
            continue
        for o in (j if isinstance(j, list) else [j]):
            if o.get('@type') == 'FAQPage':
                return o
    return None


def main():
    check = '--check' in sys.argv
    s = io.open(F, encoding='utf-8').read()
    want = build(s)
    have = current(s)

    n = len(want['mainEntity'])
    if have is None:
        say('faq.html 里没有 FAQPage schema。')
    else:
        same = json.dumps(have, ensure_ascii=False, sort_keys=True) == \
               json.dumps(want, ensure_ascii=False, sort_keys=True)
        if same:
            say('FAQPage schema 与可见问答一致（%d 条），无需改动。' % n)
            return 0
        hn = len(have.get('mainEntity', []))
        say('检测到失配：可见问答 %d 条，schema %d 条；内容也可能有差异。' % (n, hn))
        # 指出具体差在哪，便于判断是不是预期内的改动
        hmap = {q['name']: q['acceptedAnswer']['text'] for q in have.get('mainEntity', [])}
        for q in want['mainEntity']:
            if q['name'] not in hmap:
                say('  + 新增问答：%s' % q['name'][:40])
            elif hmap[q['name']] != q['acceptedAnswer']['text']:
                say('  ~ 答案有改动：%s' % q['name'][:40])
        wnames = set(q['name'] for q in want['mainEntity'])
        for name in hmap:
            if name not in wnames:
                say('  - schema 里多出（页面已无）：%s' % name[:40])

    if check:
        say('--check：仅检查，未写盘。')
        return 1

    def repl(m):
        try:
            j = json.loads(m.group(1))
        except ValueError:
            return m.group(0)
        objs = j if isinstance(j, list) else [j]
        if any(o.get('@type') == 'FAQPage' for o in objs):
            return ('<script type="application/ld+json">'
                    + json.dumps(want, ensure_ascii=False, separators=(',', ':'))
                    + '</script>')
        return m.group(0)

    if have is None:
        s2 = s.replace('</head>', '<script type="application/ld+json">'
                       + json.dumps(want, ensure_ascii=False, separators=(',', ':'))
                       + '</script></head>', 1)
    else:
        s2 = LD_RE.sub(repl, s)

    io.open(F, 'w', encoding='utf-8').write(s2)
    say('已重建 FAQPage schema：%d 条问答。' % n)
    return 0


if __name__ == '__main__':
    sys.exit(main())
