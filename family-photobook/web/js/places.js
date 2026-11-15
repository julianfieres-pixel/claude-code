// GPS -> readable place via OpenStreetMap Nominatim (max 1 request/s, cached on the device).
// https://nominatim.org/release-docs/latest/api/Reverse/  ·  https://operations.osmfoundation.org/policies/nominatim/
import * as db from './db.js';
import { dayKey } from './util.js';

const URL_ = 'https://nominatim.openstreetmap.org/reverse';
const POI = ['tourism', 'leisure', 'amenity', 'historic', 'natural', 'beach', 'aeroway'];
const CITY = ['city', 'town', 'village', 'municipality', 'hamlet'];
let last = 0, offline = false;

const key = (lat, lon) => `${lat.toFixed(3)},${lon.toFixed(3)}`;

async function lookup(lat, lon) {
  const k = key(lat, lon);
  const cached = await db.get('geo', k);
  if (cached !== undefined) return cached;
  if (offline) return null;
  const wait = 1100 - (Date.now() - last);
  if (wait > 0) await new Promise(r => setTimeout(r, wait));
  last = Date.now();
  try {
    const qs = new URLSearchParams({ lat: lat.toFixed(5), lon: lon.toFixed(5), format: 'jsonv2', zoom: 17, addressdetails: 1, 'accept-language': 'de' });
    const res = await fetch(`${URL_}?${qs}`, { referrerPolicy: 'strict-origin-when-cross-origin' });
    if (!res.ok) throw new Error(res.status);
    const data = await res.json();
    await db.put('geo', k, data);
    return data;
  } catch {
    offline = true;
    return null;
  }
}

export function formatPlace(data, home) {
  if (!data || !data.address) return '';
  const a = data.address;
  let poi = (POI.includes(data.category) || ['park', 'zoo', 'beach', 'attraction'].includes(data.type)) ? data.name : null;
  poi = poi || POI.map(k => a[k]).find(Boolean) || null;
  const city = CITY.map(k => a[k]).find(Boolean) || a.county || a.state;
  const parts = [...new Set([poi, city].filter(Boolean))];
  if (a.country && a.country_code !== home) parts.push(a.country);
  return parts.join(', ');
}

/**
 * Fill p.place for the given photos (the ones in the book).
 * - own GPS -> lookup
 * - no GPS -> borrow from the nearest photo (any in library) of the same day with GPS (within 4 h)
 * - manual places (p.placeSource === 'manual') are never overwritten
 */
export async function assignPlaces(bookPhotos, library, onProgress) {
  const withGps = library.filter(p => p.lat != null);
  const byDay = new Map();
  for (const p of withGps) {
    const k = dayKey(p.date);
    if (!byDay.has(k)) byDay.set(k, []);
    byDay.get(k).push(p);
  }
  const jobs = [];
  for (const p of bookPhotos) {
    if (p.placeSource === 'manual') continue;
    let src = p.lat != null ? p : null;
    if (!src) {
      const same = (byDay.get(dayKey(p.date)) || [])
        .map(q => [q, Math.abs(q.date - p.date)]).filter(([, d]) => d < 4 * 3600e3).sort((a, b) => a[1] - b[1]);
      src = same[0]?.[0] || null;
    }
    if (src) jobs.push([p, src]);
  }
  const results = new Map();
  let i = 0;
  for (const [, src] of jobs) {
    const k = key(src.lat, src.lon);
    if (!results.has(k)) results.set(k, await lookup(src.lat, src.lon));
    onProgress?.(++i, jobs.length);
  }
  const codes = {};
  for (const d of results.values()) if (d?.address?.country_code) codes[d.address.country_code] = (codes[d.address.country_code] || 0) + 1;
  const home = Object.entries(codes).sort((a, b) => b[1] - a[1])[0]?.[0];
  const changed = [];
  for (const [p, src] of jobs) {
    const place = formatPlace(results.get(key(src.lat, src.lon)), home);
    const source = src === p ? 'gps' : 'day';
    if (place && (place !== p.place || p.placeSource !== source)) {
      p.place = place; p.placeSource = source; changed.push(p);
    }
  }
  return { changed, offline };
}
