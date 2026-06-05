#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

DEFAULT_HOMEWORK_DAYS = "1:3,2:5,3:7,4:9,5:13,6:15,7:17,8:19,9:23,10:25"
DEFAULT_EXAM_DAYS = "1:10,2:20"
DEFAULT_EVENT_COLOR = "#b91c1c"
DEFAULT_DUE_TIME = "21:00"
DEFAULT_GOOGLE_PREFIX = "DS3000 Homework"

VESSENCE_HOME = Path(os.environ.get("VESSENCE_HOME", "/home/chieh/ambient/vessence"))
VESSENCE_DATA_HOME = Path(
    os.environ.get("VESSENCE_DATA_HOME", "/home/chieh/ambient/vessence-data")
)
os.environ.setdefault("VESSENCE_HOME", str(VESSENCE_HOME))
os.environ.setdefault("VESSENCE_DATA_HOME", str(VESSENCE_DATA_HOME))
sys.path.insert(0, str(VESSENCE_HOME))
sys.path.insert(0, str(VESSENCE_HOME / "agent_skills"))

try:
    import pymysql
except Exception as exc:  # pragma: no cover - environment guard
    raise SystemExit(f"pymysql is required: {exc}") from exc

try:
    from agent_skills.edu_homework_audit import db_connect
except Exception as exc:  # pragma: no cover - environment guard
    raise SystemExit(f"Could not import db_connect from Vessence: {exc}") from exc


WEEKDAY_INDEX = {
    "mon": 0,
    "monday": 0,
    "tue": 1,
    "tues": 1,
    "tuesday": 1,
    "wed": 2,
    "wednesday": 2,
    "thu": 3,
    "thur": 3,
    "thurs": 3,
    "thursday": 3,
    "fri": 4,
    "friday": 4,
    "sat": 5,
    "saturday": 5,
    "sun": 6,
    "sunday": 6,
}


@dataclass(frozen=True)
class SectionInfo:
    id: int
    name: str
    course_number: str | None
    section_code: str | None
    semester_year: str | None
    course_id: int
    starts_on: dt.date
    ends_on: dt.date
    timezone_name: str


@dataclass(frozen=True)
class HomeworkPlan:
    hw_num: int
    assignment_id: int
    assignment_title: str
    day_num: int
    due_date: dt.date
    due_local: dt.datetime
    due_utc_naive: dt.datetime


def parse_mapping(raw: str) -> dict[int, int]:
    mapping: dict[int, int] = {}
    for part in raw.split(","):
        item = part.strip()
        if not item:
            continue
        if ":" not in item:
            raise ValueError(f"mapping item must be N:DAY, got {item!r}")
        left, right = item.split(":", 1)
        key = int(left.strip())
        value = int(right.strip())
        if key <= 0 or value <= 0:
            raise ValueError(f"mapping values must be positive, got {item!r}")
        mapping[key] = value
    if not mapping:
        raise ValueError("mapping cannot be empty")
    return dict(sorted(mapping.items()))


def parse_time(raw: str) -> dt.time:
    try:
        hour_s, minute_s = raw.strip().split(":", 1)
        hour = int(hour_s)
        minute = int(minute_s)
        return dt.time(hour=hour, minute=minute)
    except Exception as exc:
        raise ValueError(f"due time must be HH:MM, got {raw!r}") from exc


def as_date(value: Any) -> dt.date:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str):
        return dt.datetime.fromisoformat(value).date()
    raise TypeError(f"cannot convert {value!r} to date")


def format_date_range(start: dt.date, end: dt.date) -> str:
    return start.isoformat() if start == end else f"{start.isoformat()}..{end.isoformat()}"


def fmt_due_time(t: dt.time) -> str:
    return dt.datetime.combine(dt.date(2000, 1, 1), t).strftime("Due %-I:%M %p")


