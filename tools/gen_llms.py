# -*- coding: utf-8 -*-
"""从 library.html 重建 llms.txt 的「知识文库文章」清单（给 AI 抓取器看的站点清单）。

用法：
    python tools/gen_llms.py            # 重建 llms.txt 并打印增删摘要
    python tools/gen_llms.py --check    # 只检查不写盘（有差异时退出码 1，可用于校验）

为什么需要：sitemap.xml 服务传统搜索引擎，llms.txt 服务 AI 助手与检索引擎（GEO）。
此前发布流程只更新 library / sitemap / assistant-kb，llms.txt 长期停在旧版本，
新文章对 AI 侧完全不可见。本脚本把它变成可重复执行的一步。

设计：
- 文章清单以 library.html 为唯一真源（分类、顺序、标题都跟着它走），与官网导航保持一致。
- llms.txt 的开头说明、「主要页面」、结尾声明为人工维护，脚本不碰，只替换文章清单一段。
- 幂等：内容无变化时不写盘。
"""
import io
import os
import re
import sys
import html

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)

SITE = 'https://tdgroup.hk'
LLMS = 'llms.txt'
LIBRARY = 'library.html'
SECTION_HEAD = '## 知识文库文章'
SECTION_END = '## 声明'

CAT_RE = re.compile(
    r'<div class="lib-cat[^"]*">\s*<h2>(.*?)</h2>\s*<div class="cen">(.*?)</div>\s*<ul>(.*?)</ul>',
    re.S)
LI_RE = re.compile(r'<li class="has">\s*<a href="(articles/[^"]+\.html)">(.*?)</a>\s*</li>', re.S)


def text_of(s):
    """去掉标签与结尾箭头，还原 HTML 实体（llms.txt 是纯文本，不该留 &amp;）。"""
    s = re.sub(r'<[^>]+>', '', s)
    s = html.unescape(s).strip()
    return re.sub(r'\s*→\s*$', '', s).strip()


def parse_library():
    raw = io.open(LIBRARY, encoding='utf-8').read()
    cats = []
    for zh, en, ul in CAT_RE.findall(raw):
        items = [(href, text_of(title)) for href, title in LI_RE.findall(ul)]
        cats.append((text_of(zh), text_of(en), items))
    return cats


def build_section(cats):
    lines = [SECTION_HEAD, '']
    for zh, en, items in cats:
        lines.append('### %s / %s' % (zh, en))
        lines.append('')
        for href, title in items:
            lines.append('- [%s](%s/%s)' % (title, SITE, href))
        lines.append('')
    return lines


def slugs_in(lines):
    return set(re.findall(r'/articles/([^/)]+)\.html', '\n'.join(lines)))


def main():
    if not os.path.exists(LLMS) or not os.path.exists(LIBRARY):
        print('缺少 llms.txt 或 library.html，已跳过。')
        return 1

    raw = io.open(LLMS, encoding='utf-8', newline='').read()
    nl = '\r\n' if '\r\n' in raw else '\n'
    lines = raw.replace('\r\n', '\n').split('\n')

    try:
        i = lines.index(SECTION_HEAD)
        j = lines.index(SECTION_END)
    except ValueError:
        print('llms.txt 里找不到「%s」或「%s」标题，结构已变，请人工确认后再跑。'
              % (SECTION_HEAD, SECTION_END))
        return 1
    if j < i:
        print('llms.txt 的「%s」出现在「%s」之前，结构异常。' % (SECTION_END, SECTION_HEAD))
        return 1

    cats = parse_library()
    listed = [href for _, _, items in cats for href, _ in items]
    if not listed:
        print('library.html 里没解析到任何文章，正则可能已失配，未改动 llms.txt。')
        return 1

    # 硬校验：清单里的文章必须在磁盘上存在（精确路径比对，不用子串）
    missing = [h for h in listed if not os.path.exists(h.replace('/', os.sep))]
    if missing:
        print('library.html 指向的文件不存在，先修 library 再跑：')
        for h in missing:
            print('  - ' + h)
        return 1

    old_slugs = slugs_in(lines[i:j])
    new_lines = lines[:i] + build_section(cats) + lines[j:]
    new_slugs = slugs_in(build_section(cats))

    added = sorted(new_slugs - old_slugs)
    removed = sorted(old_slugs - new_slugs)

    # 软提醒：磁盘上有、但 library.html 没挂的文章 —— 它们不会进 llms.txt，AI 侧看不见
    on_disk = set(f[:-5] for f in os.listdir('articles') if f.endswith('.html'))
    orphans = sorted(on_disk - new_slugs)

    out = nl.join(new_lines)
    changed = out != raw

    if '--check' in sys.argv:
        print('llms.txt %s（文章 %d 篇）' % ('需要更新' if changed else '已是最新', len(listed)))
    elif changed:
        io.open(LLMS, 'w', encoding='utf-8', newline='').write(out)
        print('llms.txt 已重建：%d 篇文章 / %d 个分类' % (len(listed), len(cats)))
    else:
        print('llms.txt 无变化：%d 篇文章 / %d 个分类' % (len(listed), len(cats)))

    for slug in added:
        print('  + ' + slug)
    for slug in removed:
        print('  - ' + slug)
    if orphans:
        print('提醒：以下文章在 articles/ 里但没挂进 library.html，因此不会进 llms.txt：')
        for slug in orphans:
            print('  ! ' + slug)

    return 1 if ('--check' in sys.argv and changed) else 0


if __name__ == '__main__':
    sys.exit(main())
