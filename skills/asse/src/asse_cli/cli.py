from __future__ import annotations

import json
import importlib
import subprocess
import sys
from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse

import typer

from asse_cli.agenda_client import AGENDA_BASE_URL, AGENDA_HOST, AgendaClient, is_agenda_url
from asse_cli.client import WebSession
from asse_cli.extract import (
    Reservation,
    extract_appointment_flow,
    extract_html_text_summary,
    extract_reservations_from_har,
    extract_reservations_from_html,
)
from asse_cli.har import (
    extract_cookies_for_host,
    extract_genexus_traces,
    extract_public_links,
    load_har,
    redact_value,
    summarize_requests,
)
from asse_cli.hcd_client import HCD_BASE_URL, HCD_HOST, HCD_LOGIN_URL, HcdClient, is_hcd_url
from asse_cli.hcd_extract import (
    HcdAccessLogEntry,
    HcdEncounter,
    HcdVaccination,
    HcdVaccineReport,
    extract_hcd_accesses,
    extract_hcd_accesses_from_har,
    extract_hcd_timeline,
    extract_hcd_timeline_from_har,
    extract_hcd_vaccine_report,
    extract_hcd_vaccine_report_from_har,
)


app = typer.Typer(help="CLI para flujos digitales de ASSE y salud pública uruguaya.")

agenda_app = typer.Typer(help="Agenda Web de ASSE: reservas, sesiones y HARs.")
agenda_har_app = typer.Typer(help="Inspecciona HARs de Agenda Web.")
agenda_session_app = typer.Typer(help="Gestiona sesion local de Agenda Web.")
agenda_reservas_app = typer.Typer(help="Consulta reservas de Agenda Web.")

hcd_app = typer.Typer(help="Historia Clinica Digital / HCEN.")
hcd_har_app = typer.Typer(help="Inspecciona HARs de Historia Clinica Digital.")
hcd_session_app = typer.Typer(help="Gestiona sesion local de Historia Clinica Digital.")

app.add_typer(agenda_app, name="agenda")
agenda_app.add_typer(agenda_har_app, name="har")
agenda_app.add_typer(agenda_session_app, name="session")
agenda_app.add_typer(agenda_reservas_app, name="reservas")

app.add_typer(hcd_app, name="hcd")
hcd_app.add_typer(hcd_har_app, name="har")
hcd_app.add_typer(hcd_session_app, name="session")


SESSION_DIR = Path.home() / ".asse-cli"
AGENDA_SESSION = SESSION_DIR / "agenda-session.json"
HCD_SESSION = SESSION_DIR / "hcd-session.json"


@agenda_har_app.command("summary")
def agenda_har_summary(
    har_path: Annotated[Path, typer.Argument(exists=True, file_okay=True, dir_okay=False)],
    limit: Annotated[int, typer.Option("--limit", "-n")] = 20,
) -> None:
    _print_har_summary(har_path, limit)


