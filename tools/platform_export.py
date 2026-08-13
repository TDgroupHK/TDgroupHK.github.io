# -*- coding: utf-8 -*-
"""把官网文章导出成各平台可直接发布的版式稿，附自动生成的配图。

起因（2026-08-13 用户指出）：公众号那篇文章是一整块文字墙，其他平台同样，
「根本吸引不到人类的客户」。根因是分发稿等于把官网正文原样贴过去——
官网是 840px 宽的桌面阅读，公众号是 375px 宽的手机阅读，同一段文字
在后者是前者的两倍行数。

用法：
    python tools/platform_export.py rofr-co-sale          # 导出一篇（全平台）
    python tools/platform_export.py rofr-co-sale --no-img # 跳过配图（快）
    python tools/platform_export.py --all                 # 全站导出
    python tools/platform_export.py rofr-co-sale --list   # 只看会产出哪些文件

产物在 dist/platform/<slug>/（已在 .gitignore，不进仓库、不上官网）：
    微信公众号.html          —— 全内联样式，直接全选复制粘贴进公众号编辑器
    知乎-头条-百家号.txt      —— 纯文本，段间空行，【】小标题
    微博.txt                 —— 同上，文末按规则带两条官网链接
    小红书-抖音.txt           —— 摘要版，压到平台字数上限内
    配图/                    —— 封面图 + 每章一张章节卡（PNG）
    README-发布说明.md        —— 哪个文件发哪个平台、图怎么配

外链分级严格按 CLAUDE.md 第四节第 7 条：只有微博能在正文放链接；公众号的
官网原文挂「阅读原文」位；知乎系只留一句检索引导；小红书与抖音一个字都不留。
"""
import os
import re
import sys
import html as _html
import shutil
import subprocess
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import typeset as T          # noqa: E402
import retypeset as R        # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
OUT = os.path.join('dist', 'platform')
SITE = 'https://tdgroup.hk'

# 平台外链口径（CLAUDE.md 四.7）。改这里之前先改那份文件，两边必须一致。
SEARCH_HINT = '更多资本市场解读可在公开网络检索「彤鼎集团」。'

CHROME = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'

# 配图字体：本机（Windows/Mac）优先用系统中文字体，容器里退到文泉驿。
FONT = '"Songti SC","Noto Serif SC","Source Han Serif SC","SimSun",' \
       '"WenQuanYi Zen Hei",serif'
FONT_SANS = '"PingFang SC","Noto Sans SC","Microsoft YaHei","WenQuanYi Zen Hei",sans-serif'


# ---------------------------------------------------------------- 读文章

def load(slug):
    path = os.path.join('articles', slug + '.html')
    src = open(path, encoding='utf-8').read()

    def pick(pat, default=''):
        m = re.search(pat, src, re.S)
        return m.group(1).strip() if m else default

    meta = {
        'slug': slug,
        'title': _html.unescape(TAGS(pick(r'<div class="art-head">.*?<h1>(.*?)</h1>'))),
        'sub': _html.unescape(TAGS(pick(r'<div class="sub">(.*?)</div>'))),
        'cat': _html.unescape(TAGS(pick(r'<div class="cat">(.*?)</div>'))),
        'desc': _html.unescape(pick(r'<meta name="description" content="(.*?)">')),
        'url': '%s/articles/%s.html' % (SITE, slug),
    }
    body = re.search(r'<article>(.*?)</article>', src, re.S).group(1)
    blocks = R.parse_blocks(R.untypeset(body))
    brand = re.search(r'<div class="brandbox">(.*?)</div>\s*<div class="disc">(.*?)</div>',
                      src, re.S)
    meta['brand'] = [_html.unescape(TAGS(p)) for p in
                     re.findall(r'<p>(.*?)</p>', brand.group(1), re.S)] if brand else []
    meta['disc'] = _html.unescape(TAGS(brand.group(2))) if brand else ''
    return meta, blocks


def TAGS(s):
    return re.sub(r'<[^>]+>', '', s or '').strip()


def sections(blocks):
    """把块序列按 h2 归拢成章节。返回 (answer, [ {no,title,items}, ... ])。"""
    answer, secs, cur = '', [], None
    for kind, h in blocks:
        if kind == 'answer':
            answer = h
        elif kind == 'h2':
            no, title = T.section_no(h)
            cur = {'no': no or '%02d' % (len(secs) + 1), 'title': title, 'items': []}
            secs.append(cur)
        elif cur is not None:
            cur['items'].append((kind, h))
    return answer, secs


