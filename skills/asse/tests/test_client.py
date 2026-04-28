from http.cookiejar import Cookie, CookieJar

from asse_cli.agenda_client import AGENDA_HOST, is_agenda_url
from asse_cli.client import is_url_on_host, session_cookies_from_jar
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
