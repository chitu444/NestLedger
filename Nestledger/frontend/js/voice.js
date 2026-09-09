/* NestLedger Voice Assistant v2
 * Free voice control: browser Web Speech API only.
 */
(function (global) {
  'use strict';

  const SR = global.SpeechRecognition || global.webkitSpeechRecognition;
  let recognition = null;
  let listening = false;
  let lastTranscript = '';
  let selectedAlternative = '';

  const PAGE_ALIASES = {
    dashboard: ['dashboard','home','main screen','home screen','ഡാഷ്ബോർഡ്','டாஷ்போர்டு','ಡ್ಯಾಶ್‌ಬೋರ್ಡ್','డాష్‌బోర్డ్','डैशबोर्ड'],
    payments: ['payments','payment','pay','maintenance payment','maintenance payments','bills','bill','കെട്ടണം','கட்டணம்','ಪಾವತಿ','చెల్లింపు','भुगतान'],
    receipts: ['receipts','receipt','payment receipt','receipts page','രസീത്','ரசீது','ರಸೀದಿ','రసీదు','रसीद'],
    complaints: ['complaints','complaint','raise complaint','file complaint','register complaint','പരാതി','புகார்','ದೂರು','ఫిర్యాదు','शिकायत'],
    notices: ['notices','notice','announcements','announcement','അറിയിപ്പ്','அறிவிப்பு','ಸೂಚನೆ','నోటీసు','सूचना'],
    workorders: ['work orders','work order','maintenance requests','maintenance request','repair requests','repair','maintenance','അറ്റകുറ്റപ്പണി','பராமரிப்பு','ನಿರ್ವಹಣೆ','నిర్వహణ','रखरखाव'],
    profile: ['profile','my profile','account','my account','account settings','പ്രൊഫൈൽ','சுயவிவரம்','ಪ್ರೊಫೈಲ್','ప్రొఫైల్','प्रोफ़ाइल'],
    residents: ['residents','resident','resident list','tenants','താമസക്കാർ','குடியிருப்போர்','ನಿವಾಸಿಗಳು','నివాసులు','निवासी'],
    vendors: ['vendors','vendor','service providers','vendor list','വെൻഡർമാർ','விற்பனையாளர்கள்','ವ್ಯಾಪಾರಿಗಳು','వెండర్లు','विक्रेता'],
    expenses: ['expenses','expense','spending','costs','ചെലവുകൾ','செலவுகள்','ವೆಚ್ಚಗಳು','ఖర్చులు','खर्च'],
    vendorperformance: ['vendor performance','vendor ratings','vendor rating','വെൻഡർ പ്രകടനം','விற்பனையாளர் செயல்திறன்','ವಿಕ್ರೇತ ಕಾರ್ಯಕ್ಷಮತೆ','వెండర్ పనితీరు','विक्रेता प्रदर्शन']
  };

  const COMMANDS = [
    { id:'dashboard', phrases:['dashboard','home','go home','open dashboard','show dashboard','main screen'] },
    { id:'payments', phrases:['payments','payment','open payments','show payments','my payments','payment history','bills','maintenance bill','maintenance bills'] },
    { id:'receipts', phrases:['receipts','receipt','open receipts','show receipts','payment receipt','download receipt','get receipt','generate receipt','latest receipt'] },
    { id:'complaints', phrases:['complaints','complaint','open complaints','show complaints','my complaints','raise complaint','file complaint','register complaint','new complaint'] },
    { id:'notices', phrases:['notices','notice','open notices','show notices','announcements','announcement'] },
    { id:'workorders', phrases:['work orders','work order','maintenance requests','maintenance request','open maintenance','show maintenance','repair requests','repairs'] },
    { id:'profile', phrases:['profile','my profile','open profile','my account','account settings'] },
    { id:'residents', roles:['admin'], phrases:['residents','resident list','show residents','open residents','add resident','new resident'] },
    { id:'vendors', roles:['admin'], phrases:['vendors','vendor list','show vendors','open vendors','add vendor','new vendor'] },
    { id:'expenses', roles:['admin'], phrases:['expenses','expense','show expenses','open expenses','add expense','new expense'] },
    { id:'vendorperformance', roles:['admin'], phrases:['vendor performance','vendor ratings','vendor rating','show vendor performance'] },
    { id:'read_dues', phrases:['read my dues','my dues','show my dues','how much do i owe','what do i owe','amount due','outstanding balance','maintenance due','how much is my maintenance'] },
    { id:'pay_bill', phrases:['pay my bill','pay maintenance','pay maintenance bill','pay my maintenance','make a payment','pay this bill','pay bill'] },
    { id:'latest_receipt', phrases:['latest receipt','my latest receipt','get my receipt','download my receipt','generate my receipt','receipt for my payment'] },
    { id:'new_complaint', phrases:['raise a complaint','file a complaint','register a complaint','create a complaint','new complaint','report a problem'] },
    { id:'new_workorder', phrases:['request maintenance','request repair','create work order','new maintenance request','new work order','report a repair'] },
    { id:'new_notice', roles:['admin'], phrases:['post notice','create notice','new notice','publish notice'] },
    { id:'add_resident', roles:['admin'], phrases:['add resident','create resident','new resident'] },
    { id:'add_vendor', roles:['admin'], phrases:['add vendor','create vendor','new vendor'] },
    { id:'new_expense', roles:['admin'], phrases:['add expense','create expense','new expense','record expense'] },
    { id:'logout', phrases:['log out','logout','sign out','exit account','leave account'] },
    { id:'help', phrases:['help','what can you do','voice help','commands'] }
  ];

  function normalize(text) {
    return String(text || '').normalize('NFKC').toLowerCase()
      .replace(/[“”‘’]/g, '"')
      .replace(/[^\p{L}\p{N}\s₹$]/gu, ' ')
      .replace(/\s+/g, ' ').trim();
  }

  function words(text) { return normalize(text).split(/\s+/).filter(Boolean); }

  function distance(a,b) {
    const aa=String(a), bb=String(b);
    const prev=Array.from({length:bb.length+1},(_,i)=>i);
    for(let i=0;i<aa.length;i++){
      let cur=[i+1];
      for(let j=0;j<bb.length;j++) cur[j+1]=Math.min(cur[j]+1,prev[j+1]+1,prev[j]+(aa[i]===bb[j]?0:1));
      for(let j=0;j<cur.length;j++) prev[j]=cur[j];
    }
    return prev[bb.length];
  }

  function scorePhrase(text, phrase) {
    const t=normalize(text), p=normalize(phrase);
    if (!t || !p) return 0;
    if (t === p) return 100;
    if (t.includes(p)) return 90 + Math.min(8, p.length/30);
    const tw=words(t), pw=words(p);
    let matched=0;
    pw.forEach(x=>{
      if(tw.some(y=>y===x || (x.length>=5 && y.length>=5 && distance(x,y)<=Math.max(1,Math.floor(Math.min(x.length,y.length)*0.2))))) matched++;
    });
    if(!matched) return 0;
    return 50 + 35*(matched/pw.length);
  }

  function matchCommand(transcript) {
    const role = global.state && global.state.role;
    let best=null, bestScore=0;
    for(const cmd of COMMANDS) {
      if(cmd.roles && !cmd.roles.includes(role)) continue;
      for(const phrase of cmd.phrases) {
        const s=scorePhrase(transcript,phrase);
        if(s>bestScore){bestScore=s;best=cmd;}
      }
    }
    // Page aliases are useful for natural "take me to..." phrasing.
    const t=normalize(transcript);
    for(const [page,aliases] of Object.entries(PAGE_ALIASES)){
      const s=Math.max(...aliases.map(a=>scorePhrase(t,a)));
      if(s>bestScore && s>=70) { best={id:page,phrases:aliases}; bestScore=s; }
    }
    return bestScore>=58 ? best : null;
  }

  function pageGo(page) {
    if (typeof global.go === 'function') { global.go(page); return true; }
    return false;
  }

  function speak(text) {
    if(!global.speechSynthesis || !text) return;
    const lang=(global.i18n && global.i18n.SPEECH_LOCALE && global.i18n.SPEECH_LOCALE[global.i18n.getLanguage()])
      || 'en-IN';
    const u=new SpeechSynthesisUtterance(text);
    u.lang=lang; global.speechSynthesis.cancel(); global.speechSynthesis.speak(u);
  }

  function notify(text) {
    if(typeof global.toast==='function') global.toast(text);
    speak(text);
  }

  function roleAllowed(cmd) {
    return !cmd.roles || (global.state && cmd.roles.includes(global.state.role));
  }

  function clickButtonByText(patterns, preferredPage) {
    if(preferredPage && global.state && global.state.page !== preferredPage) {
      pageGo(preferredPage);
      setTimeout(()=>clickButtonByText(patterns, preferredPage),450);
      return true;
    }
    const buttons=[...document.querySelectorAll('button:not([disabled]), a, [role="button"]')];
    const candidates=buttons.map(el=>({el,text:normalize(el.innerText||el.getAttribute('aria-label')||el.title||'')}))
      .filter(x=>x.text && patterns.some(p=>scorePhrase(x.text,p)>=72));
    if(!candidates.length) return false;
    candidates.sort((a,b)=>b.text.length-a.text.length);
    candidates[0].el.click();
    return true;
  }

  async function dashboardData() {
    try { return await global.api('/dashboard'); } catch { return null; }
  }

  async function readDues() {
    const d=await dashboardData();
    if(!d){notify('I could not read your dues right now.');return true;}
    const amount=Number(d.due||0).toLocaleString('en-IN');
    const msg=(global.i18n?global.i18n.t('pending'):'Pending')+`: ₹${amount}`;
    notify(msg); return true;
  }

  function confirmAnd(action, message) {
    if(typeof global.confirm !== 'function') { action(); return; }
    if(global.confirm(message)) action();
  }

  function execute(cmd, transcript) {
    if(!cmd || !roleAllowed(cmd)) return false;
    const t=normalize(transcript);

    if(cmd.id==='help'){
      const msg=(global.i18n && global.i18n.t('voiceHelp')) || 'You can open pages, read dues, create requests, pay bills, and get receipts by voice.';
      notify(msg); return true;
    }
    if(cmd.id==='logout'){
      confirmAnd(()=>{if(typeof global.logout==='function') global.logout();}, 'Log out of NestLedger?');
      return true;
    }
    if(cmd.id==='read_dues') return readDues();

    if(cmd.id==='pay_bill'){
      confirmAnd(()=>{
        if(global.state && global.state.page!=='payments') pageGo('payments');
        setTimeout(()=>{
          if(!clickButtonByText(['pay maintenance','pay bill','pay ₹','pay'])) notify('Open Payments and choose the bill you want to pay.');
        },500);
      }, 'Open the payment screen and prepare your maintenance payment?');
      return true;
    }

    if(cmd.id==='latest_receipt'){
      if(global.state && global.state.page!=='receipts') pageGo('receipts');
      setTimeout(()=>{
        if(!clickButtonByText(['download receipt','receipt','download'])) notify('I could not find a paid receipt yet.');
      },500);
      return true;
    }

    if(cmd.id==='new_complaint'){
      pageGo('complaints'); setTimeout(()=>{if(typeof global.complaintModal==='function')global.complaintModal();},450); return true;
    }
    if(cmd.id==='new_workorder'){
      pageGo('workorders'); setTimeout(()=>{if(typeof global.workOrderModal==='function')global.workOrderModal();},450); return true;
    }
    if(cmd.id==='new_notice'){
      pageGo('notices'); setTimeout(()=>{if(typeof global.noticeModal==='function')global.noticeModal();},450); return true;
    }
    if(cmd.id==='add_resident'){
      pageGo('residents'); setTimeout(()=>{if(typeof global.residentModal==='function')global.residentModal();},450); return true;
    }
    if(cmd.id==='add_vendor'){
      pageGo('vendors'); setTimeout(()=>{if(typeof global.vendorModal==='function')global.vendorModal();},450); return true;
    }
    if(cmd.id==='new_expense'){
      pageGo('expenses'); setTimeout(()=>{if(typeof global.expenseModal==='function')global.expenseModal();},450); return true;
    }

    if(PAGE_ALIASES[cmd.id]) return pageGo(cmd.id);

    // Natural "click/open/show ..." requests can operate visible buttons.
    if(/\b(click|press|select|open|show)\b/.test(t)){
      if(clickButtonByText([t])) return true;
    }
    return false;
  }

  function handleTranscript(transcript) {
    const text=String(transcript||'').trim();
    if(!text)return;
    lastTranscript=text;
    const cmd=matchCommand(text);
    if(cmd && execute(cmd,text)) return;

    // Voice remains conversational: hand non-command speech to the Gemini chatbot.
    if(global.NLChatbot && typeof global.NLChatbot.sendMessage==='function'){
      global.NLChatbot.open && global.NLChatbot.open();
      global.NLChatbot.sendMessage(text);
    } else {
      notify(`I heard: ${text}`);
    }
  }

  function updateUI() {
    document.querySelectorAll('.voice-mic').forEach(btn=>{
      btn.classList.toggle('listening',listening);
      btn.setAttribute('aria-pressed',String(listening));
      const label=btn.querySelector('.voice-mic-label');
      if(label) label.textContent=listening
        ? (global.i18n?global.i18n.t('voiceListening'):'Listening…')
        : (global.i18n?global.i18n.t('voiceTapToSpeak'):'Speak');
    });
  }

  function recognitionInstance() {
    if(!SR)return null;
    if(recognition)return recognition;
    recognition=new SR();
    recognition.continuous=false;
    recognition.interimResults=true;
    recognition.maxAlternatives=5;
    recognition.onresult=e=>{
      // Use the final result when available; interim text is only for responsiveness.
      let finalText='';
      for(let i=e.resultIndex;i<e.results.length;i++){
        if(e.results[i].isFinal) finalText += ' '+e.results[i][0].transcript;
      }
      if(finalText.trim()){
        listening=false; updateUI(); handleTranscript(finalText.trim());
      }
    };
    recognition.onerror=e=>{
      listening=false; updateUI();
      if(e.error!=='aborted') notify((global.i18n&&global.i18n.t('voiceTryAgain'))||'Please try again.');
    };
    recognition.onend=()=>{
      listening=false; updateUI();
    };
    return recognition;
  }

  function startListening() {
    if(!SR){
      notify((global.i18n&&global.i18n.t('voiceUnsupported'))||'Voice recognition is not supported in this browser.');
      return false;
    }
    if(listening)return true;
    const r=recognitionInstance();
    r.lang=(global.i18n&&global.i18n.SPEECH_LOCALE&&global.i18n.SPEECH_LOCALE[global.i18n.getLanguage()])||'en-IN';
    try{
      if(global.speechSynthesis)global.speechSynthesis.cancel();
      r.start(); listening=true; updateUI();
      if(typeof global.toast==='function')global.toast((global.i18n&&global.i18n.t('voiceListening'))||'Listening…');
      return true;
    }catch(e){ listening=false; updateUI(); return false; }
  }

  function mountInlineMic(container) {
    const wrap=typeof container==='string'?document.querySelector(container):container;
    if(!wrap)return;
    let btn=wrap.querySelector('#chatbotVoiceMic');
    if(!btn){
      btn=document.createElement('button');
      btn.id='chatbotVoiceMic'; btn.type='button'; btn.className='voice-mic chatbot-voice-mic';
      btn.innerHTML='<span class="voice-mic-icon">🎤</span><span class="voice-mic-label"></span>';
      wrap.appendChild(btn);
    }
    btn.onclick=startListening;
    btn.setAttribute('aria-label',(global.i18n&&global.i18n.t('voiceTapToSpeak'))||'Speak');
    btn.setAttribute('title',(global.i18n&&global.i18n.t('voiceTapToSpeak'))||'Speak');
    updateUI();
  }

  function refreshLabel(){
    document.querySelectorAll('.voice-mic').forEach(btn=>{
      const label=btn.querySelector('.voice-mic-label');
      if(label)label.textContent=listening?(global.i18n&&global.i18n.t('voiceListening')||'Listening…'):(global.i18n&&global.i18n.t('voiceTapToSpeak')||'Speak');
      btn.setAttribute('title',(global.i18n&&global.i18n.t('voiceTapToSpeak'))||'Speak');
      btn.setAttribute('aria-label',(global.i18n&&global.i18n.t('voiceTapToSpeak'))||'Speak');
    });
  }

  function unmountMicButton(){
    if(recognition){try{recognition.abort()}catch{}}
    recognition=null; listening=false; updateUI();
    document.querySelectorAll('.voice-mic').forEach(x=>x.remove());
  }

  global.NLVoice={
    mountInlineMic, unmountMicButton, refreshLabel, startListening,
    supported:!!SR,
    lastTranscript:()=>lastTranscript
  };
})(window);
