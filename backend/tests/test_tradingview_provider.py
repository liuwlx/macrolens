from __future__ import annotations

import asyncio
import json
from datetime import date
from types import SimpleNamespace

import pytest

from macrolens_worker.providers import tradingview
from macrolens_worker.providers.tradingview import (
    FrameDecoder,
    TradingViewAdapter,
    encode_frame,
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
