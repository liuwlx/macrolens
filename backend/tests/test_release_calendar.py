from datetime import UTC, datetime

from macrolens_worker.tasks.release_calendar import _event_datetime, _match_release, parse_ics


SAMPLE = """BEGIN:VCALENDAR\r
BEGIN:VEVENT\r
UID:cpi-2026-01\r
DTSTART;TZID=America/New_York:20260114T083000\r
SUMMARY:Consumer Price Index - December 2025\r
URL:https://www.bls.gov/news.release/cpi.nr0.htm\r
END:VEVENT\r
BEGIN:VEVENT\r
UID:jobs-2026-01\r
DTSTART:20260109T133000Z\r
SUMMARY:Employment Situation - December 2025\r
END:VEVENT\r
END:VCALENDAR\r
"""


def test_parse_ics_and_timezone() -> None:
    events = parse_ics(SAMPLE)
    assert len(events) == 2
    assert events[0]["UID"] == "cpi-2026-01"
    assert _event_datetime(events[0]) == datetime(2026, 1, 14, 13, 30, tzinfo=UTC)
    assert _event_datetime(events[1]) == datetime(2026, 1, 9, 13, 30, tzinfo=UTC)


def test_release_matching_is_conservative() -> None:
    assert _match_release("Consumer Price Index - May 2026") is not None
    assert _match_release("Employment Situation") is not None
    assert _match_release("Random Webinar") is None