# ---------------------------------------------------------------- 微信公众号
# 公众号编辑器会剥掉 <style> 与 class，只认元素上的 style 属性，所以全部内联。
# 字号 16px、行高 1.9、字距 .5px 是手机上中文正文的舒适区间。

S = {
    'wrap': 'font-size:16px;line-height:1.9;letter-spacing:.5px;color:#3f3a30;'
            'word-break:break-word;',
    'p': 'margin:0 0 20px;line-height:1.9;letter-spacing:.5px;color:#3f3a30;text-align:left;',
    'lede': 'margin:0 0 24px;padding:16px 18px;background:#faf6ec;'
            'border-left:3px solid #c9a962;font-size:15px;line-height:1.85;color:#6b5f45;',
    'ansbox': 'margin:0 0 26px;padding:20px 18px;background:#fbf6e8;'
              'border:1px solid #d8c48c;',
    'tag': 'display:block;margin:0 0 12px;font-size:12px;letter-spacing:3px;color:#9a7f45;',
    'ansp': 'margin:0 0 14px;font-size:16px;line-height:1.9;color:#2b2312;font-weight:bold;',
    'toc': 'margin:0 0 26px;padding:18px;background:#fdfaf2;border:1px dashed #d8c48c;',
    'tocli': 'margin:0 0 10px;font-size:15px;line-height:1.7;color:#5a5040;',
    'h2wrap': 'margin:38px 0 18px;',
    'h2no': 'display:block;font-size:12px;letter-spacing:4px;color:#c9a962;margin:0 0 8px;',
    'h2': 'margin:0;font-size:19px;line-height:1.55;color:#141210;font-weight:bold;'
          'border-left:3px solid #c9a962;padding-left:12px;',
    'lead': 'margin:0 0 20px;padding:16px 18px;background:#fbf6e8;border-left:3px solid #c9a962;'
            'font-size:16.5px;line-height:1.8;color:#2b2312;font-weight:bold;',
    'case': 'margin:0 0 22px;padding:16px 18px;background:#fffdf7;border:1px solid #e3d6b4;',
    'casep': 'margin:0 0 12px;font-size:15px;line-height:1.9;color:#4a4133;',
    'pt': 'margin:0 0 12px;padding:14px 16px;background:#fdfaf2;border:1px solid #e3d6b4;'
          'font-size:15px;line-height:1.85;color:#39332a;',
    'ptno': 'display:inline-block;margin-right:8px;color:#c9a962;font-weight:bold;',
    'hr': 'margin:34px 0;text-align:center;color:#c9a962;font-size:13px;letter-spacing:8px;',
    'brand': 'margin:36px 0 0;padding:22px 18px 6px;border-top:2px solid #c9a962;',
    'brandp': 'margin:0 0 14px;font-size:14.5px;line-height:1.85;color:#5a5040;',
    'disc': 'margin:0;font-size:12px;line-height:1.8;color:#8a8168;',
    'img': 'display:block;width:100%;height:auto;margin:0 0 22px;',
}


def esc(s):
    return s


def wx_paras(html, style, target=64):
    """公众号一段控制在 60-80 字：375px 屏、16px 字，一行约 20 字，三到四行。"""
    return ''.join('<p style="%s">%s</p>' % (style, p)
                   for p in T.split_paragraph(html, target=target, floor=85, soft=True))


