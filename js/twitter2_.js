// ==UserScript==
// @name         Grok.com Q&A -> PostgreSQL
// @namespace    http://tampermonkey.net/
// @version      2026-04-26
// @description  Capture grok.com user/assistant messages and send to local ingest service.
// @author       xi
// @match        https://grok.com/*
// @icon         https://www.google.com/s2/favicons?sz=64&domain=grok.com
// @grant        GM_xmlhttpRequest
// @connect      localhost
// @connect      127.0.0.1
// ==/UserScript==

(function () {
  'use strict';

  const API_URL = 'http://127.0.0.1:8000/api/grok/messages';
  const AUTO_UPLOAD_DEBOUNCE_MS = 1500;
  const fingerprintCache = new Set();
  let autoUploadTimer = null;

  function normalizeText(raw) {
    return (raw || '').replace(/\s+\n/g, '\n').replace(/\n{3,}/g, '\n\n').trim();
  }

  function nowIso() {
    return new Date().toISOString();
  }

  function conversationIdFromUrl() {
    const m = window.location.pathname.match(/\/chat\/([^/?#]+)/);
    return m ? m[1] : '';
  }

  function extractDialoguePairs() {
    const root = document.querySelector('[data-testid="drop-ui"]') || document.body;
    const userNodes = Array.from(root.querySelectorAll('[data-testid="user-message"]'));
    const assistantNodes = Array.from(root.querySelectorAll('[data-testid="assistant-message"]'));

    const users = userNodes.map((n) => normalizeText(n.innerText)).filter(Boolean);
    const assistants = assistantNodes.map((n) => normalizeText(n.innerText)).filter(Boolean);
    const pairCount = Math.min(users.length, assistants.length);
    if (!pairCount) return [];

    const pairs = [];
    const seen = new Set();
    for (let i = 0; i < pairCount; i += 1) {
      const question = users[i];
      const answer = assistants[i];
      if (!question || !answer) continue;
      const k = `${question}|||${answer}`;
      if (seen.has(k)) continue;
      seen.add(k);
      pairs.push({ question, answer });
    }
    return pairs;
  }

  function buildPayload(pair) {
    return {
      platform: 'grok_web',
      conversation_id: conversationIdFromUrl(),
      page_url: window.location.href,
      question: pair.question,
      answer: pair.answer,
      captured_at: nowIso(),
      user_agent: navigator.userAgent,
    };
  }

  function fingerprintPayload(payload) {
    return `${payload.platform}|${payload.conversation_id}|${payload.question}|${payload.answer}`.slice(0, 1200);
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
    const colorMap = { info: '#2563eb', ok: '#16a34a', err: '#dc2626' };
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
        if (source !== 'manual' && fingerprintCache.has(fp)) continue;
        await sendToService(payload, source);
        fingerprintCache.add(fp);
        uploaded += 1;
      }
      if (source === 'manual') {
        showToast(`已上传 ${uploaded} 条问答`, uploaded > 0 ? 'ok' : 'info');
      }
    } catch (err) {
      console.error('[grok.com upload] failed:', err);
      if (source === 'manual') {
        showToast('上传失败，请检查后端服务', 'err');
      }
    }
  }

  async function handleManualUpload() {
    const pairs = extractDialoguePairs();
    if (!pairs.length) {
      showToast('未识别到问答', 'err');
      return;
    }
    const total = pairs.length;
    const userInput = window.prompt(
      `当前识别到 ${total} 组问答。\n` +
        '输入规则：\n' +
        '- 直接回车 / latest => 上传最新 1 组\n' +
        '- 数字N (如 3) => 上传最新 N 组\n' +
        '- all => 上传全部',
      'latest'
    );
    if (userInput === null) return;
    const raw = (userInput || '').trim().toLowerCase();
    let selected = [];
    if (!raw || raw === 'latest') {
      selected = [pairs[pairs.length - 1]];
    } else if (raw === 'all') {
      selected = pairs;
    } else if (/^\d+$/.test(raw)) {
      const n = Math.max(1, Math.min(total, Number(raw)));
      selected = pairs.slice(total - n);
    } else {
      showToast('输入无效，未上传', 'err');
      return;
    }
    await uploadPairs(selected, 'manual');
  }

  function observeConversation() {
    const target = document.querySelector('[data-testid="drop-ui"]') || document.body;
    const observer = new MutationObserver(() => {
      if (autoUploadTimer) clearTimeout(autoUploadTimer);
      autoUploadTimer = setTimeout(async () => {
        const pairs = extractDialoguePairs();
        if (pairs.length) {
          await uploadPairs([pairs[pairs.length - 1]], 'auto');
        }
      }, AUTO_UPLOAD_DEBOUNCE_MS);
    });
    observer.observe(target, { childList: true, subtree: true });
  }

  function mountUploadButton() {
    if (document.getElementById('tm-grokcom-upload-btn')) return;
    const btn = document.createElement('button');
    btn.id = 'tm-grokcom-upload-btn';
    btn.type = 'button';
    btn.textContent = '上传问答(grok.com)';
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
    btn.addEventListener('click', handleManualUpload);
    document.body.appendChild(btn);
  }

  function boot() {
    mountUploadButton();
    observeConversation();
  }

  boot();
})();