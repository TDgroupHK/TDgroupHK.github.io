# 初创融资系列短视频生产线

把品牌风格的分镜数据渲染成 1080×1920 竖屏知识短视频（黑金视觉与官网一致），
供抖音 / 快手 / 小红书 / 视频号 / 微博发布。首批 5 条（初创融资 第 1–5 讲）于 2026-08-08 产出。

## 用法

```bash
cd tools/video
npm i @fontsource/noto-sans-sc @fontsource/noto-serif-sc playwright-core   # 中文字体 + 无头浏览器驱动
pip install imageio-ffmpeg                                                  # 带 libx264 的 ffmpeg
cp ../../img/td-crest-gold.png assets/                                      # 品牌徽标
node gen.js          # 渲染分镜 → build/v*/s*.png（2160×3840）
python3 assemble.py  # 组装 → out/*.mp4（约26秒/条，缓推镜头+交叉溶解）+ 封面 png
```

- Chromium 路径默认 `/opt/pw-browsers/chromium`（Claude 远程环境自带），本机运行设 `CHROMIUM_PATH` 环境变量。
- 出新视频只需在 `gen.js` 的 `VIDEOS` 数组里加一组分镜（hook / point×5 / tail），文字守则同 CLAUDE.md：
  禁用词表、无股票代码、无客户名、量化一切；尾板固定带「不构成投资建议」免责。
- 视频为无声版：发布时在平台 App 内选曲库 BGM（有版权、有流量加成），不要外配音乐。
- 分平台文案规则见 CLAUDE.md 第四节第 7 条：抖音/快手/小红书/视频号零链接零引流；仅微博可带官网链接。
