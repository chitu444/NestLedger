const state=window.NLState;
let pageLoadSeq=0;
let activePageSeq=0;
let activePageController=null;
let lastBackgroundRefreshAt=0;
const actionLocks=new Set();
let toastTimer=null;
const $=s=>document.querySelector(s);
function pctClass(value){return Math.max(0,Math.min(100,Math.round((Number(value)||0)/5)*5));}
const renderIcons=()=>{if(window.lucide&&typeof window.lucide.createIcons==='function')window.lucide.createIcons({attrs:{'stroke-width':1.8}})};
const THEME_KEY='nestledger-theme';
function getTheme(){try{return localStorage.getItem(THEME_KEY)==='dark'?'dark':'light'}catch{return 'light'}}
function applyTheme(theme=getTheme()){const t=theme==='dark'?'dark':'light';document.documentElement.dataset.theme=t;try{localStorage.setItem(THEME_KEY,t)}catch{}return t}
function themeToggleHtml(){const dark=getTheme()==='dark';return `<button type="button" class="theme-toggle" id="themeToggle" aria-label="${dark?'Switch to light mode':'Switch to dark mode'}" title="${dark?'Light mode':'Dark mode'}"><i data-lucide="${dark?'sun':'moon'}"></i></button>`}
function bindThemeToggle(){const b=$('#themeToggle');if(!b)return;b.onclick=()=>{const root=document.documentElement;root.classList.add('theme-transition');const t=applyTheme(getTheme()==='dark'?'light':'dark');b.setAttribute('aria-label',t==='dark'?'Switch to light mode':'Switch to dark mode');b.title=t==='dark'?'Light mode':'Dark mode';b.innerHTML=`<i data-lucide="${t==='dark'?'sun':'moon'}"></i>`;renderIcons();window.clearTimeout(window.__nlThemeTransitionTimer);window.__nlThemeTransitionTimer=window.setTimeout(()=>root.classList.remove('theme-transition'),430)}}
applyTheme();
let lastClientErrorAt=0;
function reportClientError(message, error){
  console.error('[NestLedger]', message, error||'');
  const now=Date.now();
  if(now-lastClientErrorAt<2500)return;
  lastClientErrorAt=now;
  if(document.getElementById('toast')) toast(message);
}
window.addEventListener('error', e=>reportClientError('Something went wrong. Please try again.', e.error||e.message));
window.addEventListener('unhandledrejection', e=>{
  const reason=e.reason;
  if(reason?.code==='REQUEST_TIMEOUT') reportClientError('The request timed out. Please try again.', reason);
  else if(reason?.code==='NETWORK_ERROR') reportClientError('Unable to reach NestLedger. Please check your connection.', reason);
  else reportClientError('Something went wrong. Please try again.', reason);
});
const esc=s=>String(s??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
function userErrorMessage(error){
  const message=String(error?.message||i18n.t('requestFailed')||'Request failed');
  const ref=String(error?.requestId||'').trim();
  return ref?`${message} (Ref: ${ref})`:message;
}
const NAV_BY_ROLE={
  resident:[['dashboard','house','dashboard'],['payments','indian-rupee','payments'],['receipts','receipt-text','receipts'],['workorders','wrench','maintenance'],['complaints','circle-alert','complaints'],['notices','megaphone','notices']],
  vendor:[['dashboard','house','dashboard'],['workorders','check-circle-2','workorders']],
  admin:[['dashboard','house','dashboard'],['residents','users','residents'],['payments','indian-rupee','payments'],['workorders','wrench','workorders'],['complaints','circle-alert','complaints'],['vendors','hammer','vendors'],['vendorperformance','star','vendorPerformance'],['expenses','receipt','expenses'],['reports','chart-no-axes-combined','businessIntelligence'],['notices','megaphone','notices']]
};
const PAGE_NAMES=new Set(['dashboard','payments','receipts','workorders','complaints','notices','profile','residents','vendors','vendorperformance','expenses','reports']);
window.NAV_BY_ROLE=NAV_BY_ROLE;window.PAGE_NAMES=PAGE_NAMES;
function toast(msg){const t=$('#toast');if(!t)return;t.textContent=String(msg||'');t.classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>t.classList.remove('show'),3000)}
async function withActionLock(key, fn){if(actionLocks.has(key))return null;actionLocks.add(key);try{return await fn()}finally{actionLocks.delete(key)}}
async function api(path,opt={}){
  const method=String(opt.method||'GET').toUpperCase();
  const listBases=['/admin/users','/admin/vendors','/admin/expenses','/admin/payments','/admin/maintenance-bills','/bills','/payments','/complaints','/notices','/work-orders','/invoices'];
  if(method==='GET' && listBases.some(x=>path===x)){
    const f=state.listFilters?.[state.page]||{}; const u=new URL(path,location.origin);
    if(state.page==='residents' && path==='/admin/users')u.searchParams.set('role','resident');
    if(f.q)u.searchParams.set('q',f.q); if(f.status)u.searchParams.set('status',f.status);
    u.searchParams.set('page',String(f.page||1)); u.searchParams.set('per_page','20'); path=u.pathname+u.search;
  }
  const requestOptions={...opt};
  if(method==='GET' && window.__NLPageLoadSeq!=null && requestOptions.pageSeq===undefined) requestOptions.pageSeq=window.__NLPageLoadSeq;
  return window.NLApi.request(path,requestOptions)
}

