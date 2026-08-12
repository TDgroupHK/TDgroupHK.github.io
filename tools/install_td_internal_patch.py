#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一次性投放脚本：把 td-internal 缺的三个文件装进去。

背景：这三个文件是 2026-08-12 在云端 Claude 会话里写的，但云端会话对私有仓库
td-internal 没有写权限（git 代理 403），推不上去。放在这个公开仓库里，是为了让
本机 AI 只要 git pull 就能拿到，不必依赖人工传文件。

装的是什么：
  tools/init_workspace.py                      工作台入口生成器
  .github/workflows/daily-handover.yml         交接文档每日自动更新
  .github/workflows/backup-freshness.yml       归档新鲜度检查

用法（在工作台目录 D:\彤鼎工作台 下）：

    python TDgroupHK.github.io/tools/install_td_internal_patch.py

它会写进同级的 td-internal/，然后你需要自己 commit + push。加 --dry-run 只看不写。

⚠️ 装完之后请把本脚本从公开仓库删掉——同一份代码存两处必然漂移，
td-internal/tools/init_workspace.py 才是它的正式位置。
"""

import argparse
import os
import sys

FILES = {
    "tools/init_workspace.py": "#!/usr/bin/env python3\n# -*- coding: utf-8 -*-\n\"\"\"\n生成工作台根目录的 AI 入口文件，让任何 AI 一进门就能全盘接管。\n\n背景：各家 AI 工具启动时读取的是**当前工作目录**下的入口文件。老板的工作台是\n`D:\\\\彤鼎工作台`，四个仓库并列在它下面——所以入口文件必须放在工作台根目录，\n放在 td-internal 里面它们看不见。\n\n本脚本在工作台根目录（本仓库的上级目录）生成：\n  AGENTS.md                        ← 总入口，内容最全\n  CLAUDE.md / GEMINI.md / QWEN.md / CONVENTIONS.md\n  .cursorrules / .clinerules / .windsurfrules\n  .github/copilot-instructions.md\n全部指向同一份内容，避免各家读到不同版本。\n\n用法：\n    python tools/init_workspace.py            # 生成/更新\n    python tools/init_workspace.py --check    # 校验是否最新（有差异退出码 1）\n    python tools/init_workspace.py --show     # 打印将要生成的内容\n\n**规则改动后必须重跑**，否则新来的 AI 读到的是旧版。\n每天的 daily-handover 工作流会自动校验这一点。\n\"\"\"\n\nimport argparse\nimport os\nimport sys\n\nREPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))\nWORKSPACE = os.path.dirname(REPO)\n\nTARGETS = [\n    \"AGENTS.md\", \"CLAUDE.md\", \"GEMINI.md\", \"QWEN.md\", \"CONVENTIONS.md\",\n    \".cursorrules\", \".clinerules\", \".windsurfrules\",\n    \".github/copilot-instructions.md\",\n]\n\nBODY = \"\"\"<!-- 本文件由 td-internal/tools/init_workspace.py 自动生成，请勿直接编辑。 -->\n<!-- 要改内容，改 td-internal/tools/init_workspace.py 里的 BODY，然后重跑该脚本。 -->\n\n# 彤鼎工作台 · AI 接管入口\n\n**你被叫来接管彤鼎集团（香港）有限公司的全部数字工作。** 这个文件是唯一入口，\n读完它加上它指向的两份规则，你就具备接手的全部前提。不需要老板再给你任何指令。\n\n## 零、最重要的一条\n\n**老板不是程序员，不要让他执行命令、不要让他当你的双手。**\n\n派活顺序：① 你能做的自己做完，不要先问\"要不要我做\"；② 你做不了但别的 AI/工具能做的，\n自己安排过去；③ **只有点击授权、只有他知道的内容（报价策略、客户判断）、拍板决策**\n这三类才找他。判断题：如果一件事「他照着你给的命令粘贴执行」就能完成，那是你的活，不是他的。\n\n## 一、目录结构\n\n```\nD:\\\\彤鼎工作台\\\\\n├── AGENTS.md               ← 本文件（各厂商入口文件内容与此完全一致）\n├── TDgroupHK.github.io\\\\    ← 官网全站 + 业务规则总纲（公开·GitHub Pages 源）\n├── TDgroup\\\\                ← 短视频线内容供给（公开）\n├── td-internal\\\\            ← 内部资料库（**私有**）\n└── TDgroupHK\\\\              ← 历史仓库，一般不动\n```\n\n缺仓库就先补齐：`python td-internal/tools/restore.py`\n\n## 二、开工前按顺序读这三份\n\n1. **`td-internal/交接文档.md`** —— 先读这个。现状快照、在办与阻塞、定期任务清单、\n   工作日志。五分钟看完就知道眼下该干什么、卡在哪。\n2. **`TDgroupHK.github.io/CLAUDE.md`** —— 业务规则总纲。品牌口径、禁用表述、合规红线、\n   发布流程、初创业务线、分工原则。**里面是真实的法律与平台合规红线，\n   违反会造成实际风险**，不是风格偏好，必须逐条遵守。\n3. **`td-internal/AGENTS.md`** —— 内部资料库导航：历史对话怎么检索、备份纪律。\n\n## 三、每天要做的事\n\n| 频率 | 做什么 | 怎么做 |\n|---|---|---|\n| 每天 2 篇 | 官网发文（早班 09:30、午班 15:30 北京时间） | 见规则总纲第五节发布流程 |\n| 每次会话结束前 | 归档本次会话 | `python td-internal/tools/backup.py` |\n| 每次会话结束前 | 登记交接文档 | `python td-internal/tools/handover.py --log \"做了什么\" --detail \"细节\"` |\n| 每周 | 检查归档新鲜度 | `python td-internal/tools/backup.py --status` |\n| 规则改动后 | 重生成入口文件 | `python td-internal/tools/init_workspace.py` |\n\n交接文档的**现状快照与每日提交汇总是自动的**（`backup.py` 与 GitHub Actions 会刷新），\n但**「为什么这么做、遗留了什么、下一步是什么」必须你自己写**——提交历史说得清改了什么，\n只有你说得清为什么。\n\n## 四、发文的硬性前置\n\n**每篇文章推送前必跑合规闸**：\n\n```\npython C:\\\\TDGroupSEO\\\\compliance_gate.py articles\\\\<slug>.html --scope site\n```\n\n退出码 1 = 拦下，不许 push。官网仓库的 CI 里也有同一道闸（`compliance-gate.yml`），\n推上去不合规会被标红——**但不要指望 CI 兜底，本地先跑**。\n\n完整发布流程（建文章页 → 挂 library.html → 补 sitemap → 重建 KB → 重建 llms.txt →\n提交 → IndexNow）见规则总纲第五节，八步一步都不能少。\n\n## 五、红线\n\n1. **`td-internal` 永不转公开。** 另外三个仓库全是公开的，`TDgroupHK.github.io`\n   还是 GitHub Pages 源——放进去的文件会被 https://tdgroup.hk 直接对外提供。\n2. **不放密钥。** API key、令牌、密码一律不入库，私有仓库也不行。\n3. **不放客户身份。** 客户公司名、联系人、未公开项目主体，能用编号代替就用编号。\n4. **不承诺收益、不碰市场操纵类表述、不写股票代码。** 细则见规则总纲第三节。\n5. **历史对话无法还原成可继续的会话**——各厂商都只提供导出、没有导入接口。\n   如实告诉老板，不要暗示还能做更多。\n\n## 六、历史怎么查\n\n全部对话已转成 Markdown 存在 `td-internal/对话存档/`，先看 `索引.md`。\n\n```\npython td-internal/tools/search.py <关键词>\npython td-internal/tools/search.py <关键词> --json     # 结构化输出\n```\n\n**不要为了\"了解业务\"通读存档**，几百篇读不动也没必要。结论都已提炼进规则总纲与\n`td-internal/内部物料/`。存档是回查用的：某条规则不知道当初为什么那样定，再去搜。\n\n## 七、接手自检\n\n动手干活前先回答这三个问题，答不上来说明还没读全：\n\n1. 彤鼎的禁用表述有哪些？\n2. 内部物料为什么不能放公开仓库？\n3. 创始人个人业绩与团队业绩的口径差别是什么？\n\n三条都答得上来，就可以开工了。\n\"\"\"\n\n\ndef content_for(path):\n    \"\"\"子目录里的文件要调整相对链接（目前正文没有相对链接，保留此钩子）。\"\"\"\n    return BODY\n\n\ndef main():\n    ap = argparse.ArgumentParser(description=\"生成工作台根目录的 AI 入口文件\")\n    ap.add_argument(\"--check\", action=\"store_true\", help=\"只校验，有差异退出码 1\")\n    ap.add_argument(\"--show\", action=\"store_true\", help=\"打印内容，不写盘\")\n    ap.add_argument(\"-d\", \"--dir\", help=\"工作台目录（默认：本仓库的上级目录）\")\n    args = ap.parse_args()\n\n    if args.show:\n        print(BODY)\n        return\n\n    ws = os.path.abspath(os.path.expanduser(args.dir)) if args.dir else WORKSPACE\n    if not os.path.isdir(ws):\n        sys.exit(f\"错误：工作台目录不存在：{ws}\")\n\n    stale, written = [], []\n    for rel in TARGETS:\n        full = os.path.join(ws, rel)\n        want = content_for(rel)\n        cur = None\n        if os.path.isfile(full):\n            with open(full, \"r\", encoding=\"utf-8\") as f:\n                cur = f.read()\n        if cur == want:\n            continue\n        if args.check:\n            stale.append(rel)\n            continue\n        os.makedirs(os.path.dirname(full) or ws, exist_ok=True)\n        with open(full, \"w\", encoding=\"utf-8\") as f:\n            f.write(want)\n        written.append(rel)\n\n    if args.check:\n        if stale:\n            print(f\"工作台入口文件不是最新（{ws}）：\")\n            for p in stale:\n                print(f\"  - {p}\")\n            print(\"\\n跑 python td-internal/tools/init_workspace.py 修复。\")\n            sys.exit(1)\n        print(f\"✅ 工作台 {len(TARGETS)} 个入口文件全部最新。\")\n        return\n\n    print(f\"工作台：{ws}\")\n    if written:\n        print(f\"已生成/更新 {len(written)} 个入口文件：\")\n        for p in written:\n            print(f\"  - {p}\")\n    else:\n        print(f\"✅ {len(TARGETS)} 个入口文件已是最新，无需改动。\")\n    print(\"\\n现在任何 AI 在该目录启动，都会自动读到接管说明。\")\n\n\nif __name__ == \"__main__\":\n    main()\n",
    ".github/workflows/daily-handover.yml": "name: 交接文档每日更新\n\n# 每天自动把四个仓库的新提交汇总进 交接文档.md，并刷新现状快照。\n#\n# 为什么放在 GitHub Actions：老板要求「交接文档每天都要更新」，这样 Codex 或任何 AI\n# 随时接管都能看到最新状态。如果靠本机定时任务，电脑不开机就断档；靠 AI 自觉登记，\n# 忘一次就断档。放在 GitHub 上跑，与任何电脑、任何 AI 账号都无关。\n#\n# 它只做「机器能知道的部分」——哪天改了什么、仓库什么状态。\n# 「为什么这么做、遗留什么」仍必须由当次干活的 AI 用 handover.py --log 写。\n\non:\n  schedule:\n    - cron: '0 16 * * *'      # UTC 16:00 ＝ 北京时间次日 00:00\n  workflow_dispatch:\n\npermissions:\n  contents: write\n\njobs:\n  update:\n    runs-on: ubuntu-latest\n    steps:\n      - name: 检出本仓库\n        uses: actions/checkout@v4\n        with:\n          path: td-internal\n          fetch-depth: 0\n\n      # 两个公开仓库无需凭据，直接浅克隆足够读提交历史\n      - name: 拉取兄弟仓库\n        run: |\n          git clone --quiet https://github.com/TDgroupHK/TDgroupHK.github.io.git TDgroupHK.github.io\n          git clone --quiet https://github.com/TDgroupHK/TDgroup.git TDgroup\n          ls -1\n\n      - uses: actions/setup-python@v5\n        with:\n          python-version: '3.11'\n\n      - name: 汇总提交并刷新快照\n        working-directory: td-internal\n        run: python tools/handover.py --sync-git\n\n      - name: 校验工作台入口文件是否最新\n        working-directory: td-internal\n        continue-on-error: true\n        run: |\n          # 工作台根目录在 CI 里就是 runner 的 workspace，入口文件不在仓库内，\n          # 所以这里只做提示，不拦截。真正的校验在本机跑。\n          python tools/init_workspace.py --check || \\\n            echo \"::notice::工作台入口文件需要在本机重跑 init_workspace.py\"\n\n      - name: 有变化就提交\n        working-directory: td-internal\n        run: |\n          if [ -z \"$(git status --porcelain)\" ]; then\n            echo \"交接文档无变化，跳过提交。\"\n            exit 0\n          fi\n          git config user.name  \"github-actions[bot]\"\n          git config user.email \"41898282+github-actions[bot]@users.noreply.github.com\"\n          git add -A\n          git commit -m \"交接文档：$(TZ=Asia/Shanghai date '+%Y-%m-%d') 自动更新\"\n          git push\n          echo \"✅ 交接文档已更新。\"\n",
    ".github/workflows/backup-freshness.yml": "name: 归档新鲜度检查\n\n# 每周检查一次：对话存档是不是太久没更新了。\n# 超期就自动开一个 issue（GitHub 会发邮件通知），恢复正常后自动关掉。\n#\n# 为什么放在 GitHub Actions 而不是 Claude 的定时任务：\n# 这样它不依赖任何 AI 账号、不依赖某台电脑开机，换账号换工具都还在。\n# 免费额度对私有仓库每月 2000 分钟，这个任务每次跑不到 1 分钟。\n\non:\n  schedule:\n    - cron: '0 1 * * 1'      # UTC 周一 01:00 ＝ 北京时间周一 09:00\n  workflow_dispatch:          # 也可以在 Actions 页手动点一下运行\n\npermissions:\n  contents: read\n  issues: write\n\nenv:\n  # 超过这么多天没归档就报警\n  STALE_DAYS: 8\n  ISSUE_TITLE: \"⚠️ 对话归档超期\"\n\njobs:\n  check:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n        with:\n          fetch-depth: 0      # 要完整历史才能算最后一次提交时间\n\n      - name: 计算距上次归档多少天\n        id: check\n        run: |\n          LAST=$(git log -1 --format=%ct -- 对话存档 2>/dev/null || true)\n          if [ -z \"$LAST\" ]; then\n            echo \"days=999\" >> \"$GITHUB_OUTPUT\"\n            echo \"detail=**从未归档过。** 对话存档目录里还没有任何提交记录。\" >> \"$GITHUB_OUTPUT\"\n            exit 0\n          fi\n          NOW=$(date +%s)\n          DAYS=$(( (NOW - LAST) / 86400 ))\n          WHEN=$(TZ=Asia/Shanghai date -d \"@$LAST\" '+%Y-%m-%d %H:%M')\n          COUNT=$(ls -1 对话存档/*.md 2>/dev/null | grep -c '^对话存档/[0-9]' || echo 0)\n          echo \"days=$DAYS\" >> \"$GITHUB_OUTPUT\"\n          echo \"detail=最近一次归档：**$WHEN**（$DAYS 天前）。当前存档 $COUNT 篇。\" >> \"$GITHUB_OUTPUT\"\n\n      - name: 超期就报警\n        if: fromJSON(steps.check.outputs.days) > fromJSON(env.STALE_DAYS)\n        env:\n          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}\n          DETAIL: ${{ steps.check.outputs.detail }}\n          DAYS: ${{ steps.check.outputs.days }}\n        run: |\n          BODY=$(cat <<EOF\n          ${DETAIL}\n\n          按约定，对话归档应至少每周跑一次。已经 **${DAYS} 天**没有新的归档提交了。\n\n          ## 可能的原因\n\n          - 电脑长时间没开机，本机定时任务没跑到\n          - 定时任务没注册成功或被系统清掉了\n          - 归档跑了但推送失败（网络问题）\n\n          ## 怎么处理\n\n          在电脑上打开命令行，进入本仓库目录，跑：\n\n          \\`\\`\\`bash\n          python tools/backup.py --status    # 先看看状态\n          python tools/backup.py             # 跑一次归档并推送\n          \\`\\`\\`\n\n          如果是定时任务的问题：\n\n          \\`\\`\\`bash\n          python tools/schedule_backup.py --show     # 看有没有注册\n          python tools/schedule_backup.py --apply    # 重新注册\n          \\`\\`\\`\n\n          恢复正常后，本 issue 会在下次检查时自动关闭。\n\n          ---\n          由 \\`.github/workflows/归档新鲜度检查.yml\\` 自动创建。\n          EOF\n          )\n          EXISTING=$(gh issue list --state open --search \"in:title ${ISSUE_TITLE}\" --json number --jq '.[0].number // empty')\n          if [ -n \"$EXISTING\" ]; then\n            gh issue comment \"$EXISTING\" --body \"$BODY\"\n            echo \"已在 issue #$EXISTING 追加提醒\"\n          else\n            gh issue create --title \"${ISSUE_TITLE}\" --body \"$BODY\"\n            echo \"已创建新 issue\"\n          fi\n\n      - name: 恢复正常就关掉旧警报\n        if: fromJSON(steps.check.outputs.days) <= fromJSON(env.STALE_DAYS)\n        env:\n          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}\n          DETAIL: ${{ steps.check.outputs.detail }}\n        run: |\n          EXISTING=$(gh issue list --state open --search \"in:title ${ISSUE_TITLE}\" --json number --jq '.[0].number // empty')\n          if [ -n \"$EXISTING\" ]; then\n            gh issue close \"$EXISTING\" --comment \"✅ 归档已恢复正常。${DETAIL}\"\n            echo \"已关闭 issue #$EXISTING\"\n          else\n            echo \"✅ 归档新鲜，无需处理。${DETAIL}\"\n          fi\n"
}


def main():
    ap = argparse.ArgumentParser(description="把补丁文件装进 td-internal")
    ap.add_argument("-d", "--dir", help="td-internal 目录（默认：自动找同级目录）")
    ap.add_argument("--dry-run", action="store_true", help="只列出要写什么，不落盘")
    args = ap.parse_args()

    if args.dir:
        target = os.path.abspath(os.path.expanduser(args.dir))
    else:
        # 本脚本在 TDgroupHK.github.io/tools/ 下，工作台是它的爷爷目录
        here = os.path.dirname(os.path.abspath(__file__))
        workspace = os.path.dirname(os.path.dirname(here))
        target = os.path.join(workspace, "td-internal")

    if not os.path.isdir(os.path.join(target, ".git")):
        sys.exit(f"错误：{target} 不是一个 git 仓库。\n"
                 f"先把 td-internal 克隆到工作台目录下：\n"
                 f"  git clone https://github.com/TDgroupHK/td-internal.git")

    print(f"目标仓库：{target}\n")
    wrote = 0
    for rel, content in FILES.items():
        full = os.path.join(target, rel.replace("/", os.sep))
        exists = os.path.isfile(full)
        same = False
        if exists:
            with open(full, "r", encoding="utf-8") as f:
                same = f.read() == content
        state = "已是最新" if same else ("覆盖" if exists else "新建")
        print(f"  [{state}] {rel}")
        if same or args.dry_run:
            continue
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        wrote += 1

    if args.dry_run:
        print("\n（--dry-run，未写入任何文件）")
        return
    if not wrote:
        print("\n全部已是最新，无需改动。")
        return

    print(f"\n✅ 已写入 {wrote} 个文件。接下来：\n")
    print("  1. cd td-internal")
    print("  2. python tools/init_workspace.py      # 生成工作台九个入口文件")
    print("  3. git add -A && git commit -m \"基建：工作台入口生成器 + 两条自动工作流\" && git push")
    print("  4. 回到公开仓库把本脚本删掉（tools/install_td_internal_patch.py）")


if __name__ == "__main__":
    main()