def fetch_section(conn, section_id: int) -> SectionInfo:
    with conn.cursor(pymysql.cursors.DictCursor) as cur:
        cur.execute(
            """
            SELECT id, course_number, section_id, semester_year, course_id,
                   term_starts_on, term_ends_on, timezone_name
            FROM `class`
            WHERE id = %s
            """,
            (section_id,),
        )
        row = cur.fetchone()
    if not row:
        raise SystemExit(f"No class/section row found for id {section_id}")
    missing = [
        col
        for col in ("course_id", "term_starts_on", "term_ends_on", "timezone_name")
        if row.get(col) in (None, "")
    ]
    if missing:
        raise SystemExit(f"Section {section_id} is missing required fields: {', '.join(missing)}")
    section_name = " ".join(
        str(part)
        for part in (row.get("course_number"), row.get("semester_year"), row.get("section_id"))
        if part not in (None, "")
    )
    return SectionInfo(
        id=int(row["id"]),
        name=section_name or f"section {row['id']}",
        course_number=row.get("course_number"),
        section_code=row.get("section_id"),
        semester_year=row.get("semester_year"),
        course_id=int(row["course_id"]),
        starts_on=as_date(row["term_starts_on"]),
        ends_on=as_date(row["term_ends_on"]),
        timezone_name=str(row["timezone_name"] or "America/New_York"),
    )


def fetch_holidays(conn, section_id: int) -> list[dict[str, Any]]:
    with conn.cursor(pymysql.cursors.DictCursor) as cur:
        cur.execute(
            """
            SELECT id, label, starts_on, ends_on
            FROM section_holidays
            WHERE section_id = %s
            ORDER BY starts_on, id
            """,
            (section_id,),
        )
        return list(cur.fetchall())


def holiday_dates(rows: list[dict[str, Any]]) -> set[dt.date]:
    dates: set[dt.date] = set()
    for row in rows:
        start = as_date(row["starts_on"])
        end = as_date(row["ends_on"])
        day = start
        while day <= end:
            dates.add(day)
            day += dt.timedelta(days=1)
    return dates


def parse_weekdays(days_raw: str | None) -> set[int]:
    days: set[int] = set()
    for token in re.split(r"[,/ ]+", (days_raw or "").strip().lower()):
        if not token:
            continue
        if token not in WEEKDAY_INDEX:
            raise ValueError(f"unknown weekday token {token!r} in {days_raw!r}")
        days.add(WEEKDAY_INDEX[token])
    return days


def fetch_recurring_class_events(conn, section_id: int) -> list[dict[str, Any]]:
    with conn.cursor(pymysql.cursors.DictCursor) as cur:
        cur.execute(
            """
            SELECT id, title, days, time_str, position
            FROM section_events
            WHERE section_id = %s
              AND auto_increment = 1
              AND specific_date IS NULL
            ORDER BY position, id
            """,
            (section_id,),
        )
        return list(cur.fetchall())


def build_class_days(
    section: SectionInfo,
    class_events: list[dict[str, Any]],
    holidays: set[dt.date],
) -> list[dt.date]:
    weekdays: set[int] = set()
    for event in class_events:
        weekdays.update(parse_weekdays(event.get("days")))
    if not weekdays:
        raise SystemExit(
            f"Section {section.id} has no recurring auto-increment class-day events"
        )
    days: list[dt.date] = []
    day = section.starts_on
    while day <= section.ends_on:
        if day.weekday() in weekdays and day not in holidays:
            days.append(day)
        day += dt.timedelta(days=1)
    if not days:
        raise SystemExit(f"No class days generated for section {section.id}")
    return days


def fetch_hw_assignments(conn, course_id: int, needed: int) -> list[dict[str, Any]]:
    with conn.cursor(pymysql.cursors.DictCursor) as cur:
        cur.execute(
            """
            SELECT id, title, position, published, assignment_type
            FROM assignments
            WHERE course_id = %s
              AND kind = 'hw'
              AND assignment_type = 'module'
            ORDER BY position, id
            """,
            (course_id,),
        )
        rows = list(cur.fetchall())
    if len(rows) < needed:
        raise SystemExit(
            f"Course {course_id} has only {len(rows)} homework assignments; need {needed}"
        )
    return rows


