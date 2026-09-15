#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""新会话开场包生成器。

解决的问题：开新会话省 token，但怕丢记忆。记忆其实不在聊天记录里，
而在仓库文件里——真正会丢的是「上一次会话做到哪、下一步该干嘛」。
本脚本把这一段补上，顺带告诉新会话：这次的活该读哪几份规则、别读哪些。

用法：
    python tools/session_brief.py "给电商线加一篇文章"
    python tools/session_brief.py                 # 不带任务，只出状态快照
    python tools/session_brief.py --copy "…"      # 输出精简版，直接粘给新会话
"""
from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

# 任务关键词 -> 该读的规则文件。命中几条读几条，没命中就只读常驻铁律。
ROUTES = [
    (r"文章|发文|写稿|发布|上线|library|sitemap|llms|合规闸|indexnow",
     ".claude/rules/publishing.md", "文章生产标准 / 合规闸 / 发布八步"),
    (r"初创|早期|天使|股权|startup|founder-equity|合伙人",
     ".claude/rules/line-startup.md", "初创线产品阶梯与抵扣链"),
    (r"\bAI\b|ai-transformation|ai-readiness|智能体|转型线|落地",
     ".claude/rules/line-ai.md", "AI 转型线甲乙两半与红线"),
    (r"资产|电站|光伏|asset-platform|海外资产|节点|阿根廷|马来",
     ".claude/rules/line-asset.md", "资产平台节点表与合规边界"),
    (r"电商|核定|征收|税务|ecommerce-tax",
     ".claude/rules/line-ecommerce.md", "电商税务线口径与禁用词"),
]

ALWAYS = [
    ("CLAUDE.md 第二节", "品牌标准：TD GROUP 彤鼎，⛔ 不许单用 TD"),
    ("CLAUDE.md 第三节", "禁用表述：看主语——讲别人放行，自述能力拦下"),
    ("CLAUDE.md 第六节", "修改边界：品牌文案/合规声明/黑金配色未经要求不动"),
    ("CLAUDE.md 第九节", "分工原则：能自动做的自己做完，别把活推给用户"),
]


def sh(*cmd: str) -> str:
    try:
        return subprocess.run(cmd, cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    except Exception:
        return ""


def snapshot() -> list[str]:
    out = []
    arts = len(list((ROOT / "articles").glob("*.html"))) if (ROOT / "articles").is_dir() else 0
    out.append(f"知识文库 {arts} 篇；分支 {sh('git', 'rev-parse', '--abbrev-ref', 'HEAD') or '?'}")
    log = sh("git", "log", "--oneline", "-5")
    if log:
        out.append("最近 5 次提交：")
        out += [f"  {l}" for l in log.split("\n")]
    dirty = sh("git", "status", "--porcelain")
    out.append(f"工作区：{'有未提交改动 ' + str(len(dirty.splitlines())) + ' 处' if dirty else '干净'}")
    return out


def route(task: str) -> list[tuple[str, str]]:
    hits = []
    for pat, path, why in ROUTES:
        if re.search(pat, task, re.I):
            hits.append((path, why))
    return hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("task", nargs="?", default="", help="一句话说清本次要干什么")
    ap.add_argument("--copy", action="store_true", help="只输出可粘贴的开场白")
    args = ap.parse_args()

    hits = route(args.task) if args.task else []

    if args.copy:
        print(f"本次任务：{args.task or '（待定）'}")
        if hits:
            print("开工前先读：" + "、".join(p for p, _ in hits))
        else:
            print("开工前先读：CLAUDE.md 第零节索引，按表判断要不要读分线规则。")
        print("搜索 articles/ 一律派 Agent 子代理，主会话不直读文章文件。")
        print("收尾跑 backup.py + handover.py。")
        return 0

    print("=" * 62)
    print("  新会话开场包")
    print("=" * 62)
    print(f"\n【本次任务】{args.task or '（未指定）'}\n")

    print("【必读 · 常驻铁律】已在 CLAUDE.md 里，开场自动加载")
    for k, v in ALWAYS:
        print(f"  · {k:<16} {v}")

    print("\n【按需读 · 本次相关】")
    if hits:
        for p, why in hits:
            size = (ROOT / p).stat().st_size if (ROOT / p).exists() else 0
            print(f"  ✅ {p:<34} {why}（{size} 字符）")
        skipped = [p for _, p, _ in ROUTES if p not in {h[0] for h in hits}]
        print(f"  ⛔ 本次不用读：{len(skipped)} 份分线规则，省约 "
              f"{int(sum((ROOT / s).stat().st_size for s in skipped if (ROOT / s).exists()) * 0.55)} token")
    elif args.task:
        print("  未命中分线规则——只按常驻铁律办即可，别翻 .claude/rules/。")
    else:
        print("  （未指定任务，无法判断。带上任务描述再跑一次。）")

    print("\n【站点状态】")
    for l in snapshot():
        print(f"  {l}")

    print("\n【省 token 三条硬规矩】")
    print("  1. 搜索 articles/（260 篇 / 10 MB）派 Agent 子代理，主会话绝不直读文章文件")
    print("  2. 改页面用 Edit 精确替换，不要整页 Read 再整页 Write")
    print("  3. 会话结束前：python tools/backup.py && python tools/handover.py --log \"…\"")
    print("     ⚠ 云端容器一回收，没归档的会话永久消失（CLAUDE.md 第九节）")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
