# -*- coding: utf-8 -*-
"""给 articles/ 存量文章重排版式。只动版式，不动一个字。

用法：
    python tools/retypeset.py                  # 全部文章
    python tools/retypeset.py rofr-co-sale     # 只处理指定 slug（可多个）
    python tools/retypeset.py --dry-run        # 只报告改动量，不写盘
    python tools/retypeset.py --check          # 有文章尚未重排则退出码 1（CI 用）
    python tools/retypeset.py --force          # 已重排的也重跑（改了 typeset.py 后用）

安全保证：每篇写盘前逐字比对重排前后的正文纯文本，不一致就中止且不写该文件。
新增的导览、章节序号、标签文字不计入比对（见 strip_injected）。

⚠ 本脚本不改 schema 的 dateModified——版式变更不是内容更新，
   拿版式当「本周更新」是 CLAUDE.md 第六节明令禁止的 content refresh spam。
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import typeset as T  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)

MARKER = '<!--typeset:v1-->'
BLOCK = re.compile(r'<(h2|h3|p|div|ul|ol|blockquote|figure|hr)\b[^>]*>.*?</\1>|<hr\s*/?>',
                   re.S | re.I)
# 「结论先行」段有两种写法：整段裹在 <strong> 里，以及只有开头几句裹着（甚至完全没裹）。
LEAD_P = re.compile(r'^<p>\s*(?:<strong>\s*)?结论先行[：:]', re.I)
ANSWER = re.compile(r'^<div class="answer">(.*)</div>$', re.S)


def parse_blocks(body):
    """把正文切成 (kind, html) 块。认不出的原样带走，不丢内容。"""
    blocks, pos = [], 0
    for m in BLOCK.finditer(body):
        if m.start() > pos and body[pos:m.start()].strip():
            blocks.append(('raw', body[pos:m.start()]))
        chunk = m.group(0)
        a = ANSWER.match(chunk)
        if a:
            blocks.append(('answer', a.group(1).strip()))
        elif chunk.lower().startswith('<h2'):
            blocks.append(('h2', re.sub(r'^<h2[^>]*>|</h2>$', '', chunk, flags=re.I)))
        elif LEAD_P.match(chunk):
            inner = re.sub(r'^<p[^>]*>|</p>$', '', chunk, flags=re.I)
            # 加粗改由 .ts-lead / .ts-case 的样式承担，原来的 <strong> 一律去掉：
            # 有的文章只裹了前半段，留着会在卡片中间吊一个没配对的 </strong>。
            inner = re.sub(r'</?strong\s*>', '', inner, flags=re.I)
            blocks.append(('lead', inner.strip()))
        elif chunk.lower().startswith('<p'):
            blocks.append(('p', re.sub(r'^<p[^>]*>|</p>$', '', chunk, flags=re.I)))
        else:
            blocks.append(('raw', chunk))
        pos = m.end()
    if body[pos:].strip():
        blocks.append(('raw', body[pos:]))
    return blocks


STRIP_TOC = re.compile(r'<div class="ts-toc">.*?</ol></div>', re.S)
STRIP_TAG = re.compile(r'<span class="(?:tag|no)">.*?</span>', re.S)


def strip_injected(html):
    """去掉本脚本注入的导览与标签，剩下的应与原文逐字相同。"""
    html = STRIP_TOC.sub('', html)
    return STRIP_TAG.sub('', html)


# ---------------------------------------------------------------- 还原

CARD = re.compile(r'<div class="(answer|ts-lead|ts-case)">(.*?)</div>', re.S)
PTS = re.compile(r'<ol class="ts-pts">(.*?)</ol>', re.S)
CONT = re.compile(r'</p>\s*<p data-ts="1">', re.S)
H2ID = re.compile(r'<h2 id="[^"]*">(?:<span class="no">[^<]*</span>)?(.*?)</h2>', re.S)


def untypeset(body):
    """把已重排的正文还原成重排前的样子，好让 --force 从头再排一次。

    没有它，改动切分参数后重跑只会在已经切碎的段落上再切，越跑越碎，
    而且比对基准会变成上一次的产物而不是原文。
    """
    body = body.replace(MARKER, '')
    body = STRIP_TOC.sub('', body)
    body = re.sub(r'<hr class="ts-hr">', '', body)
    body = H2ID.sub(lambda m: '<h2>%s</h2>' % m.group(1), body)

    def card(m):
        kind, inner = m.group(1), STRIP_TAG.sub('', m.group(2))
        text = ''.join(re.findall(r'<p[^>]*>(.*?)</p>', inner, re.S))
        if kind == 'answer':
            return '<div class="answer">%s</div>' % text
        return ('\x00LEAD\x00' if kind == 'ts-lead' else '') + text
    body = CARD.sub(card, body)
    # 结论卡 + 案例卡还原成原来那一段 <p><strong>结论先行：…</strong></p>
    body = re.sub(r'\x00LEAD\x00(.*?)(?=<h2|<h3|<div|<p|<ol|<ul|<hr|$)',
                  lambda m: '<p><strong>结论先行：%s</strong></p>' % m.group(1),
                  body, flags=re.S)

    def pts(m):
        items = re.findall(r'<li>(.*?)</li>', m.group(1), re.S)
        return '<p>%s</p>' % ''.join(re.sub(r'</?b>', '', it) for it in items)
    body = PTS.sub(pts, body)
    # 被切开的续段并回上一段
    body = CONT.sub('', body)
    return body


def build(body):
    blocks = parse_blocks(body)
    html, sections = T.render_body(blocks)
    toc = T.render_toc(sections)
    if toc:
        # 导览紧跟核心结论金框之后；没有金框就放在最前
        i = html.find('</div>', html.find('<div class="answer">')) if '<div class="answer">' in html else -1
        html = (html[:i + 6] + toc + html[i + 6:]) if i > 0 else toc + html
    return MARKER + html, len(sections)


LEAD_WORD = re.compile(r'结论先行[：:]?')


def verify(old_body, new_body):
    """改版不改字。原文的「结论先行：」前缀被提成标签，比对时两边同样处理。"""
    a = LEAD_WORD.sub('', T.plain_text(old_body))
    b = LEAD_WORD.sub('', T.plain_text(strip_injected(new_body)))
    return a == b, a, b


def inject_css(html):
    """把版式 CSS 写进页面 <style>，已存在则整块替换。"""
    if T.MARK_BEGIN in html:
        return re.sub(re.escape(T.MARK_BEGIN) + r'.*?' + re.escape(T.MARK_END),
                      lambda _: T.CSS, html, flags=re.S)
    i = html.find('</style>')
    if i < 0:
        return html
    return html[:i] + '\n' + T.CSS + '\n' + html[i:]


def process(path, force=False):
    src = open(path, encoding='utf-8').read()
    m = re.search(r'(<article>)(.*?)(</article>)', src, re.S)
    if not m:
        return 'skip', '没有 <article> 正文'
    body = m.group(2)
    if MARKER in body and not force:
        return 'done', '已重排'
    if MARKER in body:
        body = untypeset(body)
    new_body, nsec = build(body)
    ok, a, b = verify(body, new_body)
    if not ok:
        for k in range(min(len(a), len(b))):
            if a[k] != b[k]:
                ctx = '第%d字附近\n  原: %s\n  新: %s' % (k, a[max(0, k - 30):k + 30], b[max(0, k - 30):k + 30])
                break
        else:
            ctx = '长度不同：原 %d 字，新 %d 字' % (len(a), len(b))
        return 'fail', ctx
    out = inject_css(src[:m.start()]) + m.group(1) + new_body + m.group(3) + src[m.end():]
    return 'ok', (out, nsec, T.plain_text(body))


def main(argv):
    force = '--force' in argv
    dry = '--dry-run' in argv
    check = '--check' in argv
    slugs = [a for a in argv if not a.startswith('-')]
    files = ([os.path.join('articles', s if s.endswith('.html') else s + '.html') for s in slugs]
             if slugs else sorted(os.path.join('articles', f) for f in os.listdir('articles')
                                  if f.endswith('.html')))
    stats = {'ok': 0, 'done': 0, 'skip': 0, 'fail': 0}
    pending = []
    for f in files:
        status, payload = process(f, force=force)
        stats[status] += 1
        if status == 'fail':
            print('✗ %s 内容比对不一致，未写入：\n  %s' % (f, payload))
        elif status == 'ok':
            pending.append(f)
            if not dry and not check:
                out, nsec, _ = payload
                open(f, 'w', encoding='utf-8', newline='\n').write(out)
    print('重排 %d 篇 / 已排 %d 篇 / 跳过 %d 篇 / 失败 %d 篇'
          % (stats['ok'], stats['done'], stats['skip'], stats['fail']))
    if check and pending:
        print('以下文章尚未重排：\n  ' + '\n  '.join(pending))
        return 1
    if dry and pending:
        print('（--dry-run，未写盘）')
    return 1 if stats['fail'] else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
