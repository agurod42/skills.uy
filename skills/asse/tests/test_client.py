from http.cookiejar import Cookie, CookieJar

from asse_cli.client import _session_cookies_from_jar


def test_session_cookies_prefers_agendaweb_duplicate() -> None:
    jar = CookieJar()
    jar.set_cookie(_cookie("JSESSIONID", "host-only", "", "/"))
    jar.set_cookie(_cookie("JSESSIONID", "agendaweb", "agendaweb.asse.uy", "/agendaweb"))
    jar.set_cookie(_cookie("ROUTEID", "external", "idp.asse.uy", "/"))
    jar.set_cookie(_cookie("GX_SESSION_ID", "gx", "", "/"))

    cookies = _session_cookies_from_jar(jar)

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
