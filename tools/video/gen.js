// 彤鼎初创融资系列短视频：分镜渲染器
// 输出：build/v{N}/s{i}.png（2160×3840，供 ffmpeg 组装）；封面 out/v{N}-cover.png（1080×1920）
const { chromium } = require('playwright-core');
const fs = require('fs');
const path = require('path');

const ROOT = __dirname;

const VIDEOS = [
  {
    id: 'v1', ep: '01', slug: 'equity-split',
    title: '合伙人股权怎么分',
    scenes: [
      { type: 'hook', eyebrow: '初创融资 · 第 1 讲', h: '股权平均分，\n为什么是\n最危险的分法？', sub: '散伙的公司，多半死在股权上' },
      { type: 'point', no: '01', h: '平均分的问题\n不是不公平，是僵局', lines: ['两人各半、三人各三分之一', '重大事项没人能拍板', '投资人把它当作治理缺陷'] },
      { type: 'point', no: '02', h: '没有成熟机制，\n人走了股份带不走', lines: ['股份第一天就全给完', '合伙人中途离开，公司收不回来', '之后每一轮融资都要解释这件事'] },
      { type: 'point', no: '03', h: '写法其实很简单', lines: ['四年分批成熟', '首年为悬崖期：干满12个月才起算', '离职回购价格提前写进协议'] },
      { type: 'point', no: '04', h: '第三条红线：代持', lines: ['融资尽调第一轮就会被翻出来', '还原要工商变更＋税务处理', '公司越值钱，代价越高'] },
      { type: 'point', no: '05', h: '在公司值钱之前，\n把股权分好、写清', lines: ['那时候改，只是改一份协议', '拖到融资时改，要所有人点头'] },
      { type: 'tail' },
    ],
  },
  {
    id: 'v2', ep: '02', slug: 'first-financing',
    title: '第一次融资要多久',
    scenes: [
      { type: 'hook', eyebrow: '初创融资 · 第 2 讲', h: '第一次融资，\n从启动到钱进账\n要多久？', sub: '常见 4 – 8 个月，每一段都有卡点' },
      { type: 'point', no: '01', h: '材料准备\n2 – 4 周', lines: ['商业计划书＋财务模型', '股权结构表 cap table', '缺一件，尽调就多拖一段'] },
      { type: 'point', no: '02', h: '接触与路演\n4 – 8 周', lines: ['只见阶段和赛道匹配的机构', '海投三十家不匹配的', '是最常见的时间黑洞'] },
      { type: 'point', no: '03', h: '条款谈判\n2 – 4 周', lines: ['排他期一签，30–60天', '期间不能接触其他投资人', '签之前要想清楚'] },
      { type: 'point', no: '04', h: '尽职调查\n4 – 8 周', lines: ['代持、社保、知识产权都会被翻', '历史问题主动披露', '比被查出来主动得多'] },
      { type: 'point', no: '05', h: '交割 3 – 6 周，\n钱才真正到账', lines: ['条款清单本身不是钱', '协议签署＋工商变更＋打款', '走完才算融资完成'] },
      { type: 'tail' },
    ],
  },
  {
    id: 'v3', ep: '03', slug: 'financial-hygiene',
    title: '财务规范什么时候开始',
    scenes: [
      { type: 'hook', eyebrow: '初创融资 · 第 3 讲', h: '公司刚起步，\n要不要花钱\n做财务规范？', sub: '看你三年后想不想融资、上市' },
      { type: 'point', no: '01', h: '今天的账，\n三年后被逐笔翻', lines: ['境外上市要审最近2–3年报表', '规范的起点', '＝上市目标年份倒推三年'] },
      { type: 'point', no: '02', h: '最大的坑：\n公私账不分', lines: ['老板个人卡收货款', '公司账付家庭开支', '审计阶段几乎补不回来'] },
      { type: 'point', no: '03', h: '社保按最低缴，\n是问询高频事项', lines: ['历史欠缴要补，还可能有滞纳', '越拖数字越大'] },
      { type: 'point', no: '04', h: '无合同、现金收款', lines: ['合同、发票、回款要三流一致', '证明不了收入真实性', '这部分收入等于没有'] },
      { type: 'point', no: '05', h: '这笔账很好算', lines: ['早期代理记账：一年几千元', '后期财务清理：动辄数十万', '差的只是开始的时间'] },
      { type: 'tail' },
    ],
  },
  {
    id: 'v4', ep: '04', slug: 'angel-valuation',
    title: '天使轮估值怎么定',
    scenes: [
      { type: 'hook', eyebrow: '初创融资 · 第 4 讲', h: '公司还没利润，\n估值是怎么\n定出来的？', sub: '早期估值，多数是倒推出来的' },
      { type: 'point', no: '01', h: '最常用：按投资人\n目标持股倒推', lines: ['投资人通常要 15% – 20%', '融资额 ÷ 出让比例', '＝投后估值'] },
      { type: 'point', no: '02', h: '一个算例', lines: ['融 1,000 万、出让 20%', '投后估值 5,000 万', '投前 = 5,000 万 − 1,000 万 = 4,000 万'] },
      { type: 'point', no: '03', h: '投前投后一字之差，\n差的是稀释', lines: ['期权池设在投前还是投后', '直接决定创始人被稀释多少', '谈判时先问清这一条'] },
      { type: 'point', no: '04', h: '估值不是越高越好', lines: ['下一轮接不住这个估值', '反稀释条款会让你加倍稀释', '融资额和用途才是主线'] },
      { type: 'point', no: '05', h: '出让比例的常见区间', lines: ['天使轮 10% – 20%', '连续三轮后创始团队还剩多少', '签字之前先算完'] },
      { type: 'tail' },
    ],
  },
  {
    id: 'v5', ep: '05', slug: 'offshore-timing',
    title: '境外架构什么时候搭',
    scenes: [
      { type: 'hook', eyebrow: '初创融资 · 第 5 讲', h: '要接美元基金，\n境外架构\n什么时候搭？', sub: '在估值起来之前，把决定做掉' },
      { type: 'point', no: '01', h: '什么是红筹架构', lines: ['境外设控股主体', '控制境内运营公司', '为境外融资和上市留接口'] },
      { type: 'point', no: '02', h: '关键时点：\n37号文外汇登记', lines: ['境内居民设境外主体须登记', '公司越小、估值越低', '办理越简单'] },
      { type: 'point', no: '03', h: '晚搭的代价是税', lines: ['创始人境内股权换境外股权', '可能触发 20% 个人所得税', '估值越高，税基越大'] },
      { type: 'point', no: '04', h: '早搭也有成本', lines: ['开曼＋BVI＋香港年度维护', '一年约 5 – 15 万元', '方向错了还有重组成本'] },
      { type: 'point', no: '05', h: '判断标准就三条', lines: ['资金来源是不是美元', '目标上市地在不在境外', '行业是否涉及准入限制'] },
      { type: 'tail' },
    ],
  },
];

