from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4

from websockets.asyncio.client import connect
from websockets.typing import Origin

from macrolens_api.config import Settings, get_settings
from macrolens_api.models import Dataset, Provider, SourceSeries
from macrolens_worker.providers.base import (
    NormalizedObservation,
    ProviderAdapter,
    ProviderDataError,
    ProviderFetchResult,
    parse_decimal,
    period_end,
)

_FRAME_PREFIX = b"~m~"
_FREQUENCY_MAP = {
    "D": "daily",
    "W": "weekly",
    "M": "monthly",
    "3M": "quarterly",
    "12M": "annual",
}


def encode_frame(message: dict[str, Any]) -> str:
    payload = json.dumps(message, ensure_ascii=False, separators=(",", ":"))
    return f"~m~{len(payload.encode('utf-8'))}~m~{payload}"


def _encode_control_frame(payload: str) -> str:
    return f"~m~{len(payload.encode('utf-8'))}~m~{payload}"


class FrameDecoder:
    """Decode TradingView length-prefixed frames across message boundaries."""

    def __init__(self) -> None:
        self._buffer = bytearray()

    def feed(self, data: str | bytes) -> list[dict[str, Any]]:
        self._buffer.extend(data.encode("utf-8") if isinstance(data, str) else data)
        messages: list[dict[str, Any]] = []
        while True:
            if not self._buffer.startswith(_FRAME_PREFIX):
                start = self._buffer.find(_FRAME_PREFIX)
                if start < 0:
                    self._buffer.clear()
                    break
                del self._buffer[:start]
            marker = self._buffer.find(_FRAME_PREFIX, len(_FRAME_PREFIX))
            if marker < 0:
                break
            length_bytes = bytes(self._buffer[len(_FRAME_PREFIX) : marker])
            if not length_bytes.isdigit():
                del self._buffer[: len(_FRAME_PREFIX)]
                continue
            payload_start = marker + len(_FRAME_PREFIX)
            payload_end = payload_start + int(length_bytes)
            if len(self._buffer) < payload_end:
                break
            payload = bytes(self._buffer[payload_start:payload_end])
            del self._buffer[:payload_end]
            try:
                message = json.loads(payload.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                if payload == b"heartbeat":
                    messages.append({"m": "heartbeat", "p": []})
                continue
            if isinstance(message, dict) and isinstance(message.get("m"), str):
                messages.append(message)
        return messages


def _parse_date_text(value: str) -> date | None:
    normalized = " ".join(value.strip().split())
    for fmt in ("%d %b %Y", "%b %d %Y", "%Y-%m-%d", "%d %B %Y", "%B %d %Y"):
        try:
            return datetime.strptime(normalized, fmt).date()
        except ValueError:
            continue
    return None


def parse_observation_period(period: object, frequency: object) -> date | None:
    if period is None:
        return None
    frequency_code = str(frequency or "").upper()
    if isinstance(period, (int, float)):
        timestamp = float(period)
        if 19_000_101 <= timestamp <= 21_001_231:
            return datetime.strptime(str(int(timestamp)), "%Y%m%d").date()
        if timestamp > 100_000_000_000:
            timestamp /= 1000
        return datetime.fromtimestamp(timestamp, UTC).date()
    text = " ".join(str(period).strip().split())
    quarter = re.fullmatch(r"Q([1-4])\s+(\d{4})", text, flags=re.IGNORECASE)
    if quarter:
        return date(int(quarter.group(2)), (int(quarter.group(1)) - 1) * 3 + 1, 1)
    year = re.fullmatch(r"(\d{4})", text)
    if year:
        return date(int(year.group(1)), 1, 1)
    month = re.fullmatch(r"([A-Za-z]{3,9})\s+(\d{4})", text)
    if month:
        return _parse_date_text(f"1 {month.group(1)} {month.group(2)}")
    parsed = _parse_date_text(text)
    if parsed is not None:
        return parsed
    if frequency_code == "M" and re.fullmatch(r"\d{4}-\d{2}", text):
        return date.fromisoformat(f"{text}-01")
    return None


def _frequency_label(value: object) -> str:
    return _FREQUENCY_MAP.get(str(value or "").upper(), "monthly")


def _symbol_from_source(source: SourceSeries) -> str:
    symbol = str(source.provider_series_id or "").strip()
    if not symbol.startswith("ECONOMICS:"):
        raise ProviderDataError(f"TradingView source mapping has invalid Symbol: {symbol!r}")
    return symbol


@asynccontextmanager
async def _connect_tradingview(
    endpoint: str,
    settings: Settings,
) -> AsyncIterator[Any]:
    """Open TradingView WebSocket and make outbound network failures actionable."""

    try:
        async with connect(
            endpoint,
            origin=Origin(settings.tradingview_origin),
            user_agent_header=settings.tradingview_user_agent,
            open_timeout=settings.tradingview_connect_timeout_seconds,
            ping_interval=settings.tradingview_ping_interval_seconds,
            ping_timeout=settings.tradingview_ping_timeout_seconds,
        ) as websocket:
            yield websocket
    except (ConnectionError, TimeoutError) as exc:
        raise ProviderDataError(
            "TradingView WebSocket TLS connection failed: the remote server or outbound "
            "proxy reset the connection; check the worker's outbound proxy or firewall."
        ) from exc


class TradingViewAdapter(ProviderAdapter):
    code = "TRADINGVIEW_WEB"
    symbol_errors: dict[str, str]

    async def fetch(
        self,
        provider: Provider,
        mappings: list[tuple[SourceSeries, Dataset]],
        *,
        mode: str,
    ) -> list[ProviderFetchResult]:
        if mode not in {"latest", "incremental"}:
            raise ProviderDataError(f"TradingView V1 only supports latest sync, got {mode!r}")
        if not mappings:
            return []

        self.symbol_errors = {}
        settings = get_settings()
        symbol_to_mapping = {
            _symbol_from_source(source): (source, dataset) for source, dataset in mappings
        }
        symbols = list(symbol_to_mapping)
        quote_session = f"qs_{uuid4().hex}"
        latest_values: dict[str, dict[str, Any]] = {}
        completed: set[str] = set()
        decoder = FrameDecoder()
        endpoint = (
            f"{settings.tradingview_ws_url}?from=markets%2Fworld-economy%2Fcountries%2Funited-states%2F"
            f"&date={datetime.now(UTC).replace(microsecond=0).isoformat().replace('+00:00', 'Z')}"
            "&auth=sessionid"
        )

        async with _connect_tradingview(endpoint, settings) as websocket:
            commands = [
                {"m": "set_data_quality", "p": ["low"]},
                {"m": "set_auth_token", "p": ["unauthorized_user_token"]},
                {"m": "set_locale", "p": ["zh-Hans", "CN"]},
                {"m": "quote_create_session", "p": [quote_session]},
                {
                    "m": "quote_set_fields",
                    "p": [
                        quote_session,
                        "pro_name",
                        "short_name",
                        "type",
                        "exchange",
                        "lp",
                        "prev_close_price",
                        "reference-last-period-start",
                        "reference-last-period",
                        "value_unit_id",
                        "measure",
                        "data_frequency",
                        "country_code",
                        "short_description",
                        "source2",
                        "next_release_date",
                        "forecast_raw",
                    ],
                },
                {"m": "quote_add_symbols", "p": [quote_session, *symbols]},
                {"m": "quote_fast_symbols", "p": [quote_session, *symbols]},
            ]
            for command in commands:
                await websocket.send(encode_frame(command))

            deadline = (
                asyncio.get_running_loop().time()
                + settings.tradingview_receive_timeout_seconds
            )
            received_response = False
            while len(completed) < len(symbols):
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    break
                receive_timeout = min(
                    remaining,
                    settings.tradingview_idle_timeout_seconds
                    if received_response
                    else remaining,
                )
                try:
                    incoming = await asyncio.wait_for(
                        websocket.recv(), timeout=receive_timeout
                    )
                except TimeoutError:
                    break
                received_response = True
                for payload in decoder.feed(incoming):
                    method = payload.get("m")
                    params = payload.get("p")
                    if method == "heartbeat":
                        await websocket.send(_encode_control_frame("heartbeat"))
                    elif method == "qsd" and isinstance(params, list) and len(params) >= 2:
                        item = params[1]
                        if isinstance(item, dict) and isinstance(item.get("n"), str):
                            symbol = item["n"]
                            previous = latest_values.setdefault(symbol, {})
                            previous_values = previous.get("v")
                            merged_values = (
                                dict(previous_values) if isinstance(previous_values, dict) else {}
                            )
                            previous.update(item)
                            if isinstance(item.get("v"), dict):
                                merged_values.update(item["v"])
                                previous["v"] = merged_values
                    elif (
                        method == "quote_completed"
                        and isinstance(params, list)
                        and len(params) >= 2
                    ):
                        completed.add(str(params[1]))

        captured_at = datetime.now(UTC)
        grouped: dict[int, tuple[Dataset, list[NormalizedObservation]]] = {}
        for symbol, (source, dataset) in symbol_to_mapping.items():
            item = latest_values.get(symbol)
            if item is None:
                self.symbol_errors[symbol] = "no_response"
                continue
            if item.get("s") != "ok":
                self.symbol_errors[symbol] = str(
                    item.get("errmsg") or item.get("s") or "provider_error"
                )
                continue
            values = item.get("v")
            if not isinstance(values, dict):
                self.symbol_errors[symbol] = "missing_value_payload"
                continue
            frequency_code = str(values.get("data_frequency") or "")
            frequency = _frequency_label(frequency_code)
            period = parse_observation_period(
                values.get("reference-last-period-start")
                or values.get("reference-last-period"),
                frequency_code,
            )
            value = parse_decimal(values.get("lp"))
            if period is None:
                self.symbol_errors[symbol] = "unparsed_period"
                continue
            if value is None:
                self.symbol_errors[symbol] = "missing_latest_value"
                continue
            observation = NormalizedObservation(
                source_series_id=source.id,
                period_start=period,
                period_end=period_end(period, frequency),
                value=value,
                vintage_at=captured_at,
                quality_flags=[
                    "tradingview_qsd",
                    f"tradingview_frequency:{frequency_code or 'M'}",
                    f"tradingview_unit:{values.get('value_unit_id') or 'VALUE'}",
                ],
            )
            bucket = grouped.setdefault(dataset.id, (dataset, []))
            bucket[1].append(observation)

        return [
            ProviderFetchResult(
                provider=provider,
                dataset=dataset,
                request_url=endpoint.split("?", 1)[0],
                request_parameters={"mode": mode, "symbols": symbols},
                content_type="application/json",
                raw_bytes=b"",
                observations=observations,
                captured_at=captured_at,
                persist_raw=False,
            )
            for dataset, observations in grouped.values()
        ]
