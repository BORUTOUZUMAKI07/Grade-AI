import React from 'react';
import { Link, NavLink } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { Brain, ChevronLeft, ChevronRight } from 'lucide-react';
import { useAuth } from '../auth.jsx';

export const glass = 'glass';
export const inputCls = 'w-full rounded-xl border border-white/10 bg-black/40 px-4 py-2.5 text-sm text-white outline-none transition placeholder:text-neutral-600 focus:border-yellow-400/70 focus:ring-4 focus:ring-yellow-400/10';
export const btnCls = 'inline-flex items-center justify-center gap-2 rounded-full bg-white/5 px-4 py-2 text-sm text-neutral-200 transition hover:bg-white/10 disabled:opacity-50';
export const btnPrimary = 'inline-flex items-center justify-center gap-2 rounded-full bg-yellow-400 px-5 py-2 text-sm font-bold text-black transition hover:bg-yellow-300 disabled:opacity-50';

export function Pager({ page, pages, total, onPage }) {
  return (
    <div className="mt-4 flex items-center justify-between text-xs text-neutral-500">
      <span>{total} total · page {page} of {pages}</span>
      <div className="flex gap-2">
        <button className={btnCls} disabled={page <= 1} onClick={() => onPage(page - 1)} aria-label="Previous page"><ChevronLeft size={14} /></button>
        <button className={btnCls} disabled={page >= pages} onClick={() => onPage(page + 1)} aria-label="Next page"><ChevronRight size={14} /></button>
      </div>
    </div>
  );
}

export const ResultBadge = ({ result }) => result
  ? <span className="rounded-full bg-white/5 px-3 py-1 text-xs font-semibold" style={{ color: result === 'Pass' ? 'var(--pass)' : 'var(--fail)' }}>{result}</span>
  : <span className="text-xs text-neutral-600">Not checked</span>;

export default function Shell({ title, subtitle, actions, children }) {
  const { user, logout } = useAuth();
  const staff = user.role === 'teacher' || user.role === 'admin';
  const link = ({ isActive }) => `rounded-full px-4 py-2 text-sm transition ${isActive ? 'bg-yellow-400 font-semibold text-black' : 'text-neutral-400 hover:bg-white/5 hover:text-white'}`;
  return (
    <div className="min-h-screen bg-[var(--bg)] text-neutral-300">
      <Toaster position="top-right" toastOptions={{ style: { background: 'rgba(15,15,15,0.9)', color: '#eee', border: '1px solid rgba(255,255,255,0.12)' } }} />
      <div className="mx-auto max-w-7xl px-4 py-6 lg:px-8">
        <nav className="glass sticky top-4 z-30 mb-10 flex items-center justify-between gap-4 rounded-full px-5 py-3">
          <Link to="/" className="flex items-center gap-3">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-yellow-300 to-yellow-600 text-black"><Brain size={18} /></span>
            <span className="text-lg font-extrabold tracking-tight text-white">Grade<span className="text-yellow-400">AI</span></span>
          </Link>
          <div className="flex items-center gap-1">
            <NavLink to="/" end className={link}>Dashboard</NavLink>
            {staff && <NavLink to="/students" className={link}>Students</NavLink>}
            {staff && <NavLink to="/batch" className={link}>Batch</NavLink>}
            {user.role === 'admin' && <NavLink to="/admin" className={link}>Admin</NavLink>}
          </div>
          <div className="flex items-center gap-3">
            <span className="hidden text-xs text-neutral-400 lg:inline">{user.full_name}</span>
            <button onClick={logout} className="rounded-full px-3 py-2 text-sm text-neutral-400 transition hover:bg-white/5 hover:text-white">Sign out</button>
          </div>
        </nav>
        <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-white">{title}</h1>
            {subtitle && <p className="mt-1 text-sm text-neutral-400">{subtitle}</p>}
          </div>
          {actions}
        </header>
        {children}
      </div>
    </div>
  );
}
