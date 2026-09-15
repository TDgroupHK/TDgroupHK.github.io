#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""新会话开场包生成器。

解决的问题：开新会话省 token，但怕丢记忆。记忆其实不在聊天记录里，
而在仓库文件里——真正会丢的是「上一次会话做到哪、下一步该干嘛」。
本脚本把这一段补上，顺带告诉新会话：这次的活该读哪几份规则、别读哪些。

⭐ 2026-09-15 起**全自动**：`.claude/settings.json` 的两个钩子替廖总跑掉了这些，
   他不必记任何命令——
   - `SessionStart` → `--hook-start`：开场自动把「上次做到哪 + 站点状态 + 索引」喂给新会话。
   - `UserPromptSubmit` → `--hook-prompt`：每次他发话，回复之前自动判断该读哪几份规则，
     并把他拍板的话自动记进会话日志。
   手动几个模式仍然保留，供人工排查用。

用法：
    python tools/session_brief.py "给电商线加一篇文章"
    python tools/session_brief.py                 # 不带任务，只出状态快照
    python tools/session_brief.py --copy "…"      # 输出精简版，直接粘给新会话
    python tools/session_brief.py --hook-start    # 钩子用：会话开场注入
    python tools/session_brief.py --hook-prompt   # 钩子用：每轮发话前注入
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

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

# 廖总拍板时的说法。命中就把他的原话自动记进会话日志——
# 这类句子是最值钱也最容易丢的东西（它往往不产生任何提交）。
# ⚠ 宁可多记几条也别漏：日志多一条是噪音，少一条是永久丢失。
DECISION_PAT = re.compile(
    r"拍板|定了|就这么办|全部按照|以后都|从今天起|从现在起|不要再|别再|改成|换成|"
    r"我决定|听我的|就用|取消|撤下|加回|不用了|废弃|方向是|口径是",
)
# 这些是提问或闲聊，不是拍板。命中则不记。
NOT_DECISION_PAT = re.compile(r"^\s*(为什么|怎么|如何|能不能|可以吗|是不是|什么是|有没有)")
DECISION_MAX = 300  # 太长的段落不整段塞进日志


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


def last_log_entry() -> str:
    """会话日志的最后一条——新会话靠它知道「上次做到哪」。"""
    log = ROOT / ".claude" / "session-log.md"
    if not log.exists():
        return ""
    lines = log.read_text(encoding="utf-8").split("\n")
    heads = [i for i, l in enumerate(lines) if l.startswith("## ")]
    if not heads:
        return ""
    entry = "\n".join(lines[heads[-1]:]).strip()
    return entry[:900]


def emit(context: str, event: str) -> None:
    """把内容注入模型上下文。空内容就什么都不发，别白烧 token。"""
    if not context.strip():
        return
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": context.strip(),
        }
    }, ensure_ascii=False))


def read_hook_input() -> dict:
    if sys.stdin.isatty():
        return {}
    try:
        return json.load(sys.stdin) or {}
    except Exception:
        return {}


def hook_start() -> int:
    """SessionStart：把上次的进度和站点状态直接喂给新会话。

    这一段是「新开会话不丢记忆」的落点——记忆本来就在文件里，
    问题只是新会话不知道去翻。现在不用它翻了，开场就在手上。
    """
    read_hook_input()
    parts = ["【本仓库会话开场自动注入，来自 tools/session_brief.py】"]

    last = last_log_entry()
    if last:
        parts.append(f"\n上一次会话留下的记录（`.claude/session-log.md` 末条）：\n{last}")

    parts.append("\n当前状态：" + "；".join(snapshot()[:1]))
    parts.append(
        "\n本次要注意：\n"
        "- 分线细则在 `.claude/rules/`，用到哪条读哪条，⛔ 别一次全读（见 CLAUDE.md 第零节索引表）。\n"
        "- 搜索 `articles/`（260 篇 / 10 MB）派 `article-finder` 子代理，主会话⛔ 不直读文章文件。\n"
        "- 改页面用 Edit 精确替换，⛔ 不要整页 Read 再整页 Write。\n"
        "- 会话结束与压缩前会自动记工作日志，不必手动跑。"
    )
    emit("\n".join(parts), "SessionStart")
    return 0


def hook_prompt() -> int:
    """UserPromptSubmit：廖总每次发话、我回复之前自动做两件事。

    一、判断这活该读哪几份规则，直接告诉模型（省得它自己摸索或全读）。
    二、他要是在拍板，把原话自动记进会话日志——这类话往往不产生任何提交，
        是最容易永久丢失的一类信息。
    """
    data = read_hook_input()
    prompt = str(data.get("prompt") or data.get("user_prompt") or "").strip()
    if not prompt:
        return 0

    out = []

    hits = route(prompt)
    if hits:
        lines = [f"- `{p}`（{why}）" for p, why in hits]
        out.append("【自动路由】本次改动涉及这些分线规则，动手前先读：\n" + "\n".join(lines))

    # 自动捕捉拍板
    if (DECISION_PAT.search(prompt) and not NOT_DECISION_PAT.match(prompt)):
        text = " ".join(prompt.split())[:DECISION_MAX]
        try:
            import datetime
            import session_log
            session_log.append(
                f"\n## {datetime.datetime.now():%Y-%m-%d %H:%M} · "
                f"{sh('git', 'rev-parse', '--abbrev-ref', 'HEAD') or '?'}\n"
                f"\n**廖总原话**：{text}\n"
            )
            out.append(
                "【已自动留痕】这句话像是拍板，已原话记进 `.claude/session-log.md`。"
                "若理解有偏差，用 `session_log.py --decision \"…\"` 补一条准确的。"
            )
        except Exception:
            pass  # 留痕失败绝不打断廖总的对话

    emit("\n\n".join(out), "UserPromptSubmit")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("task", nargs="?", default="", help="一句话说清本次要干什么")
    ap.add_argument("--copy", action="store_true", help="只输出可粘贴的开场白")
    ap.add_argument("--hook-start", action="store_true", help="钩子用：会话开场注入")
    ap.add_argument("--hook-prompt", action="store_true", help="钩子用：每轮发话前注入")
    args = ap.parse_args()

    if args.hook_start:
        return hook_start()
    if args.hook_prompt:
        return hook_prompt()

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
    try:
        sys.exit(main())
    except Exception as e:
        # 钩子绝不能拖垮会话：出错就安静退出，什么都不注入。
        print(f"session_brief 跳过：{e}", file=sys.stderr)
        sys.exit(0)
