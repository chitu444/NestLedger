function money(v){return `₹${Number(v||0).toLocaleString('en-IN',{maximumFractionDigits:0})}`}
function percent(v){return `${Number(v||0).toFixed(1)}%`}
function barRows(items,total){return items.map(x=>`<div class="bi-bar-row"><span>${esc(x.label)}</span><b>${esc(String(x.value))}</b><i><em class="pct-w-${pctClass(Math.min(100,total?x.value/total*100:0))}"></em></i></div>`).join('')}
function normalizeBI(d){
  const num=(v)=>{const n=Number(v);return Number.isFinite(n)?n:0};
  const monthly=Array.isArray(d?.monthly)?d.monthly.map(x=>({label:String(x?.label||''),collected:num(x?.collected),expenses:num(x?.expenses)})):[];
  const categories=Array.isArray(d?.expense_categories)?d.expense_categories.map(x=>({label:String(x?.label||'Other'),value:num(x?.value)})):[];
  const complaints=Array.isArray(d?.complaints)?d.complaints.map(x=>({label:String(x?.label||''),value:Math.max(0,Math.round(num(x?.value)))})):[];
  const vendors=Array.isArray(d?.vendors)?d.vendors.map(v=>({name:String(v?.name||'Vendor'),service:String(v?.service||'General Services'),rating:v?.rating==null?null:num(v.rating),jobs:Math.max(0,Math.round(num(v?.jobs)))})):[];
  return {collection:num(d?.collection),expenses:num(d?.expenses),pending:num(d?.pending),pending_bills:Math.max(0,Math.round(num(d?.pending_bills))),expense_count:Math.max(0,Math.round(num(d?.expense_count))),collection_rate:num(d?.collection_rate),open_complaints:Math.max(0,Math.round(num(d?.open_complaints))),open_work_orders:Math.max(0,Math.round(num(d?.open_work_orders))),monthly,categories,complaints,vendors,insight:String(d?.insight||'Keep an eye on unresolved issues and overdue collections.')};
}
async function businessIntelligence(c){
  let d;
  try {
    d=await api('/business-intelligence',{cacheTtl:10000});
    if(!d || d.ok===false) throw new Error(d?.error?.message||'Business Intelligence could not be loaded.');
  } catch(e) { c.innerHTML=`<div class="page-title bi-title"><span class="eyebrow">${i18n.t('businessIntelligence')||'Business intelligence'}</span><h2>Community intelligence</h2><p class="muted">The analytics service could not load this time.</p></div><section class="panel"><div class="empty-state"><i data-lucide="triangle-alert"></i><h4>Business Intelligence is temporarily unavailable</h4><p>${esc(e.message||'Please sign in again and retry.')}</p><button class="primary" type="button" data-nl-action="loadPage" data-nl-args=""><i data-lucide="refresh-cw"></i> Retry</button></div></section>`; renderIcons(); return; }
  d=normalizeBI(d);
  const trend=d.monthly;
  const max=Math.max(...trend.map(x=>Math.max(x.collected||0,x.expenses||0)),1);
  const expenseTotal=d.categories.reduce((a,x)=>a+x.value,0)||1;
  c.innerHTML=`<div class="page-title bi-title"><span class="eyebrow">${i18n.t('businessIntelligence')||'Business intelligence'}</span><h2>Community intelligence</h2><p>A quiet decision room for the numbers that matter. Nothing extra on the main dashboard.</p></div>
  <div class="bi-toolbar"><div><span class="bi-live"><i data-lucide="sparkles"></i> Live from NestLedger</span><small>Updated ${new Date().toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit'})}</small></div><button class="secondary" data-nl-action="loadPage" data-nl-args=""><i data-lucide="refresh-cw"></i> Refresh</button></div>
  <div class="bi-kpis">
    <article class="bi-kpi"><span><i data-lucide="wallet-cards"></i> Collected</span><b>${money(d.collection)}</b><small>${percent(d.collection_rate)} collection rate</small></article>
    <article class="bi-kpi"><span><i data-lucide="clock-3"></i> Outstanding</span><b>${money(d.pending)}</b><small>${d.pending_bills} unpaid bills</small></article>
    <article class="bi-kpi"><span><i data-lucide="receipt-text"></i> Expenses</span><b>${money(d.expenses)}</b><small>${d.expense_count} recorded expenses</small></article>
    <article class="bi-kpi"><span><i data-lucide="triangle-alert"></i> Open issues</span><b>${d.open_complaints}</b><small>${d.open_work_orders} active work orders</small></article>
  </div>
  <div class="bi-grid">
    <section class="panel bi-panel"><div class="panel-head"><div><span class="eyebrow">Cash flow</span><h3>Six-month movement</h3></div></div><div class="bi-chart">${trend.map(x=>`<div class="bi-month"><div class="bi-bars"><i title="Collected" class="pct-h-${pctClass(Math.max(5,(x.collected||0)/max*100))}"></i><em title="Expenses" class="pct-h-${pctClass(Math.max(5,(x.expenses||0)/max*100))}"></em></div><b>${esc(x.label)}</b><small>${money(x.collected)}</small></div>`).join('')}</div><div class="bi-legend"><span><i></i> Collected</span><span><em></em> Expenses</span></div></section>
    <section class="panel bi-panel"><div class="panel-head"><div><span class="eyebrow">Spend profile</span><h3>Where money goes</h3></div></div><div class="bi-bars-list">${barRows(d.categories,expenseTotal)||'<div class="empty-state">No expenses recorded yet.</div>'}</div></section>
  </div>
  <div class="bi-grid">
    <section class="panel bi-panel"><div class="panel-head"><div><span class="eyebrow">Operations</span><h3>Issue health</h3></div></div><div class="status-bars bi-status">${(d.complaints).map(x=>`<div><span>${esc(x.label)}</span><b>${x.value}</b><i><em class="pct-w-${pctClass(Math.min(100,d.open_complaints?x.value/Math.max(1,d.open_complaints)*100:0))}"></em></i></div>`).join('')}</div><div class="bi-insight"><i data-lucide="lightbulb"></i><span>${esc(d.insight||'Keep an eye on unresolved issues and overdue collections.')}</span></div></section>
    <section class="panel bi-panel"><div class="panel-head"><div><span class="eyebrow">Vendors</span><h3>Service performance</h3></div><a class="text-link" data-page-jump="vendorperformance">View full list <i data-lucide="arrow-up-right"></i></a></div><div class="bi-vendors">${(d.vendors).slice(0,5).map(v=>`<div class="bi-vendor"><span class="avatar">${esc((v.name||'V')[0].toUpperCase())}</span><div><b>${esc(v.name)}</b><small>${esc(v.service)}</small></div><strong>${v.rating===null?'—':`${v.rating} / 5`}</strong></div>`).join('')||'<div class="empty-state">No vendor performance data yet.</div>'}</div></section>
  </div>`;
  document.querySelectorAll('[data-page-jump]').forEach(x=>x.onclick=()=>{state.page=x.dataset.pageJump;renderShell()});renderIcons()
}