const FONT_CSS = ['400', '500', '700', '900']
  .map(w => `node_modules/@fontsource/noto-sans-sc/${w}.css`)
  .concat(['600', '900'].map(w => `node_modules/@fontsource/noto-serif-sc/${w}.css`))
  .map(f => `<link rel="stylesheet" href="../../${f}">`)
  .join('\n');

function baseCss() {
  return `
:root{--gold:#c9a962;--gold-hi:#e8cf96;--night:#0a0908;--line:rgba(201,169,98,.32);--body:#d9d0bb;--mute:#8f8468;}
*{margin:0;padding:0;box-sizing:border-box;}
html,body{width:1080px;height:1920px;overflow:hidden;}
body{background:
  radial-gradient(ellipse at 14% 12%,rgba(201,169,98,.14) 0,transparent 46%),
  radial-gradient(ellipse at 86% 88%,rgba(201,169,98,.09) 0,transparent 50%),
  var(--night);
  color:var(--body);font-family:"Noto Sans SC",sans-serif;position:relative;}
body::before{content:"";position:absolute;inset:0;background-image:
  linear-gradient(to right,rgba(201,169,98,.045) 1px,transparent 1px),
  linear-gradient(to bottom,rgba(201,169,98,.045) 1px,transparent 1px);
  background-size:135px 135px;}
.frame{position:absolute;inset:44px;border:1.5px solid rgba(201,169,98,.30);}
.frame::after{content:"";position:absolute;inset:10px;border:1px solid rgba(201,169,98,.12);}
.stage{position:absolute;inset:44px;padding:96px 92px;display:flex;flex-direction:column;}
.eyebrow{display:flex;align-items:center;gap:22px;color:var(--gold);font-family:Georgia,serif;font-style:italic;letter-spacing:8px;font-size:30px;}
.eyebrow::before{content:"";width:74px;height:2px;background:var(--gold);}
.eyebrow .en{letter-spacing:5px;color:var(--mute);font-size:26px;}
.brandbar{margin-top:auto;display:flex;align-items:center;justify-content:space-between;border-top:1px solid var(--line);padding-top:44px;}
.brandbar .nm{color:#d4c5a0;letter-spacing:10px;font-size:31px;font-weight:700;}
.brandbar .nm small{display:block;color:var(--gold);font-family:Georgia,serif;font-style:italic;letter-spacing:5px;font-size:21px;margin-top:10px;font-weight:400;}
.brandbar img{height:104px;opacity:.96;}
h1{font-family:"Noto Serif SC",serif;font-weight:900;color:#fff;font-size:96px;line-height:1.36;letter-spacing:4px;white-space:pre-line;}
h1 em{color:var(--gold-hi);font-style:normal;}
.sub{margin-top:64px;display:flex;align-items:center;gap:26px;color:var(--gold-hi);font-size:44px;letter-spacing:3px;}
.sub::before{content:"";width:16px;height:16px;background:var(--gold);transform:rotate(45deg);flex:none;}
.bigno{font-family:Georgia,serif;font-style:italic;color:rgba(201,169,98,.5);font-size:150px;line-height:1;}
h2{font-family:"Noto Serif SC",serif;font-weight:900;color:#fff;font-size:88px;line-height:1.4;letter-spacing:3px;margin-top:34px;white-space:pre-line;}
.lines{margin-top:78px;display:flex;flex-direction:column;gap:44px;}
.ln{display:flex;gap:30px;align-items:flex-start;color:var(--body);font-size:47px;line-height:1.6;letter-spacing:1.5px;font-weight:500;}
.ln::before{content:"";width:17px;height:17px;background:var(--gold);transform:rotate(45deg);flex:none;margin-top:26px;}
.tailwrap{position:absolute;inset:44px;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:0 90px;}
.tailwrap img{height:210px;margin-bottom:64px;}
.tailwrap .nm{color:#fff;font-size:66px;letter-spacing:22px;font-weight:700;font-family:"Noto Serif SC",serif;}
.tailwrap .en{color:var(--gold);font-family:Georgia,serif;font-style:italic;letter-spacing:9px;font-size:30px;margin-top:22px;}
.tailwrap .series{margin-top:90px;border:1.5px solid var(--gold);color:var(--gold-hi);padding:26px 66px;font-size:41px;letter-spacing:6px;}
.tailwrap .follow{margin-top:56px;color:var(--body);font-size:44px;letter-spacing:4px;}
.tailwrap .legal{position:absolute;bottom:64px;left:0;right:0;color:#6b6350;font-size:24px;letter-spacing:2px;}
.ep{position:absolute;top:104px;right:100px;font-family:Georgia,serif;font-style:italic;color:rgba(201,169,98,.45);font-size:56px;}
`;
}

