# -*- coding: utf-8 -*-
"""
微信 4.x 采集底座（抗白屏）
===========================

解决的问题
----------
微信 4.x 界面由 Chromium(CEF) 渲染。Chromium 的无障碍树平时是关的，一旦检测到
有辅助技术访问才动态切到完整模式。老式 UIAutomation 采集代码逐节点取属性，
一次遍历就是几千次跨进程 COM 调用打进渲染进程，叠加「运行中动态开启 a11y」
这个本身就不稳的切换，把渲染进程拖挂 —— 屏幕上剩一个纯白窗口，它没有 owner，
所以关掉就整个微信退出；它挡着，所以采集拿不到控件树。

本底座的三处对策
----------------
1. 启动参数     : --force-renderer-accessibility 让 a11y 从进程启动就常开，
                  绕开中途切换那个崩点；--disable-gpu 灭掉合成类白屏。
2. 缓存请求取树 : BuildUpdatedCache + TreeScope_Subtree + AutomationElementMode_None，
                  整棵子树一次跨进程调用取回，之后纯本地内存遍历。
                  几千次 RPC -> 1 次。这是决定性的一处。
3. 子进程 + 看门狗 : 快照在独立子进程里做，挂了挂的是子进程；父进程超时即杀。
                  看门狗识别白屏/无响应后自动重启微信、从断点续采。

用法
----
  python wx4_collect.py --rescue
      白框已经出来了就跑这个。体检 -> 全杀微信 -> 带 CEF 开关重开一个实例
      -> 等到窗口不再是白的为止。

  python wx4_collect.py --doctor
      只看不动：几个微信进程、几个主窗口、哪个是白壳、是不是装了两份、
      腾讯电脑管家在不在跑。

  python wx4_collect.py --selftest
      抓一次完整控件树，存成 tree.json + tree.txt。**先跑这个** ——
      有了树的实际形状，才能把 WeChat 特有的选择器写对。

  python wx4_collect.py --watch
      只跑看门狗，观察白屏什么时候发生、发生前在做什么。

  作为库用：
      from wx4_collect import Harness
      def collect(tree, h):        # tree 是纯 dict，不含任何 COM 引用
          ...                       # 你的采集逻辑，用 find() 定位节点
          return {"done": True}     # 返回 truthy 表示这一轮采完了
      Harness().run(collect)

依赖：pip install comtypes
只跑 Windows。Python 3.8+。
"""

from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import json
import os
import subprocess
import sys
import threading
import time

if not sys.platform.startswith("win"):
    sys.exit("这个脚本只能在 Windows 上跑。")

HERE = os.path.dirname(os.path.abspath(__file__))
CHECKPOINT = os.path.join(HERE, "wx4_checkpoint.json")

WECHAT_EXES = ("weixin.exe", "wechat.exe")

# 让 a11y 从启动就常开（避开中途切换的崩点）+ 关掉 GPU 合成（灭白屏）
CEF_SWITCHES = ["--force-renderer-accessibility", "--disable-gpu"]


# ----------------------------------------------------------------------------
# Win32 基础设施（不碰 COM，因此可以安全地跑在看门狗线程里）
# ----------------------------------------------------------------------------

u32 = ctypes.WinDLL("user32", use_last_error=True)
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
gdi = ctypes.WinDLL("gdi32", use_last_error=True)

for _setter in (lambda: ctypes.WinDLL("shcore").SetProcessDpiAwareness(2),
                lambda: u32.SetProcessDPIAware()):
    try:
        _setter()
        break
    except Exception:
        continue

u32.GetWindow.argtypes = [wt.HWND, wt.UINT]
u32.GetWindow.restype = wt.HWND
u32.GetDC.argtypes = [wt.HWND]
u32.GetDC.restype = wt.HDC
u32.ReleaseDC.argtypes = [wt.HWND, wt.HDC]
gdi.GetPixel.argtypes = [wt.HDC, ctypes.c_int, ctypes.c_int]
gdi.GetPixel.restype = wt.DWORD

WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)


