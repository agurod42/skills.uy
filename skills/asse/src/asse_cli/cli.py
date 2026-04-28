from __future__ import annotations

import json
import importlib
import shutil
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
    extract_html_text_summary,
    extract_reservations_from_html,
)
from asse_cli.hcd_client import HCD_BASE_URL, HCD_HOST, HCD_LOGIN_URL, HcdClient, is_hcd_url
from asse_cli.hcd_extract import (
    HcdAccessLogEntry,
    HcdEncounter,
    HcdVisitDocument,
    HcdVisitTarget,
    HcdVaccination,
    HcdVaccineReport,
    extract_hcd_accesses,
    extract_hcd_timeline,
    extract_hcd_vaccine_report,
)


app = typer.Typer(help="CLI para flujos digitales de ASSE y salud pública uruguaya.")

agenda_app = typer.Typer(help="Agenda Web de ASSE: reservas y sesiones.")
agenda_session_app = typer.Typer(help="Gestiona sesion local de Agenda Web.")
agenda_reservas_app = typer.Typer(help="Consulta reservas de Agenda Web.")

hcd_app = typer.Typer(help="Historia Clinica Digital / HCEN.")
hcd_session_app = typer.Typer(help="Gestiona sesion local de Historia Clinica Digital.")

app.add_typer(agenda_app, name="agenda")
agenda_app.add_typer(agenda_session_app, name="session")
agenda_app.add_typer(agenda_reservas_app, name="reservas")

app.add_typer(hcd_app, name="hcd")
hcd_app.add_typer(hcd_session_app, name="session")


SESSION_DIR = Path.home() / ".asse-cli"
AGENDA_SESSION = SESSION_DIR / "agenda-session.json"
HCD_SESSION = SESSION_DIR / "hcd-session.json"


@agenda_session_app.command("login-url")
def agenda_session_login_url() -> None:
    client = AgendaClient()
    try:
        typer.echo(client.discover_login_url())
    finally:
        client.close()


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


