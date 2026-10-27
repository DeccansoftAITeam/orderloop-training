"""Tests for scripts/ai_gate.py (the fail-closed AI review gate).

Run: python -m unittest discover -s scripts -p "test_ai_gate.py"

The gate reads the JSON that `claude -p --output-format json --json-schema ...`
prints. Exit codes: 0 approve, 1 changes requested, 2 anything else.
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

GATE = Path(__file__).resolve().parent / "ai_gate.py"


def result(structured=None, **over) -> dict:
    """A result object shaped like real `claude -p --output-format json` output."""
    base = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "num_turns": 1,
        "session_id": "00000000-0000-0000-0000-000000000000",
        "total_cost_usd": 0.05,
        "result": "",
        "terminal_reason": "completed",
    }
    if structured is not None:
        base["structured_output"] = structured
    base.update(over)
    return base


def run_gate(payload) -> int:
    data = payload if isinstance(payload, (str, bytes)) else json.dumps(payload)
    if isinstance(data, str):
        data = data.encode("utf-8")
    proc = subprocess.run([sys.executable, str(GATE)], input=data, capture_output=True, timeout=30)
    return proc.returncode


class GateTests(unittest.TestCase):
    def test_clean_approval_passes(self):
        self.assertEqual(run_gate(result({"verdict": "approve", "findings": []})), 0)

    def test_low_findings_do_not_block(self):
        findings = [{"severity": "low", "file": "a.py", "line": 1, "summary": "naming"}]
        self.assertEqual(run_gate(result({"verdict": "approve", "findings": findings})), 0)

    def test_changes_requested_fails_with_1(self):
        self.assertEqual(run_gate(result({"verdict": "changes_requested", "findings": []})), 1)

    def test_approve_with_a_high_finding_still_fails(self):
        findings = [{"severity": "high", "file": "a.py", "line": 3, "summary": "leak"}]
        self.assertEqual(run_gate(result({"verdict": "approve", "findings": findings})), 1)

    def test_error_result_fails_with_2(self):
        self.assertEqual(run_gate(result(None, is_error=True, subtype="error_max_turns")), 2)

    def test_budget_exhausted_fails_with_2(self):
        self.assertEqual(run_gate(result(None, is_error=True, subtype="error_max_budget_usd", result=None)), 2)

    def test_success_without_structured_output_fails_with_2(self):
        self.assertEqual(run_gate(result(None, result="Looks fine to me")), 2)

    def test_unknown_verdict_fails_with_2(self):
        self.assertEqual(run_gate(result({"verdict": "maybe", "findings": []})), 2)

    def test_empty_input_fails_with_2(self):
        self.assertEqual(run_gate(""), 2)

    def test_not_json_fails_with_2(self):
        self.assertEqual(run_gate("Error: not logged in"), 2)

    def test_json_that_is_not_an_object_fails_with_2(self):
        self.assertEqual(run_gate("[1, 2, 3]"), 2)

    def test_utf8_bom_is_accepted(self):
        raw = b"\xef\xbb\xbf" + json.dumps(result({"verdict": "approve", "findings": []})).encode("utf-8")
        self.assertEqual(run_gate(raw), 0)

    def test_utf16_from_powershell_redirect_is_accepted(self):
        raw = json.dumps(result({"verdict": "approve", "findings": []})).encode("utf-16")
        self.assertEqual(run_gate(raw), 0)


if __name__ == "__main__":
    unittest.main()