def render_wechat(meta, blocks, imgs=None):
    answer, secs = sections(blocks)
    imgs = imgs or {}
    o = ['<section style="%s">' % S['wrap']]
    if imgs.get('cover'):
        o.append('<img src="%s" style="%s">' % (imgs['cover'], S['img']))
    if meta['sub']:
        o.append('<section style="%s">%s</section>' % (S['lede'], meta['sub']))
    if answer:
        o.append('<section style="%s"><span style="%s">核 心 结 论</span>%s</section>'
                 % (S['ansbox'], S['tag'], wx_paras(answer, S['ansp'], 70)))
    if len(secs) >= 3:
        li = ''.join('<p style="%s"><span style="color:#c9a962;">%s</span>　%s</p>'
                     % (S['tocli'], s['no'], s['title']) for s in secs)
        o.append('<section style="%s"><span style="%s">本 文 要 点</span>%s</section>'
                 % (S['toc'], S['tag'], li))
    for i, s in enumerate(secs):
        if i:
            o.append('<section style="%s">◆ ◆ ◆</section>' % S['hr'])
        o.append('<section style="%s"><span style="%s">CHAPTER %s</span>'
                 '<p style="%s">%s</p></section>'
                 % (S['h2wrap'], S['h2no'], s['no'], S['h2'], s['title']))
        if imgs.get(s['no']):
            o.append('<img src="%s" style="%s">' % (imgs[s['no']], S['img']))
        for kind, h in s['items']:
            if kind == 'lead':
                concl, case = T.parse_lead(h)
                o.append('<p style="%s">%s</p>' % (S['lead'], concl))
                if case.strip():
                    o.append('<section style="%s"><span style="%s">实 操 案 例</span>%s</section>'
                             % (S['case'], S['tag'], wx_paras(case, S['casep'], 62)))
            elif kind == 'p':
                intro, items = T.find_enumeration(h)
                if items:
                    if intro:
                        o.append(wx_paras(intro, S['p']))
                    for k, it in enumerate(items):
                        head, rest = T.item_parts(it)
                        o.append('<p style="%s"><span style="%s">%02d</span>%s%s</p>'
                                 % (S['pt'], S['ptno'], k + 1,
                                    '<strong>%s</strong>' % head if head else '', rest))
                else:
                    o.append(wx_paras(h, S['p']))
            elif kind == 'h3':
                o.append('<p style="%s">%s</p>' % (S['h2'], TAGS(h)))
            else:
                o.append(wx_paras(TAGS(h), S['p']))
    if meta['brand']:
        b = ''.join('<p style="%s">%s</p>' % (S['brandp'], p) for p in meta['brand'])
        o.append('<section style="%s">%s<p style="%s">%s</p></section>'
                 % (S['brand'], b, S['disc'], meta['disc']))
    o.append('</section>')
    return ''.join(o)


# ---------------------------------------------------------------- 纯文本平台

def txt_paras(html, target=58):
    return '\n\n'.join(TAGS(p) for p in
                        T.split_paragraph(html, target=target, floor=80, soft=True))


def render_plain(meta, blocks, tail=''):
    answer, secs = sections(blocks)
    o = [meta['title'], '']
    if meta['sub']:
        o += [meta['sub'], '']
    if answer:
        o += ['【核心结论】', '', txt_paras(answer, 62), '']
    if len(secs) >= 3:
        o += ['【本文要点】', '']
        o += ['%s　%s' % (s['no'], s['title']) for s in secs]
        o += ['']
    for s in secs:
        o += ['—————————————', '%s　%s' % (s['no'], s['title']), '—————————————', '']
        for kind, h in s['items']:
            if kind == 'lead':
                concl, case = T.parse_lead(h)
                o += ['【结论先行】', concl, '']
                if case.strip():
                    o += ['【案例】', txt_paras(case, 56), '']
            elif kind == 'p':
                intro, items = T.find_enumeration(h)
                if items:
                    if intro:
                        o += [txt_paras(intro), '']
                    for k, it in enumerate(items):
                        head, rest = T.item_parts(it)
                        o += ['%02d｜%s%s' % (k + 1, head, TAGS(rest)), '']
                else:
                    o += [txt_paras(h), '']
            else:
                o += [txt_paras(TAGS(h)), '']
    if meta['brand']:
        o += ['—————————————', '']
        o += [p for p in meta['brand']] + ['']
    if meta['disc']:
        o += [meta['disc'], '']
    if tail:
        o += [tail]
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(o)).strip() + '\n'


def render_short(meta, blocks, limit=900):
    """小红书 / 抖音图文：正文有字数上限，全文贴不进去，只发结论 + 要点 + 一个案例。"""
    answer, secs = sections(blocks)
    o = [meta['title'], '']
    if answer:
        o += [TAGS(T.split_paragraph(answer, 90, 90)[0]), '']
    o += ['｜本文讲清楚这几件事｜', '']
    o += ['· %s' % s['title'] for s in secs]
    o += ['']
    for s in secs:
        for kind, h in s['items']:
            if kind == 'lead':
                concl, _ = T.parse_lead(h)
                o += ['｜%s｜' % s['title'], concl, '']
                break
        if sum(len(x) for x in o) > limit:
            break
    txt = re.sub(r'\n{3,}', '\n\n', '\n'.join(o)).strip()
    if len(txt) > limit:
        txt = txt[:limit].rsplit('\n', 1)[0]
    return txt + '\n'


