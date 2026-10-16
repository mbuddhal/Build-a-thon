from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from datetime import date, datetime
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"
FIXTURE_PATH = ROOT / "data" / "tasks.example.json"
MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
API_URL = "https://api.openai.com/v1/responses"
CLAUDE_MODEL = os.getenv("ANTHROPIC_MODEL", os.getenv("CLAUDE_MODEL", "claude-haiku-5-5"))
CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"


def load_local_env() -> None:
    """Load ignored .env files and the explicitly supplied secret file silently."""
    for path in (ROOT / ".env", ROOT.parent / ".env"):
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            value = value.strip().strip('"').strip("'")
            if key.strip() and key.strip() not in os.environ:
                os.environ[key.strip()] = value

    secret_files = [
        (os.getenv("OPENAI_API_KEY_FILE") or str(ROOT / "openai.txt.txt"), "OPENAI_API_KEY", "OPENAI_MODEL"),
        (os.getenv("ANTHROPIC_API_KEY_FILE") or str(ROOT / "claude.txt.txt"), "ANTHROPIC_API_KEY", "ANTHROPIC_MODEL"),
    ]
    for secret_path, key_name, model_name in secret_files:
        path = Path(secret_path)
        if not path.exists() or os.getenv(key_name):
            continue
        lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip() and not line.strip().startswith("#")]
        for line in lines:
            if "=" in line:
                name, value = line.split("=", 1)
                name = name.strip()
                value = value.strip().strip('"').strip("'")
                if name == model_name:
                    os.environ.setdefault(model_name, value)
                elif name == key_name and value:
                    os.environ[key_name] = value
                    break
            elif key_name == "OPENAI_API_KEY" and line.startswith("sk-"):
                os.environ[key_name] = line
                break
            elif key_name == "ANTHROPIC_API_KEY" and line.startswith("sk-ant-"):
                os.environ[key_name] = line
                break


load_local_env()


def provider_config() -> tuple[str, str, str]:
    requested = os.getenv("PLANNER_PROVIDER", "").strip().lower()
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    if requested in {"anthropic", "claude"} and anthropic_key:
        return "anthropic", anthropic_key, os.getenv("ANTHROPIC_MODEL", CLAUDE_MODEL)
    if requested == "openai" and openai_key:
        return "openai", openai_key, os.getenv("OPENAI_MODEL", MODEL)
    if anthropic_key:
        return "anthropic", anthropic_key, os.getenv("ANTHROPIC_MODEL", CLAUDE_MODEL)
    if openai_key:
        return "openai", openai_key, os.getenv("OPENAI_MODEL", MODEL)
    return "mock", "", ""


def slugify(value: str, index: int) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return f"{slug or 'task'}-{index + 1}"


