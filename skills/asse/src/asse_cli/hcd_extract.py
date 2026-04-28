from __future__ import annotations

from dataclasses import dataclass
import base64
import html
import json
import re
from typing import Any, Iterable
from urllib.parse import urljoin

from bs4 import BeautifulSoup


HCD_SERVLET_BASE = "https://historiaclinicadigital.gub.uy/mihcd/servlet/"


@dataclass(frozen=True)
class HcdEncounter:
    row: int
    date: str
    category: str
    provider: str
    provider_detail: str
    specialty: str
    professional: str
    prescription_text: str
    prescription_url: str


@dataclass(frozen=True)
class HcdVaccination:
    vaccine: str
    dose: str
    administration_date: str
    lot: str
    age: str
    vaccinator: str


@dataclass(frozen=True)
class HcdVaccineReport:
    report_url: str
    notice: str
    vaccinations: tuple[HcdVaccination, ...]


@dataclass(frozen=True)
class HcdAccessLogEntry:
    access_type: str
    date_time: str
    provider: str
    oid: str
    observation: str
    detail: str
    emergency: bool


@dataclass(frozen=True)
class HcdVisitDocument:
    row: int
    title: str
    date: str
    category: str
    provider: str
    professional: str
    event_date: str
    text: str


@dataclass(frozen=True)
class HcdVisitTarget:
    row: int
    date: str
    category: str
    provider: str
    specialty: str
    professional: str
    parms: tuple[str, str, str, str]
    hsh: tuple[dict[str, str], ...]


def extract_hcd_visit_targets(content: str) -> list[HcdVisitTarget]:
    values = _flat_values_from_content(content)
    suffixes = sorted(
        {
            match.group(1)
            for key in values
            if (match := re.match(r"gxhash_vDOCREPOID_(\d{4})$", key))
        }
    )
    targets: list[HcdVisitTarget] = []
    for suffix in suffixes:
        hash_names = ("vDOCREPOID", "vDOCUNIQUEID", "vDOCFECHA", "vDOCCATEGORIA")
        hashes = tuple(
            {"hsh": _text(values.get(f"gxhash_{name}_{suffix}")), "row": suffix}
            for name in hash_names
        )
        if any(not item["hsh"] for item in hashes):
            continue
        parms = tuple(
            _text(values.get(f"{name}_{suffix}")) or _gx_hash_value(item["hsh"])
            for name, item in zip(hash_names, hashes, strict=True)
        )
        if any(not item for item in parms):
            continue
        targets.append(
            HcdVisitTarget(
                row=int(suffix),
                date=_text(values.get(f"HCHISTORYLINEIMAGE_{suffix}_Fecha")),
                category=parms[3],
                provider=_text(values.get(f"HCHISTORYLINEIMAGE_{suffix}_Nombreprestador"))
                or _text(values.get(f"HCHISTORYLINEIMAGE_{suffix}_Datainfoextraprestador")),
                specialty=_text(values.get(f"HCHISTORYLINEDATA_{suffix}_Especialidad")),
                professional=_text(values.get(f"HCHISTORYLINEDATA_{suffix}_Profesional")),
                parms=parms,  # type: ignore[arg-type]
                hsh=hashes,
            )
        )
    return targets


def extract_hcd_ajax_security_token(content: str) -> str:
    values = _flat_values_from_content(content)
    ajax_key = _text(values.get("GX_AJAX_KEY")) or _text(values.get("GX_AJAX_IV"))
    ajax_security_token = _text(values.get("AJAX_SECURITY_TOKEN"))
    if not ajax_key or len(ajax_security_token) < 32:
        return ""
    return f"{ajax_key}{ajax_security_token[:32]}"


def extract_hcd_security_headers(content: str) -> dict[str, str]:
    values = _flat_values_from_content(content)
    headers: dict[str, str] = {}
    ajax_security_token = _text(values.get("AJAX_SECURITY_TOKEN"))
    gx_auth_token = _text(values.get("GX_AUTH_HC"))
    if ajax_security_token:
        headers["AJAX_SECURITY_TOKEN"] = ajax_security_token
    if gx_auth_token:
        headers["X-GXAUTH-TOKEN"] = gx_auth_token
    return headers


def extract_hcd_visit_wrapper_meta(content: str) -> dict[str, str]:
    values = _flat_values_from_content(content)
    return {
        "date": _text(values.get("vFECHASTRING")),
        "category": _text(values.get("vCATEGORIA")),
    }


def extract_hcd_visualizer_url(response: dict[str, Any]) -> str:
    for command in response.get("gxCommands") or []:
        value = _find_visualizer_url(command)
        if value:
            return value
    return ""


def extract_hcd_cda_iframe_url(content: str) -> str:
    soup = BeautifulSoup(content, "html.parser")
    iframe = soup.find("iframe", src=True)
    if iframe:
        return urljoin(HCD_SERVLET_BASE, str(iframe["src"]))
    match = re.search(r"com\.mihcd\.aopencdasesion[^\"'<>\s]*", content)
    return urljoin(HCD_SERVLET_BASE, match.group(0)) if match else ""


