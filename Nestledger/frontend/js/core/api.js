(function () {
  const API = '/api';
  const TIMEOUT = 15000;
  const cache = new Map();
  const inflight = new Map();
  const lastMeta = new Map();
  let requestId = 0;

  function cacheKey(path) { return String(path); }
  function invalidate(prefix) {
    for (const key of cache.keys()) if (!prefix || key.startsWith(prefix)) cache.delete(key);
  }
  function clear() { cache.clear(); inflight.clear(); }

  async function request(path, opt = {}) {
    const options = { ...opt, headers: { ...(opt.body ? {'Content-Type':'application/json'} : {}), ...(opt.headers || {}) } };
    const method = String(options.method || 'GET').toUpperCase();
    const isGet = method === 'GET';
    const ttl = options.cacheTtl === undefined ? (isGet ? 1500 : 0) : Number(options.cacheTtl || 0);
    delete options.cacheTtl;
    const key = cacheKey(path);
    if (isGet && ttl > 0) {
      const hit = cache.get(key);
      if (hit && hit.expires > Date.now()) return hit.data;
      if (inflight.has(key)) return inflight.get(key);
    }
    if (window.NLState?.token) options.headers.Authorization = `Bearer ${window.NLState.token}`;
    const id = ++requestId;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), TIMEOUT);
    if (!options.signal) options.signal = controller.signal;

    const run = (async () => {
      try {
        const response = await fetch(API + path, options);
        let data = null;
        try { data = await response.json(); } catch { data = {}; }
        if (response.status === 401) {
          window.NLCore?.onUnauthorized?.();
          throw new Error(window.i18n?.t('requestFailed') || 'Session expired. Please sign in again.');
        }
        if (!response.ok) {
          const message = data?.error?.message || data?.error || data?.message || `Request failed (${response.status})`;
          const error = new Error(message); error.status = response.status; error.code = data?.error?.code; throw error;
        }
        if (isGet) { if (data && data.meta) lastMeta.set(key, data.meta); if (ttl > 0) cache.set(key, {data, expires: Date.now() + ttl}); }
        if (!isGet) invalidate('/');
        return data;
      } finally { clearTimeout(timer); }
    })();
    if (isGet && ttl > 0) {
      inflight.set(key, run);
      try { return await run; } finally { inflight.delete(key); }
    }
    return run;
  }

  async function download(path, opt = {}) {
    const options = { ...opt, headers: { ...(opt.headers || {}) } };
    if (window.NLState?.token) options.headers.Authorization = `Bearer ${window.NLState.token}`;
    const response = await fetch(API + path, options);
    if (response.status === 401) { window.NLCore?.onUnauthorized?.(); throw new Error(window.i18n?.t('requestFailed') || 'Session expired. Please sign in again.'); }
    if (!response.ok) {
      let data = {}; try { data = await response.json(); } catch {}
      throw new Error(data?.error?.message || data?.error || `Download failed (${response.status})`);
    }
    return response;
  }

  window.NLApi = { request, download, invalidate, clear, meta: (p) => lastMeta.get(p) || null, get: (p, ttl=0) => request(p, {cacheTtl:ttl}), id: () => requestId };
})();
