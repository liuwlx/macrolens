from __future__ import annotations

import asyncio
import json
from datetime import date
from types import SimpleNamespace

import pytest

from macrolens_worker.providers import tradingview
from macrolens_worker.providers.base import ProviderDataError
from macrolens_worker.providers.tradingview import (
    ChartHistoryDecoder,
    FrameDecoder,
    TradingViewAdapter,
    encode_frame,
    parse_chart_period,
    parse_observation_period,
)


def _frame(message: dict[str, object]) -> str:
    return encode_frame(message)


def test_encode_frame_uses_utf8_payload_length() -> None:
    encoded = encode_frame({"m": "set_locale", "p": ["zh-Hans", "中国"]})
    payload = encoded.split("~m~", 2)[2]
    declared = int(encoded.split("~m~", 2)[1])
    assert declared == len(payload.encode("utf-8"))
    assert json.loads(payload)["m"] == "set_locale"


def test_frame_decoder_handles_multiple_frames_and_split_utf8_frame() -> None:
    decoder = FrameDecoder()
    first = _frame({"m": "heartbeat", "p": []}).encode("utf-8")
    second = _frame({"m": "qsd", "p": ["qs_1", {"n": "ECONOMICS:USUR"}]}).encode(
        "utf-8"
    )
    combined = first + second
    midpoint = len(first) + 5

    assert decoder.feed(combined[:midpoint]) == [{"m": "heartbeat", "p": []}]
    assert decoder.feed(combined[midpoint:]) == [
        {"m": "qsd", "p": ["qs_1", {"n": "ECONOMICS:USUR"}]}
    ]


@pytest.mark.parametrize(
    ("period", "frequency", "expected"),
    [
        ("29 Jul 2026", "D", date(2026, 7, 29)),
        ("8 Aug 2026", "W", date(2026, 8, 8)),
        ("Jul 2026", "M", date(2026, 7, 1)),
        ("Q2 2026", "3M", date(2026, 4, 1)),
        ("2025", "12M", date(2025, 1, 1)),
    ],
)
def test_parse_observation_period(period: str, frequency: str, expected: date) -> None:
    assert parse_observation_period(period, frequency) == expected


class _FakeSocket:
    def __init__(self, messages: list[str]) -> None:
        self.messages = iter(messages)
        self.sent: list[str] = []

    async def send(self, message: str) -> None:
        self.sent.append(message)

    async def recv(self) -> str:
        return next(self.messages)


class _FakeConnection:
    def __init__(self, socket: _FakeSocket) -> None:
        self.socket = socket

    async def __aenter__(self) -> _FakeSocket:
        return self.socket

    async def __aexit__(self, *_args: object) -> None:
        return None


def test_fetch_parses_qsd_and_returns_normalized_observation(monkeypatch) -> None:
    async def run() -> None:
        socket = _FakeSocket(
        [
            _frame(
                {
                    "m": "qsd",
                    "p": [
                        "qs_test",
                        {
                            "n": "ECONOMICS:USUR",
                            "s": "ok",
                            "v": {
                                "lp": 4.1,
                                "prev_close_price": 4.2,
                                "reference-last-period": "Jul 2026",
                                "data_frequency": "M",
                                "value_unit_id": "PCT",
                                "country_code": "US",
                                "short_description": "United States Unemployment Rate",
                                "source2": {"name": "BLS"},
                            },
                        },
                    ],
                }
            ),
            _frame(
                {
                    "m": "qsd",
                    "p": [
                        "qs_test",
                        {
                            "n": "ECONOMICS:USUR",
                            "s": "ok",
                            "v": {"reference-last-period-start": 20260701},
                        },
                    ],
                }
            ),
            _frame({"m": "quote_completed", "p": ["qs_test", "ECONOMICS:USUR"]}),
        ]
    )

        def fake_connect(*_args: object, **_kwargs: object) -> _FakeConnection:
            return _FakeConnection(socket)

        monkeypatch.setattr(tradingview, "connect", fake_connect)
        source = SimpleNamespace(
            id=7,
            provider_series_id="ECONOMICS:USUR",
            source_frequency="monthly",
            source_unit="percent",
            source_locator={},
        )
        dataset = SimpleNamespace(id=3, code="TRADINGVIEW_ECONOMICS")

        results = await TradingViewAdapter(client=None).fetch(  # type: ignore[arg-type]
            SimpleNamespace(code="TRADINGVIEW_WEB"),
            [(source, dataset)],
            mode="latest",
        )

        assert len(results) == 1
        assert len(results[0].observations) == 1
        observation = results[0].observations[0]
        assert observation.source_series_id == 7
        assert observation.period_start == date(2026, 7, 1)
        assert str(observation.value) == "4.1"
        assert results[0].raw_bytes == b""
        assert results[0].persist_raw is False
        assert any("quote_add_symbols" in message for message in socket.sent)

    asyncio.run(run())


