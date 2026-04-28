import subprocess

import pytest
import typer
from asse_cli import cli as cli_module
from asse_cli.cli import _reservation_to_dict, _resolve_hcd_visit_index
from asse_cli.extract import Reservation


def test_reservation_to_dict_redacts_code_by_default() -> None:
    reservation = Reservation(
        row=1,
        date="27/05/2026",
        service="Dermatología",
        professional="BARQUET, VIRGINIA",
        number_and_time="Número: 1 Hora aprox.: 12:30",
        consultation_code="1234567890123456",
    )

    data = _reservation_to_dict(reservation)

    assert data["consultation_code"] == "123456...123456"


def test_reservation_to_dict_can_show_full_code() -> None:
    reservation = Reservation(
        row=1,
        date="27/05/2026",
        service="Dermatología",
        professional="BARQUET, VIRGINIA",
        number_and_time="Número: 1 Hora aprox.: 12:30",
        consultation_code="1234567890123456",
    )

    data = _reservation_to_dict(reservation, show_codes=True)

    assert data["consultation_code"] == "1234567890123456"


def test_install_python_requirement_uses_uv_when_pip_is_missing(monkeypatch) -> None:
    calls: list[list[str]] = []

    monkeypatch.setattr(cli_module, "_find_executable", lambda name: "/usr/local/bin/uv")

    def fake_run(command, check, capture_output, text):
        calls.append(command)
        if command[0:3] == [cli_module.sys.executable, "-m", "pip"]:
            return subprocess.CompletedProcess(command, 1, stderr="No module named pip")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(cli_module.subprocess, "run", fake_run)

    cli_module._install_python_requirement("playwright>=1.45.0")

    assert calls == [
        [cli_module.sys.executable, "-m", "pip", "install", "playwright>=1.45.0"],
        [
            "/usr/local/bin/uv",
            "pip",
            "install",
            "--python",
            cli_module.sys.executable,
            "playwright>=1.45.0",
        ],
    ]


def test_install_python_requirement_uses_ensurepip_when_uv_is_unavailable(monkeypatch) -> None:
    calls: list[list[str]] = []

    monkeypatch.setattr(cli_module, "_find_executable", lambda name: "")

    def fake_run(command, check, capture_output, text):
        calls.append(command)
        if len(calls) == 1:
            return subprocess.CompletedProcess(command, 1, stderr="No module named pip")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(cli_module.subprocess, "run", fake_run)

    cli_module._install_python_requirement("playwright>=1.45.0")

    assert calls == [
        [cli_module.sys.executable, "-m", "pip", "install", "playwright>=1.45.0"],
        [cli_module.sys.executable, "-m", "ensurepip", "--upgrade"],
        [cli_module.sys.executable, "-m", "pip", "install", "playwright>=1.45.0"],
    ]


@pytest.mark.parametrize(
    ("index_arg", "index_option", "extra_args", "expected"),
    [
        (None, None, [], 1),
        ("1", None, [], 1),
        (None, 2, [], 2),
        ("show", None, ["3"], 3),
        ("show", None, [], 1),
    ],
)
def test_resolve_hcd_visit_index(
    index_arg: str | None,
    index_option: int | None,
    extra_args: list[str],
    expected: int,
) -> None:
    assert _resolve_hcd_visit_index(index_arg, index_option, extra_args) == expected


@pytest.mark.parametrize(
    ("index_arg", "index_option", "extra_args"),
    [
        ("abc", None, []),
        ("0", None, []),
        ("1", 2, []),
        ("show", None, ["1", "2"]),
    ],
)
def test_resolve_hcd_visit_index_rejects_invalid_input(
    index_arg: str | None,
    index_option: int | None,
    extra_args: list[str],
) -> None:
    with pytest.raises(typer.BadParameter):
        _resolve_hcd_visit_index(index_arg, index_option, extra_args)
