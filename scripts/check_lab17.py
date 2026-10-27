"""Check for Lab 17 (Headless and CI). Standard library only.

Run from the repository root:  python scripts/check_lab17.py

Nothing here calls the network or needs an Anthropic key. It checks:
  1. scripts/ai_gate.py (unit tests plus extra fail-closed cases)
  2. .github/workflows/ci.yml (structure, pinned actions, least privilege, timeouts, no secret echo)
  3. docs/headless-run.json (the result of your own local `claude -p` run)
  4. git hygiene (committed, no key-shaped text anywhere)
"""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
GATE = ROOT / "scripts" / "ai_gate.py"
RUN_JSON = ROOT / "docs" / "headless-run.json"
failures: list[str] = []


def check(ok: bool, message: str) -> None:
    print(("PASS  " if ok else "FAIL  ") + message)
    if not ok:
        failures.append(message)


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


# --------------------------------------------------------------------------
# A small YAML reader for the subset GitHub workflows use: block mappings and
# sequences, scalars, quoted strings, `|` and `>` block scalars, `[a, b]`, `{}`.
# Everything is returned as str, dict or list ("true" stays the string "true").
# --------------------------------------------------------------------------
class Yaml:
    def __init__(self, text: str):
        self.raw = text.replace("\r\n", "\n").split("\n")
        self.i = 0

    @staticmethod
    def strip_comment(s: str) -> str:
        quote = None
        for k, ch in enumerate(s):
            if quote:
                if ch == quote:
                    quote = None
            elif ch in "\"'":
                quote = ch
            elif ch == "#" and (k == 0 or s[k - 1] in " \t"):
                return s[:k].rstrip()
        return s.rstrip()

    def skip_blank(self):
        while self.i < len(self.raw):
            t = self.strip_comment(self.raw[self.i])
            if t.strip():
                return
            self.i += 1

    def indent_of(self, line: str) -> int:
        return len(line) - len(line.lstrip(" "))

    def parse(self):
        self.skip_blank()
        return self.node(self.indent_of(self.raw[self.i])) if self.i < len(self.raw) else {}

    def node(self, indent: int):
        line = self.strip_comment(self.raw[self.i]).strip()
        return self.sequence(indent) if line.startswith("- ") or line == "-" else self.mapping(indent)

    def scalar(self, s: str):
        s = s.strip()
        if s.startswith("[") and s.endswith("]"):
            inner = s[1:-1].strip()
            return [self.scalar(p) for p in inner.split(",")] if inner else []
        if s == "{}":
            return {}
        if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
            return s[1:-1]
        return s

    def block_scalar(self, indent: int) -> str:
        out = []
        while self.i < len(self.raw):
            line = self.raw[self.i]
            if line.strip() and self.indent_of(line) <= indent:
                break
            out.append(line.strip())
            self.i += 1
        return "\n".join(out).strip()

    def mapping(self, indent: int):
        result: dict = {}
        while True:
            self.skip_blank()
            if self.i >= len(self.raw):
                break
            line = self.raw[self.i]
            if self.indent_of(line) != indent:
                break
            text = self.strip_comment(line).strip()
            m = re.match(r"""^("[^"]*"|'[^']*'|[^\s:][^:]*?)\s*:(?:\s+(.*))?$""", text)
            if not m or text.startswith("- "):
                break
            key, rest = self.scalar(m.group(1)), (m.group(2) or "").strip()
            self.i += 1
            if rest[:1] in ("|", ">"):
                result[key] = self.block_scalar(indent)
            elif rest:
                result[key] = self.scalar(rest)
            else:
                self.skip_blank()
                if self.i < len(self.raw):
                    nxt = self.raw[self.i]
                    ni = self.indent_of(nxt)
                    is_seq = self.strip_comment(nxt).strip().startswith("-")
                    if ni > indent or (ni == indent and is_seq):
                        result[key] = self.node(ni)
                        continue
                result[key] = {}
        return result

    def sequence(self, indent: int):
        items = []
        while True:
            self.skip_blank()
            if self.i >= len(self.raw):
                break
            line = self.raw[self.i]
            text = self.strip_comment(line).strip()
            if self.indent_of(line) != indent or not (text.startswith("- ") or text == "-"):
                break
            rest = text[1:].strip()
            if not rest:
                self.i += 1
                self.skip_blank()
                items.append(self.node(self.indent_of(self.raw[self.i])))
            elif re.match(r"""^("[^"]*"|'[^']*'|[^\s:\[{'"][^:]*?)\s*:(\s|$)""", rest):
                # "- key: value": rewrite the line as a mapping that starts two columns in
                self.raw[self.i] = " " * (indent + 2) + rest
                items.append(self.mapping(indent + 2))
            else:
                self.i += 1
                items.append(self.scalar(rest))
        return items


