from asse_cli.cli import _reservation_to_dict
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
