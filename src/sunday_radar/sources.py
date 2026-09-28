from __future__ import annotations

from datetime import date

from sunday_radar.adapters.bank_of_korea import load_window as load_bank_of_korea
from sunday_radar.adapters.morningnews import load_window as load_morningnews
from sunday_radar.domain import SourceDay
from sunday_radar.settings import Settings


def load_sources(settings: Settings, as_of: date) -> list[SourceDay]:
    days = [
        *load_morningnews(settings.morningnews_root, as_of),
        *load_bank_of_korea(settings.bank_of_korea_cache_dir, as_of),
    ]
    return sorted(days, key=lambda day: (day.report_date, day.source_kind))