def to_utc_naive(local_dt: dt.datetime) -> dt.datetime:
    return local_dt.astimezone(dt.timezone.utc).replace(tzinfo=None)


def build_homework_plan(
    section: SectionInfo,
    class_days: list[dt.date],
    assignments: list[dict[str, Any]],
    homework_days: dict[int, int],
    due_time: dt.time,
) -> list[HomeworkPlan]:
    tz = ZoneInfo(section.timezone_name)
    plan: list[HomeworkPlan] = []
    for hw_num, day_num in homework_days.items():
        if day_num > len(class_days):
            raise SystemExit(
                f"HW{hw_num} maps to Day {day_num}, but only {len(class_days)} class days exist"
            )
        assignment = assignments[hw_num - 1]
        due_date = class_days[day_num - 1]
        due_local = dt.datetime.combine(due_date, due_time, tzinfo=tz)
        plan.append(
            HomeworkPlan(
                hw_num=hw_num,
                assignment_id=int(assignment["id"]),
                assignment_title=str(assignment["title"]),
                day_num=day_num,
                due_date=due_date,
                due_local=due_local,
                due_utc_naive=to_utc_naive(due_local),
            )
        )
    return plan


def fetch_exam_events(conn, section_id: int) -> list[dict[str, Any]]:
    with conn.cursor(pymysql.cursors.DictCursor) as cur:
        cur.execute(
            """
            SELECT id, title, specific_date
            FROM section_events
            WHERE section_id = %s
              AND specific_date IS NOT NULL
              AND LOWER(title) LIKE '%%exam%%'
            ORDER BY specific_date, id
            """,
            (section_id,),
        )
        return list(cur.fetchall())


def check_exam_anchors(
    class_days: list[dt.date],
    exam_days: dict[int, int],
    exam_events: list[dict[str, Any]],
) -> list[str]:
    lines: list[str] = []
    for exam_num, day_num in exam_days.items():
        expected = class_days[day_num - 1] if day_num <= len(class_days) else None
        matches = [
            event
            for event in exam_events
            if re.search(rf"\bexam\s*{exam_num}\b", str(event["title"]), re.I)
        ]
        if expected is None:
            lines.append(f"Exam {exam_num}: Day {day_num} is beyond generated class days")
            continue
        if not matches:
            lines.append(
                f"Exam {exam_num}: expected {expected.isoformat()} from Day {day_num}; no app event found"
            )
            continue
        for event in matches:
            actual = as_date(event["specific_date"])
            status = "OK" if actual == expected else "MISMATCH"
            lines.append(
                f"Exam {exam_num}: {status}; schedule Day {day_num} = {expected.isoformat()}, "
                f"event {event['id']} {event['title']!r} = {actual.isoformat()}"
            )
    return lines


def fetch_existing_due_rows(conn, section_id: int, assignment_ids: list[int]) -> dict[int, dict[str, Any]]:
    if not assignment_ids:
        return {}
    placeholders = ",".join(["%s"] * len(assignment_ids))
    with conn.cursor(pymysql.cursors.DictCursor) as cur:
        cur.execute(
            f"""
            SELECT id, assignment_id, due_at
            FROM assignment_section_due
            WHERE section_id = %s AND assignment_id IN ({placeholders})
            """,
            [section_id, *assignment_ids],
        )
        return {int(row["assignment_id"]): row for row in cur.fetchall()}