# ---------------------------------------------------------------- 配图

# 版面全部挂在 .card 上，不靠 body/视口——headless 的视口尺寸不完全等于
# --window-size（有 500px 下限，且截图时还会按内容高度重排），
# 拿视口当定位基准会让边框与落款跑到画面外。
CARD = """<!doctype html><meta charset="utf-8"><style>
*{margin:0;padding:0;box-sizing:border-box}
html,body{background:#0a0908}
.card{position:relative;overflow:hidden;width:%(w)dpx;height:%(h)dpx;
padding:%(padt)dpx %(pad)dpx %(padb)dpx;color:#d9d0bb;font-family:%(sans)s;
display:flex;flex-direction:column;justify-content:center;
background:#0a0908 radial-gradient(ellipse at 12%% 18%%,rgba(201,169,98,.14) 0,transparent 45%%),
radial-gradient(ellipse at 88%% 84%%,rgba(201,169,98,.09) 0,transparent 50%%)}
.frame{position:absolute;top:%(inset)dpx;right:%(inset)dpx;bottom:%(inset)dpx;left:%(inset)dpx;
border:1px solid rgba(201,169,98,.22)}
.eyebrow{position:absolute;top:%(padt)dpx;left:%(pad)dpx;color:#c9a962;font-size:%(eye)dpx;
letter-spacing:%(eyels)dpx;font-family:Georgia,serif;font-style:italic}
.mid{position:relative}
.rule{width:56px;height:2px;background:#c9a962;margin-bottom:%(gap)dpx}
h1{font-family:%(serif)s;font-size:%(fs)dpx;line-height:1.42;color:#fff;font-weight:900;
letter-spacing:.5px}
.sub{margin-top:%(gap)dpx;padding-top:%(gap)dpx;border-top:1px solid rgba(201,169,98,.22);
color:#a89b7d;font-size:%(sfs)dpx;line-height:1.75}
.foot{position:absolute;left:%(pad)dpx;bottom:%(padb2)dpx;color:#8f8468;font-size:%(ffs)dpx;
letter-spacing:3px}
</style><div class="card"><div class="frame"></div>
<div class="eyebrow">%(eyebrow)s</div>
<div class="mid"><div class="rule"></div><h1>%(title)s</h1>%(subhtml)s</div>
<div class="foot">彤鼎集團　TD GROUP · HONG KONG</div></div>"""


