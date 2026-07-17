"""RM-136 passive read-only FTP/FTPS policy."""

import pytest

from app.tenders.collector.manual_probe_transport import (
    ManualProbeTransportError,
    select_ftp_sample,
    validate_ftp_passive_endpoint,
)
from app.tenders.collector.manual_provider_protocol import ManualProviderFtpsMode


def test_ftps_modes_are_closed_and_passive_sample_is_bounded() -> None:
    assert {mode.value for mode in ManualProviderFtpsMode} == {"implicit", "explicit"}
    assert select_ftp_sample(("a.txt", "latest.csv", "older.csv"), ".csv") == "latest.csv"
    with pytest.raises(ManualProbeTransportError):
        select_ftp_sample(tuple(f"{index}.csv" for index in range(101)), ".csv", max_entries=100)


def test_passive_bounce_to_private_or_unresolved_address_is_rejected() -> None:
    assert validate_ftp_passive_endpoint("93.184.216.34", 50000, ("93.184.216.34",)) == (
        "93.184.216.34",
        50000,
    )
    with pytest.raises(ManualProbeTransportError):
        validate_ftp_passive_endpoint("127.0.0.1", 50000, ("93.184.216.34",))
    with pytest.raises(ManualProbeTransportError):
        validate_ftp_passive_endpoint("93.184.216.99", 50000, ("93.184.216.34",))