def normalize_tasks(raw_tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    for index, raw in enumerate(raw_tasks):
        name = str(raw.get("name", "")).strip()
        if not name:
            continue
        task_id = str(raw.get("id") or slugify(name, index)).strip()
        if task_id in used_ids:
            task_id = f"{task_id}-{index + 1}"
        used_ids.add(task_id)
        tasks.append({
            "id": task_id,
            "name": name,
            "due_date": str(raw.get("due_date") or "N/A").strip() or "N/A",
            "effort": str(raw.get("effort") or "N/A").strip() or "N/A",
            "importance": str(raw.get("importance") or "N/A").strip() or "N/A",
            "dependencies": str(raw.get("dependencies") or "N/A").strip() or "N/A",
        })
    return tasks


def parse_due_score(value: str) -> int:
    if value == "N/A":
        return 0
    try:
        days = (datetime.strptime(value, "%Y-%m-%d").date() - date.today()).days
    except ValueError:
        return 0
    if days < 0:
        return 40
    if days <= 2:
        return 35
    if days <= 7:
        return 25
    if days <= 14:
        return 15
    return 5


def priority_score(task: dict[str, Any]) -> int:
    importance = {"high": 30, "medium": 20, "low": 10}.get(task["importance"].lower(), 0)
    dependency_score = 5 if task["dependencies"] != "N/A" else 0
    return importance + parse_due_score(task["due_date"]) + dependency_score


def fit_steps(steps: list[dict[str, Any]], available_minutes: int, task_name: str) -> list[dict[str, Any]]:
    if available_minutes <= 0:
        return []
    fitted: list[dict[str, Any]] = []
    remaining = available_minutes
    for index, step in enumerate(steps[:4]):
        title = str(step.get("title", "")).strip() or f"Make progress on {task_name}"
        try:
            minutes = max(1, int(step.get("minutes", 1)))
        except (TypeError, ValueError):
            minutes = 1
        if remaining <= 0:
            break
        minutes = min(minutes, remaining)
        fitted.append({"title": title, "minutes": minutes, "order": index + 1})
        remaining -= minutes
    if not fitted:
        fitted.append({"title": f"Make progress on {task_name}", "minutes": available_minutes, "order": 1})
    return fitted


def parse_effort_minutes(value: str) -> int | None:
    if value == "N/A":
        return None
    match = re.search(r"(\d+(?:\.\d+)?)\s*(hour|hr|h|minute|min|m)?", value.lower())
    if not match:
        return None
    amount = float(match.group(1))
    unit = match.group(2) or "min"
    if unit in {"hour", "hr", "h"}:
        amount *= 60
    return max(1, int(round(amount)))


def fit_text_steps(step_titles: list[str], available_minutes: int, task_name: str) -> list[dict[str, Any]]:
    titles = [str(title).strip() for title in step_titles if str(title).strip()][:4]
    if not titles:
        titles = task_specific_steps({"name": task_name, "dependencies": "N/A"})
    step_count = min(len(titles), 4)
    base = max(1, available_minutes // step_count)
    return fit_steps([
        *({"title": title, "minutes": base} for title in titles[:step_count - 1]),
        {"title": titles[step_count - 1], "minutes": available_minutes},
    ], available_minutes, task_name)


def task_specific_steps(task: dict[str, Any]) -> list[str]:
    """Return a concrete strategy for the task type instead of repeating generic planning language."""
    text = f"{task['name']} {task['dependencies']}".lower()
    if any(word in text for word in ("midterm", "exam", "test", "quiz")):
        return [
            "List the chapters or topics covered and mark the two least-confident areas",
            "Review chapter notes for those areas and write a one-page concept summary",
            "Complete a short practice test without notes and check every missed question",
            "Make flashcards for missed concepts, formulas, and vocabulary",
        ]
    if any(word in text for word in ("paper", "essay", "report", "research", "outline")):
        return [
            "Read the prompt and highlight the required question, evidence, and format",
            "Turn the prompt into a three-part outline with a working claim",
            "Gather the strongest course sources or notes for each outline section",
            "Draft the opening section and leave placeholders for any missing evidence",
        ]
    if any(word in text for word in ("discussion", "post", "reflection")):
        return [
            "Highlight the discussion question and identify the course concept it tests",
            "Pull one specific example from the reading or lecture notes",
            "Draft a direct answer with the example and one explanation",
            "Add a question or connection that can invite a classmate response",
        ]
    if any(word in text for word in ("homework", "problem", "practice", "worksheet")):
        return [
            "Read the instructions and identify the problem types or skills required",
            "Work one representative problem with notes open, showing each step",
            "Try a second problem without notes and flag where the method breaks down",
            "Write a short error checklist for the remaining problems",
        ]
    return [
        "Open the instructions and highlight the required deliverable",
        "Gather the notes, readings, or materials needed to begin",
        "Complete the smallest concrete piece of the assignment",
        "Write down the next unfinished piece so restarting is easy",
    ]


def queue_with_previews(tasks: list[dict[str, Any]], scheduled_ids: set[str], previews: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    preview_map = {
        str(item.get("task_id")): [str(step) for step in item.get("steps", []) if str(step).strip()]
        for item in (previews or [])
        if item.get("task_id")
    }
    queue = []
    for task in tasks:
        if task["id"] in scheduled_ids:
            continue
        item = dict(task)
        item["next_steps"] = preview_map.get(task["id"]) or task_specific_steps(task)
        queue.append(item)
    return queue


def next_session_task(tasks: list[dict[str, Any]], schedule: list[dict[str, Any]], queue: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Choose the highest-priority task with work left after the current session."""
    allocated = {
        block["task"]["id"]: sum(
            item.get("minutes", 0) for item in schedule if item["task"]["id"] == block["task"]["id"]
        )
        for block in schedule
    }
    queue_ids = {task["id"] for task in queue}
    candidates: list[dict[str, Any]] = []
    for task in tasks:
        effort = parse_effort_minutes(task["effort"])
        task_allocated = allocated.get(task["id"], 0)
        remaining = effort - task_allocated if effort is not None else None
        if task["id"] in queue_ids or (remaining is not None and remaining > 0):
            candidate = dict(task)
            if remaining is not None and remaining > 0:
                candidate["remaining_minutes"] = remaining
            candidates.append(candidate)
    return max(candidates, key=priority_score) if candidates else None


def schedule_tasks(tasks: list[dict[str, Any]], available_minutes: int, requested_blocks: list[dict[str, Any]] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ranked = sorted(tasks, key=lambda task: (-priority_score(task), tasks.index(task)))
    by_id = {task["id"]: task for task in tasks}
    blocks = requested_blocks or [{"task_id": task["id"], "minutes": parse_effort_minutes(task["effort"]), "steps": task_specific_steps(task)} for task in ranked]
    scheduled: list[dict[str, Any]] = []
    scheduled_ids: set[str] = set()
    remaining = available_minutes
    for block in blocks:
        task_id = str(block.get("task_id", ""))
        task = by_id.get(task_id)
        if not task or task_id in scheduled_ids or remaining <= 0:
            continue
        requested = block.get("minutes")
        try:
            target = int(requested) if requested is not None else (parse_effort_minutes(task["effort"]) or 20)
        except (TypeError, ValueError):
            target = parse_effort_minutes(task["effort"]) or 20
        minutes = min(max(1, target), remaining)
        titles = block.get("steps") or task_specific_steps(task)
        scheduled.append({"task": task, "minutes": minutes, "steps": fit_text_steps(titles, minutes, task["name"])})
        scheduled_ids.add(task_id)
        remaining -= minutes
    if requested_blocks:
        for task in ranked:
            if task["id"] in scheduled_ids or remaining <= 0:
                continue
            target = parse_effort_minutes(task["effort"]) or max(15, remaining // max(1, len(ranked) - len(scheduled_ids)))
            minutes = min(target, remaining)
            scheduled.append({"task": task, "minutes": minutes, "steps": fit_text_steps(task_specific_steps(task), minutes, task["name"])})
            scheduled_ids.add(task["id"])
            remaining -= minutes
    queue = queue_with_previews(tasks, scheduled_ids)
    return scheduled, queue


def estimate_total_minutes(tasks: list[dict[str, Any]], model_estimate: Any = None) -> int:
    """Estimate the complete workload, using model output when valid and a modest fallback for N/A effort."""
    try:
        estimate = int(model_estimate)
    except (TypeError, ValueError):
        estimate = 0
    if estimate > 0:
        return estimate
    return sum(parse_effort_minutes(task["effort"]) or 20 for task in tasks)


def mock_plan(tasks: list[dict[str, Any]], available_minutes: int) -> dict[str, Any]:
    schedule, queue = schedule_tasks(tasks, available_minutes)
    estimated_total = estimate_total_minutes(tasks)
    return {
        "mode": "mock",
        "provider": "mock",
        "summary": "Use this study block across assignments in priority order; importance and urgency decide the order, while effort helps determine each time allocation.",
        "schedule": schedule,
        "total_minutes": sum(block["minutes"] for block in schedule),
        "unused_minutes": max(0, available_minutes - sum(block["minutes"] for block in schedule)),
        "estimated_total_minutes": estimated_total,
        "overage_minutes": max(0, estimated_total - available_minutes),
        "queue": queue,
        "next_session_task": next_session_task(tasks, schedule, queue),
        "uncertainties": ([f"Due date for {task['name']} is N/A." for task in tasks if task["due_date"] == "N/A"]
                          + [f"Effort for {task['name']} is N/A." for task in tasks if task["effort"] == "N/A"]),
    }


PLAN_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "summary": {"type": "string"},
        "ranked_task_ids": {"type": "array", "items": {"type": "string"}},
        "estimated_total_minutes": {"type": "integer", "minimum": 1},
        "schedule": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "properties": {"task_id": {"type": "string"}, "minutes": {"type": "integer", "minimum": 1}, "steps": {"type": "array", "items": {"type": "string"}}},
            "required": ["task_id", "minutes", "steps"],
        }},
        "queue_previews": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "properties": {"task_id": {"type": "string"}, "steps": {"type": "array", "items": {"type": "string"}}},
            "required": ["task_id", "steps"],
        }},
        "uncertainties": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "ranked_task_ids", "estimated_total_minutes", "schedule", "queue_previews", "uncertainties"],
}


CLAUDE_PLAN_SCHEMA = json.loads(json.dumps(PLAN_SCHEMA))
CLAUDE_PLAN_SCHEMA["properties"]["estimated_total_minutes"].pop("minimum", None)
CLAUDE_PLAN_SCHEMA["properties"]["schedule"]["items"]["properties"]["minutes"].pop("minimum", None)


def extract_output_text(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]
    chunks: list[str] = []
    for item in payload.get("output", []):
        for content in item.get("content", []):
            if isinstance(content.get("text"), str):
                chunks.append(content["text"])
    return "".join(chunks)


def planning_prompt() -> str:
    return (
        "You are a bounded study-planning assistant. Return only the supplied schema. "
        "Rank tasks using only supplied evidence. Treat N/A as unknown and never invent dates, effort, grades, "
        "or dependencies. Estimate the total minutes required for the complete workload, including reasonable "
        "estimates for tasks whose effort is N/A. Build a multi-assignment schedule for the available minutes, ordered by priority. Use "
        "importance and urgency to order work, and use effort estimates to decide how much time each block needs. "
        "Make each assignment's steps specific to its ambiguity: for an exam or midterm, use study actions such as reviewing chapter notes, doing a practice "
        "test, and making flashcards; for writing, use prompt analysis, outlining, evidence gathering, and drafting; "
        "for discussion work, use question analysis, course evidence, drafting, and a response prompt. "
        "Also provide concrete preview steps for every queued task. Keep the schedule total within the session minutes."
    )


def finalize_live_plan(tasks: list[dict[str, Any]], available_minutes: int, result: dict[str, Any], provider: str) -> dict[str, Any]:
    schedule, queue = schedule_tasks(tasks, available_minutes, result.get("schedule", []))
    total_minutes = sum(block["minutes"] for block in schedule)
    estimated_total = estimate_total_minutes(tasks, result.get("estimated_total_minutes"))
    queue = queue_with_previews(tasks, {block["task"]["id"] for block in schedule}, result.get("queue_previews", []))
    return {
        "mode": "live", "provider": provider,
        "summary": str(result.get("summary", "")).strip(),
        "schedule": schedule, "total_minutes": total_minutes,
        "unused_minutes": max(0, available_minutes - total_minutes),
        "estimated_total_minutes": estimated_total,
        "overage_minutes": max(0, estimated_total - available_minutes),
        "queue": queue,
        "next_session_task": next_session_task(tasks, schedule, queue),
        "uncertainties": [str(item) for item in result.get("uncertainties", [])],
    }


def live_plan_openai(tasks: list[dict[str, Any]], available_minutes: int, api_key: str, model: str) -> dict[str, Any]:
    body = {
        "model": model,
        "input": [
            {"role": "system", "content": planning_prompt()},
            {"role": "user", "content": json.dumps({"available_minutes": available_minutes, "tasks": tasks}, indent=2)},
        ],
        "text": {"format": {"type": "json_schema", "name": "study_plan", "strict": True, "schema": PLAN_SCHEMA}},
    }
    request = urllib.request.Request(API_URL, data=json.dumps(body).encode("utf-8"), headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {api_key}"
    }, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"OpenAI request failed ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"OpenAI connection failed: {exc.reason}") from exc
    text = extract_output_text(payload)
    if not text:
        raise RuntimeError("OpenAI returned no structured plan.")
    try:
        result = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("OpenAI returned invalid JSON.") from exc
    return finalize_live_plan(tasks, available_minutes, result, "openai")


def extract_anthropic_text(payload: dict[str, Any]) -> str:
    chunks = [block.get("text", "") for block in payload.get("content", []) if block.get("type") == "text"]
    return "".join(chunk for chunk in chunks if isinstance(chunk, str))


def live_plan_anthropic(tasks: list[dict[str, Any]], available_minutes: int, api_key: str, model: str) -> dict[str, Any]:
    body = {
        "model": model,
        "max_tokens": 1400,
        "system": planning_prompt(),
        "messages": [{"role": "user", "content": json.dumps({"available_minutes": available_minutes, "tasks": tasks}, indent=2)}],
        "output_config": {"format": {"type": "json_schema", "schema": CLAUDE_PLAN_SCHEMA}},
    }
    request = urllib.request.Request(CLAUDE_API_URL, data=json.dumps(body).encode("utf-8"), headers={
        "Content-Type": "application/json", "x-api-key": api_key, "anthropic-version": "2023-06-01"
    }, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"Claude request failed ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Claude connection failed: {exc.reason}") from exc
    text = extract_anthropic_text(payload)
    if not text:
        raise RuntimeError("Claude returned no structured plan.")
    try:
        result = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Claude returned invalid JSON.") from exc
    return finalize_live_plan(tasks, available_minutes, result, "anthropic")


def live_plan(tasks: list[dict[str, Any]], available_minutes: int, api_key: str) -> dict[str, Any]:
    """Backward-compatible OpenAI adapter for local callers and older tests."""
    return live_plan_openai(tasks, available_minutes, api_key, os.getenv("OPENAI_MODEL", MODEL))


def make_plan(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        available_minutes = int(payload.get("available_minutes", 0))
    except (TypeError, ValueError) as exc:
        raise ValueError("Available study time must be a whole number of minutes.") from exc
    if available_minutes <= 0 or available_minutes > 1440:
        raise ValueError("Available study time must be between 1 and 1440 minutes.")
    tasks = normalize_tasks(payload.get("tasks", []))
    if not tasks:
        raise ValueError("Add at least one assignment with a name.")
    provider, api_key, model = provider_config()
    if os.getenv("PLANNER_MODE", "").lower() == "mock" or not api_key:
        return mock_plan(tasks, available_minutes)
    if provider == "anthropic":
        return live_plan_anthropic(tasks, available_minutes, api_key, model)
    return live_plan_openai(tasks, available_minutes, api_key, model)


class PlannerHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(STATIC), **kwargs)

    def json_response(self, status: int, body: dict[str, Any]) -> None:
        encoded = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:
        if self.path == "/api/health":
            provider, _, model = provider_config()
            live = provider != "mock" and os.getenv("PLANNER_MODE", "").lower() != "mock"
            self.json_response(HTTPStatus.OK, {"ok": True, "mode": "live" if live else "mock", "provider": provider, "model": model or MODEL})
            return
        if self.path == "/api/fixture":
            self.json_response(HTTPStatus.OK, json.loads(FIXTURE_PATH.read_text(encoding="utf-8")))
            return
        super().do_GET()

    def do_POST(self) -> None:
        if self.path != "/api/plan":
            self.json_response(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            self.json_response(HTTPStatus.OK, make_plan(payload))
        except ValueError as exc:
            self.json_response(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except RuntimeError as exc:
            self.json_response(HTTPStatus.BAD_GATEWAY, {"error": str(exc)})
        except Exception as exc:
            self.json_response(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"Planner error: {exc}"})


def main() -> None:
    port = int(os.getenv("PORT", "8000"))
    server = ThreadingHTTPServer(("127.0.0.1", port), PlannerHandler)
    print(f"Study Sprint Planner running at http://127.0.0.1:{port}")
    provider, _, _ = provider_config()
    live = provider != "mock" and os.getenv("PLANNER_MODE", "").lower() != "mock"
    print(f"Mode: {'live' if live else 'mock'} ({provider})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Study Sprint Planner.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
