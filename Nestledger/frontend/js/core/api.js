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
  function clear() { cache.clear(); inflight.clear(); lastMeta.clear(); }

  async function request(path, opt = {}) {
    const options = { ...opt, headers: { ...(opt.body ? {'Content-Type':'application/json'} : {}), ...(opt.headers || {}) } };
    const method = String(options.method || 'GET').toUpperCase();
    const isGet = method === 'GET';
    const ttl = options.cacheTtl === undefined ? (isGet ? 30000 : 0) : Number(options.cacheTtl || 0);
    delete options.cacheTtl;
    const guardPageSeq = options.pageSeq;
    delete options.pageSeq;
    const key = cacheKey(path);
    const basePath = String(path).split('?')[0];
    if (isGet && ttl > 0) {
      const hit = cache.get(key);
      if (hit && hit.expires > Date.now()) return hit.data;
      if (inflight.has(key)) return inflight.get(key);
    }
    if (window.NLState?.token) options.headers.Authorization = `Bearer ${window.NLState.token}`;
    const id = ++requestId;
    const controller = new AbortController();
    let timedOut = false;
    const timer = setTimeout(() => { timedOut = true; controller.abort(); }, TIMEOUT);
    if (options.signal) {
      if (options.signal.aborted) controller.abort();
      else options.signal.addEventListener('abort', () => controller.abort(), { once: true });
    }
    options.signal = controller.signal;

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
        if (isGet && guardPageSeq != null && window.__NLPageLoadSeq != null && guardPageSeq !== window.__NLPageLoadSeq) {
          // A stale navigation response is intentionally ignored by the page
          // loader. Do not turn it into a misleading timeout/network error.
          const staleError = new DOMException('Stale page request', 'AbortError');
          staleError.code = 'STALE_PAGE_REQUEST';
          throw staleError;
        }
        if (isGet) { if (data && data.meta) { lastMeta.set(key, data.meta); lastMeta.set(basePath, data.meta); } if (ttl > 0) cache.set(key, {data, expires: Date.now() + ttl}); }
        if (!isGet) invalidate('/');
        return data;
      } catch (error) {
        if (error?.name === 'AbortError') {
          if (error?.code === 'STALE_PAGE_REQUEST' || (isGet && guardPageSeq != null && guardPageSeq !== window.__NLPageLoadSeq)) {
            throw error;
          }
          const timeoutError = new Error(timedOut
            ? 'The request timed out. Please check your connection and try again.'
            : 'The request was cancelled. Please try again.');
          timeoutError.code = timedOut ? 'REQUEST_TIMEOUT' : 'REQUEST_ABORTED';
          throw timeoutError;
        }
        if (error instanceof TypeError) {
          const networkError = new Error('Unable to reach NestLedger. Please check your internet connection and try again.');
          networkError.code = 'NETWORK_ERROR';
          throw networkError;
        }
        throw error;
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
    const controller = new AbortController();
    let timedOut = false;
    const timer = setTimeout(() => { timedOut = true; controller.abort(); }, TIMEOUT);
    if (options.signal) {
      if (options.signal.aborted) controller.abort();
      else options.signal.addEventListener('abort', () => controller.abort(), { once: true });
    }
    options.signal = controller.signal;
    try {
      const response = await fetch(API + path, options);
      if (response.status === 401) { window.NLCore?.onUnauthorized?.(); throw new Error(window.i18n?.t('requestFailed') || 'Session expired. Please sign in again.'); }
      if (!response.ok) {
        let data = {}; try { data = await response.json(); } catch {}
        const error = new Error(data?.error?.message || data?.error || `Download failed (${response.status})`);
        error.status = response.status; error.code = data?.error?.code; throw error;
      }
      return response;
    } catch (error) {
      if (error?.name === 'AbortError') {
        const timeoutError = new Error(timedOut ? 'The download timed out. Please try again.' : 'The download was cancelled. Please try again.');
        timeoutError.code = timedOut ? 'REQUEST_TIMEOUT' : 'REQUEST_ABORTED'; throw timeoutError;
      }
      if (error instanceof TypeError) {
        const networkError = new Error('Unable to reach NestLedger. Please check your internet connection and try again.');
        networkError.code = 'NETWORK_ERROR'; throw networkError;
      }
      throw error;
    } finally { clearTimeout(timer); }
  }

  async function prefetch(paths){
    const queue=[...new Set(paths||[])];
    let cursor=0;
    async function worker(){
      while(cursor<queue.length){
        const path=queue[cursor++];
        try{await request(path,{cacheTtl:15000})}catch{}
      }
    }
    await Promise.all([worker(),worker()]);
  }

  window.NLApi = { request, download, invalidate, clear, meta: (p) => lastMeta.get(p) || null, get: (p, ttl=0) => request(p, {cacheTtl:ttl}), prefetch, id: () => requestId };
})();
