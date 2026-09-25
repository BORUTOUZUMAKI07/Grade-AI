import React, { useState, useEffect, useMemo, lazy, Suspense } from 'react';
import { motion, AnimatePresence, useReducedMotion, useScroll, useSpring } from 'framer-motion';
import {
  ComposedChart, Scatter, XAxis, YAxis, ZAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, RadarChart, PolarGrid, PolarAngleAxis, Radar,
  BarChart, Bar, Cell, RadialBarChart, RadialBar, PolarAngleAxis as GaugeAxis, ReferenceLine
} from 'recharts';
import confetti from 'canvas-confetti';
import { Link } from 'react-router-dom';
import { useAuth } from './auth.jsx';
import CountUp from 'react-countup';
import toast, { Toaster } from 'react-hot-toast';
import ModelAnalytics from './components/ModelAnalytics.jsx';
import LivePredictionCharts from './components/LivePredictionCharts.jsx';
import {
  BookOpen, CalendarCheck, Trophy, Sparkles, Activity, Database,
  ScatterChart as ScatterIcon, Radar as RadarIcon, Terminal, CheckCircle2,
  XCircle, Loader2, Gauge, Layers, Box, Brain, Zap, ArrowDown, ChevronDown, BarChart3, Download, Trash2
} from 'lucide-react';

/*  npm i framer-motion recharts canvas-confetti react-countup react-hot-toast lucide-react
    index.html: add Google Fonts "Sora" (400-800) and "JetBrains Mono" (400-700)  */


// Three.js is code-split so the form and charts load first
const Backdrop = lazy(() => import('./Scene3D.jsx').then((m) => ({ default: m.Backdrop })));
const Cube3D = lazy(() => import('./Scene3D.jsx').then((m) => ({ default: m.Cube3D })));

// Yellow ramp, dark to light
const Y = Object.fromEntries([50, 200, 300, 400, 500, 600, 700, 900].map((n) => [n, `var(--color-yellow-${n})`]));

const glass =
  'glass-spot relative bg-gradient-to-br from-white/[0.07] to-white/[0.02] backdrop-blur-2xl border border-white/10 ' +
  'shadow-[0_8px_40px_-12px_rgba(0,0,0,0.9),inset_0_1px_0_0_rgba(255,255,255,0.08)] rounded-3xl';

const TABS = [
  { id: 'distribution', label: 'Distribution', icon: ScatterIcon },
  { id: 'behavioral', label: 'Profile', icon: RadarIcon },
  { id: 'why', label: 'Why this result', icon: Brain },
  { id: 'hist', label: 'Histograms', icon: BarChart3 },
  { id: 'space', label: '3D space', icon: Box },
  { id: 'registry', label: 'Records', icon: Database },
  { id: 'liveResponse', label: 'Live response', icon: Activity },
  { id: 'modelAnalytics', label: 'Model analytics', icon: Brain },
];

function Field({ icon: Icon, label, hint, value, onChange, min, max, step, unit }) {
  const pct = value === '' ? 0 : Math.min(100, (parseFloat(value) / max) * 100);
  return (
    <label className="block group">
      <div className="flex items-center justify-between mb-2">
        <span className="flex items-center gap-2 text-sm font-medium text-neutral-300">
          <Icon size={15} className="text-yellow-400" /> {label}
        </span>
        <span className="text-xs text-neutral-500">{hint}</span>
      </div>
      <div className="relative">
        <input
          type="number" required min={min} max={max} step={step} value={value}
          onChange={(e) => onChange(e.target.value)} placeholder={`${min} – ${max}`}
          className="w-full rounded-2xl bg-black/40 border border-white/10 px-4 py-3.5 pr-12 font-mono text-lg text-yellow-300 placeholder:text-neutral-700 outline-none transition focus:border-yellow-400/70 focus:ring-4 focus:ring-yellow-400/10"
        />
        <span className="absolute right-4 top-1/2 -translate-y-1/2 text-xs text-neutral-500">{unit}</span>
      </div>
      <input
        type="range" min={min} max={max} step={step} value={value === '' ? min : value}
        onChange={(e) => onChange(e.target.value)} aria-label={`${label} slider`}
        className="mt-3 w-full h-1.5 appearance-none rounded-full cursor-pointer accent-yellow-400"
        style={{ background: `linear-gradient(90deg, ${Y[600]}, ${Y[300]} ${pct}%, rgba(255,255,255,0.08) ${pct}%)` }}
      />
    </label>
  );
}

function Stat({ icon: Icon, label, children, tone = 'text-white' }) {
  return (
    <motion.div layout className={`${glass} p-5 overflow-hidden`}>
      <div className="absolute -top-10 -right-10 h-28 w-28 rounded-full bg-yellow-400/10 blur-2xl" />
      <div className="flex items-center gap-2 text-xs text-neutral-400 mb-3">
        <Icon size={14} className="text-yellow-500" /> {label}
      </div>
      <div className={`font-mono text-3xl font-bold ${tone}`}>{children}</div>
    </motion.div>
  );
}

const tip = {
  contentStyle: { background: 'rgba(10,10,10,0.85)', backdropFilter: 'blur(12px)', border: '1px solid rgba(var(--accent-rgb),0.25)', borderRadius: 14, fontSize: 12, color: Y[300] },
  cursor: { stroke: 'rgba(var(--accent-rgb),0.3)' },
};

const NAV = [['Predict', 'predict'], ['How it works', 'how'], ['Insights', 'insights'], ['FAQ', 'faq']];

const FEATURES = [
  { k: 'study_hours', label: 'Study hours', max: 12 },
  { k: 'attendance', label: 'Attendance', max: 100 },
  { k: 'previous_marks', label: 'Previous marks', max: 100 },
];
const THEMES = [['brass', '#c9a24b', 'Onyx & Brass'], ['ember', '#e2672b', 'Carbon & Ember'], ['petrol', '#4aaeb4', 'Slate & Petrol']];
const DEFAULT_PALETTE = { accent: '#c9a24b', accent2: '#8f6d2b', pass: '#5fae8a', fail: '#c8645a' };

