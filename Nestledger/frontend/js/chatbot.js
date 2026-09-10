/* NestLedger AI chatbot — AK
 * Gemini-backed conversational assistant with a deterministic action layer.
 * The action layer only calls existing, allowlisted NestLedger functions and
 * requires confirmation before payments/destructive/state-changing actions.
 */
(function (global) {
  let isPanelOpen = false;
  let isThinking = false;
  const conversationHistory = [];
  const NAV_ALIASES = {
    home:'dashboard', dashboard:'dashboard', overview:'dashboard',
    payment:'payments', payments:'payments', bills:'payments', dues:'payments',
    complaint:'complaints', complaints:'complaints', issues:'complaints',
    notice:'notices', notices:'notices', announcements:'notices',
    workorder:'workorders', workorders:'workorders', requests:'workorders', maintenance:'workorders', jobs:'workorders',
    receipt:'receipts', receipts:'receipts',
    profile:'profile', account:'profile',
    resident:'residents', residents:'residents',
    vendor:'vendors', vendors:'vendors',
    expense:'expenses', expenses:'expenses',
    performance:'vendorperformance', vendorperformance:'vendorperformance', vendorsperformance:'vendorperformance',
    reports:'reports', 'business intelligence':'reports', intelligence:'reports'
  };
  const ALLOWED_NAV = new Set(['dashboard','payments','complaints','notices','workorders','receipts','profile','residents','vendors','expenses','vendorperformance','reports']);
  const HEROICON_CPU = `<svg class="ak-heroicon" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M8.25 3v1.5M4.5 8.25H3m18 0h-1.5M4.5 12H3m18 0h-1.5m-15 3.75H3m18 0h-1.5M8.25 19.5V21M12 3v1.5m0 15V21m3.75-18v1.5m0 15V21m-9-1.5h10.5a2.25 2.25 0 0 0 2.25-2.25V6.75a2.25 2.25 0 0 0-2.25-2.25H6.75A2.25 2.25 0 0 0 4.5 6.75v10.5a2.25 2.25 0 0 0 2.25 2.25m.75-12h9v9h-9z"/></svg>`;

  function escapeHtml(str) {
    return String(str ?? '').replace(/[&<>'"]/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  }
  function role() { return (global.state && global.state.user && global.state.user.role) || 'resident'; }
  function hasI18n() { return global.i18n && typeof global.i18n.t === 'function'; }
  function currentLang() { return global.i18n && typeof global.i18n.getLanguage === 'function' ? global.i18n.getLanguage() : 'en'; }
  function confirmAction(message) { return typeof global.confirm === 'function' ? global.confirm(message) : true; }

  function formatAssistantText(text) {
    if (!text) return '';
    const lines = String(text).split('\n');
    let html = '', inList = false;
    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed.startsWith('* ') || trimmed.startsWith('- ')) {
        if (!inList) { html += '<ul>'; inList = true; }
        html += `<li>${escapeHtml(trimmed.slice(2)).replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')}</li>`;
      } else {
        if (inList) { html += '</ul>'; inList = false; }
        if (trimmed) html += `<p>${escapeHtml(trimmed).replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')}</p>`;
      }
    }
    if (inList) html += '</ul>';
    return html || `<p>${escapeHtml(text)}</p>`;
  }

  function getRoleSuggestions() {
    const r = role();
    if (r === 'vendor') return [
      {label:'Open jobs',query:'Show me open work orders'},
      {label:'My jobs',query:'Show my active jobs'},
      {label:'My quotations',query:'Show my quotations'},
      {label:'How to finish',query:'How do I start and complete a job?'}
    ];
    if (r === 'admin') return [
      {label:'Finances',query:'Give me a financial summary'},
      {label:'Complaints',query:'Show complaints that need attention'},
      {label:'Notices',query:'Show the latest notices'},
      {label:'Vendor performance',query:'How is vendor performance?'}
    ];
    return [
      {label:'My dues',query:'How much maintenance do I owe?'},
      {label:'My complaints',query:'Show my complaints and their status'},
      {label:'My requests',query:'Show my work orders'},
      {label:'Payments',query:'Take me to payments'}
    ];
  }

  function renderChips() {
    const wrap = document.getElementById('chatbotChips');
    if (!wrap) return;
    const suggestions = getRoleSuggestions();
    wrap.innerHTML = suggestions.map((s,i)=>`<button type="button" class="chatbot-chip" data-idx="${i}">${escapeHtml(s.label)}</button>`).join('');
    wrap.querySelectorAll('.chatbot-chip').forEach(btn => btn.onclick = () => {
      const item = suggestions[Number(btn.dataset.idx)];
      if (item) sendMessage(item.query);
    });
  }

  function mountChatbot() {
    if (document.getElementById('chatbotFab')) return;
    const fab = document.createElement('button');
    fab.id='chatbotFab'; fab.className='chatbot-fab'; fab.type='button';
    fab.setAttribute('aria-label','Open AK community assistant'); fab.title='AK — Community Assistant';
    fab.innerHTML=`<span class="chatbot-fab-icon">${HEROICON_CPU}</span><span class="chatbot-fab-label">AK</span>`;
    fab.onclick=toggleChatbot; document.body.appendChild(fab);

    const panel=document.createElement('div'); panel.id='chatbotPanel'; panel.className='chatbot-panel';
    panel.innerHTML=`
      <div class="chatbot-header">
        <div class="chatbot-header-info">
          <div class="chatbot-avatar">${HEROICON_CPU}</div>
          <div><h4 class="chatbot-title" id="chatbotHeaderTitle">AK · Community Assistant</h4><p class="chatbot-sub" id="chatbotHeaderSub">Your NestLedger command assistant</p><span class="chatbot-voice-status" id="chatbotVoiceStatus" hidden>Listening…</span></div>
        </div>
        <div class="chatbot-header-actions">
          <button type="button" class="chatbot-icon-btn" id="chatbotClearBtn" title="Clear chat"><i data-lucide="trash-2"></i></button>
          <button type="button" class="chatbot-icon-btn" id="chatbotCloseBtn" title="Close chat"><i data-lucide="x"></i></button>
        </div>
      </div>
      <div class="chatbot-chips" id="chatbotChips"></div>
      <div class="chatbot-body" id="chatbotBody"></div>
      <form class="chatbot-footer" id="chatbotForm">
        <div class="chatbot-input-wrap"><input type="text" class="chatbot-input" id="chatbotInput" placeholder="Ask AK anything or type a command..." autocomplete="off" /></div>
        <button type="button" class="voice-mic chatbot-voice-mic" id="chatbotVoiceMic" aria-label="Speak to AK" title="Speak to AK"><span class="voice-mic-icon"><i data-lucide="mic"></i></span></button>
        <button type="submit" class="chatbot-send" id="chatbotSendBtn">Send</button>
      </form>`;
    document.body.appendChild(panel);
    if (global.lucide?.createIcons) global.lucide.createIcons({attrs:{'stroke-width':1.8}});
    document.getElementById('chatbotCloseBtn').onclick=closeChatbot;
    document.getElementById('chatbotClearBtn').onclick=clearChat;
    document.getElementById('chatbotForm').onsubmit=(e)=>{e.preventDefault();const input=document.getElementById('chatbotInput');const v=input.value.trim();if(v&&!isThinking){input.value='';sendMessage(v);}};
    renderChips(); initGreeting();
    if (global.NLVoice?.mountInlineMic) global.NLVoice.mountInlineMic(document.getElementById('chatbotForm'));
  }

  function initGreeting() {
    const body=document.getElementById('chatbotBody'); if(!body||body.children.length) return;
    appendMessage('assistant', `Hi! I'm **AK**, NestLedger's community assistant. I can answer questions, open sections, find your records, and carry out supported actions with confirmation when needed. What would you like to do?`);
  }

  function appendMessage(type,text,action=null) {
    const body=document.getElementById('chatbotBody'); if(!body) return;
    const el=document.createElement('div'); el.className=`chatbot-msg ${type}`;
    if(type==='user') el.textContent=text;
    else {
      let html=formatAssistantText(text);
      if(action?.target){html+=`<div><button type="button" class="chat-action-btn" data-action="${escapeHtml(action.target)}">↗ ${escapeHtml(action.label||'Open')}</button></div>`;}
      el.innerHTML=html;
      el.querySelector('.chat-action-btn')?.addEventListener('click',()=>executeAction({type:'navigate',target:el.querySelector('.chat-action-btn').dataset.action},false));
    }
    body.appendChild(el); body.scrollTop=body.scrollHeight;
  }
  function showTyping(){removeTyping();const body=document.getElementById('chatbotBody');if(!body)return;const t=document.createElement('div');t.id='chatbotTyping';t.className='chatbot-typing';t.innerHTML='<span></span><span></span><span></span>';body.appendChild(t);body.scrollTop=body.scrollHeight;}
  function removeTyping(){document.getElementById('chatbotTyping')?.remove();}

  function normalizeText(s){return String(s||'').toLowerCase().replace(/[’']/g,"'").replace(/\s+/g,' ').trim();}
  function parseId(text, keywords) {
    const k=keywords.join('|');
    const m=normalizeText(text).match(new RegExp(`(?:${k})\\s*(?:#|no\\.?|number|id)?\\s*(\\d+)`,'i'));
    return m?Number(m[1]):null;
  }
  function parsePair(text, firstKeys, secondKeys){
    const a=parseId(text,firstKeys), b=parseId(text,secondKeys);
    return {a,b};
  }
  function pageFromText(text){
    const s=normalizeText(text);
    const explicit=s.match(/(?:go to|open|show me|take me to|navigate to|visit)\s+(.+)/i);
    const candidate=(explicit?explicit[1]:s).replace(/^(the|my)\s+/,'').replace(/[?.!]+$/,'').trim();
    const keys=Object.keys(NAV_ALIASES).sort((a,b)=>b.length-a.length);
    return keys.find(k=>candidate===k||candidate.includes(k)) ? NAV_ALIASES[keys.find(k=>candidate===k||candidate.includes(k))] : null;
  }
  function roleAllows(action){
    const r=role();
    if(action==='admin') return r==='admin';
    if(action==='vendor') return r==='vendor';
    if(action==='resident') return r==='resident';
    return true;
  }

  async function executeLocalCommand(text){
    const s=normalizeText(text);
    if(!s) return false;
    if(/^(clear|clear chat|reset chat|start over)$/.test(s)){clearChat();return true;}
    if(/^(close|close chat|hide assistant)$/.test(s)){closeChatbot();return true;}
    if(/^(refresh|reload|refresh page)$/.test(s)){if(typeof loadPage==='function')await loadPage();appendMessage('assistant','Done — I refreshed the current section.');return true;}
    if(/^(dark mode|enable dark mode|turn on dark mode)$/.test(s)){global.applyTheme?.('dark');appendMessage('assistant','Dark mode is on.');return true;}
    if(/^(light mode|enable light mode|turn off dark mode)$/.test(s)){global.applyTheme?.('light');appendMessage('assistant','Light mode is on.');return true;}
    if(/^(logout|log out|sign out)$/.test(s)){if(confirmAction('Log out of NestLedger?'))global.logout?.();return true;}
    if(/^(mark all notifications read|read all notifications|clear notifications)$/.test(s)){if(!confirmAction('Mark all notifications as read?'))return true;try{await global.api('/notifications/read-all',{method:'PATCH'});global.renderBell?.();appendMessage('assistant','All notifications are marked as read.');}catch(e){appendMessage('assistant',`I couldn't update notifications: ${e.message||'request failed'}`);}return true;}

    const nav=pageFromText(s);
    if(nav && ALLOWED_NAV.has(nav)){global.go?.(nav);appendMessage('assistant',`Opening **${nav.replace(/([a-z])([A-Z])/g,'$1 $2')}**.`);return true;}

    if(/\b(create|add|new|raise|post|assign)\b/.test(s)){
      const map=[
        {re:/resident/,fn:'residentModal',roles:['admin'],label:'resident form'},
        {re:/vendor/,fn:'vendorModal',roles:['admin'],label:'vendor form'},
        {re:/expense/,fn:'expenseModal',roles:['admin'],label:'expense form'},
        {re:/notice|announcement/,fn:'noticeModal',roles:['admin'],label:'notice form'},
        {re:/maintenance bill|bill|dues/,fn:'maintenanceBillModal',roles:['admin'],label:'maintenance bill form'},
        {re:/complaint|issue/,fn:'complaintModal',roles:['resident'],label:'complaint form'},
        {re:/work order|maintenance request|repair/,fn:'workOrderModal',roles:['resident','admin'],label:'work order form'}
      ];
      const hit=map.find(x=>x.re.test(s));
      if(hit){if(!hit.roles.includes(role())){appendMessage('assistant',`I can't open the ${hit.label} from your current role.`);return true;}if(typeof global[hit.fn]==='function'){global[hit.fn](role()==='admin'&&hit.fn==='workOrderModal');appendMessage('assistant',`I opened the **${hit.label}**. I won't submit it until you review the details.`);}return true;}
    }

    if(/\b(pay|make payment|pay bill|pay vendor)\b/.test(s)){
      const billId=parseId(s,['bill','payment','invoice']);
      const vendorWoId=parseId(s,['work order','workorder','job']);
      if(/vendor|work order|job/.test(s) && vendorWoId && typeof global.payVendor==='function' && ['resident','admin'].includes(role())){
        if(confirmAction(`Start vendor payment for work order #${vendorWoId}?`))global.payVendor(vendorWoId);else appendMessage('assistant','Payment cancelled.');
        return true;
      }
      if(billId&&role()==='resident'&&typeof global.payBill==='function'){
        if(confirmAction(`Start payment for bill #${billId}?`))global.payBill(billId);else appendMessage('assistant','Payment cancelled.');
        return true;
      }
      global.go?.('payments'); appendMessage('assistant','Opening Payments. I will not start a payment automatically. Tell me the bill number if you want to prepare a specific payment.'); return true;
    }

    const woId=parseId(s,['work order','workorder','job','request']);
    if(woId && role()==='vendor'){
      if(/\b(accept|take|claim)\b/.test(s)&&typeof global.acceptWorkOrder==='function'){if(confirmAction(`Accept work order #${woId}?`))global.acceptWorkOrder(woId);else appendMessage('assistant','Action cancelled.');return true;}
      if(/\b(withdraw|drop|cancel)\b/.test(s)&&typeof global.withdrawWorkOrder==='function'){if(confirmAction(`Withdraw from work order #${woId}?`))global.withdrawWorkOrder(woId);else appendMessage('assistant','Action cancelled.');return true;}
      if(/\b(start|begin|in progress)\b/.test(s)&&typeof global.setWorkOrderStatus==='function'){if(confirmAction(`Start work order #${woId}?`))global.setWorkOrderStatus(woId,'in_progress');else appendMessage('assistant','Action cancelled.');return true;}
      if(/\b(complete|finish|done)\b/.test(s)&&typeof global.setWorkOrderStatus==='function'){if(confirmAction(`Mark work order #${woId} as completed?`))global.setWorkOrderStatus(woId,'completed');else appendMessage('assistant','Action cancelled.');return true;}
    }

    const quote=parsePair(s,['quote','quotation'],['work order','workorder','job','request']);
    if(quote.a&&quote.b){
      if(/\baccept\b/.test(s)&&role()==='resident'&&typeof global.acceptQuote==='function'){if(confirmAction(`Accept quote #${quote.a} for work order #${quote.b}?`))global.acceptQuote(quote.b,quote.a);else appendMessage('assistant','Action cancelled.');return true;}
      if(/\breject|decline\b/.test(s)&&role()==='resident'&&typeof global.rejectQuote==='function'){if(confirmAction(`Reject quote #${quote.a} for work order #${quote.b}?`))global.rejectQuote(quote.b,quote.a);else appendMessage('assistant','Action cancelled.');return true;}
      if(/\bwithdraw\b/.test(s)&&role()==='vendor'&&typeof global.withdrawQuote==='function'){if(confirmAction(`Withdraw quote #${quote.a} from work order #${quote.b}?`))global.withdrawQuote(quote.b,quote.a);else appendMessage('assistant','Action cancelled.');return true;}
    }

    const complaintId=parseId(s,['complaint','issue']);
    if(complaintId&&role()==='admin'&&typeof global.updateComplaintStatus==='function'){
      const statuses=[['close|closed|resolve|resolved','closed'],['open|reopen','open'],['progress|in progress','in_progress']];
      const hit=statuses.find(([re])=>new RegExp(`\\b(?:${re})\\b`).test(s));
      if(hit){if(confirmAction(`Set complaint #${complaintId} to ${hit[1]}?`))global.updateComplaintStatus(complaintId,hit[1]);else appendMessage('assistant','Action cancelled.');return true;}
    }

    const ratingWo=parseId(s,['work order','workorder','job']);
    if(ratingWo&&role()==='resident'&&/\b(rate|rating|review)\b/.test(s)&&typeof global.rateVendorModal==='function'){global.rateVendorModal(ratingWo);return true;}

    if(/\b(help|what can you do|commands|capabilities)\b/.test(s)){
      appendMessage('assistant','I can navigate every main section, answer role-scoped questions, refresh data, switch themes, manage notifications, open creation forms, and carry out supported work-order, quotation, complaint, and payment actions. Sensitive actions always ask for confirmation.');
      return true;
    }
    return false;
  }

  async function sendMessage(messageText){
    const text=String(messageText||'').trim(); if(!text||isThinking)return;
    appendMessage('user',text); conversationHistory.push({role:'user',parts:[{text}]});
    if(await executeLocalCommand(text)) return;
    isThinking=true; showTyping();
    const sendBtn=document.getElementById('chatbotSendBtn'); if(sendBtn)sendBtn.disabled=true;
    try{
      const data=await global.api('/ai/chat',{method:'POST',body:JSON.stringify({message:text,lang:currentLang(),history:conversationHistory.slice(-10)})});
      removeTyping();
      const reply=data.reply||'I could not process that request.';
      appendMessage('assistant',reply,data.action&&data.action.type==='navigate'?data.action:null);
      conversationHistory.push({role:'model',parts:[{text:reply}]});
      const lower=normalizeText(text);
      const target=data.action?.target;
      if(target&&ALLOWED_NAV.has(target)&&/\b(take me|go to|open|show me|navigate)\b/.test(lower))global.go?.(target);
    }catch(e){removeTyping();appendMessage('assistant',`I couldn't reach the assistant service right now. ${e.message||'Please try again.'}`);}
    finally{isThinking=false;if(sendBtn)sendBtn.disabled=false;document.getElementById('chatbotInput')?.focus();}
  }

  async function executeAction(action, announce=true){
    if(!action)return false;
    if(action.type==='navigate'&&ALLOWED_NAV.has(action.target)){global.go?.(action.target);if(announce)appendMessage('assistant',`Opening **${action.target}**.`);return true;}
    return false;
  }

  function openChatbot(){isPanelOpen=true;document.getElementById('chatbotPanel')?.classList.add('open');const b=document.getElementById('chatbotBody');if(b)b.scrollTop=b.scrollHeight;document.getElementById('chatbotInput')?.focus();}
  function closeChatbot(){isPanelOpen=false;document.getElementById('chatbotPanel')?.classList.remove('open');}
  function toggleChatbot(){isPanelOpen?closeChatbot():openChatbot();}
  function clearChat(){conversationHistory.length=0;removeTyping();isThinking=false;const b=document.getElementById('chatbotBody');if(b)b.innerHTML='';initGreeting();renderChips();document.getElementById('chatbotInput')?.focus();}
  function refreshLabel(){const title=document.getElementById('chatbotHeaderTitle');if(title)title.textContent=`AK · ${hasI18n()?global.i18n.t('chatbotTitle'):'Community Assistant'}`;const sub=document.getElementById('chatbotHeaderSub');if(sub)sub.textContent='Your NestLedger command assistant';const input=document.getElementById('chatbotInput');if(input)input.placeholder='Ask AK anything or type a command...';const send=document.getElementById('chatbotSendBtn');if(send)send.textContent=hasI18n()?global.i18n.t('chatbotSend'):'Send';renderChips();}

  global.NLChatbot={mount:mountChatbot,open:openChatbot,close:closeChatbot,toggle:toggleChatbot,clearChat,refreshLabel,sendMessage,executeAction};
})(window);