def _proc_path(pid: int) -> str:
    h = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return ""
    try:
        size = wt.DWORD(1024)
        buf = ctypes.create_unicode_buffer(1024)
        if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return buf.value
        return ""
    finally:
        k32.CloseHandle(h)


def _pid_of(hwnd) -> int:
    pid = wt.DWORD()
    u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wt.DWORD), ("cntUsage", wt.DWORD), ("th32ProcessID", wt.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)), ("th32ModuleID", wt.DWORD),
        ("cntThreads", wt.DWORD), ("th32ParentProcessID", wt.DWORD),
        ("pcPriClassBase", ctypes.c_long), ("dwFlags", wt.DWORD),
        ("szExeFile", wt.WCHAR * 260),
    ]


def list_processes(names=None):
    """枚举进程。names 为小写文件名集合，None 表示全部。返回 [(pid, exe, path)]。"""
    snap = k32.CreateToolhelp32Snapshot(0x00000002, 0)   # TH32CS_SNAPPROCESS
    if snap == -1:
        return []
    out = []
    try:
        e = PROCESSENTRY32W()
        e.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        ok = k32.Process32FirstW(snap, ctypes.byref(e))
        while ok:
            exe = e.szExeFile
            if names is None or exe.lower() in names:
                out.append((e.th32ProcessID, exe, _proc_path(e.th32ProcessID)))
            e = PROCESSENTRY32W()
            e.dwSize = ctypes.sizeof(PROCESSENTRY32W)
            ok = k32.Process32NextW(snap, ctypes.byref(e))
    finally:
        k32.CloseHandle(snap)
    return out


def wechat_processes():
    return list_processes({"weixin.exe", "wechat.exe"})


def helper_processes():
    return list_processes({"wechatappex.exe", "weixinappex.exe"})


def _title(hwnd) -> str:
    n = u32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(n + 1)
    u32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def enum_wechat_windows():
    """列出所有可见的微信顶层主窗口，带健康度。返回 [dict]。"""
    found = []

    def cb(hwnd, _):
        if not u32.IsWindowVisible(hwnd):
            return True
        if u32.GetWindow(hwnd, 4):        # GW_OWNER：有 owner 的不是主窗口
            return True
        path = _proc_path(_pid_of(hwnd))
        if os.path.basename(path).lower() not in WECHAT_EXES:
            return True
        r = wt.RECT()
        u32.GetWindowRect(hwnd, ctypes.byref(r))
        area = (r.right - r.left) * (r.bottom - r.top)
        if area <= 100_000:               # 排掉托盘/隐藏的小窗
            return True
        found.append({
            "hwnd": hwnd, "pid": _pid_of(hwnd), "path": path,
            "title": _title(hwnd), "area": area,
            "size": (r.right - r.left, r.bottom - r.top),
            "white": white_ratio(hwnd), "hung": is_hung(hwnd),
        })
        return True

    u32.EnumWindows(WNDENUMPROC(cb), 0)
    return found


def is_healthy(w, white_thresh=0.92) -> bool:
    if w["hung"]:
        return False
    if w["white"] < 0:        # 像素读不到（GPU 合成），不据此判死
        return True
    return w["white"] < white_thresh


def find_wechat_window():
    """
    返回 (hwnd, exe_path)；找不到返回 (None, '')。

    ⚠ 必须先按健康度排、再按面积排。白壳那个通常是最大化的，
    单纯「取最大窗口」会让采集器一头扎进已经死掉的渲染进程里。
    """
    wins = enum_wechat_windows()
    if not wins:
        return None, ""
    wins.sort(key=lambda w: (is_healthy(w), w["area"]), reverse=True)
    top = wins[0]
    return top["hwnd"], top["path"]


def is_hung(hwnd, timeout_ms: int = 1500) -> bool:
    """给窗口线程发个空消息，超时不回 = UI 线程卡死。"""
    res = ctypes.c_size_t()
    ok = u32.SendMessageTimeoutW(
        hwnd, 0x0000, 0, 0, 0x0002, timeout_ms, ctypes.byref(res)  # WM_NULL, SMTO_ABORTIFHUNG
    )
    return not bool(ok)


