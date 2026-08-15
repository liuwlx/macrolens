from __future__ import annotations

import asyncio
import sys
from datetime import UTC, date, datetime
from decimal import Decimal
from types import ModuleType, SimpleNamespace

import pytest
from typer.testing import CliRunner

from macrolens_worker.providers.base import NormalizedObservation, ProviderFetchResult


class _ScalarResult:
    def __init__(self, providers: list[SimpleNamespace]) -> None:
        self._providers = providers

    def all(self) -> list[SimpleNamespace]:
        return self._providers


class _Session:
    def __init__(self, providers: list[SimpleNamespace]) -> None:
        self._providers = providers

    async def __aenter__(self) -> _Session:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def scalars(self, _statement: object) -> _ScalarResult:
        return _ScalarResult(self._providers)


class _PassingAdapter:
    def __init__(self, _client: object) -> None:
        pass

    async def fetch(
        self,
        provider: SimpleNamespace,
        mappings: list[tuple[SimpleNamespace, SimpleNamespace]],
        *,
        mode: str,
    ) -> list[ProviderFetchResult]:
        assert mode == "incremental"
        source, dataset = mappings[0]
        today = date.today()
        return [
            ProviderFetchResult(
                provider=provider,
                dataset=dataset,
                request_url="https://example.test",
                request_parameters={},
                content_type="application/json",
                raw_bytes=b"{}",
                observations=[
                    NormalizedObservation(
                        source.id,
                        today,
                        today,
                        Decimal("1"),
                        vintage_at=datetime.now(UTC),
                    )
                ],
            )
        ]


class _FailingAdapter:
    def __init__(self, _client: object) -> None:
        pass

    async def fetch(
        self,
        _provider: SimpleNamespace,
        _mappings: list[tuple[SimpleNamespace, SimpleNamespace]],
        *,
        mode: str,
    ) -> list[ProviderFetchResult]:
        raise RuntimeError(f"{mode} fetch failed")


def _stub_storage(monkeypatch: pytest.MonkeyPatch) -> None:
    storage = ModuleType("macrolens_api.services.storage")
    storage.ObjectStorage = object  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "macrolens_api.services.storage", storage)


def test_explicit_audit_fails_when_one_requested_provider_is_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_storage(monkeypatch)
    from macrolens_worker import live_audit

    passing = SimpleNamespace(code="PASSING", id=1)
    skipped = SimpleNamespace(code="SKIPPED", id=2)
    source = SimpleNamespace(
        id=101,
        provider_series_id="PASSING.SERIES",
        source_frequency="daily",
        source_locator={"skip_freshness_check": True},
    )
    dataset = SimpleNamespace(id=11, code="passing")

    async def mappings(
        _session: object, provider: SimpleNamespace
    ) -> list[tuple[SimpleNamespace, SimpleNamespace]]:
        return [(source, dataset)] if provider.code == "PASSING" else []

    monkeypatch.setattr(live_audit, "SessionLocal", lambda: _Session([passing, skipped]))
    monkeypatch.setattr(live_audit, "_provider_mappings", mappings)
    monkeypatch.setattr(
        live_audit,
        "ADAPTERS",
        {"PASSING": _PassingAdapter, "SKIPPED": _PassingAdapter},
    )

    report = asyncio.run(
        live_audit.audit_live_data(provider_codes=["PASSING", "SKIPPED"])
    )

    assert report["passed_provider_count"] == 1
    assert report["skipped_provider_count"] == 1
    assert report["all_executed_passed"] is False


def test_explicit_audit_passes_when_all_requested_providers_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_storage(monkeypatch)
    from macrolens_worker import live_audit

    providers = [
        SimpleNamespace(code="FIRST", id=1),
        SimpleNamespace(code="SECOND", id=2),
    ]
    source = SimpleNamespace(
        id=102,
        provider_series_id="PASSING.SERIES",
        source_frequency="daily",
        source_locator={"skip_freshness_check": True},
    )
    dataset = SimpleNamespace(id=12, code="passing")

    async def mappings(
        _session: object, _provider: SimpleNamespace
    ) -> list[tuple[SimpleNamespace, SimpleNamespace]]:
        return [(source, dataset)]

    monkeypatch.setattr(live_audit, "SessionLocal", lambda: _Session(providers))
    monkeypatch.setattr(live_audit, "_provider_mappings", mappings)
    monkeypatch.setattr(
        live_audit,
        "ADAPTERS",
        {"FIRST": _PassingAdapter, "SECOND": _PassingAdapter},
    )

    report = asyncio.run(
        live_audit.audit_live_data(provider_codes=["FIRST", "SECOND"])
    )

    assert report["passed_provider_count"] == 2
    assert report["all_executed_passed"] is True


def test_explicit_audit_fails_when_requested_provider_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_storage(monkeypatch)
    from macrolens_worker import live_audit

    monkeypatch.setattr(live_audit, "SessionLocal", lambda: _Session([]))

    report = asyncio.run(
        live_audit.audit_live_data(provider_codes=["MISSING"])
    )

    assert report["failed_provider_count"] == 1
    assert report["providers"][0]["issues"][0]["code"] == "provider_missing"
    assert report["all_executed_passed"] is False


