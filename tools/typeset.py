# -*- coding: utf-8 -*-
"""排版引擎：把「一段 300 字、通篇无图」的正文，重排成手机上读得下去的版式。

问题（2026-08-13 用户指出）：官网与各平台分发稿全是文字墙。抽样 199 篇正文，
段落均长 107 字、最长 619 字，一段在手机上就是连续二十行；正文配图数量为 0。
读者划两屏就走，内容再准也换不来客户。

本模块只做**版式**，不改一个字。三件事：

1. 断行  —— 把长段按句号切成 2-4 句一段（`split_paragraph`）。
2. 结构  —— 认出正文里本来就有的结构，把它显性化（`parse_lead` / `find_enumeration`）：
             「结论先行：<结论>。<案例>」拆成结论卡 + 案例卡；
             「其一是…其二是…」拆成编号要点卡。
3. 图形  —— 章节序号带、要点卡、分隔纹样等版面元素（`css` / `render_*`）。

被 tools/retypeset.py（官网存量文章）、tools/platform_export.py（公众号等分发稿）、
tools/new_article.py（新文章）共用，三条线的版式必须一致。

不改字的保证：`plain_text()` 对重排前后取纯文本，retypeset.py 会逐篇断言两者
的正文内容完全相同（新增的导览与标签除外，见该脚本 verify）。
"""
import re

# ---------------------------------------------------------------- 基础工具

TAG = re.compile(r'<[^>]+>')
# 行内标签：跨句时不允许在中间断段，否则标签会被切坏
INLINE_OPEN = re.compile(r'<(strong|em|b|i|a|span|code)\b', re.I)
INLINE_CLOSE = re.compile(r'</(strong|em|b|i|a|span|code)\s*>', re.I)

SENT_END = '。！？'
# 句末标点之后若紧跟这些收尾符号，要一并划进上一句
TRAILERS = '”』」）)》】…—、'


def plain_text(html):
    """取纯文本，用于「改版不改字」的校验。空白与实体做归一化。"""
    t = TAG.sub('', html)
    t = (t.replace('&quot;', '"').replace('&ldquo;', '"').replace('&rdquo;', '"')
          .replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
          .replace('&nbsp;', ' '))
    return re.sub(r'\s+', '', t)


def visual_len(html):
    """可见字数（不含标签）。"""
    return len(plain_text(html))


def split_sentences(html, soft=False):
    """按句号切句，只在「不在标签内、且行内标签全部闭合」的位置下刀。

    行内标签跨句时（例如整段被 <strong> 包住）不切，交由调用方先剥外层标签。
    soft=True 时把分号也当断点：中文长句常用分号并列三四个小句，
    手机上不在分号处断就是十几行连着走。官网列宽够，不开；平台分发稿开。
    """
    stops = SENT_END + ('；;' if soft else '')
    out, buf, depth, in_tag = [], [], 0, False
    i = 0
    while i < len(html):
        ch = html[i]
        if ch == '<':
            m = INLINE_OPEN.match(html, i) or INLINE_CLOSE.match(html, i)
            if m:
                depth += 1 if m.re is INLINE_OPEN else -1
            in_tag = True
        buf.append(ch)
        if ch == '>':
            in_tag = False
        elif ch in stops and not in_tag and depth <= 0:
            j = i + 1
            while j < len(html) and html[j] in TRAILERS:
                buf.append(html[j])
                j += 1
            out.append(''.join(buf))
            buf = []
            i = j
            continue
        i += 1
    if buf:
        out.append(''.join(buf))
    return [s for s in out if s.strip()]


def split_paragraph(html, target=90, floor=120, soft=False):
    """把一段切成若干段。短于 floor 的整段返回，不动。

    target 是每段的目标可见字数：累计到 target 就收一段，但绝不切开半句话，
    所以实际落在 target ± 一句话的范围内。
    """
    if visual_len(html) <= floor:
        return [html]
    sents = split_sentences(html, soft=soft)
    if len(sents) < 2:
        return [html]
    paras, cur, n = [], [], 0
    for s in sents:
        cur.append(s)
        n += visual_len(s)
        if n >= target:
            paras.append(''.join(cur))
            cur, n = [], 0
    if cur:
        # 收尾若只剩一句短话，并回上一段，避免出现孤零零的一行
        tail = ''.join(cur)
        if paras and visual_len(tail) < 40:
            paras[-1] += tail
        else:
            paras.append(tail)
    return paras


# ---------------------------------------------------------------- 结构识别

