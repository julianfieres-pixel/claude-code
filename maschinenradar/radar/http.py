"""Hoeflicher HTTP-Abruf: robots.txt beachten, Pausen je Host, optionaler Platten-Cache."""
from __future__ import annotations

import hashlib
import time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import requests

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0 Safari/537.36"
)


class FetchError(Exception):
    pass


class Fetcher:
    def __init__(
        self,
        delay: float = 3.0,
        cache_dir: Path | None = None,
        cache_hours: float = 0,
        user_agent: str = USER_AGENT,
        timeout: float = 40,
    ):
        self.delay = delay
        self.cache_dir = cache_dir
        self.cache_hours = cache_hours
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": user_agent, "Accept-Language": "de,en;q=0.8"}
        )
        self._robots: dict[str, RobotFileParser | None] = {}
        self._last: dict[str, float] = {}
        self.requests_made = 0

    # -- robots ---------------------------------------------------------
    def _robots_for(self, host: str) -> RobotFileParser | None:
        if host not in self._robots:
            rp: RobotFileParser | None = RobotFileParser()
            try:
                r = self.session.get(f"https://{host}/robots.txt", timeout=self.timeout)
                if r.status_code == 200:
                    rp.parse(r.text.splitlines())
                elif r.status_code in (401, 403):
                    raise FetchError(f"{host}: robots.txt verweigert ({r.status_code})")
                else:
                    rp = None  # keine robots.txt -> keine Einschraenkung
            except requests.RequestException as e:
                raise FetchError(f"{host}: robots.txt nicht abrufbar ({e})") from e
            self._robots[host] = rp
        return self._robots[host]

    def allowed(self, url: str) -> bool:
        rp = self._robots_for(urlsplit(url).netloc)
        return True if rp is None else rp.can_fetch("*", url)

    def _wait(self, host: str) -> None:
        rp = self._robots.get(host)
        crawl = (rp.crawl_delay("*") if rp else None) or 0
        pause = max(self.delay, float(crawl))
        rest = self._last.get(host, 0) + pause - time.monotonic()
        if rest > 0:
            time.sleep(rest)

    # -- cache ----------------------------------------------------------
    def _cache_path(self, url: str) -> Path | None:
        if not self.cache_dir or self.cache_hours <= 0:
            return None
        return self.cache_dir / (hashlib.sha1(url.encode()).hexdigest() + ".html")

    # -- abruf ----------------------------------------------------------
    def get(self, url: str) -> str | None:
        """HTML der Seite; None bei 404 (keine Treffer). FetchError bei Sperre/Fehler."""
        cp = self._cache_path(url)
        if cp and cp.exists() and time.time() - cp.stat().st_mtime < self.cache_hours * 3600:
            return cp.read_text(encoding="utf-8")
        host = urlsplit(url).netloc
        if not self.allowed(url):
            raise FetchError(f"robots.txt untersagt {url}")
        self._wait(host)
        try:
            r = self.session.get(url, timeout=self.timeout)
        except requests.RequestException as e:
            raise FetchError(f"{url}: {e}") from e
        finally:
            self._last[host] = time.monotonic()
            self.requests_made += 1
        if r.status_code == 404:
            return None
        if r.status_code != 200:
            raise FetchError(f"{url}: HTTP {r.status_code}")
        r.encoding = r.encoding if r.encoding and r.encoding.lower() != "iso-8859-1" else r.apparent_encoding
        if cp:
            cp.parent.mkdir(parents=True, exist_ok=True)
            cp.write_text(r.text, encoding="utf-8")
        return r.text
