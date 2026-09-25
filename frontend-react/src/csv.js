// Small CSV helpers (no dependency). Handles quoted cells, doubled quotes and Windows line endings.
export function parseCsv(text) {
  const rows = []; let row = [], cell = '', quoted = false;
  const endRow = () => { row.push(cell); cell = ''; if (row.some((x) => x.trim() !== '')) rows.push(row); row = []; };
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (c === '"' && text[i + 1] === '"') { cell += '"'; i++; } else if (c === '"') quoted = false; else cell += c;
    } else if (c === '"') quoted = true;
    else if (c === ',') { row.push(cell); cell = ''; }
    else if (c === '\n' || c === '\r') { if (c === '\r' && text[i + 1] === '\n') i++; endRow(); }
    else cell += c;
  }
  if (cell !== '' || row.length) endRow();
  if (!rows.length) return [];
  const head = rows.shift().map((h) => h.replace(/^\ufeff/, '').trim().toLowerCase().replace(/[\s-]+/g, '_'));
  return rows.map((r) => Object.fromEntries(head.map((h, i) => [h, (r[i] ?? '').trim()])));
}

// First non-empty value among possible column names
export const pick = (row, names) => { for (const n of names) if (row[n] !== undefined && row[n] !== '') return row[n]; return ''; };

// Cells starting with = + - @ would run as formulas in Excel, so they are prefixed with an apostrophe
const safe = (v) => { const s = String(v ?? ''); return /^[=+\-@\t\r]/.test(s) ? `'${s}` : s; };
export function toCsv(rows, columns) {
  const esc = (v) => { const s = safe(v); return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
  return [columns.join(','), ...rows.map((r) => columns.map((c) => esc(r[c])).join(','))].join('\n');
}

export function saveText(text, filename, type = 'text/csv') {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement('a'); a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}