def white_ratio(hwnd) -> float:
    """客户区采样 49 点，返回纯白占比。返回 -1 表示读不到像素。"""
    r = wt.RECT()
    if not u32.GetClientRect(hwnd, ctypes.byref(r)):
        return -1.0
    w, h = r.right, r.bottom
    if w < 20 or h < 20:
        return -1.0
    hdc = u32.GetDC(hwnd)
    if not hdc:
        return -1.0
    try:
        white = total = 0
        for i in range(1, 8):
            for j in range(1, 8):
                c = gdi.GetPixel(hdc, w * i // 8, h * j // 8)
                if c == 0xFFFFFFFF:       # CLR_INVALID
                    continue
                total += 1
                b, g, rr = (c >> 16) & 0xFF, (c >> 8) & 0xFF, c & 0xFF
                if rr > 244 and g > 244 and b > 244:
                    white += 1
        return (white / total) if total else -1.0
    finally:
        u32.ReleaseDC(hwnd, hdc)


def kill_wechat():
    for exe in ("Weixin.exe", "WeChat.exe", "WeChatAppEx.exe"):
        subprocess.run(["taskkill", "/F", "/IM", exe],
                       capture_output=True, creationflags=0x08000000)


def launch_wechat(exe_path: str):
    """带 CEF 开关启动。CEF 从全局命令行读开关，宿主不认识的参数会被忽略。"""
    if not exe_path or not os.path.exists(exe_path):
        raise RuntimeError("不知道微信装在哪。先让微信跑起来跑一次 --selftest，"
                           "或用 --exe 指定 Weixin.exe 路径。")
    subprocess.Popen([exe_path] + CEF_SWITCHES,
                     creationflags=0x00000008)  # DETACHED_PROCESS


def doctor(verbose=True):
    """体检：进程、窗口、健康度、双开与干扰软件。返回诊断 dict。"""
    def say(s):
        if verbose:
            print(s)

    procs = wechat_processes()
    helpers = helper_processes()
    wins = enum_wechat_windows()
    interfere = list_processes({"qqpctray.exe", "qqpcrtp.exe", "qqpcmgr.exe"})

    say("=" * 68)
    say("微信进程 %d 个：" % len(procs))
    for pid, exe, path in procs:
        say("   pid=%-6d %s" % (pid, path or exe))
    for pid, exe, path in helpers:
        say("   pid=%-6d %s  (小程序/内置浏览器宿主)" % (pid, path or exe))

    say("")
    say("微信主窗口 %d 个：" % len(wins))
    for w in wins:
        say("   hwnd=0x%-10X pid=%-6d %dx%d 标题=%r" %
            (w["hwnd"], w["pid"], w["size"][0], w["size"][1], w["title"]))
        say("      白色占比 %s | UI线程 %s | 判定：%s" % (
            ("%.0f%%" % (w["white"] * 100)) if w["white"] >= 0 else "读不到(GPU合成)",
            "卡死" if w["hung"] else "正常",
            "✅ 健康" if is_healthy(w) else "❌ 白壳/已死"))

    # 双开判定：看不同的可执行文件路径，而不是看进程数（微信本来就多进程）
    paths = {p.lower() for _, _, p in procs if p}
    problems = []
    if len(paths) > 1:
        problems.append("装了两份微信并且都在跑：\n      " + "\n      ".join(sorted(paths)) +
                        "\n      两份抢同一个数据目录和单实例互斥量，足以把渲染进程搞崩。")
    elif len(procs) > 1 and len({p for _, _, p in procs}) == 1:
        problems.append("同一份微信起了 %d 个实例（多开）。" % len(procs))
    if len(wins) > 1:
        problems.append("有 %d 个微信主窗口。采集器必须挑健康的那个，不能挑最大的。" % len(wins))
    if any(not is_healthy(w) for w in wins):
        problems.append("存在白壳窗口 —— 渲染进程已死，关它会整个退出微信。")
    if interfere:
        problems.append("腾讯电脑管家在跑（%s）。它的内存清理与反注入会回收\n"
                        "      微信渲染进程，也会干扰 UIAutomation 跨进程访问。"
                        % ", ".join(sorted({e for _, e, _ in interfere})))

    say("")
    if problems:
        say("发现 %d 个问题：" % len(problems))
        for i, p in enumerate(problems, 1):
            say("   %d. %s" % (i, p))
    else:
        say("没发现问题，微信状态正常。")
    say("=" * 68)
    return {"procs": procs, "windows": wins, "problems": problems}


def rescue(exe_path=None, wait=90, verbose=True):
    """
    急救：白框出现时跑这个。全杀 -> 带 CEF 开关重开 -> 等到窗口不白为止。
    只留一个实例，避免两份微信互相打架。
    """
    def say(s):
        if verbose:
            print(s)

    d = doctor(verbose=verbose)

    if not exe_path:
        # 优先用健康窗口的路径；没有健康的就用任意一个微信进程的路径
        healthy = [w for w in d["windows"] if is_healthy(w)]
        cands = [w["path"] for w in healthy] or [w["path"] for w in d["windows"]]
        cands += [p for _, _, p in d["procs"] if p]
        exe_path = next((c for c in cands if c and os.path.exists(c)), None)

    if not exe_path:
        say("\n找不到 Weixin.exe 路径，用 --exe 指定。")
        return False

    say("\n>>> 全部结束微信进程……")
    kill_wechat()
    time.sleep(3)
    left = wechat_processes()
    if left:
        say("    还有残留：%s —— 可能需要管理员权限再跑一次。"
            % ", ".join("pid=%d" % p for p, _, _ in left))

    say(">>> 重新启动：%s %s" % (exe_path, " ".join(CEF_SWITCHES)))
    launch_wechat(exe_path)

    deadline = time.time() + wait
    while time.time() < deadline:
        time.sleep(2)
        wins = enum_wechat_windows()
        good = [w for w in wins if is_healthy(w)]
        if good:
            say("\n✅ 好了。健康窗口 hwnd=0x%X，白色占比 %s。" % (
                good[0]["hwnd"],
                ("%.0f%%" % (good[0]["white"] * 100)) if good[0]["white"] >= 0 else "读不到"))
            say("   a11y 已随 --force-renderer-accessibility 常开，现在可以跑 --selftest。")
            return True
        if wins:
            say("    等待中……（%d 个窗口，暂时都不健康——可能停在登录页）" % len(wins))

    say("\n❌ 等了 %ds 还是没有健康窗口。" % wait)
    say("   如果卡在登录页，手机确认一下再重跑；如果又是白的，看看是不是")
    say("   电脑管家把渲染进程回收了 —— 把微信加进它的白名单再试。")
    return False


# ----------------------------------------------------------------------------
# 快照：整棵子树一次跨进程调用取回
# ----------------------------------------------------------------------------

def _uia_snapshot(hwnd: int, max_depth: int) -> dict:
    """在子进程里执行。返回纯 dict 树，不含任何 COM 引用。"""
    import comtypes
    import comtypes.client

    comtypes.CoInitializeEx()
    comtypes.client.GetModule("UIAutomationCore.dll")
    from comtypes.gen import UIAutomationClient as UIA

    iuia = comtypes.client.CreateObject(UIA.CUIAutomation,
                                        interface=UIA.IUIAutomation)

    P = {
        "name": 30005, "auto_id": 30011, "ctrl": 30003,
        "cls": 30012, "rect": 30001, "offscreen": 30022,
    }

    cache = iuia.CreateCacheRequest()
    for pid in P.values():
        cache.AddProperty(pid)
    cache.TreeScope = 7                                  # TreeScope_Subtree
    cache.TreeFilter = iuia.CreateTrueCondition()        # 别漏掉 raw 节点
    # 关键：只要缓存值、不要活的 provider 引用。少掉每个节点一个跨进程对象。
    cache.AutomationElementMode = 0                      # AutomationElementMode_None

    root = iuia.ElementFromHandle(ctypes.c_void_p(hwnd))

    # ↓↓↓ 整棵子树，就这一次跨进程调用 ↓↓↓
    root = root.BuildUpdatedCache(cache)

    ctype_names = {v: k[5:-13] for k, v in vars(UIA).items()
                   if k.startswith("UIA_") and k.endswith("ControlTypeId")}

    def walk(el, depth):
        try:
            r = el.CachedBoundingRectangle
            rect = [int(r.left), int(r.top), int(r.right), int(r.bottom)]
        except Exception:
            rect = None
        node = {
            "name": el.CachedName or "",
            "auto_id": el.CachedAutomationId or "",
            "cls": el.CachedClassName or "",
            "type": ctype_names.get(el.CachedControlType, str(el.CachedControlType)),
            "rect": rect,
            "children": [],
        }
        if depth >= max_depth:
            node["truncated"] = True
            return node
        try:
            kids = el.GetCachedChildren()          # 纯本地读，无 RPC
        except Exception:
            kids = None
        if kids:
            for i in range(kids.Length):
                node["children"].append(walk(kids.GetElement(i), depth + 1))
        return node

    return walk(root, 0)


def snapshot(hwnd: int, timeout: float = 25.0, max_depth: int = 30):
    """
    在子进程里取快照。渲染进程若挂死，卡住的是子进程，超时即杀，父进程毫发无伤。
    返回树 dict；超时/失败返回 None。
    """
    cmd = [sys.executable, os.path.abspath(__file__),
           "--_snapshot", str(hwnd), "--depth", str(max_depth)]
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=timeout,
                           creationflags=0x08000000)
    except subprocess.TimeoutExpired:
        return None
    if p.returncode != 0:
        sys.stderr.write((p.stderr or b"").decode("utf-8", "replace") + "\n")
        return None
    try:
        return json.loads(p.stdout.decode("utf-8", "replace"))
    except Exception:
        return None


