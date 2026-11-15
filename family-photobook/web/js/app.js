// Unser Fotojahr – UI & orchestration
import * as db from './db.js';
import { CLUSTER_DIST, clusterFaces, dist, labelForCluster, loadModels } from './faces.js';
import { analyzeFile, fileId, isImage, makeLarge, readTakeoutSidecars } from './ingest.js';
import { buildBook, enrich, markDuplicates } from './select.js';
import { assignPlaces } from './places.js';
import { googleEnabled, pickFromGooglePhotos } from './google.js';
import * as ex from './export.js';
import { blobUrl, dateDe, dayKey, el, fmtNum, isIOS, isTouch, monthTitle, yieldUI } from './util.js';

const PERSONS = ['a', 'b', 'c'];
const PCOLOR = { a: 'var(--p-a)', b: 'var(--p-b)', c: 'var(--p-c)' };
const DEFAULTS = {
  title: 'Unser Jahr', names: { a: 'Papa', b: 'Mama', c: 'Sohn' }, focus: 'c', perMonth: 25, prints: 3,
  refs: [], overrides: {}, placeNoticeHidden: false, lookupPlaces: true,
};
const S = {
  photos: new Map(), files: new Map(), assets: new Map(), settings: structuredClone(DEFAULTS),
  book: [], clusters: null, dupCount: 0, view: 'welcome', showAllFaces: false, bgRunning: false,
};
const app = document.getElementById('app');

// ---------------------------------------------------------------- icons
const P = {
  phone: '<rect x="6" y="2.5" width="12" height="19" rx="2.5"/><path d="M10.5 18.5h3"/>',
  google: '<path d="M12 3a9 9 0 1 0 8.6 11.6"/><path d="M12 12h8.6"/><path d="M12 3c2.5 0 4.7 1 6.4 2.6"/>',
  folder: '<path d="M3 7.5A2.5 2.5 0 0 1 5.5 5H9l2 2.5h7.5A2.5 2.5 0 0 1 21 10v7.5a2.5 2.5 0 0 1-2.5 2.5h-13A2.5 2.5 0 0 1 3 17.5z"/>',
  lock: '<rect x="4.5" y="10.5" width="15" height="10" rx="2.5"/><path d="M8 10.5V7.5a4 4 0 0 1 8 0v3"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><circle cx="17" cy="9" r="2.5"/><path d="M17 14.5a4.5 4.5 0 0 1 4.5 4.5"/>',
  sliders: '<path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0"/><circle cx="16" cy="6" r="2"/><circle cx="10" cy="12" r="2"/><circle cx="18" cy="18" r="2"/>',
  share: '<path d="M12 3v12M7.5 7.5 12 3l4.5 4.5"/><path d="M5 12v6.5A2.5 2.5 0 0 0 7.5 21h9a2.5 2.5 0 0 0 2.5-2.5V12"/>',
  printer: '<path d="M7 9V3h10v6"/><rect x="3" y="9" width="18" height="8" rx="2"/><path d="M7 14h10v7H7z"/>',
  star: '<path d="m12 3 2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1-4.4-4.3 6.1-.9z"/>',
  x: '<path d="M6 6l12 12M18 6 6 18"/>',
  pin: '<path d="M12 21s-7-6.2-7-11.5a7 7 0 0 1 14 0C19 14.8 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.5"/>',
  left: '<path d="m15 5-7 7 7 7"/>', right: '<path d="m9 5 7 7-7 7"/>',
  trash: '<path d="M4 7h16M9 7V4.5h6V7M6.5 7l1 13h9l1-13"/>',
  check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 7.5v.5"/>',
  download: '<path d="M12 3v12M7.5 10.5 12 15l4.5-4.5"/><path d="M5 19.5h14"/>',
  book: '<path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5z"/><path d="M4 20.5A2.5 2.5 0 0 0 6.5 23H20v-5"/>',
};
const icon = (name, cls = 'icon') => el('span', { html: `<svg class="${cls}" viewBox="0 0 24 24" aria-hidden="true">${P[name]}</svg>`, style: 'display:inline-flex' });
const LOGO = '<svg viewBox="0 0 32 32" aria-hidden="true"><rect x="3" y="5" width="22" height="22" rx="4" fill="var(--accent)" transform="rotate(-8 14 16)"/><rect x="8" y="5" width="21" height="21" rx="4" fill="var(--card)" stroke="var(--ink)" stroke-width="1.6"/><circle cx="15" cy="13" r="2.6" fill="var(--p-a)"/><circle cx="21.5" cy="13.8" r="2.2" fill="var(--p-b)"/><circle cx="18" cy="18.5" r="1.8" fill="var(--p-c)"/></svg>';

// ---------------------------------------------------------------- helpers
const name = k => S.settings.names[k] || k;
const hasPeople = () => S.settings.refs.some(r => r.person !== 'other');
const live = () => [...S.photos.values()].filter(p => !p.dupOf);
let saveT;
function saveSettings() { clearTimeout(saveT); saveT = setTimeout(() => db.put('state', 'settings', S.settings), 250); }

function stripRuntime(p) {
  const { name: n, size, lastModified, sha, dhash, w, h, taken, dateSource, lat, lon, place, placeSource, sharp, expo, thumb, addedAt } = p;
  return { name: n, size, lastModified, sha, dhash, w, h, taken, dateSource, lat, lon, place, placeSource, sharp, expo, thumb, addedAt,
    faces: p.faces.map(({ box, det, happy, desc, crop }) => ({ box, det, happy, desc, crop })) };
}
const savePhoto = p => db.put('photos', p.id, stripRuntime(p));

function toast(msg, action, fn, ms = 3800) {
  const t = document.getElementById('toast');
  t.replaceChildren(msg);
  t.style.pointerEvents = action ? 'auto' : 'none';
  if (action) t.append(' ', el('button', { style: 'color:inherit;text-decoration:underline;font-weight:600', onclick: () => { t.classList.remove('show'); fn(); } }, action));
  t.classList.add('show');
  clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove('show'), ms);
}

