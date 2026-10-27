"""AI review gate. Reads the JSON that `claude -p --output-format json --json-schema ...` prints.

Fails closed: only a clean, valid "approve" exits 0.
Exit codes: 0 approve, 1 changes requested, 2 anything else (error, bad input, crash).
"""

import json
import sys

BLOCKING = {"critical", "high"}
KNOWN = BLOCKING | {"medium", "low"}


def decode(raw: bytes) -> str:
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):  # PowerShell '>' writes UTF-16
        return raw.decode("utf-16")
    return raw.decode("utf-8-sig")


def decide(raw: bytes) -> tuple[int, str]:
    data = json.loads(decode(raw))
    if not isinstance(data, dict):
        return 2, "output is not a JSON object"
    if data.get("is_error") is not False:
        return 2, f"run failed: {data.get('subtype')}"
    if data.get("subtype") != "success":
        return 2, f"run did not succeed: {data.get('subtype')}"
    out = data.get("structured_output")
    if not isinstance(out, dict):
        return 2, "no structured_output"
    verdict, findings = out.get("verdict"), out.get("findings")
    if verdict not in ("approve", "changes_requested") or not isinstance(findings, list):
        return 2, "verdict or findings not valid"
    if not all(isinstance(f, dict) and f.get("severity") in KNOWN for f in findings):
        return 2, "a finding has no known severity"  # an unknown word must not slip through as harmless
    blocking = [f for f in findings if f["severity"] in BLOCKING]
    if verdict == "changes_requested" or blocking:
        return 1, f"changes requested ({len(blocking)} blocking findings)"
    return 0, "approved"


def main() -> int:
    try:
        code, message = decide(sys.stdin.buffer.read())
    except Exception as exc:  # fail closed: a crash must never look like a pass or a review
        code, message = 2, f"gate could not read the result ({type(exc).__name__})"
    print(f"ai_gate: {message}")
    return code


if __name__ == "__main__":
    sys.exit(main())
