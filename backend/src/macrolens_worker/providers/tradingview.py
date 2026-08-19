from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
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


def parse_chart_period(timestamp: object, frequency: str) -> date:
    if not isinstance(timestamp, (int, float)):
        raise ProviderDataError(f"TradingView chart timestamp is invalid: {timestamp!r}")
    seconds = float(timestamp)
    if seconds > 100_000_000_000:
        seconds /= 1000
    value = datetime.fromtimestamp(seconds, UTC).date()
    normalized = frequency.lower()
    if normalized == "monthly":
        return value.replace(day=1)
    if normalized == "quarterly":
        return value.replace(month=((value.month - 1) // 3) * 3 + 1, day=1)
    if normalized in {"semiannual", "semi-annual"}:
        return value.replace(month=1 if value.month <= 6 else 7, day=1)
    if normalized == "annual":
        return value.replace(month=1, day=1)
    return value


@dataclass(frozen=True, slots=True)
class ChartHistoryPoint:
    period_start: date
    value: Decimal
    timestamp: float


@dataclass(frozen=True, slots=True)
class ChartHistoryResult:
    points: tuple[ChartHistoryPoint, ...]
    metadata: dict[str, Any]
    available_data_range_begin_date: date | None
    completed: bool


class ChartHistoryDecoder:
    """Decode economic chart-session updates without treating them as OHLC bars."""

    def __init__(self, *, frequency: str) -> None:
        self.frequency = frequency
        self._frame_decoder = FrameDecoder()
        self._metadata: dict[str, Any] = {}
        self._points: dict[date, ChartHistoryPoint] = {}
        self._completed = False
        self._error: str | None = None

    def feed(self, data: str | bytes) -> list[dict[str, Any]]:
        return self._frame_decoder.feed(data)

    def consume(self, message: dict[str, Any]) -> None:
        method = message.get("m")
        params = message.get("p")
        if method == "symbol_resolved" and isinstance(params, list) and len(params) >= 2:
            metadata = params[1]
            if isinstance(metadata, dict):
                self._metadata.update(metadata)
            return
        if method == "series_error":
            self._error = str(params[1] if isinstance(params, list) and len(params) > 1 else params)
            return
        if method == "series_completed":
            self._completed = True
            return
        if method != "timescale_update" or not isinstance(params, list) or len(params) < 2:
            return
        payload = params[1]
        if not isinstance(payload, dict):
            return
        for series_payload in payload.values():
            if not isinstance(series_payload, dict):
                continue
            rows = series_payload.get("s") or series_payload.get("st")
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                values = row.get("v")
                if not isinstance(values, list) or len(values) < 2:
                    continue
                timestamp = values[0]
                period_start = parse_chart_period(timestamp, self.frequency)
                value = parse_decimal(values[1])
                if value is None:
                    continue
                point = ChartHistoryPoint(period_start, value, float(timestamp))
                previous = self._points.get(period_start)
                if previous is not None and previous.value != point.value:
                    raise ProviderDataError(
                        "TradingView chart returned conflicting values for "
                        f"period={period_start}."
                    )
                self._points[period_start] = point

    def finish(self) -> ChartHistoryResult:
        if self._error:
            raise ProviderDataError(f"TradingView chart series failed: {self._error}")
        if not self._completed:
            raise ProviderDataError("TradingView chart history did not receive series_completed")
        if not self._points:
            raise ProviderDataError("TradingView chart history returned no observations")
        begin_raw = self._metadata.get("available_data_range_begin_date")
        begin = None
        if isinstance(begin_raw, (int, float)):
            begin = datetime.fromtimestamp(float(begin_raw), UTC).date()
        return ChartHistoryResult(
            points=tuple(self._points[key] for key in sorted(self._points)),
            metadata=dict(self._metadata),
            available_data_range_begin_date=begin,
            completed=True,
        )

    @property
    def completed(self) -> bool:
        return self._completed

    @property
    def oldest_period(self) -> date | None:
        return min(self._points) if self._points else None

    @property
    def error(self) -> str | None:
        return self._error

    def prepare_for_more_data(self) -> None:
        self._completed = False


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
        self.symbol_errors = {}
        if mode not in {"latest", "incremental", "backfill"}:
            raise ProviderDataError(f"TradingView V1 does not support sync mode {mode!r}")
        if not mappings:
            return []

        if mode == "backfill":
            return await self._fetch_history(provider, mappings)

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

    async def _fetch_history(
        self,
        provider: Provider,
        mappings: list[tuple[SourceSeries, Dataset]],
    ) -> list[ProviderFetchResult]:
        if len(mappings) != 1:
            raise ProviderDataError("TradingView history sync accepts exactly one Series")
        source, dataset = mappings[0]
        settings = get_settings()
        symbol = _symbol_from_source(source)
        frequency = source.source_frequency or "monthly"
        resolution = {
            "daily": "1D",
            "weekly": "1W",
            "monthly": "1M",
            "quarterly": "3M",
            "annual": "12M",
        }.get(frequency.lower())
        if resolution is None:
            raise ProviderDataError(f"TradingView history has unsupported frequency {frequency!r}")

        chart_session = f"cs_{uuid4().hex}"
        symbol_session = f"sds_sym_{uuid4().hex}"
        series_id = "sds_1"
        turnaround = "s1"
        decoder = ChartHistoryDecoder(frequency=frequency)
        endpoint = (
            f"{settings.tradingview_ws_url}?from=markets%2Fworld-economy%2Fcountries%2F"
            f"united-states%2F&date={datetime.now(UTC).replace(microsecond=0).isoformat()}"
            "&auth=sessionid"
        )
        symbol_payload = "=" + json.dumps(
            {"symbol": symbol, "adjustment": "splits", "session": "regular"},
            separators=(",", ":"),
        )
        initial_bars = 5000
        max_requests = 10
        request_count = 0
        last_oldest: date | None = None

        async with _connect_tradingview(endpoint, settings) as websocket:
            commands: list[dict[str, Any]] = [
                {"m": "set_data_quality", "p": ["low"]},
                {"m": "set_auth_token", "p": ["unauthorized_user_token"]},
                {"m": "set_locale", "p": ["zh-Hans", "CN"]},
                {"m": "chart_create_session", "p": [chart_session, ""]},
                {"m": "switch_timezone", "p": [chart_session, "Etc/UTC"]},
                {"m": "resolve_symbol", "p": [chart_session, symbol_session, symbol_payload]},
                {
                    "m": "create_series",
                    "p": [
                        chart_session,
                        series_id,
                        turnaround,
                        symbol_session,
                        resolution,
                        initial_bars,
                        "",
                    ],
                },
            ]
            for command in commands:
                await websocket.send(encode_frame(command))

            while True:
                try:
                    incoming = await asyncio.wait_for(
                        websocket.recv(),
                        timeout=settings.tradingview_receive_timeout_seconds,
                    )
                except TimeoutError as exc:
                    raise ProviderDataError(
                        "TradingView chart history timed out before series_completed"
                    ) from exc
                for payload in decoder.feed(incoming):
                    if payload.get("m") == "heartbeat":
                        await websocket.send(_encode_control_frame("heartbeat"))
                    else:
                        decoder.consume(payload)
                if decoder.error:
                    raise ProviderDataError(
                        f"TradingView chart series failed: {decoder.error}"
                    )
                if not decoder.completed:
                    continue

                metadata_begin = decoder.finish().available_data_range_begin_date
                oldest = decoder.oldest_period
                if (
                    metadata_begin is None
                    or oldest is None
                    or oldest <= metadata_begin
                    or request_count >= max_requests
                    or oldest == last_oldest
                ):
                    break
                last_oldest = oldest
                request_count += 1
                decoder.prepare_for_more_data()
                await websocket.send(
                    encode_frame(
                        {
                            "m": "request_more_data",
                            "p": [chart_session, series_id, initial_bars],
                        }
                    )
                )

            result = decoder.finish()
            await websocket.send(
                encode_frame({"m": "remove_series", "p": [chart_session, series_id]})
            )
            await websocket.send(encode_frame({"m": "chart_delete_session", "p": [chart_session]}))

        captured_at = datetime.now(UTC)
        observations = [
            NormalizedObservation(
                source_series_id=source.id,
                period_start=point.period_start,
                period_end=period_end(point.period_start, frequency),
                value=point.value,
                vintage_at=captured_at,
                quality_flags=[
                    "tradingview_chart",
                    f"tradingview_frequency:{frequency}",
                    f"tradingview_resolution:{resolution}",
                ],
            )
            for point in result.points
        ]
        if result.available_data_range_begin_date and (
            observations[0].period_start > result.available_data_range_begin_date
        ):
            raise ProviderDataError(
                "TradingView chart history did not reach available_data_range_begin_date"
            )
        return [
            ProviderFetchResult(
                provider=provider,
                dataset=dataset,
                request_url=endpoint.split("?", 1)[0],
                request_parameters={
                    "mode": "backfill",
                    "symbol": symbol,
                    "resolution": resolution,
                    "history_start": observations[0].period_start.isoformat(),
                    "history_end": observations[-1].period_start.isoformat(),
                    "observation_count": len(observations),
                    "request_more_data_count": request_count,
                },
                content_type="application/json",
                raw_bytes=b"",
                observations=observations,
                captured_at=captured_at,
                persist_raw=False,
            )
        ]
