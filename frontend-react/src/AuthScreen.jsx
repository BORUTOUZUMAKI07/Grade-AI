import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Brain, Loader2 } from 'lucide-react';
import { useAuth } from './auth.jsx';

const input = 'w-full rounded-2xl border border-white/10 bg-black/40 px-4 py-3.5 text-sm text-white outline-none transition placeholder:text-neutral-600 focus:border-yellow-400/70 focus:ring-4 focus:ring-yellow-400/10';

export default function AuthScreen() {
  const { login, register } = useAuth();
  const [mode, setMode] = useState('login');
  const [form, setForm] = useState({ name: '', email: '', password: '' });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setError('');
    try {
      if (mode === 'login') await login(form.email, form.password);
      else await register(form.name, form.email, form.password);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="grid min-h-screen place-items-center bg-[var(--bg)] px-4 py-10">
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="glass w-full max-w-md p-8">
        <div className="mb-8 flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-br from-yellow-300 to-yellow-600 text-black"><Brain size={19} /></span>
          <span className="text-xl font-extrabold tracking-tight text-white">Grade<span className="text-yellow-400">AI</span></span>
        </div>
        <h1 className="text-2xl font-bold text-white">{mode === 'login' ? 'Welcome back' : 'Create your account'}</h1>
        <p className="mt-1 text-sm text-neutral-400">{mode === 'login' ? 'Sign in to run predictions and see your history.' : 'It takes under a minute.'}</p>

        <form onSubmit={submit} className="mt-6 space-y-4">
          {mode === 'register' && (
            <input className={input} placeholder="Full name" autoComplete="name" required maxLength={120} value={form.name} onChange={set('name')} aria-label="Full name" />
          )}
          <input className={input} type="email" placeholder="Email" autoComplete="email" required value={form.email} onChange={set('email')} aria-label="Email" />
          <input className={input} type="password" placeholder={mode === 'register' ? 'Password (at least 8 characters)' : 'Password'}
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'} required minLength={mode === 'register' ? 8 : undefined} value={form.password} onChange={set('password')} aria-label="Password" />
          {error && <p role="alert" className="rounded-xl border border-[color:var(--fail)]/40 bg-white/5 px-4 py-3 text-sm text-[color:var(--fail)]">{error}</p>}
          <button disabled={busy} className="flex w-full items-center justify-center gap-2 rounded-2xl bg-yellow-400 py-3.5 text-sm font-bold text-black transition hover:bg-yellow-300 disabled:opacity-60">
            {busy && <Loader2 size={16} className="animate-spin" />}{mode === 'login' ? 'Sign in' : 'Create account'}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-neutral-400">
          {mode === 'login' ? 'New here? ' : 'Already have an account? '}
          <button type="button" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(''); }} className="font-semibold text-yellow-400 hover:underline">
            {mode === 'login' ? 'Create an account' : 'Sign in'}
          </button>
        </p>
      </motion.div>
    </main>
  );
}
