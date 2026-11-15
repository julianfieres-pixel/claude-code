// Duplicates, scoring, per-month top selection and print picks.
import { identify } from './faces.js';
import { dayKey, hamming, monthKey } from './util.js';

const NEAR_DUP_BITS = 4;
const SIMILAR_BITS = 12;
const SIMILAR_SECONDS = 180;
export const RESERVE = 12; // extra candidates per month kept ready for swapping

export const WEIGHTS = { people: 0.32, faces: 0.13, sharp: 0.23, expo: 0.12, res: 0.08, smile: 0.12 };

/** Attach runtime fields: date, people, score. */
export function enrich(photos, refs, personWeights) {
  for (const p of photos) {
    p.date = new Date(p.taken);
    p.month = monthKey(p.date);
    const people = new Set();
    for (const f of p.faces) {
      f.person = refs.length ? identify(f.desc, refs).person : null;
      if (f.person) people.add(f.person);
    }
    p.people = [...people];
    p.score = score(p, personWeights, refs.length > 0);
  }
}

function score(p, personWeights, hasPeople) {
  const fam = p.faces.filter(f => f.person);
  const wsum = Object.values(personWeights).reduce((a, b) => a + b, 0) || 1;
  const people = Math.min(p.people.reduce((a, k) => a + (personWeights[k] ?? 1), 0) / wsum, 1);
  const faceArea = Math.max(0, ...fam.map(f => f.box[2] * f.box[3]));
  const faces = Math.min(Math.sqrt(faceArea) / 0.35, 1);
  const sharp = Math.min(Math.log1p(p.sharp) / Math.log1p(600), 1);
  const res = Math.min((p.w * p.h) / 8e6, 1);
  const smile = fam.length ? fam.reduce((a, f) => a + f.happy, 0) / fam.length : 0;
  const strangers = p.faces.filter(f => !f.person && f.box[2] * f.box[3] > 0.002).length;
  const w = { ...WEIGHTS };
  if (!hasPeople) { w.people = 0; w.faces = 0; w.smile = 0; }
  const total = (w.people * people + w.faces * faces + w.sharp * sharp + w.expo * p.expo + w.res * res + w.smile * smile)
    / Object.values(w).reduce((a, b) => a + b, 0);
  return Math.round(100 * Math.max(0, total - Math.min(strangers * 0.03, 0.15)) * 10) / 10;
}

const originalFirst = p => (p.dateSource === 'exif' || p.dateSource === 'takeout' ? 1 : 0);

/** Marks p.dupOf (id of kept photo). Exact: same bytes. Near: same picture, re-saved / burst. */
export function markDuplicates(photos) {
  const pairs = [];
  for (const p of photos) p.dupOf = null;
  const bySha = new Map();
  for (const p of photos) {
    const prev = bySha.get(p.sha);
    if (!prev) { bySha.set(p.sha, p); continue; }
    const [keep, drop] = p.w * p.h > prev.w * prev.h ? [p, prev] : [prev, p];
    drop.dupOf = keep.id; bySha.set(p.sha, keep); pairs.push([drop, keep]);
  }
  const rest = photos.filter(p => !p.dupOf).sort((a, b) => a.date - b.date);
  const better = (a, b) => (originalFirst(a) - originalFirst(b)) || (a.score - b.score) || (a.w * a.h - b.w * b.h);
  for (let i = 0; i < rest.length; i++) {
    const p = rest[i];
    if (p.dupOf) continue;
    for (let j = i + 1; j < rest.length; j++) {
      const q = rest[j];
      const dt = (q.date - p.date) / 1000;
      if (dt > 86400) break;
      const limit = originalFirst(p) && originalFirst(q) ? 120 : 86400;
      if (dt > limit || q.dupOf || hamming(p.dhash, q.dhash) > NEAR_DUP_BITS) continue;
      const [keep, drop] = better(p, q) >= 0 ? [p, q] : [q, p];
      drop.dupOf = keep.id; pairs.push([drop, keep]);
      if (drop === p) break;
    }
  }
  return pairs;
}

const similar = (a, b) => Math.abs(a.date - b.date) / 1000 <= SIMILAR_SECONDS && hamming(a.dhash, b.dhash) <= SIMILAR_BITS;

function pickTop(cands, n, pinned) {
  const ranked = [...cands].sort((a, b) => b.score - a.score);
  const chosen = [...pinned];
  const skipped = [];
  for (const p of ranked) {
    if (chosen.length >= n) break;
    if (chosen.includes(p)) continue;
    if (chosen.some(c => similar(c, p))) skipped.push(p); else chosen.push(p);
  }
  for (const p of skipped) { if (chosen.length >= n) break; chosen.push(p); }
  return chosen;
}

function pickPrint(top, k, forced, minSide = 1200) {
  const picks = top.filter(p => forced.has(p.id));
  const pool = top.filter(p => Math.min(p.w, p.h) >= minSide && !picks.includes(p));
  const ranked = (pool.length ? pool : top.filter(p => !picks.includes(p))).sort((a, b) => b.score - a.score);
  if (!picks.length && ranked.length) {
    const most = Math.max(...ranked.map(p => p.people.length));
    picks.push(ranked.find(p => p.people.length === most));
  }
  while (picks.length < k) {
    const rest = ranked.filter(p => !picks.includes(p));
    if (!rest.length) break;
    const covered = new Set(picks.flatMap(q => q.people));
    const bonus = p => p.score
      + (picks.every(q => dayKey(q.date) !== dayKey(p.date)) ? 8 : 0)
      + (p.place && picks.every(q => q.place !== p.place) ? 4 : 0)
      + (p.people.some(x => !covered.has(x)) ? 4 : 0);
    picks.push(rest.reduce((a, b) => (bonus(b) > bonus(a) ? b : a)));
  }
  return picks;
}

/**
 * overrides: {[id]: {excluded?, pinned?, print?: true|false}}
 * Returns [{key, total, top:[photo], print:Set(id), reserve:[photo]}] sorted by month.
 */
export function buildBook(photos, { perMonth, prints, requirePeople, overrides }) {
  const months = new Map();
  for (const p of photos) {
    if (p.dupOf) continue;
    if (!months.has(p.month)) months.set(p.month, []);
    months.get(p.month).push(p);
  }
  const out = [];
  for (const [key, items] of [...months].sort((a, b) => a[0].localeCompare(b[0]))) {
    const ok = items.filter(p => !overrides[p.id]?.excluded);
    let cands = requirePeople ? ok.filter(p => p.people.length) : ok;
    if (requirePeople && cands.length < Math.min(perMonth, 6)) {
      // too few family photos this month: top up with the best other photos
      cands = cands.concat(ok.filter(p => !p.people.length).sort((a, b) => b.score - a.score).slice(0, perMonth - cands.length));
    }
    if (!cands.length) continue;
    const pinned = cands.filter(p => overrides[p.id]?.pinned);
    const top = pickTop(cands, perMonth, pinned).sort((a, b) => a.date - b.date);
    const forced = new Set(top.filter(p => overrides[p.id]?.print === true).map(p => p.id));
    const blocked = new Set(top.filter(p => overrides[p.id]?.print === false).map(p => p.id));
    const printPicks = pickPrint(top.filter(p => !blocked.has(p.id)), Math.max(prints, forced.size), forced);
    const reserve = cands.filter(p => !top.includes(p)).sort((a, b) => b.score - a.score).slice(0, RESERVE);
    out.push({ key, total: items.length, top, print: new Set(printPicks.map(p => p.id)), reserve });
  }
  return out;
}
