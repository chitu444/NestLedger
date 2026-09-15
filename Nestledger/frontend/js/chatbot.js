/* AK — NestLedger Community Assistant
 * Reliable local-first assistant. Voice commands are handled by the deterministic NLVoice command layer.
 */
(function (global) {
  const NAV = {
    home:'dashboard', dashboard:'dashboard', overview:'dashboard',
    payment:'payments', payments:'payments', bill:'payments', bills:'payments', dues:'payments',
    receipt:'receipts', receipts:'receipts',
    complaint:'complaints', complaints:'complaints', issue:'complaints', issues:'complaints',
    notice:'notices', notices:'notices', announcements:'notices',
    workorder:'workorders', workorders:'workorders', request:'workorders', requests:'workorders', maintenance:'workorders', jobs:'workorders',
    profile:'profile', account:'profile',
    resident:'residents', residents:'residents', vendor:'vendors', vendors:'vendors',
    expense:'expenses', expenses:'expenses', performance:'vendorperformance', vendorperformance:'vendorperformance',
    reports:'reports', intelligence:'reports', 'business intelligence':'reports'
  };
  const ALLOWED = new Set(Object.values(NAV));
  let open = false, busy = false;

  const esc = s => String(s ?? '').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const norm = s => String(s||'').toLowerCase().replace(/[’']/g,"'").replace(/\s+/g,' ').trim();
  const role = () => global.NLState?.user?.role || 'resident';
  const api = (p,o={}) => global.api ? global.api(p,o) : global.NLApi.request(p,o);
  const go = p => global.go?.(p);

  function icon(){return `<svg class="ak-heroicon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path stroke-linecap="round" stroke-linejoin="round" d="M8.25 3v1.5M12 3v1.5m3.75-1.5v1.5M8.25 19.5V21M12 19.5V21m3.75-1.5V21M3 8.25h1.5M3 12h1.5M3 15.75h1.5M19.5 8.25H21M19.5 12H21m-1.5 3.75H21M6.75 4.5h10.5a2.25 2.25 0 0 1 2.25 2.25v10.5a2.25 2.25 0 0 1-2.25 2.25H6.75a2.25 2.25 0 0 1-2.25-2.25V6.75A2.25 2.25 0 0 1 6.75 4.5Zm.75 2.25h9v9h-9v-9Z"/></svg>`;}
  function suggestions(){
    if(role()==='admin') return [['Finance summary','Give me a financial summary'],['BI dashboard','Open Business Intelligence'],['Complaints','Show complaints that need attention'],['Vendor performance','How is vendor performance?']];
    if(role()==='vendor') return [['My jobs','Show my active jobs'],['Open jobs','Show open work orders'],['My profile','Open my profile'],['Help','What can you do?']];
    return [['My dues','How much do I owe?'],['My requests','Show my work orders'],['My complaints','Show my complaints'],['Payments','Open payments']];
  }
  function renderSuggestions(){const el=document.getElementById('akSuggestions');if(!el)return;el.innerHTML=suggestions().map((x,i)=>`<button type="button" data-i="${i}">${esc(x[0])}</button>`).join('');el.querySelectorAll('button').forEach(b=>b.onclick=()=>send(suggestions()[+b.dataset.i][1]));}
  function add(type,text){const body=document.getElementById('akBody');if(!body)return;const m=document.createElement('div');m.className='ak-msg '+type;m.innerHTML=type==='user'?esc(text):String(text);body.appendChild(m);body.scrollTop=body.scrollHeight;}
  function reply(text){add('assistant',esc(text).replace(/\*\*(.*?)\*\*/g,'<strong>$1</strong>').replace(/\n/g,'<br>'));}
  function navFrom(s){const direct=s.match(/(?:go to|open|show me|take me to|navigate to)\s+(.+)/);const candidate=(direct?direct[1]:s).replace(/^(the|my)\s+/,'').replace(/[?.!]$/,'').trim();const key=Object.keys(NAV).sort((a,b)=>b.length-a.length).find(k=>candidate===k||candidate.includes(k));return key?NAV[key]:null;}
  function id(s, words){const m=s.match(new RegExp(`(?:${words.join('|')})\\s*(?:#|no\\.?|number|id)?\\s*(\\d+)`));return m?+m[1]:null;}
  function local(s){
    if(/^(close|hide assistant|close chat)$/.test(s)){close();return true;}
    if(/^(clear|clear chat|reset chat)$/.test(s)){clear();return true;}
    if(/^(help|what can you do|commands|capabilities)$/.test(s)){reply('I can open NestLedger sections, explain your bills and requests, summarize your records, show community notices, and guide supported actions. Sensitive actions always require your confirmation.');return true;}
    const page=navFrom(s); if(page&&ALLOWED.has(page)){go(page);reply(`Opening ${page.replace('vendorperformance','vendor performance').replace('workorders','work orders')}.`);return true;}
    if(/\b(due|dues|owe|outstanding|maintenance bill)\b/.test(s)){go('payments');reply('I opened Payments so you can see your current maintenance bills, outstanding amount and payment history.');return true;}
    if(/\b(complaint|issue)\b/.test(s)){go('complaints');reply('I opened Complaints so you can review current issues and their status.');return true;}
    if(/\b(notice|announcement)\b/.test(s)){go('notices');reply('I opened Notices for the latest community announcements.');return true;}
    if(/\b(work order|maintenance request|repair|job)\b/.test(s)){go('workorders');reply('I opened Work Orders so you can review maintenance requests and job status.');return true;}
    if(/\bpay|payment\b/.test(s)){go('payments');reply('I opened Payments. I will not start a payment without your explicit confirmation.');return true;}
    if(/\b(refresh|reload)\b/.test(s)){global.loadPage?.();reply('Refreshing the current section.');return true;}
    return false;
  }
  async function send(text){text=String(text||'').trim();if(!text||busy)return;add('user',text);const s=norm(text);if(s==='start listening'||s==='begin listening'||s==='voice on'||s==='listen to me'){global.NLVoice?.startListening?.();reply('Voice control is on. I am listening for commands. Say “stop listening” when you are finished.');return;}if(s==='stop listening'||s==='voice off'||s==='turn off voice'||s==='pause listening'){global.NLVoice?.stopListening?.();reply('Voice control is off.');return;}if(global.NLVoice?.handleText?.(text)){return;}if(local(s))return;busy=true;const btn=document.getElementById('akSend');if(btn)btn.disabled=true;try{const d=await api('/ai/chat',{method:'POST',body:JSON.stringify({message:text,lang:global.i18n?.getLanguage?.()||'en',history:[]})});if(d?.action?.target&&ALLOWED.has(d.action.target)){go(d.action.target);}reply(d?.reply||'I could not find an answer for that. Try asking me to open a section or show your current records.');}catch(e){reply(`I couldn't reach the assistant service. ${e?.message||'Please try again.'}`);}finally{busy=false;if(btn)btn.disabled=false;document.getElementById('akInput')?.focus();}}
  function mount(){if(document.getElementById('akFab'))return;const fab=document.createElement('button');fab.id='akFab';fab.className='chatbot-fab';fab.type='button';fab.setAttribute('aria-label','Open AK community assistant');fab.title='AK — Community Assistant';fab.innerHTML=`<span class="chatbot-fab-icon">${icon()}</span>`;fab.onclick=toggle;document.body.appendChild(fab);
    const panel=document.createElement('section');panel.id='akPanel';panel.className='chatbot-panel';panel.innerHTML=`<header class="ak-header"><div class="ak-head-main"><div class="ak-avatar">${icon()}</div><div><strong>AK · Community Assistant</strong><small>NestLedger command center</small></div></div><div class="ak-actions"><button id="akClear" type="button" aria-label="Clear chat" title="Clear chat">⌫</button><button id="akClose" type="button" aria-label="Close assistant" title="Close">×</button></div></header><div class="ak-suggestions" id="akSuggestions"></div><div class="ak-body" id="akBody"></div><form class="ak-footer" id="akForm"><div class="ak-input-row"><input id="akInput" autocomplete="off" placeholder="Ask AK or say a command…"><button id="chatbotVoiceMic" class="voice-mic chatbot-voice-mic" type="button" aria-label="Start listening" title="Start listening"><span class="voice-mic-icon"><i data-lucide="mic"></i></span></button><button id="akSend" type="submit">Send</button></div><div class="chatbot-voice-status" id="chatbotVoiceStatus" data-state="off" aria-live="polite">Voice off</div></form>`;document.body.appendChild(panel);
    if(global.NLVoice?.mountInlineMic)global.NLVoice.mountInlineMic(document.getElementById('akForm')); if(global.NLVoice?.mountGlobalMic)global.NLVoice.mountGlobalMic();
    document.getElementById('akClose').onclick=close;document.getElementById('akClear').onclick=clear;document.getElementById('akForm').onsubmit=e=>{e.preventDefault();const i=document.getElementById('akInput');const v=i.value.trim();if(v){i.value='';send(v);}};renderSuggestions();reply('Hi! I’m AK. I can help you navigate NestLedger and understand what is happening in your community.');
  }
  function openChat(){open=true;document.getElementById('akPanel')?.classList.add('open');document.getElementById('akInput')?.focus();}
  function close(){open=false;document.getElementById('akPanel')?.classList.remove('open');}
  function toggle(){open?close():openChat();}
  function clear(){const b=document.getElementById('akBody');if(b)b.innerHTML='';reply('Chat cleared. What would you like AK to help with?');renderSuggestions();}
  global.NLChatbot={mount,open:openChat,close,toggle,clearChat:clear,refreshLabel:renderSuggestions,sendMessage:send};
})(window);