# ----------------------------------------------------------------------------
# 树的检索工具（纯本地，随便用，不会有任何跨进程代价）
# ----------------------------------------------------------------------------

def find(tree, *, name=None, name_contains=None, auto_id=None,
         type=None, cls=None, limit=None):
    """深度优先找节点。所有给出的条件取与。返回节点 list。"""
    hits = []

    def go(n):
        if limit and len(hits) >= limit:
            return
        ok = True
        if name is not None and n.get("name") != name:
            ok = False
        if name_contains is not None and name_contains not in n.get("name", ""):
            ok = False
        if auto_id is not None and n.get("auto_id") != auto_id:
            ok = False
        if type is not None and n.get("type") != type:
            ok = False
        if cls is not None and n.get("cls") != cls:
            ok = False
        if ok:
            hits.append(n)
        for c in n.get("children", ()):
            go(c)

    go(tree)
    return hits


def render(tree, indent=0, out=None):
    """把树打成人眼能读的缩进文本。"""
    out = [] if out is None else out
    bits = [tree.get("type", "?")]
    if tree.get("name"):
        bits.append("name=%r" % tree["name"][:60])
    if tree.get("auto_id"):
        bits.append("id=%s" % tree["auto_id"])
    if tree.get("cls"):
        bits.append("cls=%s" % tree["cls"])
    out.append("  " * indent + " ".join(bits))
    for c in tree.get("children", ()):
        render(c, indent + 1, out)
    return out


