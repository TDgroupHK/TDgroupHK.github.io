# -*- coding: utf-8 -*-
"""2026-09-11 官网门面改名「TD GROUP 彤鼎」(廖总拍板)。一次性批量替换，幂等。

只改门面位置：title/og/twitter 标题后缀、meta 描述里的机构自称、og:site_name、
JSON-LD 机构 name、logo 字标与 alt、文章作者行/品牌段标题/免责句、RSS 名、llms.txt 抬头。
正文里的「彤鼎集团」「彤鼎」是搜索资产，一个不动；页脚法定名一个不动。
为什么不单用 TD：道明银行在香港注册了「TD」36 类商标。

用法：python tools/rebrand_tdgroup.py          # dry-run，只打印命中数
      python tools/rebrand_tdgroup.py --commit # 真改
"""
import io, json, os, re, sys, collections

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
sys.path.insert(0, os.path.join(REPO, 'tools'))
from freshness_audit import body_hash, LEDGER  # noqa: E402

B = 'TD GROUP 彤鼎'
LEGAL_CN = '彤鼎集团（香港）有限公司'
LD_RE = re.compile(r'(<script type="application/ld\+json">)(.*?)(</script>)', re.S)
META_DESC_RE = re.compile(r'(<meta (?:name="description"|property="og:description"|name="twitter:description") content=")([^"]*)(")')
NEW_ALT = ['彤鼎集團（香港）有限公司', '彤鼎集团', '彤鼎', 'TD Group (Hong Kong) Limited']

# (标签, 旧, 新, 是否正则) —— 全文级
PLAIN = [
    ('M1 首页标题前缀', LEGAL_CN + ' TD Group — ', B + ' — ', False),
    ('M1 文库标题后缀', ' | 彤鼎集团知识文库', ' | ' + B + '知识文库', False),
    ('M1 页面标题后缀', r' \| 彤鼎集团(?=</title>|")', ' | ' + B, True),
    ('M1 about 标题后缀', r' \| TD Group(?=</title>|")', ' | ' + B, True),
    ('M3 og:site_name', 'og:site_name" content="彤鼎集团 TD Group"', 'og:site_name" content="' + B + '"', False),
    ('M5 logo 字标', '<span class="nm">彤鼎集團<small>TD GROUP · HONG KONG</small></span>',
     '<span class="nm">TD GROUP<small>彤鼎</small></span>', False),
    ('M5 logo 字标(测评页)', '<a class="logo" href="/">彤鼎集团<small>TD GROUP</small></a>',
     '<a class="logo" href="/">TD GROUP<small>彤鼎</small></a>', False),
    ('M5 logo alt', 'alt="彤鼎集团 TD Group"', 'alt="' + B + '"', False),
    ('M6 作者行', 'rel="author" style="color:var(--gold-dim);">彤鼎集团团队</a>',
     'rel="author" style="color:var(--gold-dim);">' + B + '团队</a>', False),
    ('M6 品牌段标题', '<h3>关于彤鼎集团与华尔街彤鼎俱乐部</h3>', '<h3>关于 ' + B + '与华尔街彤鼎俱乐部</h3>', False),
    ('M6 免责句', '本文由彤鼎集团团队整理', '本文由 ' + B + '团队整理', False),
    ('M8 RSS 链接名', 'rss+xml" title="彤鼎集团知识文库"', 'rss+xml" title="' + B + '知识文库"', False),
    ('X 英文单用 TD Group', r'\bTD Group (?=designs|extends)', B + ' ', True),
    # CSS：副字从 Georgia 斜体英文改成中文副字（斜体会把汉字压歪）
    ('M5 logo 副字 CSS',
     '.logo .nm small{display:block;color:var(--gold);font-family:Georgia,serif;font-style:italic;font-weight:400;font-size:10.5px;letter-spacing:3px;margin-top:2px;}',
     '.logo .nm small{display:block;color:var(--gold);font-family:"PingFang SC","Noto Sans SC","Microsoft YaHei",sans-serif;font-weight:400;font-size:11px;letter-spacing:9px;margin-top:3px;}', False),
    ('M5 logo 主字 CSS',
     '.logo .nm{color:#fff;font-weight:700;letter-spacing:4px;font-size:17px;}',
     '.logo .nm{color:#fff;font-weight:700;letter-spacing:3px;font-size:17px;font-family:Georgia,"Times New Roman",serif;}', False),
    ('M5 logo 主字 CSS(测评页)',
     '.logo{color:#fff;font-weight:700;letter-spacing:4px;font-size:16px;}',
     '.logo{color:#fff;font-weight:700;letter-spacing:2px;font-size:16px;white-space:nowrap;margin-right:14px;font-family:Georgia,"Times New Roman",serif;}', False),
    ('M5 logo 副字 CSS(测评页)',
     '.logo small{color:var(--gold);font-family:Georgia,serif;font-style:italic;font-weight:400;font-size:10px;letter-spacing:2px;margin-left:10px;}',
     '.logo small{color:var(--gold);font-family:"PingFang SC","Noto Sans SC","Microsoft YaHei",sans-serif;font-weight:400;font-size:11px;letter-spacing:8px;display:block;margin-top:3px;}', False),
]


