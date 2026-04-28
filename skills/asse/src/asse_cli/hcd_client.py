from __future__ import annotations

from urllib.parse import urljoin, urlparse

from asse_cli.client import UnexpectedResponseError, WebClient, WebSession, is_url_on_host
from asse_cli.genexus import GeneXusEvent
from asse_cli.hcd_extract import (
    HcdVisitDocument,
    HcdVisitTarget,
    extract_hcd_ajax_security_token,
    extract_hcd_cda_iframe_url,
    extract_hcd_security_headers,
    extract_hcd_visit_document,
    extract_hcd_visit_targets,
    extract_hcd_visit_wrapper_meta,
    extract_hcd_visualizer_url,
)


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

    def visit_targets(self) -> list[HcdVisitTarget]:
        response = self.timeline()
        self._ensure_authenticated(response.url)
        return extract_hcd_visit_targets(response.text)

    def visit_document(self, index: int) -> HcdVisitDocument:
        timeline_response = self.timeline()
        self._ensure_authenticated(timeline_response.url)
        targets = extract_hcd_visit_targets(timeline_response.text)
        if index < 1 or index > len(targets):
            raise ValueError(f"No existe visita #{index}. Disponibles: {len(targets)}")
        target = targets[index - 1]
        ajax_token = extract_hcd_ajax_security_token(timeline_response.text)
        if not ajax_token:
            raise RuntimeError("No pude extraer el token AJAX de HCD para abrir la visita")

        event = GeneXusEvent(
            obj_class="hc",
            pkg_name="com.mihcd",
            events=("'OPENCDA'",),
            parms=list(target.parms),
            hsh=list(target.hsh),
            grid=45,
            row=f"{target.row:04d}",
            p_row="",
            grids={"Freestylegrid": {"id": 45, "lastRow": 0, "pRow": ""}},
        )
        security_headers = extract_hcd_security_headers(timeline_response.text)
        if "AJAX_SECURITY_TOKEN" not in security_headers or "X-GXAUTH-TOKEN" not in security_headers:
            raise RuntimeError("No pude extraer los headers de seguridad de HCD para abrir la visita")
        try:
            response = self.post_event(
                f"com.mihcd.hc?{ajax_token},Destacados=TODOS",
                event,
                headers=security_headers,
            )
        except UnexpectedResponseError as exc:
            raise RuntimeError(
                "HCD no devolvio la respuesta GeneXus esperada al abrir la visita. "
                f"{exc} Refresque la sesion con: asse hcd session login-browser"
            ) from exc
        visualizer_url = extract_hcd_visualizer_url(response)
        if not visualizer_url:
            raise RuntimeError("HCD no devolvio URL de visualizacion CDA")

        visualizer_response = self.get(visualizer_url)
        meta = extract_hcd_visit_wrapper_meta(visualizer_response.text)
        iframe_url = extract_hcd_cda_iframe_url(visualizer_response.text)
        if not iframe_url:
            iframe_url = urljoin(HCD_BASE_URL, "com.mihcd.aopencdasesion")
        cda_response = self.get(iframe_url)
        document = extract_hcd_visit_document(cda_response.text, meta=meta, row=index)
        if not document:
            raise RuntimeError("No pude extraer contenido CDA de la visita")
        return document

    @staticmethod
    def _ensure_authenticated(url: object) -> None:
        path = urlparse(str(url)).path.lower()
        if path.endswith("/com.mihcd.loginweb"):
            raise RuntimeError(
                "Sesion HCD expirada. Refresque con: asse hcd session login-browser"
            )


def is_hcd_url(url: str) -> bool:
    return is_url_on_host(url, HCD_HOST)
