"""Versioned, explicit deadline arithmetic. All intervals are half-open [start, end).

Business calendars use local wall-clock intervals and UTC elapsed consumption.
On DST boundaries fold=0 selects the first occurrence; end <= start is rejected.
No status label implicitly pauses a clock.
"""
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Calendar:
    version: str = "illustrative-business-v1"
    timezone: str = "Asia/Kolkata"
    weekdays: tuple = (0, 1, 2, 3, 4)
    intervals: tuple = ((9, 17),)
    holidays: frozenset[date] = field(default_factory=frozenset)


def merged_pauses(pauses):
    output = []
    for start, end in sorted(pauses):
        if not start.tzinfo or not end.tzinfo or end <= start:
            raise ValueError("Pauses need ordered timezone-aware timestamps")
        start, end = start.astimezone(timezone.utc), end.astimezone(timezone.utc)
        if output and start <= output[-1][1]:
            output[-1] = (output[-1][0], max(output[-1][1], end))
        else:
            output.append((start, end))
    return output


def calculate(origin, minutes, mode="elapsed", calendar=None, pauses=()):
    if not origin.tzinfo or minutes <= 0 or minutes > 5256000:
        raise ValueError("A timezone-aware origin and duration of 1 to 5,256,000 minutes are required")
    pauses = merged_pauses(pauses)
    remaining = timedelta(minutes=minutes)
    cursor = origin.astimezone(timezone.utc)
    if mode == "elapsed":
        for start, end in pauses:
            if end <= cursor:
                continue
            usable = max(timedelta(), start - cursor)
            if remaining <= usable:
                return cursor + remaining
            remaining -= usable
            cursor = max(cursor, end)
        return cursor + remaining
    if mode != "business":
        raise ValueError("Unknown SLA mode")
    calendar = calendar or Calendar()
    zone = ZoneInfo(calendar.timezone)
    day = cursor.astimezone(zone).date()
    for _ in range(36500):
        if day.weekday() in calendar.weekdays and day not in calendar.holidays:
            for start_hour, end_hour in calendar.intervals:
                start = datetime.combine(day, time(start_hour), zone).astimezone(timezone.utc)
                end = datetime.combine(day, time(end_hour), zone).astimezone(timezone.utc)
                start = max(start, cursor)
                if end <= start:
                    continue
                segments = [(start, end)]
                for p_start, p_end in pauses:
                    next_segments = []
                    for a, b in segments:
                        if p_end <= a or p_start >= b:
                            next_segments.append((a, b))
                        else:
                            if a < p_start:
                                next_segments.append((a, p_start))
                            if p_end < b:
                                next_segments.append((p_end, b))
                    segments = next_segments
                for a, b in segments:
                    usable = b - a
                    if remaining <= usable:
                        return a + remaining
                    remaining -= usable
        day += timedelta(days=1)
    raise ValueError("Deadline exceeds the supported calendar horizon")
