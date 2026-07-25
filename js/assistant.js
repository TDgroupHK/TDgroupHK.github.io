/* 彤鼎智能助手 —— 检索式站内问答组件
   纯原生 JS，零外部依赖。知识库来自本站 FAQ 与文库文章，仅返回站内已审核文本，不生成内容。 */
(function () {
  'use strict';
  if (window.__tdAssistant) return;
  window.__tdAssistant = 1;

  var WECHAT = 'esonleo';
  var EMAIL = 'liaoqijie@tdgroup.hk';
  var KB_URL = 'js/assistant-kb.json';

  // 文章页在 /articles/ 下，需回退一级才能取到 js/ 与同级页面
  var BASE = /\/articles\//.test(location.pathname) ? '../' : '';

  var QUICK = [
    '赴美上市有哪几条路径？',
    '要花多少钱、多长时间？',
    '纳斯达克门槛是多少？',
    '达不到门槛怎么办？',
    '美股还是港股？',
    '俱乐部是什么？'
  ];

  /* ---------------- 样式 ---------------- */
  var css = '' +
    '.tda-btn{position:fixed;right:22px;bottom:22px;z-index:99998;width:56px;height:56px;border-radius:50%;' +
    'background:#0a0908;border:1px solid rgba(201,169,98,.55);color:#c9a962;cursor:pointer;' +
    'box-shadow:0 6px 24px rgba(0,0,0,.32);display:flex;align-items:center;justify-content:center;' +
    'transition:transform .18s ease,box-shadow .18s ease;font-family:"Microsoft YaHei","微软雅黑",sans-serif}' +
    '.tda-btn:hover{transform:translateY(-2px);box-shadow:0 10px 30px rgba(0,0,0,.42)}' +
    '.tda-btn svg{width:24px;height:24px}' +
    '.tda-btn .tda-dot{position:absolute;top:2px;right:2px;width:9px;height:9px;border-radius:50%;background:#c9a962;border:2px solid #0a0908}' +
    '.tda-wrap{position:fixed;right:22px;bottom:88px;z-index:99999;width:372px;max-width:calc(100vw - 32px);' +
    'height:540px;max-height:calc(100vh - 120px);background:#fdfcf9;border:1px solid rgba(10,9,8,.14);' +
    'border-radius:6px;box-shadow:0 18px 56px rgba(0,0,0,.26);display:none;flex-direction:column;overflow:hidden;' +
    'font-family:"Microsoft YaHei","微软雅黑",sans-serif}' +
    '.tda-wrap.on{display:flex}' +
    '.tda-hd{background:#0a0908;color:#f4f1ea;padding:14px 16px;display:flex;align-items:center;gap:10px;flex:0 0 auto}' +
    '.tda-hd b{font-size:14.5px;font-weight:600;letter-spacing:.3px}' +
    '.tda-hd small{display:block;font-size:11px;color:rgba(244,241,234,.55);margin-top:2px;letter-spacing:.2px}' +
    '.tda-hd .tda-x{margin-left:auto;background:none;border:0;color:rgba(244,241,234,.6);font-size:22px;line-height:1;cursor:pointer;padding:0 2px}' +
    '.tda-hd .tda-x:hover{color:#c9a962}' +
    '.tda-body{flex:1 1 auto;overflow-y:auto;padding:14px 16px;background:#fdfcf9}' +
    '.tda-msg{margin-bottom:14px;font-size:13.5px;line-height:1.78;color:#26231f;word-break:break-word}' +
    '.tda-msg.u{text-align:right}' +
    '.tda-msg.u span{display:inline-block;background:#0a0908;color:#f4f1ea;padding:8px 12px;border-radius:4px;max-width:82%;text-align:left}' +
    '.tda-msg.a span{display:block;background:#fff;border:1px solid rgba(10,9,8,.1);border-left:2px solid #c9a962;padding:11px 13px;border-radius:3px}' +
    '.tda-msg.a b{color:#0a0908}' +
    '.tda-rel{margin-top:9px;padding-top:9px;border-top:1px dashed rgba(10,9,8,.14)}' +
    '.tda-rel i{display:block;font-style:normal;font-size:11px;color:#8a8377;letter-spacing:.4px;margin-bottom:5px}' +
    '.tda-rel a{display:block;font-size:12.5px;color:#0a0908;text-decoration:none;padding:3px 0;line-height:1.5}' +
    '.tda-rel a:hover{color:#c9a962}' +
    '.tda-chips{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:12px}' +
    '.tda-chip{background:#fff;border:1px solid rgba(10,9,8,.16);color:#3a352e;font-size:12px;padding:6px 10px;' +
    'border-radius:14px;cursor:pointer;font-family:inherit;transition:.15s;line-height:1.4}' +
    '.tda-chip:hover{border-color:#c9a962;color:#0a0908;background:#fffdf8}' +
    '.tda-cta{background:#0a0908;border-radius:4px;padding:12px 14px;margin-top:4px}' +
    '.tda-cta p{margin:0 0 8px;font-size:12.5px;color:rgba(244,241,234,.8);line-height:1.65}' +
    '.tda-cta a,.tda-cta button{display:inline-block;font-size:12.5px;color:#c9a962;text-decoration:none;border:1px solid rgba(201,169,98,.45);' +
    'background:none;padding:6px 11px;border-radius:3px;margin:0 6px 0 0;cursor:pointer;font-family:inherit}' +
    '.tda-cta a:hover,.tda-cta button:hover{background:rgba(201,169,98,.12)}' +
    '.tda-ft{flex:0 0 auto;border-top:1px solid rgba(10,9,8,.1);background:#fff;padding:10px 12px}' +
    '.tda-in{display:flex;gap:8px}' +
    '.tda-in input{flex:1;border:1px solid rgba(10,9,8,.18);border-radius:3px;padding:9px 11px;font-size:13px;' +
    'font-family:inherit;color:#26231f;outline:none;min-width:0}' +
    '.tda-in input:focus{border-color:#c9a962}' +
    '.tda-in button{background:#0a0908;color:#c9a962;border:0;border-radius:3px;padding:0 15px;font-size:13px;cursor:pointer;font-family:inherit;white-space:nowrap}' +
    '.tda-in button:hover{background:#1a1815}' +
    '.tda-dis{font-size:10.5px;color:#9a9488;line-height:1.55;margin-top:8px;letter-spacing:.1px}' +
    '@media(max-width:520px){.tda-wrap{right:12px;left:12px;width:auto;bottom:80px;height:calc(100vh - 108px)}.tda-btn{right:14px;bottom:14px}}';

  var st = document.createElement('style');
  st.textContent = css;
  document.head.appendChild(st);

  /* ---------------- DOM ---------------- */
  var btn = document.createElement('button');
  btn.className = 'tda-btn';
  btn.setAttribute('aria-label', '打开彤鼎智能助手');
  btn.innerHTML = '<span class="tda-dot"></span><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>';

  var wrap = document.createElement('div');
  wrap.className = 'tda-wrap';
  wrap.setAttribute('role', 'dialog');
  wrap.setAttribute('aria-label', '彤鼎智能助手');
  wrap.innerHTML =
    '<div class="tda-hd"><div><b>彤鼎智能助手</b><small>境外上市 · 跨境资本运作</small></div>' +
    '<button class="tda-x" aria-label="关闭">&times;</button></div>' +
    '<div class="tda-body"></div>' +
    '<div class="tda-ft"><div class="tda-in">' +
    '<input type="text" placeholder="输入你的问题，例如：上市要多少钱" aria-label="输入问题">' +
    '<button type="button">发送</button></div>' +
    '<div class="tda-dis">答案取自本站已发布内容，仅供参考，不构成法律、税务或投资建议，亦不构成任何收益承诺。</div></div>';

  document.body.appendChild(btn);
  document.body.appendChild(wrap);

  var body = wrap.querySelector('.tda-body');
  var input = wrap.querySelector('input');
  var send = wrap.querySelector('.tda-in button');

  /* ---------------- 埋点（复用站内已装的 GA4 / 百度统计） ---------------- */
  function track(action, label) {
    try { if (window.gtag) window.gtag('event', action, { event_category: 'assistant', event_label: label }); } catch (e) {}
    try { if (window._hmt) window._hmt.push(['_trackEvent', 'assistant', action, label]); } catch (e) {}
  }

  /* ---------------- 知识库 ---------------- */
  var KB = null, loading = false;
  function loadKB(cb) {
    if (KB) return cb(KB);
    if (loading) return setTimeout(function () { loadKB(cb); }, 120);
    loading = true;
    var x = new XMLHttpRequest();
    x.open('GET', BASE + KB_URL, true);
    x.onreadystatechange = function () {
      if (x.readyState !== 4) return;
      loading = false;
      if (x.status >= 200 && x.status < 300) {
        try { KB = JSON.parse(x.responseText); } catch (e) { KB = { qas: [], arts: [] }; }
      } else { KB = { qas: [], arts: [] }; }
      cb(KB);
    };
    x.send();
  }

  /* ---------------- 中文匹配：字符二元组重合度 ---------------- */
  function norm(s) {
    return (s || '').toLowerCase().replace(/[\s，。、？！；：""''（）()【】《》~·\-—_.,?!;:"']/g, '');
  }
  function grams(s) {
    s = norm(s);
    var g = {}, i;
    for (i = 0; i < s.length; i++) { g[s[i]] = (g[s[i]] || 0) + 0.4; }
    for (i = 0; i < s.length - 1; i++) { var k = s.substr(i, 2); g[k] = (g[k] || 0) + 1; }
    return g;
  }
  function score(qg, text, w) {
    var tg = grams(text), s = 0, k;
    for (k in qg) { if (tg[k]) s += Math.min(qg[k], tg[k]); }
    return s * w;
  }

  // 意图关键词 → 直答，优先于检索
  var INTENT = [
    { k: ['微信', '联系方式', '怎么联系', '联系你们', '电话', '客服', '找谁', '咨询一下', '加你'], t: 'contact' },
    { k: ['会费', '入会费', '多少钱入会', '会员费', '怎么入会', '加入俱乐部', '入会条件'], t: 'clubfee' },
    { k: ['你是谁', '你是机器人', '真人', 'ai', '智能助手'], t: 'whoami' }
  ];
  function intentOf(q) {
    var n = norm(q), i, j;
    for (i = 0; i < INTENT.length; i++) {
      for (j = 0; j < INTENT[i].k.length; j++) { if (n.indexOf(norm(INTENT[i].k[j])) > -1) return INTENT[i].t; }
    }
    return null;
  }

  function search(q) {
    var qg = grams(q), out = [], i;
    for (i = 0; i < KB.qas.length; i++) {
      out.push({ kind: 'qa', s: score(qg, KB.qas[i].q, 3) + score(qg, KB.qas[i].a, 0.7), d: KB.qas[i] });
    }
    var arts = [];
    for (i = 0; i < KB.arts.length; i++) {
      arts.push({ s: score(qg, KB.arts[i].t, 3) + score(qg, KB.arts[i].d, 0.8), d: KB.arts[i] });
    }
    out.sort(function (a, b) { return b.s - a.s; });
    arts.sort(function (a, b) { return b.s - a.s; });
    return { best: out[0], arts: arts.slice(0, 3).filter(function (a) { return a.s > 2.2; }) };
  }

  /* ---------------- 渲染 ---------------- */
  function esc(s) { return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
  function scroll() { body.scrollTop = body.scrollHeight; }

  function addUser(t) {
    var d = document.createElement('div');
    d.className = 'tda-msg u';
    d.innerHTML = '<span>' + esc(t) + '</span>';
    body.appendChild(d); scroll();
  }
  function addBot(htmlStr) {
    var d = document.createElement('div');
    d.className = 'tda-msg a';
    d.innerHTML = '<span>' + htmlStr + '</span>';
    body.appendChild(d); scroll();
    return d;
  }
  function relHTML(arts) {
    if (!arts || !arts.length) return '';
    var h = '<div class="tda-rel"><i>延伸阅读</i>';
    for (var i = 0; i < arts.length; i++) {
      h += '<a href="' + BASE + arts[i].d.u + '">' + esc(arts[i].d.t) + ' →</a>';
    }
    return h + '</div>';
  }
  function ctaHTML(msg) {
    return '<div class="tda-cta"><p>' + msg + '</p>' +
      '<a href="mailto:' + EMAIL + '?subject=' + encodeURIComponent('官网咨询') + '" data-cta="email">发邮件咨询</a>' +
      '<button type="button" data-cta="wechat">复制微信号</button></div>';
  }

  function answer(q) {
    var it = intentOf(q);
    if (it === 'contact') {
      track('intent', 'contact');
      addBot('<b>联系方式</b><br>邮箱 ' + EMAIL + '，微信 ' + WECHAT + '。<br>' +
        '如需就具体项目沟通，建议邮件说明企业所在行业、近两年营收与净利润区间、以及计划上市的地区，会更快得到有针对性的回复。' +
        ctaHTML('工作日通常一个工作日内回复。'));
      return;
    }
    if (it === 'clubfee') {
      track('intent', 'clubfee');
      addBot('<b>华尔街彤鼎俱乐部</b><br>俱乐部面向有资本市场规划的企业家，提供闭门分享与案例拆解、企业家同行网络、专业资源对接。' +
        '会员权益与费用以一对一沟通为准，不在公开页面列示，可邮件了解详情。<br>' +
        '涉及投资类权益的部分，仅面向符合条件的合格投资者，并会充分揭示风险，不构成任何投资建议或收益承诺。' +
        ctaHTML('想了解会员详情，请邮件说明企业情况。'));
      return;
    }
    if (it === 'whoami') {
      track('intent', 'whoami');
      addBot('我是本站的检索式助手，答案直接取自彤鼎官网已发布的问答与文库文章，不会自行编写内容，因此不会出现凭空生成的数字。' +
        '需要就具体项目做判断时，请直接联系团队。' + ctaHTML('复杂问题建议直接沟通。'));
      return;
    }

    var r = search(q);
    if (r.best && r.best.s > 3.2) {
      track('hit', q.slice(0, 40));
      addBot('<b>' + esc(r.best.d.q) + '</b><br>' + esc(r.best.d.a) + relHTML(r.arts) +
        ctaHTML('需要针对你企业的具体判断？'));
    } else if (r.arts.length) {
      track('partial', q.slice(0, 40));
      addBot('这个问题在站内问答里没有直接对应的条目，以下文库文章可能相关：' + relHTML(r.arts) +
        ctaHTML('没找到想要的？直接问团队更快。'));
    } else {
      track('miss', q.slice(0, 40));
      addBot('这个问题超出了站内已发布内容的范围，我不便凭推测回答。<br>' +
        '你可以换个说法再试（例如「纳斯达克门槛」「上市费用」「VIE架构」「37号文」），或者直接联系团队。' +
        ctaHTML('直接说明企业情况，会得到更准确的答复。'));
    }
  }

  /* ---------------- 交互 ---------------- */
  var greeted = false;
  function greet() {
    if (greeted) return;
    greeted = true;
    var h = '你好。我可以基于本站已发布的问答与 136 篇文库文章回答关于境外上市与跨境资本运作的问题。<br>可以先看这几个常见问题：';
    addBot(h);
    var c = document.createElement('div');
    c.className = 'tda-chips';
    for (var i = 0; i < QUICK.length; i++) {
      var b = document.createElement('button');
      b.className = 'tda-chip'; b.type = 'button'; b.textContent = QUICK[i];
      c.appendChild(b);
    }
    body.appendChild(c); scroll();
  }

  function ask(q) {
    q = (q || '').trim();
    if (!q) return;
    addUser(q);
    input.value = '';
    loadKB(function () { setTimeout(function () { answer(q); }, 180); });
  }

  function open() {
    wrap.classList.add('on');
    btn.setAttribute('aria-expanded', 'true');
    track('open', location.pathname);
    loadKB(function () { greet(); });
    if (window.innerWidth > 520) setTimeout(function () { input.focus(); }, 60);
  }
  function close() { wrap.classList.remove('on'); btn.setAttribute('aria-expanded', 'false'); }

  btn.addEventListener('click', function () { wrap.classList.contains('on') ? close() : open(); });
  wrap.querySelector('.tda-x').addEventListener('click', close);
  send.addEventListener('click', function () { ask(input.value); });
  input.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); ask(input.value); } });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && wrap.classList.contains('on')) close(); });

  body.addEventListener('click', function (e) {
    var t = e.target;
    if (t.classList && t.classList.contains('tda-chip')) { ask(t.textContent); return; }
    var cta = t.getAttribute && t.getAttribute('data-cta');
    if (cta === 'email') { track('cta_email', location.pathname); return; }
    if (cta === 'wechat') {
      e.preventDefault();
      track('cta_wechat', location.pathname);
      var ok = false;
      try {
        if (navigator.clipboard && navigator.clipboard.writeText) { navigator.clipboard.writeText(WECHAT); ok = true; }
        else {
          var ta = document.createElement('textarea');
          ta.value = WECHAT; ta.style.position = 'fixed'; ta.style.opacity = '0';
          document.body.appendChild(ta); ta.select();
          ok = document.execCommand('copy');
          document.body.removeChild(ta);
        }
      } catch (err) { ok = false; }
      t.textContent = ok ? '已复制：' + WECHAT : '微信号：' + WECHAT;
      setTimeout(function () { t.textContent = '复制微信号'; }, 2600);
    }
  });
})();
