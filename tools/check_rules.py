#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""规则分层完整性校验。

CLAUDE.md 在 2026-09-15 拆成「常驻铁律 + .claude/rules/ 分线细则」两层，
目的是把每次会话的常驻 token 从约 13,000 降到约 6,400。

本脚本只管两件事：

1. **搬走的那几节没丢字。** 以拆分前的提交为基线，核对四、五、七、十、
   十一、十二节的正文如今完整躺在 .claude/rules/ 里。⚠ 留在 CLAUDE.md 的
   常驻节（一、二、三、六、八、九）**不比对基线**——那几节本来就要持续修订，
   拿基线卡它们只会逼人去关闸。它们的历史由 git 本身保管。
2. **CLAUDE.md 没有重新胖回去。** 常驻体积卡在 RESIDENT_LIMIT 以内。

搬走的节日后确需修订（比如廖总改了某条线的报价），改 .claude/rules/ 里那份，
然后用 --bless 把基线滚到当前提交，并在 commit message 里写清改了什么。

用法：
    python tools/check_rules.py                 # 跑闸
    python tools/check_rules.py --base <ref>    # 指定别的基线
    python tools/check_rules.py --list          # 只列当前分层结构与体量
    python tools/check_rules.py --bless         # 修订分线规则后滚动基线
"""
from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
RULES_DIR = ROOT / ".claude" / "rules"
# 拆分前最后一个含完整 CLAUDE.md 的提交
DEFAULT_BASE = "0579d61"

# 被搬进 .claude/rules/ 的节——只有这几节拿基线严格比对。
# 留在 CLAUDE.md 的常驻节要持续修订，不在此列。
MOVED_SECTIONS = (
    "四、新文章生产标准",
    "四·补、发布前合规闸",
    "五、发布流程",
    "七、初创客群业务线",
    "十、AI 转型线",
    "十一、资产型上市资本平台",
    "十二、电商核定征收线",
)

# 常驻体积上限。CLAUDE.md 每涨 1 KB，每次会话、每个定时班次都多烧一份，
# 所以给它一个会报警的天花板——新规则该进 .claude/rules/，不是往这里堆。
# 拆分后约 11.3 KB，留 3 KB 余量给铁律本身的增补。
RESIDENT_LIMIT = 14000


def norm(text: str) -> str:
    """抹掉空白差异后比对——搬家允许换行收尾不同，不允许改字。"""
    return re.sub(r"\s+", "", text)


def split_sections(md: str) -> dict[str, str]:
    lines = md.split("\n")
    heads = [i for i, l in enumerate(lines) if l.startswith("## ")]
    heads.append(len(lines))
    out = {}
    for a, b in zip(heads, heads[1:]):
        title = lines[a][3:].strip()
        out[title] = "\n".join(lines[a + 1 : b]).strip()
    return out


BASELINE_FILE = RULES_DIR / ".baseline"


def baseline_ref() -> str:
    """基线 ref。修订分线规则后用 --bless 滚动它，不必改本脚本源码。"""
    if BASELINE_FILE.exists():
        ref = BASELINE_FILE.read_text(encoding="utf-8").strip().split("\n")[0]
        if ref and not ref.startswith("#"):
            return ref
    return DEFAULT_BASE


def sh_head() -> str:
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                          cwd=ROOT, capture_output=True, text=True,
                          check=True).stdout.strip()


def load_base(ref: str) -> str:
    try:
        return subprocess.run(
            ["git", "show", f"{ref}:CLAUDE.md"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout
    except subprocess.CalledProcessError as e:
        sys.exit(f"取不到基线 {ref}:CLAUDE.md —— {e.stderr.strip()}")


def current_corpus() -> tuple[str, dict[str, int]]:
    """当前分层里的全部规则文本，以及各文件体量。"""
    parts = [(ROOT / "CLAUDE.md").read_text(encoding="utf-8")]
    sizes = {"CLAUDE.md": len(parts[0])}
    for p in sorted(RULES_DIR.glob("*.md")):
        t = p.read_text(encoding="utf-8")
        parts.append(t)
        sizes[str(p.relative_to(ROOT))] = len(t)
    return "\n".join(parts), sizes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=None, help="基线 git ref（默认读 .claude/rules/.baseline）")
    ap.add_argument("--list", action="store_true", help="只列结构不校验")
    ap.add_argument("--bless", action="store_true",
                    help="有意修订了分线规则后，把基线滚到当前 HEAD")
    args = ap.parse_args()
    if args.base is None:
        args.base = baseline_ref()

    if args.bless:
        head = sh_head()
        BASELINE_FILE.write_text(
            "# tools/check_rules.py 的比对基线。\n"
            "# 有意修订 .claude/rules/ 里的分线规则后，用 --bless 滚动到当前提交，\n"
            "# 并在 commit message 里写清改了哪条线的什么。\n"
            f"{head}\n", encoding="utf-8")
        print(f"基线已滚到 {head}（写入 {BASELINE_FILE.relative_to(ROOT)}）")
        print("⚠ 记得把这个文件一起提交，否则 CI 上的闸仍用旧基线。")
        return 0

    corpus, sizes = current_corpus()

    resident = sizes.get("CLAUDE.md", 0)
    on_demand = sum(v for k, v in sizes.items() if k != "CLAUDE.md")
    print("当前分层：")
    for k, v in sizes.items():
        tag = "常驻" if k == "CLAUDE.md" else "按需"
        print(f"  [{tag}] {k:<36} {v:>6} 字符  ≈{int(v * 0.55):>5} tok")
    print(f"  常驻合计 {resident} 字符 ≈{int(resident * 0.55)} tok；"
          f"按需 {on_demand} 字符（用到才读）")

    if args.list:
        return 0

    base = load_base(args.base)
    want = split_sections(base)
    body = norm(corpus)

    checked, missing = [], []
    for title, content in want.items():
        if not content or not title.startswith(MOVED_SECTIONS):
            continue
        checked.append(title)
        if norm(content) not in body:
            missing.append(title)

    failed = False

    print(f"\n以 {args.base} 为基线核对搬走的 {len(checked)} 节：", end=" ")
    if missing:
        print(f"❌ {len(missing)} 节内容对不上")
        for t in missing:
            print(f"    缺：{t}")
        print("\n拆分的前提是一个字都不丢。把缺失内容补回 CLAUDE.md 或对应 rules 文件。")
        failed = True
    else:
        print("✅ 全部完整，一字未丢")

    print(f"常驻体积闸（上限 {RESIDENT_LIMIT} 字符）：", end=" ")
    if resident > RESIDENT_LIMIT:
        print(f"❌ CLAUDE.md 已 {resident} 字符，超出 {resident - RESIDENT_LIMIT}")
        print("  常驻规则每涨一点，每次会话和每个定时班次都多烧一份。")
        print("  新增的分线细则请挪进 .claude/rules/，并在 CLAUDE.md 第零节索引表加一行。")
        failed = True
    else:
        print(f"✅ {resident} 字符，余量 {RESIDENT_LIMIT - resident}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
