import React, { useEffect, useMemo, useState } from 'react';
import {
  Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Scatter, ScatterChart,
  Tooltip, XAxis, YAxis, ReferenceLine
} from 'recharts';

const panel = 'rounded-2xl border border-white/10 bg-black/30 p-5';
const colors = ['#e9bd54', '#61b995', '#d77d6b', '#8c9fe8', '#b68ad6', '#64b8c4'];

const labelFeature = (key) => ({
  StudyHours: 'Study hours', Attendance: 'Attendance', PreviousMarks: 'Previous marks',
  study_hours: 'Study hours', attendance: 'Attendance', previous_marks: 'Previous marks',
}[key] || key);

function Metric({ label, value, detail }) {
  return <div className={panel}>
    <p className="text-xs uppercase tracking-wide text-neutral-500">{label}</p>
    <p className="mono mt-2 text-2xl font-bold text-white">{value}</p>
    {detail && <p className="mt-1 text-xs leading-relaxed text-neutral-500">{detail}</p>}
  </div>;
}

function ChartTitle({ title, note }) {
  return <div className="mb-4">
    <h3 className="font-semibold text-white">{title}</h3>
    {note && <p className="mt-1 text-xs leading-relaxed text-neutral-500">{note}</p>}
  </div>;
}

const tooltipStyle = {
  contentStyle: { background: '#111', border: '1px solid rgba(255,255,255,.15)', borderRadius: 12, color: '#eee', fontSize: 12 },
};

