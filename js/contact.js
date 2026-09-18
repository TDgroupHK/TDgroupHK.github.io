/* ============================================================
   TD GROUP 彤鼎 · 联系出口：埋点 + 复制微信号（2026-09-18 建）
   为什么要有这份文件：产品页与自测页此前的出口只有 mailto，而 mailto 在微信内置浏览器
   和没装邮件客户端的电脑上点了没有任何反应（也不报错）；加上全站没有一条联系类事件，
   「没人想联系」和「点了没反应」这两件事分不出来。这里只做两件事：
     ① 给「点邮件」和「复制微信」各发一个 GA4 事件 contact_click；
     ② 提供一个在任何浏览器里都真的能用的出口（复制微信号）。
   ⛔ 事件里只带一个 event_label = 动作|页面 slug，不带任何访客填写的内容或个人信息。
   ⛔ 纯静态、无外部依赖；本文件在每页 <head> 里以 defer 引入。
   ============================================================ */
(function () {
  var WX = 'esonleo';
  var DONE = '已复制，去微信里搜索添加';

  function slug() {
    var p = (location.pathname || '').split('/').pop() || 'index.html';
    return p.replace(/\.html?$/, '') || 'index';
  }

  function track(kind) {
    var label = kind + '|' + slug();
    try { if (typeof gtag === 'function') gtag('event', 'contact_click', { event_label: label }); } catch (e) {}
    try { if (window._hmt) window._hmt.push(['_trackEvent', '联系出口', kind, slug()]); } catch (e) {}
  }

  // 原地提示：沿用站内既有做法（copyResult 就是直接改按钮文字），过一会儿自己变回去
  function say(btn, text) {
    if (!btn.getAttribute('data-wx-label')) btn.setAttribute('data-wx-label', btn.textContent);
    btn.textContent = text;
    if (btn.wxTimer) clearTimeout(btn.wxTimer);
    btn.wxTimer = setTimeout(function () {
      btn.textContent = btn.getAttribute('data-wx-label');
    }, 8000);
  }

  function execCopy() {
    var ta = document.createElement('textarea');
    ta.value = WX;
    ta.setAttribute('readonly', '');
    ta.style.cssText = 'position:fixed;left:-9999px;top:0;opacity:0;';
    document.body.appendChild(ta);
    var ok = false;
    try {
      ta.select();
      ta.setSelectionRange(0, WX.length);
      ok = document.execCommand('copy');
    } catch (e) { ok = false; }
    document.body.removeChild(ta);
    return ok;
  }

  // 兜底：剪贴板 API 用不了（http、旧内核、权限被拒）时，把微信号显示出来并选中，让人自己复制
  function selectFallback(btn) {
    var span = btn.parentNode.querySelector('.wx-plain');
    if (!span) {
      span = document.createElement('span');
      span.className = 'wx-plain';
      span.textContent = WX;
      btn.parentNode.insertBefore(span, btn.nextSibling);
    }
    span.style.display = 'inline-block';
    try {
      var r = document.createRange();
      r.selectNodeContents(span);
      var sel = window.getSelection();
      sel.removeAllRanges();
      sel.addRange(r);
    } catch (e) {}
    say(btn, '已选中微信号，长按或 Ctrl+C 复制');
  }

  function copyWx(btn) {
    track('wechat_copy');
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(WX).then(
        function () { say(btn, DONE); },
        function () { if (execCopy()) say(btn, DONE); else selectFallback(btn); }
      );
      return;
    }
    if (execCopy()) say(btn, DONE); else selectFallback(btn);
  }

  document.addEventListener('click', function (ev) {
    var t = ev.target;
    if (!t || !t.closest) return;
    var wx = t.closest('[data-wx-copy]');
    if (wx) { ev.preventDefault(); copyWx(wx); return; }
    // 自测页的「发送结果」按钮是用 location.href 打开 mailto 的，不是 <a>，所以单独标一个属性
    if (t.closest('[data-mail-track]') || t.closest('a[href^="mailto:"]')) track('mailto');
  }, false);
})();
