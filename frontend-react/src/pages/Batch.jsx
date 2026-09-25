import React, { useMemo, useRef, useState } from 'react';
import toast from 'react-hot-toast';
import { Download, Loader2, Play, Upload } from 'lucide-react';
import Shell, { Pager, ResultBadge, btnCls, btnPrimary } from '../components/Shell.jsx';
import { useAuth } from '../auth.jsx';
import { parseCsv, pick, saveText, toCsv } from '../csv.js';

const RANGES = { study_hours: [0, 24], attendance: [0, 100], previous_marks: [0, 100] };
const PER_PAGE = 15;

function readRows(text) {
  const valid = [], problems = [];
  parseCsv(text).forEach((r, i) => {
    const row = {
      label: pick(r, ['name', 'label', 'student', 'roll_no']) || null,
      study_hours: pick(r, ['study_hours', 'studyhours', 'hours']),
      attendance: pick(r, ['attendance']),
      previous_marks: pick(r, ['previous_marks', 'previousmarks', 'marks']),
    };
    const bad = Object.entries(RANGES).find(([k, [lo, hi]]) => { const n = Number(row[k]); return row[k] === '' || Number.isNaN(n) || n < lo || n > hi; });
    if (bad) problems.push(`Row ${i + 2}: ${bad[0].replace('_', ' ')} must be a number from ${RANGES[bad[0]][0]} to ${RANGES[bad[0]][1]}`);
    else valid.push({ ...row, study_hours: Number(row.study_hours), attendance: Number(row.attendance), previous_marks: Number(row.previous_marks) });
  });
  return { valid, problems };
}

export default function Batch() {
  const { api } = useAuth();
  const fileRef = useRef(null);
  const [parsed, setParsed] = useState(null);
  const [fileName, setFileName] = useState('');
  const [busy, setBusy] = useState(false);
  const [out, setOut] = useState(null);
  const [page, setPage] = useState(1);
  const [model, setModel] = useState('decision_tree');

  const onFile = async (e) => {
    const file = e.target.files?.[0]; e.target.value = '';
    if (!file) return;
    setOut(null); setPage(1); setFileName(file.name);
    setParsed(readRows(await file.text()));
  };

  const run = async () => {
    setBusy(true);
    try {
      const rows = parsed.valid.slice(0, 500);
      setOut(await api('/predict/batch', { rows, model }));
      setPage(1);
      toast.success(`Checked ${rows.length} students`);
    } catch (e) { toast.error(e.message); } finally { setBusy(false); }
  };

  const pages = out ? Math.max(1, Math.ceil(out.results.length / PER_PAGE)) : 1;
  const slice = useMemo(() => (out ? out.results.slice((page - 1) * PER_PAGE, page * PER_PAGE) : []), [out, page]);
  const cols = ['label', 'study_hours', 'attendance', 'previous_marks', 'predicted_result', 'pass_probability'];

  return (
    <Shell title="Batch predictions" subtitle="Upload a CSV to check a whole class at once (up to 500 students).">
      <div className="glass p-6">
        <input ref={fileRef} type="file" accept=".csv,text/csv" hidden onChange={onFile} />
        <div className="flex flex-wrap items-center gap-3">
          <label className="text-xs text-neutral-400">Model <select value={model} onChange={(e) => setModel(e.target.value)} className="ml-2 rounded-xl border border-white/10 bg-black/40 px-3 py-2 text-sm text-white"><option value="decision_tree">Decision Tree</option><option value="linear_regression">Linear Regression</option></select></label>
          <button className={btnCls} onClick={() => fileRef.current.click()}><Upload size={14} /> Choose CSV file</button>
          <button className={btnCls} onClick={() => saveText('name,study_hours,attendance,previous_marks\nAsha,7,82,66\nBen,3,58,44\n', 'batch-template.csv')}><Download size={14} /> Download template</button>
          {parsed && parsed.valid.length > 0 && <button className={btnPrimary} onClick={run} disabled={busy}>{busy ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />} Run predictions</button>}
        </div>
        <p className="mt-3 text-xs text-neutral-500">Columns: name (optional), study_hours (0 to 24), attendance (0 to 100), previous_marks (0 to 100).</p>

        {parsed && (
          <div className="mt-5 text-sm">
            <p className="text-neutral-300"><span className="font-semibold text-white">{fileName}</span>: {parsed.valid.length} valid rows{parsed.problems.length > 0 && `, ${parsed.problems.length} with problems`}.{parsed.valid.length > 500 && ' Only the first 500 will be checked.'}</p>
            {parsed.problems.length > 0 && (
              <ul className="mt-2 max-h-28 overflow-auto rounded-xl border border-white/10 bg-black/30 p-3 text-xs" style={{ color: 'var(--fail)' }}>
                {parsed.problems.slice(0, 20).map((p) => <li key={p}>{p}</li>)}
                {parsed.problems.length > 20 && <li>…and {parsed.problems.length - 20} more</li>}
              </ul>
            )}
          </div>
        )}
      </div>

      {out && (
        <div className="glass mt-6 p-6">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-neutral-300"><span className="font-semibold" style={{ color: 'var(--pass)' }}>{out.passed} likely to pass</span> · <span className="font-semibold" style={{ color: 'var(--fail)' }}>{out.failed} at risk</span></p>
            <button className={btnCls} onClick={() => saveText(toCsv(out.results, cols), 'batch-results.csv')}><Download size={14} /> Export CSV</button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs text-neutral-500"><tr>{['Student', 'Study hours', 'Attendance', 'Marks', 'Result', 'Chance of passing'].map((h) => <th key={h} className="p-3 font-medium">{h}</th>)}</tr></thead>
              <tbody className="divide-y divide-white/5">
                {slice.map((r, i) => (
                  <tr key={i} className="hover:bg-white/[0.03]">
                    <td className="p-3 font-medium text-white">{r.label || `Row ${(page - 1) * PER_PAGE + i + 1}`}</td>
                    <td className="mono p-3 text-neutral-400">{r.study_hours}h</td><td className="mono p-3 text-neutral-400">{r.attendance}%</td><td className="mono p-3 text-neutral-400">{r.previous_marks}</td>
                    <td className="p-3"><ResultBadge result={r.predicted_result} /></td><td className="mono p-3">{Math.round(r.pass_probability * 100)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pager page={page} pages={pages} total={out.results.length} onPage={setPage} />
        </div>
      )}
    </Shell>
  );
}