def test_fetch_records_no_such_symbol_for_registry_classification(monkeypatch) -> None:
    async def run() -> None:
        symbol = "ECONOMICS:USBAVCPIYY"
        socket = _FakeSocket(
            [
                _frame(
                    {
                        "m": "qsd",
                        "p": [
                            "qs_test",
                            {
                                "n": symbol,
                                "s": "error",
                                "errmsg": "no_such_symbol",
                                "v": {},
                            },
                        ],
                    }
                ),
                _frame({"m": "quote_completed", "p": ["qs_test", symbol]}),
            ]
        )

        def fake_connect(*_args: object, **_kwargs: object) -> _FakeConnection:
            return _FakeConnection(socket)

        monkeypatch.setattr(tradingview, "connect", fake_connect)
        adapter = TradingViewAdapter(client=None)  # type: ignore[arg-type]
        results = await adapter.fetch(
            SimpleNamespace(code="TRADINGVIEW_WEB"),  # type: ignore[arg-type]
            [
                (
                    SimpleNamespace(id=8, provider_series_id=symbol),
                    SimpleNamespace(id=3, code="TRADINGVIEW_ECONOMICS"),
                )
            ],
            mode="latest",
        )

        assert results == []
        assert adapter.symbol_errors == {symbol: "no_such_symbol"}
        assert any("quote_fast_symbols" in message for message in socket.sent)

    asyncio.run(run())


def test_fetch_normalizes_tls_connection_reset(monkeypatch) -> None:
    async def run() -> None:
        def failed_connect(*_args: object, **_kwargs: object) -> object:
            raise ConnectionResetError()

        monkeypatch.setattr(tradingview, "connect", failed_connect)
        adapter = TradingViewAdapter(client=None)  # type: ignore[arg-type]

        with pytest.raises(
            ProviderDataError,
            match="TradingView WebSocket TLS connection failed.*outbound proxy",
        ):
            await adapter.fetch(
                SimpleNamespace(code="TRADINGVIEW_WEB"),  # type: ignore[arg-type]
                [
                    (
                        SimpleNamespace(id=9, provider_series_id="ECONOMICS:USUR"),
                        SimpleNamespace(id=3, code="TRADINGVIEW_ECONOMICS"),
                    )
                ],
                mode="latest",
            )

    asyncio.run(run())


def test_parse_chart_period_aligns_economic_months() -> None:
    assert parse_chart_period(1751328000, "monthly") == date(2025, 7, 1)
    assert parse_chart_period(1751328000, "quarterly") == date(2025, 7, 1)
    assert parse_chart_period(1751328000, "annual") == date(2025, 1, 1)


def test_chart_history_decoder_extracts_economic_values_and_metadata() -> None:
    decoder = ChartHistoryDecoder(frequency="monthly")
    decoder.consume(
        {
            "m": "symbol_resolved",
            "p": [
                "sds_sym_1",
                {
                    "type": "economic",
                    "data_frequency": "M",
                    "available_data_range_begin_date": 946684800,
                },
            ],
        }
    )
    decoder.consume(
        {
            "m": "timescale_update",
            "p": [
                "cs_test",
                {
                    "sds_1": {
                        "s": [
                            {"i": 0, "v": [1751328000, 4.1]},
                            # Extra values must not be interpreted as extra economic observations.
                            {"i": 1, "v": [1754006400, 4.2, 99.0, 98.0, 97.0]},
                        ]
                    }
                },
            ],
        }
    )
    decoder.consume({"m": "series_completed", "p": ["sds_1", "streaming"]})

    result = decoder.finish()
    assert result.completed is True
    assert result.available_data_range_begin_date == date(2000, 1, 1)
    assert [(point.period_start, str(point.value)) for point in result.points] == [
        (date(2025, 7, 1), "4.1"),
        (date(2025, 8, 1), "4.2"),
    ]


def test_chart_history_decoder_rejects_incomplete_series() -> None:
    decoder = ChartHistoryDecoder(frequency="monthly")
    decoder.consume(
        {
            "m": "timescale_update",
            "p": ["cs_test", {"sds_1": {"s": [{"i": 0, "v": [1751328000, 4.1]}]}}],
        }
    )

    with pytest.raises(tradingview.ProviderDataError, match="series_completed"):
        decoder.finish()


