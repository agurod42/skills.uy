from pathlib import Path

from asse_cli.extract import (
    extract_appointment_flow,
    extract_reservations_from_har,
    extract_reservations_from_html,
)
from asse_cli.har import extract_cookies_for_host, extract_genexus_traces, load_har


FIXTURES = Path("/Users/agurodriguez/Downloads")


def test_extract_genexus_events() -> None:
    requests = load_har(FIXTURES / "agendaweb.asse.uy.har")
    traces = extract_genexus_traces(requests)
    assert len(traces) == 13
    assert any(trace.obj_class == "reservarcita" and "'BUSCAR'" in trace.events for trace in traces)


def test_extract_reservations() -> None:
    requests = load_har(FIXTURES / "agendaweb.asse.uy.har")
    reservations = extract_reservations_from_har(requests)
    assert len(reservations) >= 50
    assert reservations[0].date
    assert reservations[0].service


def test_extract_initial_reservations_from_html() -> None:
    requests = load_har(FIXTURES / "agendaweb.asse.uy.har")
    html = next(
        request.response_text
        for request in requests
        if request.url == "https://agendaweb.asse.uy/agendaweb/servlet/com.agendaweb.misreservas"
    )
    reservations = extract_reservations_from_html(html or "")
    assert len(reservations) == 10
    assert reservations[0].consultation_code


def test_extract_reservations_from_initial_hidden_grid_html() -> None:
    html = """
    <html><body>
      <input type="hidden" name="GridmisreservasContainerDataV"
        value='[["/icon.png","27/05/2026","Dermatología","BARQUET, VIRGINIA","Número: 1 Hora aprox.: 12:30","/detail.png","/cancel.png","67723656"]]' />
    </body></html>
    """

    reservations = extract_reservations_from_html(html)

    assert len(reservations) == 1
    assert reservations[0].date == "27/05/2026"
    assert reservations[0].service == "Dermatología"
    assert reservations[0].consultation_code == "67723656"


def test_extract_appointment_flow() -> None:
    requests = load_har(FIXTURES / "agendaweb.asse.uy.har")
    steps = extract_appointment_flow(requests)
    events = [step.event for step in steps]
    assert "'BUSCAR'" in events
    assert "'SIGUIENTE'" in events


def test_extract_cookies_for_host() -> None:
    requests = load_har(FIXTURES / "agendaweb.asse.uy.har")
    cookies = extract_cookies_for_host(requests, "agendaweb.asse.uy")
    assert "JSESSIONID" in cookies