def upsert_due_rows(conn, section_id: int, plan: list[HomeworkPlan]) -> tuple[int, int]:
    updated = 0
    inserted = 0
    with conn.cursor() as cur:
        for item in plan:
            cur.execute(
                """
                INSERT INTO assignment_section_due (section_id, assignment_id, due_at)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    due_at = VALUES(due_at),
                    updated_at = CURRENT_TIMESTAMP
                """,
                (section_id, item.assignment_id, item.due_utc_naive),
            )
            if cur.rowcount == 1:
                inserted += 1
            else:
                updated += 1
    return inserted, updated


def upsert_app_homework_events(
    conn,
    section_id: int,
    plan: list[HomeworkPlan],
    due_time: dt.time,
    color: str,
) -> tuple[int, int]:
    updated = 0
    inserted = 0
    time_str = fmt_due_time(due_time)
    with conn.cursor(pymysql.cursors.DictCursor) as read_cur, conn.cursor() as write_cur:
        for item in plan:
            title = f"Homework {item.hw_num} due"
            read_cur.execute(
                """
                SELECT id
                FROM section_events
                WHERE section_id = %s AND title = %s
                ORDER BY id
                LIMIT 1
                """,
                (section_id, title),
            )
            existing = read_cur.fetchone()
            if existing:
                write_cur.execute(
                    """
                    UPDATE section_events
                    SET days = '', time_str = %s, specific_date = %s, color = %s
                    WHERE id = %s
                    """,
                    (time_str, item.due_date, color, existing["id"]),
                )
                updated += 1
            else:
                write_cur.execute(
                    """
                    INSERT INTO section_events
                        (section_id, title, days, time_str, position, auto_increment, specific_date, color)
                    VALUES
                        (%s, %s, '', %s, %s, 0, %s, %s)
                    """,
                    (section_id, title, time_str, 100 + item.hw_num, item.due_date, color),
                )
                inserted += 1
    return inserted, updated


def clear_section_homework(
    conn,
    section_id: int,
    assignment_ids: list[int],
) -> tuple[int, int]:
    if assignment_ids:
        placeholders = ",".join(["%s"] * len(assignment_ids))
        due_sql = (
            "DELETE FROM assignment_section_due "
            f"WHERE section_id = %s AND assignment_id IN ({placeholders})"
        )
        due_params: list[Any] = [section_id, *assignment_ids]
    else:
        due_sql = "DELETE FROM assignment_section_due WHERE section_id = %s"
        due_params = [section_id]
    with conn.cursor() as cur:
        cur.execute(due_sql, due_params)
        due_deleted = cur.rowcount
        cur.execute(
            """
            DELETE FROM section_events
            WHERE section_id = %s
              AND title REGEXP '^Homework [0-9]+ due$'
            """,
            (section_id,),
        )
        events_deleted = cur.rowcount
    return int(due_deleted), int(events_deleted)


def hydrate_google_env_from_processes() -> None:
    needed = [key for key in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET") if not os.environ.get(key)]
    if not needed:
        return
    proc_root = Path("/proc")
    uid = os.getuid()
    for path in proc_root.iterdir():
        if not path.name.isdigit():
            continue
        try:
            if path.stat().st_uid != uid:
                continue
            raw = (path / "environ").read_bytes()
        except Exception:
            continue
        for chunk in raw.split(b"\0"):
            if b"=" not in chunk:
                continue
            key_b, value_b = chunk.split(b"=", 1)
            key = key_b.decode(errors="ignore")
            if key in needed and value_b:
                os.environ[key] = value_b.decode(errors="ignore")
        needed = [key for key in needed if not os.environ.get(key)]
        if not needed:
            return


def google_service(require_write: bool):
    hydrate_google_env_from_processes()
    from agent_skills import calendar_tools

    return calendar_tools._service(require_write=require_write)


def google_window_bounds(window: str, timezone_name: str) -> tuple[dt.datetime, dt.datetime]:
    if ":" not in window:
        raise ValueError("Google deletion window must be START:END, for example 2026-01-01:2026-05-15")
    start_s, end_s = window.split(":", 1)
    tz = ZoneInfo(timezone_name)
    start = dt.datetime.combine(dt.date.fromisoformat(start_s), dt.time.min, tzinfo=tz)
    end = dt.datetime.combine(dt.date.fromisoformat(end_s), dt.time.min, tzinfo=tz)
    return start, end


def to_google_utc(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def list_google_homework_events(
    service,
    start: dt.datetime,
    end: dt.datetime,
    query_prefix: str,
) -> list[dict[str, Any]]:
    resp = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=to_google_utc(start),
            timeMax=to_google_utc(end),
            q=query_prefix,
            singleEvents=True,
            orderBy="startTime",
            maxResults=2500,
        )
        .execute()
    )
    return [
        event
        for event in resp.get("items", [])
        if str(event.get("summary", "")).startswith(query_prefix)
    ]


