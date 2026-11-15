// Read one photo: metadata (date, GPS), fingerprints, quality metrics, faces, thumbnail.
import exifr from '../vendor/exifr.esm.js';
import { detectFaces } from './faces.js';
import { canvasToBlob, sha256 } from './util.js';

export const IMAGE_RE = /\.(jpe?g|png|heic|heif|webp|tiff?)$/i;
const FILENAME_DATE = /(20\d{2}|19\d{2})[-_.]?(0[1-9]|1[0-2])[-_.]?(0[1-9]|[12]\d|3[01])(?:[-_. ]?([01]\d|2[0-3])[-_.]?([0-5]\d)[-_.]?([0-5]\d))?/;
const ANALYSIS_SIDE = 1024;
const THUMB_SIDE = 480;

export const fileId = f => `${f.name}|${f.size}|${f.lastModified}`;
export const isImage = f => (f.type && f.type.startsWith('image/')) || IMAGE_RE.test(f.name);
const isHeic = f => /heic|heif/i.test(f.type) || /\.(heic|heif)$/i.test(f.name);

export function dateFromFilename(name) {
  const m = name.match(FILENAME_DATE);
  if (!m) return null;
  const d = new Date(+m[1], +m[2] - 1, +m[3], m[4] ? +m[4] : 12, m[5] ? +m[5] : 0, m[6] ? +m[6] : 0);
  return isNaN(d) ? null : d;
}

async function readExif(buffer) {
  try {
    const x = await exifr.parse(buffer, {
      tiff: true, exif: true, gps: true, ifd1: false, xmp: false, icc: false, iptc: false,
      pick: ['DateTimeOriginal', 'CreateDate', 'ModifyDate', 'latitude', 'longitude', 'GPSLatitude', 'GPSLongitude', 'GPSLatitudeRef', 'GPSLongitudeRef'],
    });
    if (!x) return {};
    const taken = x.DateTimeOriginal || x.CreateDate || x.ModifyDate;
    let { latitude: lat, longitude: lon } = x;
    if (lat != null && Math.abs(lat) < 1e-6 && Math.abs(lon) < 1e-6) lat = lon = null;
    return { taken: taken instanceof Date && !isNaN(taken) && taken.getFullYear() > 1990 ? taken : null, lat, lon };
  } catch {
    return {};
  }
}

let heic2anyLoaded;
async function decode(file) {
  try {
    return await createImageBitmap(file, { imageOrientation: 'from-image' });
  } catch (err) {
    if (!isHeic(file)) throw err;
    // Browsers without native HEIC support (Chrome/Firefox): convert with libheif (wasm)
    heic2anyLoaded ??= new Promise((res, rej) => {
      const s = document.createElement('script');
      s.src = new URL('../vendor/heic2any.min.js', import.meta.url).href;
      s.onload = () => res(window.heic2any); s.onerror = rej;
      document.head.append(s);
    });
    const heic2any = await heic2anyLoaded;
    // a converter that never answers must not block the whole import
    const jpeg = await Promise.race([
      heic2any({ blob: file, toType: 'image/jpeg', quality: 0.9 }),
      new Promise((_, rej) => setTimeout(() => rej(new Error('HEIC-Umwandlung: Zeitüberschreitung')), 60000)),
    ]);
    return createImageBitmap(Array.isArray(jpeg) ? jpeg[0] : jpeg);
  }
}

export function drawScaled(src, maxSide) {
  const scale = Math.min(1, maxSide / Math.max(src.width, src.height));
  const c = document.createElement('canvas');
  c.width = Math.max(1, Math.round(src.width * scale));
  c.height = Math.max(1, Math.round(src.height * scale));
  const ctx = c.getContext('2d', { willReadFrequently: true });
  ctx.imageSmoothingQuality = 'high';
  ctx.drawImage(src, 0, 0, c.width, c.height);
  return c;
}

function dhash(canvas) {
  const c = document.createElement('canvas');
  c.width = 9; c.height = 8;
  const ctx = c.getContext('2d', { willReadFrequently: true });
  ctx.drawImage(canvas, 0, 0, 9, 8);
  const d = ctx.getImageData(0, 0, 9, 8).data;
  const g = i => d[i * 4] * 0.299 + d[i * 4 + 1] * 0.587 + d[i * 4 + 2] * 0.114;
  let hex = '', nibble = 0, bits = 0;
  for (let y = 0; y < 8; y++) for (let x = 0; x < 8; x++) {
    nibble = (nibble << 1) | (g(y * 9 + x) > g(y * 9 + x + 1) ? 1 : 0);
    if (++bits === 4) { hex += nibble.toString(16); nibble = 0; bits = 0; }
  }
  return hex;
}