LEAD_PREFIX = re.compile(r'^\s*结论先行[：:]\s*')


def parse_lead(html):
    """拆「结论先行：<结论>。<案例……>」。

    返回 (结论 html, 案例 html)；案例可能为空。结论取第一句到第一个句号，
    但若第一句短于 30 字则继续并入下一句——有些文章的结论写成了两短句。
    """
    inner = LEAD_PREFIX.sub('', html)
    sents = split_sentences(inner)
    if not sents:
        return inner, ''
    take, n = [], 0
    for s in sents:
        take.append(s)
        n += visual_len(s)
        if n >= 30:
            break
    concl = ''.join(take)
    case = ''.join(sents[len(take):])
    return concl, case


ORD = '一二三四五六七八九十'
ORD_VAL = {c: i + 1 for i, c in enumerate(ORD)}

# 正文里实际用到的枚举写法。要求带「是/，/：/、」收口，避免误伤「其一部分」这类词。
ENUM = re.compile(
    r'(?:其(?P<a>[' + ORD + r'])(?=[是，、：])'
    r'|步骤(?P<b>[' + ORD + r'])(?=[是，：])'
    r'|层次(?P<c>[' + ORD + r'])(?=[是，：])'
    r'|变量之(?P<d>[' + ORD + r'])(?=[是，：])'
    r'|情形(?P<e>[' + ORD + r'])(?=[是，：])'
    r'|做法(?P<f>[' + ORD + r'])(?=[是，：])'
    r'|第(?P<g>[' + ORD + r'])(?:类|种|步|层|条)(?=[是，：]))'
)


def find_enumeration(html, min_items=3):
    """认出「其一…其二…其三…」这类枚举，返回 (引子, [条目 html, ...])。

    条件：序号从「一」起、连续递增、至少 min_items 条，且都在标签外。
    认不出就返回 (html, [])，调用方按普通段落处理。
    """
    marks = []
    for m in ENUM.finditer(html):
        # 落在标签内部的忽略
        if html.count('<', 0, m.start()) != html.count('>', 0, m.start()):
            continue
        ch = next(v for v in m.groupdict().values() if v)
        marks.append((m.start(), ORD_VAL[ch]))
    if len(marks) < min_items:
        return html, []
    # 取从 1 开始的最长连续递增段
    seq = []
    for pos, val in marks:
        if val == (seq[-1][1] + 1 if seq else 1):
            seq.append((pos, val))
    if len(seq) < min_items:
        return html, []
    intro = html[:seq[0][0]].strip()
    items = []
    for k, (pos, _) in enumerate(seq):
        end = seq[k + 1][0] if k + 1 < len(seq) else len(html)
        items.append(html[pos:end].strip())
    return intro, items


ITEM_TITLE = re.compile(r'^(.{0,28}?)(?<![，。])(?:是|：)(.+)$', re.S)


def item_parts(item):
    """把一条枚举拆成「小标题 / 正文」，纯为加粗用，一个字都不删。

    「其一是通知形式与送达地址：约定书面形式……」→ 标题止于第一个「：」，
    找不到分界就整条当正文。
    """
    head = re.match(r'^(?:其[' + ORD + r']|步骤[' + ORD + r']|层次[' + ORD + r']|'
                    r'变量之[' + ORD + r']|情形[' + ORD + r']|做法[' + ORD + r']|'
                    r'第[' + ORD + r'][类种步层条])[是，：]?', item)
    if not head:
        return '', item
    marker = head.group(0)
    rest = item[head.end():]
    m = re.match(r'^([^：:。]{2,24}[：:])(.+)$', rest, re.S)
    if m:
        return marker + m.group(1), m.group(2)
    # 没有冒号时退而求其次断在第一个逗号，但标题过长就不加粗了——
    # 加粗半句话比不加粗更难读。
    m = re.match(r'^([^。]{2,14})([，,].+)$', rest, re.S)
    if m:
        return marker + m.group(1), m.group(2)
    # 认不出小标题时只加粗序号本身。收口的「是/，/：」推给正文，
    # 否则会像「其二是」那样吊着一个字——同时保证一个字都没丢。
    if marker and marker[-1] in '是，：,:':
        return marker[:-1], marker[-1] + rest
    return marker, rest


CN_NUM = re.compile(r'^\s*([' + ORD + r']+)[、.．]\s*')