def fit_font(text, box_w, box_h, lo=15, hi=60, lh=1.42):
    """挑一个能把 text 塞进 box 的最大字号。

    中文字宽约等于字号，加上字距按 1.12 倍估；行数按估出的每行字数向上取整。
    宁可小一号——封面被裁掉半行比字小难看得多，上一版就是写死字号才溢出的。
    """
    for f in range(hi, lo - 1, -1):
        per_line = max(1, int(box_w / (f * 1.12)))
        lines = -(-len(text) // per_line)
        if lines * f * lh <= box_h:
            return f
    return lo


def clip(text, n):
    """章节卡副标题超长就在句读处收一刀，配图不是正文，不必塞全。"""
    if len(text) <= n:
        return text
    cut = max(text.rfind(c, 0, n) for c in '，。；、')
    return (text[:cut] if cut > n * 0.5 else text[:n]) + '……'


def crop_png_bottom(path, keep_h):
    """把 PNG 裁到 keep_h 行高（只裁底部）。纯标准库，不引入 Pillow。

    为什么要裁：headless Chromium 的可视视口比 --window-size 矮几十像素
    （实测 500 → 413），而截图输出又是按 window-size 出的。所以渲染时按
    「目标高 + 余量」开窗，保证卡片整个进视口，再把多出来的底部裁掉。
    不这么做，卡片底部的边框与落款就会掉在视口外——生成的图看着「没问题」，
    只是少了一截，很容易一直没人发现。
    """
    import struct
    import zlib
    raw = open(path, 'rb').read()
    if raw[:8] != b'\x89PNG\r\n\x1a\n':
        return False
    pos, idat, ihdr = 8, [], None
    while pos < len(raw):
        ln = struct.unpack('>I', raw[pos:pos + 4])[0]
        typ = raw[pos + 4:pos + 8]
        data = raw[pos + 8:pos + 8 + ln]
        if typ == b'IHDR':
            ihdr = data
        elif typ == b'IDAT':
            idat.append(data)
        pos += 12 + ln
    if not ihdr or not idat:
        return False
    w, h, depth, color, _, _, interlace = struct.unpack('>IIBBBBB', ihdr)
    if depth != 8 or interlace != 0 or keep_h >= h:
        return False
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(color)
    if not channels:
        return False
    stride = 1 + w * channels
    body = zlib.decompress(b''.join(idat))[:keep_h * stride]

    def chunk(typ, data):
        return (struct.pack('>I', len(data)) + typ + data
                + struct.pack('>I', zlib.crc32(typ + data) & 0xffffffff))
    out = (b'\x89PNG\r\n\x1a\n'
           + chunk(b'IHDR', struct.pack('>II', w, keep_h) + ihdr[8:])
           + chunk(b'IDAT', zlib.compress(body, 9))
           + chunk(b'IEND', b''))
    open(path, 'wb').write(out)
    return True


# 开窗时给的余量，必须大于 headless 视口与窗口的高度差（实测 87px）。
VIEWPORT_SLACK = 200


def make_card(path, w, h, eyebrow, title, sub='', big=False):
    pad, padt = int(w * 0.075), int(w * 0.085)
    inner_w = w - 2 * pad
    if sub:
        sub = clip(sub, 52)
    sfs = max(13, int(w * 0.023))
    sub_h = (-(-len(sub) // max(1, int(inner_w / (sfs * 1.1)))) * sfs * 1.75 + sfs * 2) if sub else 0
    avail = h - padt - int(w * 0.11) - int(w * 0.03) - sub_h
    fs = fit_font(title, inner_w, avail, lo=16, hi=int(w * (0.062 if big else 0.05)))
    cfg = dict(w=w, h=h, sans=FONT_SANS, serif=FONT,
               pad=pad, padt=padt, padb=int(w * 0.09), padb2=int(w * 0.05),
               inset=int(w * 0.028),
               eye=int(w * 0.021), eyels=int(w * 0.0075), gap=int(w * 0.022),
               fs=fs, sfs=sfs, ffs=int(w * 0.016),
               eyebrow=_html.escape(eyebrow), title=_html.escape(title),
               subhtml='<div class="sub">%s</div>' % _html.escape(sub) if sub else '')
    scale = 2
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, 'c.html')
        open(f, 'w', encoding='utf-8').write(CARD % cfg)
        subprocess.run([CHROME, '--headless', '--no-sandbox', '--disable-gpu',
                        '--hide-scrollbars', '--force-device-scale-factor=%d' % scale,
                        '--window-size=%d,%d' % (w, h + VIEWPORT_SLACK),
                        '--virtual-time-budget=2500',
                        '--screenshot=' + os.path.abspath(path), 'file://' + f],
                       capture_output=True)
    return os.path.exists(path) and crop_png_bottom(path, h * scale)


def make_images(meta, blocks, outdir):
    """封面图 + 每章一张章节卡。公众号封面按 2.35:1，章节卡按 16:9。

    章节卡上印的是该章的「结论先行」一句话——是文章自己的内容，不是装饰文案。
    """
    _, secs = sections(blocks)
    d = os.path.join(outdir, '配图')
    os.makedirs(d, exist_ok=True)
    made = {}
    # ⚠ 尺寸不能低于 500×500：headless Chromium 的视口有 500px 下限，
    #   比它矮的卡片会按 500 排版再截到指定高度，底部的边框与落款就没了。
    #   所以 2.35:1 用 1175×500 而不是 900×383，比例一样。
    if make_card(os.path.join(d, '00-封面-2.35比1.png'), 1175, 500,
                 meta['cat'], meta['title'], big=True):
        made['cover'] = '配图/00-封面-2.35比1.png'
    make_card(os.path.join(d, '00-封面-1比1.png'), 800, 800,
              meta['cat'], meta['title'], big=True)
    for s in secs:
        one = ''
        for kind, h in s['items']:
            if kind == 'lead':
                one = TAGS(T.parse_lead(h)[0])
                break
        name = '%s-章节卡.png' % s['no']
        if make_card(os.path.join(d, name), 900, 506,
                     'CHAPTER %s' % s['no'], s['title'], one):
            made[s['no']] = '配图/' + name
    return made


# ---------------------------------------------------------------- 落盘

README = """# {title}

官网原文：{url}

本目录由 `python tools/platform_export.py {slug}` 生成，**不进仓库、不上官网**。
每次重跑会整个覆盖，不要在这里手改内容——要改改官网原文再重跑。

## 哪个文件发哪个平台

| 文件 | 平台 | 怎么用 |
|---|---|---|
| `微信公众号.html` | 微信公众号 | 浏览器打开 → 全选复制 → 粘进公众号编辑器。样式全是内联的，粘过去不掉格式。图要在编辑器里重新插入（见下）。 |
| `知乎-头条-百家号.txt` | 知乎 / 头条号 / 百家号 / 企鹅号 / 简书 / 豆瓣 | 直接粘贴。段间已留空行，小标题用【】，不带任何链接。 |
| `微博.txt` | 新浪微博 | 直接粘贴。文末带官网原文与首页两条链接——**这是目前唯一允许正文放链接的平台**。 |
| `小红书-抖音.txt` | 小红书 / 抖音图文 | 摘要版，已压到平台字数上限内。一个链接、一句检索引导都没有。 |

## 配图怎么用

`配图/` 下：

- `00-封面-2.35比1.png` —— 公众号头条封面
- `00-封面-1比1.png` —— 公众号次条 / 分享缩略图
- `NN-章节卡.png` —— 每章一张，插在该章标题下面

公众号编辑器不接受从本地 HTML 粘过来的图，**图要单独上传**：粘完正文后，
按 `微信公众号.html` 里的位置，在每个章节标题下方插入对应的 `NN-章节卡.png`。

## 发布顺序

带链接的平台（微博）必须排在官网 `git push` 且线上能打开之后再发，
否则链接会短暂 404。其余平台不受此限。
"""


def export(slug, with_img=True, list_only=False):
    meta, blocks = load(slug)
    outdir = os.path.join(OUT, slug)
    files = ['微信公众号.html', '知乎-头条-百家号.txt', '微博.txt',
             '小红书-抖音.txt', 'README-发布说明.md']
    if list_only:
        print(slug + ':')
        for f in files:
            print('  ' + os.path.join(outdir, f))
        print('  ' + os.path.join(outdir, '配图/') + '  （封面 2 张 + 章节卡若干）')
        return
    if os.path.isdir(outdir):
        shutil.rmtree(outdir)
    os.makedirs(outdir, exist_ok=True)
    imgs = make_images(meta, blocks, outdir) if with_img else {}

    def w(name, text):
        open(os.path.join(outdir, name), 'w', encoding='utf-8', newline='\n').write(text)

    w('微信公众号.html',
      '<!doctype html><meta charset="utf-8"><title>%s｜公众号版</title>'
      '<meta name="viewport" content="width=device-width,initial-scale=1">'
      '<body style="margin:0 auto;max-width:414px;background:#fff;padding:22px 16px;">'
      '%s' % (_html.escape(meta['title']), render_wechat(meta, blocks, imgs)))
    w('知乎-头条-百家号.txt', render_plain(meta, blocks, SEARCH_HINT))
    w('微博.txt', render_plain(meta, blocks,
                              '本文官网原文：%s\n彤鼎集团官网：%s' % (meta['url'], SITE)))
    w('小红书-抖音.txt', render_short(meta, blocks))
    w('README-发布说明.md', README.format(title=meta['title'], url=meta['url'], slug=slug))
    n = len([f for f in os.listdir(os.path.join(outdir, '配图'))]) if with_img else 0
    print('✓ %-34s → %s（4 个平台稿 + %d 张配图）' % (slug, outdir, n))


def main(argv):
    with_img = '--no-img' not in argv
    list_only = '--list' in argv
    if '--all' in argv:
        slugs = sorted(f[:-5] for f in os.listdir('articles') if f.endswith('.html'))
    else:
        slugs = [a for a in argv if not a.startswith('-')]
    if not slugs:
        print(__doc__)
        return 2
    if with_img and not os.path.exists(CHROME) and not list_only:
        print('提示：找不到 Chromium（%s），本次不生成配图。'
              '在本机跑请把 CHROME 指向本地 Chrome。' % CHROME)
        with_img = False
    for s in slugs:
        export(s, with_img=with_img, list_only=list_only)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
