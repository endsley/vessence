# chieh_class_v2 DS3000 Scheduling Notes

Local app root: `/home/chieh/code/chieh_class_v2`.

Database helper: `/home/chieh/ambient/vessence/agent_skills/edu_homework_audit.py` exposes `db_connect()`, which connects to the `teaching_app` MySQL database through the local Cloud SQL proxy at `127.0.0.1:3307`.

Important tables:

- `class`: section rows. Use `id` as the section identifier for due dates.
- `assignments`: course-level assignment rows. DS3000 homework rows use `kind = 'hw'` and `assignment_type = 'module'`, then are ordered by `position, id`. In-class rows are also `kind = 'hw'` but use `assignment_type = 'extra_credit'`; do not set homework due dates on them.
- `assignment_section_due`: per-section homework due dates. Unique key is `(section_id, assignment_id)`.
- `section_events`: app calendar events. Recurring class-day rows have `auto_increment = 1` and `specific_date IS NULL`. Homework due events are one-off rows with `specific_date` set.
- `section_holidays`: no-class date ranges. Ranges are inclusive.

Known DS3000 Daily Course Schedule mapping from the 2026 Course Daily Topics document:

```text
HW1 Day 3
HW2 Day 5
HW3 Day 7
HW4 Day 9
HW5 Day 13
HW6 Day 15
HW7 Day 17
HW8 Day 19
HW9 Day 23
HW10 Day 25
Exam 1 Day 10
Exam 2 Day 20
```

Fall 2026 active section observed during setup:

- `class.id = 36`
- `course_number = DS3000`
- `semester_year = F26`
- `section_id = 3-8-9`
- term starts `2026-09-09`
- term ends `2026-12-20`
- recurring class days Tuesday and Friday
- existing exam events on `2026-10-13` and `2026-11-17`

Spring 2026 section previously used:

- `class.id = 33`
- code `DS3000-S26`

When setting future semesters, re-read the live database instead of relying on these historical IDs.