function sheet(...content) {
  const close = () => bd.remove();
  const bd = el('div', { class: 'backdrop', onclick: e => { if (e.target === bd) close(); } },
    el('div', { class: 'sheet', role: 'dialog', 'aria-modal': 'true' }, ...content));
  document.body.append(bd);
  const onKey = e => { if (e.key === 'Escape') { close(); removeEventListener('keydown', onKey); } };
  addEventListener('keydown', onKey);
  return close;
}

function pickFiles({ directory = false } = {}) {
  const input = el('input', { type: 'file', multiple: true, accept: directory ? null : 'image/*,.heic,.heif,.json', class: 'sr' });
  if (directory) input.webkitdirectory = true;
  input.addEventListener('change', () => { if (input.files.length) addFiles([...input.files]); input.remove(); });
  document.body.append(input);
  input.click();
}

function imgSrc(p) {
  const a = S.assets.get(p.id);
  if (a?.large) return blobUrl('L' + p.id, a.large);
  return blobUrl('T' + p.id, p.thumb);
}

function caption(p) {
  return {
    place: p.place || '',
    date: dateDe(p.date, p.dateSource === 'file'),
    people: p.people.map(name),
  };
}

// ---------------------------------------------------------------- data
async function boot() {
  const [settings, photos] = await Promise.all([db.get('state', 'settings'), db.getAll('photos')]);
  if (settings) S.settings = { ...structuredClone(DEFAULTS), ...settings };
  for (const [id, rec] of photos) { rec.id = id; S.photos.set(id, rec); }
  if (!S.photos.size) return go('welcome');
  recompute();
  go(!hasPeople() && clusters().length ? 'people' : 'book');
}

function recompute() {
  const list = [...S.photos.values()];
  const weights = { a: 1, b: 1, c: 1 };
  if (S.settings.focus) weights[S.settings.focus] = 1.6;
  enrich(list, S.settings.refs, weights);
  S.dupCount = markDuplicates(list).length;
  S.book = buildBook(list, {
    perMonth: S.settings.perMonth, prints: S.settings.prints, requirePeople: hasPeople(), overrides: S.settings.overrides,
  });
}

function clusters() {
  if (!S.clusters) {
    const faces = [];
    for (const p of live()) p.faces.forEach((face, idx) => { if (face.box[2] * face.box[3] >= 0.002) faces.push({ photo: p, idx, face }); });
    S.clusters = clusterFaces(faces).filter(c => c.members.length >= 2 || faces.length < 40);
  }
  return S.clusters;
}

async function loadAssets(ids) {
  const missing = ids.filter(id => !S.assets.has(id));
  for (const id of missing) S.assets.set(id, (await db.get('assets', id)) || {});
}

// ---------------------------------------------------------------- import
let cancelImport = false;
async function addFiles(files, hints = new Map()) {
  const sidecars = await readTakeoutSidecars(files.filter(f => /\.json$/i.test(f.name)));
  const imgs = files.filter(f => isImage(f) && !/\.json$/i.test(f.name));
  if (!imgs.length) return toast('Keine Fotos gefunden.');
  db.persist();
  const todo = [];
  for (const f of imgs) {
    const id = fileId(f);
    S.files.set(id, f);
    if (!S.photos.has(id)) todo.push(f);
  }
  const ui = renderProgress(todo.length, imgs.length - todo.length);
  let lock = null;
  try { lock = await navigator.wakeLock?.request('screen'); } catch { /* not supported */ }
  cancelImport = false;
  let errors = 0;
  try {
    ui.stage(0);
    await loadModels();
    ui.stage(1);
    const t0 = performance.now();
    for (const [i, f] of todo.entries()) {
      if (cancelImport) break;
      const id = fileId(f);
      try {
        const rec = await analyzeFile(f, hints.get(f) || sidecars.get(f.name) || {});
        rec.id = id;
        S.photos.set(id, rec);
        await savePhoto(rec);
        ui.thumb(rec);
      } catch (err) {
        errors++;
        console.warn('Foto übersprungen', f.name, err);
      }
      ui.count(i + 1, (performance.now() - t0) / (i + 1));
      if (i % 4 === 0) await yieldUI();
    }
    ui.stage(2);
    await yieldUI();
    S.clusters = null;
    recompute();
    ui.stage(3);
    await yieldUI();
    clusters();
  } finally {
    lock?.release?.().catch(() => {});
  }
  const added = todo.length - errors;
  if (!hasPeople() && clusters().length) go('people'); else go('book');
  toast(`${fmtNum(added)} Fotos hinzugefügt${errors ? `, ${errors} nicht lesbar` : ''}${S.dupCount ? ` · ${fmtNum(S.dupCount)} Duplikate erkannt` : ''}`);
}

// ---------------------------------------------------------------- views
function go(view) {
  S.view = view;
  const y = view === S._lastView ? scrollY : 0;
  S._lastView = view;
  app.replaceChildren(({ welcome: viewWelcome, people: viewPeople, book: viewBook })[view]());
  scrollTo(0, y);
  if (view === 'book') background();
}

