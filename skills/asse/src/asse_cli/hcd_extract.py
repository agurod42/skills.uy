from __future__ import annotations

from dataclasses import dataclass
import html
import json
import re
from typing import Any, Iterable
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from asse_cli.har import HarRequest


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


def extract_hcd_timeline_from_har(requests: list[HarRequest]) -> list[HcdEncounter]:
    best: list[HcdEncounter] = []
    for request in requests:
        if "historiaclinicadigital.gub.uy" not in request.host:
            continue
        if "com.mihcd.hc" not in request.url:
            continue
        encounters = extract_hcd_timeline(request.response_text or "")
        if len(encounters) > len(best):
            best = encounters
    return best


def extract_hcd_vaccine_report_from_har(requests: list[HarRequest]) -> HcdVaccineReport | None:
    best: HcdVaccineReport | None = None
    for request in requests:
        if "historiaclinicadigital.gub.uy" not in request.host:
            continue
        if "com.mihcd.historiavacunas" not in request.url:
            continue
        report = extract_hcd_vaccine_report(request.response_text or "")
        if report and (best is None or report.report_url or report.vaccinations):
            best = report
    return best


def extract_hcd_accesses_from_har(requests: list[HarRequest]) -> list[HcdAccessLogEntry]:
    best: list[HcdAccessLogEntry] = []
    for request in requests:
        if "historiaclinicadigital.gub.uy" not in request.host:
            continue
        if "historiaaccesos" not in request.url and "contenedoraccesos" not in request.url:
            continue
        accesses = extract_hcd_accesses(request.response_text or "")
        if len(accesses) > len(best):
            best = accesses
    return best


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


def _text(value: Any) -> str:
    if value is None:
        return ""
    return _compact_text(html.unescape(str(value)))


def _compact_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()
