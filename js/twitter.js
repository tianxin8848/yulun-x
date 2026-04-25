// ==UserScript==
// @name         Grok Q&A -> PostgreSQL
// @namespace    http://tampermonkey.net/
// @version      2026-04-26
// @description  Capture Grok latest Q&A and send to backend service for PostgreSQL storage.
// @author       xi
// @match        https://x.com/i/grok*
// @icon         https://www.google.com/s2/favicons?sz=64&domain=x.com
// @grant        GM_xmlhttpRequest
// @connect      localhost
// @connect      127.0.0.1
// ==/UserScript==

(function () {
  'use strict';

  const API_URL = 'http://127.0.0.1:8000/api/grok/messages';
  const MIN_TEXT_LEN = 15;
  const AUTO_UPLOAD_DEBOUNCE_MS = 1500;
  const fingerprintCache = new Set();
  let autoUploadTimer = null;

  function nowIso() {
    return new Date().toISOString();
  }

  function normalizeText(raw) {
    return (raw || '').replace(/\s+\n/g, '\n').replace(/\n{3,}/g, '\n\n').trim();
  }

  function isProbablyNoise(text) {
    if (!text || text.length < MIN_TEXT_LEN) return true;
    const noise = ['查看新帖子', '专注模式', '复制分享链接', '书签', '聊天历史记录', '新聊天', '想法'];
    return noise.includes(text.trim());
  }

  function collectMessageCandidates() {
    const root = document.querySelector('div[data-testid="primaryColumn"]') || document.body;
    const nodes = Array.from(root.querySelectorAll('div[dir="ltr"]'));
    const results = [];

    nodes.forEach((node) => {
      const text = normalizeText(node.innerText);
      if (isProbablyNoise(text)) return;
      if (text.length > 20000) return;
      if (node.querySelector('button, nav, svg') && text.length < 80) return;
      results.push(text);
    });

    const deduped = [];
    const seen = new Set();
    for (const item of results) {
      const key = item.replace(/\s+/g, ' ').trim();
      if (seen.has(key)) continue;
      seen.add(key);
      deduped.push(item);
    }
    return deduped;
  }

  function isQuestionText(text) {
    return /[?？]$/.test(text.trim()) || text.includes('怎么') || text.includes('如何');
  }

  function extractLatestPair() {
    const messages = collectMessageCandidates();
    if (messages.length < 2) {
      return null;
    }

    // 从后往前找最后一个“像问题”的文本，再取它后面的第一条作为回答
    for (let i = messages.length - 2; i >= 0; i -= 1) {
      const question = messages[i];
      const answer = messages[i + 1];
      if (!question || !answer) continue;
      if (isQuestionText(question) && answer.length >= MIN_TEXT_LEN) {
        return { question, answer };
      }
    }

    // 回退策略：直接用最后两条
    return {
      question: messages[messages.length - 2],
      answer: messages[messages.length - 1],
    };
  }

  function buildPayload(pair) {
    const url = new URL(window.location.href);
    return {
      platform: 'x_grok',
      conversation_id: url.searchParams.get('conversation') || '',
      page_url: window.location.href,
      question: pair.question,
      answer: pair.answer,
      captured_at: nowIso(),
      user_agent: navigator.userAgent,
    };
  }

  function fingerprintPayload(payload) {
    return `${payload.conversation_id}|${payload.question}|${payload.answer}`.slice(0, 1000);
  }

  function sendToService(payload, source = 'manual') {
    const body = JSON.stringify({ ...payload, source });
    return new Promise((resolve, reject) => {
      GM_xmlhttpRequest({
        method: 'POST',
        url: API_URL,
        headers: { 'Content-Type': 'application/json' },
        data: body,
        onload: (res) => {
          if (res.status >= 200 && res.status < 300) {
            resolve(res.responseText || '');
          } else {
            reject(new Error(`HTTP ${res.status}: ${res.responseText || ''}`));
          }
        },
        onerror: (err) => reject(err),
      });
    });
  }

  function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    const colorMap = {
      info: '#1d9bf0',
      ok: '#16a34a',
      err: '#dc2626',
    };
    toast.textContent = message;
    toast.style.cssText = [
      'position:fixed',
      'right:24px',
      'bottom:92px',
      'z-index:999999',
      'padding:8px 12px',
      'border-radius:8px',
      'font-size:13px',
      'color:#fff',
      `background:${colorMap[type] || colorMap.info}`,
      'box-shadow:0 6px 18px rgba(0,0,0,0.25)',
    ].join(';');
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 2200);
  }

  async function uploadLatest(source = 'manual') {
    const pair = extractLatestPair();
    if (!pair) {
      showToast('未找到可上传的问答', 'err');
      return;
    }

    const payload = buildPayload(pair);
    const fp = fingerprintPayload(payload);
    if (fingerprintCache.has(fp) && source !== 'manual') {
      return;
    }

    try {
      await sendToService(payload, source);
      fingerprintCache.add(fp);
      if (source === 'manual') {
        showToast('最新问答已上传', 'ok');
      }
    } catch (error) {
      console.error('[Grok Upload] failed:', error);
      if (source === 'manual') {
        showToast('上传失败，请检查后端服务', 'err');
      }
    }
  }

  function observeConversation() {
    const target = document.querySelector('main') || document.body;
    const observer = new MutationObserver(() => {
      if (autoUploadTimer) clearTimeout(autoUploadTimer);
      autoUploadTimer = setTimeout(() => uploadLatest('auto'), AUTO_UPLOAD_DEBOUNCE_MS);
    });
    observer.observe(target, { childList: true, subtree: true });
  }

  function mountUploadButton() {
    if (document.getElementById('tm-grok-upload-btn')) return;
    const btn = document.createElement('button');
    btn.id = 'tm-grok-upload-btn';
    btn.type = 'button';
    btn.textContent = '上传最新问答';
    btn.style.cssText = [
      'position:fixed',
      'right:24px',
      'bottom:24px',
      'z-index:999999',
      'padding:10px 14px',
      'background:#111827',
      'color:#fff',
      'border:none',
      'border-radius:999px',
      'cursor:pointer',
      'font-size:13px',
      'font-weight:600',
      'box-shadow:0 8px 24px rgba(0,0,0,0.3)',
    ].join(';');
    btn.addEventListener('click', () => {
      uploadLatest('manual');
    });
    document.body.appendChild(btn);
  }

  function boot() {
    mountUploadButton();
    observeConversation();
    // 首次进入页面时尝试自动抓一次
    setTimeout(() => uploadLatest('auto'), 2000);
  }

  boot();
})();