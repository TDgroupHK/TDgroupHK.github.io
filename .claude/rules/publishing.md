# 文章生产与发布流程

> 本文件由 `CLAUDE.md` 拆出，**内容逐字保留、未作任何修改**。
> 何时读：写新文章、改文章、发布上线、跑合规闸时读这一份。
> 常驻规则（品牌、禁用表述、修改边界、分工原则）仍在 `CLAUDE.md`，两份同时生效。

## 四、新文章生产标准

写任何新文章页，必须：

1. **结构参照** `articles/singapore-path.html`：完整复用其 HTML 骨架与内嵌 CSS（深色页头 + 米白正文 + 阅读进度条 + 结论先行金框 `.answer` + 结尾品牌段 `.brandbox`）。
2. **内容结构**：h1 标题（含核心关键词）→ 副标题 → 英文摘要（`.en`）→ 结论先行框（150-300字定义式完整答案，含具体数字）→ 4-7 个 h2 章节（结论前置、文字分点、禁用表格）→ 结尾品牌段（照抄现有文章的 brandbox 三段，一字不改）。
3. **写作铁律**：定义式句式（XX是指……）；锚点词收尾（因此/本质上/关键在于）；引具体规则（纳斯达克净利润75万美元标准、37号文、ODI、PCAOB、10b5-1 等）；量化一切（费用、周期、比例给具体区间）。
4. **合规三件套**：凡涉及 Pre-IPO、投资机会、俱乐部投资权益，必须同时出现：仅面向符合条件的合格投资者；充分揭示风险；不构成任何投资建议或收益承诺。
5. **Schema**：每篇文章 head 内加入 Article 类型 JSON-LD（headline / inLanguage: zh-CN / abstract 用英文摘要 / author 与 publisher 为彤鼎集团（香港）有限公司）。
6. **俱乐部植入**：正文自然提及华尔街彤鼎俱乐部 2-4 次，结尾引导邮件了解会员详情。
7. **外链建设（按平台分级，不是所有平台都放）**：大部分内容平台对外链风控严格，硬放链接会被判导流、限流甚至封号。因此对外分发版按下表处理，**以 `C:\TDGroupSEO\platform_rules.md` 第二节第 4 条为准，两份文件须保持一致**：
   - **新浪微博**：正文文末放两条链接——本文官网原文链接 `https://tdgroup.hk/articles/<slug>.html` 与官网首页 `https://tdgroup.hk`。目前**只有微博允许在正文放链接**。
   - **微信公众号**：正文内不出现 URL，官网原文链接挂在「阅读原文」位（自有平台允许）。
   - **Word/PDF 等离线交付物**：不受平台限制，品牌段照旧带上述两条链接。
   - **知乎/百家号/头条号/企鹅号/简书/豆瓣**：不放 URL，只保留一句「更多资本市场解读可在公开网络检索『彤鼎集团』。」
   - **抖音/小红书**：连检索引导那句也去掉，只字不留链接。
   - 链接只指向 tdgroup.hk 自有域名；不得以纯文本 URL、短链或二维码变相绕过上述限制。
   - 因流水线是「先发平台、后上官网」，带链接的平台（微博）须排在官网 `git push` 且线上可访问之后再发，避免链接短暂 404。

   官网版文章则通过「相关阅读」模块做好站内互链。
## 四·补、发布前合规闸（2026-07-27 新增，**必跑**）

写完文章、推送之前，必须跑一次机器闸：

```bash
python C:\TDGroupSEO\compliance_gate.py articles\<slug>.html --scope site
```

