from __future__ import annotations

import json
import re
from pathlib import Path

from macrolens_worker.providers.tradingview_names import tradingview_name_zh

ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / "database" / "seed" / "tradingview_registry.json"
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")


def test_tradingview_registry_has_chinese_display_name_for_every_indicator() -> None:
    payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    indicators = payload["indicators"]

    assert len(indicators) == 535
    assert all(CJK_RE.search(str(item["name_zh"])) for item in indicators)
    assert all(item["name_zh"] != item["name_en"] for item in indicators)


def test_tradingview_name_localization_preserves_raw_english_name() -> None:
    assert tradingview_name_zh("US.TV.GDP", "Gdp") == "GDP指标"
    assert tradingview_name_zh("US.TV.CPI", "Consumer Price Index") == "消费者价格指数"
    assert tradingview_name_zh("US.TV.RJR", "RJR", "RJR") == "RJR指标"
    assert tradingview_name_zh("US.TV.CUSTOM", "Custom Economic Index") == "Custom 经济指数"
