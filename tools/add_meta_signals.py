# -*- coding: utf-8 -*-
"""给文章补两个 E-E-A-T 信号：可见的发布/更新日期，以及指向创始人实体页的链接。

为什么需要：
1. 上市与金融属 YMYL 领域，AI 引擎与搜索引擎在这类话题上尤其看重「内容有多新」
   与「背后是谁」。此前 158 篇文章**页面上一个日期都没有**，schema 里虽有
   dateModified，但可见层缺失——用户与部分抓取器都读不到。
2. 品牌段里的「廖启捷」是纯文本。链到 founder.html 后，158 篇文章各贡献一条
   指向该 Person 实体的内链，AI 才能把「这些内容」与「这个人的专业背景」关联起来。

日期取自文章自身 Article schema 的 datePublished / dateModified，不新造数据。

用法：
    python tools/add_meta_signals.py --dry-run
    python tools/add_meta_signals.py
"""
import io
import os
import re
import sys
import glob
import json

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)

LD_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
ARTICLE_TYPES = ('Article', 'NewsArticle', 'BlogPosting')
# art-head 的收尾：<div class="en">…</div>\n</div></div>
HEAD_END = re.compile(r'(<div class="en">.*?</div>\s*)(</div></div>)', re.S)
# 品牌段里的纯文本姓名（只替换第一处，且只在未链接时）
NAME_PLAIN = '董事局主席廖启捷领衔'
NAME_LINKED = ('董事局主席<a href="../founder.html" style="color:var(--gold-dim);'
               'font-weight:700;">廖启捷</a>领衔')

DATE_TPL = ('<div class="pubmeta" style="margin-top:18px;padding-top:14px;'
            'border-top:1px solid rgba(201,169,98,.18);font-size:12.5px;'
            'color:#8f8468;letter-spacing:.4px;">'
            '发布于 <time datetime="%s">%s</time>%s'
            '　·　作者 <a href="../founder.html" rel="author" '
            'style="color:var(--gold-dim);">彤鼎集团团队</a>'
            '</div>')


def say(msg):
    try:
        print(msg)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or 'gb18030'
        sys.stdout.write(msg.encode(enc, 'replace').decode(enc, 'replace') + '\n')


def dates_of(s):
    """从文章自身 schema 取日期，取不到返回 (None, None)。"""
    for b in LD_RE.findall(s):
        try:
            j = json.loads(b)
        except ValueError:
            continue
        for o in (j if isinstance(j, list) else [j]):
            if o.get('@type') in ARTICLE_TYPES:
                return o.get('datePublished'), o.get('dateModified')
    return None, None


def cn(d):
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})', d or '')
    return '%s年%s月%s日' % (m.group(1), int(m.group(2)), int(m.group(3))) if m else None


def main():
    dry = '--dry-run' in sys.argv
    n_date = n_link = 0
    skip_date = []
    changed = set()

    for p in sorted(glob.glob('articles/*.html')):
        s = io.open(p, encoding='utf-8').read()
        orig = s

        # 1) 可见日期
        if 'class="pubmeta"' not in s:
            pub, mod = dates_of(s)
            cpub, cmod = cn(pub), cn(mod)
            if cpub:
                extra = ''
                if cmod and cmod != cpub:
                    extra = '　·　更新于 <time datetime="%s">%s</time>' % (mod, cmod)
                block = DATE_TPL % (pub, cpub, extra)
                m = HEAD_END.search(s)
                if m:
                    s = s[:m.end(1)] + block + s[m.end(1):]
                    n_date += 1
                else:
                    skip_date.append((os.path.basename(p), '未匹配 art-head 结构'))
            else:
                skip_date.append((os.path.basename(p), 'schema 无 datePublished'))

        # 2) 创始人实体链接
        if NAME_PLAIN in s and 'founder.html' not in s.split('<div class="brandbox">')[-1]:
            s = s.replace(NAME_PLAIN, NAME_LINKED, 1)
            n_link += 1

        if s != orig:
            changed.add(p)
            if not dry:
                io.open(p, 'w', encoding='utf-8').write(s)

    say('补可见日期：%d 篇' % n_date)
    say('补创始人实体链接：%d 篇' % n_link)
    say('实际改动文件：%d 个' % len(changed))
    if skip_date:
        say('未加日期 %d 篇：' % len(skip_date))
        for f, why in skip_date[:8]:
            say('   %-44s %s' % (f, why))
    if dry:
        say('--dry-run：未写盘。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