function viewWelcome() {
  const sources = [
    el('button', { class: 'source', onclick: openPhoneSheet },
      el('span', { class: 'ico' }, icon('phone')), el('strong', {}, 'Fotos vom Handy'),
      el('small', {}, 'iPhone-Mediathek oder Android-Galerie')),
    el('button', { class: 'source', onclick: openGoogleSheet },
      el('span', { class: 'ico' }, icon('google')), el('strong', {}, 'Google Fotos'),
      el('small', {}, googleEnabled() ? 'Direkt aus eurem Google-Konto auswählen' : 'So holt ihr die Bilder aus Google Fotos')),
  ];
  if (!isTouch()) {
    sources.push(el('button', { class: 'source', onclick: () => pickFiles({ directory: true }) },
      el('span', { class: 'ico' }, icon('folder')), el('strong', {}, 'Ordner am Computer'),
      el('small', {}, 'z. B. iCloud-Export oder Google Takeout')));
  }
  return el('div', { class: 'welcome wrap' },
    el('div', { class: 'brand', html: `${LOGO}<span>Unser Fotojahr</span>` }),
    el('section', { class: 'hero' },
      el('div', {},
        el('h1', { html: 'Euer Jahr<br>in <em>Bildern.</em>' }),
        el('p', { class: 'lede' }, 'Wählt einfach alle Fotos aus. Die App entfernt Duplikate, sortiert nach Monaten, findet die schönsten Bilder von euch dreien und schlägt pro Monat vor, welche ihr drucken solltet – mit Ort und Datum darunter.'),
        el('div', { class: 'sources' }, sources),
        el('p', { class: 'privacy' }, icon('lock'), el('span', {}, 'Eure Fotos bleiben auf diesem Gerät. Nichts wird hochgeladen – auch die Gesichtserkennung läuft hier.'))),
      el('div', { class: 'collage', 'aria-hidden': 'true' },
        el('div', { class: 'polaroid p1' }, el('div'), el('span', {}, 'Juli · Ostsee')),
        el('div', { class: 'polaroid p2' }, el('div'), el('span', {}, 'Oktober · Herbst')),
        el('div', { class: 'polaroid p3' }, el('div'), el('span', {}, 'Mai · Garten')))),
    el('section', { class: 'steps' },
      ...[['1', 'Fotos wählen', 'Ruhig alle – auch doppelte und Serienbilder.'],
        ['2', 'Wer ist wer?', 'Einmal antippen, wer Papa, Mama und euer Sohn ist.'],
        ['3', 'Fotobuch ansehen', 'Die besten 20–30 Fotos pro Monat, schön gestaltet.'],
        ['4', 'Drucken', '2–3 Empfehlungen pro Monat – teilen, speichern oder als PDF.']]
        .map(([n, t, d]) => el('div', { class: 'step' }, el('b', {}, n), el('strong', {}, t), el('p', {}, d)))));
}

function openPhoneSheet() {
  const close = sheet(
    el('h3', {}, 'Fotos vom Handy'),
    el('ol', {},
      el('li', {}, 'Tippe auf „Fotos auswählen“. Es öffnet sich eure Mediathek.'),
      el('li', {}, isIOS() ? 'Mehrere Fotos markierst du schnell, indem du mit dem Finger über die Fotos wischst. Unter „Sammlungen“/„Alben“ findest du auch geteilte Alben.' : 'Halte ein Foto gedrückt und markiere dann weitere – oder wähle ein ganzes Album.'),
      isIOS() ? el('li', {}, 'Für Orte unter den Fotos: Wenn oben „Optionen“ erscheint, dort die Ortsdaten einschließen. Fehlen Orte, übernimmt die App sie von anderen Fotos desselben Tages oder ihr tippt sie ein.') : null,
      el('li', {}, 'Ihr könnt beliebig oft weitere Fotos hinzufügen, z. B. später die vom anderen Handy.')),
    el('div', { class: 'choices' },
      el('button', { class: 'btn block', onclick: () => { close(); pickFiles(); } }, icon('phone'), 'Fotos auswählen')));
}

function openGoogleSheet() {
  if (googleEnabled()) {
    const status = el('p', { class: 'muted' }, 'Ihr wählt die Fotos in Google Fotos selbst aus. Die App bekommt nur Zugriff auf genau diese Bilder.');
    const btn = el('button', { class: 'btn block', onclick: async () => {
      btn.disabled = true;
      try {
        const items = await pickFromGooglePhotos(t => { status.textContent = t; });
        close();
        if (items.length) addFiles(items.map(i => i.file), new Map(items.map(i => [i.file, i.hints])));
      } catch (e) { status.textContent = `Das hat nicht geklappt: ${e.message}`; btn.disabled = false; }
    } }, icon('google'), 'Mit Google Fotos verbinden');
    const close = sheet(el('h3', {}, 'Google Fotos'), status, el('div', { class: 'choices' }, btn),
      el('p', { class: 'muted', style: 'font-size:13.5px;margin-top:14px' }, 'Hinweis: Google entfernt beim Weitergeben die Ortsdaten. Orte ergänzt die App aus Fotos desselben Tages, oder ihr tippt sie ein. Mit Ortsdaten: Weg über Google Takeout (unten).'),
      takeoutHelp());
    return;
  }
  const close = sheet(
    el('h3', {}, 'Fotos aus Google Fotos'),
    el('p', {}, 'Auf dem Handy (am schnellsten):'),
    el('ol', {},
      el('li', {}, 'Google-Fotos-App öffnen, ein Foto gedrückt halten und weitere markieren (die Suche hilft, z. B. „März 2026“).'),
      el('li', {}, isIOS() ? 'Auf „Teilen“ tippen und „Auf Gerät speichern“ wählen.' : 'Oben rechts auf ⋮ tippen und „Herunterladen“ wählen.'),
      el('li', {}, 'Zurück hier „Fotos vom Handy“ wählen – die Bilder sind jetzt in der Galerie.')),
    takeoutHelp(),
    el('div', { class: 'choices' }, el('button', { class: 'btn block', onclick: () => { close(); pickFiles(); } }, icon('phone'), 'Fotos vom Handy auswählen')));
}

const takeoutHelp = () => el('details', { style: 'margin-top:10px' },
  el('summary', { style: 'cursor:pointer;font-weight:600' }, 'Ganzes Archiv mit Orten (am Computer)'),
  el('ol', {},
    el('li', {}, 'takeout.google.com öffnen, nur „Google Fotos“ auswählen und den Export anfordern.'),
    el('li', {}, 'Die ZIP-Dateien herunterladen und entpacken.'),
    el('li', {}, 'Hier „Ordner am Computer“ wählen und den entpackten Ordner angeben. Datum und Orte aus den Begleitdateien werden automatisch übernommen.')));

