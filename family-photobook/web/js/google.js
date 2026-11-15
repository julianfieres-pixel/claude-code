// Google Photos Picker API (https://developers.google.com/photos/picker/guides/get-started-picker)
// Optional: needs an OAuth client ID in config.js. The user picks photos in Google's own picker;
// we only get read access to exactly those photos. Note: Google removes GPS from downloads
// ("=d" keeps Exif except location), so places come from same-day photos or manual entry.
import { CONFIG } from '../config.js';

const SCOPE = 'https://www.googleapis.com/auth/photospicker.mediaitems.readonly';
const API = 'https://photospicker.googleapis.com/v1';

export const googleEnabled = () => Boolean(CONFIG.googleClientId);

let gisLoaded;
function loadGis() {
  gisLoaded ??= new Promise((res, rej) => {
    const s = document.createElement('script');
    s.src = 'https://accounts.google.com/gsi/client';
    s.onload = res; s.onerror = () => rej(new Error('Google-Anmeldung konnte nicht geladen werden'));
    document.head.append(s);
  });
  return gisLoaded;
}

function getToken() {
  return new Promise((resolve, reject) => {
    const client = google.accounts.oauth2.initTokenClient({
      client_id: CONFIG.googleClientId,
      scope: SCOPE,
      callback: r => (r.error ? reject(new Error(r.error)) : resolve(r.access_token)),
      error_callback: e => reject(new Error(e.message || e.type)),
    });
    client.requestAccessToken();
  });
}

const sleep = ms => new Promise(r => setTimeout(r, ms));
const secs = s => (parseFloat(s) || 3) * 1000;

/**
 * Must be called from a click handler (popups). onStatus(text) for UI updates.
 * Returns [{file, hints}] ready for analysis.
 */
export async function pickFromGooglePhotos(onStatus) {
  const popup = window.open('', 'gphotos', 'width=1000,height=800'); // open now, inside the user gesture
  try {
    await loadGis();
    onStatus('Bei Google anmelden …');
    const token = await getToken();
    const auth = { Authorization: `Bearer ${token}` };
    const session = await (await fetch(`${API}/sessions`, { method: 'POST', headers: auth })).json();
    if (!session.pickerUri) throw new Error(session.error?.message || 'Keine Picker-Sitzung');
    if (popup && !popup.closed) popup.location.href = `${session.pickerUri}/autoclose`;
    else window.open(`${session.pickerUri}/autoclose`, 'gphotos');

    onStatus('Wähle in Google Fotos die Bilder aus und tippe auf „Fertig“ …');
    let s = session;
    const deadline = Date.now() + secs(session.pollingConfig?.timeoutIn || '1800s');
    while (!s.mediaItemsSet) {
      if (Date.now() > deadline) throw new Error('Zeit für die Auswahl abgelaufen');
      await sleep(secs(s.pollingConfig?.pollInterval));
      s = await (await fetch(`${API}/sessions/${session.id}`, { headers: auth })).json();
    }

    const items = [];
    let pageToken = '';
    do {
      const qs = new URLSearchParams({ sessionId: session.id, pageSize: '100', ...(pageToken && { pageToken }) });
      const page = await (await fetch(`${API}/mediaItems?${qs}`, { headers: auth })).json();
      items.push(...(page.mediaItems || []).filter(m => m.type === 'PHOTO'));
      pageToken = page.nextPageToken;
    } while (pageToken);

    const out = [];
    for (const [i, m] of items.entries()) {
      onStatus(`Lade Foto ${i + 1} von ${items.length} aus Google Fotos …`);
      const res = await fetch(`${m.mediaFile.baseUrl}=d`, { headers: auth });
      if (!res.ok) continue;
      const blob = await res.blob();
      const taken = new Date(m.createTime);
      const file = new File([blob], m.mediaFile.filename || `${m.id}.jpg`,
        { type: m.mediaFile.mimeType || blob.type, lastModified: taken.getTime() });
      out.push({ file, hints: { taken, source: 'google' } });
    }
    fetch(`${API}/sessions/${session.id}`, { method: 'DELETE', headers: auth }).catch(() => {});
    return out;
  } finally {
    if (popup && !popup.closed) popup.close();
  }
}
