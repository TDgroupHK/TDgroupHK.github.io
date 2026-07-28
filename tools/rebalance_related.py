# -*- coding: utf-8 -*-
"""重新分配每篇文章的「相关阅读」，让站内链接权重均匀覆盖全部文章。

问题：相关阅读原本各自挑选，结果高度集中——少数热门文章被指向 20 次以上，
而 67 篇一次都没被指向。没有入链的文章只能靠 library 与 sitemap 被发现，
既拿不到站内权重，也不容易被 AI 判断为主题网络的一部分。

做法：贪心均衡。逐篇挑选相关阅读时，在**同分类**候选里优先选当前入链最少的，
从而把链接摊平。同分类不够时按全站入链最少补齐。

用法：
    python tools/rebalance_related.py --dry-run   # 只看改动与前后分布
    python tools/rebalance_related.py             # 实际写入
    python tools/rebalance_related.py --links 4   # 每篇的相关阅读条数（默认 4）
"""
import io
import os
import re
import sys
import glob
import html as H
from collections import Counter, defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)

UL_RE = re.compile(
    r'(<div class="related".*?<ul style="list-style:none;padding:0;margin:0;font-size:15\.5px;">)(.*?)(</ul>)',
    re.S)

LI_TPL = ('<li style="margin:7px 0;padding-left:16px;position:relative;">'
          '<span style="position:absolute;left:0;top:.6em;width:6px;height:6px;'
          'background:#9a7f45;transform:rotate(45deg);"></span>'
          '<a href="%s" style="color:#6b5426;font-weight:700;">%s</a></li>')


def say(msg):
    try:
        print(msg)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or 'gb18030'
        sys.stdout.write(msg.encode(enc, 'replace').decode(enc, 'replace') + '\n')


