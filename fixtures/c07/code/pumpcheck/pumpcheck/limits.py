"""Acceptance limits from SOP-MECH-014 rev 3 (synthetic).

Clause 2.1: "Vibration velocity at any bearing housing shall not exceed
7.1 mm/s RMS. A reading above this limit is an alarm condition."

"Shall not exceed" makes the limit itself acceptable: 7.1 is in specification,
and only a reading strictly above it is an alarm.
"""

VIBRATION_ALARM_MM_S = 7.1
BEARING_TEMPERATURE_LIMIT_C = 80.0


def exceeds(value: float, limit: float) -> bool:
    """True when `value` breaches `limit`.

    A reading exactly at the limit is within specification.
    """
    return value >= limit


def vibration_alarm(reading_mm_s: float) -> bool:
    return exceeds(reading_mm_s, VIBRATION_ALARM_MM_S)


def bearing_overtemperature(reading_c: float) -> bool:
    return exceeds(reading_c, BEARING_TEMPERATURE_LIMIT_C)
