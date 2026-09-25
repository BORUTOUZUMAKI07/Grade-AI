import React, { useCallback, useEffect, useState } from 'react';
import toast from 'react-hot-toast';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import Shell, { Pager, inputCls } from '../components/Shell.jsx';
import { useAuth } from '../auth.jsx';

const Card = ({ label, value }) => (
  <div className="glass p-5"><div className="text-xs text-neutral-400">{label}</div><div className="mono mt-2 text-3xl font-bold text-white">{value}</div></div>
);

export default function Admin() {
  const { api, user: me } = useAuth();
  const [stats, setStats] = useState(null);
  const [users, setUsers] = useState({ items: [], total: 0, pages: 1 });
  const [q, setQ] = useState('');
  const [role, setRole] = useState('');
  const [page, setPage] = useState(1);

  const loadStats = useCallback(() => api('/admin/stats').then(setStats).catch((e) => toast.error(e.message)), [api]);
  const loadUsers = useCallback(() => {
    const qs = new URLSearchParams({ page, page_size: 10 });
    if (q.trim()) qs.set('q', q.trim());
    if (role) qs.set('role', role);
    return api(`/admin/users?${qs}`).then(setUsers).catch((e) => toast.error(e.message));
  }, [api, page, q, role]);

  useEffect(() => { loadStats(); }, [loadStats]);
  useEffect(() => { const t = setTimeout(loadUsers, 250); return () => clearTimeout(t); }, [loadUsers]);
  useEffect(() => { setPage(1); }, [q, role]);

  const patch = async (u, body) => {
    try { await api(`/admin/users/${u.id}`, body, 'PATCH'); toast.success('Saved'); await Promise.all([loadUsers(), loadStats()]); } catch (e) { toast.error(e.message); }
  };

  return (
    <Shell title="Admin" subtitle="People, roles and usage across GradeAI.">
      {stats && (
        <>
          <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Card label="Users" value={stats.total_users} />
            <Card label="Active users" value={stats.active_users} />
            <Card label="Predictions" value={stats.total_predictions} />
            <Card label="Predicted to pass" value={`${Math.round(stats.pass_rate * 100)}%`} />
          </div>
          <div className="glass mb-6 p-6">
            <h2 className="mb-4 text-sm font-semibold text-white">Predictions in the last 14 days</h2>
            <div className="h-56">
              <ResponsiveContainer>
                <BarChart data={stats.predictions_by_day.map((d) => ({ ...d, day: d.day.slice(5) }))} margin={{ top: 5, right: 5, bottom: 0, left: -25 }}>
                  <CartesianGrid strokeDasharray="3 6" stroke="rgba(255,255,255,0.06)" vertical={false} />
                  <XAxis dataKey="day" stroke="#525252" fontSize={11} /><YAxis allowDecimals={false} stroke="#525252" fontSize={11} />
                  <Tooltip contentStyle={{ background: 'rgba(10,10,10,0.9)', border: '1px solid rgba(255,255,255,0.12)', borderRadius: 12, fontSize: 12 }} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
                  <Bar dataKey="count" name="Predictions" fill="var(--color-yellow-400)" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </>
      )}

      <div className="glass p-6">
        <div className="mb-4 flex flex-wrap gap-3">
          <input className={`${inputCls} max-w-xs`} placeholder="Search name or email" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search users" />
          <select className={`${inputCls} w-40`} value={role} onChange={(e) => setRole(e.target.value)} aria-label="Filter by role">
            <option value="">All roles</option><option value="admin">Admin</option><option value="teacher">Teacher</option><option value="student">Student</option>
          </select>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs text-neutral-500"><tr>{['Name', 'Email', 'Role', 'Active', 'Predictions', 'Joined'].map((h) => <th key={h} className="p-3 font-medium">{h}</th>)}</tr></thead>
            <tbody className="divide-y divide-white/5">
              {users.items.map((u) => {
                const self = u.id === me.id;
                return (
                  <tr key={u.id} className="hover:bg-white/[0.03]">
                    <td className="p-3 font-medium text-white">{u.full_name}{self && <span className="ml-2 text-xs text-neutral-500">(you)</span>}</td>
                    <td className="p-3 text-neutral-400">{u.email}</td>
                    <td className="p-3">
                      <select className={`${inputCls} w-32 py-1.5`} value={u.role} disabled={self} onChange={(e) => patch(u, { role: e.target.value })} aria-label={`Role for ${u.full_name}`}>
                        <option value="admin">Admin</option><option value="teacher">Teacher</option><option value="student">Student</option>
                      </select>
                    </td>
                    <td className="p-3">
                      <button role="switch" aria-checked={u.is_active} disabled={self} onClick={() => patch(u, { is_active: !u.is_active })} aria-label={`Active: ${u.full_name}`}
                        className={`relative h-6 w-11 rounded-full transition disabled:opacity-40 ${u.is_active ? 'bg-yellow-400' : 'bg-white/15'}`}>
                        <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-black transition-all ${u.is_active ? 'left-[22px]' : 'left-0.5 bg-white'}`} />
                      </button>
                    </td>
                    <td className="mono p-3 text-neutral-300">{u.prediction_count}</td>
                    <td className="p-3 text-xs text-neutral-500">{new Date(u.created_at).toLocaleDateString()}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {users.items.length === 0 && <p className="p-8 text-center text-sm text-neutral-500">No users match.</p>}
        </div>
        <Pager page={page} pages={users.pages} total={users.total} onPage={setPage} />
      </div>
    </Shell>
  );
}
