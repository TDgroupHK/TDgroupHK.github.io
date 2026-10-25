# -*- coding: utf-8 -*-
"""
微信采集白框诊断器
==================

用法：
    python wechat_white_dialog_probe.py

跑起来后正常做你的采集动作。白框一弹出来，按 F8，脚本会把当前前台窗口的
全部身份信息 dump 到控制台和同目录的 白框诊断.log。按 Esc 退出。

判据（看 dump 里的「类名」和「子窗口类名链」）：

  1) 类名是 Chrome_WidgetWin_0 / Chrome_WidgetWin_1，
     或子窗口链里出现 Chrome_RenderWidgetHostHWND / Intermediate D3D Window
     => CEF（微信 4.x 内嵌浏览器）渲染进程挂了。走处方 A：
        关硬件加速 -> 取消「关闭主界面时退出微信」-> 清 xwechat 的 cache/GPUCache
        -> 修复 WebView2 -> 根治是采集期间退回微信 3.9.x

  2) 类名是 WeChatMainWndForPC
     => 还是 3.9 内核，白框不是 CEF 白屏，多半是安全验证窗或采集工具自己的遮罩。走处方 B。

  3) 「进程」不是 Weixin.exe / WeChat.exe / WeChatAppEx.exe
     => 白框是你采集工具（或它依赖的 RPA 库）自己弹的。走处方 B：
        去掉窗口置顶与 SetWindowPos 改尺寸，UIAutomation 遍历间隔 >= 200ms。

  另外重点看两行：
    「是否模态」= 是   -> 证实了「不关掉就采不了」（owner 被 disable，控件树取不到）
    「owner」   = 无   -> 白框就是顶层主窗口，证实了「关掉它整个微信退出」

无第三方依赖，纯 ctypes，Python 3.8+ / Windows。
"""

import ctypes
import ctypes.wintypes as wt
import os
import sys
import time
import datetime

if not sys.platform.startswith("win"):
    sys.exit("这个脚本只能在 Windows 上跑。")

u32 = ctypes.WinDLL("user32", use_last_error=True)
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
gdi = ctypes.WinDLL("gdi32", use_last_error=True)

# 高 DPI 下坐标才准
for setter in (
    lambda: ctypes.WinDLL("shcore").SetProcessDpiAwareness(2),
    lambda: u32.SetProcessDPIAware(),
):
    try:
        setter()
        break
    except Exception:
        continue

# 64 位下 HWND 是指针，必须显式声明 restype，否则会被截断成 int
u32.GetForegroundWindow.restype = wt.HWND
u32.GetWindow.argtypes = [wt.HWND, wt.UINT]
u32.GetWindow.restype = wt.HWND
u32.GetParent.argtypes = [wt.HWND]
u32.GetParent.restype = wt.HWND
u32.GetDC.argtypes = [wt.HWND]
u32.GetDC.restype = wt.HDC
u32.ReleaseDC.argtypes = [wt.HWND, wt.HDC]
gdi.GetPixel.argtypes = [wt.HDC, ctypes.c_int, ctypes.c_int]
gdi.GetPixel.restype = wt.DWORD

GW_OWNER = 4
WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "白框诊断.log")


