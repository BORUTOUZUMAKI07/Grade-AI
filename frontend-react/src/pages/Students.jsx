import React, { useCallback, useEffect, useRef, useState } from 'react';
import toast from 'react-hot-toast';
import { FileText, Loader2, Plus, Trash2, Upload, Users } from 'lucide-react';
import Shell, { Pager, ResultBadge, btnCls, btnPrimary, inputCls } from '../components/Shell.jsx';
import { useAuth } from '../auth.jsx';
import { parseCsv, pick } from '../csv.js';

function useDebounced(value, ms = 300) {
  const [v, setV] = useState(value);
  useEffect(() => { const t = setTimeout(() => setV(value), ms); return () => clearTimeout(t); }, [value, ms]);
  return v;
}

export default function Students() {
  const { api, download } = useAuth();
  const [classes, setClasses] = useState([]);
  const [classId, setClassId] = useState(null);
  const [q, setQ] = useState('');
  const dq = useDebounced(q);
  const [page, setPage] = useState(1);
  const [data, setData] = useState({ items: [], total: 0, pages: 1 });
  const [loading, setLoading] = useState(true);
  const [newClass, setNewClass] = useState('');
  const [form, setForm] = useState({ full_name: '', roll_no: '' });
  const fileRef = useRef(null);

  const guard = async (fn, ok) => { try { await fn(); if (ok) toast.success(ok); } catch (e) { toast.error(e.message); } };

  const loadClasses = useCallback(() => api('/classes?page_size=100').then((r) => setClasses(r.items)).catch((e) => toast.error(e.message)), [api]);
  const loadStudents = useCallback(async () => {
    setLoading(true);
    try {
      const qs = new URLSearchParams({ page, page_size: 10 });
      if (classId) qs.set('class_id', classId);
      if (dq.trim()) qs.set('q', dq.trim());
      setData(await api(`/students?${qs}`));
    } catch (e) { toast.error(e.message); } finally { setLoading(false); }
  }, [api, page, dq, classId]);

  useEffect(() => { loadClasses(); }, [loadClasses]);
  useEffect(() => { loadStudents(); }, [loadStudents]);
  useEffect(() => { setPage(1); }, [dq, classId]);

  const addClass = (e) => { e.preventDefault(); guard(async () => { await api('/classes', { name: newClass }); setNewClass(''); await loadClasses(); }, 'Class added'); };
  const deleteClass = (c) => window.confirm(`Delete class "${c.name}"? Its students are kept.`) && guard(async () => {
    await api(`/classes/${c.id}`, undefined, 'DELETE'); if (classId === c.id) setClassId(null); await Promise.all([loadClasses(), loadStudents()]);
  }, 'Class deleted');
  const addStudent = (e) => { e.preventDefault(); guard(async () => {
    await api('/students', { full_name: form.full_name, roll_no: form.roll_no || null, class_id: classId });
    setForm({ full_name: '', roll_no: '' }); await Promise.all([loadStudents(), loadClasses()]);
  }, 'Student added'); };
  const deleteStudent = (s) => window.confirm(`Delete ${s.full_name}? Their past predictions stay in your history.`) && guard(async () => {
    await api(`/students/${s.id}`, undefined, 'DELETE'); await Promise.all([loadStudents(), loadClasses()]);
  }, 'Student deleted');

  const importFile = (e) => {
    const file = e.target.files?.[0]; e.target.value = '';
    if (!file) return;
    guard(async () => {
      const rows = parseCsv(await file.text())
        .map((r) => ({ full_name: pick(r, ['full_name', 'name', 'student', 'student_name']), roll_no: pick(r, ['roll_no', 'roll', 'roll_number']) || null }))
        .filter((r) => r.full_name);
      if (!rows.length) throw new Error('No students found. The file needs a "name" column and, optionally, a "roll_no" column.');
      let created = 0, skipped = 0;
      for (let i = 0; i < rows.length; i += 500) {
        const r = await api('/students/import', { class_id: classId, rows: rows.slice(i, i + 500) });
        created += r.created; skipped += r.skipped;
      }
      await Promise.all([loadStudents(), loadClasses()]);
      toast.success(`Imported ${created} students${skipped ? `, skipped ${skipped} with a roll number already in use` : ''}`);
    });
  };

  const current = classes.find((c) => c.id === classId);
  return (
    <Shell title="Students" subtitle="Organise your classes, then check each student and download reports."
      actions={<div className="flex gap-2">
        <input ref={fileRef} type="file" accept=".csv,text/csv" hidden onChange={importFile} />
        <button className={btnCls} onClick={() => fileRef.current.click()}><Upload size={14} /> Import CSV</button>
        {current && <button className={btnCls} onClick={() => guard(() => download(`/reports/classes/${current.id}`, `class-${current.name}.pdf`))}><FileText size={14} /> Class report</button>}
      </div>}>
      <div className="grid gap-6 lg:grid-cols-4">
        <aside className="glass h-fit p-5 lg:col-span-1">
          <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-white"><Users size={15} className="text-yellow-400" /> Classes</h2>
          <button onClick={() => setClassId(null)} className={`mb-1 w-full rounded-xl px-3 py-2 text-left text-sm transition ${classId === null ? 'bg-yellow-400 font-semibold text-black' : 'hover:bg-white/5'}`}>All students</button>
          {classes.map((c) => (
            <div key={c.id} className={`group mb-1 flex items-center rounded-xl transition ${classId === c.id ? 'bg-yellow-400 text-black' : 'hover:bg-white/5'}`}>
              <button onClick={() => setClassId(c.id)} className="flex-1 truncate px-3 py-2 text-left text-sm">{c.name} <span className={classId === c.id ? 'text-black/60' : 'text-neutral-500'}>({c.student_count})</span></button>
              <button onClick={() => deleteClass(c)} aria-label={`Delete class ${c.name}`} className="px-2 opacity-60 hover:opacity-100"><Trash2 size={13} /></button>
            </div>
          ))}
          <form onSubmit={addClass} className="mt-4 flex gap-2">
            <input className={inputCls} placeholder="New class" value={newClass} onChange={(e) => setNewClass(e.target.value)} maxLength={80} required aria-label="New class name" />
            <button className={btnPrimary} aria-label="Add class"><Plus size={16} /></button>
          </form>
        </aside>

        <section className="glass p-6 lg:col-span-3">
          <div className="mb-4 flex flex-wrap gap-3">
            <input className={`${inputCls} max-w-xs`} placeholder="Search name or roll number" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search students" />
            <form onSubmit={addStudent} className="flex flex-1 flex-wrap gap-2">
              <input className={`${inputCls} min-w-40 flex-1`} placeholder={`Add a student${current ? ` to ${current.name}` : ''}`} value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} maxLength={120} required aria-label="Student name" />
              <input className={`${inputCls} w-32`} placeholder="Roll no." value={form.roll_no} onChange={(e) => setForm({ ...form, roll_no: e.target.value })} maxLength={40} aria-label="Roll number" />
              <button className={btnPrimary}><Plus size={14} /> Add</button>
            </form>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs text-neutral-500"><tr>{['Student', 'Roll no.', 'Class', 'Latest result', 'Chance of passing', 'Checked', ''].map((h) => <th key={h} className="p-3 font-medium">{h}</th>)}</tr></thead>
              <tbody className="divide-y divide-white/5">
                {data.items.map((s) => (
                  <tr key={s.id} className="transition hover:bg-white/[0.03]">
                    <td className="p-3 font-medium text-white">{s.full_name}</td>
                    <td className="mono p-3 text-neutral-400">{s.roll_no || '-'}</td>
                    <td className="p-3 text-neutral-400">{s.class_name || '-'}</td>
                    <td className="p-3"><ResultBadge result={s.last_result} /></td>
                    <td className="mono p-3 text-neutral-300">{s.last_pass_probability != null ? `${Math.round(s.last_pass_probability * 100)}%` : '-'}</td>
                    <td className="p-3 text-xs text-neutral-500">{s.last_checked ? new Date(s.last_checked).toLocaleDateString() : '-'}</td>
                    <td className="p-3">
                      <div className="flex justify-end gap-1">
                        <button className={btnCls} onClick={() => guard(() => download(`/reports/students/${s.id}`, `report-${s.full_name}.pdf`))} aria-label={`Download report for ${s.full_name}`}><FileText size={14} /></button>
                        <button className={btnCls} onClick={() => deleteStudent(s)} aria-label={`Delete ${s.full_name}`}><Trash2 size={14} /></button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {loading && <div className="flex justify-center p-6"><Loader2 className="animate-spin text-yellow-400" /></div>}
            {!loading && data.items.length === 0 && <p className="p-8 text-center text-sm text-neutral-500">No students yet. Add one above or import a CSV.</p>}
          </div>
          <Pager page={page} pages={data.pages} total={data.total} onPage={setPage} />
          <p className="mt-4 text-xs text-neutral-600">To check a student, choose them on the Dashboard before running a prediction. Their result then appears here.</p>
        </section>
      </div>
    </Shell>
  );
}
