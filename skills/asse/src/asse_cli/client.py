from __future__ import annotations

import json
import time
from http.cookiejar import Cookie, CookieJar
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from asse_cli.genexus import GeneXusEvent, GeneXusState


BASE_URL = "https://agendaweb.asse.uy/agendaweb/servlet/"
PUBLIC_HOME_URL = "https://www.asse.com.uy/home"
SESSION_COOKIE_HOST = "agendaweb.asse.uy"


@dataclass
class AsseSession:
    cookies: dict[str, str] = field(default_factory=dict)
    base_url: str = BASE_URL
    state: GeneXusState = field(default_factory=GeneXusState)
    current_url: str | None = None

    @classmethod
    def load(cls, path: Path) -> "AsseSession":
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(cookies=dict(data.get("cookies", {})), current_url=data.get("current_url"))

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"cookies": self.cookies, "current_url": self.current_url}, indent=2),
            encoding="utf-8",
        )


class AsseClient:
    def __init__(self, session: AsseSession | None = None, timeout: float = 30.0):
        self.session = session or AsseSession()
        self.http = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={
                "User-Agent": "asse-cli/0.1",
                "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
            },
            cookies=self.session.cookies,
        )

    def close(self) -> None:
        self._sync_session_cookies()
        self.http.close()

    def discover_login_url(self) -> str:
        response = self.http.get(PUBLIC_HOME_URL)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for anchor in soup.find_all("a", href=True):
            href = str(anchor["href"])
            if "agendaweb" in href and "aredirectlogin" in href:
                return href
        raise RuntimeError("No encontre el link de Agenda Web en la home publica de ASSE")

    def get(self, servlet_or_url: str) -> httpx.Response:
        url = self._url(servlet_or_url)
        response = self.http.get(url)
        response.raise_for_status()
        self.session.current_url = str(response.url)
        self._sync_session_cookies()
        return response

    def post_event(self, servlet_or_url: str, event: GeneXusEvent) -> dict[str, Any]:
        url = self._url(servlet_or_url)
        if "gx-no-cache=" not in url:
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}gx-no-cache={int(time.time() * 1000)}"
        response = self.http.post(
            url,
            json=event.to_payload(),
            headers={
                "Content-Type": "application/json",
                "Origin": "https://agendaweb.asse.uy",
                "Referer": self.session.current_url or self.base_url,
            },
        )
        response.raise_for_status()
        data = response.json()
        self.session.state.apply_response(data)
        self._sync_session_cookies()
        return data

    @property
    def base_url(self) -> str:
        return self.session.base_url

    def _url(self, servlet_or_url: str) -> str:
        if servlet_or_url.startswith(("http://", "https://")):
            return servlet_or_url
        return urljoin(self.base_url, servlet_or_url)

    def _sync_session_cookies(self) -> None:
        self.session.cookies = _session_cookies_from_jar(self.http.cookies.jar)


def _session_cookies_from_jar(jar: CookieJar) -> dict[str, str]:
    selected: dict[str, tuple[int, str]] = {}
    for cookie in jar:
        score = _cookie_score(cookie)
        if score == 0:
            continue
        current = selected.get(cookie.name)
        if current is None or score >= current[0]:
            selected[cookie.name] = (score, cookie.value)
    return {name: value for name, (_, value) in selected.items()}


def _cookie_score(cookie: Cookie) -> int:
    domain = cookie.domain.lstrip(".")
    path = cookie.path or "/"
    if domain == SESSION_COOKIE_HOST:
        return 4 if path.startswith("/agendaweb") else 3
    if domain.endswith(f".{SESSION_COOKIE_HOST}"):
        return 2
    if not domain:
        return 1
    return 0
