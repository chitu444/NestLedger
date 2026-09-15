(function () {
  function readUser() {
    try { return JSON.parse(localStorage.getItem('nestledgerUser') || 'null'); }
    catch { localStorage.removeItem('nestledgerUser'); return null; }
  }
  const state = window.NLState = window.NLState || {
    token: (()=>{try{return localStorage.getItem('nestledgerToken')}catch{return null}})(),
    user: readUser(),
    role: 'resident',
    page: 'dashboard',
    version: 0
  };
  state.role = state.user?.role || 'resident';
  state.bump = () => ++state.version;
  state.clearSession = () => {
    try { localStorage.removeItem('nestledgerToken'); localStorage.removeItem('nestledgerUser'); } catch {}
    state.token = null; state.user = null; state.role = 'resident'; state.page = 'dashboard'; state.bump();
  };
  state.saveSession = (d) => {
    state.token = d.token; state.user = d.user; state.role = d.user?.role || 'resident'; state.bump();
    try { localStorage.setItem('nestledgerToken', d.token); localStorage.setItem('nestledgerUser', JSON.stringify(d.user)); } catch {}
  };
  state.can = (permission) => {
    const permissions = {
      resident: new Set(['dashboard.view','payments.view','payments.pay','receipts.view','workorders.view','workorders.create','complaints.view','complaints.create','notices.view','profile.view','profile.edit']),
      vendor: new Set(['dashboard.view','workorders.view','workorders.accept','workorders.update','quotes.manage','profile.view','profile.edit']),
      admin: new Set(['*'])
    };
    return permissions[state.role]?.has('*') || permissions[state.role]?.has(permission) || false;
  };
})();
