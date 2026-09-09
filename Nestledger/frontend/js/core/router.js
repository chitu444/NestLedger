(function () {
  const aliases = { reports: 'reports', 'business-intelligence': 'reports' };
  const pathFor = p => p === 'dashboard' ? '/' : (p === 'reports' ? '/business-intelligence' : `/${p}`);
  function normalize(path) {
    const clean = (path || '/').replace(/^\/+|\/+$/g, '') || 'dashboard';
    return aliases[clean] || clean;
  }
  function canVisit(page) {
    if (page === 'profile') return true;
    const nav = window.NAV_BY_ROLE?.[window.NLState?.role] || [];
    return nav.some(item => item[0] === page);
  }
  function navigate(page, replace=false) {
    const target = normalize(page);
    if (!window.PAGE_NAMES?.has(target) || !canVisit(target)) return false;
    window.NLState.page = target;
    window.NLState.bump();
    const url = pathFor(target);
    if (window.location.pathname !== url) history[replace ? 'replaceState' : 'pushState']({page:target}, '', url);
    if (typeof window.updateNavActive === 'function') window.updateNavActive();
    if (typeof window.loadPage === 'function') window.loadPage();
    return true;
  }
  function syncFromUrl() {
    const page = normalize(window.location.pathname);
    if (window.PAGE_NAMES?.has(page) && canVisit(page)) window.NLState.page = page;
    else if (window.PAGE_NAMES?.has(page) && !canVisit(page)) window.NLState.page = 'dashboard';
  }
  window.NLRouter = { navigate, syncFromUrl, pathFor };
})();
