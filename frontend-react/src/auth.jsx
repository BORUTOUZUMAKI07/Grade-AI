import React, { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react';

export const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
const AuthCtx = createContext(null);
export const useAuth = () => useContext(AuthCtx);

const fail = async (res) => {
  const data = await res.json().catch(() => null);
  const err = new Error(data?.reason || data?.details?.[0]?.msg || 'Something went wrong. Please try again.');
  err.status = res.status;
  throw err;
};

async function raw(path, { token, body, method } = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: method || (body ? 'POST' : 'GET'),
    credentials: 'include', // sends the httpOnly refresh cookie
    headers: { ...(body ? { 'Content-Type': 'application/json' } : {}), ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) await fail(res);
  return res.status === 204 ? null : res.json();
}

async function rawBlob(path, token) {
  const res = await fetch(`${API_BASE}${path}`, { credentials: 'include', headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!res.ok) await fail(res);
  return res.blob();
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);
  const token = useRef(null); // access token lives in memory only, never in localStorage
  const inflight = useRef(null);

  const apply = (d) => { token.current = d.access_token; setUser(d.user); return d.user; };
  const clear = () => { token.current = null; setUser(null); };
  // One refresh at a time: parallel callers (two tabs of requests, StrictMode) share the same request
  const refresh = () => {
    if (!inflight.current) inflight.current = raw('/auth/refresh', { method: 'POST' }).then(apply).finally(() => { inflight.current = null; });
    return inflight.current;
  };
  const withRetry = async (call) => {
    try { return await call(token.current); } catch (e) {
      if (e.status !== 401) throw e;
      try { await refresh(); } catch { clear(); throw e; }
      return call(token.current);
    }
  };

  useEffect(() => { refresh().catch(() => {}).finally(() => setReady(true)); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const value = useMemo(() => ({
    user,
    ready,
    login: async (email, password) => apply(await raw('/auth/login', { body: { email, password } })),
    register: async (full_name, email, password) => apply(await raw('/auth/register', { body: { full_name, email, password } })),
    logout: async () => { try { await raw('/auth/logout', { method: 'POST' }); } finally { clear(); } },
    api: (path, body, method) => withRetry((t) => raw(path, { token: t, body, method })),
    download: async (path, filename) => {
      const blob = await withRetry((t) => rawBlob(path, t));
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a'); a.href = url; a.download = filename; a.click();
      URL.revokeObjectURL(url);
    },
  }), [user, ready]); // eslint-disable-line react-hooks/exhaustive-deps

  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}
