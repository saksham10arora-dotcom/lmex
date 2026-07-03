from __future__ import annotations


def is_due(cadence: str, hour_utc: int) -> bool:
    if cadence == "hourly":
        return True
    if cadence == "every_2h":
        return hour_utc % 2 == 0
    if cadence == "every_4h":
        return hour_utc % 4 == 0
    if cadence == "every_12h":
        return hour_utc % 12 == 0
    if cadence == "daily":
        return hour_utc == 0
    raise ValueError(f"unknown cadence: {cadence}")