// ---------------------------------------------------------------- progress
function renderProgress(n, known) {
  const count = el('div', { class: 'big-count' }, '0');
  const of = el('div', { class: 'muted' }, `von ${fmtNum(n)} neuen Fotos${known ? ` · ${fmtNum(known)} schon bekannt` : ''}`);
  const bar = el('i');
  const eta = el('div', { class: 'hint' }, '');
  const labels = ['Gesichtserkennung vorbereiten', 'Fotos anschauen', 'Duplikate & Monate sortieren', 'Gesichter gruppieren'];
  const items = labels.map(l => el('li', {}, el('span', { class: 'dot' }), l));
  const strip = el('div', { class: 'strip' });
  app.replaceChildren(el('div', { class: 'progress-screen' }, el('div', { class: 'progress-card' },
    el('div', { class: 'brand', style: 'justify-content:center', html: `${LOGO}<span>Unser Fotojahr</span>` }),
    el('h2', {}, 'Eure Fotos werden angeschaut'),
    count, of, el('div', { class: 'bar' }, bar), eta,
    el('ul', { class: 'stages' }, items), strip,
    el('p', { class: 'hint' }, isTouch() ? 'Bitte die App geöffnet lassen und das Handy nicht sperren. Bereits angeschaute Fotos bleiben gespeichert.' : 'Bereits angeschaute Fotos bleiben gespeichert – ihr könnt jederzeit weitermachen.'),
    el('button', { class: 'btn ghost small', onclick: () => { cancelImport = true; } }, 'Anhalten'))));
  scrollTo(0, 0);
  return {
    stage(i) { items.forEach((li, j) => { li.className = j < i ? 'done' : j === i ? 'on' : ''; li.querySelector('.dot').replaceChildren(j < i ? icon('check') : ''); }); },
    count(i, msPer) {
      count.textContent = fmtNum(i);
      bar.style.width = `${(100 * i) / Math.max(n, 1)}%`;
      const left = Math.round(((n - i) * msPer) / 60000);
      eta.textContent = n - i > 0 ? (left >= 1 ? `noch etwa ${left} Min.` : 'gleich fertig') : '';
    },
    thumb(rec) {
      strip.prepend(el('img', { src: blobUrl('T' + rec.id, rec.thumb), alt: '' }));
      while (strip.children.length > 6) strip.lastChild.remove();
    },
  };
}

// ---------------------------------------------------------------- people
function topbar(extra = []) {
  return el('header', { class: 'topbar' }, el('div', { class: 'wrap' },
    el('button', { class: 'brand', onclick: () => go('book'), html: `${LOGO}<span>${escapeHtml(S.settings.title)}</span>` }),
    el('div', { class: 'actions' }, extra)));
}
const escapeHtml = s => s.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

function personStats() {
  const counts = { a: 0, b: 0, c: 0 };
  for (const p of live()) for (const k of p.people) counts[k]++;
  return counts;
}

function viewPeople() {
  const cl = clusters();
  const refs = S.settings.refs;
  const labelled = cl.map(c => ({ c, label: labelForCluster(c, refs) }));
  const counts = personStats();
  const avatar = k => labelled.find(x => x.label === k)?.c.rep;

  const persons = el('div', { class: 'persons' }, PERSONS.map(k => {
    const rep = avatar(k);
    const av = el('div', { class: 'av', style: rep ? `background-image:url(${blobUrl(`F${rep.photo.id}:${rep.idx}`, rep.face.crop)})` : '' }, rep ? '' : (name(k)[0] || '?'));
    return el('div', { class: 'person', style: `--pc:${PCOLOR[k]}` }, av,
      el('input', { type: 'text', value: name(k), 'aria-label': 'Name', maxlength: 24,
        oninput: e => { S.settings.names[k] = e.target.value.trim(); saveSettings(); } }),
      el('small', {}, counts[k] ? `${fmtNum(counts[k])} Fotos` : 'noch keine Fotos'));
  }));

  const open = labelled.filter(x => !x.label);
  const done = labelled.filter(x => x.label && x.label !== 'other');
  const others = labelled.filter(x => x.label === 'other');
  const limit = S.showAllFaces ? open.length : 36;
  const faceEl = ({ c, label }) => {
    const r = c.rep;
    return el('button', { class: `face ${label && label !== 'other' ? 'labelled' : ''} ${label === 'other' ? 'other' : ''}`, style: label && PCOLOR[label] ? `--pc:${PCOLOR[label]}` : '', onclick: () => openCluster(c, label) },
      el('span', { class: 'ring', style: `background-image:url(${blobUrl(`F${r.photo.id}:${r.idx}`, r.face.crop)})` },
        label && label !== 'other' ? el('span', { class: 'tag' }, name(label)) : null),
      `${c.members.length} Fotos`);
  };

  return el('div', {},
    topbar(),
    el('main', { class: 'wrap' },
      el('div', { class: 'people-head' },
        el('h1', {}, 'Wer ist wer?'),
        el('p', {}, 'Die App hat ähnliche Gesichter gruppiert. Tippt jede Gruppe an, in der einer von euch dreien zu sehen ist. Kinder verändern sich schnell – euer Sohn taucht deshalb oft in mehreren Gruppen auf (Baby, Kleinkind …). Ordnet ruhig alle zu.')),
      persons,
      open.length ? el('p', { class: 'sectionlabel' }, `Noch zuordnen · ${open.length}`) : null,
      el('div', { class: 'faces', style: 'padding-bottom:20px' }, open.slice(0, limit).map(faceEl)),
      open.length > limit ? el('button', { class: 'btn ghost small', onclick: () => { S.showAllFaces = true; go('people'); } }, `Alle ${open.length} Gruppen zeigen`) : null,
      done.length ? el('p', { class: 'sectionlabel', style: 'margin-top:20px' }, `Zugeordnet · ${done.length}`) : null,
      el('div', { class: 'faces', style: 'padding-bottom:20px' }, done.map(faceEl)),
      others.length ? el('p', { class: 'sectionlabel', style: 'margin-top:20px' }, `Andere Personen · ${others.length}`) : null,
      el('div', { class: 'faces' }, others.map(faceEl))),
    el('div', { class: 'cta-bar' }, el('div', { class: 'wrap' },
      el('span', { class: 'muted' }, done.length ? `${done.length} Gruppen zugeordnet` : 'Tippt auf ein Gesicht'),
      el('button', { class: 'btn', disabled: !done.length, onclick: () => { recompute(); go('book'); } }, icon('book'), 'Fotobuch ansehen'))));
}

