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

  function extractAllPairs() {
    const messages = collectMessageCandidates();
    if (messages.length < 2) {
      return [];
    }

    const pairs = [];
    const used = new Set();
    for (let i = 0; i < messages.length - 1; i += 1) {
      const question = messages[i];
      const answer = messages[i + 1];
      if (!question || !answer) continue;
      if (isQuestionText(question) && answer.length >= MIN_TEXT_LEN) {
        const key = `${question}|||${answer}`;
        if (!used.has(key)) {
          used.add(key);
          pairs.push({ question, answer });
        }
      }
    }

    if (pairs.length === 0) {
      pairs.push({
        question: messages[messages.length - 2],
        answer: messages[messages.length - 1],
      });
    }
    return pairs;
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

  async function uploadPairs(pairs, source = 'manual') {
    let uploaded = 0;
    try {
      for (const pair of pairs) {
        const payload = buildPayload(pair);
        const fp = fingerprintPayload(payload);
        if (fingerprintCache.has(fp) && source !== 'manual') continue;
        await sendToService(payload, source);
        fingerprintCache.add(fp);
        uploaded += 1;
      }
      if (source === 'manual') {
        showToast(`已上传 ${uploaded} 条问答`, uploaded > 0 ? 'ok' : 'info');
      }
    } catch (error) {
      console.error('[Grok Upload] failed:', error);
      if (source === 'manual') {
        showToast('上传失败，请检查后端服务', 'err');
      }
    }
  }

  async function uploadLatest(source = 'manual') {
    const pairs = extractAllPairs();
    if (!pairs.length) {
      showToast('未找到可上传的问答', 'err');
      return;
    }
    await uploadPairs([pairs[pairs.length - 1]], source);
  }

  function parseManualSelection(input, total) {
    const raw = (input || '').trim().toLowerCase();
    if (!raw || raw === 'latest') {
      return [total];
    }
    if (raw === 'all') {
      return Array.from({ length: total }, (_, i) => i + 1);
    }
    if (/^\d+$/.test(raw)) {
      const n = Math.max(1, Math.min(total, Number(raw)));
      // 最新 N 条（按时间顺序上传）
      return Array.from({ length: n }, (_, i) => total - n + 1 + i);
    }
    const indexList = raw
      .split(',')
      .map((x) => Number(x.trim()))
      .filter((x) => Number.isInteger(x) && x >= 1 && x <= total);
    return Array.from(new Set(indexList)).sort((a, b) => a - b);
  }

  async function handleManualUpload() {
    const pairs = extractAllPairs();
    const total = pairs.length;
    if (!total) {
      showToast('未识别到问答', 'err');
      return;
    }
    const userInput = window.prompt(
      `当前识别到 ${total} 组问答。\n` +
        '输入规则：\n' +
        '- 直接回车 / latest => 上传最新 1 组\n' +
        '- 数字N (如 3) => 上传最新 N 组\n' +
        '- 逗号序号 (如 1,3,5) => 上传指定序号\n' +
        '- all => 上传全部',
      'latest'
    );
    if (userInput === null) return;
    const indexes = parseManualSelection(userInput, total);
    if (!indexes.length) {
      showToast('输入无效，未上传', 'err');
      return;
    }
    const selectedPairs = indexes.map((idx) => pairs[idx - 1]);
    await uploadPairs(selectedPairs, 'manual');
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
      handleManualUpload();
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