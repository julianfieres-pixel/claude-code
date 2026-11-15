export const MONTHS = ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August',
  'September', 'Oktober', 'November', 'Dezember'];

export const monthKey = d => d ? `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}` : 'unbekannt';

export function monthTitle(key) {
  if (key === 'unbekannt') return 'Ohne Datum';
  const [y, m] = key.split('-');
  return `${MONTHS[+m - 1]} ${y}`;
}

export function dateDe(d, approx = false) {
  if (!d) return '';
  return `${d.getDate()}. ${MONTHS[d.getMonth()]} ${d.getFullYear()}${approx ? ' (ungefähr)' : ''}`;
}

export const dayKey = d => d ? `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}` : '';

export const yieldUI = () => new Promise(r => setTimeout(r, 0));

export const fmtNum = n => n.toLocaleString('de-DE');

export async function sha256(buffer) {
  const h = await crypto.subtle.digest('SHA-256', buffer);
  return [...new Uint8Array(h)].map(b => b.toString(16).padStart(2, '0')).join('');
}

export function hamming(a, b) {
  // a, b: 16-char hex strings (64-bit dHash)
  let n = 0;
  for (let i = 0; i < 16; i += 4) {
    let x = parseInt(a.slice(i, i + 4), 16) ^ parseInt(b.slice(i, i + 4), 16);
    while (x) { n += x & 1; x >>= 1; }
  }
  return n;
}

export function canvasToBlob(canvas, quality = 0.85) {
  return new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', quality));
}

export function el(tag, attrs = {}, ...children) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === 'class') e.className = v;
    else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
    else if (k === 'html') e.innerHTML = v;
    else e.setAttribute(k, v === true ? '' : v);
  }
  for (const c of children.flat()) if (c != null && c !== false) e.append(c.nodeType ? c : document.createTextNode(c));
  return e;
}

// object URLs for blobs, cached per key so we do not leak memory
const urlCache = new Map();
export function blobUrl(key, blob) {
  if (!blob) return '';
  let u = urlCache.get(key);
  if (!u || u.blob !== blob) {
    if (u) URL.revokeObjectURL(u.url);
    u = { blob, url: URL.createObjectURL(blob) };
    urlCache.set(key, u);
  }
  return u.url;
}

export const isTouch = () => matchMedia('(pointer: coarse)').matches;
export const isIOS = () => /iPad|iPhone|iPod/.test(navigator.userAgent) ||
  (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
