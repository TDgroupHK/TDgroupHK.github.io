# -*- coding: utf-8 -*-
"""把一份简单 Markdown 稿件转成合规的官网文章页，并完成全部上线动作。

设计目的：让外部工具（或人）只负责写正文，机械且易错的部分全部由本脚本承担——
HTML 骨架、meta、JSON-LD、library 挂载、sitemap、相关阅读、知识库、llms.txt。
其中任何一步漏掉都不会报错，但会让文章对搜索引擎或 AI 侧不可见（孤儿文章）。

用法：
    python tools/new_article.py 稿件.md              # 生成并上线（不含 git commit）
    python tools/new_article.py 稿件.md --dry-run    # 只校验与预览，不写盘
    python tools/new_article.py 稿件.md --date 2026-07-26

稿件格式（--sample 可打印模板）：
    标题: 文章标题
    slug: english-slug-here
    分类: 上市路径与门槛
    栏目: 上市路径 LISTING PATH
    副标题: 一句话副标题
    描述: 120-160 字中文摘要，会用作 meta description 与 schema description
    英文摘要: 80-120 words English abstract.

    结论: 150-300 字定义式完整答案，含具体数字。

    ## 一、章节标题
    段落一。
    段落二。

    ## 二、章节标题
    段落一。
"""
import io
import os
import re
import sys
import json
import datetime
import subprocess

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)

TEMPLATE = 'articles/vie-structure.html'
SITE = 'https://tdgroup.hk'

# CLAUDE.md 第三节禁用表述。排名义的「第一」单独处理，避免误伤「第一年」「第一步」。
FORBIDDEN = ['顶级', '最强', '行业领先', '著名', '知名', '保本', '保收益', '稳赚',
             '承诺回报', '点仓', '坐庄', '拉盘']
RANK_FIRST = re.compile(r'(?:全球|国内|业内|行业|市场|中国)\s*第一|第一\s*(?:品牌|机构|平台|投行|选择)')
# 股票代码形态：美股 4-5 位大写、港股 5 位数字带引号、A股 6 位数字
TICKER = re.compile(r'\((?:NASDAQ|NYSE|SEHK|HKEX)[:：]\s*[A-Z0-9.]{1,6}\)|股票代码')

CAT_LABELS = {
    '初创与早期融资': '初创融资 EARLY STAGE',
    '上市路径与门槛': '上市路径 LISTING PATH',
    '跨境架构与合规': '架构合规 STRUCTURING',
    '上市执行': '上市执行 EXECUTION',
    '融资与条款': '融资条款 FINANCING',
    '挂牌之后': '挂牌之后 POST-LISTING',
    '资本运作': '资本运作 CAPITAL OPS',
    '财富与传承': '财富传承 WEALTH & LEGACY',
    '企业家成长': '企业家成长 FOUNDER GROWTH',
}

SAMPLE = """标题: 纳斯达克上市的公众持股人数要求怎么满足
slug: nasdaq-public-holders-howto
分类: 上市路径与门槛
栏目: 上市路径 LISTING PATH
副标题: 300名圆整股股东这道硬指标的达成路径与常见误区
描述: 纳斯达克资本市场要求首次上市时公众持股人数不少于300名圆整股股东，这是一条不可豁免的硬指标。本文说明圆整股股东的认定口径、常见的达成路径、以及为什么临近挂牌才启动往往来不及。
英文摘要: Nasdaq Capital Market requires at least 300 round lot holders at the time of initial listing. This article explains how round lot holders are defined, the practical routes to meet the threshold, and why starting late in the process often fails.

结论: 公众持股人数要求，是指企业首次在纳斯达克上市时，必须拥有不少于300名持有100股及以上的圆整股股东（round lot holders）。这一指标与净利润、股东权益等财务标准并列，属于上市资格的组成部分，交易所不予豁免。实践中它常被低估：财务指标可以通过报表体现，而股东人数需要真实的持股分散过程，通常需要在递表前6至12个月开始安排，临近挂牌才启动往往无法完成。关键在于，这是一个时间问题而非资金问题。

## 一、圆整股股东的认定口径
结论先行：只有持有100股及以上的账户才计入，且必须是真实受益人。
交易所要求的不是账户数量，而是圆整股股东数量。持有99股及以下的账户不计入这一指标，无论账户总数多少。
承销商在提交上市申请时需提供股东名册，交易所会核查持股分布的真实性。因此，本质上这一指标考察的是股票是否具备真实的公众持有基础。

## 二、常见的达成路径
结论先行：主要通过公开发行本身与发行前的合规增资两条路径。
公开发行环节由承销商完成配售，是最主要的股东人数来源。发行规模与配售策略直接决定挂牌时的股东结构。
发行前的合规增资也可以贡献股东人数，但必须符合证券法关于私募发行的要求，且需充分揭示风险。关键在于任何安排都不得涉及代持或虚假分散。

## 三、为什么临近挂牌才启动往往来不及
结论先行：股东人数的形成需要真实时间，无法在递表后短期内补齐。
持股分散涉及开户、资金到位、合规审查等环节，每一环都有客观周期。在递表前6至12个月启动，是行业内较为稳妥的安排。
若在交易所问询阶段才发现人数不足，通常只能延后挂牌窗口。因此，本质上这是一个项目排期问题，应在架构设计阶段就纳入时间表。

## 四、常见误区与合规边界
结论先行：任何以代持、虚假账户凑数的做法都会在核查阶段暴露。
交易所与承销商都会核查股东名册的真实性，代持安排一旦被识别，影响的不只是这一项指标，而是整个申报的可信度。
彤鼎在项目中的角色是路径规划与全流程统筹，具体证券发行由持牌合作机构承做。关键在于把合规前置，而不是在核查时再想办法。
"""