def test_fetch_backfill_persists_chart_history_without_raw_payload(monkeypatch) -> None:
    async def run() -> None:
        symbol = "ECONOMICS:USUR"
        socket = _FakeSocket(
            [
                _frame(
                    {
                        "m": "symbol_resolved",
                        "p": [
                            "sds_sym_1",
                            {
                                "type": "economic",
                                "data_frequency": "M",
                                "available_data_range_begin_date": 1751328000,
                            },
                        ],
                    }
                ),
                _frame(
                    {
                        "m": "timescale_update",
                        "p": [
                            "cs_test",
                            {
                                "sds_1": {
                                    "s": [
                                        {"i": 0, "v": [1751328000, 4.1]},
                                        {"i": 1, "v": [1754006400, 4.2]},
                                    ]
                                }
                            },
                        ],
                    }
                ),
                _frame({"m": "series_completed", "p": ["sds_1", "streaming"]}),
            ]
        )

        def fake_connect(*_args: object, **_kwargs: object) -> _FakeConnection:
            return _FakeConnection(socket)

        monkeypatch.setattr(tradingview, "connect", fake_connect)
        adapter = TradingViewAdapter(client=None)  # type: ignore[arg-type]
        results = await adapter.fetch(
            SimpleNamespace(code="TRADINGVIEW_WEB"),  # type: ignore[arg-type]
            [
                (
                    SimpleNamespace(
                        id=7,
                        provider_series_id=symbol,
                        source_frequency="monthly",
                        source_unit="percent",
                    ),
                    SimpleNamespace(id=3, code="TRADINGVIEW_ECONOMICS"),
                )
            ],
            mode="backfill",
        )

        assert len(results) == 1
        assert [str(item.value) for item in results[0].observations] == ["4.1", "4.2"]
        assert results[0].persist_raw is False
        assert results[0].request_parameters["mode"] == "backfill"
        assert adapter.symbol_errors == {}
        assert any('"chart_create_session"' in message for message in socket.sent)
        assert any('"create_series"' in message for message in socket.sent)
        resolve_symbol = next(
            json.loads(message.split("~m~", 2)[2])
            for message in socket.sent
            if '"resolve_symbol"' in message
        )
        symbol_descriptor = resolve_symbol["p"][2]
        assert symbol_descriptor.startswith("=")
        assert json.loads(symbol_descriptor[1:])["symbol"] == symbol

    asyncio.run(run())


def test_fetch_backfill_requests_more_data_until_provider_start(monkeypatch) -> None:
    async def run() -> None:
        socket = _FakeSocket(
            [
                _frame(
                    {
                        "m": "symbol_resolved",
                        "p": [
                            "sds_sym_1",
                            {
                                "type": "economic",
                                "data_frequency": "M",
                                "available_data_range_begin_date": 1751328000,
                            },
                        ],
                    }
                ),
                _frame(
                    {
                        "m": "timescale_update",
                        "p": [
                            "cs_test",
                            {"sds_1": {"s": [{"i": 0, "v": [1782864000, 5.1]}]}},
                        ],
                    }
                ),
                _frame({"m": "series_completed", "p": ["sds_1", "streaming"]}),
                _frame(
                    {
                        "m": "timescale_update",
                        "p": [
                            "cs_test",
                            {
                                "sds_1": {
                                    "s": [
                                        {"i": 0, "v": [1751328000, 4.1]},
                                        {"i": 1, "v": [1754006400, 4.2]},
                                    ]
                                }
                            },
                        ],
                    }
                ),
                _frame({"m": "series_completed", "p": ["sds_1", "streaming"]}),
            ]
        )

        def fake_connect(*_args: object, **_kwargs: object) -> _FakeConnection:
            return _FakeConnection(socket)

        monkeypatch.setattr(tradingview, "connect", fake_connect)
        adapter = TradingViewAdapter(client=None)  # type: ignore[arg-type]
        results = await adapter.fetch(
            SimpleNamespace(code="TRADINGVIEW_WEB"),  # type: ignore[arg-type]
            [
                (
                    SimpleNamespace(
                        id=7,
                        provider_series_id="ECONOMICS:USUR",
                        source_frequency="monthly",
                    ),
                    SimpleNamespace(id=3, code="TRADINGVIEW_ECONOMICS"),
                )
            ],
            mode="backfill",
        )

        assert len(results[0].observations) == 3
        assert results[0].request_parameters["request_more_data_count"] == 1
        assert any('"request_more_data"' in message for message in socket.sent)

    asyncio.run(run())