def load_yaml(path: Path):
    return Yaml(path.read_text(encoding="utf-8")).parse()


def as_text(value) -> str:
    return json.dumps(value) if not isinstance(value, str) else value


# --------------------------------------------------------------------------
branch = git("branch", "--show-current")
check(branch not in ("", "main"), f"you are on your own branch, not main (on '{branch}')")

# --- 1. the gate ----------------------------------------------------------
print("\n-- scripts/ai_gate.py")
check(GATE.exists(), "scripts/ai_gate.py exists")
if GATE.exists():
    proc = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "scripts", "-p", "test_ai_gate.py"],
                          cwd=ROOT, capture_output=True, text=True, timeout=300)
    check(proc.returncode == 0, "the provided tests in scripts/test_ai_gate.py pass")

    def gate(payload) -> int:
        data = payload if isinstance(payload, bytes) else (payload if isinstance(payload, str) else json.dumps(payload)).encode()
        return subprocess.run([sys.executable, str(GATE)], input=data, capture_output=True, timeout=30).returncode

    ok = {"type": "result", "subtype": "success", "is_error": False}
    check(gate({**ok, "structured_output": {"verdict": "approve", "findings": [{"severity": "critical"}]}}) == 1,
          "gate: approve with a critical finding is still a failure (exit 1)")
    check(gate({"subtype": "success", "structured_output": {"verdict": "approve", "findings": []}}) == 2,
          "gate: a result without is_error is not trusted (exit 2)")
    check(gate({**ok, "structured_output": {"verdict": "approve", "findings": "none"}}) == 2,
          "gate: findings that are not a list are rejected (exit 2)")
    check(gate({**ok, "is_error": "false", "structured_output": {"verdict": "approve", "findings": []}}) == 2,
          "gate: is_error must be the boolean false (exit 2)")
    check(gate({**ok, "structured_output": {"verdict": "APPROVE", "findings": []}}) == 2,
          "gate: the verdict must match exactly (exit 2)")
    check(gate({**ok, "structured_output": {"verdict": "approve", "findings": [{"severity": "severe"}]}}) == 2,
          "gate: an unknown severity word is rejected, not treated as harmless (exit 2)")
    check(gate({**ok, "structured_output": {"verdict": "approve"}}) == 2,
          "gate: a missing findings list is rejected (exit 2)")
    check(gate(b"\xff\xfe\x00\x00garbage") == 2, "gate: undecodable bytes exit 2, not a traceback exit 1")
    src = GATE.read_text(encoding="utf-8")
    check("sys.exit" in src and "except" in src, "gate: catches errors itself and exits with its own code")