def say(msg):
    """Windows 中文控制台是 GBK，输出前按实际编码降级，避免脚本因一个字符崩掉。"""
    try:
        print(msg)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or 'gb18030'
        sys.stdout.write(msg.encode(enc, 'replace').decode(enc, 'replace') + '\n')


def die(msg):
    say('错误：' + msg)
    sys.exit(1)


# ------------------------------------------------------------------ 解析稿件
def read_text(path):
    """中文 Windows 上记事本另存默认是 ANSI(GBK)，外部工具的输出常是 UTF-8，
    两种都要能读，否则用户会撞上看不懂的 UnicodeDecodeError。"""
    data = open(path, 'rb').read()
    for enc in ('utf-8-sig', 'utf-8', 'gb18030'):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    die('稿件文件编码无法识别，请另存为 UTF-8 或 ANSI 后重试：%s' % path)


def parse(path):
    raw = read_text(path).replace('\r\n', '\n')
    meta, body = {}, ''
    lines = raw.split('\n')
    i = 0
    keys = ['标题', 'slug', '分类', '栏目', '副标题', '描述', '英文摘要', '结论']
    while i < len(lines):
        line = lines[i]
        m = re.match(r'^(%s)\s*[:：]\s*(.*)$' % '|'.join(keys), line.strip())
        if m:
            k, v = m.group(1), m.group(2).strip()
            # 允许值跨行，直到下一个已知键或 ## 开头
            j = i + 1
            while j < len(lines):
                nxt = lines[j].strip()
                if not nxt:
                    j += 1
                    continue
                if nxt.startswith('##') or re.match(
                        r'^(%s)\s*[:：]' % '|'.join(keys), nxt):
                    break
                v += nxt
                j += 1
            meta[k] = v.strip()
            i = j
            continue
        if line.strip().startswith('##'):
            body = '\n'.join(lines[i:])
            break
        i += 1

    need = ['标题', 'slug', '分类', '描述', '英文摘要', '结论']
    miss = [k for k in need if not meta.get(k)]
    if miss:
        die('稿件缺少必填字段：%s\n（用 python tools/new_article.py --sample 看格式示例）'
            % '、'.join(miss))
    if meta['分类'] not in CAT_LABELS:
        die('分类「%s」不在 library.html 的八大分类中。可选：%s'
            % (meta['分类'], '、'.join(CAT_LABELS)))
    if not re.match(r'^[a-z0-9-]+$', meta['slug']):
        die('slug 只能用小写字母、数字与短横线，当前为「%s」' % meta['slug'])

    # 章节
    secs = []
    for blk in re.split(r'\n(?=##\s)', body):
        blk = blk.strip()
        if not blk.startswith('##'):
            continue
        head, *rest = blk.split('\n')
        title = head.lstrip('#').strip()
        paras = [p.strip() for p in rest if p.strip()]
        if title and paras:
            secs.append((title, paras))
    if len(secs) < 3:
        die('章节数 %d 太少，至少需要 3 个 ## 章节（规范建议 4-7 个）' % len(secs))

    meta.setdefault('栏目', CAT_LABELS[meta['分类']])
    meta.setdefault('副标题', '')
    return meta, secs


