from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


SENSITIVE_HEADERS = {"cookie", "authorization", "set-cookie"}


@dataclass(frozen=True)
class HarRequest:
    method: str
    url: str
    status: int
    mime_type: str
    request_headers: dict[str, str]
    response_headers: dict[str, str]
    post_text: str | None
    response_text: str | None

    @property
    def host(self) -> str:
        return urlparse(self.url).netloc

    @property
    def path(self) -> str:
        return urlparse(self.url).path

    @property
    def url_without_query(self) -> str:
        parsed = urlparse(self.url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

    @property
    def is_json_response(self) -> bool:
        return "json" in self.mime_type.lower()

    def post_json(self) -> dict[str, Any] | None:
        if not self.post_text:
            return None
        try:
            value = json.loads(self.post_text)
        except json.JSONDecodeError:
            return None
        return value if isinstance(value, dict) else None

    def response_json(self) -> dict[str, Any] | None:
        if not self.response_text:
            return None
        try:
            value = json.loads(self.response_text)
        except json.JSONDecodeError:
            return None
        return value if isinstance(value, dict) else None


@dataclass(frozen=True)
class GeneXusTrace:
    url: str
    obj_class: str
    events: tuple[str, ...]
    grids: tuple[str, ...]
    hash_count: int
    parm_count: int
    response_keys: tuple[str, ...]
    command_names: tuple[str, ...]


def load_har(path: Path) -> list[HarRequest]:
    with path.open("r", encoding="utf-8") as file:
        raw = json.load(file)

    entries = raw.get("log", {}).get("entries", [])
    requests: list[HarRequest] = []
    for entry in entries:
        request = entry.get("request", {})
        response = entry.get("response", {})
        content = response.get("content", {})
        post_data = request.get("postData") or {}
        requests.append(
            HarRequest(
                method=str(request.get("method", "")),
                url=str(request.get("url", "")),
                status=int(response.get("status", 0) or 0),
                mime_type=str(content.get("mimeType", "")),
                request_headers=_headers_to_dict(request.get("headers", [])),
                response_headers=_headers_to_dict(response.get("headers", [])),
                post_text=post_data.get("text"),
                response_text=content.get("text"),
            )
        )
    return requests


def summarize_requests(requests: list[HarRequest]) -> dict[str, Counter[str]]:
    hosts: Counter[str] = Counter()
    endpoints: Counter[str] = Counter()
    methods: Counter[str] = Counter()
    statuses: Counter[str] = Counter()

    for request in requests:
        hosts[request.host] += 1
        endpoints[f"{request.method} {request.status} {request.url_without_query}"] += 1
        methods[request.method] += 1
        statuses[str(request.status)] += 1

    return {
        "hosts": hosts,
        "endpoints": endpoints,
        "methods": methods,
        "statuses": statuses,
    }


def extract_genexus_traces(requests: list[HarRequest]) -> list[GeneXusTrace]:
    traces: list[GeneXusTrace] = []
    for request in requests:
        if request.method != "POST":
            continue
        body = request.post_json()
        if not body:
            continue
        if "objClass" not in body and "events" not in body:
            continue

        response = request.response_json() or {}
        commands = response.get("gxCommands") or []
        traces.append(
            GeneXusTrace(
                url=request.url,
                obj_class=str(body.get("objClass", "")),
                events=tuple(str(event) for event in body.get("events", [])),
                grids=tuple(sorted((body.get("grids") or {}).keys())),
                hash_count=len(body.get("hsh") or []),
                parm_count=len(body.get("parms") or []),
                response_keys=tuple(sorted(response.keys())),
                command_names=tuple(_command_name(command) for command in commands),
            )
        )
    return traces


def extract_public_links(requests: list[HarRequest], contains: str = "") -> list[str]:
    links: set[str] = set()
    needle = contains.lower()
    for request in requests:
        if not request.response_text or "html" not in request.mime_type.lower():
            continue
        # Good enough for link discovery in static public pages; the live client uses HTML parsing.
        for marker in ('href="', "href='"):
            quote = marker[-1]
            start = 0
            while True:
                idx = request.response_text.find(marker, start)
                if idx == -1:
                    break
                idx += len(marker)
                end = request.response_text.find(quote, idx)
                if end == -1:
                    break
                href = request.response_text[idx:end]
                if not needle or needle in href.lower():
                    links.add(href)
                start = end + 1
    return sorted(links)


def redact_value(value: str, keep: int = 6) -> str:
    if len(value) <= keep * 2:
        return "<redacted>"
    return f"{value[:keep]}...{value[-keep:]}"


def safe_headers(headers: dict[str, str]) -> dict[str, str]:
    redacted: dict[str, str] = {}
    for name, value in headers.items():
        if name.lower() in SENSITIVE_HEADERS:
            redacted[name] = redact_value(value)
        else:
            redacted[name] = value
    return redacted


def extract_cookies_for_host(requests: list[HarRequest], host: str) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for request in requests:
        if request.host != host:
            continue
        header = _case_insensitive_get(request.request_headers, "cookie")
        if header:
            cookies.update(_parse_cookie_header(header))
    return cookies


def _headers_to_dict(headers: list[dict[str, Any]]) -> dict[str, str]:
    return {str(header.get("name", "")): str(header.get("value", "")) for header in headers}


def _case_insensitive_get(headers: dict[str, str], name: str) -> str | None:
    lower_name = name.lower()
    for key, value in headers.items():
        if key.lower() == lower_name:
            return value
    return None


def _parse_cookie_header(header: str) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for part in header.split(";"):
        if "=" not in part:
            continue
        name, value = part.strip().split("=", 1)
        if name:
            cookies[name] = value
    return cookies


def _command_name(command: Any) -> str:
    if isinstance(command, dict):
        if len(command) == 1:
            return next(iter(command))
        for key in ("name", "Name", "cmd"):
            if key in command:
                return str(command[key])
        return ",".join(sorted(command.keys()))
    return type(command).__name__
