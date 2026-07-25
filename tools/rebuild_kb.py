# -*- coding: utf-8 -*-
"""重建站内智能助手知识库 js/assistant-kb.json，并为漏装的页面补上组件与统计代码。

用途：每次新增文章后运行一次，新文章即自动进入 AI 客服的检索范围。
用法：在仓库根目录执行  python tools/rebuild_kb.py
无输出异常即成功；会打印本次变更摘要。幂等，可反复运行。
"""
import io
import os
import re
import json
import glob
import html
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)

BAIDU_ID = 'e3a889dea1f5f91507c6f71b57b6902a'
GA_ID = 'G-QYZJ4ZZT57'

LD = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
ARTICLE_TYPES = ('Article', 'NewsArticle', 'BlogPosting')


def ld_blocks(text):
    for m in LD.finditer(text):
        try:
            yield json.loads(m.group(1))
        except ValueError:
            continue


def objs(j):
    return j if isinstance(j, list) else [j]


# ---------- 1. 补齐文章 schema 的 description（搬用同页 meta description） ----------
def backfill_descriptions():
    fixed = []
    for p in glob.glob('articles/*.html'):
        s = io.open(p, encoding='utf-8').read()
        md = re.search(r'<meta name="description" content="([^"]*)"', s)
        if not md:
            continue
        desc = html.unescape(md.group(1)).strip()
        if not desc:
            continue
        changed = [False]

        def repl(m):
            try:
                j = json.loads(m.group(1))
            except ValueError:
                return m.group(0)
            touched = False
            for o in objs(j):
                if o.get('@type') in ARTICLE_TYPES and not o.get('description'):
                    o['description'] = desc
                    touched = True
            if not touched:
                return m.group(0)
            changed[0] = True
            return '<script type="application/ld+json">' + \
                   json.dumps(j, ensure_ascii=False, separators=(',', ':')) + '</script>'

        s2 = LD.sub(repl, s)
        if changed[0]:
            io.open(p, 'w', encoding='utf-8').write(s2)
            fixed.append(os.path.basename(p))
    return fixed


# ---------- 2. 生成知识库 ----------
def build_kb():
    qas = []
    if os.path.exists('faq.html'):
        s = io.open('faq.html', encoding='utf-8').read()
        for j in ld_blocks(s):
            for o in objs(j):
                if o.get('@type') == 'FAQPage':
                    for x in o.get('mainEntity', []):
                        qas.append({
                            'q': x['name'],
                            'a': x['acceptedAnswer']['text'].strip(),
                        })
    arts = []
    for p in sorted(glob.glob('articles/*.html')):
        t = io.open(p, encoding='utf-8').read()
        title = desc = None
        for j in ld_blocks(t):
            for o in objs(j):
                if o.get('@type') in ARTICLE_TYPES:
                    title = o.get('headline') or title
                    desc = o.get('description') or desc
        if not title:
            m = re.search(r'<title>(.*?)</title>', t, re.S)
            title = re.sub(r'\s*[|｜].*$', '', m.group(1)).strip() if m else os.path.basename(p)
        arts.append({
            't': title,
            'd': (desc or '')[:180],
            'u': 'articles/' + os.path.basename(p),
        })

    out = 'js/assistant-kb.json'
    old = io.open(out, encoding='utf-8').read() if os.path.exists(out) else ''
    new = json.dumps({'qas': qas, 'arts': arts}, ensure_ascii=False, separators=(',', ':'))
    if not os.path.isdir('js'):
        os.makedirs('js')
    if new != old:
        io.open(out, 'w', encoding='utf-8').write(new)
    return len(qas), len(arts), (new != old), sum(1 for a in arts if not a['d'])


# ---------- 3. 给漏装的页面补 assistant.js 与统计代码 ----------
ANALYTICS = (
    '<!-- Google tag (gtag.js) -->\n'
    '<script async src="https://www.googletagmanager.com/gtag/js?id=%s"></script>\n'
    '<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}'
    "gtag('js',new Date());gtag('config','%s');</script>\n"
    '<!-- Baidu Tongji -->\n'
    '<script>var _hmt=_hmt||[];(function(){var hm=document.createElement("script");'
    'hm.src="https://hm.baidu.com/hm.js?%s";'
    'var s=document.getElementsByTagName("script")[0];s.parentNode.insertBefore(hm,s);})();</script>\n'
) % (GA_ID, GA_ID, BAIDU_ID)


def inject_missing():
    added_js, added_an = [], []
    for p in sorted(glob.glob('*.html')) + sorted(glob.glob('articles/*.html')):
        s = io.open(p, encoding='utf-8').read()
        if '</head>' not in s:
            continue
        orig = s
        if 'assistant.js' not in s:
            prefix = '../' if p.startswith('articles') else ''
            s = s.replace('</head>',
                          '<script defer src="%sjs/assistant.js"></script>\n</head>' % prefix, 1)
            added_js.append(p)
        if 'hm.baidu.com' not in s and 'googletagmanager.com' not in s:
            s = s.replace('</head>', ANALYTICS + '</head>', 1)
            added_an.append(p)
        if s != orig:
            io.open(p, 'w', encoding='utf-8').write(s)
    return added_js, added_an


if __name__ == '__main__':
    filled = backfill_descriptions()
    nq, na, changed, nodesc = build_kb()
    js_add, an_add = inject_missing()

    lines = [
        '知识库：%d 条问答 + %d 篇文章%s' % (nq, na, '（有更新）' if changed else '（无变化）'),
    ]
    if filled:
        lines.append('补齐 schema description：%d 篇 %s' % (len(filled), filled[:5]))
    if nodesc:
        lines.append('警告：仍有 %d 篇文章缺 description，会削弱检索命中率' % nodesc)
    if js_add:
        lines.append('补装 assistant.js：%d 页 %s' % (len(js_add), js_add[:5]))
    if an_add:
        lines.append('补装统计代码：%d 页 %s' % (len(an_add), an_add[:5]))
    if not (filled or js_add or an_add) and not changed:
        lines.append('全部已是最新，无需改动。')

    # Windows 控制台默认 GBK，避免中文输出报错
    msg = '\n'.join(lines)
    try:
        print(msg)
    except UnicodeEncodeError:
        sys.stdout.write(msg.encode('utf-8', 'replace').decode('gbk', 'replace') + '\n')
