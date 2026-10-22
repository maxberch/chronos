"""Unit tests for Chronos DAG, replay caching, and branching (zero-dependency unittest)."""

import os
import tempfile
import unittest
from chronos.models import EventType
from chronos.tracer import ChronosSession
from chronos.storage import ChronosStore


class TestChronosCore(unittest.TestCase):
    def setUp(self):
        self.fd, self.temp_db = tempfile.mkstemp(suffix=".db")
        os.close(self.fd)

    def tearDown(self):
        if os.path.exists(self.temp_db):
            os.remove(self.temp_db)

    def test_record_and_replay_cache(self):
        # 1. First run: record 3 steps
        session1 = ChronosSession(run_name="test-run", db_path=self.temp_db)

        # Step 1
        out1 = session1.step(
            name="fetch_webpage",
            event_type=EventType.TOOL,
            inputs={"url": "https://example.com"},
            fn=lambda: "<html>Example Content</html>"
        )
        self.assertEqual(out1, "<html>Example Content</html>")
        chk1_id = session1.parent_checkpoint_id

        # Step 2
        out2 = session1.step(
            name="extract_entities",
            event_type=EventType.LLM,
            inputs={"text": out1, "model": "gemini-flash"},
            fn=lambda: {"entities": ["Example Corp", "Tech"]}
        )
        self.assertEqual(out2["entities"], ["Example Corp", "Tech"])
        chk2_id = session1.parent_checkpoint_id

        # Step 3 (Simulated Failure)
        with self.assertRaises(ZeroDivisionError):
            session1.step(
                name="calculate_ratio",
                event_type=EventType.TOOL,
                inputs={"dividend": 100, "divisor": 0},
                fn=lambda: 100 / 0
            )
        chk3_fail_id = session1.parent_checkpoint_id

        # 2. Verify checkpoints stored
        store = ChronosStore(db_path=self.temp_db)
        chk2 = store.get_checkpoint(chk2_id)
        self.assertIsNotNone(chk2)
        self.assertEqual(chk2.event.name, "extract_entities")
        self.assertIsNone(chk2.event.error)

        chk3 = store.get_checkpoint(chk3_fail_id)
        self.assertIsNotNone(chk3)
        self.assertEqual(chk3.event.error, "division by zero")

        # 3. Fork from Step 2 to fix the bug (Rewind / Time-Travel)
        session2 = ChronosSession.fork(
            parent_checkpoint_id=chk2_id,
            new_branch_name="fix-ratio-calculation",
            db_path=self.temp_db
        )
        self.assertEqual(session2.mode, "REPLAY")
        self.assertEqual(len(session2.replay_queue), 2)  # Has Step 1 and Step 2 in history

        # Replay Step 1 (Identical inputs -> Cache Hit!)
        call_count_step1 = 0
        def real_step1_fn():
            nonlocal call_count_step1
            call_count_step1 += 1
            return "SHOULD NOT BE CALLED"

        replay_out1 = session2.step(
            name="fetch_webpage",
            event_type=EventType.TOOL,
            inputs={"url": "https://example.com"},
            fn=real_step1_fn
        )
        self.assertEqual(replay_out1, "<html>Example Content</html>")
        self.assertEqual(call_count_step1, 0)  # Proves function was NOT executed!

        # Replay Step 2 (Identical inputs -> Cache Hit!)
        replay_out2 = session2.step(
            name="extract_entities",
            event_type=EventType.LLM,
            inputs={"text": replay_out1, "model": "gemini-flash"},
            fn=lambda: {"entities": ["SHOULD NOT RUN"]}
        )
        self.assertEqual(replay_out2["entities"], ["Example Corp", "Tech"])

        # Step 3 with patched divisor (diverges -> live execution succeeds!)
        fixed_out3 = session2.step(
            name="calculate_ratio",
            event_type=EventType.TOOL,
            inputs={"dividend": 100, "divisor": 5},  # Fixed parameter!
            fn=lambda: 100 / 5
        )
        self.assertEqual(fixed_out3, 20.0)
        self.assertNotEqual(session2.parent_checkpoint_id, chk3_fail_id)


if __name__ == "__main__":
    unittest.main()
