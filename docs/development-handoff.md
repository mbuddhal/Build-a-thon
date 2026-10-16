# Study Sprint Planner Development Handoff

## What is built

The app implements the bounded Option 2 workflow: a student enters available minutes and assignments, receives a priority-ordered multi-assignment schedule with task-specific study moves, and sees anything that does not fit in a grey later queue with its details and an AI preview. The schedule can be edited, time-boxed, and reordered with drag-and-drop or arrow controls. Missing due dates and effort estimates are displayed as `N/A`; effort is optional and estimated for workload reporting. The app reports overage and recommends the highest-priority unfinished task for the next session, including partial overflow.

## Run locally

From the repository root in PowerShell:

```powershell
.\run.ps1
```

Open `http://127.0.0.1:8000`. The launcher uses `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` from the process environment, local `.env` files, or ignored provider key files. Claude is preferred when both are present. If no key is found, the app uses deterministic mock mode so the UI remains demoable.

To force offline mode:

```powershell
$env:PLANNER_MODE = "mock"
.\run.ps1
```

## Architecture

- `app/server.py` is a standard-library Python backend with `/api/health`, `/api/fixture`, and `/api/plan`.
- `app/static/` contains the browser form, result renderer, and responsive styling.
- `data/tasks.example.json` is the synthetic demo fixture.
- `skills/study-planner/` contains the reusable workflow Skill and its UI metadata.
- `tests/test_planner.py` covers missing-value normalization, time fitting, queue previews, overage reporting, partial overflow, and empty input validation.

The backend uses strict JSON Schema output in live mode through either the OpenAI Responses API or Anthropic Messages API. Generated steps are still checked and fitted locally so the displayed total never exceeds the student's available time.

## Three-minute demo

1. Click **Load example**.
2. Use the default 45 minutes and click **Build my study plan**.
3. Point out the time split across assignments, plus task-specific moves such as chapter review, practice testing, and flashcards.
4. Edit a session step, move it with ↑/↓ or drag-and-drop, and save the plan.
5. Point out that unknown dates and effort appear as `N/A` rather than being invented, while the estimated total still reports a workload.
6. Show the overage message and next-session recommendation when the workload does not fit.
7. Change available time to 20 minutes and run again to show the plan shrinking.

## Verification completed

- Python unit tests pass.
- Python compilation passes.
- `git diff --check` passes.
- The browser workflow was exercised with the example fixture.
- Live configuration detects the supplied model key without exposing it; a live network call may require local network access that is unavailable in a restricted sandbox.

## Explicit boundaries

The app does not submit assignments, edit calendars, send messages, research the web, or maintain a full-semester schedule. The student remains the final decision-maker.