# ------------------------------------------------------------------ 合规检查
def lint(meta, secs):
    text = ' '.join([meta.get(k, '') for k in
                     ['标题', '副标题', '描述', '结论']])
    for t, ps in secs:
        text += ' ' + t + ' ' + ' '.join(ps)

    # 合规规则针对读者看到的文字，不针对标签属性。
    # 若不剥离，站内链接如 pre-ipo-financial-cleanup.html 会被误判为正文提及 Pre-IPO，
    # 进而要求合规三件套——这是误报，会拦下本身没有问题的稿件。
    text = re.sub(r'<[^>]+>', ' ', text)

    problems = []
    for w in FORBIDDEN:
        if w in text:
            problems.append('出现禁用词「%s」' % w)
    m = RANK_FIRST.search(text)
    if m:
        problems.append('出现排名义的「第一」：…%s…' % m.group(0))
    m = TICKER.search(text)
    if m:
        problems.append('疑似出现股票代码：%s' % m.group(0))

    # Pre-IPO / 投资机会须带合规三件套。
    # 2026-08-01 放宽「认购」：它单独出现时多半是 IPO 发行与交割的标准术语
    # （股票认购协议、认购资金、基石认购、超额认购、认购倍数…），与向投资人
    # 推介 Pre-IPO 项目无关。这类误伤会让每一篇讲交割流程的文章都被拦下。
    # 现在只有当「认购」与推介语境词（机会/权益/份额/额度/名额/优先）同现时才触发。
    # 参照 compliance_words.json 已有的「正当术语」白名单做法——2026-07-27 校准时
    # 「配售」全站误报 64 处，处理方式也是这一条：不删规则，只把正当用法排除掉。
    PITCH = r'Pre-?IPO|投资机会|投资权益'
    SUBSCRIBE_IN_PITCH = (r'认购[^。；\n]{0,20}(机会|权益|份额|额度|名额|优先)'
                          r'|(机会|权益|份额|额度|名额|优先)[^。；\n]{0,20}认购')
    if re.search(PITCH, text, re.I) or re.search(SUBSCRIBE_IN_PITCH, text):
        need = [('合格投资者', r'合格投资者'),
                ('揭示风险', r'揭示风险|风险揭示|充分.{0,4}风险'),
                ('不构成投资建议或收益承诺', r'不构成.{0,10}(投资建议|收益承诺)')]
        for name, pat in need:
            if not re.search(pat, text):
                problems.append('正文涉及 Pre-IPO/投资机会，但缺少合规三件套之「%s」' % name)

    words = len(re.findall(r'[一-鿿]', text))
    return problems, words


