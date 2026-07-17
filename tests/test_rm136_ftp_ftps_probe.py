"""RM-136 passive read-only FTP/FTPS policy."""

import asyncio

import pytest

from app.tenders.collector.cancellation import CollectorCancellationToken
from app.tenders.collector.manual_probe_transport import (
    ManualFtpProbeResponse,
    ManualProviderProbeTransport,
    ManualProbeTargetPolicy,
    ManualProbeTransportError,
    select_ftp_sample,
    validate_ftp_passive_endpoint,
)
from app.tenders.collector.manual_provider_protocol import ManualProviderFtpsMode
from app.tenders.collector.manual_provider_protocol import ManualProviderProtocolFamily


class _Resolver:
    async def resolve(self, hostname: str) -> tuple[str, ...]:
        return ("93.184.216.34",)


class _Ftps:
    async def read_sample(
        self, target, pinned_address, suffix, ftps_mode, cancellation_token, credentials
    ):
        assert pinned_address == "93.184.216.34"
        assert ftps_mode is ManualProviderFtpsMode.IMPLICIT
        return ManualFtpProbeResponse(
            names=("latest.csv",),
            passive_address="93.184.216.34",
            passive_port=50000,
            sample_name="latest.csv",
            sample=b"title\nTender",
        )


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


def test_ftps_mode_selects_only_the_typed_control_port() -> None:
    policy = ManualProbeTargetPolicy()
    implicit = policy.validate_endpoint(
        "ftps://source.example.test/incoming",
        ManualProviderProtocolFamily.FTPS,
        ftps_mode=ManualProviderFtpsMode.IMPLICIT,
    )
    explicit = policy.validate_endpoint(
        "ftps://source.example.test:21/incoming",
        ManualProviderProtocolFamily.FTPS,
        ftps_mode=ManualProviderFtpsMode.EXPLICIT,
    )
    assert implicit.port == 990
    assert explicit.port == 21


def test_ftps_orchestrator_allows_only_validated_passive_read_sample() -> None:
    transport = ManualProviderProbeTransport(resolver=_Resolver(), ftp=_Ftps())
    sample = asyncio.run(
        transport.probe_ftp(
            "ftps://source.example.test/incoming",
            ManualProviderProtocolFamily.FTPS,
            ".csv",
            CollectorCancellationToken(),
            ftps_mode=ManualProviderFtpsMode.IMPLICIT,
        )
    )
    assert sample == b"title\nTender"


def test_plaintext_ftp_credentials_are_blocked() -> None:
    from app.tenders.collector.manual_probe_transport import ManualProbeCredentials

    transport = ManualProviderProbeTransport(resolver=_Resolver(), ftp=_Ftps())
    with pytest.raises(ManualProbeTransportError):
        asyncio.run(
            transport.probe_ftp(
                "ftp://source.example.test/incoming",
                ManualProviderProtocolFamily.FTP,
                ".csv",
                CollectorCancellationToken(),
                credentials=ManualProbeCredentials(username="user", password="password"),
            )
        )