function openCluster(c, label) {
  const assign = person => {
    S.settings.refs = S.settings.refs.filter(r => dist(r.desc, c.centroid) >= CLUSTER_DIST);
    if (person) S.settings.refs.push({ person, desc: c.centroid.map(v => +v.toFixed(5)) });
    saveSettings();
    recompute();
    close();
    go('people');
  };
  const crops = c.members.slice(0, 8).map(m => el('img', { src: blobUrl(`F${m.photo.id}:${m.idx}`, m.face.crop), alt: '', style: 'width:52px;height:52px;border-radius:50%;object-fit:cover' }));
  const close = sheet(
    el('h3', {}, 'Wer ist das?'),
    el('p', {}, `${c.members.length} Fotos mit diesem Gesicht`),
    el('div', { style: 'display:flex;gap:6px;flex-wrap:wrap;margin:6px 0 4px' }, crops),
    el('div', { class: 'choices' },
      PERSONS.map(k => el('button', { class: 'choice', style: `--pc:${PCOLOR[k]}`, onclick: () => assign(k) },
        el('span', { class: 'sw' }), name(k), label === k ? el('small', {}, '✓ zugeordnet') : null)),
      el('button', { class: 'choice', onclick: () => assign('other') }, el('span', { class: 'sw' }), 'Jemand anderes', label === 'other' ? el('small', {}, '✓') : null),
      label ? el('button', { class: 'choice', onclick: () => assign(null) }, 'Zuordnung aufheben') : null));
}

// ---------------------------------------------------------------- book
function viewBook() {
  const book = S.book;
  const all = book.flatMap(m => m.top);
  const actions = [
    el('button', { class: 'btn soft small', onclick: openAddSheet, title: 'Fotos hinzufügen' }, icon('plus'), el('span', { class: 'label' }, 'Fotos')),
    el('button', { class: 'iconbtn', onclick: () => go('people'), title: 'Wer ist wer?', 'aria-label': 'Personen' }, icon('users')),
    el('button', { class: 'iconbtn', onclick: openSettings, title: 'Einstellungen', 'aria-label': 'Einstellungen' }, icon('sliders')),
    el('button', { class: 'btn small', onclick: openExport }, icon('share'), el('span', { class: 'label' }, 'Drucken & Teilen')),
  ];
  if (!all.length) {
    return el('div', {}, topbar(actions), el('main', { class: 'wrap', style: 'padding:60px 16px;text-align:center' },
      el('h2', {}, 'Noch keine Fotos im Buch'),
      el('p', { class: 'muted' }, hasPeople() ? 'Auf keinem Foto wurde jemand von euch erkannt. Ordnet unter „Wer ist wer?“ weitere Gruppen zu.' : 'Fügt Fotos hinzu, um loszulegen.'),
      el('button', { class: 'btn', onclick: openAddSheet }, icon('plus'), 'Fotos hinzufügen')));
  }
  const coverPhoto = pickCover(book);
  const first = book[0].key, last = book[book.length - 1].key;
  const span = first === last ? monthTitle(first) : `${monthTitle(first)} – ${monthTitle(last)}`;
  const noPlace = all.filter(p => !p.place && p.lat == null).length;
  const totalPrint = book.reduce((a, m) => a + m.print.size, 0);

  const titleEl = el('h1', { contenteditable: 'true', spellcheck: 'false', 'aria-label': 'Titel bearbeiten',
    onblur: e => { S.settings.title = e.target.textContent.trim() || DEFAULTS.title; saveSettings(); },
    onkeydown: e => { if (e.key === 'Enter') { e.preventDefault(); e.target.blur(); } } }, S.settings.title);

  return el('div', {},
    topbar(actions),
    el('nav', { class: 'monthnav', 'aria-label': 'Monate' }, book.map(m => el('a', { href: `#m${m.key}` }, monthTitle(m.key))), el('a', { href: '#druck' }, 'Druckliste')),
    el('section', { class: 'cover' }, el('div', { class: 'cover-inner' },
      coverPhoto ? el('img', { src: imgSrc(coverPhoto), alt: '', 'data-id': coverPhoto.id }) : null,
      el('div', { class: 'cover-text' },
        el('div', { class: 'kicker' }, span),
        titleEl,
        el('div', { class: 'chips' },
          el('span', {}, `${fmtNum(all.length)} ausgewählte Fotos`),
          el('span', {}, `aus ${fmtNum(live().length)}`),
          S.dupCount ? el('span', {}, `${fmtNum(S.dupCount)} Duplikate entfernt`) : null,
          el('span', {}, `${totalPrint} zum Drucken`))))),
    el('main', { class: 'wrap' },
      noPlace > all.length * 0.4 && !S.settings.placeNoticeHidden ? el('div', { class: 'notice' }, icon('pin'),
        el('div', {}, `Bei ${fmtNum(noPlace)} Fotos fehlt der Ort – Handy-Browser und Google Fotos entfernen die Ortsdaten oft beim Auswählen. Tippt auf ein Foto und dann auf „Ort eintragen“; der Ort gilt dann für den ganzen Tag. `,
          el('button', { onclick: () => { S.settings.placeNoticeHidden = true; saveSettings(); go('book'); } }, 'Ausblenden'))) : null,
      book.map(renderMonth),
      renderPrintList(book)),
    el('footer', { class: 'end' }, 'Alles bleibt auf diesem Gerät gespeichert. ',
      el('button', { onclick: openSettings }, 'Einstellungen')));
}