function Words({ text, className }) {
  return (
    <h1 className={className} aria-label={text}>
      {text.split(' ').map((w, i) => (
        <motion.span key={i} aria-hidden="true" className="mr-[0.25em] inline-block"
          initial={{ opacity: 0, y: 28, filter: 'blur(10px)' }} animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
          transition={{ duration: 0.7, delay: 0.15 + i * 0.07, ease: [0.22, 1, 0.36, 1] }}>{w}</motion.span>
      ))}
    </h1>
  );
}

function History({ history, onClear }) {
  const exportCsv = () => {
    const head = 'time,study_hours,attendance,previous_marks,model,result,confidence\n';
    const body = history.map((h) => [new Date(h.t).toISOString(), h.study, h.att, h.marks, h.model || 'decision_tree', h.result, h.conf].join(',')).join('\n');
    const url = URL.createObjectURL(new Blob([head + body], { type: 'text/csv' }));
    const a = document.createElement('a'); a.href = url; a.download = 'gradeai-predictions.csv'; a.click(); URL.revokeObjectURL(url);
  };
  const btn = 'flex items-center gap-2 rounded-full bg-white/5 px-4 py-2 text-xs text-neutral-300 transition hover:bg-white/10';
  return (
    <div className={`${glass} p-6`}>
      <div className="mb-4 flex items-center justify-between gap-3">
        <h3 className="font-semibold text-white">Recent predictions</h3>
        {history.length > 0 && (
          <div className="flex gap-2">
            <button onClick={exportCsv} className={btn}><Download size={13} /> Export CSV</button>
            {onClear && <button onClick={onClear} className={btn}><Trash2 size={13} /> Clear</button>}
          </div>
        )}
      </div>
      {history.length === 0 ? (
        <p className="text-sm text-neutral-500">Predictions you run appear here and are saved to your account.</p>
      ) : (
        <div className="custom-scrollbar max-h-72 overflow-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs text-neutral-500"><tr>{['Time', 'Hours', 'Attendance', 'Marks', 'Model', 'Result', 'Confidence'].map((h) => <th key={h} className="p-2 font-medium">{h}</th>)}</tr></thead>
            <tbody className="mono divide-y divide-white/5 text-neutral-400">
              {history.slice(0, 20).map((h) => (
                <tr key={h.t}>
                  <td className="p-2">{new Date(h.t).toLocaleTimeString()}</td><td className="p-2">{h.study}h</td><td className="p-2">{h.att}%</td><td className="p-2">{h.marks}</td><td className="p-2 text-xs">{({decision_tree:'Decision Tree',linear_regression:'Linear Regression',kmeans:'K-Means',pca_knn:'PCA + kNN'}[h.model] || h.model || 'Decision Tree')}</td>
                  <td className="p-2 font-semibold" style={{ color: h.result === 'Pass' ? 'var(--pass)' : 'var(--fail)' }}>{h.result}</td><td className="p-2">{h.conf}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

const FAQS = [
  ['What does GradeAI predict?', 'Whether a student is likely to pass or fail, based on daily study hours, attendance and previous marks.'],
  ['How much can I trust the result?', 'The confidence score shows how sure the model is, using the records it was trained on. Treat it as guidance for a conversation, not a final judgement of a student.'],
  ['What do the charts and the 3D view show?', 'Every training record appears as a point, so you can see where your student sits compared with students who passed and failed.'],
  ['Where does the data come from?', 'From the records stored in the backend. You can browse all of them in the Records tab after running a prediction.'],
];

function SectionTitle({ id, title, sub }) {
  return (
    <div id={id} className="mx-auto mb-12 max-w-2xl scroll-mt-28 text-center">
      <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">{title}</h2>
      {sub && <p className="mt-3 text-base leading-relaxed text-neutral-400">{sub}</p>}
    </div>
  );
}

const reveal = { initial: { opacity: 0, y: 24 }, whileInView: { opacity: 1, y: 0 }, viewport: { once: true, margin: '-60px' }, transition: { duration: 0.5 } };

function Snapshot({ data, me }) {
  if (!data) {
    return <div className={`${glass} p-10 text-center text-sm text-neutral-400`}>Run a prediction above to see how passing and failing students differ in the data.</div>;
  }
  const rows = data.raw_records;
  const avg = (res, k) => { const g = rows.filter((x) => x.result === res); return g.length ? g.reduce((t, x) => t + x[k], 0) / g.length : 0; };
  const rate = rows.length ? Math.round((rows.filter((x) => x.result === 'Pass').length / rows.length) * 100) : 0;
  const metrics = [['study hours per day', 'study_hours', 12], ['attendance (%)', 'attendance', 100], ['previous marks', 'previous_marks', 100]];
  return (
    <div className={`${glass} grid gap-10 p-8 lg:grid-cols-3`}>
      <div className="flex flex-col justify-center">
        <div className="text-sm text-neutral-400">Students who passed</div>
        <div className="mono text-6xl font-bold text-yellow-300"><CountUp end={rate} duration={1.2} preserveValue />%</div>
        <p className="mt-2 text-sm text-neutral-500">across {rows.length} training records</p>
      </div>
      <div className="space-y-6 lg:col-span-2">
        {metrics.map(([label, k, max]) => (
          <div key={k}>
            <div className="mb-2 text-sm text-neutral-300">Average {label}</div>
            {['Pass', 'Fail'].map((res) => {
              const v = avg(res, k);
              return (
                <div key={res} className="mb-1.5 flex items-center gap-3">
                  <span className="w-10 text-xs text-neutral-500">{res}</span>
                  <div className="h-2 flex-1 rounded-full bg-white/5">
                    <motion.div initial={{ width: 0 }} whileInView={{ width: `${Math.min(100, (v / max) * 100)}%` }} viewport={{ once: true }} transition={{ duration: 0.8 }}
                      className="h-full rounded-full" style={{ background: res === 'Pass' ? 'var(--pass)' : 'var(--fail)' }} />
                  </div>
                  <span className="mono w-14 text-right text-xs text-neutral-300">{v.toFixed(1)}</span>
                </div>
              );
            })}
          </div>
        ))}
      </div>
      {me && (
        <div className="grid gap-3 sm:grid-cols-3 lg:col-span-3">
          {FEATURES.map((f) => {
            const v = me[f.k]; const pct = Math.round((rows.filter((x) => x[f.k] < v).length / Math.max(1, rows.length)) * 100);
            return (
              <div key={f.k} className="rounded-2xl border border-white/10 bg-black/30 p-4">
                <div className="text-xs text-neutral-500">{f.label}</div>
                <div className="mono mt-1 text-2xl font-bold text-white">{pct}<span className="text-sm text-neutral-500"> percentile</span></div>
                <div className="mt-1 text-xs text-neutral-400">Higher than {pct}% of students in the data</div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function Faq() {
  const [open, setOpen] = useState(0);
  return (
    <div className="mx-auto max-w-3xl space-y-3">
      {FAQS.map(([q, a], i) => (
        <div key={q} className={`${glass} overflow-hidden rounded-2xl`}>
          <button onClick={() => setOpen(open === i ? -1 : i)} aria-expanded={open === i} className="flex w-full items-center justify-between gap-4 px-6 py-5 text-left text-base font-medium text-white">
            {q}
            <ChevronDown size={18} className={`shrink-0 text-yellow-400 transition-transform ${open === i ? 'rotate-180' : ''}`} />
          </button>
          <AnimatePresence initial={false}>
            {open === i && (
              <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
                <p className="px-6 pb-5 text-sm leading-relaxed text-neutral-400">{a}</p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      ))}
    </div>
  );
}

export default function App() {
  const reduce = useReducedMotion();
  const { user, logout, api } = useAuth();
  const [studyHours, setStudyHours] = useState('');
  const [attendance, setAttendance] = useState('');
  const [previousMarks, setPreviousMarks] = useState('');
  const [loading, setLoading] = useState(false);
  const [selectedModel, setSelectedModel] = useState('decision_tree');
  const [modelRegistry, setModelRegistry] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [sensitivity, setSensitivity] = useState(null);
  const [predictionInputs, setPredictionInputs] = useState(null);
  const [data, setData] = useState(null);
  const [activeTab, setActiveTab] = useState('distribution');
  const [logs, setLogs] = useState([]);
  const [activeRow, setActiveRow] = useState(null);
  const [feat, setFeat] = useState('study_hours');
  const [students, setStudents] = useState([]);
  const [studentId, setStudentId] = useState('');
  const [theme, setTheme] = useState(() => { try { return localStorage.getItem('gradeai-theme') || 'brass'; } catch { return 'brass'; } });
  const [palette, setPalette] = useState(DEFAULT_PALETTE);
  const [history, setHistory] = useState([]);
  const progress = useSpring(useScroll().scrollYProgress, { stiffness: 120, damping: 24 });
  const last = history[0];
  const me = last ? { study_hours: last.study, attendance: last.att, previous_marks: last.marks } : null;

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem('gradeai-theme', theme); } catch { /* storage unavailable */ }
    const cs = getComputedStyle(document.documentElement);
    const g = (n) => cs.getPropertyValue(n).trim();
    setPalette({ accent: g('--color-yellow-400'), accent2: g('--color-yellow-600'), pass: g('--pass'), fail: g('--fail') });
  }, [theme]);
  useEffect(() => {
    api('/predict/models').then((r) => setModelRegistry(r.models || [])).catch(() => {});
    if (user.role !== 'student') api('/predict/analytics').then(setAnalytics).catch(() => {});
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    api('/predict/history?page_size=50')
      .then((page) => setHistory(page.items.map((h) => ({ t: new Date(h.created_at).getTime(), study: h.study_hours, att: h.attendance, marks: h.previous_marks, result: h.result, model: h.model_name || 'decision_tree', conf: Math.round(h.confidence * 100) }))))
      .catch(() => {});
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (user.role === 'student') return;
    api('/students?page_size=100').then((r) => setStudents(r.items)).catch(() => {});
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const move = (e) => {
      const el = e.target.closest && e.target.closest('.glass-spot');
      if (!el) return;
      const b = el.getBoundingClientRect();
      el.style.setProperty('--mx', `${e.clientX - b.left}px`); el.style.setProperty('--my', `${e.clientY - b.top}px`);
    };
    window.addEventListener('pointermove', move);
    return () => window.removeEventListener('pointermove', move);
  }, []);

  const hist = useMemo(() => {
    const f = FEATURES.find((x) => x.k === feat); const n = 8; const w = f.max / n;
    const idx = (v) => Math.min(n - 1, Math.max(0, Math.floor(v / w)));
    const bins = Array.from({ length: n }, (_, i) => ({ label: `${+(i * w).toFixed(1)}–${+((i + 1) * w).toFixed(1)}`, Pass: 0, Fail: 0 }));
    data?.raw_records.forEach((r) => { bins[idx(r[feat])][r.result]++; });
    return { bins, me: last ? bins[idx(last[{ study_hours: 'study', attendance: 'att', previous_marks: 'marks' }[feat]])].label : null };
  }, [data, feat, last]);

  const log = (msg, level = 'SYS') => {
    const t = new Date().toLocaleTimeString();
    setLogs((p) => [{ t, level, msg }, ...p.slice(0, 20)]);
  };

  useEffect(() => {
    log('GradeAI engine ready.', 'CORE');
    log('Waiting for student inputs.', 'IDLE');
  }, []);

  const run = async (e) => {
    e.preventDefault();
    setLoading(true);
    log(`Sending inputs to ${selectedModel}…`, 'RUN');
    try {
      const payload = await api('/predict/', {
        study_hours: parseFloat(studyHours || 0),
        attendance: parseFloat(attendance || 0),
        previous_marks: parseFloat(previousMarks || 0),
        student_id: studentId ? Number(studentId) : undefined,
        model: selectedModel,
      });
      setData(payload);
      const submittedInputs = { study_hours: parseFloat(studyHours || 0), attendance: parseFloat(attendance || 0), previous_marks: parseFloat(previousMarks || 0) };
      setPredictionInputs(submittedInputs);
      setSensitivity(null);
      try {
        const curve = await api('/predict/sensitivity', { ...submittedInputs, model: payload.selected_model || selectedModel });
        setSensitivity(curve);
      } catch (curveError) {
        log('Prediction succeeded; live response curve unavailable: ' + curveError.message, 'WARN');
      }
      setHistory((h) => [{ t: Date.now(), study: parseFloat(studyHours || 0), att: parseFloat(attendance || 0), marks: parseFloat(previousMarks || 0), result: payload.predicted_result, model: payload.selected_model || selectedModel, conf: Math.round(payload.confidence_score * 100) }, ...h].slice(0, 50));
      log(`Prediction (${payload.selected_model || selectedModel}): ${payload.predicted_result.toUpperCase()}`, 'OK');
      if (payload.predicted_result === 'Pass') {
        toast.success('Predicted to pass');
        if (!reduce) confetti({ particleCount: 110, spread: 70, colors: [palette.accent, palette.pass, '#ffffff'], origin: { y: 0.6 } });
      } else toast('Predicted to fail. Try raising study hours or attendance.', { icon: '⚠️' });
    } catch (err) {
      log(`Request failed: ${err.message}`, 'ERR');
      toast.error(`Request failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const points = useMemo(
    () => (data ? data.raw_records.map((r, i) => ({ id: i, x: r.study_hours, y: r.attendance, z: r.previous_marks, result: r.result })) : []),
    [data]
  );
  const radar = [
    { subject: 'Study', A: Math.min(100, (parseFloat(studyHours || 0) / 12) * 100) },
    { subject: 'Attendance', A: parseFloat(attendance || 0) },
    { subject: 'Prior marks', A: parseFloat(previousMarks || 0) },
    { subject: 'Confidence', A: data ? data.confidence_score * 100 : 0 },
  ];
  const bars = useMemo(() => {
    const c = { Pass: 0, Fail: 0 };
    data?.raw_records.forEach((r) => c[r.result]++);
    return [{ name: 'Pass', count: c.Pass, fill: 'var(--pass)' }, { name: 'Fail', count: c.Fail, fill: 'var(--fail)' }];
  }, [data]);

  const passed = data?.predicted_result === 'Pass';
  const conf = data ? Math.round(data.confidence_score * 100) : 0;
  const blob = (cls, dur) => (
    <motion.div
      className={`absolute rounded-full blur-[120px] ${cls}`}
      animate={reduce ? {} : { x: [0, 60, -40, 0], y: [0, -50, 40, 0], scale: [1, 1.15, 0.95, 1] }}
      transition={{ duration: dur, repeat: Infinity, ease: 'easeInOut' }}
    />
  );

  return (
    <div className="relative min-h-screen w-full overflow-x-hidden bg-[var(--bg)] text-neutral-300 antialiased selection:bg-yellow-400 selection:text-black" style={{ fontFamily: "'Sora', system-ui, sans-serif" }}>
      <style>{`
        .mono{font-family:'JetBrains Mono',ui-monospace,monospace}
        .scroll::-webkit-scrollbar{width:6px}.scroll::-webkit-scrollbar-thumb{background:rgba(var(--accent-rgb),.25);border-radius:9px}
        .shine{background:linear-gradient(110deg,transparent 30%,rgba(255,255,255,.35) 50%,transparent 70%);background-size:220% 100%;animation:shine 3.2s linear infinite}
        @keyframes shine{from{background-position:200% 0}to{background-position:-20% 0}}
        @media (prefers-reduced-motion:reduce){.shine{animation:none}}
      `}</style>
      <Toaster position="top-right" toastOptions={{ style: { background: 'rgba(15,15,15,0.9)', color: Y[200], border: '1px solid rgba(var(--accent-rgb),0.25)', backdropFilter: 'blur(12px)' } }} />

      <motion.div style={{ scaleX: progress }} className="fixed left-0 right-0 top-0 z-50 h-0.5 origin-left bg-yellow-400" />
      {/* Ambient background */}
      <div className="pointer-events-none fixed inset-0 -z-0">
        <Suspense fallback={null}><Backdrop palette={palette} /></Suspense>
        {blob('h-[520px] w-[520px] -top-40 -left-32 bg-yellow-500/10', 18)}
        {blob('h-[460px] w-[460px] top-1/3 -right-40 bg-yellow-700/10', 22)}
        {blob('h-[380px] w-[380px] -bottom-32 left-1/3 bg-yellow-300/5', 26)}
        <div className="absolute inset-0 bg-[radial-gradient(rgba(255,255,255,0.06)_1px,transparent_1px)] [background-size:26px_26px] [mask-image:radial-gradient(ellipse_70%_60%_at_50%_40%,#000,transparent)]" />
      </div>

      <div className="relative z-10 mx-auto max-w-7xl px-4 py-6 lg:px-8 lg:py-10">
        {/* Navigation */}
        <motion.nav initial={{ opacity: 0, y: -12 }} animate={{ opacity: 1, y: 0 }} className={`${glass} sticky top-4 z-30 flex items-center justify-between rounded-full px-5 py-3`}>
          <a href="#hero" className="flex items-center gap-3">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-yellow-300 to-yellow-600 text-black shadow-[0_0_24px_-4px_rgba(var(--accent-rgb),0.7)]"><Brain size={18} /></span>
            <span className="text-lg font-extrabold tracking-tight text-white">Grade<span className="text-yellow-400">AI</span></span>
          </a>
          <div className="hidden items-center gap-1 md:flex">
            {NAV.map(([label, id]) => (
              <a key={id} href={`#${id}`} className="rounded-full px-4 py-2 text-sm text-neutral-400 transition hover:bg-white/5 hover:text-white">{label}</a>
            ))}
          </div>
          <div className="flex items-center gap-4">
            <div className="hidden items-center gap-2 sm:flex" role="group" aria-label="Colour theme">
              {THEMES.map(([id, hex, name]) => (
                <button key={id} onClick={() => setTheme(id)} title={name} aria-label={name} aria-pressed={theme === id}
                  className={`h-5 w-5 rounded-full border transition ${theme === id ? 'scale-110 border-white' : 'border-white/20 hover:scale-110'}`} style={{ background: hex }} />
              ))}
            </div>
            <div className="hidden items-center gap-1 lg:flex">
              {user.role !== 'student' && <Link to="/students" className="rounded-full px-3 py-2 text-sm text-neutral-400 transition hover:bg-white/5 hover:text-white">Students</Link>}
              {user.role !== 'student' && <Link to="/batch" className="rounded-full px-3 py-2 text-sm text-neutral-400 transition hover:bg-white/5 hover:text-white">Batch</Link>}
              {user.role === 'admin' && <Link to="/admin" className="rounded-full px-3 py-2 text-sm text-neutral-400 transition hover:bg-white/5 hover:text-white">Admin</Link>}
            </div>
            <span className="hidden text-xs text-neutral-400 xl:inline">{user.full_name}{user.role === 'admin' ? ' · admin' : ''}</span>
            <button onClick={logout} className="rounded-full px-3 py-2 text-sm text-neutral-400 transition hover:bg-white/5 hover:text-white">Sign out</button>
            <a href="#predict" className="rounded-full bg-yellow-400 px-5 py-2 text-sm font-bold text-black transition hover:bg-yellow-300">Predict now</a>
          </div>
        </motion.nav>

        {/* Hero */}
        <section id="hero" className="flex min-h-[85vh] scroll-mt-28 flex-col items-center justify-center py-20 text-center">
          <motion.span {...reveal} className="mb-6 inline-flex items-center gap-2 rounded-full border border-yellow-400/25 bg-yellow-400/10 px-4 py-1.5 text-xs font-medium text-yellow-300">
            <Zap size={13} /> Pass or fail prediction for students
          </motion.span>
          <Words text="Know how a student will do before the exam" className="max-w-4xl text-5xl font-extrabold leading-[1.05] tracking-tight text-white sm:text-6xl lg:text-7xl" />
          <motion.p {...reveal} className="mt-6 max-w-2xl text-lg leading-relaxed text-neutral-400">
            Enter study hours, attendance and previous marks. GradeAI compares them with real records and tells you whether the student is likely to pass, and how sure it is.
          </motion.p>
          <motion.div {...reveal} className="mt-10 flex flex-wrap items-center justify-center gap-4">
            <a href="#predict" className="rounded-2xl bg-gradient-to-r from-yellow-500 via-yellow-300 to-yellow-500 px-8 py-4 text-sm font-bold text-black shadow-[0_10px_40px_-10px_rgba(var(--accent-rgb),0.7)] transition hover:scale-[1.03]">Try the predictor</a>
            <a href="#how" className={`${glass} rounded-2xl px-8 py-4 text-sm font-semibold text-white transition hover:bg-white/10`}>See how it works</a>
          </motion.div>
          <motion.div {...reveal} className="mt-16 grid w-full max-w-3xl grid-cols-1 gap-4 sm:grid-cols-3">
            {[['3 inputs', 'Hours, attendance, marks'], ['Instant', 'Result in seconds'], ['3D view', 'Explore every record']].map(([t, d]) => (
              <div key={t} className={`${glass} rounded-2xl p-5`}>
                <div className="text-xl font-bold text-yellow-300">{t}</div>
                <div className="mt-1 text-sm text-neutral-400">{d}</div>
              </div>
            ))}
          </motion.div>
          <a href="#predict" aria-label="Scroll to the predictor" className="mt-14 text-yellow-400/70"><ArrowDown className="animate-bounce" /></a>
        </section>

        <SectionTitle id="predict" title="Predict a result" sub="Fill in the three fields and run the model. Charts and a 3D view appear below the result." />

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
          {/* Input panel */}
          <motion.section initial={{ opacity: 0, x: -16 }} animate={{ opacity: 1, x: 0 }} className={`${glass} flex flex-col p-6 lg:col-span-4`}>
            <h2 className="mb-6 flex items-center gap-2 text-base font-semibold text-white"><Layers size={17} className="text-yellow-400" /> Student details</h2>
            <form onSubmit={run} className="space-y-6">
              <label className="block"><span className="mb-2 block text-sm font-medium text-neutral-300">Prediction model</span><select value={selectedModel} onChange={(e) => { setSelectedModel(e.target.value); setSensitivity(null); }} className="w-full rounded-2xl border border-white/10 bg-black/40 px-4 py-3.5 text-sm text-white outline-none focus:border-yellow-400/70">{(modelRegistry.length ? modelRegistry.filter((m) => m.available) : [{id:'decision_tree',name:'Decision Tree'},{id:'linear_regression',name:'Linear Regression'}]).map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}</select><p className="mt-1 text-xs text-neutral-500">{selectedModel === 'linear_regression' ? 'Linear score fitted to Pass/Fail labels; not exam marks.' : selectedModel === 'kmeans' ? 'Assigns the nearest cluster, then estimates outcome from that cluster’s Pass/Fail label mix.' : selectedModel === 'pca_knn' ? 'Projects inputs into PCA space and votes using the 15 nearest labeled training records.' : 'Uses the trained decision tree and its decision path.'}</p></label>
              <Field icon={BookOpen} label="Study hours" hint="per day" value={studyHours} onChange={setStudyHours} min={0} max={24} step={0.1} unit="h" />
              <Field icon={CalendarCheck} label="Attendance" hint="percent" value={attendance} onChange={setAttendance} min={0} max={100} step={1} unit="%" />
              <Field icon={Trophy} label="Previous marks" hint="out of 100" value={previousMarks} onChange={setPreviousMarks} min={0} max={100} step={1} unit="/100" />
              {students.length > 0 && (
                <label className="block">
                  <span className="mb-2 flex items-center justify-between text-sm font-medium text-neutral-300">Student <span className="text-xs font-normal text-neutral-500">optional</span></span>
                  <select value={studentId} onChange={(e) => setStudentId(e.target.value)} className="w-full rounded-2xl border border-white/10 bg-black/40 px-4 py-3.5 text-sm text-white outline-none transition focus:border-yellow-400/70 focus:ring-4 focus:ring-yellow-400/10">
                    <option value="">Not linked to a student</option>
                    {students.map((st) => <option key={st.id} value={st.id}>{st.full_name}{st.roll_no ? ` (${st.roll_no})` : ''}</option>)}
                  </select>
                </label>
              )}
              <motion.button
                whileHover={reduce ? {} : { scale: 1.02 }} whileTap={{ scale: 0.97 }}
                type="submit" disabled={loading}
                className="relative w-full overflow-hidden rounded-2xl bg-gradient-to-r from-yellow-500 via-yellow-300 to-yellow-500 py-4 text-sm font-bold text-black shadow-[0_10px_40px_-10px_rgba(var(--accent-rgb),0.7)] transition disabled:opacity-60"
              >
                <span className="shine absolute inset-0" />
                <span className="relative flex items-center justify-center gap-2">
                  {loading ? <><Loader2 size={16} className="animate-spin" /> Predicting…</> : <><Activity size={16} /> Predict result</>}
                </span>
              </motion.button>
            </form>

            <div className="mt-8 flex-1">
              <div className="mb-2 flex items-center gap-2 text-xs text-neutral-500"><Terminal size={13} /> Activity log</div>
              <div className="scroll mono h-36 space-y-1.5 overflow-y-auto rounded-2xl border border-white/5 bg-black/50 p-3 text-[11px]" aria-live="polite">
                {logs.map((l, i) => (
                  <div key={i} className={l.level === 'OK' ? 'text-yellow-300' : l.level === 'ERR' ? 'text-red-400' : 'text-neutral-500'}>
                    <span className="text-neutral-700">{l.t}</span> {l.msg}
                  </div>
                ))}
              </div>
            </div>
          </motion.section>

          {/* Results */}
          <div className="flex flex-col gap-6 lg:col-span-8">
            <AnimatePresence mode="wait">
              {data ? (
                <motion.div key="kpi" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                  <Stat icon={passed ? CheckCircle2 : XCircle} label="Predicted result" tone={passed ? 'text-[color:var(--pass)]' : 'text-[color:var(--fail)]'}>
                    {data.predicted_result}
                  </Stat>
                  <Stat icon={Gauge} label="Model confidence">
                    <CountUp end={conf} duration={1.2} preserveValue />%
                  </Stat>
                  <Stat icon={Database} label="Training records" tone="text-yellow-400">
                    <CountUp end={data.metadata.total_records} duration={1.2} preserveValue />
                  </Stat>
                </motion.div>
              ) : (
                <motion.div key="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className={`${glass} grid place-items-center border-dashed p-14 text-center`}>
                  <Sparkles className="mb-3 text-yellow-500" />
                  <p className="text-sm text-neutral-400">Enter study hours, attendance and previous marks, then choose Predict result.</p>
                </motion.div>
              )}
            </AnimatePresence>

            {data && (
              <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className={`${glass} flex min-h-[470px] flex-1 flex-col p-5`}>
                <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
                  <div role="tablist" className="flex flex-wrap gap-1 rounded-full border border-white/10 bg-black/40 p-1">
                    {TABS.filter(({ id }) => id !== 'modelAnalytics' || user.role !== 'student').map(({ id, label, icon: I }) => (
                      <button key={id} role="tab" aria-selected={activeTab === id} onClick={() => setActiveTab(id)}
                        className={`relative flex items-center gap-2 rounded-full px-4 py-2 text-xs font-semibold transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-yellow-400 ${activeTab === id ? 'text-black' : 'text-neutral-400 hover:text-white'}`}>
                        {activeTab === id && <motion.span layoutId="tab-pill" className="absolute inset-0 rounded-full bg-gradient-to-r from-yellow-400 to-yellow-300" transition={{ type: 'spring', stiffness: 400, damping: 32 }} />}
                        <span className="relative flex items-center gap-2"><I size={14} /> {label}</span>
                      </button>
                    ))}
                  </div>
                  <span className="text-xs text-neutral-500">Hover a point for details</span>
                </div>

                <AnimatePresence mode="wait">
                  <motion.div key={activeTab} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }} className="min-h-0 flex-1">
                    {activeTab === 'distribution' && (
                      <div className="h-[340px] w-full">
                        <ResponsiveContainer>
                          <ComposedChart margin={{ top: 10, right: 10, bottom: 20, left: -10 }}>
                            <defs>
                              <filter id="glow"><feGaussianBlur stdDeviation="3" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
                            </defs>
                            <CartesianGrid strokeDasharray="3 6" stroke="rgba(255,255,255,0.06)" />
                            <XAxis type="number" dataKey="x" name="Study hours" unit="h" stroke="#525252" fontSize={11} label={{ value: 'Study hours', position: 'insideBottom', offset: -10, fill: '#737373', fontSize: 11 }} />
                            <YAxis type="number" dataKey="y" name="Attendance" unit="%" stroke="#525252" fontSize={11} />
                            <ZAxis type="number" dataKey="z" range={[40, 260]} name="Previous marks" />
                            <Tooltip {...tip} cursor={{ strokeDasharray: '3 3', stroke: Y[400] }} />
                            <Scatter name="Pass" data={points.filter((p) => p.result === 'Pass')} fill="var(--pass)" fillOpacity={0.85} />
                            <Scatter name="Fail" data={points.filter((p) => p.result === 'Fail')} fill="var(--fail)" fillOpacity={0.7} />
                          </ComposedChart>
                        </ResponsiveContainer>
                        <p className="mt-1 text-center text-xs text-neutral-500">Bubble size shows previous marks. Yellow = pass, grey = fail.</p>
                      </div>
                    )}

                    {activeTab === 'behavioral' && (
                      <div className="grid h-[340px] grid-cols-1 gap-4 md:grid-cols-3">
                        <div className="rounded-2xl border border-white/5 bg-black/30 p-2 md:col-span-1">
                          <ResponsiveContainer>
                            <RadarChart outerRadius="70%" data={radar}>
                              <PolarGrid stroke="rgba(255,255,255,0.1)" />
                              <PolarAngleAxis dataKey="subject" tick={{ fill: '#a3a3a3', fontSize: 10 }} />
                              <Radar dataKey="A" stroke={Y[300]} fill={Y[400]} fillOpacity={0.25} strokeWidth={2} />
                              <Tooltip {...tip} />
                            </RadarChart>
                          </ResponsiveContainer>
                        </div>
                        <div className="relative rounded-2xl border border-white/5 bg-black/30 p-2">
                          <ResponsiveContainer>
                            <RadialBarChart innerRadius="70%" outerRadius="100%" data={[{ v: conf }]} startAngle={210} endAngle={-30}>
                              <GaugeAxis type="number" domain={[0, 100]} tick={false} />
                              <RadialBar dataKey="v" cornerRadius={20} fill={Y[400]} background={{ fill: 'rgba(255,255,255,0.06)' }} />
                            </RadialBarChart>
                          </ResponsiveContainer>
                          <div className="pointer-events-none absolute inset-0 grid place-items-center text-center">
                            <div><div className="mono text-3xl font-bold text-yellow-300">{conf}%</div><div className="text-xs text-neutral-500">confidence</div></div>
                          </div>
                        </div>
                        <div className="rounded-2xl border border-white/5 bg-black/30 p-2">
                          <ResponsiveContainer>
                            <BarChart data={bars} margin={{ top: 20, right: 10, bottom: 0, left: -20 }}>
                              <CartesianGrid strokeDasharray="3 6" stroke="rgba(255,255,255,0.06)" vertical={false} />
                              <XAxis dataKey="name" stroke="#525252" fontSize={11} />
                              <YAxis stroke="#525252" fontSize={11} />
                              <Tooltip {...tip} cursor={{ fill: 'rgba(var(--accent-rgb),0.06)' }} />
                              <Bar dataKey="count" radius={[10, 10, 0, 0]}>{bars.map((b) => <Cell key={b.name} fill={b.fill} />)}</Bar>
                            </BarChart>
                          </ResponsiveContainer>
                        </div>
                      </div>
                    )}

                    {activeTab === 'why' && (
                      <div className="custom-scrollbar h-[340px] overflow-auto pr-1">
                        <p className="mb-4 text-sm text-neutral-400">The model followed these steps to reach <span className="font-semibold text-white">{data.predicted_result}</span>:</p>
                        <ol className="space-y-2">
                          {(data.explanation || []).map((step, i) => (
                            <li key={i} className="flex gap-3 rounded-xl border border-white/10 bg-black/30 px-4 py-3 text-sm text-neutral-200">
                              <span className="mono text-yellow-400">{i + 1}</span><span>{step}</span>
                            </li>
                          ))}
                        </ol>
                        <p className="mt-5 text-xs leading-relaxed text-neutral-500">Model: {data.model_source}. Confidence is the share of training students in the same branch who had this result, slightly reduced so a small branch never reads as 100%.</p>
                      </div>
                    )}

                    {activeTab === 'hist' && (
                      <div className="h-[340px] w-full">
                        <div className="mb-3 flex flex-wrap gap-2" role="group" aria-label="Feature">
                          {FEATURES.map((f) => (
                            <button key={f.k} onClick={() => setFeat(f.k)} aria-pressed={feat === f.k}
                              className={`rounded-full px-3 py-1.5 text-xs transition ${feat === f.k ? 'bg-yellow-400 font-semibold text-black' : 'bg-white/5 text-neutral-400 hover:text-white'}`}>{f.label}</button>
                          ))}
                        </div>
                        <ResponsiveContainer width="100%" height="88%">
                          <BarChart data={hist.bins} margin={{ top: 20, right: 10, bottom: 0, left: -20 }} barGap={2}>
                            <CartesianGrid strokeDasharray="3 6" stroke="rgba(255,255,255,0.06)" vertical={false} />
                            <XAxis dataKey="label" stroke="#525252" fontSize={11} />
                            <YAxis allowDecimals={false} stroke="#525252" fontSize={11} />
                            <Tooltip {...tip} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
                            <Bar dataKey="Pass" fill="var(--pass)" radius={[6, 6, 0, 0]} />
                            <Bar dataKey="Fail" fill="var(--fail)" radius={[6, 6, 0, 0]} />
                            {hist.me && <ReferenceLine x={hist.me} stroke={Y[300]} strokeDasharray="4 4" label={{ value: 'This student', fill: Y[300], fontSize: 11, position: 'top' }} />}
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    )}

                    {activeTab === 'space' && (
                      <div className="relative h-[340px] w-full overflow-hidden rounded-2xl border border-white/5 bg-black/40">
                        <Suspense fallback={<div className="grid h-full place-items-center text-xs text-neutral-500">Loading 3D view…</div>}>
                          <Cube3D points={points} palette={palette} me={last ? { x: last.study, y: last.att, z: last.marks } : null} />
                        </Suspense>
                        <p className="pointer-events-none absolute bottom-2 left-0 right-0 text-center text-xs text-neutral-500">Circles passed, diamonds failed. Dashed lines join this student to the 5 most similar records.</p>
                      </div>
                    )}

                    {activeTab === 'liveResponse' && (
                      <div className="custom-scrollbar max-h-[720px] overflow-y-auto pr-1">
                        <LivePredictionCharts sensitivity={sensitivity} prediction={data} selectedModel={data?.selected_model || selectedModel} inputs={predictionInputs} />
                      </div>
                    )}

                    {activeTab === 'modelAnalytics' && user.role !== 'student' && (
                      <div className="custom-scrollbar max-h-[720px] overflow-y-auto pr-1">
                        <ModelAnalytics analytics={analytics} selectedModel={data.selected_model || selectedModel} prediction={data} />
                      </div>
                    )}

                    {activeTab === 'registry' && (
                      <div className="scroll h-[340px] overflow-y-auto rounded-2xl border border-white/5 bg-black/30">
                        <table className="w-full border-collapse text-left text-sm">
                          <thead className="sticky top-0 z-10 bg-neutral-950/90 text-xs text-neutral-500 backdrop-blur-xl">
                            <tr>{['Study hours', 'Attendance', 'Previous marks', 'Result'].map((h, i) => <th key={h} className={`p-3 font-medium ${i === 3 ? 'text-center' : ''}`}>{h}</th>)}</tr>
                          </thead>
                          <tbody className="mono divide-y divide-white/5 text-neutral-400">
                            {data.raw_records.map((r, i) => (
                              <tr key={i} onMouseEnter={() => setActiveRow(i)} onMouseLeave={() => setActiveRow(null)} className={`transition-colors ${activeRow === i ? 'bg-yellow-400/10 text-white' : 'hover:bg-white/[0.03]'}`}>
                                <td className="p-3 font-semibold text-yellow-400">{r.study_hours}h</td>
                                <td className="p-3">{r.attendance}%</td>
                                <td className="p-3">{r.previous_marks}</td>
                                <td className="p-3 text-center">
                                  <span className={`rounded-full px-3 py-1 text-xs font-semibold ${r.result === 'Pass' ? 'bg-white/5 text-[color:var(--pass)]' : 'bg-white/5 text-[color:var(--fail)]'}`}>{r.result}</span>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </motion.div>
                </AnimatePresence>
              </motion.div>
            )}
          </div>
        </div>
        {/* How it works */}
        <section className="py-28">
          <SectionTitle id="how" title="How it works" sub="Three steps from numbers to a result you can act on." />
          <div className="grid gap-6 md:grid-cols-3">
            {[
              [Layers, 'Enter three numbers', 'Study hours per day, attendance and the marks from the last exam.'],
              [Brain, 'The model compares', 'GradeAI checks them against its training records to find the closest matching pattern.'],
              [Trophy, 'Read the result', 'You get pass or fail, a confidence score, and charts showing where the student sits among the data.'],
            ].map(([Icon, title, text], i) => (
              <motion.div key={title} {...reveal} transition={{ duration: 0.5, delay: i * 0.1 }} className={`${glass} p-8`}>
                <div className="mb-5 flex items-center justify-between">
                  <span className="grid h-12 w-12 place-items-center rounded-2xl bg-yellow-400/10 text-yellow-300"><Icon size={22} /></span>
                  <span className="mono text-sm text-neutral-600">Step {i + 1}</span>
                </div>
                <h3 className="text-lg font-semibold text-white">{title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-neutral-400">{text}</p>
              </motion.div>
            ))}
          </div>
        </section>

        {/* Insights */}
        <section className="py-20">
          <SectionTitle id="insights" title="What drives the result" sub="The model looks at these signals together, not one at a time." />
          <div className="mb-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {[
              [BookOpen, 'Study hours', 'How long the student studies on a typical day.'],
              [CalendarCheck, 'Attendance', 'The share of classes the student attended.'],
              [Trophy, 'Previous marks', 'Where the student stood in the last exam.'],
              [Gauge, 'Confidence', 'How strongly the training records back the prediction.'],
            ].map(([Icon, title, text], i) => (
              <motion.div key={title} {...reveal} transition={{ duration: 0.5, delay: i * 0.08 }} className={`${glass} p-6`}>
                <Icon size={20} className="mb-4 text-yellow-400" />
                <h3 className="font-semibold text-white">{title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-neutral-400">{text}</p>
              </motion.div>
            ))}
          </div>
          <motion.div {...reveal}><Snapshot data={data} me={me} /></motion.div>
          <motion.div {...reveal} className="mt-8"><History history={history} /></motion.div>
        </section>

        {/* FAQ */}
        <section className="py-20">
          <SectionTitle id="faq" title="Questions" />
          <Faq />
        </section>

        {/* Closing call to action */}
        <section className="py-20">
          <motion.div {...reveal} className={`${glass} relative overflow-hidden px-8 py-16 text-center`}>
            <div className="absolute left-1/2 top-0 h-40 w-[70%] -translate-x-1/2 rounded-full bg-yellow-400/20 blur-3xl" />
            <h2 className="relative text-3xl font-bold text-white sm:text-4xl">Check a student now</h2>
            <p className="relative mx-auto mt-3 max-w-xl text-neutral-400">It takes three numbers and a few seconds.</p>
            <a href="#predict" className="relative mt-8 inline-block rounded-2xl bg-yellow-400 px-8 py-4 text-sm font-bold text-black transition hover:bg-yellow-300">Back to the predictor</a>
          </motion.div>
        </section>

        {/* Footer */}
        <footer className="flex flex-col items-center justify-between gap-4 border-t border-white/10 py-8 text-sm text-neutral-500 sm:flex-row">
          <span className="font-bold text-white">Grade<span className="text-yellow-400">AI</span></span>
          <span>Pass or fail prediction from study hours, attendance and previous marks.</span>
        </footer>
      </div>
    </div>
  );
}
