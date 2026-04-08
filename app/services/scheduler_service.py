"""Scheduling Engine — timezone, recurring schedules, and optimal time recommendations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone

from app.core.db import get_supabase

TIMEZONE_MAP: dict[str, timezone] = {
    "UTC": UTC,
    "KST": timezone(timedelta(hours=9)),
    "JST": timezone(timedelta(hours=9)),
    "EST": timezone(timedelta(hours=-5)),
    "CST": timezone(timedelta(hours=-6)),
    "PST": timezone(timedelta(hours=-8)),
    "CET": timezone(timedelta(hours=1)),
    "IST": timezone(timedelta(hours=5, minutes=30)),
}


@dataclass(frozen=True, slots=True)
class PeakWindow:
    platform: str
    days: list[str]
    hours: list[int]
    description: str


PEAK_TIMES: tuple[PeakWindow, ...] = (
    PeakWindow(
        "youtube",
        ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
        [14, 15, 16],
        "YouTube performs best at 2-4 PM in your timezone.",
    ),
    PeakWindow(
        "tiktok",
        ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
        [19, 20, 21],
        "TikTok engagement peaks at 7-9 PM.",
    ),
    PeakWindow(
        "instagram",
        ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
        [11, 19],
        "Instagram sees spikes at 11 AM and 7 PM.",
    ),
    PeakWindow(
        "x",
        ["mon", "tue", "wed", "thu", "fri"],
        [8, 9],
        "X/Twitter engagement is highest at 8-9 AM on weekdays.",
    ),
    PeakWindow(
        "linkedin",
        ["tue", "wed", "thu"],
        [10],
        "LinkedIn peaks on Tue/Wed/Thu at 10 AM.",
    ),
)

DAY_INDICES = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


@dataclass(frozen=True, slots=True)
class TimeRecommendation:
    platform: str
    recommended_times: list[str]
    description: str


@dataclass(frozen=True, slots=True)
class ScheduleEntry:
    id: str
    user_id: str
    post_id: str | None
    platform: str
    tz: str
    recurrence: str
    cron_expression: str | None
    next_run_at: str
    is_active: bool
    created_at: str
    updated_at: str


def resolve_timezone(tz_name: str) -> timezone:
    """Resolve a timezone name to a timezone object."""
    return TIMEZONE_MAP.get(tz_name.upper(), UTC)


def to_utc(dt: datetime, tz_name: str) -> datetime:
    """Convert a naive or aware datetime to UTC using the given timezone name."""
    tz = resolve_timezone(tz_name)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    return dt.astimezone(UTC)


def compute_next_run(
    recurrence: str,
    tz_name: str,
    base_time: datetime | None = None,
    cron_expression: str | None = None,
) -> datetime:
    """Compute the next run time based on recurrence type."""
    now = base_time or datetime.now(UTC)
    tz = resolve_timezone(tz_name)
    local_now = now.astimezone(tz)

    if recurrence == "daily":
        next_local = local_now.replace(
            hour=local_now.hour, minute=0, second=0, microsecond=0,
        ) + timedelta(days=1)
        return next_local.astimezone(UTC)

    if recurrence == "weekly":
        days_ahead = 7
        next_local = local_now.replace(
            hour=local_now.hour, minute=0, second=0, microsecond=0,
        ) + timedelta(days=days_ahead)
        return next_local.astimezone(UTC)

    if recurrence == "custom" and cron_expression:
        return _parse_simple_cron(cron_expression, local_now).astimezone(UTC)

    # once — schedule for 1 hour from now
    return now + timedelta(hours=1)


def _parse_simple_cron(cron_expr: str, local_now: datetime) -> datetime:
    """Parse a simplified cron: 'HH:MM day1,day2' e.g. '14:00 mon,wed,fri'."""
    parts = cron_expr.strip().split()
    if len(parts) < 2:
        return local_now + timedelta(hours=1)

    time_part = parts[0]
    day_part = parts[1] if len(parts) > 1 else ""

    try:
        hour, minute = (int(x) for x in time_part.split(":"))
    except ValueError:
        return local_now + timedelta(hours=1)

    target_days = [
        DAY_INDICES[d.strip().lower()]
        for d in day_part.split(",")
        if d.strip().lower() in DAY_INDICES
    ]
    if not target_days:
        target_days = list(range(7))

    # Find the next matching day
    for offset in range(1, 8):
        candidate = local_now + timedelta(days=offset)
        if candidate.weekday() in target_days:
            return candidate.replace(
                hour=hour, minute=minute, second=0, microsecond=0,
            )

    return local_now.replace(
        hour=hour, minute=minute, second=0, microsecond=0,
    ) + timedelta(days=1)


class SchedulerService:
    """Manages recurring schedules with timezone and peak time support."""

    async def create_schedule(
        self,
        user_id: str,
        platform: str,
        recurrence: str,
        tz: str = "UTC",
        cron_expression: str | None = None,
        post_id: str | None = None,
    ) -> dict:
        """Create a new recurring schedule."""
        next_run = compute_next_run(recurrence, tz, cron_expression=cron_expression)

        sb = get_supabase()
        row = {
            "user_id": user_id,
            "post_id": post_id,
            "platform": platform,
            "tz": tz.upper(),
            "recurrence": recurrence,
            "cron_expression": cron_expression,
            "next_run_at": next_run.isoformat(),
            "is_active": True,
        }
        result = sb.table("schedules").insert(row).execute()
        return result.data[0]

    async def list_schedules(
        self,
        user_id: str,
        is_active: bool | None = None,
        page: int = 1,
        limit: int = 50,
    ) -> tuple[list[dict], int]:
        """List schedules for a user with optional filtering."""
        sb = get_supabase()
        query = sb.table("schedules").select("*", count="exact").eq("user_id", user_id)
        if is_active is not None:
            query = query.eq("is_active", is_active)

        start = (page - 1) * limit
        end = start + limit - 1
        result = query.order("created_at", desc=True).range(start, end).execute()
        return result.data, result.count or 0

    async def delete_schedule(self, schedule_id: str, user_id: str) -> bool:
        """Soft-delete a schedule by marking it inactive."""
        sb = get_supabase()
        result = (
            sb.table("schedules")
            .update({"is_active": False})
            .eq("id", schedule_id)
            .eq("user_id", user_id)
            .execute()
        )
        return len(result.data) > 0

    async def get_due_schedules(self) -> list[dict]:
        """Find schedules that are due for execution."""
        sb = get_supabase()
        now = datetime.now(UTC).isoformat()
        result = (
            sb.table("schedules")
            .select("*")
            .eq("is_active", True)
            .lte("next_run_at", now)
            .execute()
        )
        return result.data

    async def advance_schedule(self, schedule_id: str, schedule: dict) -> dict | None:
        """Advance a schedule to its next run time after execution."""
        recurrence = schedule.get("recurrence", "once")
        if recurrence == "once":
            sb = get_supabase()
            sb.table("schedules").update({"is_active": False}).eq(
                "id", schedule_id,
            ).execute()
            return None

        next_run = compute_next_run(
            recurrence,
            schedule.get("tz", "UTC"),
            cron_expression=schedule.get("cron_expression"),
        )
        sb = get_supabase()
        result = (
            sb.table("schedules")
            .update({"next_run_at": next_run.isoformat()})
            .eq("id", schedule_id)
            .execute()
        )
        return result.data[0] if result.data else None

    @staticmethod
    def recommend_times(
        platforms: list[str],
        tz: str = "UTC",
    ) -> list[TimeRecommendation]:
        """Recommend optimal posting times for given platforms."""
        target_tz = resolve_timezone(tz)
        recommendations: list[TimeRecommendation] = []

        for peak in PEAK_TIMES:
            if peak.platform not in platforms:
                continue

            times: list[str] = []
            for day in peak.days[:3]:
                day_idx = DAY_INDICES[day]
                for hour in peak.hours:
                    local_dt = datetime.now(target_tz).replace(
                        hour=hour, minute=0, second=0, microsecond=0,
                    )
                    while local_dt.weekday() != day_idx:
                        local_dt += timedelta(days=1)
                    times.append(
                        f"{day.capitalize()} {local_dt.strftime('%H:%M')} {tz.upper()}"
                    )

            recommendations.append(
                TimeRecommendation(
                    platform=peak.platform,
                    recommended_times=times[:5],
                    description=peak.description,
                )
            )

        # Include platforms not in PEAK_TIMES with generic advice
        known = {p.platform for p in PEAK_TIMES}
        for platform in platforms:
            if platform not in known:
                recommendations.append(
                    TimeRecommendation(
                        platform=platform,
                        recommended_times=["Weekdays 10:00-14:00 " + tz.upper()],
                        description=(
                            f"No specific peak data for {platform}. "
                            "Try weekday midday as a starting point."
                        ),
                    )
                )

        return recommendations
