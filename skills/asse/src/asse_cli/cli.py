from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from asse_cli.client import AsseClient, AsseSession
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
    summarize_requests,
)

app = typer.Typer(help="CLI experimental para Agenda Web de ASSE.")
har_app = typer.Typer(help="Inspecciona capturas HAR.")
session_app = typer.Typer(help="Gestiona sesion local.")
reservas_app = typer.Typer(help="Consulta reservas con una sesion valida.")
app.add_typer(har_app, name="har")
app.add_typer(session_app, name="session")
app.add_typer(reservas_app, name="reservas")


DEFAULT_SESSION = Path.home() / ".asse-cli" / "session.json"


@har_app.command("summary")
def har_summary(
    har_path: Annotated[Path, typer.Argument(exists=True, file_okay=True, dir_okay=False)],
    limit: Annotated[int, typer.Option("--limit", "-n")] = 20,
) -> None:
    requests = load_har(har_path)
    summary = summarize_requests(requests)
    typer.echo(f"Requests: {len(requests)}")
    _print_counter("Hosts", summary["hosts"], limit)
    _print_counter("Methods", summary["methods"], limit)
    _print_counter("Statuses", summary["statuses"], limit)
    _print_counter("Endpoints", summary["endpoints"], limit)


@har_app.command("events")
def har_events(
    har_path: Annotated[Path, typer.Argument(exists=True, file_okay=True, dir_okay=False)],
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    traces = extract_genexus_traces(load_har(har_path))
    if json_output:
        typer.echo(json.dumps([trace.__dict__ for trace in traces], indent=2, ensure_ascii=False))
        return
    for trace in traces:
        typer.echo(
            f"{trace.obj_class:14} {','.join(trace.events):42} "
            f"parms={trace.parm_count:<2} hsh={trace.hash_count:<2} "
            f"commands={','.join(trace.command_names) or '-'}"
        )


@har_app.command("public-links")
def har_public_links(
    har_path: Annotated[Path, typer.Argument(exists=True, file_okay=True, dir_okay=False)],
    contains: Annotated[str, typer.Option("--contains", "-c")] = "agenda",
) -> None:
    for link in extract_public_links(load_har(har_path), contains=contains):
        typer.echo(link)


@har_app.command("reservations")
def har_reservations(
    har_path: Annotated[Path, typer.Argument(exists=True, file_okay=True, dir_okay=False)],
    json_output: Annotated[bool, typer.Option("--json")] = False,
    show_codes: Annotated[bool, typer.Option("--show-codes")] = False,
) -> None:
    reservations = extract_reservations_from_har(load_har(har_path))
    if json_output:
        typer.echo(json.dumps([item.__dict__ for item in reservations], indent=2, ensure_ascii=False))
        return
    if not reservations:
        typer.echo("No encontre reservas en el HAR.")
        return
    for item in reservations:
        code = item.consultation_code if show_codes else _redact(item.consultation_code)
        typer.echo(
            f"{item.row:02d} | {item.date} | {item.service} | "
            f"{item.professional} | {item.number_and_time} | {code}"
        )


@har_app.command("appointment-flow")
def har_appointment_flow(
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


@session_app.command("login-url")
def session_login_url() -> None:
    client = AsseClient()
    try:
        typer.echo(client.discover_login_url())
    finally:
        client.close()


@session_app.command("import-har-cookies")
def session_import_har_cookies(
    har_path: Annotated[Path, typer.Argument(exists=True, file_okay=True, dir_okay=False)],
    session_path: Annotated[Path, typer.Option("--session")] = DEFAULT_SESSION,
    host: Annotated[str, typer.Option("--host")] = "agendaweb.asse.uy",
) -> None:
    cookies = extract_cookies_for_host(load_har(har_path), host)
    if not cookies:
        typer.echo(f"No encontre cookies para {host}.")
        raise typer.Exit(1)
    session = AsseSession(cookies=cookies)
    session.save(session_path)
    typer.echo(f"Sesion escrita en {session_path}")
    for name in sorted(cookies):
        typer.echo(f"  {name}={_redact(cookies[name])}")


@session_app.command("login-browser")
def session_login_browser(
    session_path: Annotated[Path, typer.Option("--session")] = DEFAULT_SESSION,
    headless: Annotated[bool, typer.Option("--headless")] = False,
) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise typer.BadParameter(
            'Falta Playwright. Instalalo con: pip install -e ".[browser]" && playwright install chromium'
        ) from exc

    client = AsseClient()
    try:
        login_url = client.discover_login_url()
    finally:
        client.close()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()
        page.goto(login_url)
        typer.echo("Complete el login en el navegador. Esperando Agenda Web...")
        page.wait_for_url("**/agendaweb/servlet/com.agendaweb.*", timeout=180_000)
        cookies = {
            cookie["name"]: cookie["value"]
            for cookie in context.cookies()
            if cookie.get("domain", "").endswith("agendaweb.asse.uy")
        }
        current_url = page.url
        browser.close()

    if not cookies:
        typer.echo("El navegador no devolvio cookies de agendaweb.asse.uy.")
        raise typer.Exit(1)
    AsseSession(cookies=cookies, current_url=current_url).save(session_path)
    typer.echo(f"Sesion guardada en {session_path}")


@session_app.command("show")
def session_show(
    session_path: Annotated[Path, typer.Option("--session")] = DEFAULT_SESSION,
) -> None:
    if not session_path.exists():
        typer.echo(f"No existe sesion local: {session_path}")
        raise typer.Exit(1)
    session = AsseSession.load(session_path)
    typer.echo(f"Session file: {session_path}")
    typer.echo(f"Current URL: {session.current_url or '-'}")
    typer.echo("Cookies:")
    for name, value in sorted(session.cookies.items()):
        typer.echo(f"  {name}={_redact(value)}")


@reservas_app.command("list")
def reservas_list(
    session_path: Annotated[Path, typer.Option("--session")] = DEFAULT_SESSION,
    show_codes: Annotated[bool, typer.Option("--show-codes")] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    if not session_path.exists():
        typer.echo(f"No existe sesion local: {session_path}")
        typer.echo("Use primero: asse session login-browser")
        raise typer.Exit(1)
    session = AsseSession.load(session_path)
    client = AsseClient(session)
    try:
        response = client.get("com.agendaweb.misreservas")
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
            typer.echo("No pude extraer reservas. La sesion puede estar vencida o la pagina cambio.")
            typer.echo(f"URL final: {response.url}")
            if summary:
                typer.echo(f"Respuesta: {summary}")
        raise typer.Exit(1)
    if json_output:
        typer.echo(
            json.dumps(
                [_reservation_to_dict(item, show_codes=show_codes) for item in reservations],
                indent=2,
                ensure_ascii=False,
            )
        )
        return
    for item in reservations:
        code = item.consultation_code if show_codes else _redact(item.consultation_code)
        typer.echo(
            f"{item.row:02d} | {item.date} | {item.service} | "
            f"{item.professional} | {item.number_and_time} | {code}"
        )


def _print_counter(title: str, counter: object, limit: int) -> None:
    typer.echo(f"\n{title}:")
    for value, count in counter.most_common(limit):  # type: ignore[attr-defined]
        typer.echo(f"  {count:4d}  {value}")


def _redact(value: str) -> str:
    if len(value) < 14:
        return "<redacted>"
    return f"{value[:6]}...{value[-6:]}"


def _reservation_to_dict(item: Reservation, show_codes: bool = False) -> dict[str, object]:
    return {
        "row": item.row,
        "date": item.date,
        "service": item.service,
        "professional": item.professional,
        "number_and_time": item.number_and_time,
        "consultation_code": item.consultation_code
        if show_codes
        else _redact(item.consultation_code),
    }


if __name__ == "__main__":
    app()
