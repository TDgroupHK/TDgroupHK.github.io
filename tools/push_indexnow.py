# -*- coding: utf-8 -*-
"""向 IndexNow 提交 URL，让 Bing / Yandex 等快速收录（ChatGPT、Copilot 的联网结果走 Bing 索引）。

用法：
    python tools/push_indexnow.py                      # 提交 sitemap 中最近 7 天 lastmod 的页面
    python tools/push_indexnow.py --all                # 提交 sitemap 全部页面
    python tools/push_indexnow.py articles/foo.html …  # 提交指定页面

IndexNow 无需登录、无每日配额限制（建议只提交有变化的页面，不要反复全量推）。
成功返回 HTTP 200 或 202，均表示已接收。
"""
import io
import os
import re
import sys
import json
import datetime
import urllib.request
import urllib.error

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)

HOST = 'tdgroup.hk'
ENDPOINT = 'https://api.indexnow.org/indexnow'


def find_key():
    """key 文件形如 <32位十六进制>.txt，内容与文件名一致，必须能被公开访问。"""
    for f in os.listdir('.'):
        m = re.match(r'^([a-f0-9]{32})\.txt$', f)
        if m:
            return m.group(1)
    return None


def sitemap_urls(recent_days=None):
    sm = io.open('sitemap.xml', encoding='utf-8').read()
    entries = re.findall(r'<url>\s*<loc>([^<]+)</loc>(?:\s*<lastmod>([\d-]+)</lastmod>)?', sm)
    if not entries:  # 兼容单行紧凑写法
        entries = re.findall(r'<loc>([^<]+)</loc><lastmod>([\d-]+)</lastmod>', sm)
    if recent_days is None:
        return [u for u, _ in entries]
    cutoff = datetime.date.today() - datetime.timedelta(days=recent_days)
    out = []
    for u, lm in entries:
        if not lm:
            continue
        try:
            d = datetime.datetime.strptime(lm, '%Y-%m-%d').date()
        except ValueError:
            continue
        if d >= cutoff:
            out.append(u)
    return out


def push(urls, key):
    payload = {
        'host': HOST,
        'key': key,
        'keyLocation': 'https://%s/%s.txt' % (HOST, key),
        'urlList': urls,
    }
    body = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        ENDPOINT, data=body,
        headers={'Content-Type': 'application/json; charset=utf-8'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode('utf-8', 'replace')[:200]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace')[:200]
    except Exception as e:  # 网络异常不应阻断发布流程
        return 0, str(e)[:200]


def main():
    key = find_key()
    if not key:
        print('未找到 IndexNow key 文件（应为 <32位十六进制>.txt 放在仓库根目录），已跳过。')
        return 0

    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if args:
        urls = ['https://%s/%s' % (HOST, a.replace('\\', '/').lstrip('/')) for a in args]
    elif '--all' in sys.argv:
        urls = sitemap_urls()
    else:
        urls = sitemap_urls(recent_days=7)

    if not urls:
        print('没有需要提交的 URL（sitemap 中近 7 天无 lastmod 更新）。')
        return 0

    # IndexNow 单次上限 10000
    urls = urls[:10000]
    status, resp = push(urls, key)
    ok = status in (200, 202)
    msg = 'IndexNow 提交 %d 条 → HTTP %s %s' % (len(urls), status, '成功' if ok else '失败')
    if not ok and resp:
        msg += '\n  响应：' + resp
    try:
        print(msg)
    except UnicodeEncodeError:
        sys.stdout.write(msg.encode('utf-8', 'replace').decode('gbk', 'replace') + '\n')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
