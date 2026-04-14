import os
import shutil
import sys
import threading
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "src"))

os.chdir(_ROOT)

from ludens_flow.paths import get_logs_dir, get_state_file
from ludens_flow.state import (
    LudensState,
    StateConflictError,
    init_workspace,
    load_state,
    reset_current_project_state,
    save_state,
)


class StateStoreTests(unittest.TestCase):
    def setUp(self):
        self.previous_workspace = os.environ.get("LUDENS_WORKSPACE_DIR")
        self.previous_project = os.environ.get("LUDENS_PROJECT_ID")
        self.workspace_root = (_ROOT / "workspace_test_state_store").resolve()
        shutil.rmtree(self.workspace_root, ignore_errors=True)
        os.environ["LUDENS_WORKSPACE_DIR"] = str(self.workspace_root)
        os.environ.pop("LUDENS_PROJECT_ID", None)
        init_workspace()

    def tearDown(self):
        shutil.rmtree(self.workspace_root, ignore_errors=True)
        if self.previous_workspace is None:
            os.environ.pop("LUDENS_WORKSPACE_DIR", None)
        else:
            os.environ["LUDENS_WORKSPACE_DIR"] = self.previous_workspace

        if self.previous_project is None:
            os.environ.pop("LUDENS_PROJECT_ID", None)
        else:
            os.environ["LUDENS_PROJECT_ID"] = self.previous_project

    def test_revision_conflict_is_rejected(self):
        stale = load_state()
        fresh = load_state()

        fresh.phase = "PM_DISCUSS"
        save_state(fresh)
        self.assertEqual(fresh.revision, 1)

        stale.phase = "ENG_DISCUSS"
        with self.assertRaises(StateConflictError):
            save_state(stale)

    def test_reset_keeps_clean_state_and_no_leftover_lock(self):
        state = load_state()
        save_state(state)
        self.assertEqual(state.revision, 1)

        reset_state = reset_current_project_state(clear_images=False)
        self.assertEqual(reset_state.revision, 0)
        self.assertFalse(get_state_file().exists())

        lock_path = get_state_file().with_name(get_state_file().name + ".lock")
        self.assertFalse(lock_path.exists())

        audit_log = (get_logs_dir() / "audit.log").read_text(encoding="utf-8")
        self.assertIn("event=PROJECT_RESET", audit_log)

    def test_concurrent_stale_writes_conflict_without_corrupting_state(self):
        base = load_state()
        save_state(base)

        results = []
        result_lock = threading.Lock()

        def worker(index: int):
            local_copy = LudensState.from_dict(base.to_dict())
            local_copy.phase = "PM_DISCUSS" if index % 2 == 0 else "ENG_DISCUSS"
            try:
                save_state(local_copy)
                with result_lock:
                    results.append("saved")
            except StateConflictError:
                with result_lock:
                    results.append("conflict")

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(6)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertIn("saved", results)
        self.assertIn("conflict", results)

        final_state = load_state()
        self.assertGreaterEqual(final_state.revision, 2)


if __name__ == "__main__":
    unittest.main()
