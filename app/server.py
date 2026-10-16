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

    secret_path = os.getenv("OPENAI_API_KEY_FILE") or str(ROOT / "openai.txt.txt")
    path = Path(secret_path)
    if path.exists() and not os.getenv("OPENAI_API_KEY"):
        lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip() and not line.strip().startswith("#")]
        for line in lines:
            if line.startswith("OPENAI_MODEL="):
                os.environ.setdefault("OPENAI_MODEL", line.split("=", 1)[1].strip().strip('"').strip("'"))
            elif line.startswith("OPENAI_API_KEY="):
                os.environ["OPENAI_API_KEY"] = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
            elif line.startswith("sk-"):
                os.environ["OPENAI_API_KEY"] = line
                break


load_local_env()


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


def mock_plan(tasks: list[dict[str, Any]], available_minutes: int) -> dict[str, Any]:
    ranked = sorted(tasks, key=lambda task: (-priority_score(task), tasks.index(task)))
    top = ranked[0]
    step_count = 3 if available_minutes >= 25 else 2
    base = max(1, available_minutes // step_count)
    steps = fit_steps([
        {"title": f"Review the requirements for {top['name']}", "minutes": base},
        {"title": f"Create a small working outline for {top['name']}", "minutes": base},
        {"title": f"Complete the next concrete piece of {top['name']}", "minutes": available_minutes},
    ], available_minutes, top["name"])
    return {
        "mode": "mock",
        "recommended_task": top,
        "summary": f"Start with {top['name']} because it has the strongest available priority signals.",
        "session_steps": steps,
        "total_minutes": sum(step["minutes"] for step in steps),
        "queue": [task for task in tasks if task["id"] != top["id"]],
        "uncertainties": ([f"Due date for {task['name']} is N/A." for task in tasks if task["due_date"] == "N/A"]
                          + [f"Effort for {task['name']} is N/A." for task in tasks if task["effort"] == "N/A"]),
    }


PLAN_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "summary": {"type": "string"},
        "ranked_task_ids": {"type": "array", "items": {"type": "string"}},
        "recommended_task_id": {"type": "string"},
        "next_steps": {"type": "array", "minItems": 1, "maxItems": 4, "items": {
            "type": "object", "additionalProperties": False,
            "properties": {"title": {"type": "string"}, "minutes": {"type": "integer", "minimum": 1}},
            "required": ["title", "minutes"],
        }},
        "uncertainties": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "ranked_task_ids", "recommended_task_id", "next_steps", "uncertainties"],
}


def extract_output_text(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]
    chunks: list[str] = []
    for item in payload.get("output", []):
        for content in item.get("content", []):
            if isinstance(content.get("text"), str):
                chunks.append(content["text"])
    return "".join(chunks)


def live_plan(tasks: list[dict[str, Any]], available_minutes: int, api_key: str) -> dict[str, Any]:
    body = {
        "model": os.getenv("OPENAI_MODEL", MODEL),
        "input": [
            {"role": "system", "content": (
                "You are a bounded study-planning assistant. Return only the supplied schema. "
                "Rank tasks using only supplied evidence. Treat N/A as unknown and never invent dates, effort, grades, "
                "or dependencies. Choose exactly one task and create next steps that fit the available minutes."
            )},
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
    ids = {task["id"] for task in tasks}
    top_id = result.get("recommended_task_id")
    if top_id not in ids:
        raise RuntimeError("OpenAI returned an unknown recommended task.")
    top = next(task for task in tasks if task["id"] == top_id)
    steps = fit_steps(result.get("next_steps", []), available_minutes, top["name"])
    return {
        "mode": "live", "recommended_task": top, "summary": str(result.get("summary", "")).strip(),
        "session_steps": steps, "total_minutes": sum(step["minutes"] for step in steps),
        "queue": [task for task in tasks if task["id"] != top_id],
        "uncertainties": [str(item) for item in result.get("uncertainties", [])],
    }


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
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if os.getenv("PLANNER_MODE", "").lower() == "mock" or not api_key:
        return mock_plan(tasks, available_minutes)
    return live_plan(tasks, available_minutes, api_key)


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
            live = os.getenv("OPENAI_API_KEY", "").strip() and os.getenv("PLANNER_MODE", "").lower() != "mock"
            self.json_response(HTTPStatus.OK, {"ok": True, "mode": "live" if live else "mock", "model": os.getenv("OPENAI_MODEL", MODEL)})
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
    live = os.getenv("OPENAI_API_KEY", "").strip() and os.getenv("PLANNER_MODE", "").lower() != "mock"
    print(f"Mode: {'live' if live else 'mock'}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Study Sprint Planner.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