function saveSession(d){window.NLState.saveSession(d)}
async function logout(show=true){try{await api('/auth/logout',{method:'POST',cacheTtl:0})}catch{}window.NLApi.clear();window.NLState.clearSession();if(window.NLVoice?.unmountMicButton)NLVoice.unmountMicButton();if(window.NLChatbot?.close)NLChatbot.close();document.getElementById('chatbotFab')?.remove();document.getElementById('chatbotPanel')?.remove();render();if(show)toast(i18n.t('loggedOut'))}

window.NLCore=window.NLCore||{};window.NLCore.onUnauthorized=()=>logout(false);
function render(){if(!state.token||!state.user)return renderAuth('login');state.role=state.user.role;renderShell()}
function renderAuth(mode='login'){let isLogin=mode==='login';$('#app').innerHTML=`<div class="auth"><section class="auth-art"><div class="brand">${i18n.t('appName')}<span> / community OS</span></div><div class="art-copy"><h1>${i18n.t('heroTitle')}</h1><p>${i18n.t('heroSubtitle')}</p><div class="art-grid"><div class="mini"><b>24/7</b><small>${i18n.t('digitalAccess')}</small></div><div class="mini"><b>₹</b><small>${i18n.t('securePayments')}</small></div></div></div></section><section class="auth-panel"><div class="auth-tools">${themeToggleHtml()}${langSelectHtml()}</div><div class="auth-card">${isLogin?loginForm():registerForm()}</div></section></div>`;const authCard=$('.auth-card');if(!isLogin&&authCard)authCard.classList.add('register-card');bindAuth(mode);bindThemeToggle();renderIcons()}
function roleButtons(selected){return `<div class="role-switch">${['resident','vendor','admin'].map(r=>`<button type="button" class="role-btn ${selected===r?'active':''}" data-role="${r}">${r==='resident'?'<i data-lucide="house"></i> '+i18n.t('resident'):r==='vendor'?'<i data-lucide="wrench"></i> '+i18n.t('vendor'):'<i data-lucide="shield-check"></i> '+i18n.t('admin')}</button>`).join('')}</div>`}
function loginForm(){return `<div class="brand brand-accent">${i18n.t('appName')}</div><h2>${i18n.t('welcomeBack')}</h2><p class="sub">${i18n.t('welcomeBackSub')}</p><div id="authError"></div>${roleButtons('resident')}<form id="loginForm"><div class="field"><label>${i18n.t('email')}</label><input id="email" type="email" required placeholder="you@example.com"></div><div class="field"><label>${i18n.t('password')}</label><input id="password" type="password" required placeholder="••••••••"></div><button type="submit" class="primary">${i18n.t('enterWorkspace')} <i data-lucide="arrow-right"></i></button></form><div class="switch-link"><a id="forgotPassword">Forgot password?</a></div><div class="switch-link">${i18n.t('newHere')} <a id="toRegister">${i18n.t('register')}</a></div>`}
function apartmentPickerHtml(id='apartment'){return `<div class="apartment-picker" data-apartment-picker="${id}"><input type="hidden" id="${id}" value=""><div class="apartment-picker-head"><div><b>Choose your apartment</b><small>Select one available unit</small></div><span class="apartment-selection" id="${id}Selection">None selected</span></div><div class="apartment-legend"><span><i class="available"></i>Available</span><span><i class="selected"></i>Selected</span><span><i class="occupied"></i>Occupied</span></div><div class="apartment-blocks" id="${id}Blocks"></div><div class="apartment-seats" id="${id}Seats"><span class="muted">Loading apartments…</span></div><div class="field-error" id="err-apartment"></div></div>`}
async function initApartmentPicker(id='apartment', initialValue=''){
  const root=document.querySelector(`[data-apartment-picker="${id}"]`); if(!root)return;
  const blocks=root.querySelector(`#${id}Blocks`), seats=root.querySelector(`#${id}Seats`), hidden=root.querySelector(`#${id}`), selection=root.querySelector(`#${id}Selection`); if(!blocks||!seats||!hidden)return;
  try{
    const d=await api('/auth/apartments');
    const items=(Array.isArray(d.apartments)?d.apartments:[]).filter(x=>/^[A-M]-[1-7]$/.test(String(x.code||'').trim().toUpperCase()));
    initialValue=String(initialValue||'').trim().toUpperCase(); if(hidden && !hidden.value)hidden.value=initialValue; const byBlock={}; items.forEach(x=>{const [block,unit]=String(x.code||'').split('-');(byBlock[block]??=[]).push(x)});
    const letters=Object.keys(byBlock).sort();
    blocks.innerHTML=letters.map((letter,i)=>`<button type="button" class="apartment-block-btn ${i===0?'active':''}" data-block="${letter}">${letter}</button>`).join('');
    const renderBlock=letter=>{seats.innerHTML=(byBlock[letter]||[]).map(x=>`<button type="button" class="apartment-seat ${x.occupied?'occupied':''}" data-code="${esc(x.code)}" ${x.occupied?'disabled aria-disabled="true"':''}><strong>${esc(x.code)}</strong><small>${x.occupied?'Occupied':'Available'}</small></button>`).join(''); seats.querySelectorAll('.apartment-seat:not(.occupied)').forEach(btn=>btn.onclick=()=>{hidden.value=btn.dataset.code;selection.textContent=btn.dataset.code;seats.querySelectorAll('.apartment-seat').forEach(x=>x.classList.toggle('selected',x===btn));});};
    blocks.querySelectorAll('.apartment-block-btn').forEach(btn=>btn.onclick=()=>{blocks.querySelectorAll('.apartment-block-btn').forEach(x=>x.classList.toggle('active',x===btn));renderBlock(btn.dataset.block)});
    const initialBlock=initialValue.includes('-')?initialValue.split('-')[0]:letters[0]||'A'; blocks.querySelectorAll('.apartment-block-btn').forEach(btn=>btn.classList.toggle('active',btn.dataset.block===initialBlock)); renderBlock(initialBlock); const initialSeat=seats.querySelector(`[data-code=\"${initialValue}\"]`); if(initialSeat){initialSeat.classList.add('selected'); if(selection)selection.textContent=initialValue}
  }catch(e){seats.innerHTML=`<div class="error">Unable to load apartment availability. Please refresh and try again.</div>`}
}
function registerForm(){return `<div class="brand brand-accent">${i18n.t('appName')}</div><h2>${i18n.t('createAccount')}</h2><p class="sub">${i18n.t('joinCommunitySub')}</p><div id="authError"></div><div class="role-switch"><button type="button" class="role-btn active"><i data-lucide="house"></i> ${i18n.t('resident')}</button></div><form id="registerForm" novalidate><div class="field"><label>${i18n.t('name')}</label><input id="name" required placeholder="${i18n.t('name')}"><div class="field-error" id="err-name"></div></div><div class="grid2"><div class="field"><label>${i18n.t('email')}</label><input id="email" type="email" required placeholder="you@example.com"><div class="field-error" id="err-email"></div></div><div class="field"><label>${i18n.t('phone')}</label><input id="phone" placeholder="9876543210"><div class="field-error" id="err-phone"></div></div></div><div class="field"><label>${i18n.t('apartment')}</label>${apartmentPickerHtml('apartment')}</div><div class="field"><label>${i18n.t('password')}</label><input id="password" type="password" minlength="8" required placeholder="••••••••"><div class="field-error" id="err-password"></div></div><button type="submit" class="primary">${i18n.t('register')} <i data-lucide="arrow-right"></i></button></form><div class="switch-link">${i18n.t('alreadyRegistered')} <a id="toLogin">${i18n.t('signIn')}</a></div>`}
function fieldError(id,msg){const el=document.getElementById('err-'+id);if(el)el.textContent=msg||''}
function clearFieldErrors(){document.querySelectorAll('.field-error').forEach(el=>el.textContent='')}
function validEmail(v){return /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v)}
function validPhone(v){return !v || /^[6-9][0-9]{9}$/.test(v.replace(/\D/g,'').slice(-10))}
let selectedRole='resident';
function bindAuth(mode){selectedRole='resident';document.querySelectorAll('.role-btn[data-role]').forEach(b=>b.onclick=()=>{selectedRole=b.dataset.role;document.querySelectorAll('.role-btn[data-role]').forEach(x=>x.classList.toggle('active',x===b));});if($('#toRegister'))$('#toRegister').onclick=()=>renderAuth('register');if($('#toLogin'))$('#toLogin').onclick=()=>renderAuth('login');if($('#forgotPassword'))$('#forgotPassword').onclick=forgotPasswordModal;if(mode==='login')$('#loginForm').onsubmit=doLogin;else {$('#registerForm').onsubmit=doRegister;initApartmentPicker('apartment')}if($('#langSelect'))$('#langSelect').onchange=e=>{i18n.setLanguage(e.target.value);renderAuth(mode)}}
function forgotPasswordModal(){document.body.insertAdjacentHTML('beforeend',`<div class="modal-backdrop" id="modal"><div class="modal"><button class="close" data-nl-action="__closeModal">×</button><h3>Reset resident password</h3><p class="muted">Use the temporary password provided when your resident account was created.</p><form id="forgotForm"><div class="field"><label>Email</label><input id="fpEmail" type="email" required></div><div class="field"><label>Temporary password</label><input id="fpCurrent" type="password" required></div><div class="field"><label>New password</label><input id="fpNew" type="password" minlength="8" required></div><button type="submit" class="primary">Change password</button></form></div></div>`);$('#forgotForm').onsubmit=async e=>{e.preventDefault();try{const d=await api('/auth/forgot-password',{method:'POST',body:JSON.stringify({email:$('#fpEmail').value,current_password:$('#fpCurrent').value,new_password:$('#fpNew').value})});$('#modal').remove();toast(d.message)}catch(x){toast(userErrorMessage(x))}}}
async function doLogin(e){e.preventDefault();const err=$('#authError');err.innerHTML='';const form=e.currentTarget,button=form.querySelector('button[type=submit]');if(form.dataset.submitting==='1')return;form.dataset.submitting='1';if(button){button.disabled=true;button.dataset.originalText=button.textContent;button.textContent='Signing in...'}try{const d=await api('/auth/login',{method:'POST',body:JSON.stringify({email:$('#email').value,password:$('#password').value,role:selectedRole})});saveSession(d);render();toast(i18n.t('welcomeToApp'));}catch(x){form.dataset.submitting='';if(button){button.disabled=false;button.textContent=button.dataset.originalText||button.textContent}err.innerHTML=`<div class="error">${esc(x.message)}</div>`}}
async function doRegister(e){e.preventDefault();const err=$('#authError');const form=e.currentTarget,button=form.querySelector('button[type=submit]');if(form.dataset.submitting==='1')return;form.dataset.submitting='1';if(button){button.disabled=true;button.dataset.originalText=button.textContent;button.textContent='Creating account...'}err.innerHTML='';clearFieldErrors();let ok=true;
    if(!$('#name').value.trim()){fieldError('name',i18n.t('requiredField'));ok=false}
    if(!validEmail($('#email').value.trim())){fieldError('email',i18n.t('invalidEmail'));ok=false}
    if(!validPhone($('#phone').value.trim())){fieldError('phone',i18n.t('invalidPhone'));ok=false}
    if(!$('#apartment').value){fieldError('apartment','Please select an available apartment.');ok=false}
    if($('#password').value.length<8){fieldError('password',i18n.t('weakPassword'));ok=false}
    if(!ok){form.dataset.submitting='';if(button){button.disabled=false;button.textContent=button.dataset.originalText||button.textContent}return;}
    try{const d=await api('/auth/register',{method:'POST',body:JSON.stringify({name:$('#name').value,email:$('#email').value,phone:$('#phone').value,apartment:$('#apartment').value,password:$('#password').value,role:'resident'})});toast(d.message);renderAuth('login');}catch(x){form.dataset.submitting='';if(button){button.disabled=false;button.textContent=button.dataset.originalText||button.textContent}err.innerHTML=`<div class="error">${esc(x.message)}</div>`}}