export default function ModelAnalytics({ analytics, selectedModel, prediction, api }) {
  const [trainingPredictions, setTrainingPredictions] = useState(null);
  const [trainingPredictionsError, setTrainingPredictionsError] = useState('');
  useEffect(() => {
    if (typeof api !== 'function') return;
    setTrainingPredictions(null);
    setTrainingPredictionsError('');
    api('/predict/training-predictions?model=' + encodeURIComponent(selectedModel || 'decision_tree'))
      .then(setTrainingPredictions)
      .catch((error) => setTrainingPredictionsError(error?.message || 'Could not load model-specific training predictions.'));
  }, [api, selectedModel]);
  const summary = analytics?.summary || {};
  const pca = analytics?.pca;
  const cluster = analytics?.clustering;
  const pcaRows = useMemo(() => {
    if (!Array.isArray(pca?.scores)) return [];
    const records = Array.isArray(cluster?.records) ? cluster.records : [];
    return pca.scores.map((score, i) => ({
      pc1: Number(score?.[0] ?? 0),
      pc2: Number(score?.[1] ?? 0),
      result: records[i]?.result || 'Unknown',
      cluster: records[i]?.cluster ?? null,
      index: i + 1,
    }));
  }, [pca, cluster]);
  const importance = Object.entries(summary.tree?.variable_importance || {})
    .map(([feature, value]) => ({ feature: labelFeature(feature), importance: Number(value) }))
    .sort((a, b) => b.importance - a.importance);
  const weights = analytics?.regression?.weights || {};
  const coefficients = Object.entries(weights)
    .map(([feature, value]) => ({ feature: feature === 'intercept' ? 'Intercept' : labelFeature(feature), coefficient: Number(value) }))
    .filter((item) => Number.isFinite(item.coefficient));
  const clusterSizes = Array.isArray(cluster?.cluster_sizes)
    ? cluster.cluster_sizes.map((size, i) => ({ name: 'Cluster ' + (i + 1), count: Number(size) }))
    : [];
  const clusterProfiles = useMemo(() => {
    const records = Array.isArray(cluster?.records) ? cluster.records : [];
    const groups = new Map();
    records.forEach((r) => {
      const id = Number(r.cluster);
      if (!groups.has(id)) groups.set(id, { cluster: 'Cluster ' + id, count: 0, study_hours: 0, attendance: 0, previous_marks: 0, pass: 0 });
      const g = groups.get(id); g.count += 1;
      g.study_hours += Number(r.study_hours || 0); g.attendance += Number(r.attendance || 0); g.previous_marks += Number(r.previous_marks || 0);
      if (r.result === 'Pass') g.pass += 1;
    });
    return [...groups.values()].map((g) => ({
      ...g, study_hours: +(g.study_hours / g.count).toFixed(2),
      attendance: +(g.attendance / g.count).toFixed(2),
      previous_marks: +(g.previous_marks / g.count).toFixed(2),
      pass_rate: +(100 * g.pass / g.count).toFixed(1),
    })).sort((a, b) => a.cluster.localeCompare(b.cluster));
  }, [cluster]);
  const variance = pca?.metadata?.explained_variance || summary.pca?.explained_variance || [];
  const varianceRows = variance.map((v, i) => ({ component: 'PC' + (i + 1), variance: +(Number(v) * 100).toFixed(2) }));
  const trainedAt = summary.trained_at ? new Date(summary.trained_at).toLocaleString() : 'Not available';
  const modelName = ({ decision_tree: 'Decision Tree', linear_regression: 'Linear Regression', kmeans: 'K-Means + cluster label mapping', pca_knn: 'PCA + nearest-neighbour' })[selectedModel] || selectedModel;

  if (!analytics || !summary || Object.keys(summary).length === 0) {
    return <div className={panel}><p className="font-semibold text-white">Model analytics are not available yet.</p><p className="mt-2 text-sm text-neutral-400">Run the R training workflow and make sure its JSON artifacts are deployed to backend/model_store.</p></div>;
  }

  return <div className="space-y-5">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div><h2 className="text-xl font-bold text-white">Training & model analytics</h2>
        <p className="mt-1 max-w-3xl text-sm text-neutral-400">Exploratory charts describe the synthetic training data and fitted artifacts; they are not independent model validation. Do not use these demo metrics for high-stakes student decisions.</p></div>
      <span className="rounded-full border border-yellow-400/30 bg-yellow-400/10 px-3 py-1.5 text-xs font-semibold text-yellow-200">Prediction model: {modelName}</span>
    </div>

    {prediction && <div className="rounded-2xl border border-yellow-400/20 bg-yellow-400/[0.05] p-4">
      <p className="text-xs uppercase tracking-wide text-yellow-200/70">Latest prediction using {modelName}</p>
      <div className="mt-2 flex flex-wrap items-center gap-4">
        <span className="text-lg font-bold text-white">{prediction.predicted_result}</span>
        <span className="text-sm text-neutral-300">Pass probability: {(Number(prediction.pass_probability || 0) * 100).toFixed(1)}%</span>
        <span className="text-sm text-neutral-300">Confidence proxy: {(Number(prediction.confidence_score || 0) * 100).toFixed(1)}%</span>
      </div>
    </div>}

    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <Metric label="Training rows" value={summary.total_records ?? '—'} detail="Records used by the current training artifacts" />
      <Metric label="Pass records" value={summary.result_counts?.Pass ?? 0} detail="Training label count" />
      <Metric label="Fail records" value={summary.result_counts?.Fail ?? 0} detail="Training label count" />
      <Metric label="Trained at" value={trainedAt} detail="Timestamp embedded in the summary artifact" />
    </div>

    {summary.validation && <section className={panel}>
      <ChartTitle title="Held-out evaluation" note={`Stratified 80/20 hold-out · ${summary.validation.test_rows} test rows · seed ${summary.validation.seed}. These are synthetic-demo results, not evidence of real-world student performance.`} />
      <div className="grid gap-4 lg:grid-cols-2">
        {[
          ['Decision Tree', summary.validation.decision_tree],
          ['Linear probability model', summary.validation.linear_regression],
        ].map(([name, result]) => result && <div key={name} className="rounded-xl border border-white/10 bg-black/20 p-4">
          <h4 className="mb-3 font-semibold text-white">{name}</h4>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {[
              ['Accuracy', result.accuracy], ['Precision', result.precision], ['Recall', result.recall],
              ['F1', result.f1], ['ROC-AUC', result.roc_auc], ['Brier score', result.brier_score], ['ECE', result.calibration?.expected_calibration_error],
            ].map(([label, value]) => <div key={label} className="rounded-lg bg-white/[0.03] p-3">
              <p className="text-[10px] uppercase tracking-wide text-neutral-500">{label}</p>
              <p className="mono mt-1 text-lg font-semibold text-white">{Number.isFinite(Number(value)) ? Number(value).toFixed(3) : 'N/A'}</p>
            </div>)}
          </div>
          <p className="mt-3 text-xs text-neutral-500">Majority-class baseline accuracy: {Number(result.baseline_majority_accuracy ?? 0).toFixed(3)}</p>
          {Array.isArray(result.calibration?.bins) && <details className="mt-3 rounded-lg border border-white/10 p-3">
            <summary className="cursor-pointer text-xs font-medium text-neutral-300">Reliability bins (held-out)</summary>
            <div className="mt-2 overflow-x-auto">
              <table className="w-full text-xs text-neutral-400">
                <thead><tr><th className="p-2 text-left">Score bin</th><th className="p-2 text-right">N</th><th className="p-2 text-right">Mean score</th><th className="p-2 text-right">Observed Pass</th></tr></thead>
                <tbody>{result.calibration.bins.map((bin) => <tr key={bin.bin}><td className="p-2">{bin.bin}</td><td className="p-2 text-right">{bin.count}</td><td className="p-2 text-right">{bin.count ? Number(bin.mean_predicted).toFixed(3) : '—'}</td><td className="p-2 text-right">{bin.count ? Number(bin.observed_pass_rate).toFixed(3) : '—'}</td></tr>)}</tbody>
              </table>
            </div>
            <p className="mt-2 text-xs text-neutral-500">{result.calibration.note}</p>
          </details>}
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-xs text-neutral-300">
              <thead><tr><th className="p-2 text-left font-medium text-neutral-500">Actual / predicted</th><th className="p-2">Fail</th><th className="p-2">Pass</th></tr></thead>
              <tbody>
                <tr><td className="p-2">Fail</td><td className="p-2 text-center">{result.confusion_matrix?.rows?.actual_Fail?.predicted_Fail ?? '—'}</td><td className="p-2 text-center">{result.confusion_matrix?.rows?.actual_Fail?.predicted_Pass ?? '—'}</td></tr>
                <tr><td className="p-2">Pass</td><td className="p-2 text-center">{result.confusion_matrix?.rows?.actual_Pass?.predicted_Fail ?? '—'}</td><td className="p-2 text-center">{result.confusion_matrix?.rows?.actual_Pass?.predicted_Pass ?? '—'}</td></tr>
              </tbody>
            </table>
          </div>
        </div>)}
      </div>
      <p className="mt-4 text-xs leading-relaxed text-neutral-500">Metrics are from a single held-out split; no cross-validation or probability-calibration procedure is claimed. The training artifacts used by the app are refit on the full dataset after evaluation. PCA and K-Means remain descriptive and are not assigned classifier accuracy.</p>
    </section>}

    <section className={panel}>
      <ChartTitle title="Selected-model predictions on the reference records" note="This distribution runs the selected model over each synthetic training row. It is an in-sample description, not a held-out score or a live-student population estimate." />
      {trainingPredictionsError && <p className="text-sm text-red-300">{trainingPredictionsError}</p>}
      {!trainingPredictions && !trainingPredictionsError && <p className="text-sm text-neutral-500">Loading selected-model predictions…</p>}
      {trainingPredictions && <div className="grid gap-4 md:grid-cols-3">
        <Metric label="Predicted Pass" value={trainingPredictions.predicted_pass ?? '—'} detail="Selected model output across training rows" />
        <Metric label="Predicted Fail" value={trainingPredictions.predicted_fail ?? '—'} detail="Selected model output across training rows" />
        <Metric label="Training match rate" value={Number.isFinite(Number(trainingPredictions.training_match_rate)) ? (Number(trainingPredictions.training_match_rate) * 100).toFixed(1) + '%' : 'N/A'} detail="In-sample only; not generalization" />
      </div>}
      {trainingPredictions && <p className="mt-3 text-xs leading-relaxed text-neutral-500">{trainingPredictions.warning} Source: {trainingPredictions.source}. Total rows: {trainingPredictions.total_records}.</p>}
    </section>

    <div className="grid gap-5 xl:grid-cols-2">
      <div className={panel}>
        <ChartTitle title="PCA projection: PC1 vs PC2" note="Each dot is one training record projected onto the first two principal components. Color denotes the recorded Pass/Fail label; hover for its cluster and row." />
        <div className="h-[330px]">
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart margin={{ top: 8, right: 18, bottom: 16, left: 0 }}>
              <CartesianGrid strokeDasharray="3 5" stroke="#292929" />
              <XAxis type="number" dataKey="pc1" name="PC1" stroke="#777" fontSize={11} label={{ value: 'PC1', position: 'insideBottom', offset: -8, fill: '#888' }} />
              <YAxis type="number" dataKey="pc2" name="PC2" stroke="#777" fontSize={11} label={{ value: 'PC2', angle: -90, position: 'insideLeft', fill: '#888' }} />
              <Tooltip {...tooltipStyle} formatter={(value, name) => [Number(value).toFixed(3), name]} />
              <Scatter name="Pass" data={pcaRows.filter((r) => r.result === 'Pass')} fill="#61b995" />
              <Scatter name="Fail" data={pcaRows.filter((r) => r.result === 'Fail')} fill="#d77d6b" />
            </ScatterChart>
          </ResponsiveContainer>
        </div>
        {!pcaRows.length && <p className="text-xs text-amber-300">PCA scores are missing from the deployed artifact.</p>}
      </div>

      <div className={panel}>
        <ChartTitle title="PCA explained variance" note="Share of standardized feature variance represented by each principal component." />
        <div className="h-[330px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={varianceRows} margin={{ top: 10, right: 12, bottom: 8, left: -12 }}>
              <CartesianGrid strokeDasharray="3 5" stroke="#292929" vertical={false} />
              <XAxis dataKey="component" stroke="#777" fontSize={11} />
              <YAxis stroke="#777" fontSize={11} unit="%" />
              <Tooltip {...tooltipStyle} formatter={(v) => [v + '%', 'Explained variance']} />
              <Bar dataKey="variance" radius={[7, 7, 0, 0]}>{varianceRows.map((r, i) => <Cell key={r.component} fill={colors[i % colors.length]} />)}</Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <p className="text-xs text-neutral-500">PC1 + PC2 explain {varianceRows.slice(0, 2).reduce((s, r) => s + r.variance, 0).toFixed(2)}% of the variance.</p>
      </div>

      <div className={panel}>
        <ChartTitle title="K-Means cluster sizes" note="Unsupervised groups from the training records. Cluster IDs are arbitrary group labels, not student grades." />
        <div className="h-[280px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={clusterSizes} margin={{ top: 10, right: 12, bottom: 8, left: -12 }}>
              <CartesianGrid strokeDasharray="3 5" stroke="#292929" vertical={false} />
              <XAxis dataKey="name" stroke="#777" fontSize={11} />
              <YAxis allowDecimals={false} stroke="#777" fontSize={11} />
              <Tooltip {...tooltipStyle} />
              <Bar dataKey="count" name="Training records" radius={[7, 7, 0, 0]}>{clusterSizes.map((r, i) => <Cell key={r.name} fill={colors[i % colors.length]} />)}</Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="text-neutral-500"><tr>{['Cluster', 'Avg hours', 'Avg attendance', 'Avg marks', 'Pass rate'].map((h) => <th key={h} className="p-2 font-medium">{h}</th>)}</tr></thead>
            <tbody className="divide-y divide-white/5 text-neutral-300">
              {clusterProfiles.map((r) => <tr key={r.cluster}><td className="p-2">{r.cluster}</td><td className="p-2">{r.study_hours}</td><td className="p-2">{r.attendance}%</td><td className="p-2">{r.previous_marks}</td><td className="p-2">{r.pass_rate}%</td></tr>)}
            </tbody>
          </table>
        </div>
      </div>

      <div className={panel}>
        <ChartTitle title={selectedModel === 'decision_tree' ? 'Decision Tree feature importance' : 'Decision Tree feature importance (reference)'} note="Relative importance reported by the trained tree artifact; not a causal effect." />
        <div className="h-[280px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={importance} layout="vertical" margin={{ top: 8, right: 20, bottom: 8, left: 12 }}>
              <CartesianGrid strokeDasharray="3 5" stroke="#292929" horizontal={false} />
              <XAxis type="number" stroke="#777" fontSize={11} />
              <YAxis type="category" dataKey="feature" width={115} stroke="#aaa" fontSize={11} />
              <Tooltip {...tooltipStyle} />
              <Bar dataKey="importance" name="Relative importance" radius={[0, 7, 7, 0]}>{importance.map((r, i) => <Cell key={r.feature} fill={colors[i % colors.length]} />)}</Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <p className="text-xs text-neutral-500">In-sample training accuracy: {(Number(summary.tree?.accuracy ?? 0) * 100).toFixed(1)}%. This is descriptive only; use the held-out evaluation panel above for the provided split, and do not treat synthetic-demo metrics as real-world performance.</p>
      </div>

      <div className={panel + ' xl:col-span-2'}>
        <ChartTitle title={selectedModel === 'linear_regression' ? 'Linear Regression coefficients (selected model)' : 'Linear Regression coefficients (reference model)'} note="The model fits Pass=1 / Fail=0 as a linear probability score, clipped to [0,1]. It does not predict exam marks." />
        <div className="grid gap-5 lg:grid-cols-[1.2fr_1fr]">
          <div className="h-[320px] min-w-0">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={coefficients} layout="vertical" margin={{ top: 12, right: 28, bottom: 12, left: 18 }}>
                <CartesianGrid strokeDasharray="3 5" stroke="#292929" horizontal={false} />
                <XAxis type="number" stroke="#888" fontSize={11} domain={['auto', 'auto']} tickFormatter={(v) => Number(v).toFixed(2)} />
                <YAxis type="category" dataKey="feature" stroke="#bbb" fontSize={11} width={125} />
                <ReferenceLine x={0} stroke="#f3f4f6" strokeWidth={1.5} />
                <Tooltip {...tooltipStyle} formatter={(v) => [Number(v).toFixed(5), 'Coefficient']} />
                <Bar dataKey="coefficient" name="Coefficient" radius={[0, 6, 6, 0]} isAnimationActive={false}>
                  {coefficients.map((r) => <Cell key={r.feature} fill={r.coefficient < 0 ? '#ef746b' : '#55c59a'} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="grid content-start gap-3 sm:grid-cols-2 lg:grid-cols-1">
            <Metric label="Training R-squared" value={Number(summary.regression?.r_squared ?? 0).toFixed(3)} detail="In-sample fit to binary pass/fail labels; not validation performance" />
            <Metric label="Training RMSE" value={Number(summary.regression?.rmse ?? 0).toFixed(3)} detail="In-sample error on a 0/1 target; not exam-mark error or calibrated probability error" />
            <p className="text-xs leading-relaxed text-neutral-500">{summary.dataset_note || 'Metrics describe the dataset used to train these artifacts.'}</p>
          </div>
        </div>
      </div>
    </div>
    <p className="text-xs leading-relaxed text-neutral-600">Artifacts trained: {summary.tree?.accuracy !== undefined ? 'Decision Tree' : 'Tree metrics unavailable'} · {summary.regression ? 'Linear Regression' : 'Regression metrics unavailable'} · {pca ? 'PCA' : 'PCA unavailable'} · {cluster ? 'K-Means' : 'K-Means unavailable'}. Values reflect the currently deployed JSON artifacts; they update only after training artifacts are refreshed and deployed.</p>
  </div>;
}
