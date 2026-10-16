---
name: study-planner
description: "Turn a student's changing workload into a bounded multi-assignment study schedule with priority-based time blocks, concrete next steps, and an ordered queue of assignments that do not fit."
---

# Study Planner

Use this skill when a student has several assignments and wants a realistic schedule for one available study session. The goal is a reviewable multi-assignment schedule, not automatic submission, calendar management, or full-semester scheduling.

## Inputs

Collect:

- Available study minutes for the current session.
- One or more assignments with a name.
- Optional due date, effort estimate, importance, and dependency information.

Represent missing due dates and effort estimates as `N/A`. Do not invent them.

## Procedure

1. Validate that available minutes is a positive number and every assignment has a usable name.
2. Preserve the student's assignment order and identifiers.
3. Interpret the task descriptions and rank the workload using the available evidence: deadline, importance, effort, dependencies, and session time.
4. Allocate the available minutes across assignments in priority order. Use importance and urgency to order work, and use effort estimates to determine each block's size.
5. Break each scheduled assignment into two to four concrete, task-specific next steps that fit its allocated block.
6. Enforce the total time budget deterministically after model output; never trust generated arithmetic without checking it.
7. Put assignments that do not fit into an ordered later queue. Keep the last remaining assignment as the last queue entry, and show `N/A` for missing fields.
8. Explain the allocation logic and list uncertainties or missing information.
9. Report the estimated total workload and how many minutes exceed the current session, when applicable.
10. Recommend the highest-priority unfinished assignment as the starting point for the next study session, including a task that was only partially completed.
11. Let the student review, edit, reorder, and rerun the schedule.

## Output format

Return:

- `schedule`: ordered assignment blocks with minutes and two to four concrete next steps per block.
- `summary`: a short explanation of how time was allocated.
- `total_minutes`: the checked total, never greater than available minutes.
- `unused_minutes`: any available time not assigned to an estimate.
- `queue`: every assignment that did not fit, in display order.
- `estimated_total_minutes`: the model's estimate for the complete workload, including reasonable estimates for `N/A` effort.
- `overage_minutes`: estimated workload minutes beyond the current session, never negative.
- `next_session_task`: the highest-priority unfinished assignment, including partial overflow, or `null` when no work remains.
- `uncertainties`: missing or ambiguous information, using `N/A` where appropriate.

## Boundaries

- Do not submit assignments, edit calendars, send messages, or call external business tools.
- Do not fabricate deadlines, effort estimates, dependencies, grades, or task content.
- Treat model output as a proposal that the controller validates.
- If the model response is invalid, return a recoverable error or ask the student to revise the input; do not silently present an unvalidated plan.
- The student remains the final decision-maker.