def delete_google_events(service, events: list[dict[str, Any]]) -> int:
    deleted = 0
    for event in events:
        service.events().delete(calendarId="primary", eventId=event["id"]).execute()
        deleted += 1
    return deleted


def create_google_homework_events(
    service,
    section: SectionInfo,
    plan: list[HomeworkPlan],
    query_prefix: str,
) -> int:
    existing_start = min(item.due_local for item in plan) - dt.timedelta(days=1)
    existing_end = max(item.due_local for item in plan) + dt.timedelta(days=2)
    existing = list_google_homework_events(service, existing_start, existing_end, query_prefix)
    existing_keys = {
        (
            str(event.get("summary", "")),
            str(event.get("start", {}).get("dateTime", ""))[:10],
        )
        for event in existing
    }
    created = 0
    for item in plan:
        summary = f"{query_prefix} {item.hw_num} due"
        key = (summary, item.due_date.isoformat())
        if key in existing_keys:
            continue
        body = {
            "summary": summary,
            "description": f"{section.name}: Homework {item.hw_num} due date",
            "start": {
                "dateTime": item.due_local.replace(tzinfo=None).isoformat(timespec="seconds"),
                "timeZone": section.timezone_name,
            },
            "end": {
                "dateTime": (item.due_local + dt.timedelta(minutes=15))
                .replace(tzinfo=None)
                .isoformat(timespec="seconds"),
                "timeZone": section.timezone_name,
            },
        }
        service.events().insert(calendarId="primary", body=body).execute()
        created += 1
    return created