function pickCover(book) {
  const prints = book.flatMap(m => m.top.filter(p => m.print.has(p.id)));
  const pool = prints.length ? prints : book.flatMap(m => m.top);
  return pool.filter(p => p.w >= p.h).sort((a, b) => (b.people.length - a.people.length) || (b.score - a.score))[0] || pool[0];
}

function tile(p, m, feature = false) {
  const isPrint = m.print.has(p.id);
  const c = caption(p);
  return el('figure', { class: 'tile', tabindex: 0, 'data-id': p.id, onclick: () => openLightbox(p.id),
    onkeydown: e => { if (e.key === 'Enter') openLightbox(p.id); } },
    isPrint ? el('span', { class: 'ribbon' }, icon('star', 'icon'), 'Drucken') : null,
    p.people.length ? el('span', { class: 'dots' }, p.people.map(k => el('i', { style: `--pc:${PCOLOR[k]}`, title: name(k) }))) : null,
    el('img', { src: imgSrc(p), alt: [c.place, c.date].filter(Boolean).join(', '), loading: 'lazy', decoding: 'async',
      width: p.w, height: p.h, 'data-id': p.id }),
    el('figcaption', {}, c.place ? el('b', {}, c.place) : null, [c.date, ...(feature ? [c.people.join(' · ')] : [])].filter(Boolean).join(' · ')));
}

function renderMonth(m) {
  const [y] = m.key.split('-');
  const prints = m.top.filter(p => m.print.has(p.id)).sort((a, b) => b.score - a.score);
  const rest = m.top.filter(p => !m.print.has(p.id));
  const n = Math.min(prints.length, 3);
  return el('section', { class: 'month', id: `m${m.key}` },
    el('div', { class: 'month-head' },
      el('h2', { html: m.key === 'unbekannt' ? 'Ohne Datum' : `${escapeHtml(monthTitle(m.key).split(' ')[0])}<em>${y}</em>` }),
      el('span', { class: 'stat' }, `${m.top.length} von ${fmtNum(m.total)} Fotos · ${m.print.size} zum Drucken`)),
    prints.length ? el('div', { class: `features n${n}` }, prints.slice(0, 3).map(p => tile(p, m, true))) : null,
    el('div', { class: 'grid' }, [...prints.slice(3), ...rest].map(p => tile(p, m))));
}

function renderPrintList(book) {
  return el('section', { class: 'printlist', id: 'druck' },
    el('h2', {}, 'Eure Druckliste'),
    el('p', { class: 'lede' }, `Pro Monat ${S.settings.prints} Empfehlungen – ausgewählt nach Schärfe, Auflösung, Lächeln und danach, dass möglichst ihr alle drei drauf seid und verschiedene Tage zu sehen sind. Antippen zum Ändern.`),
    book.map(m => el('div', { class: 'prow' },
      el('h4', {}, monthTitle(m.key)),
      el('div', { class: 'pics' }, m.top.filter(p => m.print.has(p.id)).map(p =>
        el('img', { src: imgSrc(p), alt: '', 'data-id': p.id, onclick: () => openLightbox(p.id) }))))),
    el('div', { class: 'export-actions' },
      el('button', { class: 'btn', onclick: () => exportPhotos('print') }, icon('share'), 'Druckfotos speichern'),
      el('button', { class: 'btn soft', onclick: () => print() }, icon('printer'), 'Fotobuch als PDF')));
}

// ---------------------------------------------------------------- lightbox
function openLightbox(id) {
  const order = S.book.flatMap(m => m.top.map(p => ({ p, m })));
  let i = order.findIndex(x => x.p.id === id);
  if (i < 0) return;
  const box = el('div', { class: 'lightbox', role: 'dialog', 'aria-modal': 'true' });
  const close = () => { box.remove(); removeEventListener('keydown', onKey); };
  const onKey = e => {
    if (e.key === 'Escape') close();
    if (e.key === 'ArrowRight') step(1);
    if (e.key === 'ArrowLeft') step(-1);
  };
  const step = d => { i = (i + d + order.length) % order.length; draw(); };
  let x0 = null;
  const draw = () => {
    const { p, m } = order[i];
    const isPrint = m.print.has(p.id);
    const c = caption(p);
    const img = el('img', { src: imgSrc(p), alt: '' });
    // full quality if the original is available in this session
    const f = S.files.get(p.id);
    if (f && /jpe?g|png|webp/i.test(f.type)) img.src = blobUrl('O' + p.id, f);
    box.replaceChildren(
      el('div', { class: 'lb-top' },
        el('button', { class: 'iconbtn', onclick: close, 'aria-label': 'Schließen' }, icon('x')),
        el('span', { style: 'font-size:14px;opacity:.7' }, `${monthTitle(m.key)} · ${m.top.indexOf(p) + 1}/${m.top.length}`),
        el('div', {},
          el('button', { class: 'iconbtn', onclick: () => step(-1), 'aria-label': 'Zurück' }, icon('left')),
          el('button', { class: 'iconbtn', onclick: () => step(1), 'aria-label': 'Weiter' }, icon('right')))),
      el('div', { class: 'lb-img',
        ontouchstart: e => { x0 = e.touches[0].clientX; },
        ontouchend: e => { if (x0 == null) return; const dx = e.changedTouches[0].clientX - x0; if (Math.abs(dx) > 50) step(dx < 0 ? 1 : -1); x0 = null; } }, img),
      el('div', { class: 'lb-info' },
        el('div', { class: 'lb-place' }, icon('pin'), c.place || el('span', { style: 'opacity:.6' }, 'Ort unbekannt'),
          el('button', { onclick: () => editPlace(p, draw) }, c.place ? 'ändern' : 'Ort eintragen')),
        el('div', { class: 'lb-meta' }, c.date,
          p.people.map(k => el('span', { class: 'pchip', style: `--pc:${PCOLOR[k]}` }, el('i'), name(k)))),
        el('div', { class: 'lb-actions' },
          el('button', { class: `btn small ${isPrint ? 'on' : 'ghost'}`, onclick: () => { togglePrint(p, m); draw(); } }, icon('star'), isPrint ? 'Wird gedruckt' : 'Zum Drucken'),
          el('button', { class: 'btn small ghost', onclick: () => { removePhoto(p); order.splice(i, 1); if (!order.length) close(); else { i %= order.length; draw(); } } }, icon('trash'), 'Aus dem Buch'),
          el('button', { class: 'btn small ghost', onclick: () => shareOne(p) }, icon('share'), 'Teilen'))));
  };
  addEventListener('keydown', onKey);
  document.body.append(box);
  draw();
}