def extract_hcd_visit_document(
    content: str,
    *,
    meta: dict[str, str] | None = None,
    row: int = 1,
) -> HcdVisitDocument | None:
    if not content:
        return None
    soup = BeautifulSoup(content, "html.parser")
    title = _compact_text(soup.title.get_text(" ")) if soup.title else ""
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = _lines_text(soup)
    if not text:
        return None
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    meta = meta or {}
    return HcdVisitDocument(
        row=row,
        title=title,
        date=meta.get("date", ""),
        category=meta.get("category", ""),
        provider=_value_after_label(lines, "Prestador"),
        professional=_value_after_label(lines, "Profesional"),
        event_date=_value_after_label(lines, "Fecha del evento"),
        text=text,
    )


def extract_hcd_timeline(content: str) -> list[HcdEncounter]:
    values = _flat_values_from_content(content)
    suffixes = sorted(
        {
            match.group(1)
            for key in values
            if (match := re.match(r"HCHISTORYLINEIMAGE_(\d{4})_Fecha$", key))
        }
    )
    encounters: list[HcdEncounter] = []
    for suffix in suffixes:
        row = int(suffix)
        date = _text(values.get(f"HCHISTORYLINEIMAGE_{suffix}_Fecha"))
        specialty = _text(values.get(f"HCHISTORYLINEDATA_{suffix}_Especialidad"))
        professional = _text(values.get(f"HCHISTORYLINEDATA_{suffix}_Profesional"))
        provider = _text(values.get(f"HCHISTORYLINEIMAGE_{suffix}_Nombreprestador"))
        provider_detail = _text(values.get(f"HCHISTORYLINEIMAGE_{suffix}_Datainfoextraprestador"))
        category = _text(values.get(f"vDOCCATEGORIA_{suffix}"))
        prescription_text = _text(values.get(f"HCHISTORYLINEDATA_{suffix}_Textoprescripcion"))
        prescription_url = _text(values.get(f"HCHISTORYLINEDATA_{suffix}_Urlprescripcion"))
        if not any((date, specialty, professional, provider, prescription_text, prescription_url)):
            continue
        encounters.append(
            HcdEncounter(
                row=row,
                date=date,
                category=category,
                provider=provider,
                provider_detail=provider_detail,
                specialty=specialty,
                professional=professional,
                prescription_text=prescription_text,
                prescription_url=prescription_url,
            )
        )
    return encounters


def extract_hcd_vaccine_report(content: str) -> HcdVaccineReport | None:
    if not content:
        return None
    soup = BeautifulSoup(content, "html.parser")
    report_url = ""
    iframe = soup.find("iframe", src=True)
    if iframe:
        report_url = urljoin(HCD_SERVLET_BASE, str(iframe["src"]))
    if not report_url:
        match = re.search(r"com\.mihcd\.areportevacunacion\?[^\"'<>\s]+", content)
        if match:
            report_url = urljoin(HCD_SERVLET_BASE, match.group(0))

    notice = ""
    notice_tag = soup.find(id="VISUALIZARCDAHTML")
    if notice_tag:
        notice = _compact_text(notice_tag.get_text(" "))

    vaccinations = tuple(_extract_vaccinations(_flat_values_from_content(content)))
    if not report_url and not notice and not vaccinations:
        return None
    return HcdVaccineReport(report_url=report_url, notice=notice, vaccinations=vaccinations)


def extract_hcd_accesses(content: str) -> list[HcdAccessLogEntry]:
    if not content:
        return []
    root = _json_from_text(content)
    objects: list[dict[str, Any]] = []
    if isinstance(root, dict):
        objects.extend(_walk_dicts(root))
    else:
        values = _flat_values_from_content(content)
        objects.extend(_walk_dicts(values))

    entries: list[HcdAccessLogEntry] = []
    seen: set[tuple[str, str, str, str]] = set()
    for item in objects:
        if "HistorialAccesosFechaHora" not in item:
            continue
        entry = HcdAccessLogEntry(
            access_type=_text(item.get("HistorialAccesosType")),
            date_time=_text(item.get("HistorialAccesosFechaHora")),
            provider=_text(item.get("HistorialAccesosPrestador")),
            oid=_text(item.get("HistorialAccesosOid")),
            observation=_text(item.get("HistorialAccesosObservacion")),
            detail=_text(item.get("HistorialAccesosDetalle")),
            emergency=bool(item.get("HistorialAccesosEsEmergencia")),
        )
        key = (entry.date_time, entry.provider, entry.oid, entry.detail)
        if key in seen:
            continue
        seen.add(key)
        entries.append(entry)
    return entries


