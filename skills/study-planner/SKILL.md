---
name: study-planner
description: "Turn a student's changing workload into a bounded study-session plan with one recommended task, concrete next steps, and an ordered queue of remaining assignments."
---

# Study Planner

Use this skill when a student has several assignments and wants a realistic plan for one available study session. The goal is a reviewable plan, not automatic submission, calendar management, or full-semester scheduling.

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
4. Select exactly one recommended task when at least one valid task exists.
5. Break the recommended task into two to four concrete next steps that fit within the current session.
6. Enforce the time budget deterministically after model output; never trust generated arithmetic without checking it.
7. Put every other assignment into an ordered queue. Keep the last remaining assignment as the last queue entry, and show `N/A` for missing fields.
8. Explain the recommendation and list uncertainties or missing information.
9. Let the student review, edit, and rerun the plan.

## Output format

Return:

- `recommended_task`: the one selected task.
- `summary`: a short reason for selecting it.
- `session_steps`: two to four actions with positive integer minute estimates.
- `total_minutes`: the checked total, never greater than available minutes.
- `queue`: every non-recommended assignment in display order.
- `uncertainties`: missing or ambiguous information, using `N/A` where appropriate.

## Boundaries

- Do not submit assignments, edit calendars, send messages, or call external business tools.
- Do not fabricate deadlines, effort estimates, dependencies, grades, or task content.
- Treat model output as a proposal that the controller validates.
- If the model response is invalid, return a recoverable error or ask the student to revise the input; do not silently present an unvalidated plan.
- The student remains the final decision-maker.