def count(tree):
    return 1 + sum(count(c) for c in tree.get("children", ()))


# ----------------------------------------------------------------------------
# 看门狗 + 采集驱动
# ----------------------------------------------------------------------------

class Watchdog(threading.Thread):
    """
    独立线程盯着微信主窗口。连续 N 次判定为白屏或卡死，就置 dead 事件。
    只用 Win32，不碰 COM，所以渲染进程挂了它照样活着。
    """

    def __init__(self, interval=2.0, strikes=3, white_thresh=0.92, on_event=None):
        super().__init__(daemon=True)
        self.interval, self.strikes, self.white_thresh = interval, strikes, white_thresh
        self.on_event = on_event or (lambda msg: None)
        self.dead = threading.Event()
        self.stopped = threading.Event()
        self._bad = 0

    def run(self):
        while not self.stopped.is_set():
            hwnd, _ = find_wechat_window()
            if hwnd is None:
                self._strike("微信主窗口不见了")
            else:
                wr = white_ratio(hwnd)
                if is_hung(hwnd):
                    self._strike("UI 线程无响应")
                elif wr >= self.white_thresh:
                    self._strike("窗口 %.0f%% 是纯白 —— 渲染进程死了" % (wr * 100))
                else:
                    if self._bad:
                        self.on_event("恢复正常")
                    self._bad = 0
            self.stopped.wait(self.interval)

    def _strike(self, why):
        self._bad += 1
        self.on_event("异常 %d/%d：%s" % (self._bad, self.strikes, why))
        if self._bad >= self.strikes:
            self.dead.set()

    def reset(self):
        self._bad = 0
        self.dead.clear()


