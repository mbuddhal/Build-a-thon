import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from server import fit_steps, make_plan, normalize_tasks, task_specific_steps  # noqa: E402


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.raw_tasks = [
            {"name": "First assignment", "importance": "Low"},
            {"name": "Top assignment", "importance": "High"},
            {"name": "Final assignment", "importance": "N/A"},
        ]

    def test_missing_values_become_na(self):
        tasks = normalize_tasks(self.raw_tasks)
        self.assertEqual(tasks[0]["due_date"], "N/A")
        self.assertEqual(tasks[0]["effort"], "N/A")
        self.assertEqual(tasks[2]["importance"], "N/A")

    def test_fit_steps_never_exceeds_available_time(self):
        steps = fit_steps([{"title": "One", "minutes": 20}, {"title": "Two", "minutes": 20}], 25, "Example")
        self.assertEqual(sum(step["minutes"] for step in steps), 25)

    def test_mock_plan_allocates_time_by_priority_and_effort(self):
        previous_mode = os.environ.get("PLANNER_MODE")
        os.environ["PLANNER_MODE"] = "mock"
        try:
            plan = make_plan({"available_minutes": 60, "tasks": [
                {"name": "First assignment", "importance": "Low", "effort": "15 min"},
                {"name": "Top assignment", "importance": "High", "effort": "30 min"},
                {"name": "Final assignment", "importance": "N/A", "effort": "30 min"},
            ]})
        finally:
            if previous_mode is None:
                os.environ.pop("PLANNER_MODE", None)
            else:
                os.environ["PLANNER_MODE"] = previous_mode
        self.assertEqual([block["task"]["name"] for block in plan["schedule"]], ["Top assignment", "First assignment", "Final assignment"])
        self.assertEqual([block["minutes"] for block in plan["schedule"]], [30, 15, 15])
        self.assertLessEqual(plan["total_minutes"], 60)

    def test_midterm_plan_uses_task_specific_study_moves(self):
        task = normalize_tasks([{"name": "Study for midterm", "dependencies": "Chapters 1-4"}])[0]
        steps = task_specific_steps(task)
        joined = " ".join(steps).lower()
        self.assertIn("chapter notes", joined)
        self.assertIn("practice test", joined)
        self.assertIn("flashcards", joined)

    def test_queue_assignments_include_next_move_previews(self):
        previous_mode = os.environ.get("PLANNER_MODE")
        os.environ["PLANNER_MODE"] = "mock"
        try:
            plan = make_plan({"available_minutes": 20, "tasks": [
                {"name": "Study for midterm", "importance": "High", "effort": "45 min"},
                {"name": "Write discussion post", "importance": "Low", "effort": "30 min"},
            ]})
        finally:
            if previous_mode is None:
                os.environ.pop("PLANNER_MODE", None)
            else:
                os.environ["PLANNER_MODE"] = previous_mode
        self.assertEqual(len(plan["queue"]), 1)
        self.assertTrue(plan["queue"][0]["next_steps"])

    def test_empty_tasks_are_rejected(self):
        with self.assertRaises(ValueError):
            make_plan({"available_minutes": 30, "tasks": []})


if __name__ == "__main__":
    unittest.main()
