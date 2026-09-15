#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把四个会话钩子装进全局设置，让工作台所有仓库都生效。

背景（廖总 2026-09-15 选的方案）：钩子原本只写在官网仓库的
`.claude/settings.json` 里，只在那个仓库的会话生效。工作台下还有
`TDgroup`、`td-internal`、`TDgroupHK` 三个仓库，要同样的行为就得装全局。

为什么要有这个脚本，而不是手写 JSON：
  全局设置里的命令必须是**绝对路径**，而本机那条路径是
  `D:\\彤鼎工作台\\官网仓库\\tools\\...`——中文目录名、反斜杠、JSON 转义，
  手写极易出错，而**settings.json 一旦格式坏掉，那个文件里的全部设置会静默失效**。
  所以让脚本自己算路径、自己转义。

它只往 `~/.claude/settings.json` 的 hooks 段加这四条，**其余设置一个字不动**
（读-合并-写，不是覆盖）。同名钩子若已存在本脚本装的版本，就地更新而不重复叠加。

用法：
    python tools/install_global_hooks.py            # 装（会先预览再写）
    python tools/install_global_hooks.py --check    # 只看现状，不写
    python tools/install_global_hooks.py --uninstall  # 卸掉本脚本装的那几条
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import sys

TOOLS = pathlib.Path(__file__).resolve().parent
SETTINGS = pathlib.Path.home() / ".claude" / "settings.json"

# 标记：只有带这个标记的钩子条目才归本脚本管，别人手写的一律不碰。
MARK = "tdgroup-session-hooks"

EVENTS = {
    "SessionStart": ("session_brief.py", "--hook-start", "读取上次会话进度"),
    "UserPromptSubmit": ("session_brief.py", "--hook-prompt", "路由规则并留痕"),
    "SessionEnd": ("session_log.py", "", "记录会话工作日志"),
    "PreCompact": ("session_log.py", "", "压缩前落盘"),
}


def build_entry(script: str, flag: str, status: str) -> dict:
    """用 args 形式传参：命令不过 shell，中文路径与空格都不会被拆开。"""
    args = [str(TOOLS / script)]
    if flag:
        args.append(flag)
    return {
        "hooks": [{
            "type": "command",
            "command": sys.executable or "python",
            "args": args,
            "timeout": 20,
            "statusMessage": f"{status}（{MARK}）",
        }]
    }


def is_ours(entry: dict) -> bool:
    return any(MARK in str(h.get("statusMessage", ""))
               for h in entry.get("hooks", []))


def load() -> dict:
    if not SETTINGS.exists():
        return {}
    raw = SETTINGS.read_text(encoding="utf-8").strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        sys.exit(
            f"⛔ {SETTINGS} 不是合法 JSON（{e}）。\n"
            "   先把它修好再装——格式坏掉时那个文件里的全部设置都会静默失效，\n"
            "   所以本脚本拒绝在这种状态下写入。"
        )


def show(cfg: dict) -> None:
    hooks = cfg.get("hooks", {})
    print(f"全局设置：{SETTINGS}"
          f"{'（还不存在）' if not SETTINGS.exists() else ''}")
    print(f"脚本目录：{TOOLS}\n")
    for ev in EVENTS:
        entries = hooks.get(ev, [])
        ours = [e for e in entries if is_ours(e)]
        other = len(entries) - len(ours)
        mark = "✅ 已装" if ours else "— 未装"
        extra = f"；另有 {other} 条别人的（不会动）" if other else ""
        print(f"  {ev:<18} {mark}{extra}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只看现状，不写")
    ap.add_argument("--uninstall", action="store_true", help="卸掉本脚本装的那几条")
    args = ap.parse_args()

    for s in ("session_brief.py", "session_log.py"):
        if not (TOOLS / s).exists():
            sys.exit(f"⛔ 找不到 {TOOLS / s}——请在官网仓库里运行本脚本。")

    cfg = load()
    show(cfg)
    if args.check:
        return 0

    if SETTINGS.exists():
        backup = SETTINGS.with_suffix(".json.bak")
        shutil.copy2(SETTINGS, backup)
        print(f"\n已备份到 {backup}")

    hooks = cfg.setdefault("hooks", {})
    changed = []
    for ev, (script, flag, status) in EVENTS.items():
        entries = [e for e in hooks.get(ev, []) if not is_ours(e)]  # 留下别人的
        if not args.uninstall:
            entries.append(build_entry(script, flag, status))
        if entries:
            hooks[ev] = entries
        else:
            hooks.pop(ev, None)
        changed.append(ev)
    if not hooks:
        cfg.pop("hooks", None)

    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")

    # 写完立刻回读一遍：坏掉的 settings.json 是静默失效的，不能等下次会话才发现。
    try:
        json.loads(SETTINGS.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.exit(f"⛔ 写出的 JSON 不合法（{e}）——请从 .bak 还原。")

    verb = "卸载" if args.uninstall else "安装"
    print(f"\n✅ {verb}完成：{'、'.join(changed)}")
    print(f"   {SETTINGS}")
    if not args.uninstall:
        print("\n现在工作台所有仓库的会话都会自动：开场读上次进度、发话前路由规则、"
              "结束与压缩前落盘。")
        print("⚠ 当前已开着的会话不会立刻生效——打开一次 /hooks 重载，或重开会话。")
        print("⚠ 官网仓库自己的 .claude/settings.json 保留不动：它归仓库管，"
              "换机器或别人克隆时照样有。两边同名钩子会各跑一次，"
              "落盘脚本是幂等的（没新提交就不写），不会记重。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