def _extract_vaccinations(values: dict[str, Any]) -> Iterable[HcdVaccination]:
    row_dicts = [
        item for item in _walk_dicts(values) if any(str(key).lower().startswith("vacuna") for key in item)
    ]
    seen: set[tuple[str, str, str]] = set()
    for item in row_dicts:
        vaccine = _first_text(item, "Vacuna", "VacunaNombre", "VacunaTipo")
        dose = _first_text(item, "Dosis", "VacunaDosis")
        administration_date = _first_text(
            item,
            "FechaAdmin",
            "FechaAdministracion",
            "VacunaFechaAdministracion",
        )
        lot = _first_text(item, "Lote", "VacunaLote")
        age = _first_text(item, "Edad", "VacunaEdad")
        vaccinator = _first_text(item, "Vacunatorio", "VacunaVacunatorio")
        if not any((vaccine, dose, administration_date, lot, age, vaccinator)):
            continue
        key = (vaccine, dose, administration_date)
        if key in seen:
            continue
        seen.add(key)
        yield HcdVaccination(
            vaccine=vaccine,
            dose=dose,
            administration_date=administration_date,
            lot=lot,
            age=age,
            vaccinator=vaccinator,
        )


def _flat_values_from_content(content: str) -> dict[str, Any]:
    if not content:
        return {}
    root = _json_from_text(content)
    if isinstance(root, dict):
        return _flat_values_from_response(root)

    state = _gx_state_from_html(content)
    if state:
        return state

    saved = _saved_json_response_from_html(content)
    if saved:
        return _flat_values_from_response(saved)

    return _regex_json_pairs(content)


def _flat_values_from_response(response: dict[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    if any(key in response for key in ("gxValues", "gxHiddens", "gxProps")):
        _merge_named_items(values, response.get("gxValues") or [])
        _merge_named_items(values, response.get("gxHiddens") or [])
        _merge_named_items(values, response.get("gxProps") or [])
        return values
    return dict(response)


def _gx_state_from_html(content: str) -> dict[str, Any]:
    soup = BeautifulSoup(content, "html.parser")
    field = soup.find("input", attrs={"name": "GXState"})
    if not field:
        return {}
    raw = field.get("value")
    if not isinstance(raw, str):
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _saved_json_response_from_html(content: str) -> dict[str, Any]:
    for match in re.finditer(r"gx\.ajax\.saveJsonResponse\((.*?)\);", content, re.S):
        raw = match.group(1).strip()
        value = _json_from_text(raw)
        if isinstance(value, str):
            value = _json_from_text(value)
        if isinstance(value, dict):
            return value
    return {}


def _regex_json_pairs(content: str) -> dict[str, Any]:
    values: dict[str, Any] = {}
    pattern = re.compile(
        r'"((?:HCHISTORYLINE(?:IMAGE|DATA)|vDOC)[A-Za-z0-9_]+)"\s*:\s*"((?:\\.|[^"\\])*)"'
    )
    for key, raw in pattern.findall(content):
        value = _json_from_text(f'"{raw}"')
        values[key] = value if isinstance(value, str) else raw
    return values


def _json_from_text(text: str) -> Any:
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _merge_named_items(target: dict[str, Any], items: list[Any] | dict[str, Any]) -> None:
    if isinstance(items, dict):
        target.update(items)
        return
    for item in items:
        if isinstance(item, dict):
            target.update(item)
        elif isinstance(item, list) and len(item) >= 2 and isinstance(item[0], str):
            target[item[0]] = item[1]


def _walk_dicts(value: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        found.append(value)
        for child in value.values():
            found.extend(_walk_dicts(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_walk_dicts(child))
    elif isinstance(value, str):
        nested = _json_from_text(value)
        if nested is not None and nested is not value:
            found.extend(_walk_dicts(nested))
    return found


def _first_text(item: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = _text(item.get(key))
        if value:
            return value
    return ""


def _gx_hash_value(token: str) -> str:
    parts = token.split(".")
    if len(parts) < 2:
        return ""
    payload = parts[1]
    payload += "=" * (-len(payload) % 4)
    try:
        value = json.loads(base64.urlsafe_b64decode(payload).decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return ""
    return _text(value.get("gx-val")) if isinstance(value, dict) else ""


def _find_visualizer_url(value: Any) -> str:
    if isinstance(value, str):
        return value if "visualizarcda" in value else ""
    if isinstance(value, list):
        for item in value:
            found = _find_visualizer_url(item)
            if found:
                return found
    if isinstance(value, dict):
        for item in value.values():
            found = _find_visualizer_url(item)
            if found:
                return found
    return ""


def _value_after_label(lines: list[str], label: str) -> str:
    for idx, line in enumerate(lines):
        if line == label and idx + 1 < len(lines):
            return lines[idx + 1]
        prefix = f"{label} "
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    return ""


def _text(value: Any) -> str:
    if value is None:
        return ""
    return _compact_text(html.unescape(str(value)))


def _compact_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _lines_text(soup: BeautifulSoup) -> str:
    lines: list[str] = []
    for line in soup.get_text("\n").splitlines():
        line = _compact_text(html.unescape(line))
        if line:
            lines.append(line)
    return "\n".join(lines)
