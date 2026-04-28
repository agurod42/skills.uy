from __future__ import annotations

from asse_cli.client import WebClient, WebSession, is_url_on_host


HCD_BASE_URL = "https://historiaclinicadigital.gub.uy/mihcd/servlet/"
HCD_LOGIN_URL = f"{HCD_BASE_URL}com.mihcd.loginweb"
HCD_HOST = "historiaclinicadigital.gub.uy"
HCD_ORIGIN = "https://historiaclinicadigital.gub.uy"
HCD_COOKIE_PATH = "/mihcd"


class HcdClient(WebClient):
    def __init__(self, session: WebSession | None = None, timeout: float = 30.0):
        super().__init__(
            session=session,
            base_url=HCD_BASE_URL,
            host=HCD_HOST,
            origin=HCD_ORIGIN,
            preferred_cookie_path=HCD_COOKIE_PATH,
            timeout=timeout,
        )

    def timeline(self):
        return self.get("com.mihcd.hc?Destacados=TODOS")

    def vaccines(self):
        return self.get("com.mihcd.historiavacunas")

    def accesses(self):
        return self.get("com.mihcd.contenedoraccesos")


def is_hcd_url(url: str) -> bool:
    return is_url_on_host(url, HCD_HOST)
