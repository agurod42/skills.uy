import json
import base64

from asse_cli.hcd_extract import (
    extract_hcd_ajax_security_token,
    extract_hcd_accesses,
    extract_hcd_security_headers,
    extract_hcd_timeline,
    extract_hcd_visit_document,
    extract_hcd_visit_targets,
    extract_hcd_visualizer_url,
    extract_hcd_vaccine_report,
)


def test_extract_hcd_timeline_from_gx_state() -> None:
    html = """
    <input type="hidden" name="GXState"
      value='{
        "HCHISTORYLINEIMAGE_0001_Fecha": "21/04/2026",
        "HCHISTORYLINEIMAGE_0001_Nombreprestador": "ASSE",
        "HCHISTORYLINEIMAGE_0001_Datainfoextraprestador": "Centro",
        "HCHISTORYLINEDATA_0001_Especialidad": "SERVICIO DE CARDIOLOGIA",
        "HCHISTORYLINEDATA_0001_Profesional": "DRA. TEST",
        "HCHISTORYLINEDATA_0001_Textoprescripcion": "Retirar medicacion",
        "HCHISTORYLINEDATA_0001_Urlprescripcion": "https://example.test/doc?token=abc"
      }' />
    """

    encounters = extract_hcd_timeline(html)

    assert len(encounters) == 1
    assert encounters[0].date == "21/04/2026"
    assert encounters[0].provider == "ASSE"
    assert encounters[0].specialty == "SERVICIO DE CARDIOLOGIA"
    assert encounters[0].professional == "DRA. TEST"
    assert encounters[0].prescription_url.endswith("token=abc")


def test_extract_hcd_timeline_from_saved_json_string() -> None:
    response = {
        "gxProps": [
            {
                "HCHISTORYLINEIMAGE_0002_Fecha": "20/04/2026",
                "HCHISTORYLINEDATA_0002_Especialidad": "SERVICIO DE ENFERMERIA",
                "HCHISTORYLINEDATA_0002_Profesional": "LIC. TEST",
            }
        ]
    }
    html = f"<script>gx.ajax.saveJsonResponse({json.dumps(json.dumps(response))});</script>"

    encounters = extract_hcd_timeline(html)

    assert len(encounters) == 1
    assert encounters[0].row == 2
    assert encounters[0].specialty == "SERVICIO DE ENFERMERIA"


def test_extract_hcd_vaccine_report() -> None:
    html = """
    <div id="VISUALIZARCDAHTML">Este documento no equivale al certificado.</div>
    <iframe src="com.mihcd.areportevacunacion?opaque-token"></iframe>
    """

    report = extract_hcd_vaccine_report(html)

    assert report is not None
    assert report.notice == "Este documento no equivale al certificado."
    assert report.report_url.endswith("com.mihcd.areportevacunacion?opaque-token")


def test_extract_hcd_accesses() -> None:
    response = {
        "gxProps": [
            {
                "vDP_SDT_GRIDDPHISTORIALACCESOS": [
                    {
                        "HistorialAccesosType": "HC",
                        "HistorialAccesosFechaHora": "2025-11-12T13:04:10",
                        "HistorialAccesosPrestador": "ASSE",
                        "HistorialAccesosOid": "2.16.858.test",
                        "HistorialAccesosObservacion": "- Atención a la Salud",
                        "HistorialAccesosDetalle": "Acceso habilitado por el usuario",
                        "HistorialAccesosEsEmergencia": False,
                    }
                ]
            }
        ]
    }

    accesses = extract_hcd_accesses(json.dumps(response))

    assert len(accesses) == 1
    assert accesses[0].provider == "ASSE"
    assert accesses[0].detail == "Acceso habilitado por el usuario"


def test_extract_hcd_visit_document() -> None:
    html = """
    <html>
      <head><title>SERVICIO DE CARDIOLOGIA</title></head>
      <body>
        <table>
          <tr><td>Prestador</td><td>ASSE</td></tr>
          <tr><td>Profesional</td><td>DRA. TEST</td></tr>
          <tr><td>Fecha del evento</td><td>Abril 9, 2026</td></tr>
        </table>
        <h2>Consulta actual</h2>
        <p>Texto clinico de prueba.</p>
      </body>
    </html>
    """

    document = extract_hcd_visit_document(
        html,
        meta={"date": "09 de abril 2026", "category": "Policlinica"},
    )

    assert document is not None
    assert document.title == "SERVICIO DE CARDIOLOGIA"
    assert document.date == "09 de abril 2026"
    assert document.category == "Policlinica"
    assert document.provider == "ASSE"
    assert document.professional == "DRA. TEST"
    assert document.event_date == "Abril 9, 2026"
    assert "Texto clinico de prueba." in document.text


def test_extract_hcd_visit_targets() -> None:
    html = f"""
    <input type="hidden" name="GXState"
      value='{{
        "GX_AJAX_IV": "12345678901234567890123456789012",
        "AJAX_SECURITY_TOKEN": "abcdefabcdefabcdefabcdefabcdefabcdef",
        "HCHISTORYLINEIMAGE_0001_Fecha": "21/04/2026",
        "HCHISTORYLINEDATA_0001_Especialidad": "SERVICIO",
        "HCHISTORYLINEDATA_0001_Profesional": "DRA. TEST",
        "GX_AUTH_HC": "auth-token",
        "gxhash_vDOCREPOID_0001": "{_hash("repo")}",
        "gxhash_vDOCUNIQUEID_0001": "{_hash("unique")}",
        "gxhash_vDOCFECHA_0001": "{_hash("2026/04/21 00:00:00")}",
        "gxhash_vDOCCATEGORIA_0001": "{_hash("Policlinica")}"
      }}' />
    """

    targets = extract_hcd_visit_targets(html)

    assert extract_hcd_ajax_security_token(html) == "12345678901234567890123456789012abcdefabcdefabcdefabcdefabcdefab"
    assert extract_hcd_security_headers(html) == {
        "AJAX_SECURITY_TOKEN": "abcdefabcdefabcdefabcdefabcdefabcdef",
        "X-GXAUTH-TOKEN": "auth-token",
    }
    assert len(targets) == 1
    assert targets[0].parms == ("repo", "unique", "2026/04/21 00:00:00", "Policlinica")
    assert len(targets[0].hsh) == 4


def test_extract_hcd_ajax_security_token_prefers_ajax_key() -> None:
    html = """
    <input type="hidden" name="GXState"
      value='{
        "GX_AJAX_IV": "11111111111111111111111111111111",
        "GX_AJAX_KEY": "22222222222222222222222222222222",
        "AJAX_SECURITY_TOKEN": "abcdefabcdefabcdefabcdefabcdefabcdef"
      }' />
    """

    assert extract_hcd_ajax_security_token(html) == "22222222222222222222222222222222abcdefabcdefabcdefabcdefabcdefab"


def test_extract_hcd_visualizer_url_from_ucmethod() -> None:
    response = {
        "gxCommands": [
            {"exomethod": {"Method": "OpenRedirectModal", "Parms": []}},
            {
                "ucmethod": {
                    "Control": "UCBROWSERINTERFACE1Container",
                    "Method": "goUrl",
                    "Parms": ["com.mihcd.visualizarcda?opaque-token"],
                }
            },
        ]
    }

    assert extract_hcd_visualizer_url(response) == "com.mihcd.visualizarcda?opaque-token"


def _hash(value: str) -> str:
    payload = base64.urlsafe_b64encode(json.dumps({"gx-val": value}).encode()).decode().rstrip("=")
    return f"header.{payload}.signature"