def section_no(title):
    """从「三、共同出售权：……」取出序号 03 与去掉序号的标题。"""
    m = CN_NUM.match(title)
    if not m:
        return '', title.strip()
    val = 0
    s = m.group(1)
    if s.startswith('十'):
        val = 10 + (ORD_VAL[s[1]] if len(s) > 1 else 0)
    elif len(s) == 2 and s[1] == '十':
        val = ORD_VAL[s[0]] * 10
    elif len(s) == 3:
        val = ORD_VAL[s[0]] * 10 + ORD_VAL[s[2]]
    else:
        val = ORD_VAL.get(s, 0)
    return '%02d' % val, title[m.end():].strip()


# ---------------------------------------------------------------- 官网版式

MARK_BEGIN = '/* == typeset v1 : 版式（tools/typeset.py 生成，勿手改） == */'
MARK_END = '/* == /typeset v1 == */'

CSS = MARK_BEGIN + """
article{max-width:760px;font-size:17.5px;}
article p{margin:20px 0;line-height:2.0;text-align:left;}
article h2{margin:60px 0 10px;font-size:25px;border-left:3px solid var(--gold);padding-left:18px;
scroll-margin-top:104px;}/* 导航是 fixed 的，不留这一段本文要点跳过去会被压在导航底下 */
article h2 .no{display:block;font-family:Georgia,serif;font-style:italic;font-size:14px;
letter-spacing:5px;color:#9a7f45;margin-bottom:9px;font-weight:400;}
article h2 .no::after{content:"";display:inline-block;width:40px;height:1px;
background:rgba(154,127,69,.5);vertical-align:middle;margin-left:14px;}
.ts-toc{border:1px solid rgba(154,127,69,.4);background:#fdfaf2;padding:24px 28px;margin:8px 0 40px;}
.ts-toc b{display:block;font-size:12.5px;letter-spacing:4px;color:#9a7f45;
font-family:Georgia,serif;font-style:italic;margin-bottom:14px;}
.ts-toc ol{list-style:none;padding:0;margin:0;counter-reset:t;}
.ts-toc li{counter-increment:t;position:relative;padding-left:38px;margin:9px 0;
font-size:15.5px;line-height:1.7;color:#4a4133;}
.ts-toc li::before{content:"0" counter(t);position:absolute;left:0;top:1px;
font-family:Georgia,serif;font-style:italic;color:#c9a962;font-size:15px;}
.ts-toc a{color:#4a4133;border-bottom:1px solid transparent;}
.ts-toc a:hover{color:#6b5426;border-bottom-color:#c9a962;}
.answer{font-weight:400;}
.answer .tag,.ts-lead .tag,.ts-case .tag{display:block;font-size:12px;letter-spacing:4px;
color:#9a7f45;font-family:Georgia,serif;font-style:italic;margin-bottom:14px;}
.answer p{margin:14px 0;font-weight:600;line-height:1.95;}
.answer p:first-of-type{margin-top:0;}
.ts-lead{border-left:4px solid #c9a962;background:#fbf6e8;padding:22px 26px;margin:26px 0;}
.ts-lead p{margin:0;font-size:18px;font-weight:700;line-height:1.85;color:#2b2312;}
.ts-case{border:1px solid rgba(154,127,69,.34);background:#fffdf7;padding:22px 26px;margin:26px 0;}
.ts-case p{margin:12px 0;font-size:16px;line-height:1.95;color:#4a4133;}
.ts-case p:first-of-type{margin-top:0;}
.ts-case p:last-child{margin-bottom:0;}
.ts-pts{list-style:none;padding:0;margin:26px 0;counter-reset:p;}
.ts-pts li{counter-increment:p;position:relative;padding:18px 22px 18px 62px;margin:10px 0;
background:#fdfaf2;border:1px solid rgba(154,127,69,.24);line-height:1.9;font-size:16px;color:#39332a;}
.ts-pts li::before{content:"0" counter(p);position:absolute;left:20px;top:16px;
font-family:Georgia,serif;font-style:italic;font-size:19px;color:#c9a962;}
.ts-pts li b{color:#141210;}
.ts-hr{border:0;height:26px;margin:52px 0;background:no-repeat center/26px 26px
url("data:image/svg+xml;charset=utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M12 2l10 10-10 10L2 12z' fill='none' stroke='%23c9a962' stroke-width='1.3'/%3E%3Cpath d='M12 7.5l4.5 4.5-4.5 4.5L7.5 12z' fill='%23c9a962'/%3E%3C/svg%3E");
position:relative;}
.ts-hr::before,.ts-hr::after{content:"";position:absolute;top:13px;width:calc(50% - 30px);
height:1px;background:linear-gradient(90deg,transparent,rgba(154,127,69,.45));}
.ts-hr::before{left:0;}
.ts-hr::after{right:0;background:linear-gradient(270deg,transparent,rgba(154,127,69,.45));}
@media(max-width:760px){
/* 原样式最窄断点在 960px，手机上标题与留白仍按平板尺寸走，偏大偏挤。
   导航六项在 500px 宽尚不溢出，但更窄的机型会，故补一个换行兜底。 */
.nav-in{padding:14px 18px;}
.menu{flex-wrap:wrap;gap:14px 18px;font-size:13px;}
.logo .mark-img{height:44px;}
.logo .nm{font-size:15px;letter-spacing:2px;}
.wrap{padding:0 20px;}
.art-head{padding:118px 0 42px;}
.art-head h1{font-size:26px;letter-spacing:0;line-height:1.55;}
.art-head .sub{font-size:15.5px;line-height:1.75;}
.art-head .en{font-size:13px;line-height:1.8;}
.art-foot{padding:0 20px 56px;}
article{font-size:17px;padding:40px 20px 64px;}
article p{margin:18px 0;line-height:1.95;}
article h2{font-size:21px;margin:48px 0 6px;scroll-margin-top:88px;}
.answer,.ts-lead,.ts-case{padding:18px 18px;}
.ts-lead p{font-size:16.5px;}
.ts-pts li{padding:16px 16px 16px 54px;font-size:15.5px;}
.ts-pts li::before{left:16px;}
.ts-toc{padding:20px 18px;}
}
""" + MARK_END