# ------------------------------------------------------------------ 生成 HTML
def build_html(meta, secs, date, related):
    tpl = io.open(TEMPLATE, encoding='utf-8').read()
    slug = meta['slug']
    url = '%s/articles/%s.html' % (SITE, slug)
    title_full = '%s | 彤鼎集团知识文库' % meta['标题']

    s = tpl
    s = re.sub(r'<title>.*?</title>', '<title>%s</title>' % esc(title_full), s, count=1, flags=re.S)
    s = sub_attr(s, r'<meta name="description" content="', meta['描述'])
    s = sub_attr(s, r'<link rel="canonical" href="', url)
    s = sub_attr(s, r'<meta property="og:title" content="', title_full)
    s = sub_attr(s, r'<meta property="og:description" content="', meta['描述'])
    s = sub_attr(s, r'<meta property="og:url" content="', url)
    s = sub_attr(s, r'<meta name="twitter:title" content="', title_full)
    s = sub_attr(s, r'<meta name="twitter:description" content="', meta['描述'])

    # JSON-LD：解析后改字段再序列化，不做字符串替换（避免顶着模板文章的 schema 上线）
    def fix_ld(m):
        try:
            j = json.loads(m.group(1))
        except ValueError:
            return m.group(0)
        objs = j if isinstance(j, list) else [j]
        touched = False
        for o in objs:
            if o.get('@type') in ('Article', 'NewsArticle', 'BlogPosting'):
                o['headline'] = meta['标题']
                o['description'] = meta['描述']
                o['abstract'] = meta['英文摘要']
                o['datePublished'] = date
                o['dateModified'] = date
                o['inLanguage'] = 'zh-CN'
                o['mainEntityOfPage'] = {'@type': 'WebPage', '@id': url}
                o.pop('image', None)
                touched = True
        if not touched:
            return m.group(0)
        return ('<script type="application/ld+json">'
                + json.dumps(j, ensure_ascii=False, separators=(',', ':'))
                + '</script>')

    s = re.sub(r'<script type="application/ld\+json">(.*?)</script>', fix_ld, s, flags=re.S)

    # art-head
    s = re.sub(r'<div class="cat">.*?</div>', '<div class="cat">%s</div>' % esc(meta['栏目']), s, count=1, flags=re.S)
    s = re.sub(r'<h1>.*?</h1>', '<h1>%s</h1>' % esc(meta['标题']), s, count=1, flags=re.S)
    s = re.sub(r'<div class="sub">.*?</div>', '<div class="sub">%s</div>' % esc(meta['副标题']), s, count=1, flags=re.S)
    s = re.sub(r'<div class="en">.*?</div>', '<div class="en">%s</div>' % esc(meta['英文摘要']), s, count=1, flags=re.S)

    # 正文
    parts = ['<div class="answer">%s</div>' % esc(meta['结论'], allow_links=True, allow_bold=True)]
    for ci, (t, ps) in enumerate(secs, 1):
        parts.append('<h2>%s</h2>' % esc(t))
        # ---- 章节论点卡片图（2026-08-15 廖总：「以后的全部文章都要考虑易读性，
        # 要加插图，否则流量起不来」）----
        # ⛔ 在此之前**官网 199 篇文章一张图都没有**：08-13 建的卡片图只被分发版用了，
        # `ensure_cards` 也只负责生成并 push 图，从没有人把它插进官网页面 ——
        # 图挂在 img/cards/ 上，官网自己不用（CLAUDE.md 第 9 节：有生产方没消费方）。
        # ⚠ 判据是**图在不在仓库里**，不是「这篇该不该有图」：单独跑 new_article.py
        # 时图可能还没生成，那就安全退化成纯文字，⛔ 不许因此报错中止 ——
        # 官网页不上线是 404，没有图只是少个加分项，轻重不同。
        card = os.path.join(REPO, 'img', 'cards', '%s-%d.jpg' % (meta['slug'], ci))
        if os.path.exists(card):
            parts.append(
                '<figure style="margin:30px 0;">'
                '<img src="../img/cards/%s-%d.jpg" alt="%s" loading="lazy" '
                'style="width:100%%;height:auto;display:block;border-radius:3px;">'
                '</figure>' % (meta['slug'], ci, esc(t)))
        for k, p in enumerate(ps):
            if k == 0 and p.startswith('结论先行'):
                # ⛔ 这一段不切：article_cards.py 取的就是它去渲染章节插图，
                # 切开之后卡片上只剩半句。它本来就该 40-60 字，超长是稿子的问题。
                parts.append('<p><strong>%s</strong></p>' % esc(p, allow_links=True))
            else:
                for seg in wrap_para(p):
                    parts.append('<p>%s</p>' % esc(seg, allow_links=True, allow_bold=True))
    s = re.sub(r'<article[^>]*>.*?</article>',
               '<article>\n' + '\n'.join(parts) + '\n</article>', s, count=1, flags=re.S)

    # 相关阅读
    if related:
        li = ''
        for href, txt in related:
            li += ('<li style="margin:7px 0;padding-left:16px;position:relative;">'
                   '<span style="position:absolute;left:0;top:.6em;width:6px;height:6px;'
                   'background:#9a7f45;transform:rotate(45deg);"></span>'
                   '<a href="%s" style="color:#6b5426;font-weight:700;">%s</a></li>'
                   % (href, esc(txt)))
        s = re.sub(r'(<ul style="list-style:none;padding:0;margin:0;font-size:15\.5px;">).*?(</ul>)',
                   lambda m: m.group(1) + li + m.group(2), s, count=1, flags=re.S)
    return s


# 稿件正文允许的唯一内联标签：指向同目录文章的站内链接。
# 全部转义后再按白名单还原——既防止稿件注入任意 HTML，又让站内互链能正常工作。
# 只放行 <a href="xxx.html">文字</a> 形式：不接受协议、路径、查询串，
# 因此 javascript:、外站链接、onclick 之类都无法通过。
_ESCAPED_LINK = re.compile(
    r'&lt;a href=&quot;([a-z0-9-]+\.html)&quot;&gt;([^&<>]{1,60})&lt;/a&gt;')