def esc(t):
    return (t or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def load_library():
    """library.html 是分类与标题的唯一真源。返回 {slug: (分类, 标题)} 与分类顺序。"""
    lib = io.open('library.html', encoding='utf-8').read()
    cat_of, title_of, cats = {}, {}, []
    for m in re.finditer(r'<h2>([^<]+)</h2>(.*?)(?=<h2>|</section>|\Z)', lib, re.S):
        cat = m.group(1).strip()
        cats.append(cat)
        for slug, title in re.findall(
                r'<li class="has"><a href="articles/([^"]+)">([^<]+?)\s*→?\s*</a></li>',
                m.group(2)):
            cat_of[slug] = cat
            # library.html 里的标题已是 HTML 转义形态（如 D&amp;O），
            # 先还原成纯文本，写出时再统一转义一次，避免变成 &amp;amp;
            title_of[slug] = H.unescape(title.strip())
    return cat_of, title_of, cats


def current_links():
    """读出每篇现有的相关阅读目标，用于统计改动前的分布。"""
    out = {}
    for p in sorted(glob.glob('articles/*.html')):
        s = io.open(p, encoding='utf-8').read()
        m = UL_RE.search(s)
        out[os.path.basename(p)] = (
            re.findall(r'<a href="([a-z0-9-]+\.html)"', m.group(2)) if m else [])
    return out


def distribution(links_map):
    c = Counter()
    for src, tgts in links_map.items():
        for t in tgts:
            c[t] += 1
    return c


def grams(s):
    """中文按字符二元组切分，用于粗略的主题相似度。"""
    s = re.sub(r'[\s，。、：（）()·\-—|｜]', '', (s or '').lower())
    return set(s[i:i + 2] for i in range(len(s) - 1))


def load_text():
    """每篇的标题 + meta description，作为相似度比较的文本。"""
    out = {}
    for p in sorted(glob.glob('articles/*.html')):
        s = io.open(p, encoding='utf-8').read()
        t = re.search(r'<h1>(.*?)</h1>', s, re.S)
        d = re.search(r'<meta name="description" content="([^"]*)"', s)
        out[os.path.basename(p)] = grams(
            (t.group(1) if t else '') + (d.group(1) if d else ''))
    return out


def sim(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / float(min(len(a), len(b)))


def plan(cat_of, title_of, n_links):
    """贪心：入链最少的优先被选（保证覆盖），入链数相同时选主题最相似的（保证相关）。"""
    text = load_text()
    slugs = sorted(f for f in map(os.path.basename, glob.glob('articles/*.html')))
    by_cat = defaultdict(list)
    for s in slugs:
        by_cat[cat_of.get(s, '_未分类')].append(s)

    inbound = Counter({s: 0 for s in slugs})
    new_map = {}
    # 从入链天然最少的分类开始处理，结果更均匀
    order = sorted(slugs, key=lambda s: (len(by_cat[cat_of.get(s, '_未分类')]), s))

    for src in order:
        cat = cat_of.get(src, '_未分类')
        chosen = []

        def take(pool):
            # 入链数为第一排序键（覆盖优先），主题相似度为第二排序键（相关性）
            for cand in sorted(pool, key=lambda x: (inbound[x],
                                                    -sim(text.get(src, set()),
                                                         text.get(x, set())), x)):
                if len(chosen) >= n_links:
                    return
                if cand == src or cand in chosen:
                    continue
                if cand not in title_of:      # 未挂进 library 的不选，避免指向孤儿
                    continue
                chosen.append(cand)

        take(by_cat[cat])                     # 先同分类
        if len(chosen) < n_links:
            take(slugs)                       # 不够再全站补
        for c in chosen:
            inbound[c] += 1
        new_map[src] = chosen
    return new_map, inbound


def main():
    dry = '--dry-run' in sys.argv
    n_links = 4
    if '--links' in sys.argv:
        n_links = int(sys.argv[sys.argv.index('--links') + 1])

    cat_of, title_of, cats = load_library()
    before = current_links()
    dist_before = distribution(before)
    slugs = sorted(map(os.path.basename, glob.glob('articles/*.html')))

    new_map, dist_after = plan(cat_of, title_of, n_links)

    def stats(d):
        vals = [d.get(s, 0) for s in slugs]
        return (min(vals), sum(vals) / len(vals), max(vals),
                sum(1 for v in vals if v == 0))

    b = stats(dist_before)
    a = stats(dist_after)
    say('文章数 %d，每篇相关阅读 %d 条' % (len(slugs), n_links))
    say('')
    say('入链分布      最少   平均   最多   零入链')
    say('  改动前      %4d  %5.1f  %5d   %4d 篇' % (b[0], b[1], b[2], b[3]))
    say('  改动后      %4d  %5.1f  %5d   %4d 篇' % (a[0], a[1], a[2], a[3]))
    say('')

    # 自检
    problems = []
    for src, tgts in new_map.items():
        if len(tgts) != n_links:
            problems.append('%s 只排到 %d 条' % (src, len(tgts)))
        if src in tgts:
            problems.append('%s 自链' % src)
        if len(set(tgts)) != len(tgts):
            problems.append('%s 有重复' % src)
        for t in tgts:
            if not os.path.exists('articles/' + t):
                problems.append('%s -> %s 目标不存在' % (src, t))
    if problems:
        say('自检未通过，已中止：')
        for x in problems[:10]:
            say('  - ' + x)
        return 1
    say('自检通过：无自链、无重复、无死链，每篇均为 %d 条' % n_links)

    if dry:
        say('')
        say('--dry-run：未写盘。示例（前 3 篇）：')
        for src in slugs[:3]:
            say('  %s' % src)
            for t in new_map[src]:
                say('     -> %-42s %s' % (t, title_of.get(t, '?')[:26]))
        return 0

    changed = 0
    for src, tgts in new_map.items():
        p = 'articles/' + src
        s = io.open(p, encoding='utf-8').read()
        m = UL_RE.search(s)
        if not m:
            continue
        li = ''.join(LI_TPL % (t, esc(title_of.get(t, t))) for t in tgts)
        if m.group(2) == li:
            continue
        s = s[:m.start(2)] + li + s[m.end(2):]
        io.open(p, 'w', encoding='utf-8').write(s)
        changed += 1
    say('')
    say('已重写 %d 篇的相关阅读。建议接着执行：python tools/push_indexnow.py --all' % changed)
    return 0


if __name__ == '__main__':
    sys.exit(main())
