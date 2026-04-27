from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any

from bs4 import BeautifulSoup

from asse_cli.har import HarRequest


@dataclass(frozen=True)
class Reservation:
    row: int
    date: str
    service: str
    professional: str
    number_and_time: str
    consultation_code: str


@dataclass(frozen=True)
class AppointmentFlowStep:
    event: str
    url: str
    input_count: int
    output_names: tuple[str, ...]
    commands: tuple[str, ...]


def extract_reservations_from_har(requests: list[HarRequest]) -> list[Reservation]:
    for request in requests:
        body = request.post_json() or {}
        if body.get("objClass") != "misreservas":
            continue
        if "'VERHISTORICO'" not in body.get("events", []):
            continue
        response = request.response_json() or {}
        return extract_reservations_from_response(response)
    return []


def extract_reservations_from_html(html: str) -> list[Reservation]:
    response = extract_saved_json_response(html)
    if response:
        return extract_reservations_from_response(response)
    return _reservation_rows_from_hidden_input(html, "GridmisreservasContainerDataV")


def extract_reservations_from_response(response: dict[str, Any]) -> list[Reservation]:
    values = _response_values(response)
    rows = _reservation_rows(values)
    if rows:
        return rows
    data = _grid_data_from_hiddens(response, "GridmisreservasContainerDataV")
    if data:
        return _reservation_rows_from_grid_data(data)
    return []


def extract_appointment_flow(requests: list[HarRequest]) -> list[AppointmentFlowStep]:
    steps: list[AppointmentFlowStep] = []
    for request in requests:
        body = request.post_json() or {}
        if body.get("objClass") != "reservarcita":
            continue
        response = request.response_json() or {}
        events = body.get("events") or []
        event = "|".join(str(item) for item in events)
        steps.append(
            AppointmentFlowStep(
                event=event,
                url=request.url,
                input_count=len(body.get("parms") or []),
                output_names=tuple(sorted(_response_values(response).keys())),
                commands=tuple(_command_names(response.get("gxCommands") or [])),
            )
        )
    return steps


def _reservation_rows(values: dict[str, Any]) -> list[Reservation]:
    rows: list[Reservation] = []
    for key, value in sorted(values.items()):
        if not key.startswith("vCITAFECHA_"):
            continue
        suffix = key.rsplit("_", 1)[-1]
        rows.append(
            Reservation(
                row=int(suffix),
                date=str(value),
                service=str(values.get(f"vSERVICIONOMBRE_{suffix}", "")),
                professional=str(values.get(f"vCITAPROFESIONALNOMBRE_{suffix}", "")),
                number_and_time=str(values.get(f"vCITANUMEROYHORAAPROX_{suffix}", "")),
                consultation_code=str(values.get(f"vCITACONSULTACODIGOEXTERNO_{suffix}", "")),
            )
        )
    return rows


def _reservation_rows_from_grid_data(data: list[Any]) -> list[Reservation]:
    rows: list[Reservation] = []
    for idx, item in enumerate(data, start=1):
        if not isinstance(item, list) or len(item) < 8:
            continue
        rows.append(
            Reservation(
                row=idx,
                date=str(item[1]),
                service=str(item[2]),
                professional=str(item[3]),
                number_and_time=str(item[4]),
                consultation_code=str(item[7]),
            )
        )
    return rows


def extract_saved_json_response(html: str) -> dict[str, Any] | None:
    match = re.search(r"gx\.ajax\.saveJsonResponse\((\{.*?\})\);</script>", html, re.S)
    if not match:
        return None
    try:
        value = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def extract_html_text_summary(html: str, limit: int = 240) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = re.sub(r"\s+", " ", soup.get_text(" ")).strip()
    return text[:limit]


def _response_values(response: dict[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for item in response.get("gxValues") or []:
        if isinstance(item, dict):
            values.update(item)
    return values


def _grid_data_from_hiddens(response: dict[str, Any], name: str) -> list[Any]:
    hiddens = response.get("gxHiddens") or {}
    if not isinstance(hiddens, dict):
        return []
    raw = hiddens.get(name)
    if not isinstance(raw, str):
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return value if isinstance(value, list) else []


def _reservation_rows_from_hidden_input(html: str, name: str) -> list[Reservation]:
    soup = BeautifulSoup(html, "html.parser")
    field = soup.find("input", attrs={"name": name})
    if not field:
        return []
    raw = field.get("value")
    if not isinstance(raw, str):
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return _reservation_rows_from_grid_data(data) if isinstance(data, list) else []


def _command_names(commands: list[Any]) -> list[str]:
    names: list[str] = []
    for command in commands:
        if isinstance(command, dict) and len(command) == 1:
            names.append(next(iter(command)))
        elif isinstance(command, dict):
            names.append(",".join(sorted(command.keys())))
        else:
            names.append(type(command).__name__)
    return names
