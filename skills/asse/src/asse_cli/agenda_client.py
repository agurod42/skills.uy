from __future__ import annotations

from bs4 import BeautifulSoup

from asse_cli.client import WebClient, WebSession, is_url_on_host


AGENDA_BASE_URL = "https://agendaweb.asse.uy/agendaweb/servlet/"
AGENDA_PUBLIC_HOME_URL = "https://www.asse.com.uy/home"
AGENDA_HOST = "agendaweb.asse.uy"
AGENDA_ORIGIN = "https://agendaweb.asse.uy"
AGENDA_COOKIE_PATH = "/agendaweb"


class AgendaClient(WebClient):
    def __init__(self, session: WebSession | None = None, timeout: float = 30.0):
        super().__init__(
            session=session,
            base_url=AGENDA_BASE_URL,
            host=AGENDA_HOST,
            origin=AGENDA_ORIGIN,
            preferred_cookie_path=AGENDA_COOKIE_PATH,
            timeout=timeout,
        )

    def discover_login_url(self) -> str:
        response = self.http.get(AGENDA_PUBLIC_HOME_URL)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for anchor in soup.find_all("a", href=True):
            href = str(anchor["href"])
            if "agendaweb" in href and "aredirectlogin" in href:
                return href
        raise RuntimeError("No encontre el link de Agenda Web en la home publica de ASSE")


def is_agenda_url(url: str) -> bool:
    return is_url_on_host(url, AGENDA_HOST)
