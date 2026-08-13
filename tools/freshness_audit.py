# -*- coding: utf-8 -*-
"""挑出「该复核了」的文章，生成本周复核队列。

为什么需要：上市与跨境资本属 YMYL 领域，AI 引擎与搜索引擎在这类话题上对
「内容有多新」尤其敏感。但本站 158 篇文章里，含硬规则的（纳斯达克 75 万美元
净利润线、37 号文、ODI 备案、PCAOB、18A/18C、2500 万美元流通市值新规……）
一旦监管改了，页面就是错的——而错的金融门槛比过时的更伤信任。

排序不是单看「哪篇最久没动」，而是 **久未复核 × 规则锚点密度**：
一篇纯方法论的文章放两年也不会错，一篇通篇是具体门槛数字的文章放三个月就危险。

**本脚本只挑队列、不改任何文件。** 判断规则有没有变需要检索与判断力，
由 weekly-review 定时任务的会话来做；改日期则必须走 bump_modified.py。

用法：
    python tools/freshness_audit.py              # 默认出 6 篇
    python tools/freshness_audit.py -n 10
    python tools/freshness_audit.py --json       # 给会话读的结构化输出
"""
import io
import os
import re
import sys
import glob
import json
import argparse
import datetime
import hashlib

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
LEDGER = os.path.join('tools', 'freshness_ledger.json')

LD_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
ARTICLE_TYPES = ('Article', 'NewsArticle', 'BlogPosting')

# 会过期的「规则锚点」。命中越多，内容对监管变动越敏感。
ANCHORS = [
    # 具名规则与制度
    (r'37\s*号文', '37号文'),
    (r'\bODI\b|境外直接投资备案', 'ODI备案'),
    (r'\bPCAOB\b', 'PCAOB'),
    (r'18A|18C', '港股18A/18C'),
    (r'10b5-1', '10b5-1'),
    (r'Reg\s*[SD]\b|144\s*条|Rule\s*144', '美证券法豁免条款'),
    (r'证监会备案|境外上市备案', '证监会备案'),
    (r'VIE\s*架构|协议控制', 'VIE'),
    (r'红筹', '红筹'),
    (r'SPAC|De-SPAC', 'SPAC'),
    (r'特专科技|同股不同权|WVR', '港交所特别章节'),
    # 硬数字：金额门槛、比例、人数、周期
    (r'\d[\d,\.]*\s*万美元', '美元金额门槛'),
    (r'\d[\d,\.]*\s*(?:万|亿)\s*(?:港元|港币|新元|人民币|元)', '本币金额门槛'),
    (r'\d+(?:\.\d+)?\s*%', '比例/税率'),
    (r'\d+\s*名?(?:公众)?股东', '股东人数'),
    (r'\d+\s*家做市商', '做市商数'),
    (r'\d+\s*[-–至]\s*\d+\s*个月', '周期区间'),
    # 年份：写死年份的内容最容易显旧
    (r'202[4-9]\s*年', '写死年份'),
]
ANCHOR_RE = [(re.compile(p, re.I), n) for p, n in ANCHORS]

# 内容中性、不含时效规则的，降权（不是不复核，是排后面）
LOW_RISK = re.compile(r'(家族|传承|接班|信托|办公室|心法|认知|误区)')


def say(msg):
    try:
        print(msg)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or 'gb18030'
        sys.stdout.write(msg.encode(enc, 'replace').decode(enc, 'replace') + '\n')


def body_text(s):
    """取正文可见文字。剥掉 head、schema、脚本样式，以及 pubmeta（它本身含日期，
    会让「内容有没有变」这个判断被日期自己污染）。

    也剥掉 tools/typeset.py 注入的版式元素——本文要点导览、章节序号、
    「核心结论 / 结论先行 / 实操案例」这类标签。它们是版面不是内容：
    留着的话，2026-08-13 那次全库重排会让 199 篇的哈希同时变化，
    下一次 weekly-review 就会把纯排版改动当成实质更新、集体刷新 dateModified，
    正是本仓库明令禁止的 content refresh spam。"""
    s = s.split('</head>', 1)[-1]
    s = LD_RE.sub('', s)
    s = re.sub(r'<script.*?</script>', '', s, flags=re.S)
    s = re.sub(r'<style.*?</style>', '', s, flags=re.S)
    s = re.sub(r'<div class="pubmeta".*?</div>', '', s, flags=re.S)
    s = re.sub(r'<div class="ts-toc">.*?</ol></div>', '', s, flags=re.S)
    s = re.sub(r'<span class="(?:tag|no)">.*?</span>', '', s, flags=re.S)
    s = re.sub(r'<[^>]+>', ' ', s)
    s = re.sub(r'\s+', '', s)
    # 重排把「结论先行：」从正文提成了标签，两种写法要归一到同一个哈希
    return re.sub(r'结论先行[：:]?', '', s)