def ld_fix(block, cnt):
    new = block
    for sp in (False, True):
        c, s = (', ', ': ') if sp else (',', ':')
        old = ('"name"' + s + json.dumps(LEGAL_CN, ensure_ascii=False) + c + '"alternateName"' + s
               + json.dumps(['TD Group (Hong Kong) Limited', '彤鼎集团', 'TD Group'], ensure_ascii=False, separators=(c, s)))
        rep = ('"name"' + s + json.dumps(B, ensure_ascii=False) + c + '"legalName"' + s + '"TD GROUP (HONG KONG) LIMITED"'
               + c + '"alternateName"' + s + json.dumps(NEW_ALT, ensure_ascii=False, separators=(c, s)))
        n = new.count(old)
        if n:
            cnt['M4 主体 Organization(legalName+alternateName)'] += n
            new = new.replace(old, rep)
        club_old = '"Wall Street Tongding Club"' + c + '"彤鼎集团"' + c + '"TD Group"]'
        n = new.count(club_old)
        if n:
            cnt['M4 俱乐部 alternateName 去单用 TD Group'] += n
            new = new.replace(club_old, club_old.replace('"TD Group"]', '"%s"]' % B))
        old = '"name"' + s + '"%s"' % LEGAL_CN
        n = new.count(old)
        if n:
            cnt['M4 author/publisher/provider/worksFor name'] += n
            new = new.replace(old, '"name"' + s + '"%s"' % B)
    return new


def walk_types(o, name, out):
    if isinstance(o, dict):
        if o.get('name') == name:
            out[o.get('@type')] += 1
        for v in o.values():
            walk_types(v, name, out)
    elif isinstance(o, list):
        for v in o:
            walk_types(v, name, out)


def main():
    commit = '--commit' in sys.argv
    cnt = collections.Counter()
    files_hit = collections.defaultdict(set)
    org_types = collections.Counter()
    changed = {}
    bad_json = []
    html = [f for f in os.listdir('.') if f.endswith('.html')] + \
           ['articles/' + f for f in os.listdir('articles') if f.endswith('.html')]
    for f in sorted(html):
        s = io.open(f, encoding='utf-8', newline='').read()
        t = s
        for lab, old, new, rx in PLAIN:
            if rx:
                t, n = re.subn(old, new, t)
            else:
                n = t.count(old)
                t = t.replace(old, new)
            if n:
                cnt[lab] += n
                files_hit[lab].add(f)

        def md(m):
            inner = m.group(2)
            n1 = inner.count(LEGAL_CN + '（TD Group）')
            inner = inner.replace(LEGAL_CN + '（TD Group）', B)
            n2 = inner.count(LEGAL_CN)
            inner = inner.replace(LEGAL_CN, B)
            if n1 + n2:
                cnt['M2 meta 描述机构自称'] += n1 + n2
                files_hit['M2 meta 描述机构自称'].add(f)
            return m.group(1) + inner + m.group(3)
        t = META_DESC_RE.sub(md, t)

        def ld(m):
            try:
                walk_types(json.loads(m.group(2)), LEGAL_CN, org_types)
            except ValueError:
                pass
            before = collections.Counter(cnt)
            nb = ld_fix(m.group(2), cnt)
            for k in cnt:
                if cnt[k] != before.get(k, 0):
                    files_hit[k].add(f)
            try:
                json.loads(nb)
            except ValueError as e:
                bad_json.append((f, str(e)))
            return m.group(1) + nb + m.group(3)
        t = LD_RE.sub(ld, t)
        if t != s:
            changed[f] = (s, t)

    extra = {}
    for f, old, new, lab in (
            ('llms.txt', '# %s TD Group (Hong Kong) Limited' % LEGAL_CN,
             '# TD GROUP 彤鼎（TD GROUP (HONG KONG) LIMITED / 彤鼎集團（香港）有限公司）', 'M8 llms.txt 抬头'),
            ('feed.xml', '<channel><title>彤鼎集团知识文库</title>',
             '<channel><title>TD GROUP 彤鼎知识文库</title>', 'M8 feed.xml 频道名'),
            ('tools/new_article.py', "'%s | 彤鼎集团知识文库'", "'%s | TD GROUP 彤鼎知识文库'", 'M9 new_article 标题后缀'),
            ('tools/add_meta_signals.py', 'style="color:var(--gold-dim);">彤鼎集团团队</a>',
             'style="color:var(--gold-dim);">TD GROUP 彤鼎团队</a>', 'M9 add_meta_signals 作者行')):
        s = io.open(f, encoding='utf-8', newline='').read()
        n = s.count(old)
        cnt[lab] += n
        if n:
            files_hit[lab].add(f)
            extra[f] = (s, s.replace(old, new))

    print('== 命中（处 / 文件）')
    for k in sorted(cnt):
        print('%-44s %5d / %d' % (k, cnt[k], len(files_hit[k])))
    print('JSON-LD 里 name=法定中文名 的 @type 分布:', dict(org_types))
    print('改动 HTML 文件数:', len(changed), ' 其他文件:', len(extra))
    if bad_json:
        print('!! JSON-LD 解析失败:', bad_json[:5])
        sys.exit(2)
    if not commit:
        print('(dry-run，未写盘)')
        return
    led = json.load(io.open(LEDGER, encoding='utf-8'))
    rebased = 0
    for f, (s, t) in changed.items():
        io.open(f, 'w', encoding='utf-8', newline='').write(t)
        if f.startswith('articles/'):
            rec = led.get(f[9:-5])
            if rec and rec.get('body_hash') == body_hash(s):
                rec['body_hash'] = body_hash(t)
                rebased += 1
    for f, (s, t) in extra.items():
        io.open(f, 'w', encoding='utf-8', newline='').write(t)
    io.open(LEDGER, 'w', encoding='utf-8').write(
        json.dumps(led, ensure_ascii=False, indent=1, sort_keys=True))
    print('已写盘；时效台账按「品牌改名不算实质改动」平移 body_hash:', rebased, '篇')


if __name__ == '__main__':
    main()
