import json

from asse_cli.hcd_extract import (
    extract_hcd_accesses,
    extract_hcd_timeline,
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