@agenda_har_app.command("events")
def agenda_har_events(
    har_path: Annotated[Path, typer.Argument(exists=True, file_okay=True, dir_okay=False)],
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    _print_har_events(har_path, json_output)


@agenda_har_app.command("public-links")
def agenda_har_public_links(
    har_path: Annotated[Path, typer.Argument(exists=True, file_okay=True, dir_okay=False)],
    contains: Annotated[str, typer.Option("--contains", "-c")] = "agenda",
) -> None:
    for link in extract_public_links(load_har(har_path), contains=contains):
        typer.echo(link)


@agenda_har_app.command("reservations")
def agenda_har_reservations(
    har_path: Annotated[Path, typer.Argument(exists=True, file_okay=True, dir_okay=False)],
    json_output: Annotated[bool, typer.Option("--json")] = False,
    show_codes: Annotated[bool, typer.Option("--show-codes")] = False,
) -> None:
    reservations = extract_reservations_from_har(load_har(har_path))
    _print_reservations(reservations, json_output=json_output, show_codes=show_codes)


@agenda_har_app.command("appointment-flow")
def agenda_har_appointment_flow(
    har_path: Annotated[Path, typer.Argument(exists=True, file_okay=True, dir_okay=False)],
) -> None:
    steps = extract_appointment_flow(load_har(har_path))
    if not steps:
        typer.echo("No encontre flujo de reserva en el HAR.")
        return
    for idx, step in enumerate(steps, start=1):
        output_preview = ", ".join(step.output_names[:8])
        if len(step.output_names) > 8:
            output_preview += ", ..."
        typer.echo(
            f"{idx:02d}. {step.event} inputs={step.input_count} "
            f"commands={','.join(step.commands) or '-'} outputs={output_preview or '-'}"
        )


@agenda_session_app.command("login-url")
def agenda_session_login_url() -> None:
    client = AgendaClient()
    try:
        typer.echo(client.discover_login_url())
    finally:
        client.close()


@agenda_session_app.command("import-har-cookies")
def agenda_session_import_har_cookies(
    har_path: Annotated[Path, typer.Argument(exists=True, file_okay=True, dir_okay=False)],
    session_path: Annotated[Path, typer.Option("--session")] = AGENDA_SESSION,
) -> None:
    _import_har_cookies(har_path, session_path, host=AGENDA_HOST, base_url=AGENDA_BASE_URL)


@agenda_session_app.command("login-browser")
def agenda_session_login_browser(
    session_path: Annotated[Path, typer.Option("--session")] = AGENDA_SESSION,
    headless: Annotated[bool, typer.Option("--headless")] = False,
) -> None:
    client = AgendaClient()
    try:
        login_url = client.discover_login_url()
    finally:
        client.close()
    _login_with_browser(
        login_url=login_url,
        wait_url="**/agendaweb/servlet/com.agendaweb.*",
        cookie_host=AGENDA_HOST,
        base_url=AGENDA_BASE_URL,
        session_path=session_path,
        headless=headless,
        prompt="Complete el login en el navegador. Esperando Agenda Web...",
    )


@agenda_session_app.command("show")
def agenda_session_show(
    session_path: Annotated[Path, typer.Option("--session")] = AGENDA_SESSION,
) -> None:
    _show_session(session_path, default_base_url=AGENDA_BASE_URL)


@agenda_reservas_app.command("list")
def agenda_reservas_list(
    session_path: Annotated[Path, typer.Option("--session")] = AGENDA_SESSION,
    show_codes: Annotated[bool, typer.Option("--show-codes")] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    if not session_path.exists():
        typer.echo(f"No existe sesion local: {session_path}")
        typer.echo("Use primero: asse agenda session login-browser")
        raise typer.Exit(1)
    session = WebSession.load(session_path, default_base_url=AGENDA_BASE_URL)
    client = AgendaClient(session)
    try:
        response = client.get("com.agendaweb.misreservas")
        final_url = str(response.url)
        if not is_agenda_url(final_url):
            typer.echo("Sesion expirada: ASSE redirigio fuera de Agenda Web.")
            typer.echo(f"URL final: {final_url}")
            typer.echo("Refresque con: asse agenda session login-browser")
            raise typer.Exit(1)
        reservations = extract_reservations_from_html(response.text)
    finally:
        session.save(session_path)
        client.close()

    if not reservations:
        summary = extract_html_text_summary(response.text)
        if "Usuario no afiliado" in summary or "Sistema exclusivo para afiliados" in summary:
            typer.echo("ASSE respondio: Usuario no afiliado.")
            typer.echo("La sesion es valida, pero ese usuario no tiene acceso a Mis Reservas.")
        else:
            typer.echo("No pude extraer reservas. La pagina puede haber cambiado.")
            typer.echo(f"URL final: {response.url}")
            if summary:
                typer.echo(f"Respuesta: {summary}")
        raise typer.Exit(1)
    _print_reservations(reservations, json_output=json_output, show_codes=show_codes)


@hcd_har_app.command("summary")
def hcd_har_summary(
    har_path: Annotated[Path, typer.Argument(exists=True, file_okay=True, dir_okay=False)],
    limit: Annotated[int, typer.Option("--limit", "-n")] = 20,
) -> None:
    _print_har_summary(har_path, limit)


@hcd_har_app.command("events")
def hcd_har_events(
    har_path: Annotated[Path, typer.Argument(exists=True, file_okay=True, dir_okay=False)],
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    _print_har_events(har_path, json_output)


@hcd_har_app.command("timeline")
def hcd_har_timeline(
    har_path: Annotated[Path, typer.Argument(exists=True, file_okay=True, dir_okay=False)],
    json_output: Annotated[bool, typer.Option("--json")] = False,
    show_links: Annotated[bool, typer.Option("--show-links")] = False,
) -> None:
    encounters = extract_hcd_timeline_from_har(load_har(har_path))
    _print_hcd_timeline(encounters, json_output=json_output, show_links=show_links)


@hcd_har_app.command("vacunas")
def hcd_har_vacunas(
    har_path: Annotated[Path, typer.Argument(exists=True, file_okay=True, dir_okay=False)],
    json_output: Annotated[bool, typer.Option("--json")] = False,
    show_links: Annotated[bool, typer.Option("--show-links")] = False,
) -> None:
    report = extract_hcd_vaccine_report_from_har(load_har(har_path))
    _print_hcd_vaccine_report(report, json_output=json_output, show_links=show_links)


@hcd_har_app.command("accesos")
def hcd_har_accesos(
    har_path: Annotated[Path, typer.Argument(exists=True, file_okay=True, dir_okay=False)],
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    accesses = extract_hcd_accesses_from_har(load_har(har_path))
    _print_hcd_accesses(accesses, json_output=json_output)


@hcd_session_app.command("login-browser")
def hcd_session_login_browser(
    session_path: Annotated[Path, typer.Option("--session")] = HCD_SESSION,
    headless: Annotated[bool, typer.Option("--headless")] = False,
) -> None:
    _login_with_browser(
        login_url=HCD_LOGIN_URL,
        wait_url="**/mihcd/servlet/com.mihcd.hc*",
        cookie_host=HCD_HOST,
        base_url=HCD_BASE_URL,
        session_path=session_path,
        headless=headless,
        prompt="Complete el login de ID Uruguay en el navegador. Esperando HCD...",
    )


@hcd_session_app.command("import-har-cookies")
def hcd_session_import_har_cookies(
    har_path: Annotated[Path, typer.Argument(exists=True, file_okay=True, dir_okay=False)],
    session_path: Annotated[Path, typer.Option("--session")] = HCD_SESSION,
) -> None:
    _import_har_cookies(har_path, session_path, host=HCD_HOST, base_url=HCD_BASE_URL)


@hcd_session_app.command("show")
def hcd_session_show(
    session_path: Annotated[Path, typer.Option("--session")] = HCD_SESSION,
) -> None:
    _show_session(session_path, default_base_url=HCD_BASE_URL)


@hcd_app.command("timeline")
def hcd_timeline(
    session_path: Annotated[Path, typer.Option("--session")] = HCD_SESSION,
    json_output: Annotated[bool, typer.Option("--json")] = False,
    show_links: Annotated[bool, typer.Option("--show-links")] = False,
) -> None:
    session = _load_required_session(session_path, HCD_BASE_URL, "asse hcd session login-browser")
    client = HcdClient(session)
    try:
        response = client.timeline()
        _ensure_hcd_response(response.url)
        encounters = extract_hcd_timeline(response.text)
    finally:
        session.save(session_path)
        client.close()
    _print_hcd_timeline(encounters, json_output=json_output, show_links=show_links)


@hcd_app.command("vacunas")
def hcd_vacunas(
    session_path: Annotated[Path, typer.Option("--session")] = HCD_SESSION,
    json_output: Annotated[bool, typer.Option("--json")] = False,
    show_links: Annotated[bool, typer.Option("--show-links")] = False,
) -> None:
    session = _load_required_session(session_path, HCD_BASE_URL, "asse hcd session login-browser")
    client = HcdClient(session)
    try:
        response = client.vaccines()
        _ensure_hcd_response(response.url)
        report = extract_hcd_vaccine_report(response.text)
    finally:
        session.save(session_path)
        client.close()
    _print_hcd_vaccine_report(report, json_output=json_output, show_links=show_links)


@hcd_app.command("accesos")
def hcd_accesos(
    session_path: Annotated[Path, typer.Option("--session")] = HCD_SESSION,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    session = _load_required_session(session_path, HCD_BASE_URL, "asse hcd session login-browser")
    client = HcdClient(session)
    try:
        response = client.accesses()
        _ensure_hcd_response(response.url)
        accesses = extract_hcd_accesses(response.text)
    finally:
        session.save(session_path)
        client.close()
    if not accesses:
        typer.echo("No pude extraer accesos desde el GET de HCD.")
        typer.echo("Ese panel suele cargar por un POST K2BTools firmado; use: asse hcd har accesos <har>")
        raise typer.Exit(1)
    _print_hcd_accesses(accesses, json_output=json_output)


def _print_har_summary(har_path: Path, limit: int) -> None:
    requests = load_har(har_path)
    summary = summarize_requests(requests)
    typer.echo(f"Requests: {len(requests)}")
    _print_counter("Hosts", summary["hosts"], limit)
    _print_counter("Methods", summary["methods"], limit)
    _print_counter("Statuses", summary["statuses"], limit)
    _print_counter("Endpoints", summary["endpoints"], limit)


def _print_har_events(har_path: Path, json_output: bool) -> None:
    traces = extract_genexus_traces(load_har(har_path))
    if json_output:
        typer.echo(json.dumps([trace.__dict__ for trace in traces], indent=2, ensure_ascii=False))
        return
    for trace in traces:
        typer.echo(
            f"{trace.obj_class:18} {','.join(trace.events):42} "
            f"parms={trace.parm_count:<2} hsh={trace.hash_count:<2} "
            f"commands={','.join(trace.command_names) or '-'}"
        )


def _import_har_cookies(har_path: Path, session_path: Path, *, host: str, base_url: str) -> None:
    cookies = extract_cookies_for_host(load_har(har_path), host)
    if not cookies:
        typer.echo(f"No encontre cookies para {host}.")
        raise typer.Exit(1)
    WebSession(cookies=cookies, base_url=base_url).save(session_path)
    typer.echo(f"Sesion escrita en {session_path}")
    for name in sorted(cookies):
        typer.echo(f"  {name}={redact_value(cookies[name])}")


def _login_with_browser(
    *,
    login_url: str,
    wait_url: str,
    cookie_host: str,
    base_url: str,
    session_path: Path,
    headless: bool,
    prompt: str,
) -> None:
    sync_playwright = _ensure_playwright()

    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=headless)
        except Exception as exc:
            if not _looks_like_missing_browser(exc):
                raise
            typer.echo("Chromium de Playwright no esta instalado. Instalando en este primer uso...")
            _run_bootstrap_command([sys.executable, "-m", "playwright", "install", "chromium"])
            browser = playwright.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()
        page.goto(login_url)
        typer.echo(prompt)
        page.wait_for_url(wait_url, timeout=180_000)
        cookies = {
            cookie["name"]: cookie["value"]
            for cookie in context.cookies()
            if cookie.get("domain", "").lstrip(".").endswith(cookie_host)
        }
        current_url = page.url
        browser.close()

    if not cookies:
        typer.echo(f"El navegador no devolvio cookies de {cookie_host}.")
        raise typer.Exit(1)
    WebSession(cookies=cookies, base_url=base_url, current_url=current_url).save(session_path)
    typer.echo(f"Sesion guardada en {session_path}")


def _ensure_playwright():
    try:
        from playwright.sync_api import sync_playwright

        return sync_playwright
    except ImportError:
        typer.echo("Playwright no esta instalado. Instalando en este primer uso...")
        _run_bootstrap_command([sys.executable, "-m", "pip", "install", "playwright>=1.45.0"])
        importlib.invalidate_caches()
        try:
            from playwright.sync_api import sync_playwright

            return sync_playwright
        except ImportError as exc:
            raise typer.BadParameter(
                "No pude importar Playwright despues de instalarlo. "
                f"Reintente manualmente con: {sys.executable} -m pip install playwright"
            ) from exc


def _run_bootstrap_command(command: list[str]) -> None:
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        raise typer.BadParameter(f"Fallo el bootstrap automatico: {' '.join(command)}")


def _looks_like_missing_browser(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        "executable doesn't exist" in message
        or "please run the following command" in message
        or "playwright install" in message
    )


def _show_session(session_path: Path, *, default_base_url: str) -> None:
    if not session_path.exists():
        typer.echo(f"No existe sesion local: {session_path}")
        raise typer.Exit(1)
    session = WebSession.load(session_path, default_base_url=default_base_url)
    typer.echo(f"Session file: {session_path}")
    typer.echo(f"Base URL: {session.base_url}")
    typer.echo(f"Current URL: {session.current_url or '-'}")
    typer.echo("Cookies:")
    for name, value in sorted(session.cookies.items()):
        typer.echo(f"  {name}={redact_value(value)}")


def _load_required_session(session_path: Path, default_base_url: str, command_hint: str) -> WebSession:
    if not session_path.exists():
        typer.echo(f"No existe sesion local: {session_path}")
        typer.echo(f"Use primero: {command_hint}")
        raise typer.Exit(1)
    return WebSession.load(session_path, default_base_url=default_base_url)


def _ensure_hcd_response(url: object) -> None:
    final_url = str(url)
    if is_hcd_url(final_url):
        return
    typer.echo("Sesion expirada: HCD redirigio fuera de Historia Clinica Digital.")
    typer.echo(f"URL final: {final_url}")
    typer.echo("Refresque con: asse hcd session login-browser")
    raise typer.Exit(1)


def _print_reservations(
    reservations: list[Reservation],
    *,
    json_output: bool,
    show_codes: bool,
) -> None:
    if json_output:
        typer.echo(
            json.dumps(
                [_reservation_to_dict(item, show_codes=show_codes) for item in reservations],
                indent=2,
                ensure_ascii=False,
            )
        )
        return
    if not reservations:
        typer.echo("No encontre reservas.")
        return
    for item in reservations:
        code = item.consultation_code if show_codes else redact_value(item.consultation_code)
        typer.echo(
            f"{item.row:02d} | {item.date} | {item.service} | "
            f"{item.professional} | {item.number_and_time} | {code}"
        )


def _print_hcd_timeline(
    encounters: list[HcdEncounter],
    *,
    json_output: bool,
    show_links: bool,
) -> None:
    if json_output:
        typer.echo(
            json.dumps(
                [_hcd_encounter_to_dict(item, show_links=show_links) for item in encounters],
                indent=2,
                ensure_ascii=False,
            )
        )
        return
    if not encounters:
        typer.echo("No encontre eventos clinicos.")
        return
    for item in encounters:
        provider = item.provider or item.provider_detail or "-"
        category = f" | {item.category}" if item.category else ""
        typer.echo(
            f"{item.row:02d} | {item.date}{category} | {provider} | "
            f"{item.specialty or '-'} | {item.professional or '-'}"
        )
        if item.prescription_url:
            typer.echo(f"     receta: {_redact_url(item.prescription_url, show=show_links)}")


def _print_hcd_vaccine_report(
    report: HcdVaccineReport | None,
    *,
    json_output: bool,
    show_links: bool,
) -> None:
    if json_output:
        typer.echo(
            json.dumps(
                _hcd_vaccine_report_to_dict(report, show_links=show_links) if report else None,
                indent=2,
                ensure_ascii=False,
            )
        )
        return
    if not report:
        typer.echo("No encontre historial de vacunas.")
        return
    if report.notice:
        typer.echo(report.notice)
    if report.report_url:
        typer.echo(f"Reporte: {_redact_url(report.report_url, show=show_links)}")
    if report.vaccinations:
        for item in report.vaccinations:
            typer.echo(
                f"{item.administration_date or '-'} | {item.vaccine or '-'} | "
                f"{item.dose or '-'} | {item.lot or '-'} | {item.vaccinator or '-'}"
            )


def _print_hcd_accesses(accesses: list[HcdAccessLogEntry], *, json_output: bool) -> None:
    if json_output:
        typer.echo(
            json.dumps([_hcd_access_to_dict(item) for item in accesses], indent=2, ensure_ascii=False)
        )
        return
    if not accesses:
        typer.echo("No encontre historial de accesos.")
        return
    for item in accesses:
        emergency = " emergencia" if item.emergency else ""
        typer.echo(
            f"{item.date_time} | {item.provider or '-'} | {item.access_type or '-'}{emergency} | "
            f"{item.detail or '-'}"
        )


def _print_counter(title: str, counter: object, limit: int) -> None:
    typer.echo(f"\n{title}:")
    for value, count in counter.most_common(limit):  # type: ignore[attr-defined]
        typer.echo(f"  {count:4d}  {value}")


def _redact_url(url: str, *, show: bool = False) -> str:
    if show or not url:
        return url
    parsed = urlparse(url)
    if parsed.scheme and parsed.netloc:
        if parsed.query:
            return f"{parsed.scheme}://{parsed.netloc}{parsed.path}?<redacted>"
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    return redact_value(url)


def _reservation_to_dict(item: Reservation, show_codes: bool = False) -> dict[str, object]:
    return {
        "row": item.row,
        "date": item.date,
        "service": item.service,
        "professional": item.professional,
        "number_and_time": item.number_and_time,
        "consultation_code": item.consultation_code
        if show_codes
        else redact_value(item.consultation_code),
    }


def _hcd_encounter_to_dict(item: HcdEncounter, *, show_links: bool = False) -> dict[str, object]:
    return {
        "row": item.row,
        "date": item.date,
        "category": item.category,
        "provider": item.provider,
        "provider_detail": item.provider_detail,
        "specialty": item.specialty,
        "professional": item.professional,
        "prescription_text": item.prescription_text,
        "prescription_url": _redact_url(item.prescription_url, show=show_links),
    }


def _hcd_vaccine_report_to_dict(
    report: HcdVaccineReport,
    *,
    show_links: bool = False,
) -> dict[str, object]:
    return {
        "report_url": _redact_url(report.report_url, show=show_links),
        "notice": report.notice,
        "vaccinations": [_hcd_vaccination_to_dict(item) for item in report.vaccinations],
    }


def _hcd_vaccination_to_dict(item: HcdVaccination) -> dict[str, object]:
    return {
        "vaccine": item.vaccine,
        "dose": item.dose,
        "administration_date": item.administration_date,
        "lot": item.lot,
        "age": item.age,
        "vaccinator": item.vaccinator,
    }


def _hcd_access_to_dict(item: HcdAccessLogEntry) -> dict[str, object]:
    return {
        "access_type": item.access_type,
        "date_time": item.date_time,
        "provider": item.provider,
        "oid": item.oid,
        "observation": item.observation,
        "detail": item.detail,
        "emergency": item.emergency,
    }


if __name__ == "__main__":
    app()
