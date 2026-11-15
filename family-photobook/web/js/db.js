// Tiny IndexedDB wrapper. Everything stays on this device.
const DB_NAME = 'fotobuch';
const DB_VERSION = 1;
export const STORES = ['photos', 'assets', 'state', 'geo'];

let dbPromise;

function open() {
  if (!dbPromise) {
    dbPromise = new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, DB_VERSION);
      req.onupgradeneeded = () => {
        for (const s of STORES) if (!req.result.objectStoreNames.contains(s)) req.result.createObjectStore(s);
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }
  return dbPromise;
}

function tx(store, mode, fn) {
  return open().then(db => new Promise((resolve, reject) => {
    const t = db.transaction(store, mode);
    const result = fn(t.objectStore(store));
    t.oncomplete = () => resolve(result && 'result' in result ? result.result : result);
    t.onerror = () => reject(t.error);
    t.onabort = () => reject(t.error);
  }));
}

export const get = (store, key) => tx(store, 'readonly', s => s.get(key));
export const put = (store, key, value) => tx(store, 'readwrite', s => { s.put(value, key); });
export const del = (store, key) => tx(store, 'readwrite', s => { s.delete(key); });
export const clear = store => tx(store, 'readwrite', s => { s.clear(); });

export function getAll(store) {
  return open().then(db => new Promise((resolve, reject) => {
    const out = new Map();
    const req = db.transaction(store, 'readonly').objectStore(store).openCursor();
    req.onsuccess = () => {
      const c = req.result;
      if (c) { out.set(c.key, c.value); c.continue(); } else resolve(out);
    };
    req.onerror = () => reject(req.error);
  }));
}

export async function putMany(store, entries) {
  return tx(store, 'readwrite', s => { for (const [k, v] of entries) s.put(v, k); });
}

export async function wipe() {
  for (const s of STORES) await clear(s);
}

export async function persist() {
  try { return await navigator.storage?.persist?.(); } catch { return false; }
}
