// Getting photos out: share sheet (iPhone/Android), ZIP download (computer), print/PDF.
import * as db from './db.js';
import { monthTitle } from './util.js';

function exportName(p, i, ext) {
  const d = p.date;
  const stamp = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  return `${stamp}_${String(i).padStart(2, '0')}${ext}`;
}

/** Best available image: original file (this session) > stored original > large version > thumbnail. */
export async function bestBlob(p, files) {
  const f = files.get(p.id);
  if (f) return { blob: f, quality: 'original' };
  const a = await db.get('assets', p.id);
  if (a?.original) return { blob: a.original, quality: 'original' };
  if (a?.large) return { blob: a.large, quality: 'large' };
  return { blob: p.thumb, quality: 'thumb' };
}

const extOf = (blob, name) => (blob.type === 'image/jpeg' && !/\.jpe?g$/i.test(name) ? '.jpg'
  : (name.match(/\.[a-z0-9]+$/i)?.[0] || '.jpg').toLowerCase());

export async function collect(book, files, which) {
  const list = [];
  for (const m of book) {
    const items = which === 'print' ? m.top.filter(p => m.print.has(p.id)) : m.top;
    let i = 0;
    for (const p of items) {
      const { blob, quality } = await bestBlob(p, files);
      list.push({ month: m.key, name: exportName(p, ++i, extOf(blob, p.name)), blob, quality, p });
    }
  }
  return list;
}

export function canShareFiles(sample) {
  try { return !!navigator.canShare && navigator.canShare({ files: [sample] }); } catch { return false; }
}

export async function share(list, title) {
  const files = list.map(x => new File([x.blob], x.name, { type: x.blob.type || 'image/jpeg' }));
  await navigator.share({ files, title });
}

let zipLoaded;
export async function downloadZip(list, filename, onProgress) {
  zipLoaded ??= new Promise((res, rej) => {
    const s = document.createElement('script');
    s.src = new URL('../vendor/jszip.min.js', import.meta.url).href;
    s.onload = () => res(window.JSZip); s.onerror = rej;
    document.head.append(s);
  });
  const JSZip = await zipLoaded;
  const zip = new JSZip();
  for (const x of list) zip.folder(monthTitle(x.month)).file(x.name, x.blob);
  const blob = await zip.generateAsync({ type: 'blob', compression: 'STORE' }, meta => onProgress?.(meta.percent));
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 60_000);
}
