// Password gate (Vercel Routing Middleware). Runs on Vercel's servers before any file is
// delivered, so without the password nobody gets the app, its code or the models.
// The password lives only in the Vercel project setting APP_PASSWORD (never in this repo).
// Local testing with a plain static server has no gate.

const COOKIE = 'fj_auth';
const MAX_AGE = 60 * 60 * 24 * 365; // stay signed in on this device for a year
const PUBLIC = /^\/(icons\/[\w.-]+|manifest\.webmanifest)$/; // needed for the home-screen icon
const enc = new TextEncoder();

const HEADERS = {
  'content-type': 'text/html; charset=utf-8',
  'cache-control': 'no-store',
  'x-robots-tag': 'noindex',
  'x-frame-options': 'DENY',
  'x-content-type-options': 'nosniff',
  'referrer-policy': 'no-referrer',
  'content-security-policy': "default-src 'none'; style-src 'unsafe-inline'; img-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'",
};

async function hmacHex(key, message) {
  const k = await crypto.subtle.importKey('raw', enc.encode(key), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  const sig = await crypto.subtle.sign('HMAC', k, enc.encode(message));
  return [...new Uint8Array(sig)].map(b => b.toString(16).padStart(2, '0')).join('');
}

// The cookie never contains the password, only a value derived from it.
const sessionToken = password => hmacHex(password, 'fotojahr-session-v1');

// Compare without leaking how many characters match (both sides are hashed first).
async function same(a, b) {
  const [x, y] = await Promise.all([hmacHex('cmp', a), hmacHex('cmp', b)]);
  let diff = 0;
  for (let i = 0; i < x.length; i++) diff |= x.charCodeAt(i) ^ y.charCodeAt(i);
  return diff === 0;
}

function readCookie(request, name) {
  const m = (request.headers.get('cookie') || '').match(new RegExp(`(?:^|;\\s*)${name}=([^;]+)`));
  return m ? m[1] : '';
}

function page(message, status) {
  const html = `<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="robots" content="noindex"><title>Unser Fotojahr</title>
<link rel="icon" href="/icons/icon.svg"><link rel="apple-touch-icon" href="/icons/icon-180.png">
<link rel="manifest" href="/manifest.webmanifest">
<style>
:root{--paper:#f6f1ea;--card:#fffdf9;--ink:#2a2420;--muted:#8b8076;--line:#e4dacd;--accent:#c4623a}
@media (prefers-color-scheme:dark){:root{--paper:#1c1916;--card:#2a2521;--ink:#f1ebe4;--muted:#9c9085;--line:#3a332d;--accent:#e07f55}}
*{box-sizing:border-box}body{margin:0;min-height:100svh;display:grid;place-items:center;padding:24px 16px;background:var(--paper);color:var(--ink);font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
main{width:min(380px,100%);text-align:center}img{width:72px;height:72px;border-radius:18px}
h1{font:400 34px/1.1 "Iowan Old Style",Georgia,serif;margin:18px 0 6px}p{color:var(--muted);margin:0 0 22px}
input{width:100%;font:inherit;color:inherit;padding:14px 16px;border-radius:14px;border:1px solid var(--line);background:var(--card);text-align:center}
input:focus{outline:2px solid var(--accent);outline-offset:1px}
button{width:100%;margin-top:12px;min-height:50px;border:0;border-radius:999px;background:var(--accent);color:#fff;font:600 16px/1 inherit;cursor:pointer}
.err{color:var(--accent);font-weight:600;margin:14px 0 0}
</style></head><body><main>
<img src="/icons/icon.svg" alt="">
<h1>Unser Fotojahr</h1>
<p>Bitte das Familien-Passwort eingeben.</p>
<form method="post" action="/__login" autocomplete="on">
<input type="password" name="password" placeholder="Passwort" aria-label="Passwort" autocomplete="current-password" autofocus required>
<button type="submit">Öffnen</button>
</form>
${message ? `<p class="err" role="alert">${message}</p>` : ''}
</main></body></html>`;
  return new Response(html, { status, headers: HEADERS });
}

export default async function middleware(request) {
  const url = new URL(request.url);
  const password = process.env.APP_PASSWORD;
  if (!password) return page('Die App ist noch nicht eingerichtet (Passwort fehlt).', 503); // fail closed
  const expected = await sessionToken(password);

  if (url.pathname === '/__login' && request.method === 'POST') {
    let given = '';
    try { given = String((await request.formData()).get('password') || ''); } catch { /* malformed body */ }
    if (given.length <= 200 && await same(given, password)) {
      return new Response(null, {
        status: 303,
        headers: {
          location: '/',
          'cache-control': 'no-store',
          'set-cookie': `${COOKIE}=${expected}; Path=/; Max-Age=${MAX_AGE}; HttpOnly; Secure; SameSite=Lax`,
        },
      });
    }
    await new Promise(r => setTimeout(r, 1500)); // slow down guessing
    return page('Das Passwort stimmt nicht.', 401);
  }

  if (url.pathname === '/__logout') {
    return new Response(null, {
      status: 303,
      headers: { location: '/', 'set-cookie': `${COOKIE}=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax` },
    });
  }

  if (PUBLIC.test(url.pathname) || await same(readCookie(request, COOKIE), expected)) {
    return new Response(null, { headers: { 'x-middleware-next': '1' } }); // continue to the file
  }

  // 401 (not a redirect) so the service worker never stores the login page as the app
  return page('', 401);
}
