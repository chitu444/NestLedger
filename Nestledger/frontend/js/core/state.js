(function () {
  // Phase 3: authentication is cookie-backed. No JWT or profile is persisted in
  // localStorage. `token` is only an in-memory compatibility/session marker.
  const state = window.NLState = window.NLState || {
    token: null,
    user: null,
    role: 'resident',
    page: 'dashboard',
    version: 0
  };
  state.bump = () => ++state.version;
  state.clearSession = () => {
    state.token = null; state.user = null; state.role = 'resident'; state.page = 'dashboard'; state.bump();
  };
  state.saveSession = (d) => {
    state.token = 'cookie-session'; state.user = d.user; state.role = d.user?.role || 'resident'; state.bump();
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
