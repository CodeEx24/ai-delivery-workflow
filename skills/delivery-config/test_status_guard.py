"""Tests for the ticket status guard. Run: python skills/delivery-config/test_status_guard.py"""
import io
import json
import os
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import status_guard as g  # noqa: E402

STATUSES = {
    "todo": "To Do",
    "inProgress": "In Progress",
    "inReview": "In Review",
    "testingStaging": "Testing (Staging)",
    "doneStaging": {"name": "DONE STAGING", "movedBy": "person", "when": "Only a tester, after QA passes"},
    "testingProduction": "Testing (Production)",
    "done": {"name": "Done", "movedBy": "person"},
}
TRANSITIONS = {"transitions": [
    {"id": "11", "name": "To Do", "to": {"name": "To Do"}},
    {"id": "21", "name": "In Progress", "to": {"name": "In Progress"}},
    {"id": "31", "name": "In Review", "to": {"name": "In Review"}},
    {"id": "41", "name": "Testing", "to": {"name": "Testing (Staging)"}},
    {"id": "51", "name": "Done staging", "to": {"name": "DONE STAGING"}},
    {"id": "99", "name": "Blocked", "to": {"name": "Blocked"}},
]}
TOOL = "mcp__claude_ai_Atlassian__"


class GuardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.repo = root / "product"
        (self.repo / "docs" / "workflow").mkdir(parents=True)
        (self.repo / ".engineering").mkdir()
        (self.repo / "docs" / "workflow" / "delivery.config.json").write_text(
            json.dumps({"schema": "delivery-config/1", "statuses": STATUSES}), encoding="utf-8")
        (self.repo / ".engineering" / "config.json").write_text(json.dumps({"ticketKeys": ["ABC"]}), encoding="utf-8")
        g.STATE_PATH = root / "state.json"
        os.environ.pop("CLAUDE_PROJECT_DIR", None)

    def tearDown(self):
        self.tmp.cleanup()

    def hook(self, phase, tool, tool_input, response=None, cwd=None):
        event = {"hook_event_name": phase, "tool_name": TOOL + tool, "tool_input": tool_input,
                 "cwd": str(cwd or self.repo)}
        if response is not None:
            # MCP results arrive as text blocks holding JSON.
            event["tool_response"] = [{"type": "text", "text": json.dumps(response)}]
        sys.stdin = io.StringIO(json.dumps(event))
        out = io.StringIO()
        with redirect_stdout(out):
            g.run_hook()
        sys.stdin = sys.__stdin__
        text = out.getvalue().strip()
        return json.loads(text)["hookSpecificOutput"]["permissionDecisionReason"] if text else None

    def read(self, key, status):
        self.hook("PostToolUse", "getTransitionsForJiraIssue", {"issueIdOrKey": key}, TRANSITIONS)
        self.hook("PostToolUse", "getJiraIssue", {"issueIdOrKey": key},
                  {"key": key, "id": "15778", "fields": {"status": {"name": status}}})

    def move(self, key, tid, cwd=None):
        reason = self.hook("PreToolUse", "transitionJiraIssue", {"issueIdOrKey": key, "transition": {"id": tid}},
                           cwd=cwd)
        if reason is None:
            self.hook("PostToolUse", "transitionJiraIssue", {"issueIdOrKey": key, "transition": {"id": tid}}, {})
        return reason

    def test_review_to_done_staging_refused(self):  # merged straight past testing
        self.read("ABC-370", "In Review")
        self.assertIn("Only a person", self.move("ABC-370", "51"))

    def test_in_progress_to_done_staging_refused(self):  # a QA fix merged while still In Progress
        self.read("ABC-369", "In Progress")
        self.assertIn("Only a person", self.move("ABC-369", "51"))

    def test_testing_to_done_staging_refused_for_agents(self):
        self.read("ABC-1", "Testing (Staging)")
        self.assertIn("Only a person", self.move("ABC-1", "51"))

    def test_merge_from_review_goes_to_testing(self):
        self.read("ABC-1", "In Review")
        self.assertIsNone(self.move("ABC-1", "41"))

    def test_merge_from_in_progress_skips_review(self):
        self.read("ABC-1", "In Progress")
        self.assertIn("skips 'In Review'", self.move("ABC-1", "41"))

    def test_one_step_at_a_time_works(self):
        self.read("ABC-1", "In Progress")
        self.assertIsNone(self.move("ABC-1", "31"))
        self.assertIsNone(self.move("ABC-1", "41"))

    def test_qa_failed_back_to_in_progress(self):
        self.read("ABC-1", "Testing (Staging)")
        self.assertIsNone(self.move("ABC-1", "21"))

    def test_back_to_review_refused(self):
        self.read("ABC-1", "Testing (Staging)")
        self.assertIn("back", self.move("ABC-1", "31"))

    def test_unknown_transition_needs_a_read(self):
        self.assertIn("getTransitionsForJiraIssue", self.move("ABC-2", "41"))

    def test_stale_status_needs_a_fresh_read(self):
        self.read("ABC-1", "In Review")
        state = g.load_state()
        state["current"]["ABC-1"]["at"] = time.time() - 3600
        g.save_state(state)
        self.assertIn("Read ABC-1 first", self.move("ABC-1", "41"))

    def test_unmapped_status_refused(self):
        self.read("ABC-1", "In Review")
        self.assertIn("not in this project's status mapping", self.move("ABC-1", "99"))

    def test_permit_allows_one_move_only(self):
        self.read("ABC-1", "Testing (Staging)")
        with redirect_stdout(io.StringIO()):
            g.cmd_permit("ABC-1", "DONE STAGING", "move ABC-1 to done staging please")
        self.assertIsNone(self.move("ABC-1", "51"))
        self.read("ABC-1", "Testing (Staging)")
        self.assertIn("Only a person", self.move("ABC-1", "51"))

    def test_finds_repo_from_workspace_root(self):
        self.read("ABC-1", "In Review")
        self.assertIn("Only a person", self.move("ABC-1", "51", cwd=self.repo.parent))
        self.assertIsNone(self.move("ABC-1", "41", cwd=self.repo.parent))

    def test_no_config_still_protects_done(self):
        empty = Path(self.tmp.name) / "elsewhere"
        empty.mkdir()
        self.read("XYZ-1", "In Review")
        self.assertIn("Only a person", self.move("XYZ-1", "51", cwd=empty))

    def test_install_is_idempotent(self):
        with redirect_stdout(io.StringIO()):
            g.cmd_install(self.repo)
            g.cmd_install(self.repo)
        data = json.loads((self.repo / ".claude" / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual(len(data["hooks"]["PreToolUse"]), 1)
        self.assertEqual(len(data["hooks"]["PostToolUse"]), 1)


if __name__ == "__main__":
    unittest.main()
