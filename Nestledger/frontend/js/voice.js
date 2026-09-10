/* NestLedger Voice Assistant v3
 * Intent-driven voice control using the browser Web Speech API.
 * No network/AI dependency for deterministic app actions.
 */
(function (global) {
  'use strict';

  const SR = global.SpeechRecognition || global.webkitSpeechRecognition;
  let recognition = null;
  let listening = false;
  let restarting = false;
  let lastTranscript = '';
  let lastIntent = '';
  let lastHandledAt = 0;
  let restartTimer = null;
  let commandBusy = false;

  const PAGE_ALIASES = {
    dashboard: ['dashboard','home','main screen','home screen','control room','ഡാഷ്ബോർഡ്','டாஷ்போர்டு','ಡ್ಯಾಶ್‌ಬೋರ್ಡ್','డాష్‌బోర్డ్','डैशबोर्ड'],
    payments: ['payments','payment','pay','maintenance payment','maintenance payments','bills','bill','കെട്ടണം','கட்டணம்','ಪಾವತಿ','చెల్లింపు','भुगतान'],
    receipts: ['receipts','receipt','payment receipt','receipt page','രസീത്','ரசீது','ರಸೀದಿ','రసీదు','रसीद'],
    complaints: ['complaints','complaint','raise complaint','file complaint','register complaint','പരാതി','புகார்','ದೂರು','ఫిర్యాదు','शिकायत'],
    notices: ['notices','notice','announcements','announcement','അറിയിപ്പ്','அறிவிப்பு','ಸೂಚನೆ','నోటీసు','सूचना'],
    workorders: ['work orders','work order','maintenance requests','maintenance request','repair requests','repairs','maintenance','അറ്റകുറ്റപ്പണി','பராமரிப்பு','ನಿರ್ವಹಣೆ','నిర్వహణ','रखरखाव'],
    profile: ['profile','my profile','account','my account','account settings','പ്രൊഫൈൽ','சுயவிவரம்','ಪ್ರೊಫೈಲ್','ప్రొఫైల్','प्रोफ़ाइल'],
    residents: ['residents','resident','resident list','tenants','താമസക്കാർ','குடியிருப்போர்','ನಿವಾಸಿಗಳು','నివాసులు','निवासी'],
    vendors: ['vendors','vendor','service providers','vendor list','വെൻഡർമാർ','விற்பனையாளர்கள்','ವ್ಯಾಪಾರಿಗಳು','వెండర్లు','विक्रेता'],
    expenses: ['expenses','expense','spending','costs'],
    vendorperformance: ['vendor performance','vendor ratings','vendor rating','vendor scores'],
    notifications: ['notifications','notification','alerts','my notifications']
  };

  // Canonical intent registry. Multiple natural phrases resolve to one stable intent.
  // Roles are enforced here for UX; the API remains the security boundary.
  const COMMANDS = [
    // Global/navigation
    {id:'dashboard', phrases:['dashboard','home','go home','open dashboard','show dashboard','main screen','control room']},
    {id:'payments', phrases:['payments','payment','open payments','show payments','my payments','payment history','bills','maintenance bill','maintenance bills']},
    {id:'receipts', phrases:['receipts','receipt','open receipts','show receipts','payment receipt']},
    {id:'complaints', phrases:['complaints','complaint','open complaints','show complaints','my complaints']},
    {id:'notices', phrases:['notices','notice','open notices','show notices','announcements','announcement']},
    {id:'workorders', phrases:['work orders','work order','maintenance requests','maintenance request','open maintenance','show maintenance','repair requests','repairs']},
    {id:'profile', phrases:['profile','my profile','open profile','my account','account settings']},
    {id:'notifications', phrases:['notifications','notification','alerts','my notifications','open notifications']},
    {id:'residents', roles:['admin'], phrases:['residents','resident list','show residents','open residents','tenants']},
    {id:'vendors', roles:['admin'], phrases:['vendors','vendor list','show vendors','open vendors','service providers']},
    {id:'expenses', roles:['admin'], phrases:['expenses','expense','show expenses','open expenses','spending','costs']},
    {id:'vendorperformance', roles:['admin'], phrases:['vendor performance','vendor ratings','vendor rating','show vendor performance','vendor scores']},

    // Information
    {id:'read_dues', roles:['resident'], phrases:['read my dues','my dues','show my dues','how much do i owe','what do i owe','amount due','outstanding balance','maintenance due','how much is my maintenance']},
    {id:'payment_history', phrases:['show payment history','show my payment history','recent payments','show recent payments']},
    {id:'unpaid_bills', roles:['resident'], phrases:['show unpaid bills','show unpaid maintenance','unpaid bills','pending bills']},
    {id:'paid_bills', roles:['resident'], phrases:['show paid bills','paid bills','paid maintenance']},
    {id:'latest_receipt', roles:['resident'], phrases:['latest receipt','my latest receipt','get my receipt','download my receipt','generate my receipt','receipt for my payment']},
    {id:'read_notifications', phrases:['read notifications','read my notifications','read latest notification','what notifications do i have']},
    {id:'mark_notification_read', phrases:['mark this notification as read','mark notification as read','read this notification']},
    {id:'mark_all_notifications_read', phrases:['mark all notifications as read','mark all notifications read','read all notifications']},

    // Resident create/update actions
    {id:'pay_bill', roles:['resident'], phrases:['pay my bill','pay maintenance','pay maintenance bill','pay my maintenance','make a payment','pay this bill','pay bill']},
    {id:'new_complaint', roles:['resident'], phrases:['raise a complaint','file a complaint','register a complaint','create a complaint','new complaint','report a problem']},
    {id:'new_workorder', roles:['resident'], phrases:['request maintenance','request repair','create work order','new maintenance request','new work order','report a repair']},
    {id:'cancel_workorder', roles:['resident'], phrases:['cancel this request','cancel work order','cancel maintenance request','cancel this repair']},
    {id:'rate_vendor', roles:['resident'], phrases:['rate this vendor','rate the vendor','leave a rating','rate vendor','give a rating']},

    // Vendor job lifecycle
    {id:'vendor_open_jobs', roles:['vendor'], phrases:['show available jobs','show open jobs','open jobs','jobs available','show jobs on board']},
    {id:'vendor_my_jobs', roles:['vendor'], phrases:['show my jobs','my jobs','show accepted jobs','my active jobs','active jobs']},
    {id:'vendor_completed_jobs', roles:['vendor'], phrases:['show completed jobs','completed jobs','my completed work']},
    {id:'vendor_in_progress_jobs', roles:['vendor'], phrases:['show jobs in progress','in progress jobs','jobs in progress']},
    {id:'vendor_accept_job', roles:['vendor'], phrases:['accept this job','accept work order','take this job','accept the job']},
    {id:'vendor_start_job', roles:['vendor'], phrases:['start this job','start work','mark this job in progress','begin this job']},
    {id:'vendor_complete_job', roles:['vendor'], phrases:['complete this job','mark this job completed','finish this job','mark work complete']},
    {id:'vendor_withdraw_job', roles:['vendor'], phrases:['withdraw from this job','withdraw this job','cancel my job','leave this job']},
    {id:'submit_quote', roles:['vendor'], phrases:['submit a quote','give a quotation','submit quotation','quote for this job','submit my quotation']},
    {id:'my_quotes', roles:['vendor'], phrases:['show my quotations','show my quotes','my quotations','my quotes','quote history']},
    {id:'withdraw_quote', roles:['vendor'], phrases:['withdraw my quotation','withdraw my quote','cancel my quote','withdraw quote']},
    {id:'pay_vendor', roles:['resident','admin'], phrases:['pay vendor','pay this vendor','pay for this work order','make vendor payment']},

    // Quotation viewing/comparison
    {id:'show_quotes', roles:['resident','admin'], phrases:['show quotations','show quotes','view vendor quotes','what quotes did i receive','show quotes for this request','show quotations for this work order','compare quotes','compare quotations']},
    {id:'lowest_quote', roles:['resident','admin'], phrases:['which quote is lowest','whats the cheapest quote','what is the cheapest quote','lowest quote','cheapest quote','lowest quotation']},
    {id:'read_quotes', roles:['resident','admin'], phrases:['read the quotations','read the quotes','how much did each vendor quote','tell me the quotes']},

    // Admin CRUD/navigation
    {id:'new_notice', roles:['admin'], phrases:['post notice','create notice','new notice','publish notice','post announcement','create announcement']},
    {id:'delete_notice', roles:['admin'], phrases:['delete this notice','remove this notice','delete notice']},
    {id:'add_resident', roles:['admin'], phrases:['add resident','create resident','new resident']},
    {id:'resident_detail', roles:['admin'], phrases:['open resident','show resident details','view resident','resident details']},
    {id:'add_vendor', roles:['admin'], phrases:['add vendor','create vendor','new vendor']},
    {id:'new_expense', roles:['admin'], phrases:['add expense','create expense','new expense','record expense']},
    {id:'maintenance_bill', roles:['admin'], phrases:['create a maintenance bill','create maintenance bill','generate maintenance bill','add maintenance bill','assign maintenance']},
    {id:'admin_payments', roles:['admin'], phrases:['show all payments','show admin payments','all payments','payment records']},
    {id:'admin_bills', roles:['admin'], phrases:['show maintenance bills','all maintenance bills','maintenance billing','billing']},
    {id:'admin_workorder', roles:['admin'], phrases:['post a work order','post work order','create a work order','admin work order']},
    {id:'admin_complaints', roles:['admin'], phrases:['show all complaints','admin complaints','complaint management']},
    {id:'update_complaint', roles:['admin'], phrases:['update complaint status','change complaint status','resolve complaint','close complaint','mark complaint resolved']},
    {id:'accept_quote', roles:['admin'], phrases:['accept this quotation','accept this quote','choose this vendor quote','accept vendor quote']},
    {id:'reject_quote', roles:['admin'], phrases:['reject this quotation','reject this quote','decline this quote','decline quotation']},
    {id:'admin_resident_payments', roles:['admin'], phrases:['show resident payments','show this residents payments','resident payment history']},
    {id:'reports', roles:['admin'], phrases:['open reports','show reports','reports','financial report','operational report']},
    {id:'audit_log', roles:['admin'], phrases:['show audit log','open audit log','audit activity','audit history']},
    {id:'activity', roles:['admin'], phrases:['show recent activity','recent activity','what happened recently','system activity']},
    {id:'export_residents', roles:['admin'], phrases:['export residents','export residents to excel','export residents to csv']},
    {id:'export_vendors', roles:['admin'], phrases:['export vendors','export vendors to excel','export vendors to csv']},
    {id:'export_payments', roles:['admin'], phrases:['export payments','export payments to excel','export payments to csv']},
    {id:'export_bills', roles:['admin'], phrases:['export maintenance bills','export bills','export maintenance bills to excel','export bills to csv']},
    {id:'export_expenses', roles:['admin'], phrases:['export expenses','export expenses to excel','export expenses to csv']},
    {id:'export_complaints', roles:['admin'], phrases:['export complaints','export complaints to excel','export complaints to csv']},
    {id:'export_workorders', roles:['admin'], phrases:['export work orders','export work orders to excel','export work orders to csv']},
    {id:'export_notices', roles:['admin'], phrases:['export notices','export notices to excel','export notices to csv']},
    {id:'export_invoices', roles:['admin'], phrases:['export invoices','export invoices to excel','export invoices to csv']},

    // Global controls
    {id:'logout', phrases:['log out','logout','sign out','exit account','leave account']},
    {id:'help', phrases:['help','what can you do','voice help','commands','what can i say']},
    {id:'start_listening', phrases:['start listening','begin listening','listen to me','voice on']},
    {id:'stop_listening', phrases:['stop listening','stop voice','voice off','turn off voice','pause listening']},
    {id:'close', phrases:['close','close this','close window','close modal','dismiss']},
    {id:'cancel', phrases:['cancel','cancel that','never mind','nevermind','forget that']},
    {id:'refresh', phrases:['refresh','refresh page','reload','reload page']},
    {id:'back', phrases:['go back','back','previous page']},
    {id:'scroll_down', phrases:['scroll down','go down']},
    {id:'scroll_up', phrases:['scroll up','go up']},
    {id:'top', phrases:['go to the top','scroll to top','top of page']},
    {id:'bottom', phrases:['go to the bottom','scroll to bottom','bottom of page']}
  ];

  function normalize(text) {
    return String(text || '').normalize('NFKC').toLowerCase()
      .replace(/[“”‘’]/g, '"')
      .replace(/[^\p{L}\p{N}\s₹$]/gu, ' ')
      .replace(/\s+/g, ' ').trim();
  }

  const commandIndex = new Map();
  for (const cmd of COMMANDS) for (const phrase of cmd.phrases) {
    const key = normalize(phrase);
    const bucket = commandIndex.get(key) || [];
    bucket.push(cmd);
    commandIndex.set(key, bucket);
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
    for(const x of pw){
      if(tw.some(y=>y===x || (x.length>=5 && y.length>=5 && distance(x,y)<=Math.max(1,Math.floor(Math.min(x.length,y.length)*0.2))))) matched++;
    }
    return matched ? 50 + 35*(matched/pw.length) : 0;
  }

  function currentRole(){ return (global.state && global.state.role) || (global.state && global.state.user && global.state.user.role) || null; }
  function allowed(cmd){ return !cmd.roles || cmd.roles.includes(currentRole()); }

  function matchCommand(transcript) {
    const normalized=normalize(transcript);
    const exact=commandIndex.get(normalized);
    if(exact){ const c=exact.find(allowed); if(c)return c; }

    let best=null,bestScore=0;
    for(const cmd of COMMANDS){
      if(!allowed(cmd))continue;
      for(const phrase of cmd.phrases){
        const s=scorePhrase(transcript,phrase);
        if(s>bestScore){bestScore=s;best=cmd;}
      }
    }
    for(const [page,aliases] of Object.entries(PAGE_ALIASES)){
      const s=Math.max(...aliases.map(a=>scorePhrase(normalized,a)));
      if(s>bestScore && s>=70){best={id:page,phrases:aliases};bestScore=s;}
    }
    return bestScore>=58?best:null;
  }

  function pageGo(page){ if(typeof global.go==='function'){global.go(page);return true;} return false; }

  function speak(text){
    if(!global.speechSynthesis||!text)return;
    const lang=(global.i18n&&global.i18n.SPEECH_LOCALE&&global.i18n.SPEECH_LOCALE[global.i18n.getLanguage()])||'en-IN';
    const u=new SpeechSynthesisUtterance(text);u.lang=lang;global.speechSynthesis.cancel();global.speechSynthesis.speak(u);
  }
  function notify(text){if(typeof global.toast==='function')global.toast(text);speak(text);}

  function contextId(transcript){
    const m=normalize(transcript).match(/\b(?:work order|request|job|quote|quotation|complaint|notice|resident|vendor|payment|receipt|notification)\s*(?:number|no|id)?\s*#?\s*(\d+)\b/i);
    return m?Number(m[1]):null;
  }

  function contextPair(transcript){
    const t=normalize(transcript);
    const w=t.match(/\b(?:work order|request|job)\s*(?:number|no|id)?\s*#?\s*(\d+)\b/);
    const q=t.match(/\b(?:quote|quotation)\s*(?:number|no|id)?\s*#?\s*(\d+)\b/);
    return w&&q?{wid:Number(w[1]),qid:Number(q[1])}:null;
  }

  function complaintStatus(transcript){
    const t=normalize(transcript);
    if(/\b(in progress|in_progress)\b/.test(t))return 'in_progress';
    if(/\bresolved\b/.test(t))return 'resolved';
    if(/\bclosed\b/.test(t))return 'closed';
    if(/\bopen\b/.test(t))return 'open';
    return null;
  }

  function clickButtonByText(patterns, preferredPage){
    if(preferredPage && global.state && global.state.page!==preferredPage){
      pageGo(preferredPage);
      setTimeout(()=>clickButtonByText(patterns,preferredPage),450); return true;
    }
    const els=[...document.querySelectorAll('button:not([disabled]), a, [role="button"]')];
    const candidates=els.map(el=>({el,text:normalize(el.innerText||el.getAttribute('aria-label')||el.title||'')}))
      .filter(x=>x.text&&patterns.some(p=>scorePhrase(x.text,p)>=72));
    if(!candidates.length)return false;
    candidates.sort((a,b)=>b.text.length-a.text.length);candidates[0].el.click();return true;
  }

  async function dashboardData(){try{return await global.api('/dashboard',{cacheTtl:5000});}catch{return null;}}
  async function readDues(){
    const d=await dashboardData();
    if(!d){notify('I could not read your dues right now.');return true;}
    notify(`${global.i18n?global.i18n.t('pending'):'Pending'}: ₹${Number(d.due||0).toLocaleString('en-IN')}`);return true;
  }

  function confirmAnd(action,message){
    if(typeof global.confirm!=='function'){action();return;}
    if(global.confirm(message))action();
  }

  function visibleQuoteSummary(){
    const cache=global.state&&global.state.quoteCache;
    const page=global.state&&global.state.page;
    if(!cache||page!=='workorders')return null;
    const ids=Object.keys(cache);
    const all=ids.flatMap(id=>Array.isArray(cache[id])?cache[id]:[]);
    if(!all.length)return null;
    const valid=all.filter(q=>Number(q.amount)>0);
    return {count:all.length,lowest:valid.length?Math.min(...valid.map(q=>Number(q.amount))):null};
  }

  function execute(cmd, transcript){
    if(!cmd||!allowed(cmd)||commandBusy)return false;
    const t=normalize(transcript), id=contextId(transcript);
    commandBusy=true;
    const finish=()=>{commandBusy=false;};
    try{
      switch(cmd.id){
        case 'start_listening': startListening(); return true;
        case 'stop_listening': stopListening(); return true;
        case 'help': notify('You can navigate pages, read dues, manage requests and quotations, create records, update jobs, export admin data, and control notifications by voice. Say stop listening to pause continuous voice.'); return true;
        case 'logout': confirmAnd(()=>global.logout&&global.logout(),'Log out of NestLedger?'); return true;
        case 'close': case 'cancel': document.querySelector('.modal-backdrop')?.remove(); return true;
        case 'refresh': loadPageSafe(); return true;
        case 'back': history.back(); return true;
        case 'scroll_down': scrollBy({top:window.innerHeight*.8,behavior:'smooth'}); return true;
        case 'scroll_up': scrollBy({top:-window.innerHeight*.8,behavior:'smooth'}); return true;
        case 'top': scrollTo({top:0,behavior:'smooth'}); return true;
        case 'bottom': scrollTo({top:document.body.scrollHeight,behavior:'smooth'}); return true;
        case 'read_dues': return readDues();
        case 'payment_history': pageGo('payments'); return true;
        case 'unpaid_bills': pageGo('payments'); notify('Opening Payments. I will not start a payment automatically; choose the bill you want to pay.'); return true;
        case 'paid_bills': pageGo('payments'); return true;
        case 'latest_receipt': pageGo('receipts'); setTimeout(()=>clickButtonByText(['download receipt','receipt','download'],'receipts'),450); return true;
        case 'pay_bill': confirmAnd(()=>{pageGo('payments');setTimeout(()=>{if(!clickButtonByText(['pay maintenance','pay bill','pay ₹','pay']))notify('Open Payments and choose the bill you want to pay.');},450)},'Open the payment screen and prepare your maintenance payment?'); return true;
        case 'new_complaint': pageGo('complaints'); setTimeout(()=>global.complaintModal&&global.complaintModal(),450); return true;
        case 'new_workorder': pageGo('workorders'); setTimeout(()=>global.workOrderModal&&global.workOrderModal(),450); return true;
        case 'cancel_workorder': if(id&&global.cancelWorkOrder){global.cancelWorkOrder(id);}else notify('Please say the work order number you want to cancel.'); return true;
        case 'rate_vendor': if(id&&global.rateVendorModal){global.rateVendorModal(id);}else notify('Please open the completed work order you want to rate.'); return true;
        case 'show_quotes': if(id&&global.quotesModal){global.quotesModal(id);}else if(global.quotesModal){const b=visibleQuoteSummary();if(b)notify(`${b.count} quotations found. Lowest quote is ₹${b.lowest?.toLocaleString('en-IN')||'unavailable'}.`);else notify('Open a work order and say show quotes.');} return true;
        case 'lowest_quote': {const b=visibleQuoteSummary();if(b&&b.lowest!==null)notify(`The lowest visible quotation is ₹${b.lowest.toLocaleString('en-IN')}.`);else notify('Open the quotation comparison first.');return true;}
        case 'read_quotes': {const b=visibleQuoteSummary();if(b)notify(`${b.count} quotations are available. The lowest is ₹${b.lowest?.toLocaleString('en-IN')||'unavailable'}.`);else notify('Open a work order quotation list first.');return true;}
        case 'vendor_open_jobs': pageGo('workorders'); return true;
        case 'vendor_my_jobs': pageGo('workorders'); return true;
        case 'vendor_completed_jobs': pageGo('workorders'); return true;
        case 'vendor_in_progress_jobs': pageGo('workorders'); return true;
        case 'vendor_accept_job': if(id&&global.acceptWorkOrder)confirmAnd(()=>global.acceptWorkOrder(id),`Accept work order ${id}?`);else notify('Please say the work order number to accept.'); return true;
        case 'vendor_start_job': if(id&&global.setWorkOrderStatus)confirmAnd(()=>global.setWorkOrderStatus(id,'in_progress'),`Start work order ${id}?`);else notify('Please say the work order number to start.'); return true;
        case 'vendor_complete_job': if(id&&global.setWorkOrderStatus)confirmAnd(()=>global.setWorkOrderStatus(id,'completed'),`Mark work order ${id} as completed?`);else notify('Please say the work order number to complete.'); return true;
        case 'vendor_withdraw_job': if(id&&global.withdrawWorkOrder)global.withdrawWorkOrder(id);else notify('Please say the work order number to withdraw.'); return true;
        case 'submit_quote': if(id&&global.quoteModal)global.quoteModal(id);else notify('Open or name the work order you want to quote.'); return true;
        case 'my_quotes': pageGo('workorders'); return true;
        case 'withdraw_quote': {const pair=contextPair(transcript);if(pair&&global.withdrawQuote)global.withdrawQuote(pair.wid,pair.qid);else notify('Say the work order number and quotation number, for example: withdraw quote 7 from work order 42.');return true;}
        case 'pay_vendor': if(id&&global.payVendor)confirmAnd(()=>global.payVendor(id),`Prepare payment for the vendor on work order ${id}?`);else notify('Please say the work order number for the vendor payment.'); return true;
        case 'new_notice': pageGo('notices'); setTimeout(()=>global.noticeModal&&global.noticeModal(),450); return true;
        case 'delete_notice': if(id&&global.deleteNotice)confirmAnd(()=>global.deleteNotice(id),'Delete this notice?');else notify('Please say the notice number to delete.'); return true;
        case 'add_resident': pageGo('residents'); setTimeout(()=>global.residentModal&&global.residentModal(),450); return true;
        case 'resident_detail': if(id&&global.residentDetail)global.residentDetail(id);else notify('Please say the resident number.'); return true;
        case 'add_vendor': pageGo('vendors'); setTimeout(()=>global.vendorModal&&global.vendorModal(),450); return true;
        case 'new_expense': pageGo('expenses'); setTimeout(()=>global.expenseModal&&global.expenseModal(),450); return true;
        case 'maintenance_bill': pageGo('payments'); setTimeout(()=>global.maintenanceBillModal&&global.maintenanceBillModal(),450); return true;
        case 'admin_payments': pageGo('payments'); return true;
        case 'admin_bills': pageGo('payments'); return true;
        case 'admin_workorder': pageGo('workorders'); setTimeout(()=>global.workOrderModal&&global.workOrderModal(true),450); return true;
        case 'admin_complaints': pageGo('complaints'); return true;
        case 'update_complaint': {const status=complaintStatus(transcript);if(id&&status&&global.updateComplaintStatus)confirmAnd(()=>global.updateComplaintStatus(id,status),`Set complaint ${id} to ${status.replace('_',' ')}?`);else notify('Say the complaint number and status, for example: resolve complaint 17.');return true;}
        case 'accept_quote': {const pair=contextPair(transcript);if(pair&&global.acceptQuote)global.acceptQuote(pair.wid,pair.qid);else notify('Say the work order number and quotation number, for example: accept quote 7 for work order 42.');return true;}
        case 'reject_quote': {const pair=contextPair(transcript);if(pair&&global.rejectQuote)confirmAnd(()=>global.rejectQuote(pair.wid,pair.qid),`Reject quotation ${pair.qid} for work order ${pair.wid}?`);else notify('Say the work order number and quotation number, for example: reject quote 7 for work order 42.');return true;}
        case 'admin_resident_payments': if(id&&global.residentDetail)global.residentDetail(id);else notify('Please say the resident number.'); return true;
        case 'reports': pageGo('reports'); return true;
        case 'audit_log': notify('Audit log is available through the admin activity area.'); return true;
        case 'activity': pageGo('dashboard'); return true;
        case 'read_notifications': pageGo('dashboard'); setTimeout(()=>{const b=document.querySelector('#bellBtn');if(b)b.click();},300); return true;
        case 'mark_notification_read': {const el=document.querySelector('.notif-item.unread[data-id]');if(el){el.click();}else notify('There are no unread notifications.');return true;}
        case 'mark_all_notifications_read': {const b=document.querySelector('#markAllRead');if(b)b.click();else{const bell=document.querySelector('#bellBtn');if(bell)bell.click();setTimeout(()=>document.querySelector('#markAllRead')?.click(),250);}return true;}
        case 'export_residents': exportSafe('residents',transcript); return true;
        case 'export_vendors': exportSafe('vendors',transcript); return true;
        case 'export_payments': exportSafe('payments',transcript); return true;
        case 'export_bills': exportSafe('maintenance-bills',transcript); return true;
        case 'export_expenses': exportSafe('expenses',transcript); return true;
        case 'export_complaints': exportSafe('complaints',transcript); return true;
        case 'export_workorders': exportSafe('work-orders',transcript); return true;
        case 'export_notices': exportSafe('notices',transcript); return true;
        case 'export_invoices': exportSafe('invoices',transcript); return true;
        default:
          if(PAGE_ALIASES[cmd.id]){pageGo(cmd.id);return true;}
          if(/\b(click|press|select|open|show)\b/.test(t)&&clickButtonByText([t]))return true;
          return false;
      }
    } finally { setTimeout(finish,250); }
  }

  function loadPageSafe(){ if(typeof global.loadPage==='function')global.loadPage(); else location.reload(); }
  function exportSafe(resource, transcript=''){
    if(typeof global.exportList==='function'){
      const t=normalize(transcript);
      const format=/\bcsv\b/.test(t)?'csv':'xlsx';
      global.exportList(resource,format,global.state&&global.state.page||'dashboard');
      return;
    }
    notify('Export is not available on this screen.');
  }

  function handleTranscript(transcript){
    const text=String(transcript||'').trim();if(!text)return;
    const previousTranscript=lastTranscript;
    lastTranscript=text;
    const now=Date.now();
    // Recognition engines can emit the same final phrase more than once.
    if(normalize(text)===normalize(previousTranscript) && now-lastHandledAt<1200)return;
    const cmd=matchCommand(text);
    if(cmd&&execute(cmd,text)){lastIntent=cmd.id;lastHandledAt=now;return;}
    if(global.NLChatbot&&typeof global.NLChatbot.sendMessage==='function'){
      global.NLChatbot.open&&global.NLChatbot.open();global.NLChatbot.sendMessage(text);
    }else notify(`I heard: ${text}`);
    lastHandledAt=now;
  }

  function updateUI(){
    const listeningText=global.i18n?global.i18n.t('voiceListening'):'Listening…';
    document.querySelectorAll('.voice-mic').forEach(btn=>{
      btn.classList.toggle('listening',listening);btn.setAttribute('aria-pressed',String(listening));
      const label=btn.querySelector('.voice-mic-label');
      if(label)label.textContent=listening?listeningText:(global.i18n?global.i18n.t('voiceTapToSpeak'):'Speak');
      btn.setAttribute('title',listening?'Stop listening':((global.i18n&&global.i18n.t('voiceTapToSpeak'))||'Speak'));
      btn.setAttribute('aria-label',listening?'Stop listening':((global.i18n&&global.i18n.t('voiceTapToSpeak'))||'Speak'));
    });
    const status=document.getElementById('chatbotVoiceStatus');
    if(status){status.hidden=!listening;status.textContent=listeningText;status.setAttribute('aria-live','polite');}
  }

  function scheduleRestart(){
    if(!listening||restarting||!recognition)return;
    restarting=true;clearTimeout(restartTimer);
    restartTimer=setTimeout(()=>{restarting=false;if(!listening)return;try{recognition.start();}catch{}},180);
  }

  function recognitionInstance(){
    if(!SR)return null;if(recognition)return recognition;
    recognition=new SR();
    recognition.continuous=true;
    recognition.interimResults=true;
    recognition.maxAlternatives=5;
    recognition.onstart=()=>{
      listening=true;
      restarting=false;
      updateUI();
      if(typeof global.toast==='function')global.toast((global.i18n&&global.i18n.t('voiceListening'))||'Listening…');
    };
    recognition.onaudiostart=()=>{
      const status=document.getElementById('chatbotVoiceStatus');
      if(status&&listening){status.hidden=false;status.textContent=(global.i18n&&global.i18n.t('voiceListening'))||'Listening…';}
    };
    recognition.onspeechstart=()=>{
      const status=document.getElementById('chatbotVoiceStatus');
      if(status&&listening){status.hidden=false;status.textContent=(global.i18n&&global.i18n.t('voiceUnderstanding'))||'Understanding…';}
    };
    recognition.onresult=e=>{
      let finalText='';
      let interimText='';
      for(let i=e.resultIndex;i<e.results.length;i++){
        const transcript=String(e.results[i][0]?.transcript||'').trim();
        if(e.results[i].isFinal)finalText+=' '+transcript;
        else interimText+=' '+transcript;
      }
      const status=document.getElementById('chatbotVoiceStatus');
      if(status&&listening){
        status.hidden=false;
        status.textContent=finalText.trim() ? ((global.i18n&&global.i18n.t('voiceUnderstanding'))||'Understanding…') : (interimText.trim() ? `Heard: ${interimText.trim()}` : ((global.i18n&&global.i18n.t('voiceListening'))||'Listening…'));
      }
      if(finalText.trim())handleTranscript(finalText.trim());
    };
    recognition.onerror=e=>{
      const err=String(e.error||'').toLowerCase();
      if(err==='aborted')return;
      if(err==='not-allowed'||err==='service-not-allowed'){
        listening=false;restarting=false;updateUI();notify((global.i18n&&global.i18n.t('voiceMicPermission'))||'Microphone access is blocked. Please allow it and try again.');return;
      }
      if(err==='audio-capture'){
        listening=false;restarting=false;updateUI();notify((global.i18n&&global.i18n.t('voiceNoMicrophone'))||'No microphone was found on this device.');return;
      }
      // A network error is a hard failure for the browser speech service.
      // Repeatedly restarting only leaves the UI falsely stuck on “Listening…”.
      if(err==='network'){
        listening=false;restarting=false;updateUI();notify((global.i18n&&global.i18n.t('voiceNetwork'))||'Voice recognition needs an internet connection.');return;
      }
      if(err==='no-speech'){scheduleRestart();return;}
      listening=false;restarting=false;updateUI();notify((global.i18n&&global.i18n.t('voiceTryAgain'))||'Please try again.');
    };
    recognition.onend=()=>{if(listening)scheduleRestart();else{restarting=false;updateUI();}};
    return recognition;
  }

  function stopListening(){
    listening=false;restarting=false;clearTimeout(restartTimer);
    if(recognition){try{recognition.stop();}catch{try{recognition.abort();}catch{}}}
    if(global.speechSynthesis)global.speechSynthesis.cancel();updateUI();
  }

  function startListening(){
    if(!SR){
      notify((global.i18n&&global.i18n.t('voiceUnsupported'))||'Voice recognition is not supported in this browser. Try Chrome or Edge for voice navigation.');
      return false;
    }
    if(listening||restarting)return true;
    const r=recognitionInstance();
    r.lang=(global.i18n&&global.i18n.SPEECH_LOCALE&&global.i18n.SPEECH_LOCALE[global.i18n.getLanguage()])||'en-IN';
    try{
      if(global.speechSynthesis)global.speechSynthesis.cancel();
      // Do not claim “Listening…” until the recognition engine actually fires
      // onstart. This prevents a false listening state when the browser rejects
      // the microphone/service request.
      restarting=false;
      r.start();
      return true;
    }catch(e){
      listening=false;restarting=false;updateUI();
      notify((global.i18n&&global.i18n.t('voiceTryAgain'))||'Please try again.');
      return false;
    }
  }

  function mountInlineMic(container){
    const wrap=typeof container==='string'?document.querySelector(container):container;if(!wrap)return;
    let btn=wrap.querySelector('#chatbotVoiceMic');
    if(!btn){
      btn=document.createElement('button');btn.id='chatbotVoiceMic';btn.type='button';btn.className='voice-mic chatbot-voice-mic';
      btn.innerHTML='<span class="voice-mic-icon"><i data-lucide="mic"></i></span><span class="voice-mic-label"></span>';wrap.appendChild(btn);
      if(global.lucide&&typeof global.lucide.createIcons==='function')global.lucide.createIcons({attrs:{'stroke-width':1.8}});
    }
    btn.onclick=()=>listening?stopListening():startListening();
    btn.setAttribute('aria-label',listening?'Stop listening':((global.i18n&&global.i18n.t('voiceTapToSpeak'))||'Speak'));
    btn.setAttribute('title',listening?'Stop listening':((global.i18n&&global.i18n.t('voiceTapToSpeak'))||'Speak'));
    updateUI();
  }

  function refreshLabel(){
    document.querySelectorAll('.voice-mic').forEach(btn=>{
      const label=btn.querySelector('.voice-mic-label');
      if(label)label.textContent=listening?(global.i18n&&global.i18n.t('voiceListening')||'Listening…'):(global.i18n&&global.i18n.t('voiceTapToSpeak')||'Speak');
      btn.setAttribute('title',listening?'Stop listening':((global.i18n&&global.i18n.t('voiceTapToSpeak'))||'Speak'));
      btn.setAttribute('aria-label',listening?'Stop listening':((global.i18n&&global.i18n.t('voiceTapToSpeak'))||'Speak'));
    });
  }

  function unmountMicButton(){stopListening();recognition=null;document.querySelectorAll('.voice-mic').forEach(x=>x.remove());}

  global.NLVoice={
    mountInlineMic,unmountMicButton,refreshLabel,startListening,stopListening,
    supported:!!SR,lastTranscript:()=>lastTranscript,lastIntent:()=>lastIntent,
    isListening:()=>listening,getCommands:()=>COMMANDS.map(x=>({id:x.id,roles:x.roles||['resident','vendor','admin'],phrases:[...x.phrases]}))
  };
})(window);