function override(id) { return (S.settings.overrides[id] ??= {}); }

function togglePrint(p, m) {
  const o = override(p.id);
  o.print = !m.print.has(p.id);
  saveSettings();
  recompute();
  const nm = S.book.find(b => b.key === m.key);
  if (nm) m.print = nm.print;
  refreshBookSoon();
}

function removePhoto(p) {
  override(p.id).excluded = true;
  saveSettings();
  recompute();
  refreshBookSoon();
  toast('Foto aus dem Buch genommen – ein anderes rückt nach.', 'Rückgängig', () => {
    delete S.settings.overrides[p.id].excluded; saveSettings(); recompute(); go('book');
  });
}

let refreshT;
function refreshBookSoon() {
  clearTimeout(refreshT);
  refreshT = setTimeout(() => { if (S.view === 'book' && !document.querySelector('.lightbox')) go('book'); else refreshBookSoon(); }, 300);
}

function editPlace(p, after) {
  const input = el('input', { type: 'text', value: p.place, placeholder: 'z. B. Tierpark Hellabrunn, München' });
  const sameDay = live().filter(q => q !== p && dayKey(q.date) === dayKey(p.date));
  const cb = el('input', { type: 'checkbox', checked: true, id: 'allday' });
  const close = sheet(
    el('h3', {}, 'Wo war das?'),
    el('p', {}, dateDe(p.date)),
    input,
    sameDay.length ? el('label', { style: 'display:flex;gap:8px;align-items:center;margin-top:12px;font-size:15px' }, cb, `Für alle ${sameDay.length + 1} Fotos dieses Tages übernehmen`) : null,
    el('div', { class: 'choices' }, el('button', { class: 'btn block', onclick: async () => {
      const v = input.value.trim();
      const targets = [p, ...(cb.checked ? sameDay : [])];
      for (const q of targets) { q.place = v; q.placeSource = v ? 'manual' : ''; await savePhoto(q); }
      close(); after?.(); refreshBookSoon();
    } }, 'Speichern')));
  setTimeout(() => input.focus(), 50);
}

async function shareOne(p) {
  const { blob } = await ex.bestBlob(p, S.files);
  const file = new File([blob], p.name.replace(/\.(heic|heif)$/i, '.jpg'), { type: blob.type || 'image/jpeg' });
  if (ex.canShareFiles(file)) { try { await navigator.share({ files: [file] }); } catch { /* cancelled */ } } else {
    const a = el('a', { href: URL.createObjectURL(file), download: file.name }); a.click();
  }
}

// ---------------------------------------------------------------- sheets: add / settings / export
function openAddSheet() {
  const close = sheet(el('h3', {}, 'Weitere Fotos hinzufügen'),
    el('p', {}, 'Schon bekannte Fotos werden erkannt und nicht doppelt gezählt – ihr könnt also z. B. einfach die Fotos vom zweiten Handy dazunehmen.'),
    el('div', { class: 'choices' },
      el('button', { class: 'choice', onclick: () => { close(); pickFiles(); } }, icon('phone'), 'Fotos vom Handy / aus der Mediathek'),
      el('button', { class: 'choice', onclick: () => { close(); openGoogleSheet(); } }, icon('google'), 'Google Fotos'),
      !isTouch() ? el('button', { class: 'choice', onclick: () => { close(); pickFiles({ directory: true }); } }, icon('folder'), 'Ordner am Computer') : null));
}

function seg(options, value, onPick) {
  const wrap = el('div', { class: 'seg', role: 'group' });
  for (const [v, label] of options) {
    wrap.append(el('button', { class: v === value ? 'on' : '', onclick: () => { onPick(v); [...wrap.children].forEach(b => b.classList.toggle('on', b.textContent === label)); } }, label));
  }
  return wrap;
}

function openSettings() {
  const st = S.settings;
  const changed = () => { saveSettings(); recompute(); refreshBookSoon(); };
  sheet(el('h3', {}, 'Einstellungen'),
    el('div', { class: 'row' }, el('span', {}, 'Fotos pro Monat'), seg([[20, '20'], [25, '25'], [30, '30']], st.perMonth, v => { st.perMonth = v; changed(); })),
    el('div', { class: 'row' }, el('span', {}, 'Druckempfehlungen'), seg([[2, '2'], [3, '3']], st.prints, v => { st.prints = v; changed(); })),
    el('div', { class: 'row' }, el('span', {}, 'Bevorzugen'), seg([['', 'Alle gleich'], ...PERSONS.map(k => [k, name(k)])], st.focus, v => { st.focus = v; changed(); })),
    el('div', { class: 'row' }, el('span', {}, 'Ortsnamen online suchen', el('br'), el('small', { class: 'muted' }, 'Sendet nur gerundete Koordinaten (ca. 100 m) an OpenStreetMap, nie Fotos.')),
      seg([[true, 'An'], [false, 'Aus']], st.lookupPlaces, v => { st.lookupPlaces = v; saveSettings(); if (v) background(); })),
    el('div', { class: 'row' }, el('span', {}, 'Ausgeblendete Fotos'),
      el('button', { class: 'btn ghost small', onclick: () => { for (const o of Object.values(st.overrides)) delete o.excluded; changed(); toast('Alle Fotos wieder im Rennen.'); } }, 'Zurückholen')),
    el('div', { class: 'row', style: 'border:0' }, el('span', {}, el('strong', {}, 'Alles löschen'), el('br'), el('small', { class: 'muted' }, 'Entfernt alle Daten der App von diesem Gerät. Eure Fotos in der Mediathek bleiben unberührt.')),
      el('button', { class: 'btn ghost small', onclick: async () => { if (confirm('Wirklich alle Daten der App löschen?')) { await db.wipe(); location.reload(); } } }, 'Löschen')));
}