def test_explicit_audit_fails_when_requested_provider_fetch_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_storage(monkeypatch)
    from macrolens_worker import live_audit

    provider = SimpleNamespace(code="FAILING", id=3)
    source = SimpleNamespace(id=103)
    dataset = SimpleNamespace(id=13)

    async def mappings(
        _session: object, _provider: SimpleNamespace
    ) -> list[tuple[SimpleNamespace, SimpleNamespace]]:
        return [(source, dataset)]

    monkeypatch.setattr(live_audit, "SessionLocal", lambda: _Session([provider]))
    monkeypatch.setattr(live_audit, "_provider_mappings", mappings)
    monkeypatch.setattr(live_audit, "ADAPTERS", {"FAILING": _FailingAdapter})

    report = asyncio.run(
        live_audit.audit_live_data(provider_codes=["FAILING"])
    )

    assert report["failed_provider_count"] == 1
    assert report["providers"][0]["issues"][0]["code"] == "provider_fetch_failed"
    assert report["all_executed_passed"] is False


def test_unfiltered_audit_keeps_ignoring_intentionally_skipped_providers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_storage(monkeypatch)
    from macrolens_worker import live_audit

    passing = SimpleNamespace(code="PASSING", id=1)
    skipped = SimpleNamespace(code="SKIPPED", id=2)
    source = SimpleNamespace(
        id=104,
        provider_series_id="PASSING.SERIES",
        source_frequency="daily",
        source_locator={"skip_freshness_check": True},
    )
    dataset = SimpleNamespace(id=14, code="passing")

    async def mappings(
        _session: object, provider: SimpleNamespace
    ) -> list[tuple[SimpleNamespace, SimpleNamespace]]:
        return [(source, dataset)] if provider.code == "PASSING" else []

    monkeypatch.setattr(live_audit, "SessionLocal", lambda: _Session([passing, skipped]))
    monkeypatch.setattr(live_audit, "_provider_mappings", mappings)
    monkeypatch.setattr(
        live_audit,
        "ADAPTERS",
        {"PASSING": _PassingAdapter, "SKIPPED": _PassingAdapter},
    )

    report = asyncio.run(live_audit.audit_live_data())

    assert report["passed_provider_count"] == 1
    assert report["skipped_provider_count"] == 1
    assert report["all_executed_passed"] is True


def test_cli_explicit_audit_exits_nonzero_for_passed_and_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_storage(monkeypatch)
    from macrolens_worker import live_audit
    from macrolens_worker.main import app

    passing = SimpleNamespace(code="PASSING", id=1)
    skipped = SimpleNamespace(code="SKIPPED", id=2)
    source = SimpleNamespace(
        id=105,
        provider_series_id="PASSING.SERIES",
        source_frequency="daily",
        source_locator={"skip_freshness_check": True},
    )
    dataset = SimpleNamespace(id=15, code="passing")

    async def mappings(
        _session: object, provider: SimpleNamespace
    ) -> list[tuple[SimpleNamespace, SimpleNamespace]]:
        return [(source, dataset)] if provider.code == "PASSING" else []

    monkeypatch.setattr(live_audit, "SessionLocal", lambda: _Session([passing, skipped]))
    monkeypatch.setattr(live_audit, "_provider_mappings", mappings)
    monkeypatch.setattr(
        live_audit,
        "ADAPTERS",
        {"PASSING": _PassingAdapter, "SKIPPED": _PassingAdapter},
    )

    result = CliRunner().invoke(
        app,
        ["audit-live", "--provider", "PASSING", "--provider", "SKIPPED"],
    )

    assert result.exit_code == 5


def test_cli_explicit_audit_exits_zero_when_all_requested_providers_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_storage(monkeypatch)
    from macrolens_worker import live_audit
    from macrolens_worker.main import app

    providers = [
        SimpleNamespace(code="FIRST", id=1),
        SimpleNamespace(code="SECOND", id=2),
    ]
    source = SimpleNamespace(
        id=106,
        provider_series_id="PASSING.SERIES",
        source_frequency="daily",
        source_locator={"skip_freshness_check": True},
    )
    dataset = SimpleNamespace(id=16, code="passing")

    async def mappings(
        _session: object, _provider: SimpleNamespace
    ) -> list[tuple[SimpleNamespace, SimpleNamespace]]:
        return [(source, dataset)]

    monkeypatch.setattr(live_audit, "SessionLocal", lambda: _Session(providers))
    monkeypatch.setattr(live_audit, "_provider_mappings", mappings)
    monkeypatch.setattr(
        live_audit,
        "ADAPTERS",
        {"FIRST": _PassingAdapter, "SECOND": _PassingAdapter},
    )

    result = CliRunner().invoke(
        app,
        ["audit-live", "--provider", "FIRST", "--provider", "SECOND"],
    )

    assert result.exit_code == 0


def test_cli_explicit_audit_exits_nonzero_when_requested_provider_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_storage(monkeypatch)
    from macrolens_worker import live_audit
    from macrolens_worker.main import app

    monkeypatch.setattr(live_audit, "SessionLocal", lambda: _Session([]))

    result = CliRunner().invoke(app, ["audit-live", "--provider", "MISSING"])

    assert result.exit_code == 5


def test_cli_explicit_audit_exits_nonzero_when_requested_provider_fetch_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_storage(monkeypatch)
    from macrolens_worker import live_audit
    from macrolens_worker.main import app

    provider = SimpleNamespace(code="FAILING", id=3)
    source = SimpleNamespace(id=107)
    dataset = SimpleNamespace(id=17)

    async def mappings(
        _session: object, _provider: SimpleNamespace
    ) -> list[tuple[SimpleNamespace, SimpleNamespace]]:
        return [(source, dataset)]

    monkeypatch.setattr(live_audit, "SessionLocal", lambda: _Session([provider]))
    monkeypatch.setattr(live_audit, "_provider_mappings", mappings)
    monkeypatch.setattr(live_audit, "ADAPTERS", {"FAILING": _FailingAdapter})

    result = CliRunner().invoke(app, ["audit-live", "--provider", "FAILING"])

    assert result.exit_code == 5