function grayOf(canvas) {
  const { width: w, height: h } = canvas;
  const d = canvas.getContext('2d', { willReadFrequently: true }).getImageData(0, 0, w, h).data;
  const g = new Float32Array(w * h);
  for (let i = 0; i < g.length; i++) g[i] = d[i * 4] * 0.299 + d[i * 4 + 1] * 0.587 + d[i * 4 + 2] * 0.114;
  return { g, w, h };
}

/** Variance of the Laplacian inside a region (blur measure). */
function laplacianVar({ g, w }, x0, y0, x1, y1) {
  let sum = 0, sq = 0, n = 0;
  for (let y = Math.max(1, y0); y < y1 - 1; y++) {
    for (let x = Math.max(1, x0); x < x1 - 1; x++) {
      const i = y * w + x;
      const v = g[i - 1] + g[i + 1] + g[i - w] + g[i + w] - 4 * g[i];
      sum += v; sq += v * v; n++;
    }
  }
  if (!n) return 0;
  const m = sum / n;
  return sq / n - m * m;
}

function exposure({ g }) {
  let s = 0, s2 = 0, clip = 0;
  for (const v of g) { s += v; s2 += v * v; if (v < 8 || v > 247) clip++; }
  const n = g.length, mean = s / n / 255, std = Math.sqrt(s2 / n - (s / n) ** 2);
  const score = 1 - Math.abs(mean - 0.5) * 1.6 - (clip / n) * 1.5;
  return Math.max(0, Math.min(1, 0.7 * score + 0.3 * Math.min(std / 64, 1)));
}

/**
 * hints: optional {taken: Date, lat, lon, source} from Google Takeout JSON / Google Photos picker.
 */
export async function analyzeFile(file, hints = {}) {
  const buffer = await file.arrayBuffer();
  const [sha, exif] = await Promise.all([sha256(buffer), readExif(buffer)]);
  const bmp = await decode(file);
  const w = bmp.width, h = bmp.height;
  const canvas = drawScaled(bmp, ANALYSIS_SIDE);
  bmp.close?.();

  let taken = exif.taken, dateSource = 'exif';
  if (!taken && hints.taken) { taken = hints.taken; dateSource = hints.source || 'google'; }
  if (!taken) { taken = dateFromFilename(file.name); dateSource = 'filename'; }
  if (!taken) { taken = new Date(file.lastModified); dateSource = 'file'; }
  const lat = exif.lat ?? hints.lat ?? null, lon = exif.lon ?? hints.lon ?? null;

  const faces = await detectFaces(canvas);

  // metrics on a 512px version (consistent scale for all photos)
  const small = drawScaled(canvas, 512);
  const gray = grayOf(small);
  let sharp = 0;
  for (const f of faces) {
    const [x, y, fw, fh] = f.box;
    sharp = Math.max(sharp, laplacianVar(gray, Math.round(x * gray.w), Math.round(y * gray.h),
      Math.round((x + fw) * gray.w), Math.round((y + fh) * gray.h)));
  }
  if (!faces.length) sharp = laplacianVar(gray, 0, 0, gray.w, gray.h);

  const thumb = await canvasToBlob(drawScaled(canvas, THUMB_SIDE), 0.8);
  return {
    name: file.name, size: file.size, lastModified: file.lastModified,
    sha, dhash: dhash(canvas), w, h,
    taken: taken.toISOString(), dateSource,
    lat, lon, place: '', placeSource: lat != null ? 'gps' : '',
    faces, sharp: +sharp.toFixed(1), expo: +exposure(gray).toFixed(3),
    thumb, addedAt: Date.now(),
  };
}

/** Large display version (for the book & PDF) – made while the original file is available. */
export async function makeLarge(file, side = 2000) {
  const bmp = await decode(file);
  const c = drawScaled(bmp, side);
  bmp.close?.();
  return canvasToBlob(c, 0.88);
}

/** Google Takeout writes one JSON per photo (title, photoTakenTime, geoData). */
export async function readTakeoutSidecars(files) {
  const map = new Map();
  for (const f of files) {
    if (!/\.json$/i.test(f.name)) continue;
    try {
      const j = JSON.parse(await f.text());
      if (!j.title || !j.photoTakenTime) continue;
      const geo = (j.geoData && j.geoData.latitude) ? j.geoData : j.geoDataExif;
      map.set(j.title, {
        taken: new Date(+j.photoTakenTime.timestamp * 1000),
        lat: geo && geo.latitude ? geo.latitude : null,
        lon: geo && geo.longitude ? geo.longitude : null,
        source: 'takeout',
      });
    } catch { /* not a takeout sidecar */ }
  }
  return map;
}