function openExport() {
  sheet(el('h3', {}, 'Drucken & Teilen'),
    el('p', {}, 'Die Druckfotos könnt ihr direkt in eure Mediathek sichern oder an einen Fotodienst schicken (z. B. dm, Rossmann, CEWE oder Pixum).'),
    el('div', { class: 'choices' },
      el('button', { class: 'choice', onclick: () => exportPhotos('print') }, icon('star'), `Druckfotos (${S.book.reduce((a, m) => a + m.print.size, 0)}) speichern / teilen`),
      el('button', { class: 'choice', onclick: () => exportPhotos('all') }, icon('download'), `Alle Buchfotos (${S.book.reduce((a, m) => a + m.top.length, 0)}) als ZIP`),
      el('button', { class: 'choice', onclick: () => { document.querySelector('.backdrop')?.remove(); setTimeout(print, 100); } }, icon('printer'), 'Fotobuch als PDF / drucken')),
    el('p', { class: 'muted', style: 'font-size:13.5px;margin-top:14px' }, 'PDF: Im Druckdialog „Als PDF sichern“ wählen. Auf dem iPhone: Teilen → Drucken → mit zwei Fingern in die Vorschau zoomen → Teilen.'));
}

async function exportPhotos(which) {
  document.querySelector('.backdrop')?.remove();
  toast('Fotos werden vorbereitet …', null, null, 60000);
  const list = await ex.collect(S.book, S.files, which);
  const reduced = list.filter(x => x.quality !== 'original').length;
  const title = `${S.settings.title} – ${which === 'print' ? 'Druckfotos' : 'Fotobuch'}`;
  try {
    if (which === 'print' && list.length && ex.canShareFiles(new File([list[0].blob], list[0].name, { type: 'image/jpeg' }))) {
      await ex.share(list, title);
    } else {
      await ex.downloadZip(list, `${title}.zip`.replace(/[\\/:*?"<>|]/g, ''), pct => toast(`ZIP wird erstellt … ${Math.round(pct)} %`, null, null, 60000));
    }
    toast(reduced ? `Fertig. ${reduced} Fotos nur in Buchqualität – für Originale die Fotos erneut hinzufügen.` : 'Fertig!', null, null, 5000);
  } catch (e) {
    if (e?.name !== 'AbortError') toast(`Das hat nicht geklappt: ${e.message || e}`);
    else toast('Abgebrochen.');
  }
}

// ---------------------------------------------------------------- background work (large images, originals, places)
async function background() {
  if (S.bgRunning) return;
  S.bgRunning = true;
  const pill = el('div', { class: 'mini-progress no-print' }, el('span', { class: 'spinner' }), el('span', {}, 'Buch wird vorbereitet …'));
  try {
    const inBook = S.book.flatMap(m => [...m.top, ...m.reserve]);
    await loadAssets(inBook.map(p => p.id));
    const printIds = new Set(S.book.flatMap(m => [...m.print]));
    const todo = inBook.filter(p => S.files.has(p.id) && (!S.assets.get(p.id).large || (printIds.has(p.id) && !S.assets.get(p.id).original)));
    if (todo.length) document.body.append(pill);
    for (const [i, p] of todo.entries()) {
      pill.lastChild.textContent = `Bilder fürs Buch ${i + 1}/${todo.length}`;
      const a = { ...S.assets.get(p.id) };
      try {
        if (!a.large) a.large = await makeLarge(S.files.get(p.id));
        if (printIds.has(p.id) && !a.original) a.original = S.files.get(p.id);
        S.assets.set(p.id, a);
        await db.put('assets', p.id, a);
        for (const img of document.querySelectorAll(`img[data-id="${CSS.escape(p.id)}"]`)) img.src = imgSrc(p);
      } catch (e) { console.warn(e); }
      if (i % 3 === 0) await yieldUI();
    }
    // places
    const bookPhotos = S.book.flatMap(m => m.top);
    if (S.settings.lookupPlaces && bookPhotos.some(p => !p.place && p.placeSource !== 'manual')) {
      pill.lastChild.textContent = 'Orte werden gesucht …';
      if (!pill.isConnected) document.body.append(pill);
      const { changed } = await assignPlaces(bookPhotos, live(), (i, n) => { pill.lastChild.textContent = `Orte ${i}/${n}`; });
      for (const p of changed) await savePhoto(p);
      if (changed.length) refreshBookSoon();
    }
  } finally {
    pill.remove();
    S.bgRunning = false;
  }
}

// ---------------------------------------------------------------- start
addEventListener('beforeprint', async () => { for (const img of document.querySelectorAll('img[loading=lazy]')) img.loading = 'eager'; });
if ('serviceWorker' in navigator && location.protocol === 'https:') navigator.serviceWorker.register('sw.js').catch(() => {});
boot().catch(err => {
  console.error(err);
  app.replaceChildren(el('div', { class: 'wrap', style: 'padding:60px 16px' }, el('h2', {}, 'Die App konnte nicht starten'), el('p', { class: 'muted' }, String(err))));
});
