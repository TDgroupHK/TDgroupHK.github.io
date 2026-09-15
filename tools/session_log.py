#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""会话工作日志：把「这次会话做了什么」自动落盘。

为什么不是「每 5 轮总结一次」：
    总结本身要先把历史读一遍（输入）再写出摘要（输出），而且重写历史会让
    prompt cache 失效——后续每一轮都得按全价重新缓存一遍新前缀。
    在历史还小的时候（5 轮）这笔账必亏。压缩只有在上下文真的快满时才划算，
    那正是 Claude Code 自带的 /compact 和自动压缩在做的事，不用另造一套。

真正会丢的不是 token，是**只在聊天里说过、没写进文件的结论**。这个脚本管那一段：
会话结束时自动记下客观事实（分支、提交、改了哪些文件），决策由人或 AI 用
--decision 补一句。两者合起来才是接班人能看懂的东西。

用法：
    python tools/session_log.py                      # 钩子模式：自动记事实
    python tools/session_log.py --decision "廖总定：导航收成两组"
    python tools/session_log.py --status             # 看最近几条
"""
from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import subprocess
import sys

# ⚠ Windows 下钩子的 stdin/stdout 默认是 GBK，中文与 ⛔ 会乱码或抛错。统一成 UTF-8。
for _s in (sys.stdin, sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def work_root() -> pathlib.Path:
    """当前会话实际在哪个仓库里干活。

    ⚠ 不能写死成本脚本所在的官网仓库：钩子装进 `~/.claude/settings.json` 后
    是全局的，廖总在 `TDgroup`、`td-internal` 里开会话时也会跑到这里。
    那时该记的是**那个**仓库的分支与提交，不是官网仓库的。
    所以以 cwd 的 git 顶层为准，取不到才退回本脚本所在的仓库。
    """
    try:
        # ⚠ 必须显式 utf-8：Windows 默认按 GBK 解码，「彤鼎工作台」这种中文路径
        # 会解码失败，静默退回官网仓库——别的仓库的日志就全记错地方了。
        r = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True, timeout=15,
                           encoding="utf-8", errors="replace")
        if r.returncode == 0 and r.stdout.strip():
            return pathlib.Path(r.stdout.strip()).resolve()
    except Exception:
        pass
    return pathlib.Path(__file__).resolve().parent.parent


ROOT = work_root()
LOG = ROOT / ".claude" / "session-log.md"
STATE = ROOT / ".claude" / ".session-state.json"

HEADER = """# 会话工作日志

> 由 `tools/session_log.py` 追加（SessionEnd 钩子自动触发，见 `.claude/settings.json`）。
> 记的是**事实**：哪个分支、提交了什么、动了哪些文件。
> **决策**要自己补：`python tools/session_log.py --decision "一句话"`。
>
> ⚠ 这份文件要跟着代码一起提交推送。云端容器一回收，没推上去的就永久没了。
> 完整的交接现状仍在 `td-internal/交接文档.md`（私有仓库，本机维护）。

"""


def sh(*cmd: str, default: str = "") -> str:
    try:
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=15,
                           encoding="utf-8", errors="replace")
        return r.stdout.strip() if r.returncode == 0 else default
    except Exception:
        return default


def default_branch() -> str:
    ref = sh("git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    return ref.split("/")[-1] if ref else "main"


def read_state() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_state(d: dict) -> None:
    try:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def new_commits(since: str | None) -> list[str]:
    """这次会话新增的提交。没有基线时退回「本分支相对默认分支多出来的」。"""
    rng = f"{since}..HEAD" if since else f"origin/{default_branch()}..HEAD"
    out = sh("git", "log", "--oneline", "--no-decorate", rng)
    return [l for l in out.split("\n") if l.strip()]


def changed_files(since: str | None) -> list[str]:
    rng = f"{since}..HEAD" if since else f"origin/{default_branch()}..HEAD"
    out = sh("git", "diff", "--name-only", rng)
    return [l for l in out.split("\n") if l.strip()]


def ensure_log() -> None:
    if not LOG.exists():
        LOG.parent.mkdir(parents=True, exist_ok=True)
        LOG.write_text(HEADER, encoding="utf-8")


def append(entry: str) -> None:
    ensure_log()
    with LOG.open("a", encoding="utf-8") as f:
        f.write(entry)


def show_status() -> int:
    if not LOG.exists():
        print("还没有任何会话日志。")
        return 0
    lines = LOG.read_text(encoding="utf-8").split("\n")
    entries = [i for i, l in enumerate(lines) if l.startswith("## ")]
    print(f"{LOG.relative_to(ROOT)}：共 {len(entries)} 条\n")
    for i in entries[-3:]:
        end = next((j for j in entries if j > i), len(lines))
        print("\n".join(lines[i:end]).rstrip() + "\n")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--decision", help="这次会话定下来的事，一句话")
    ap.add_argument("--status", action="store_true", help="看最近三条")
    args = ap.parse_args()

    if args.status:
        return show_status()

    # 钩子模式下 stdin 是 JSON；没有也无所谓。
    session_id = ""
    if not sys.stdin.isatty():
        try:
            session_id = (json.load(sys.stdin) or {}).get("session_id", "")
        except Exception:
            pass

    state = read_state()
    since = state.get("last_sha")
    commits = new_commits(since)
    files = changed_files(since)
    head = sh("git", "rev-parse", "--short", "HEAD")
    branch = sh("git", "rev-parse", "--abbrev-ref", "HEAD", default="?")

    # 什么都没发生就不写——日志里全是空条目等于没有日志。
    if not commits and not args.decision:
        write_state({**state, "last_sha": head or since})
        return 0

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    out = [f"\n## {now} · {branch}"]
    if session_id:
        out.append(f"\n会话 `{session_id[:24]}`")
    if args.decision:
        out.append(f"\n**决策**：{args.decision}")
    if commits:
        out.append(f"\n提交 {len(commits)} 个：")
        out += [f"- `{c}`" for c in commits[:12]]
        if len(commits) > 12:
            out.append(f"- …另有 {len(commits) - 12} 个")
    if files:
        out.append(f"\n改动 {len(files)} 个文件："
                   + "、".join(f"`{f}`" for f in files[:10])
                   + (f" …等 {len(files)} 个" if len(files) > 10 else ""))
    out.append("")

    append("\n".join(out) + "\n")
    write_state({**state, "last_sha": head or since})

    # 钩子输出 JSON，Claude Code 会把 systemMessage 显示给用户。
    msg = f"已记入 .claude/session-log.md（{len(commits)} 个提交）"
    if not args.decision:
        msg += "；决策未记——用 session_log.py --decision \"…\" 补一句"
    msg += "。⚠ 这份日志要提交推送才留得住。"
    print(json.dumps({"systemMessage": msg}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        # 钩子绝不能拖垮会话：出错就安静退出。
        print(f"session_log 跳过：{e}", file=sys.stderr)
        sys.exit(0)