# --- 2. the workflow ------------------------------------------------------
print("\n-- .github/workflows/ci.yml")
check(WORKFLOW.exists(), ".github/workflows/ci.yml exists")
wf: dict = {}
if WORKFLOW.exists():
    try:
        wf = load_yaml(WORKFLOW)
    except Exception as exc:  # a parse problem is a finding for the student
        check(False, f"the workflow can be read ({type(exc).__name__}: {exc})")
    text = WORKFLOW.read_text(encoding="utf-8")
    jobs = wf.get("jobs", {}) if isinstance(wf, dict) else {}
    check(isinstance(jobs, dict) and len(jobs) >= 3, "at least three jobs: tests, ai-review, gate")

    on = wf.get("on", wf.get("true", {}))
    on_text = as_text(on)
    check("pull_request" in on_text and "pull_request_target" not in on_text,
          "triggers on pull_request and not pull_request_target (which hands secrets to fork code)")
    check("workflow_run" not in on_text, "does not use workflow_run")

    top = wf.get("permissions")
    check(top == {"contents": "read"}, "top-level permissions: is exactly contents: read")
    check("write-all" not in text and "read-all" not in text, "no write-all or read-all shortcut")

    allowed_job_writes = {"pull-requests", "issues", "id-token"}
    action_jobs = set()
    for name, job in jobs.items():
        for step in job.get("steps", []) if isinstance(job, dict) and isinstance(job.get("steps"), list) else []:
            if "anthropics/claude-code-action" in str(step.get("uses", "")):
                action_jobs.add(name)
    bad = []
    for name, job in jobs.items():
        perms = job.get("permissions", None) if isinstance(job, dict) else None
        if isinstance(perms, dict):
            for scope, level in perms.items():
                if level == "write" and (scope not in allowed_job_writes or (scope == "id-token" and name not in action_jobs)):
                    bad.append(f"{name}: {scope}: write")
    check(not bad, "no job asks for more than it needs" + (f" (found {bad})" if bad else ""))
    gate_jobs = [n for n, j in jobs.items() if isinstance(j, dict) and "always()" in as_text(j.get("if", ""))]
    check(len(gate_jobs) == 1 and jobs[gate_jobs[0]].get("permissions") == {},
          "one gate job runs if: always() and has permissions: {} (it needs no token at all)")

    missing = []
    for name, job in jobs.items():
        t = job.get("timeout-minutes") if isinstance(job, dict) else None
        if not (isinstance(t, str) and t.isdigit() and 1 <= int(t) <= 30):
            missing.append(name)
    check(bool(jobs) and not missing, "every job has timeout-minutes between 1 and 30" + (f" (missing: {missing})" if missing else ""))
    check(isinstance(wf.get("concurrency"), dict) and wf["concurrency"].get("cancel-in-progress") == "true",
          "concurrency with cancel-in-progress: true (cost control)")

    steps_all = [(n, s) for n, j in jobs.items() if isinstance(j, dict) and isinstance(j.get("steps"), list) for s in j["steps"] if isinstance(s, dict)]

    # pinned actions
    unpinned = []
    for _, s in steps_all:
        ref = s.get("uses")
        if not ref or ref.startswith("./"):
            continue
        action, _, version = ref.partition("@")
        first_party = action.startswith(("actions/", "github/"))
        if re.fullmatch(r"[0-9a-f]{40}", version):
            continue
        if first_party and re.fullmatch(r"v\d+(\.\d+){0,2}", version):
            continue
        unpinned.append(ref)
    check(bool(steps_all) and not unpinned,
          "every action is pinned: third-party actions by 40-character SHA, actions/* by SHA or version tag"
          + (f" (not pinned: {unpinned})" if unpinned else ""))
    third = [s["uses"] for _, s in steps_all if s.get("uses") and not s["uses"].startswith(("actions/", "github/", "./"))]
    check(bool(third) and all(re.fullmatch(r".+@[0-9a-f]{40}", u) for u in third),
          "claude-code-action and setup-uv use a full SHA (a tag can move)")

    checkouts = [s for _, s in steps_all if str(s.get("uses", "")).startswith("actions/checkout@")]
    check(bool(checkouts) and all(isinstance(s.get("with"), dict) and s["with"].get("persist-credentials") == "false" for s in checkouts),
          "every checkout sets persist-credentials: false")

    runs = [str(s.get("run", "")) for _, s in steps_all if s.get("run")]
    check(any("pytest" in r for r in runs), "a step runs the backend tests (pytest)")
    check(not any("secrets." in r or "ANTHROPIC_API_KEY" in r or "CLAUDE_CODE_OAUTH_TOKEN" in r for r in runs),
          "no run: script touches a secret (secrets belong in with: or env:, never in a script)")
    check(not any(re.search(r"\bprintenv\b|\benv\s*\||set\s+-[a-z]*x|\bdeclare\s+-x", r) for r in runs),
          "no run: script prints the environment or turns on shell tracing")
    check(not any(re.search(r"\$\{\{\s*(github\.event\.|github\.head_ref)", r) for r in runs),
          "no run: script embeds github.event.* or head_ref text (script injection); pass it through env:")
    check(not re.search(r"pr merge|enable-auto-merge|automerge|auto-merge|--auto\b|gh api .*merge", text, re.I),
          "nothing in the workflow merges a pull request (the AI never merges)")

    action_steps = [(n, s) for n, s in steps_all if "anthropics/claude-code-action" in str(s.get("uses", ""))]
    check(len(action_steps) == 1, "exactly one step uses anthropics/claude-code-action")
    if action_steps:
        jname, step = action_steps[0]
        with_ = step.get("with", {}) if isinstance(step.get("with"), dict) else {}
        key = with_.get("anthropic_api_key") or with_.get("claude_code_oauth_token") or ""
        check(re.fullmatch(r"\$\{\{\s*secrets\.[A-Z_]+\s*\}\}", key) is not None,
              "the action reads its credential from a secret (anthropic_api_key or claude_code_oauth_token)")
        args = str(with_.get("claude_args", ""))
        check(re.search(r"--max-turns\s+\d+", args) is not None, "claude_args sets --max-turns")
        check("--allowedTools" in args and "Bash" not in args.replace("mcp__", ""),
              "claude_args lists --allowedTools and does not hand out Bash")
        job_env = jobs[jname].get("env", {}) if isinstance(jobs[jname].get("env"), dict) else {}
        guards = [k for k, v in job_env.items() if "secrets." in str(v) and "!=" in str(v)]
        check(bool(guards), "the job computes a guard from the secret, for example HAS_AUTH: ${{ secrets.X != '' }}")
        check(bool(guards) and any(f"env.{g}" in str(step.get("if", "")) for g in guards),
              "the action step runs only if that guard is true (if: env.HAS_AUTH == 'true')")
        outs = jobs[jname].get("outputs")
        check(isinstance(outs, dict) and "reviewed" in outs,
              "the ai-review job exports an output saying whether a review really happened")
    if gate_jobs:
        g = jobs[gate_jobs[0]]
        needs = as_text(g.get("needs", ""))
        check("tests" in needs and "ai-review" in needs, "the gate needs both tests and ai-review")
        g_text = as_text(g)
        check("exit 1" in g_text and "needs.tests.result" in g_text and "needs.ai-review.result" in g_text,
              "the gate reads both results and exits 1 on anything but success")
        check("REQUIRE" in g_text.upper(), "the gate can require a real AI review (a repository variable switches it on)")

    if shutil.which("actionlint"):
        res = subprocess.run(["actionlint", str(WORKFLOW)], capture_output=True, text=True)
        check(res.returncode == 0, "actionlint finds no problems" + (": " + res.stdout.strip()[:300] if res.returncode else ""))
    else:
        print("INFO  actionlint is not installed; skipped (optional)")