@hcd_app.command("visitas")
def hcd_visitas(
    session_path: Annotated[Path, typer.Option("--session")] = HCD_SESSION,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    session = _load_required_session(session_path, HCD_BASE_URL, "asse hcd session login-browser")
    client = HcdClient(session)
    try:
        try:
            targets = client.visit_targets()
        except RuntimeError as exc:
            typer.echo(str(exc))
            raise typer.Exit(1) from exc
    finally:
        session.save(session_path)
        client.close()
    _print_hcd_visit_targets(targets, json_output=json_output)


@hcd_app.command("visita", context_settings={"allow_extra_args": True})
def hcd_visita(
    ctx: typer.Context,
    index_arg: Annotated[
        str | None,
        typer.Argument(metavar="INDEX", help="Numero de visita a abrir."),
    ] = None,
    session_path: Annotated[Path, typer.Option("--session")] = HCD_SESSION,
    index_option: Annotated[int | None, typer.Option("--index", "-i", min=1)] = None,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    index = _resolve_hcd_visit_index(index_arg, index_option, ctx.args)
    session = _load_required_session(session_path, HCD_BASE_URL, "asse hcd session login-browser")
    client = HcdClient(session)
    try:
        try:
            visit = client.visit_document(index)
        except (RuntimeError, ValueError) as exc:
            typer.echo(str(exc))
            raise typer.Exit(1) from exc
    finally:
        session.save(session_path)
        client.close()
    _print_hcd_visit(visit, json_output=json_output)


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
        typer.echo("Ese panel suele cargar por un POST K2BTools firmado; todavia no esta soportado live.")
        raise typer.Exit(1)
    _print_hcd_accesses(accesses, json_output=json_output)


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
        _install_python_requirement("playwright>=1.45.0")
        importlib.invalidate_caches()
        try:
            from playwright.sync_api import sync_playwright

            return sync_playwright
        except ImportError as exc:
            raise typer.BadParameter(
                "No pude importar Playwright despues de instalarlo. "
                f"Reintente manualmente con: {_manual_playwright_install_hint()}"
            ) from exc


def _install_python_requirement(requirement: str) -> None:
    candidates: list[tuple[str, list[list[str]]]] = [
        ("pip", [[sys.executable, "-m", "pip", "install", requirement]]),
    ]
    uv = _find_executable("uv")
    if uv:
        candidates.append(("uv", [[uv, "pip", "install", "--python", sys.executable, requirement]]))
    candidates.append(
        (
            "ensurepip",
            [
                [sys.executable, "-m", "ensurepip", "--upgrade"],
                [sys.executable, "-m", "pip", "install", requirement],
            ],
        )
    )

    failures: list[str] = []
    for name, steps in candidates:
        ok, failure = _run_bootstrap_steps(steps)
        if ok:
            return
        failures.append(f"{name}: {failure}")

    details = "\n".join(failures)
    raise typer.BadParameter(f"Fallo el bootstrap automatico instalando {requirement}.\n{details}")


def _run_bootstrap_steps(steps: list[list[str]]) -> tuple[bool, str]:
    for command in steps:
        result = subprocess.run(command, check=False, capture_output=True, text=True)
        if result.returncode != 0:
            return False, _format_bootstrap_failure(command, result)
    return True, ""


def _format_bootstrap_failure(command: list[str], result: subprocess.CompletedProcess[str]) -> str:
    output = "\n".join(
        part.strip() for part in (result.stderr or "", result.stdout or "") if part.strip()
    )
    if len(output) > 500:
        output = output[-500:]
    if output:
        return f"{' '.join(command)} -> {output}"
    return f"{' '.join(command)} -> exit {result.returncode}"


def _find_executable(name: str) -> str:
    found = shutil.which(name)
    if found:
        return found
    for directory in (
        Path.home() / ".local" / "bin",
        Path.home() / ".cargo" / "bin",
        Path("/opt/homebrew/bin"),
        Path("/usr/local/bin"),
    ):
        candidate = directory / name
        if candidate.is_file():
            return str(candidate)
    return ""


def _manual_playwright_install_hint() -> str:
    uv = _find_executable("uv")
    if uv:
        return f"{uv} pip install --python {sys.executable} playwright"
    return f"{sys.executable} -m ensurepip --upgrade && {sys.executable} -m pip install playwright"


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


def redact_value(value: str, keep: int = 6) -> str:
    if len(value) <= keep * 2:
        return "<redacted>"
    return f"{value[:keep]}...{value[-keep:]}"


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


def _resolve_hcd_visit_index(
    index_arg: str | None,
    index_option: int | None,
    extra_args: list[str],
) -> int:
    tokens = [token for token in [index_arg, *extra_args] if token]
    if index_option is not None:
        if tokens:
            raise typer.BadParameter("Use un indice como argumento o --index, no ambos.")
        return index_option
    if tokens and tokens[0] == "show":
        tokens = tokens[1:]
    if not tokens:
        return 1
    if len(tokens) != 1:
        raise typer.BadParameter("Uso: asse hcd visita [N]")
    try:
        index = int(tokens[0])
    except ValueError as exc:
        raise typer.BadParameter("El indice de visita debe ser un numero.") from exc
    if index < 1:
        raise typer.BadParameter("El indice de visita debe ser mayor o igual a 1.")
    return index


def _ensure_hcd_response(url: object) -> None:
    final_url = str(url)
    parsed_path = urlparse(final_url).path.lower()
    if is_hcd_url(final_url) and not parsed_path.endswith("/com.mihcd.loginweb"):
        return
    typer.echo("Sesion expirada: HCD redirigio al login.")
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


def _print_hcd_visit_targets(targets: list[HcdVisitTarget], *, json_output: bool) -> None:
    if json_output:
        typer.echo(
            json.dumps([_hcd_visit_target_to_dict(item) for item in targets], indent=2, ensure_ascii=False)
        )
        return
    if not targets:
        typer.echo("No encontre visitas abribles en HCD.")
        return
    for item in targets:
        provider = item.provider or "-"
        typer.echo(
            f"{item.row:02d} | {item.date or '-'} | {item.category or '-'} | "
            f"{provider} | {item.specialty or '-'} | {item.professional or '-'}"
        )


def _print_hcd_visit(visit: HcdVisitDocument, *, json_output: bool) -> None:
    if json_output:
        typer.echo(json.dumps(_hcd_visit_to_dict(visit), indent=2, ensure_ascii=False))
        return
    if visit.title:
        typer.echo(visit.title)
        typer.echo("")
    typer.echo(visit.text)


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


def _hcd_visit_summary_to_dict(item: HcdVisitDocument) -> dict[str, object]:
    return {
        "row": item.row,
        "title": item.title,
        "date": item.date,
        "category": item.category,
        "provider": item.provider,
        "professional": item.professional,
        "event_date": item.event_date,
    }


def _hcd_visit_to_dict(item: HcdVisitDocument) -> dict[str, object]:
    data = _hcd_visit_summary_to_dict(item)
    data["text"] = item.text
    return data


def _hcd_visit_target_to_dict(item: HcdVisitTarget) -> dict[str, object]:
    return {
        "row": item.row,
        "date": item.date,
        "category": item.category,
        "provider": item.provider,
        "specialty": item.specialty,
        "professional": item.professional,
    }


if __name__ == "__main__":
    app()
