from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from http.cookiejar import Cookie, CookieJar
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from asse_cli.genexus import GeneXusEvent, GeneXusState


@dataclass
class WebSession:
    cookies: dict[str, str] = field(default_factory=dict)
    base_url: str = ""
    state: GeneXusState = field(default_factory=GeneXusState)
    current_url: str | None = None

    @classmethod
    def load(cls, path: Path, default_base_url: str) -> "WebSession":
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            cookies=dict(data.get("cookies", {})),
            base_url=str(data.get("base_url") or default_base_url),
            current_url=data.get("current_url"),
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "cookies": self.cookies,
                    "base_url": self.base_url,
                    "current_url": self.current_url,
                },
                indent=2,
            ),
            encoding="utf-8",
        )


class WebClient:
    def __init__(
        self,
        *,
        session: WebSession | None,
        base_url: str,
        host: str,
        origin: str,
        preferred_cookie_path: str,
        timeout: float = 30.0,
    ):
        self.host = host
        self.origin = origin
        self.preferred_cookie_path = preferred_cookie_path
        self.session = session or WebSession(base_url=base_url)
        if not self.session.base_url:
            self.session.base_url = base_url
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

    def get(self, servlet_or_url: str) -> httpx.Response:
        response = self.http.get(self._url(servlet_or_url))
        response.raise_for_status()
        self._capture_current_url(response)
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
                "Origin": self.origin,
                "Referer": self.session.current_url or self.session.base_url,
            },
        )
        response.raise_for_status()
        data = response.json()
        self.session.state.apply_response(data)
        self._capture_current_url(response)
        self._sync_session_cookies()
        return data

    def is_own_url(self, url: str) -> bool:
        return is_url_on_host(url, self.host)

    def _url(self, servlet_or_url: str) -> str:
        if servlet_or_url.startswith(("http://", "https://")):
            return servlet_or_url
        return urljoin(self.session.base_url, servlet_or_url)

    def _capture_current_url(self, response: httpx.Response) -> None:
        final_url = str(response.url)
        if self.is_own_url(final_url):
            self.session.current_url = final_url

    def _sync_session_cookies(self) -> None:
        self.session.cookies = session_cookies_from_jar(
            self.http.cookies.jar,
            host=self.host,
            preferred_path=self.preferred_cookie_path,
        )


def is_url_on_host(url: str, host: str) -> bool:
    return (urlparse(url).hostname or "") == host


def session_cookies_from_jar(
    jar: CookieJar,
    *,
    host: str,
    preferred_path: str = "/",
) -> dict[str, str]:
    selected: dict[str, tuple[int, str]] = {}
    for cookie in jar:
        score = _cookie_score(cookie, host=host, preferred_path=preferred_path)
        if score == 0:
            continue
        current = selected.get(cookie.name)
        if current is None or score >= current[0]:
            selected[cookie.name] = (score, cookie.value)
    return {name: value for name, (_, value) in selected.items()}


def _cookie_score(cookie: Cookie, *, host: str, preferred_path: str) -> int:
    domain = cookie.domain.lstrip(".")
    path = cookie.path or "/"
    if domain == host:
        return 4 if path.startswith(preferred_path) else 3
    if domain.endswith(f".{host}"):
        return 2
    if not domain:
        return 1
    return 0
