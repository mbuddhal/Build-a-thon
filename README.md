# StudyBloom · Study Sprint Planner

Local BUS4498 Mini AI Build-a-thon app for Option 2: turn an overwhelming study workload into concrete next steps.

## Run locally

From PowerShell:

```powershell
.\run.ps1
```

Then open <http://127.0.0.1:8000>.

The launcher checks for `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` in the process environment, `.env` files, and the ignored local files `claude.txt.txt` and `openai.txt.txt`. Claude is preferred when both providers are available; set `PLANNER_PROVIDER=openai` to choose OpenAI explicitly. If no key is available, the app runs a clearly labeled deterministic demo mode so the interface and controller can be tested safely.

For live mode, use the supplied local secret file or an ignored `.env` file. Never commit `.env`, `openai.txt.txt`, `claude.txt.txt`, or paste a key into chat. The live adapters use strict structured output through the OpenAI Responses API or Anthropic Messages API; the local controller validates the schedule, fits steps to the time limit, calculates workload overage, and constructs the remaining queue.

## Test

```powershell
$python = 'C:\Users\zoeyt\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $python -m unittest discover -s tests -v
```

## Workflow boundary

The app plans one current study session. It divides time across assignments by priority and effort, creates task-specific next moves, lets the student edit wording and minutes, and lets the student drag schedule blocks to change their order. Anything that does not fit appears in a grey later queue with an AI preview and the supplied details. Missing due dates and effort estimates appear as `N/A`; effort is optional and estimated for total-workload reporting. If work overflows, the app recommends the highest-priority unfinished task for the next session. It does not submit assignments, edit calendars, send messages, or manage the full semester.
