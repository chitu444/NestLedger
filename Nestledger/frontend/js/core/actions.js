(function(){
  function splitArgs(raw){
    const out=[]; let cur='', quote=null, depth=0;
    for(let i=0;i<raw.length;i++){
      const ch=raw[i];
      if(quote){ cur+=ch; if(ch===quote && raw[i-1]!=='\\') quote=null; continue; }
      if(ch==='"'||ch==="'"){quote=ch;cur+=ch;continue}
      if(ch==='('||ch==='['||ch==='{'){depth++;cur+=ch;continue}
      if(ch===')'||ch===']'||ch==='}'){depth--;cur+=ch;continue}
      if(ch===','&&depth===0){out.push(cur.trim());cur='';continue}
      cur+=ch;
    }
    if(cur.trim()||raw.trim())out.push(cur.trim());
    return out;
  }
  function parseArg(value,event){
    const v=(value||'').trim();
    if(v==='event') return event;
    if(v==='true') return true;
    if(v==='false') return false;
    if((v.startsWith("'")&&v.endsWith("'"))||(v.startsWith('"')&&v.endsWith('"'))) return v.slice(1,-1).replace(/\\([\\"'])/g,'$1');
    if(/^[-+]?\d+(?:\.\d+)?$/.test(v)) return Number(v);
    return v;
  }
  function run(el,event){
    const name=el.dataset.nlAction;
    if(name==='__closeModal'){document.getElementById('modal')?.remove();return;}
    if(name==='__closeResidentDetail'){document.getElementById('residentDetailModal')?.remove();return;}
    if(name==='__closeTempPassword'){document.getElementById('tempPasswordModal')?.remove();if(typeof window.loadPage==='function')window.loadPage();return;}
    const fn=window[name];
    if(typeof fn!=='function') return;
    const args=splitArgs(el.dataset.nlArgs||'').map(x=>parseArg(x,event));
    try { fn(...args); } catch(err) { console.error('NestLedger action failed',name,err); }
  }
  document.addEventListener('click',function(event){
    const el=event.target.closest?.('[data-nl-action]');
    if(!el || el.disabled || el.getAttribute('aria-disabled')==='true') return;
    run(el,event);
  },true);
})();
