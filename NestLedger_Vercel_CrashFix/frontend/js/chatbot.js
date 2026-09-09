/* NestLedger AI Chatbot module.
 * Powered by backend Gemini route (/api/ai/chat) with server-side context & role security.
 * Depends on globals: state, go(page), api(path), toast(msg), i18n.
 */
(function (global) {
  let isPanelOpen = false;
  let isThinking = false;
  const conversationHistory = []; // { role: 'user' | 'model', parts: [{ text }] }

  function escapeHtml(str) {
    return String(str ?? '')
      .replace(/[&<>'"]/g, (c) => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        "'": '&#39;',
        '"': '&quot;',
      }[c]));
  }

  // Format assistant markdown response safely (bolding, lists, linebreaks)
  function formatAssistantText(text) {
    if (!text) return '';
    const lines = String(text).split('\n');
    let html = '';
    let inList = false;

    for (let line of lines) {
      const trimmed = line.trim();
      if (trimmed.startsWith('* ') || trimmed.startsWith('- ')) {
        if (!inList) {
          html += '<ul>';
          inList = true;
        }
        const itemContent = escapeHtml(trimmed.slice(2)).replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        html += `<li>${itemContent}</li>`;
      } else {
        if (inList) {
          html += '</ul>';
          inList = false;
        }
        if (trimmed) {
          const formatted = escapeHtml(trimmed).replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
          html += `<p>${formatted}</p>`;
        }
      }
    }
    if (inList) html += '</ul>';
    return html || `<p>${escapeHtml(text)}</p>`;
  }

  function getRoleSuggestions() {
    const role = (typeof state !== 'undefined' && state.user && state.user.role)
      ? state.user.role
      : 'resident';
    const hasI18n = window.i18n && typeof window.i18n.t === 'function';

    if (role === 'vendor') {
      return [
        { label: hasI18n ? window.i18n.t('openRequests') : 'Open jobs', query: 'Show me open work orders on the board' },
        { label: hasI18n ? window.i18n.t('activeJobs') : 'My jobs', query: 'What are my current active work orders?' },
        { label: hasI18n ? window.i18n.t('notices') : 'Notices', query: 'What notices are available?' },
        { label: 'How to accept', query: 'How do I accept a job and mark it complete?' },
      ];
    }

    if (role === 'admin') {
      return [
        { label: hasI18n ? window.i18n.t('financialOverview') : 'Finances', query: 'Give me a summary of society finances' },
        { label: hasI18n ? window.i18n.t('complaints') : 'Complaints', query: 'How many complaints need attention?' },
        { label: hasI18n ? window.i18n.t('notices') : 'Notices', query: 'Show society notices' },
        { label: hasI18n ? window.i18n.t('vendorPerformance') : 'Vendors', query: 'How is vendor performance?' },
      ];
    }

    // Resident (default)
    return [
      {
        label: hasI18n ? window.i18n.t('chatbotSuggestDues') : 'My dues',
        query: hasI18n ? window.i18n.t('chatbotSuggestDues') : 'How much maintenance do I owe?',
      },
      {
        label: hasI18n ? window.i18n.t('chatbotSuggestComplaints') : 'My complaints',
        query: hasI18n ? window.i18n.t('chatbotSuggestComplaints') : 'Show my complaints and their status',
      },
      {
        label: hasI18n ? window.i18n.t('chatbotSuggestNotices') : 'Notices',
        query: hasI18n ? window.i18n.t('chatbotSuggestNotices') : 'What notices are available?',
      },
      {
        label: hasI18n ? window.i18n.t('chatbotSuggestPay') : 'Payments',
        query: hasI18n ? window.i18n.t('chatbotSuggestPay') : 'Take me to payments',
      },
    ];
  }

  function renderChips() {
    const chipsWrap = document.getElementById('chatbotChips');
    if (!chipsWrap) return;
    const suggestions = getRoleSuggestions();
    chipsWrap.innerHTML = suggestions
      .map((s, idx) => `<button type="button" class="chatbot-chip" data-idx="${idx}">${escapeHtml(s.label)}</button>`)
      .join('');

    chipsWrap.querySelectorAll('.chatbot-chip').forEach((btn) => {
      btn.onclick = () => {
        const idx = Number(btn.dataset.idx);
        const item = suggestions[idx];
        if (item) {
          sendMessage(item.query);
        }
      };
    });
  }

  function mountChatbot() {
    if (document.getElementById('chatbotFab')) return;

    const hasI18n = window.i18n && typeof window.i18n.t === 'function';
    const fabLabel = hasI18n ? window.i18n.t('chatbotTitle') : 'AI Assistant';

    // 1. Floating Action Button
    const fab = document.createElement('button');
    fab.id = 'chatbotFab';
    fab.className = 'chatbot-fab';
    fab.type = 'button';
    fab.setAttribute('aria-label', 'Open AI Chatbot');
    fab.innerHTML = `<span class="chatbot-fab-icon"><i data-lucide="sparkles"></i></span><span class="chatbot-fab-label">${escapeHtml(fabLabel)}</span>`;
    fab.onclick = toggleChatbot;
    document.body.appendChild(fab);

    // 2. Chat Panel Container
    const panel = document.createElement('div');
    panel.id = 'chatbotPanel';
    panel.className = 'chatbot-panel';
    panel.innerHTML = `
      <div class="chatbot-header">
        <div class="chatbot-header-info">
          <div class="chatbot-avatar">✨</div>
          <div>
            <h4 class="chatbot-title" id="chatbotHeaderTitle">${escapeHtml(hasI18n ? window.i18n.t('chatbotTitle') : 'Community Assistant')}</h4>
            <p class="chatbot-sub" id="chatbotHeaderSub">${escapeHtml(hasI18n ? window.i18n.t('chatbotSubtitle') : 'Ask anything about dues, complaints, notices')}</p>
          </div>
        </div>
        <div class="chatbot-header-actions">
          <button type="button" class="chatbot-icon-btn" id="chatbotClearBtn" title="${escapeHtml(hasI18n ? window.i18n.t('chatbotClear') : 'Clear chat')}"><i data-lucide="trash-2"></i></button>
          <button type="button" class="chatbot-icon-btn" id="chatbotCloseBtn" title="${escapeHtml(hasI18n ? window.i18n.t('chatbotClose') : 'Close chat')}"><i data-lucide="x"></i></button>
        </div>
      </div>
      <div class="chatbot-chips" id="chatbotChips"></div>
      <div class="chatbot-body" id="chatbotBody"></div>
      <form class="chatbot-footer" id="chatbotForm">
        <div class="chatbot-input-wrap">
          <input type="text" class="chatbot-input" id="chatbotInput" placeholder="${escapeHtml(hasI18n ? window.i18n.t('chatbotPlaceholder') : 'Ask a question or type a command...')}" autocomplete="off" />
        </div>
        <button type="button" class="voice-mic chatbot-voice-mic" id="chatbotVoiceMic" aria-label="${escapeHtml(hasI18n ? window.i18n.t('voiceTapToSpeak') : 'Speak')}" title="${escapeHtml(hasI18n ? window.i18n.t('voiceTapToSpeak') : 'Speak')}">
          <span class="voice-mic-icon"><i data-lucide="mic"></i></span>
        </button>
        <button type="submit" class="chatbot-send" id="chatbotSendBtn">${escapeHtml(hasI18n ? window.i18n.t('chatbotSend') : 'Send')}</button>
      </form>
    `;
    document.body.appendChild(panel);
    if (global.lucide && typeof global.lucide.createIcons === 'function') global.lucide.createIcons({attrs:{'stroke-width':1.8}});

    // Event listeners
    document.getElementById('chatbotCloseBtn').onclick = closeChatbot;
    document.getElementById('chatbotClearBtn').onclick = clearChat;
    document.getElementById('chatbotForm').onsubmit = (e) => {
      e.preventDefault();
      const input = document.getElementById('chatbotInput');
      const val = input.value.trim();
      if (val && !isThinking) {
        input.value = '';
        sendMessage(val);
      }
    };

    renderChips();
    initGreeting();
    if (global.NLVoice && typeof global.NLVoice.mountInlineMic === 'function') global.NLVoice.mountInlineMic(document.getElementById('chatbotForm'));
  }

  function initGreeting() {
    const body = document.getElementById('chatbotBody');
    if (!body || body.children.length > 0) return;
    const hasI18n = window.i18n && typeof window.i18n.t === 'function';
    const greeting = hasI18n
      ? window.i18n.t('chatbotGreeting')
      : 'Hello! I am your NestLedger AI Assistant. How can I help you today?';
    appendMessage('assistant', greeting);
  }

  function appendMessage(role, text, action = null) {
    const body = document.getElementById('chatbotBody');
    if (!body) return;

    const msgEl = document.createElement('div');
    msgEl.className = `chatbot-msg ${role}`;

    if (role === 'user') {
      msgEl.textContent = text;
    } else {
      let contentHtml = formatAssistantText(text);
      const actionTarget = (action && typeof action === 'object') ? action.target : (action !== 'none' ? action : null);
      if (actionTarget) {
        const hasI18n = window.i18n && typeof window.i18n.t === 'function';
        const pageLabel = hasI18n ? window.i18n.t(actionTarget) : actionTarget;
        const openLabel = hasI18n ? window.i18n.t('chatbotActionNavigate') : 'Open';
        const btnLabel = (action && typeof action === 'object' && action.label) ? action.label : `↗ ${openLabel} ${pageLabel}`;
        contentHtml += `
          <div>
            <button type="button" class="chat-action-btn" data-action="${escapeHtml(actionTarget)}">
              ${escapeHtml(btnLabel)}
            </button>
          </div>
        `;
      }
      msgEl.innerHTML = contentHtml;

      const actionBtn = msgEl.querySelector('.chat-action-btn');
      if (actionBtn) {
        actionBtn.onclick = () => {
          const act = actionBtn.dataset.action;
          if (typeof go === 'function') {
            go(act);
          }
        };
      }
    }

    body.appendChild(msgEl);
    body.scrollTop = body.scrollHeight;
  }

  function showTyping() {
    removeTyping();
    const body = document.getElementById('chatbotBody');
    if (!body) return;
    const typing = document.createElement('div');
    typing.id = 'chatbotTyping';
    typing.className = 'chatbot-typing';
    typing.innerHTML = '<span></span><span></span><span></span>';
    body.appendChild(typing);
    body.scrollTop = body.scrollHeight;
  }

  function removeTyping() {
    const t = document.getElementById('chatbotTyping');
    if (t) t.remove();
  }

  async function sendMessage(messageText) {
    const text = String(messageText || '').trim();
    if (!text || isThinking) return;

    appendMessage('user', text);
    conversationHistory.push({
      role: 'user',
      parts: [{ text }],
    });

    isThinking = true;
    showTyping();
    const sendBtn = document.getElementById('chatbotSendBtn');
    if (sendBtn) sendBtn.disabled = true;

    const lang = window.i18n ? window.i18n.getLanguage() : 'en';

    try {
      const data = await api('/ai/chat', {
        method: 'POST',
        body: JSON.stringify({
          message: text,
          lang,
          history: conversationHistory.slice(-8), // Keep recent conversational context
        }),
      });

      removeTyping();
      const reply = data.reply || (window.i18n ? window.i18n.t('chatbotError') : 'Sorry, could not process request.');
      const action = data.action && data.action !== 'none' ? data.action : null;

      appendMessage('assistant', reply, action);
      conversationHistory.push({
        role: 'model',
        parts: [{ text: reply }],
      });

      // If action is specified and user explicitly wanted navigation, we can also execute or keep button
      const actionTarget = action && typeof action === 'object' ? action.target : action;
      if (actionTarget && ['payments', 'complaints', 'notices', 'workorders', 'dashboard', 'receipts', 'residents', 'vendors', 'expenses', 'vendorperformance'].includes(actionTarget)) {
        // Auto-navigate if prompt directly asked to "take me to" or "open"
        const lower = text.toLowerCase();
        if (lower.includes('take me') || lower.includes('go to') || lower.includes('open') || lower.includes('show me')) {
          if (typeof go === 'function') {
            go(actionTarget);
          }
        }
      }
    } catch (err) {
      removeTyping();
      const hasI18n = window.i18n && typeof window.i18n.t === 'function';
      const errMsg = hasI18n ? window.i18n.t('chatbotError') : 'Connection issue. Please try again.';
      appendMessage('assistant', errMsg);
    } finally {
      isThinking = false;
      if (sendBtn) sendBtn.disabled = false;
      const input = document.getElementById('chatbotInput');
      if (input) input.focus();
    }
  }

  function openChatbot() {
    isPanelOpen = true;
    const panel = document.getElementById('chatbotPanel');
    if (panel) {
      panel.classList.add('open');
      const body = document.getElementById('chatbotBody');
      if (body) body.scrollTop = body.scrollHeight;
      const input = document.getElementById('chatbotInput');
      if (input) input.focus();
    }
  }

  function closeChatbot() {
    isPanelOpen = false;
    const panel = document.getElementById('chatbotPanel');
    if (panel) panel.classList.remove('open');
  }

  function toggleChatbot() {
    if (isPanelOpen) {
      closeChatbot();
    } else {
      openChatbot();
    }
  }

  function clearChat() {
    conversationHistory.length = 0;
    const body = document.getElementById('chatbotBody');
    if (body) body.innerHTML = '';
    initGreeting();
    renderChips();
  }

  function refreshLabel() {
    const hasI18n = window.i18n && typeof window.i18n.t === 'function';
    if (!hasI18n) return;

    const fabLabel = document.querySelector('.chatbot-fab-label');
    if (fabLabel) fabLabel.textContent = window.i18n.t('chatbotTitle');

    const title = document.getElementById('chatbotHeaderTitle');
    if (title) title.textContent = window.i18n.t('chatbotTitle');

    const sub = document.getElementById('chatbotHeaderSub');
    if (sub) sub.textContent = window.i18n.t('chatbotSubtitle');

    const input = document.getElementById('chatbotInput');
    if (input) input.placeholder = window.i18n.t('chatbotPlaceholder');

    const sendBtn = document.getElementById('chatbotSendBtn');
    if (sendBtn) sendBtn.textContent = window.i18n.t('chatbotSend');

    renderChips();
  }

  global.NLChatbot = {
    mount: mountChatbot,
    open: openChatbot,
    close: closeChatbot,
    toggle: toggleChatbot,
    clearChat,
    refreshLabel,
    sendMessage,
  };
})(window);
