import React, { useEffect, useState } from 'react';
import toast from 'react-hot-toast';
import { FileText, Loader2, Play } from 'lucide-react';
import Shell, { ResultBadge, btnCls, btnPrimary, glass, inputCls } from '../components/Shell.jsx';
import { useAuth } from '../auth.jsx';

const Field = ({ label, unit, ...props }) => (
  <label className="block">
    <span className="mb-1.5 block text-sm font-medium text-neutral-300">{label}</span>
    <div className="relative">
      <input {...props} className={inputCls} />
      <span className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-xs text-neutral-500">{unit}</span>
    </div>
  </label>
);

export default function StudentHome() {
  const { user, api, download } = useAuth();
  const [form, setForm] = useState({ study_hours: '', attendance: '', previous_marks: '' });
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);

  const loadHistory = () => api('/predict/history?page_size=10').then((p) => setHistory(p.items)).catch(() => {});
  useEffect(() => { loadHistory(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const r = await api('/predict/', {
        study_hours: parseFloat(form.study_hours || 0),
        attendance: parseFloat(form.attendance || 0),
        previous_marks: parseFloat(form.previous_marks || 0),
      });
      setResult(r);
      loadHistory();
    } catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };

  return (
    <Shell title={`Hi, ${user.full_name.split(' ')[0]}`} subtitle="Check your own result and download your report.">
      <div className="grid gap-6 lg:grid-cols-5">
        <form onSubmit={submit} className={`${glass} space-y-4 p-6 lg:col-span-2`}>
          <Field label="Study hours per day" unit="h" type="number" min={0} max={24} step={0.1} required
            value={form.study_hours} onChange={(e) => setForm({ ...form, study_hours: e.target.value })} />
          <Field label="Attendance" unit="%" type="number" min={0} max={100} step={1} required
            value={form.attendance} onChange={(e) => setForm({ ...form, attendance: e.target.value })} />
          <Field label="Previous marks" unit="/100" type="number" min={0} max={100} step={1} required
            value={form.previous_marks} onChange={(e) => setForm({ ...form, previous_marks: e.target.value })} />
          <button disabled={busy} className={`${btnPrimary} w-full py-3`}>
            {busy ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />} Check my result
          </button>
        </form>

        <div className="space-y-6 lg:col-span-3">
          {result ? (
            <div className={`${glass} p-6`}>
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-xs text-neutral-400">Predicted result</div>
                  <div className="mono mt-1 text-3xl font-bold" style={{ color: result.predicted_result === 'Pass' ? 'var(--pass)' : 'var(--fail)' }}>{result.predicted_result}</div>
                </div>
                <button className={btnCls} onClick={() => toast.promise(download('/reports/me', `report-${user.full_name}.pdf`), { loading: 'Preparing PDF…', success: 'Downloaded', error: (e) => e.message })}>
                  <FileText size={14} /> Download report
                </button>
              </div>
              <p className="mt-3 text-sm text-neutral-400">Estimated chance of passing: {Math.round(result.pass_probability * 100)}%</p>
              {result.unsupervised_analysis && <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <div className="rounded-xl border border-white/10 bg-black/20 p-4">
                  <div className="text-xs uppercase tracking-wide text-neutral-500">K-Means · 2 clusters</div>
                  <div className="mt-2 text-xl font-semibold text-white">{result.unsupervised_analysis.kmeans?.cluster != null ? `Cluster ${result.unsupervised_analysis.kmeans.cluster}` : 'Not available'}</div>
                  <p className="mt-1 text-xs text-neutral-400">Historical training-cluster Pass share: {result.unsupervised_analysis.kmeans?.historical_training_pass_rate != null ? `${Math.round(Number(result.unsupervised_analysis.kmeans.historical_training_pass_rate) * 100)}%` : 'N/A'}</p>
                  <p className="mt-2 text-xs text-amber-300">{result.unsupervised_analysis.kmeans?.interpretation}</p>
                </div>
                <div className="rounded-xl border border-white/10 bg-black/20 p-4">
                  <div className="text-xs uppercase tracking-wide text-neutral-500">PCA · 2 components</div>
                  <div className="mono mt-2 text-lg font-semibold text-white">{result.unsupervised_analysis.pca?.components ? `PC1 ${Number(result.unsupervised_analysis.pca.components.pc1).toFixed(2)} · PC2 ${Number(result.unsupervised_analysis.pca.components.pc2).toFixed(2)}` : 'Not available'}</div>
                  <p className="mt-2 text-xs text-neutral-400">{result.unsupervised_analysis.pca?.interpretation}</p>
                </div>
              </div>}
              {result.explanation?.length > 0 && (
                <ol className="mt-4 space-y-2 border-t border-white/10 pt-4">
                  {result.explanation.map((s, i) => (
                    <li key={i} className="flex gap-3 text-sm text-neutral-300"><span className="mono text-yellow-400">{i + 1}</span>{s}</li>
                  ))}
                </ol>
              )}
            </div>
          ) : (
            <div className={`${glass} grid place-items-center p-14 text-center text-sm text-neutral-400`}>Fill in the form to see your result.</div>
          )}

          <div className={`${glass} p-6`}>
            <h2 className="mb-4 text-sm font-semibold text-white">Your recent checks</h2>
            {history.length === 0 ? (
              <p className="text-sm text-neutral-500">Nothing yet — run your first check above.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="text-xs text-neutral-500"><tr>{['Date', 'Hours', 'Attendance', 'Marks', 'Result'].map((h) => <th key={h} className="p-2 font-medium">{h}</th>)}</tr></thead>
                  <tbody className="divide-y divide-white/5">
                    {history.map((h) => (
                      <tr key={h.id}>
                        <td className="p-2 text-xs text-neutral-500">{new Date(h.created_at).toLocaleDateString()}</td>
                        <td className="mono p-2 text-neutral-300">{h.study_hours}h</td>
                        <td className="mono p-2 text-neutral-300">{h.attendance}%</td>
                        <td className="mono p-2 text-neutral-300">{h.previous_marks}</td>
                        <td className="p-2"><ResultBadge result={h.result} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>
    </Shell>
  );
}