class Harness:
    """
    采集驱动：负责活着，不负责知道微信长什么样。
    你的采集逻辑作为 collect(tree, harness) 回调传进来，只跟纯 dict 打交道。
    """

    def __init__(self, exe_path=None, verbose=True, snapshot_timeout=25.0):
        self.exe_path = exe_path
        self.verbose = verbose
        self.snapshot_timeout = snapshot_timeout
        self.state = self._load_checkpoint()

    # -- 断点 --------------------------------------------------------------
    def _load_checkpoint(self):
        try:
            with open(CHECKPOINT, encoding="utf-8") as f:
                s = json.load(f)
            self.log("载入断点：%s" % s)
            return s
        except Exception:
            return {}

    def save(self, **kw):
        """采集逻辑每采完一段就调一下，崩了能接着来。"""
        self.state.update(kw)
        tmp = CHECKPOINT + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)
        os.replace(tmp, CHECKPOINT)

    def log(self, msg):
        if self.verbose:
            print("[%s] %s" % (time.strftime("%H:%M:%S"), msg), flush=True)

    # -- 生命周期 ----------------------------------------------------------
    def ensure_wechat(self, wait=90):
        hwnd, path = find_wechat_window()
        if hwnd:
            if path and not self.exe_path:
                self.exe_path = path
            return hwnd
        self.log("微信没在跑，用 CEF 开关拉起来：%s" % " ".join(CEF_SWITCHES))
        launch_wechat(self.exe_path)
        deadline = time.time() + wait
        pressed = False
        while time.time() < deadline:
            time.sleep(2)
            hwnd, path = find_wechat_window()
            if hwnd:
                if white_ratio(hwnd) < 0.92 and not is_hung(hwnd):
                    self.log("微信已就绪。")
                    return hwnd
                if not pressed:
                    # 登录页多半只是等一下「进入微信」；回车尽力一试
                    u32.SetForegroundWindow(hwnd)
                    time.sleep(0.4)
                    u32.keybd_event(0x0D, 0, 0, 0)
                    u32.keybd_event(0x0D, 0, 2, 0)
                    pressed = True
                    self.log("已尝试自动确认登录（可能需要手机确认）。")
        raise RuntimeError("等了 %ds 微信还没进到可用状态。" % wait)

    def restart_wechat(self):
        self.log(">>> 重启微信中……")
        kill_wechat()
        time.sleep(3)
        return self.ensure_wechat()

    # -- 主循环 ------------------------------------------------------------
    def run(self, collect, max_restarts=8, settle=1.5):
        """
        collect(tree, harness) -> truthy 表示采完收工，falsy 表示还要再来一轮。
        期间无论白屏、卡死还是快照超时，都会重启微信并从断点续采。
        """
        wd = Watchdog(on_event=self.log)
        wd.start()
        restarts = 0
        try:
            hwnd = self.ensure_wechat()
            while True:
                if wd.dead.is_set():
                    if restarts >= max_restarts:
                        raise RuntimeError("重启 %d 次仍然白屏，不再重试。" % restarts)
                    restarts += 1
                    hwnd = self.restart_wechat()
                    wd.reset()
                    time.sleep(settle)
                    continue

                tree = snapshot(hwnd, timeout=self.snapshot_timeout)
                if tree is None:
                    self.log("快照超时/失败 —— 判定渲染进程已挂。")
                    wd.dead.set()
                    continue
                if count(tree) <= 2:
                    # 树是空的：a11y 没起来，或者渲染进程已经是白屏壳子
                    self.log("控件树是空的（%d 个节点）—— a11y 没起来。" % count(tree))
                    wd.dead.set()
                    continue

                if collect(tree, self):
                    self.log("采集完成。共重启 %d 次。" % restarts)
                    return
                time.sleep(settle)
        finally:
            wd.stopped.set()


