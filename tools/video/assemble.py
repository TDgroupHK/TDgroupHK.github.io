# -*- coding: utf-8 -*-
"""把 build/v*/s*.png 组装成 1080×1920 30fps 短视频（Ken Burns 缓推 + 交叉溶解）。"""
import os
import glob
import subprocess
import sys

try:
    import imageio_ffmpeg
    FF = imageio_ffmpeg.get_ffmpeg_exe()
except ImportError:
    FF = 'ffmpeg'
ROOT = os.path.dirname(os.path.abspath(__file__))
FPS = 30
XFADE = 0.5
# 场景时长：hook 3.8s / 要点 4.4s / 尾板 3.6s
def dur(i, n):
    if i == 0:
        return 3.8
    if i == n - 1:
        return 3.6
    return 4.4

def build(vdir, out):
    stills = sorted(glob.glob(os.path.join(vdir, 's*.png')),
                    key=lambda p: int(os.path.basename(p)[1:-4]))
    n = len(stills)
    durs = [dur(i, n) for i in range(n)]
    inputs, chains = [], []
    for i, (p, d) in enumerate(zip(stills, durs)):
        inputs += ['-i', p]
        frames = int(d * FPS)
        # 偶数镜头缓推近，奇数镜头缓拉远，画面不死
        if i % 2 == 0:
            z = f"1+0.09*on/{frames}"
        else:
            z = f"1.09-0.09*on/{frames}"
        chains.append(
            f"[{i}:v]scale=2160:3840,zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d={frames}:s=1080x1920:fps={FPS},setsar=1[v{i}]")
    # xfade 链
    offsets, acc = [], 0.0
    for i in range(n - 1):
        acc += durs[i] - XFADE
        offsets.append(acc)
    cur = 'v0'
    for i in range(1, n):
        nxt = f"x{i}"
        chains.append(f"[{cur}][v{i}]xfade=transition=fade:duration={XFADE}:offset={offsets[i-1]:.2f}[{nxt}]")
        cur = nxt
    fc = ';'.join(chains)
    cmd = [FF, '-y', *inputs, '-filter_complex', fc, '-map', f'[{cur}]',
           '-c:v', 'libx264', '-preset', 'medium', '-crf', '19',
           '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-1500:])
        sys.exit(1)
    total = sum(durs) - XFADE * (n - 1)
    print(os.path.basename(out), f'≈{total:.1f}s', f'{os.path.getsize(out)//1024}KB')

def cover(vdir, out):
    src = os.path.join(vdir, 's0.png')
    r = subprocess.run([FF, '-y', '-i', src, '-vf', 'scale=1080:1920', out],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-500:]); sys.exit(1)

NAMES = {
    'v1': '01-合伙人股权怎么分',
    'v2': '02-第一次融资要多久',
    'v3': '03-财务规范什么时候开始',
    'v4': '04-天使轮估值怎么定',
    'v5': '05-境外架构什么时候搭',
}
os.makedirs(os.path.join(ROOT, 'out'), exist_ok=True)
for vid, name in NAMES.items():
    vdir = os.path.join(ROOT, 'build', vid)
    if not os.path.isdir(vdir):
        continue
    build(vdir, os.path.join(ROOT, 'out', f'{name}.mp4'))
    cover(vdir, os.path.join(ROOT, 'out', f'{name}-封面.png'))
print('全部完成')