# 稿件里的 markdown 加粗 **这样**。2026-08-14 发现它既不渲染也不清理，
# 原样漏到官网页面上 —— 站上 7 篇文章正文里能看到字面的星号
# （term-sheet-seven-clauses / pre-revenue-valuation / nasdaq-ipo-workstreams /
#  us-market-cap-toolkit / valuation-enhancement-plan / share-reduction-rules-2024 /
#  market-cap-management-system），读者看到的是 `**这一条要用数字讲。**`。
# ⚠ 零告警：合规闸不查排版，页面也不报错，只有人打开看才知道。
# 与 _ESCAPED_LINK 同一个套路：先整体转义防注入，再按白名单还原这一种标记。
_ESCAPED_BOLD = re.compile(r'\*\*(?!\s)([^*\n]{1,120}?)(?<![\s*])\*\*')


def esc(t, allow_links=False, allow_bold=False):
    s = (t or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
    if allow_links:
        s = _ESCAPED_LINK.sub(lambda m: '<a href="%s">%s</a>' % (m.group(1), m.group(2)), s)
    if allow_bold:
        s = _ESCAPED_BOLD.sub(lambda m: '<strong>%s</strong>' % m.group(1), s)
    return s


# 句末标点后断句，右引号/右括号跟着上一句走（「……。」不能切在句号后面）。
# ⛔ 与 C:\TDGroupSEO\build_dist.py 的 _SENT 保持一致，别在这里另立一套判据。
_SENT = re.compile(r'(?<=[。？！])(?![」』》”）】])')


def wrap_para(p, limit=200, target=130, floor=45):
    r"""段落超过 limit 字就按句切成几段。**一个字都不改，只加断行。**

    2026-08-13 廖总原话：「全都是文字，根本吸引不到人类的客户，一定要多点断行」。
    当天给**分发层**加了 build_dist.split_para 兜底（实测 526 字的段被切到最长 158），
    ⛔ 但官网这条路是另一套代码，一段 = 一个 <p>，一个字没改 ——
    2026-08-14 实测官网 202 篇里 66 篇（33%）有超 200 字的段，最长 556 字，
    超标篇的段落中位高达 225-256。**分发层修了、官网没修，而且零告警。**

    与分发层的差别是故意的：那边无条件按 110 字切（手机信息流场景），
    这边**只切超过 200 字的段**（官网是长文阅读场景，且这样对已达标的新稿零影响、幂等）。

    ⚠ 不切开 markdown 加粗：`**这句。** 后面`——加粗内部含句号时若在那里断开，
    星号会被劈成两半，还原成 <strong> 时配不上对。判据是切点处 `**` 计数必须成对。
    """
    if len(p) <= limit:
        return [p]
    sents = [x for x in _SENT.split(p) if x.strip()]
    if len(sents) < 2:
        return [p]
    out, cur = [], ''
    for x in sents:
        # cur 里 ** 落单时不许断开，继续累加直到成对
        if cur and len(cur) + len(x) > target and cur.count('**') % 2 == 0:
            out.append(cur)
            cur = x
        else:
            cur += x
    if cur:
        if out and (len(cur) < floor or out[-1].count('**') % 2):
            out[-1] += cur
        else:
            out.append(cur)
    return out


def sub_attr(s, prefix_pat, value):
    """替换 <tag attr="..."> 里的值，只改第一处。"""
    pat = prefix_pat + r'[^"]*"'
    repl = prefix_pat.replace('\\', '') + esc(value) + '"'
    return re.sub(pat, lambda m: repl, s, count=1)


# ------------------------------------------------------------------ 站点接入
def pick_related(category, slug, n=3):
    lib = io.open('library.html', encoding='utf-8').read()
    m = re.search(r'<h2>%s</h2>(.*?)(?=<h2>|</section>|$)' % re.escape(category), lib, re.S)
    if not m:
        return []
    items = re.findall(r'<li class="has"><a href="articles/([^"]+)">([^<]+?)\s*→?\s*</a></li>', m.group(1))
    out = []
    for href, txt in items:
        if href == slug + '.html':
            continue
        out.append((href, txt.strip()))
        if len(out) >= n:
            break
    return out


def add_to_library(meta):
    lib = io.open('library.html', encoding='utf-8').read()
    entry = ('<li class="has"><a href="articles/%s.html">%s →</a></li>'
             % (meta['slug'], esc(meta['标题'])))
    if 'articles/%s.html' % meta['slug'] in lib:
        return False
    m = re.search(r'(<h2>%s</h2>.*?<ul[^>]*>)' % re.escape(meta['分类']), lib, re.S)
    if not m:
        die('library.html 里找不到分类「%s」的 <ul>，无法挂载' % meta['分类'])
    lib = lib[:m.end()] + '\n' + entry + lib[m.end():]
    io.open('library.html', 'w', encoding='utf-8').write(lib)
    return True


def add_to_sitemap(meta, date):
    sm = io.open('sitemap.xml', encoding='utf-8').read()
    loc = '%s/articles/%s.html' % (SITE, meta['slug'])
    if loc + '<' in sm or loc + '</loc>' in sm:
        return False
    entry = ('  <url><loc>%s</loc><lastmod>%s</lastmod>'
             '<changefreq>monthly</changefreq><priority>0.8</priority></url>\n' % (loc, date))
    sm = sm.replace('</urlset>', entry + '</urlset>')
    io.open('sitemap.xml', 'w', encoding='utf-8').write(sm)
    return True


def run(cmd):
    p = subprocess.run([sys.executable] + cmd, capture_output=True)
    out = (p.stdout or b'').decode('utf-8', 'replace').strip()
    err = (p.stderr or b'').decode('utf-8', 'replace').strip()
    return p.returncode, out or err


# ------------------------------------------------------------------ main
def main():
    if '--sample' in sys.argv:
        i = sys.argv.index('--sample')
        # --sample 后面给了路径就直接写 UTF-8 文件；否则打印。
        # 不建议用 shell 重定向（`--sample > x.md`），Windows 下会写成 GBK。
        if i + 1 < len(sys.argv) and not sys.argv[i + 1].startswith('--'):
            io.open(sys.argv[i + 1], 'w', encoding='utf-8').write(SAMPLE)
            say('已写入格式示例（UTF-8）：%s' % sys.argv[i + 1])
        else:
            say(SAMPLE)
        return 0
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if not args:
        die('用法：python tools/new_article.py 稿件.md   （--sample 看格式示例）')
    src = args[0]
    if not os.path.exists(src):
        die('稿件文件不存在：%s' % src)

    date = datetime.date.today().strftime('%Y-%m-%d')
    if '--date' in sys.argv:
        date = sys.argv[sys.argv.index('--date') + 1]
    dry = '--dry-run' in sys.argv

    meta, secs = parse(src)
    problems, words = lint(meta, secs)

    say('稿件：%s' % meta['标题'])
    say('slug：%s   分类：%s   章节：%d   汉字数：%d' % (meta['slug'], meta['分类'], len(secs), words))

    if problems:
        say('\n[不通过] 合规检查未通过，已中止（未写入任何文件）：')
        for p in problems:
            say('   - ' + p)
        say('\n请修改稿件后重跑。禁用表述见 CLAUDE.md 第三节。')
        return 1
    say('[通过] 合规检查通过（禁用词、排名义第一、股票代码、Pre-IPO三件套）')

    if words < 1500:
        say('[提醒] 汉字数 %d 偏少，规范建议正文 2500 字以上。仍会继续，但对 SEO 不利。' % words)

    out = 'articles/%s.html' % meta['slug']
    if os.path.exists(out) and not dry:
        die('文章已存在：%s（如需覆盖请先手动删除）' % out)

    related = pick_related(meta['分类'], meta['slug'])
    html = build_html(meta, secs, date, related)

    if dry:
        say('\n--dry-run：未写盘。将生成 %s（%d 字节），相关阅读 %d 条。'
            % (out, len(html.encode('utf-8')), len(related)))
        return 0

    io.open(out, 'w', encoding='utf-8').write(html)
    say('\n已生成 %s' % out)
    say('已挂 library.html：%s' % ('是' if add_to_library(meta) else '已存在，跳过'))
    say('已加 sitemap.xml：%s' % ('是' if add_to_sitemap(meta, date) else '已存在，跳过'))

    for name, cmd in [('知识库 rebuild_kb', ['tools/rebuild_kb.py']),
                      ('llms.txt gen_llms', ['tools/gen_llms.py'])]:
        code, o = run(cmd)
        say('%s：%s' % (name, o.splitlines()[0] if o else ('OK' if code == 0 else '失败')))

    say('\n下一步（本脚本不自动提交，便于你先看一眼页面）：')
    say('  git add -A && git commit -m "发布：%s" && git push' % meta['标题'])
    say('  python tools/push_indexnow.py articles/%s.html' % meta['slug'])
    say('  上线后地址：%s/articles/%s.html' % (SITE, meta['slug']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
