from http.cookiejar import Cookie, CookieJar

import httpx
import pytest

from asse_cli.agenda_client import AGENDA_HOST, is_agenda_url
from asse_cli.client import UnexpectedResponseError, WebClient, WebSession, is_url_on_host, session_cookies_from_jar
from asse_cli.genexus import GeneXusEvent
from asse_cli.hcd_client import HCD_HOST, is_hcd_url


def test_is_agenda_url_accepts_servlet_path() -> None:
    assert is_agenda_url("https://agendaweb.asse.uy/agendaweb/servlet/com.agendaweb.home")


def test_is_agenda_url_rejects_sso_redirect() -> None:
    assert not is_agenda_url("https://mi.iduruguay.gub.uy/login?process_state=abc")


def test_is_agenda_url_rejects_subdomain() -> None:
    assert not is_agenda_url("https://other.agendaweb.asse.uy/x")


def test_is_hcd_url_accepts_hcd_domain() -> None:
    assert is_hcd_url("https://historiaclinicadigital.gub.uy/mihcd/servlet/com.mihcd.hc")


def test_is_url_on_host_rejects_parent_domain() -> None:
    assert not is_url_on_host("https://gub.uy/mihcd/servlet/com.mihcd.hc", HCD_HOST)


def test_session_cookies_prefers_agendaweb_duplicate() -> None:
    jar = CookieJar()
    jar.set_cookie(_cookie("JSESSIONID", "host-only", "", "/"))
    jar.set_cookie(_cookie("JSESSIONID", "agendaweb", "agendaweb.asse.uy", "/agendaweb"))
    jar.set_cookie(_cookie("ROUTEID", "external", "idp.asse.uy", "/"))
    jar.set_cookie(_cookie("GX_SESSION_ID", "gx", "", "/"))

    cookies = session_cookies_from_jar(jar, host=AGENDA_HOST, preferred_path="/agendaweb")

    assert cookies == {
        "JSESSIONID": "agendaweb",
        "GX_SESSION_ID": "gx",
    }


def test_post_event_reports_non_json_without_response_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["accept"] == "*/*"
        assert request.headers["gxajaxrequest"] == "1"
        return httpx.Response(
            200,
            request=request,
            headers={"content-type": "text/html; charset=utf-8"},
            text="<html><body>private response body</body></html>",
        )

    client = WebClient(
        session=WebSession(base_url="https://historiaclinicadigital.gub.uy/mihcd/servlet/"),
        base_url="https://historiaclinicadigital.gub.uy/mihcd/servlet/",
        host=HCD_HOST,
        origin="https://historiaclinicadigital.gub.uy",
        preferred_cookie_path="/mihcd",
    )
    client.http = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)

    with pytest.raises(UnexpectedResponseError) as exc_info:
        client.post_event("com.mihcd.hc?token=secret", GeneXusEvent(obj_class="hc", pkg_name="com.mihcd", events=("'OPENCDA'",)))

    message = str(exc_info.value)
    assert "esperaba JSON GeneXus" in message
    assert "text/html" in message
    assert "/mihcd/servlet/com.mihcd.hc" in message
    assert "secret" not in message
    assert "private response body" not in message


def test_genexus_event_payload_includes_grid_row_metadata() -> None:
    event = GeneXusEvent(
        obj_class="hc",
        pkg_name="com.mihcd",
        events=("'OPENCDA'",),
        grid=45,
        row="0001",
        p_row="",
    )

    payload = event.to_payload()

    assert payload["grid"] == 45
    assert payload["row"] == "0001"
    assert payload["pRow"] == ""


def _cookie(name: str, value: str, domain: str, path: str) -> Cookie:
    return Cookie(
        version=0,
        name=name,
        value=value,
        port=None,
        port_specified=False,
        domain=domain,
        domain_specified=bool(domain),
        domain_initial_dot=domain.startswith("."),
        path=path,
        path_specified=True,
        secure=False,
        expires=None,
        discard=True,
        comment=None,
        comment_url=None,
        rest={},
        rfc2109=False,
    )