def body_hash(s):
    return hashlib.sha256(body_text(s).encode('utf-8')).hexdigest()[:16]


def dates_of(s):
    for b in LD_RE.findall(s):
        try:
            j = json.loads(b)
        except ValueError:
            continue
        for o in (j if isinstance(j, list) else [j]):
            if o.get('@type') in ARTICLE_TYPES:
                return o.get('datePublished'), o.get('dateModified')
    return None, None


def title_of(s):
    m = re.search(r'<h1[^>]*>(.*?)</h1>', s, re.S)
    return re.sub(r'\s+', '', re.sub(r'<[^>]+>', '', m.group(1))) if m else ''


def d(x):
    try:
        return datetime.date(*map(int, x[:10].split('-')))
    except (TypeError, ValueError):
        return None


def load_ledger():
    if os.path.exists(LEDGER):
        return json.load(io.open(LEDGER, encoding='utf-8'))
    return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-n', type=int, default=6, help='返回几篇（默认 6）')
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()

    today = datetime.date.today()
    led = load_ledger()
    rows = []

    for p in sorted(glob.glob('articles/*.html')):
        slug = os.path.basename(p)[:-5]
        s = io.open(p, encoding='utf-8').read()
        pub, mod = dates_of(s)
        txt = body_text(s)

        hits, names = 0, []
        for rx, nm in ANCHOR_RE:
            c = len(rx.findall(txt))
            if c:
                hits += c
                names.append(nm)
        # 密度按千字算，长文不因为长就自动排前面
        density = hits / max(len(txt) / 1000.0, 1.0)

        rec = led.get(slug, {})
        # 基准日：上次人工复核 > dateModified > datePublished
        base = d(rec.get('last_reviewed')) or d(mod) or d(pub) or today
        age = (today - base).days

        score = age * (1.0 + density)
        if LOW_RISK.search(slug) and density < 2:
            score *= 0.45

        rows.append({
            'slug': slug,
            'title': title_of(s),
            'url': 'https://tdgroup.hk/articles/%s.html' % slug,
            'datePublished': pub,
            'dateModified': mod,
            'last_reviewed': rec.get('last_reviewed'),
            'days_since': age,
            'anchor_hits': hits,
            'anchor_density': round(density, 2),
            'anchors': sorted(set(names)),
            'body_hash': body_hash(s),
            'score': round(score, 1),
        })

    rows.sort(key=lambda r: -r['score'])
    top = rows[:a.n]

    if a.json:
        print(json.dumps({'generated': today.isoformat(),
                          'total_articles': len(rows),
                          'queue': top}, ensure_ascii=False, indent=1))
        return 0

    say('本周复核队列（共 %d 篇文章，按 久未复核 × 规则锚点密度 排序）' % len(rows))
    say('=' * 78)
    for i, r in enumerate(top, 1):
        say('%d. %s' % (i, r['title'][:44]))
        say('   %s' % r['url'])
        say('   距上次复核 %d 天 | 规则锚点 %d 处（密度 %.2f/千字）| 分值 %.1f'
            % (r['days_since'], r['anchor_hits'], r['anchor_density'], r['score']))
        say('   要核的规则：%s' % ('、'.join(r['anchors'][:8]) or '无硬规则，只核表述'))
        say('')
    say('复核后如内容确有修改：python tools/bump_modified.py articles/<slug>.html')
    say('复核后确认无需修改：python tools/bump_modified.py articles/<slug>.html --reviewed-only')
    say('⚠ 内容没变就不要动 dateModified——假刷新日期是搜索引擎明确打击的行为。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