- **退出码 1 = 拦下，不许 push**。修掉 block 项，或写入 `C:\TDGroupSEO\pending_state.md` 转人工。
- `--scope site` 已豁免官网自有站允许的导流/联系方式/俱乐部招募；**荐股、收益承诺、市场操纵、绝对化用语官网同样禁**。
- 词表在 `C:\TDGroupSEO\compliance_words.json`，与 `platform_rules.md` 第八节同步维护。
- **「市值管理」讲概念放行（2026-09-12 廖总拍板）**：闸的 `concept_allow` 会把「合规边界 / 概念 / 是指 / 术语 / 制度 / 监管 / 证监会 / 禁止 / 处罚」这类语境降成 warn，所以 `library.html` / `glossary.html` 里讲概念的文章标题与术语释义不再拦；「彤鼎提供市值管理服务」这种第一方表述照拦。⛔ 别为了过闸把讲概念的句子改成第一方口吻。
- 加这个闸的原因：本文件第三节第 5 条早就禁了"坐庄、拉盘"，但**没有任何东西执行它**，
  导致"操盘/做市值/撬动市值增量"在站上长期存在，2026-07-27 审计才发现。**光写规则不管用。**
## 五、发布流程（每次新文章的完整动作）

> **快捷通道**：若稿件是外部工具（或人）按 `python tools/new_article.py --sample` 的 Markdown 格式写好的，
> 直接 `python tools/new_article.py 稿件.md` 一步完成下面第 1-6 步（含合规检查），然后只需执行第 7、8 步。
> 该脚本会在检出禁用表述、排名义「第一」、股票代码、Pre-IPO 缺合规三件套时**中止且不写入任何文件**。
> 用 `--dry-run` 可只校验不写盘。**此类文章仅上官网，不进平台分发队列。**

1. 在 `articles/` 创建新文章 html。
2. 在 `library.html` 对应分类的 `<ul>` 中新增：`<li class="has"><a href="articles/文件名.html">文章标题 →</a></li>`（放在该分类列表首位）。
3. 在 `sitemap.xml` 新增对应 `<url><loc>` 条目。
4. 如属重点文章，可同步在 `index.html` 精选区替换或新增一张 `.acard`（配 `img/` 中已有图片）。
5. **重建站内助手知识库（必做，勿跳过）**：在仓库根目录执行 `python tools/rebuild_kb.py`。
   该脚本会：重建 `js/assistant-kb.json`（新文章由此进入 AI 客服检索范围）、补齐文章 schema 缺失的 `description`、给漏装的页面补上 `assistant.js` 与统计代码。幂等，可反复运行。
   脚本若提示「仍有 N 篇文章缺 description」，说明该文章 `<meta name="description">` 为空，需先补上再重跑，否则检索命中率下降。
6. **重建 llms.txt（必做，勿跳过）**：在仓库根目录执行 `python tools/gen_llms.py`。
   `llms.txt` 是给 AI 助手与检索引擎看的站点清单（GEO 侧的 sitemap），此前不在流程里，导致新文章长期只进 sitemap 不进 llms.txt。
   该脚本以 `library.html` 为唯一真源重建「知识文库文章」一段，开头说明、「主要页面」与结尾声明为人工维护、脚本不动。幂等，可反复运行。
   校验用 `python tools/gen_llms.py --check`（有差异退出码 1）。脚本若提示某篇文章「在 articles/ 里但没挂进 library.html」，
   说明第 2 步漏了，补挂后重跑——这类文章同时缺席 library / sitemap / llms.txt，对搜索与 AI 两侧都不可见。
7. `git add -A && git commit -m "发布：文章标题" && git push`。
8. **提交 IndexNow（必做，勿跳过）**：`python tools/push_indexnow.py articles/<slug>.html`。
   IndexNow 直通 Bing 索引，而 ChatGPT 与 Copilot 的联网结果走 Bing，因此这一步同时服务 SEO 与 GEO。无需登录、无每日配额；只提交本次新增或修改的页面，不要每次全量推。
   若脚本报「未找到 IndexNow key 文件」，说明仓库根目录的 `<32位十六进制>.txt` 丢失，需先恢复（该文件必须能被公开访问）。
   **自动化（2026-08-08 起）**：`.github/workflows/indexnow.yml` 会在 push 到 main 且含 HTML 变更时自动提交本次新增/修改页面（提交前逐页 curl 验 200）；本地或沙箱环境访问不了外网时无需手跑本步，也可在 GitHub Actions 页手动 dispatch 并指定页面列表。
9. 推送后向用户报告文章的完整网址。