def out(line=""):
    print(line)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def cls_of(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    u32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def title_of(hwnd):
    n = u32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(n + 1)
    u32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def pid_of(hwnd):
    pid = wt.DWORD()
    u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def proc_name(pid):
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return "<取不到，可能需要管理员权限>"
    try:
        size = wt.DWORD(1024)
        buf = ctypes.create_unicode_buffer(1024)
        if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return buf.value
        return "<查询失败>"
    finally:
        k32.CloseHandle(h)


def rect_of(hwnd):
    r = wt.RECT()
    u32.GetWindowRect(hwnd, ctypes.byref(r))
    return r


def whiteness(hwnd):
    """在窗口客户区采样 25 个点，判断是不是真的一片纯白。"""
    r = wt.RECT()
    if not u32.GetClientRect(hwnd, ctypes.byref(r)):
        return "<取不到客户区>"
    w, h = r.right, r.bottom
    if w < 10 or h < 10:
        return "<窗口太小，跳过采样>"
    hdc = u32.GetDC(hwnd)
    if not hdc:
        return "<拿不到 DC>"
    try:
        white = total = 0
        samples = []
        for i in range(1, 6):
            for j in range(1, 6):
                x, y = w * i // 6, h * j // 6
                c = gdi.GetPixel(hdc, x, y)
                if c == 0xFFFFFFFF:  # CLR_INVALID
                    continue
                b, g, r_ = (c >> 16) & 0xFF, (c >> 8) & 0xFF, c & 0xFF
                total += 1
                if r_ > 245 and g > 245 and b > 245:
                    white += 1
                if len(samples) < 5:
                    samples.append("#%02X%02X%02X" % (r_, g, b))
        if total == 0:
            return "<GPU 合成窗口，GetPixel 读不到；这本身就是 CEF 的旁证>"
        return "%d/%d 个采样点是纯白（样本 %s）" % (white, total, " ".join(samples))
    finally:
        u32.ReleaseDC(hwnd, hdc)


def child_chain(hwnd, limit=12):
    found = []

    def cb(h, _):
        if len(found) >= limit:
            return False
        found.append("%s%s" % (cls_of(h), (" | " + title_of(h)) if title_of(h) else ""))
        return True

    u32.EnumChildWindows(hwnd, WNDENUMPROC(cb), 0)
    return found


def siblings_of_process(pid, limit=20):
    found = []

    def cb(h, _):
        if len(found) >= limit:
            return False
        if pid_of(h) == pid and u32.IsWindowVisible(h):
            r = rect_of(h)
            found.append(
                "hwnd=0x%X cls=%-28s enabled=%s %dx%d 标题=%r"
                % (
                    h,
                    cls_of(h),
                    "是" if u32.IsWindowEnabled(h) else "否",
                    r.right - r.left,
                    r.bottom - r.top,
                    title_of(h),
                )
            )
        return True

    u32.EnumWindows(WNDENUMPROC(cb), 0)
    return found


def dump():
    hwnd = u32.GetForegroundWindow()
    if not hwnd:
        out("拿不到前台窗口，跳过。")
        return

    pid = pid_of(hwnd)
    owner = u32.GetWindow(hwnd, GW_OWNER)
    r = rect_of(hwnd)

    out("=" * 72)
    out("时间          : " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    out("hwnd          : 0x%X" % hwnd)
    out("类名          : %s        <<< 主要判据看这里" % cls_of(hwnd))
    out("标题          : %r" % title_of(hwnd))
    out("进程          : %s (pid=%d)" % (proc_name(pid), pid))
    out("位置尺寸      : (%d,%d) %dx%d" % (r.left, r.top, r.right - r.left, r.bottom - r.top))
    out("像素纯白度    : %s" % whiteness(hwnd))
    out("窗口自身可用  : %s" % ("是" if u32.IsWindowEnabled(hwnd) else "否"))

    if owner:
        owner_enabled = bool(u32.IsWindowEnabled(owner))
        out("owner         : hwnd=0x%X cls=%s 标题=%r" % (owner, cls_of(owner), title_of(owner)))
        out("是否模态      : %s   （owner 被 disable 即为模态，会挡住 UIAutomation）"
            % ("是" if not owner_enabled else "否"))
    else:
        out("owner         : 无   >>> 这是顶层主窗口，关掉它会带走整个进程")
        out("是否模态      : 不适用")

    out("父窗口        : %s" % ("0x%X" % u32.GetParent(hwnd) if u32.GetParent(hwnd) else "无"))

    out("-- 子窗口类名链（最多 12 条）--")
    chain = child_chain(hwnd)
    if not chain:
        out("   （无子窗口。CEF 窗口通常也是这样——内容全在渲染进程里，这不排除 CEF）")
    for c in chain:
        out("   " + c)

    out("-- 同进程的其它可见顶层窗口 --")
    for s in siblings_of_process(pid):
        out("   " + s)
    out("=" * 72)
    out("")


def main():
    out("")
    out("### 白框诊断器已启动 —— 白框弹出时按 F8 抓取，按 Esc 退出。日志：%s" % LOG)
    VK_F8, VK_ESCAPE = 0x77, 0x1B
    f8_was_down = False
    while True:
        f8_down = bool(u32.GetAsyncKeyState(VK_F8) & 0x8000)
        if f8_down and not f8_was_down:
            dump()
        f8_was_down = f8_down
        if u32.GetAsyncKeyState(VK_ESCAPE) & 0x8000:
            out("### 已退出。把 白框诊断.log 连同脚本头部的判据一起看。")
            return
        time.sleep(0.05)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        out("### 已中断。")