# --- 3. your own headless run -------------------------------------------
print("\n-- docs/headless-run.json")
check(RUN_JSON.exists(), "docs/headless-run.json exists (the output of your local claude -p run)")
if RUN_JSON.exists():
    raw = RUN_JSON.read_bytes()
    try:
        body = raw.decode("utf-16") if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else raw.decode("utf-8-sig")
        run = json.loads(body)
    except Exception:
        run = None
    check(isinstance(run, dict) and run.get("type") == "result", "it is the JSON result object printed by claude -p --output-format json")
    if isinstance(run, dict):
        check(bool(run.get("session_id")) and isinstance(run.get("total_cost_usd"), (int, float)),
              "it has a session_id and a total_cost_usd")
        check(run.get("subtype") == "success" and run.get("is_error") is False, "the run succeeded (subtype success, is_error false)")
        check(isinstance(run.get("num_turns"), int) and run["num_turns"] <= 4, "it used few turns (you passed --max-turns)")
        out = run.get("structured_output")
        check(isinstance(out, dict) and out.get("verdict") in ("approve", "changes_requested") and isinstance(out.get("findings"), list),
              "it holds a structured_output with a verdict and a findings list (you passed --json-schema)")
        if GATE.exists():
            code = subprocess.run([sys.executable, str(GATE)], input=raw, capture_output=True, timeout=30).returncode
            check(code in (0, 1), f"your gate accepts it as a valid review (exit {code})")
        flat = body
        check(not re.search(r"sk-ant-[A-Za-z0-9_-]{8,}", flat), "the file holds no key")

# --- 4. git hygiene -------------------------------------------------------
print("\n-- git")
tracked = git("ls-files").splitlines()
for f in (".github/workflows/ci.yml", "scripts/ai_gate.py", "docs/headless-run.json"):
    check(f in tracked, f"{f} is committed")
check(git("status", "--porcelain", "--", ".github", "scripts", "docs") == "", "no uncommitted changes in .github, scripts or docs")
leaks = []
for f in tracked:
    p = ROOT / f
    if p.suffix in (".png", ".ico", ".lock", ".csv", ".db") or not p.is_file():
        continue
    try:
        t = p.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        continue
    if f != "scripts/check_lab17.py" and (re.search(r"sk-ant-[A-Za-z0-9_-]{8,}", t) or re.search(r"(ANTHROPIC_API_KEY|CLAUDE_CODE_OAUTH_TOKEN)\s*[:=]\s*[\"']?[A-Za-z0-9_-]{12,}", t)):
        leaks.append(f)
check(not leaks, "no committed file holds a key or token" + (f" (found in {leaks})" if leaks else ""))
check(".env" not in tracked, ".env is not tracked")

print()
if failures:
    print(f"{len(failures)} check(s) failed.")
    sys.exit(1)
print("ALL CHECKS PASSED")
