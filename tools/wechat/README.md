# 微信采集白屏排查工具（临时传输，用完请移走）

⚠️ **这个目录不属于官网仓库，只是把文件送到本机的临时通道。**

按 `CLAUDE.md` 第七节第 4 条，内部工具应当存放在私有仓库 `td-internal`。
云端会话拿不到 `td-internal` 的读写权限，而用户不是程序员、不该充当人肉终端
去复制粘贴七百行代码，所以借这个**非 main 分支**做一次传输。

GitHub Pages 只发布 main 分支，因此这些文件不会出现在 https://tdgroup.hk 上。

## 用完之后

1. 本机把两个脚本移进 `td-internal/tools/`；
2. 关掉对应的 PR，删掉分支 `claude/wechat-white-dialog-issue-ukt6d7`；
3. **不要合并进 main。**

## 两个脚本

### `wx4_collect.py`（28875 字节）

微信 4.x 采集底座，解决采集时弹出全屏白框、一关就整个微信退出的问题。

- `python wx4_collect.py --doctor` — **只读体检**。列出微信进程与主窗口、
  哪个是白壳、是不是装了两份微信、腾讯电脑管家在不在跑。不做任何修改。
- `python wx4_collect.py --rescue` — 急救。全杀微信进程后带 CEF 开关重开一个实例，
  等到窗口不再是白的为止。只做 `taskkill /F` 与重新启动两件事，
  不碰 `xwechat_files` 等任何数据文件，也不写注册表。
- `python wx4_collect.py --selftest` — 抓一次完整控件树，写出 `tree.json` / `tree.txt`，
  供改写采集选择器时对照。
- `python wx4_collect.py --watch` — 只跑看门狗，观察白屏发生的时机。

依赖 `comtypes`（`pip install comtypes`）。仅 Windows。

白屏成因与三处对策写在脚本头部的模块 docstring 里。

### `wechat_white_dialog_probe.py`（8450 字节）

更早的一版按键诊断器：跑起来后白框弹出时按 F8，dump 前台窗口的类名、进程、
是否模态、owner、子窗口链与像素纯白度。无第三方依赖。判据写在文件头部注释。

## 未经真机验证

两个脚本都写于 Linux 云端容器，只做过 `py_compile` 语法检查，
Win32 与 COM 调用**一行都没有实际执行过**。首次运行可能需要修正，
重点看 `_uia_snapshot()` 里 `AutomationElementMode` / `TreeScope` 的常量写法，
以及 `ElementFromHandle()` 的参数包装方式（comtypes 各版本行为不一致）。