function sceneHtml(v, s) {
  let inner = '';
  if (s.type === 'hook') {
    inner = `<div class="stage">
      <div class="eyebrow">${s.eyebrow}<span class="en">EARLY STAGE Nº${v.ep}</span></div>
      <div style="flex:1;display:flex;flex-direction:column;justify-content:center;margin-top:-60px;"><h1>${s.h}</h1><div class="sub">${s.sub}</div></div>
      <div class="brandbar"><div class="nm">彤鼎集團<small>TD GROUP · HONG KONG</small></div><img src="../../assets/td-crest-gold.png"></div>
    </div>`;
  } else if (s.type === 'point') {
    inner = `<div class="ep">${v.ep}</div><div class="stage">
      <div class="eyebrow">${v.title}<span class="en">EARLY STAGE</span></div>
      <div style="flex:1;display:flex;flex-direction:column;justify-content:center;margin-top:-40px;"><div class="bigno">${s.no}</div><h2>${s.h}</h2>
      <div class="lines">${s.lines.map(l => `<div class="ln">${l}</div>`).join('')}</div></div>
      <div class="brandbar"><div class="nm">彤鼎集團<small>TD GROUP · HONG KONG</small></div><img src="../../assets/td-crest-gold.png"></div>
    </div>`;
  } else {
    inner = `<div class="tailwrap">
      <img src="../../assets/td-crest-gold.png">
      <div class="nm">彤 鼎 集 團</div>
      <div class="en">TD GROUP (HONG KONG) LIMITED</div>
      <div class="series">初创融资系列 · 第 ${v.ep} 讲</div>
      <div class="follow">关注，看完整系列</div>
      <div class="legal">内容仅供学习参考，不构成任何法律、税务或投资建议</div>
    </div>`;
  }
  return `<!DOCTYPE html><html><head><meta charset="utf-8">${FONT_CSS}<style>${baseCss()}</style></head>
  <body><div class="frame"></div>${inner}</body></html>`;
}

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || '/opt/pw-browsers/chromium', args: ['--no-sandbox', '--force-color-profile=srgb'] });
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 2 });
  for (const v of VIDEOS) {
    const dir = path.join(ROOT, 'build', v.id);
    fs.mkdirSync(dir, { recursive: true });
    for (let i = 0; i < v.scenes.length; i++) {
      const f = path.join(dir, `s${i}.html`);
      fs.writeFileSync(f, sceneHtml(v, v.scenes[i]));
      await page.goto('file://' + f);
      await page.evaluate(() => document.fonts.ready);
      await page.waitForTimeout(120);
      await page.screenshot({ path: path.join(dir, `s${i}.png`) });
    }
    console.log(v.id, 'scenes rendered:', v.scenes.length);
  }
  await browser.close();
})();
