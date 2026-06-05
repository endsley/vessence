---
name: schedule-ds3000-homework
description: Use when Chieh asks to set, move, verify, or clear DS3000 homework due dates for a semester in the teaching app, especially from a Daily Course Schedule / Course Daily Topics document. Maps schedule day numbers to real class dates using the existing section calendar, holidays, and exam anchors, then updates assignment due dates and optional calendar events.
---

# Schedule DS3000 Homework

## What This Does

Use this skill when Chieh asks for DS3000 homework due dates to be set for a semester, moved from one semester to another, or checked against a Daily Course Schedule.

The workflow is:

1. Read the Daily Course Schedule / Course Daily Topics source.
2. Extract the course-day mapping, for example `HW1 -> Day 3` and `Exam 1 -> Day 10`.
3. Inspect the target DS3000 section calendar in `chieh_class_v2`.
4. Build the actual numbered class-day sequence from the section's recurring class-day events, term bounds, timezone, and `section_holidays`.
5. Verify exam day numbers against existing exam calendar events.
6. Dry-run the homework due-date mapping.
7. Apply the mapping to `assignment_section_due`, app calendar `section_events`, and optionally Google Calendar.

Do not guess dates from the academic calendar alone. The app calendar is the source of truth for class meetings and holidays.

## Trigger Phrases

Natural requests like these should use this skill:

- "Use the DS3000 scheduling skill to set Fall 2027 DS3000 homework due dates."
- "Read my DS3000 Daily Course Schedule and set the homework due dates."
- "Move the DS3000 homework due dates from Spring 2026 to Fall 2026."
- "Check the DS3000 homework due-date mapping against the calendar."
- "Clear the old DS3000 homework dates for one semester and set them for another."

## Required Checks

Before writing anything:

- Query Jane memory for DS3000 / teaching-app context.
- Identify the target `class.id` row. If multiple plausible active DS3000 rows exist, inspect names, term dates, recurring section events, and holidays. Ask Chieh only if the target remains ambiguous.
- Confirm the section has `term_starts_on`, `term_ends_on`, timezone, recurring auto-increment class-day `section_events`, and holidays.
- Confirm the DS3000 assignments exist as `assignments.kind = 'hw'` and `assignment_type = 'module'` for the section's `course_id`. Do not map due dates onto `In-class N` extra-credit rows.
- Run the bundled script without `--apply` and show the dry-run mapping before any write.

## Automation

Run the bundled script from the skill directory:

```bash
/home/chieh/google-adk-env/adk-venv/bin/python \
  /home/chieh/.codex/skills/schedule-ds3000-homework/scripts/schedule_ds3000_due_dates.py \
  --section-id 36 \
  --homework-days 1:3,2:5,3:7,4:9,5:13,6:15,7:17,8:19,9:23,10:25 \
  --exam-days 1:10,2:20
```

The default mode is a dry-run. It prints:

- target section metadata
- holidays used
- generated numbered class days
- homework due dates at the requested local due time
- exam anchor checks
- proposed database and calendar changes

To write app due dates and app calendar events:

```bash
/home/chieh/google-adk-env/adk-venv/bin/python \
  /home/chieh/.codex/skills/schedule-ds3000-homework/scripts/schedule_ds3000_due_dates.py \
  --section-id 36 \
  --homework-days 1:3,2:5,3:7,4:9,5:13,6:15,7:17,8:19,9:23,10:25 \
  --exam-days 1:10,2:20 \
  --apply
```

To move dates from an older section and sync Google Calendar homework events:

```bash
/home/chieh/google-adk-env/adk-venv/bin/python \
  /home/chieh/.codex/skills/schedule-ds3000-homework/scripts/schedule_ds3000_due_dates.py \
  --section-id 36 \
  --clear-section-id 33 \
  --delete-google-window 2026-01-01:2026-05-15 \
  --sync-google \
  --apply
```

Use `--sync-google` only when Chieh asks to update Google Calendar. Without it, the script writes only the teaching app.

## Rules

- Homework due time defaults to `21:00` local section time.
- `assignment_section_due.due_at` is stored as UTC-naive because that is how the app currently stores due rows.
- App calendar homework events are one-off `section_events` titled `Homework N due`, with `time_str = 'Due 9:00 PM'` and color `#b91c1c`.
- Exam entries are used as anchors. If the schedule says Exam 1 is Day 10 and the existing calendar has Exam 1 on another date, stop and report the mismatch unless Chieh explicitly asks to repair exam events.
- If moving a semester, clear only homework due rows and homework due app calendar events for the old section. Do not delete unrelated events.
- When syncing Google Calendar, delete only matching `DS3000 Homework` events inside the requested deletion window, then create missing target homework events.

## Reference

For local schema notes and known DS3000 conventions, read `references/chieh-class-v2.md` only when needed.