def render_toc(sections):
    """本文要点导览。sections 为 [(锚点 id, 序号, 标题), ...]"""
    if len(sections) < 3:
        return ''
    li = ''.join('<li><a href="#%s">%s</a></li>' % (a, t) for a, _, t in sections)
    return ('<div class="ts-toc"><b>本文要点 IN THIS ARTICLE</b><ol>%s</ol></div>' % li)


def render_answer(html):
    """结论先行金框：加标签、按句断段，去掉整块加粗。"""
    paras = split_paragraph(html, target=110, floor=140)
    body = ''.join('<p>%s</p>' % p for p in paras)
    return '<div class="answer"><span class="tag">核心结论 THE ANSWER</span>%s</div>' % body


def render_lead(concl, case):
    out = '<div class="ts-lead"><span class="tag">结论先行</span><p>%s</p></div>' % concl
    if case.strip():
        paras = split_paragraph(case, target=105, floor=130)
        out += ('<div class="ts-case"><span class="tag">实操案例 CASE</span>%s</div>'
                % ''.join('<p>%s</p>' % p for p in paras))
    return out


def paras(html, target=90, floor=120):
    """切段并标记续段。data-ts="1" 让 retypeset.py 能把它们还原成原来的一段，
    改了切分参数以后 --force 重跑才能重新排布，而不是在已切的段上再切。"""
    ps = split_paragraph(html, target, floor)
    return ''.join('<p%s>%s</p>' % (' data-ts="1"' if i else '', p)
                   for i, p in enumerate(ps))


def render_points(intro, items):
    out = ''
    if intro:
        out += paras(intro)
    li = []
    for it in items:
        head, rest = item_parts(it)
        li.append('<li><b>%s</b>%s</li>' % (head, rest) if head else '<li>%s</li>' % rest)
    return out + '<ol class="ts-pts">%s</ol>' % ''.join(li)


def render_body(blocks):
    """把段落块列表渲染成官网正文。

    blocks 为 [('h2', 标题), ('answer', html), ('lead', html), ('p', html), ...]，
    顺序即正文顺序。返回 (html, sections)。
    """
    out, sections, seen = [], [], 0
    for kind, html in blocks:
        if kind == 'h2':
            no, title = section_no(html)
            anchor = 'sec-%s' % (no or len(sections) + 1)
            sections.append((anchor, no, title))
            if seen:
                out.append('<hr class="ts-hr">')
            seen += 1
            out.append('<h2 id="%s">%s%s</h2>'
                       % (anchor,
                          '<span class="no">CHAPTER %s</span>' % no if no else '',
                          html))
        elif kind == 'answer':
            out.append(render_answer(html))
        elif kind == 'lead':
            out.append(render_lead(*parse_lead(html)))
        else:
            intro, items = find_enumeration(html)
            if items:
                out.append(render_points(intro, items))
            else:
                out.append(paras(html))
    return ''.join(out), sections
