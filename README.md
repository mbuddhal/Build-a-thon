# Study Sprint Planner

Local BUS4498 Mini AI Build-a-thon app for Option 2: turn an overwhelming study workload into concrete next steps.

## Run locally

From PowerShell:

```powershell
.\run.ps1
```

Then open <http://127.0.0.1:8000>.

The launcher checks for `OPENAI_API_KEY` in the process environment, `Build-a-thon\.env`, the parent course-resource folder `.env`, and the ignored local file `openai.txt.txt`. If no key is available, the app runs a clearly labeled deterministic demo mode so the interface and controller can be tested safely.

For live mode, use the supplied local secret file or an ignored `.env` file. Never commit `.env`, `openai.txt.txt`, or paste the key into chat. The live adapter calls the OpenAI Responses API with strict structured output; the local controller validates the recommended task, fits steps to the time limit, and constructs the remaining queue.

## Test

```powershell
$python = 'C:\Users\zoeyt\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $python -m unittest discover -s tests -v
```

## Workflow boundary

The app plans one current study session. It recommends exactly one top task, creates a time-bounded session plan, and lists every other assignment in an ordered queue. Missing due dates and effort estimates appear as `N/A`. It does not submit assignments, edit calendars, send messages, or manage the full semester.