# ----------------------------------------------------------------------------
# 命令行
# ----------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="微信 4.x 采集底座（抗白屏）")
    ap.add_argument("--rescue", action="store_true",
                    help="白框出现时的急救：全杀 + 带 CEF 开关重开 + 等到不白")
    ap.add_argument("--doctor", action="store_true",
                    help="体检：进程、窗口、双开、干扰软件（只看不动）")
    ap.add_argument("--selftest", action="store_true",
                    help="抓一次控件树，存 tree.json / tree.txt")
    ap.add_argument("--watch", action="store_true",
                    help="只跑看门狗，观察白屏发生规律")
    ap.add_argument("--exe", help="Weixin.exe 路径（微信没在跑时需要）")
    ap.add_argument("--depth", type=int, default=30, help="树的最大深度")
    ap.add_argument("--_snapshot", type=int, help=argparse.SUPPRESS)
    args = ap.parse_args()

    # 子进程模式：取快照、吐 JSON、退出
    if args._snapshot:
        sys.stdout.reconfigure(encoding="utf-8")
        json.dump(_uia_snapshot(args._snapshot, args.depth),
                  sys.stdout, ensure_ascii=False)
        return

    if args.doctor:
        doctor()
        return

    if args.rescue:
        sys.exit(0 if rescue(exe_path=args.exe) else 1)

    if args.watch:
        print("看门狗运行中，Ctrl-C 退出。现在去做你的采集动作，看白屏什么时候来。")
        wd = Watchdog(on_event=lambda m: print("[%s] %s" % (time.strftime("%H:%M:%S"), m)))
        wd.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            wd.stopped.set()
        return

    if args.selftest:
        h = Harness(exe_path=args.exe)
        hwnd = h.ensure_wechat()
        h.log("微信主窗口 hwnd=0x%X 标题=%r" % (hwnd, _title(hwnd)))
        h.log("白色占比 %.0f%%" % (white_ratio(hwnd) * 100))
        t0 = time.time()
        tree = snapshot(hwnd, timeout=60, max_depth=args.depth)
        if tree is None:
            print("\n快照失败。两种可能：")
            print("  1. a11y 没开 —— 微信不是用 --force-renderer-accessibility 启的。")
            print("     退出微信（托盘右键 退出），再跑一次本命令，让脚本自己拉起它。")
            print("  2. 渲染进程已经挂了 —— 窗口是不是白的？是就退出微信重开。")
            sys.exit(1)
        n = count(tree)
        h.log("取到 %d 个节点，耗时 %.1fs（整棵树只用了 1 次跨进程调用）" % (n, time.time() - t0))
        with open(os.path.join(HERE, "tree.json"), "w", encoding="utf-8") as f:
            json.dump(tree, f, ensure_ascii=False, indent=2)
        with open(os.path.join(HERE, "tree.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(render(tree)))
        print("\n已写出 tree.json 与 tree.txt。")
        print("拿 tree.txt 对照着把采集逻辑里的选择器改成 find(tree, ...) 的写法。")
        if n < 50:
            print("\n⚠ 只有 %d 个节点，太少了 —— a11y 多半没真正打开。" % n)
            print("  退出微信后重跑本命令，让脚本带 --force-renderer-accessibility 拉起它。")
        return

    ap.print_help()


if __name__ == "__main__":
    main()
