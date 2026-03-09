import unittest

from backend.progress_tracker import ProgressTracker


class TestProgressTracker(unittest.TestCase):
    def setUp(self):
        self.tracker = ProgressTracker()

    def test_start_update_complete_lifecycle(self):
        task_id = "task-1"

        self.tracker.start_task(task_id)
        self.tracker.update(task_id, progress=40, step="Parsing", detail="file.py")
        self.tracker.set_metrics(task_id, total_functions=10, completed_functions=4)

        current = self.tracker.get_progress(task_id)
        self.assertEqual(current["status"], "started")
        self.assertEqual(current["progress"], 40)
        self.assertEqual(current["current_step"], "Parsing")
        self.assertEqual(current["metrics"]["remaining_functions"], 6)

        self.tracker.complete(task_id, success=True, message="Done")
        done = self.tracker.get_progress(task_id)
        self.assertEqual(done["status"], "completed")
        self.assertEqual(done["progress"], 100)
        self.assertEqual(done["current_step"], "Done")

    def test_cleanup_removes_task(self):
        task_id = "task-2"
        self.tracker.start_task(task_id)
        self.tracker.cleanup(task_id)
        self.assertIsNone(self.tracker.get_progress(task_id))


if __name__ == "__main__":
    unittest.main()