def print_summary(
    section: SectionInfo,
    class_events: list[dict[str, Any]],
    holiday_rows: list[dict[str, Any]],
    class_days: list[dt.date],
    plan: list[HomeworkPlan],
    exam_lines: list[str],
    existing_due: dict[int, dict[str, Any]],
    apply: bool,
) -> None:
    mode = "APPLY" if apply else "DRY RUN"
    print(f"Mode: {mode}")
    print(
        f"Section: {section.id} {section.name} "
        f"({section.starts_on.isoformat()} to {section.ends_on.isoformat()}, {section.timezone_name})"
    )
    print("Recurring class-day events:")
    for event in class_events:
        print(f"  - {event['id']}: {event['title']} [{event['days']}] {event.get('time_str') or ''}")
    print("Holidays:")
    if holiday_rows:
        for row in holiday_rows:
            print(
                f"  - {row['label']}: "
                f"{format_date_range(as_date(row['starts_on']), as_date(row['ends_on']))}"
            )
    else:
        print("  - none")
    preview = ", ".join(f"Day {i + 1}={day.isoformat()}" for i, day in enumerate(class_days[:30]))
    print(f"Generated {len(class_days)} class days:")
    print(f"  {preview}")
    print("Homework plan:")
    for item in plan:
        existing = existing_due.get(item.assignment_id)
        old = existing["due_at"].isoformat(sep=" ") if existing and existing.get("due_at") else "none"
        print(
            f"  - HW{item.hw_num}: Day {item.day_num} = {item.due_date.isoformat()}, "
            f"due {item.due_local.strftime('%Y-%m-%d %H:%M %Z')}, "
            f"assignment {item.assignment_id} {item.assignment_title!r}, previous UTC {old}"
        )
    print("Exam anchors:")
    if exam_lines:
        for line in exam_lines:
            print(f"  - {line}")
    else:
        print("  - no exam mapping supplied")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Map DS3000 Daily Course Schedule day numbers to homework due dates."
    )
    parser.add_argument("--section-id", type=int, required=True, help="target class.id / section_id")
    parser.add_argument("--homework-days", default=DEFAULT_HOMEWORK_DAYS, help="mapping like 1:3,2:5")
    parser.add_argument("--exam-days", default=DEFAULT_EXAM_DAYS, help="mapping like 1:10,2:20")
    parser.add_argument("--due-time", default=DEFAULT_DUE_TIME, help="local due time HH:MM")
    parser.add_argument("--event-color", default=DEFAULT_EVENT_COLOR)
    parser.add_argument("--clear-section-id", type=int, action="append", default=[])
    parser.add_argument("--apply", action="store_true", help="write app database changes")
    parser.add_argument("--sync-google", action="store_true", help="sync Google Calendar homework events")
    parser.add_argument(
        "--delete-google-window",
        help="with --sync-google, delete matching homework events in START:END date window",
    )
    parser.add_argument("--google-prefix", default=DEFAULT_GOOGLE_PREFIX)
    args = parser.parse_args()

    homework_days = parse_mapping(args.homework_days)
    exam_days = parse_mapping(args.exam_days) if args.exam_days.strip() else {}
    due_time = parse_time(args.due_time)

    conn = db_connect()
    try:
        section = fetch_section(conn, args.section_id)
        holiday_rows = fetch_holidays(conn, section.id)
        holidays = holiday_dates(holiday_rows)
        class_events = fetch_recurring_class_events(conn, section.id)
        class_days = build_class_days(section, class_events, holidays)
        assignments = fetch_hw_assignments(conn, section.course_id, max(homework_days))
        plan = build_homework_plan(section, class_days, assignments, homework_days, due_time)
        exam_lines = check_exam_anchors(class_days, exam_days, fetch_exam_events(conn, section.id))
        existing_due = fetch_existing_due_rows(
            conn, section.id, [item.assignment_id for item in plan]
        )
        print_summary(
            section,
            class_events,
            holiday_rows,
            class_days,
            plan,
            exam_lines,
            existing_due,
            args.apply,
        )

        if not args.apply:
            if args.clear_section_id:
                print(f"Would clear old homework due rows/events for sections: {args.clear_section_id}")
            if args.sync_google:
                print("Would sync Google Calendar homework events.")
            return 0

        for clear_id in args.clear_section_id:
            due_deleted, events_deleted = clear_section_homework(
                conn, clear_id, [item.assignment_id for item in plan]
            )
            print(
                f"Cleared section {clear_id}: {due_deleted} due rows, "
                f"{events_deleted} app calendar homework events"
            )

        due_inserted, due_updated = upsert_due_rows(conn, section.id, plan)
        event_inserted, event_updated = upsert_app_homework_events(
            conn, section.id, plan, due_time, args.event_color
        )
        print(f"Upserted due rows: {due_inserted} inserted, {due_updated} updated")
        print(f"Upserted app homework events: {event_inserted} inserted, {event_updated} updated")

        if args.sync_google:
            svc = google_service(require_write=True)
            if args.delete_google_window:
                start, end = google_window_bounds(args.delete_google_window, section.timezone_name)
                old_events = list_google_homework_events(svc, start, end, args.google_prefix)
                deleted = delete_google_events(svc, old_events)
                print(
                    f"Deleted {deleted} Google Calendar events matching "
                    f"{args.google_prefix!r} in {args.delete_google_window}"
                )
            created = create_google_homework_events(svc, section, plan, args.google_prefix)
            print(f"Created {created} Google Calendar homework events")

        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
