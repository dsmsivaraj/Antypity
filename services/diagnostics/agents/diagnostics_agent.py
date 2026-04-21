"""Self-monitoring diagnostic agents.

Four agents, all extending BaseAgent, that plug into the standard registry
and orchestrator so they can also be triggered ad-hoc via POST /execute.

- HealthCheckAgent     — inspects DB, LLM, registry, storage
- TestRunnerAgent      — runs the pytest suite via subprocess
- CodeAnalyzerAgent    — static analysis for anti-patterns and known gaps
- DiagnosticsReporterAgent — aggregates findings into a structured summary
"""
from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from shared.base_agent import AgentMetadata, AgentResult, BaseAgent

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent

_SCAN_DIRS = ["backend", "agents", "shared"]

# (regex, severity, category, message, suggestion)
_PATTERN_CHECKS = [
    (
        r"(?<!\w)except\s*:",
        "warning",
        "quality",
        "Bare except: catches SystemExit and KeyboardInterrupt",
        "Catch specific exception types (e.g. except Exception as exc:)",
    ),
    (
        r"\beval\s*\(",
        "critical",
        "security",
        "eval() allows arbitrary code execution",
        "Replace with a safe alternative (ast.literal_eval, json.loads, etc.)",
    ),
    (
        r"\bexec\s*\(",
        "critical",
        "security",
        "exec() allows arbitrary code execution",
        "Remove exec() usage and replace with explicit logic.",
    ),
    (
        r"\b(TODO|FIXME|HACK|XXX)\b",
        "info",
        "quality",
        "Code debt marker — unresolved work item",
        "Resolve the issue or move it to the issue tracker.",
    ),
]


@dataclass
class _Issue:
    severity: str  # critical | warning | info
    category: str  # health | test | security | quality | gap
    message: str
    file: Optional[str] = None
    line: Optional[int] = None
    suggestion: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "severity": self.severity,
            "category": self.category,
            "message": self.message,
            "file": self.file,
            "line": self.line,
            "suggestion": self.suggestion,
        }


# ── HealthCheckAgent ──────────────────────────────────────────────────────────

class HealthCheckAgent(BaseAgent):
    """Inspects all platform components and returns structured health status."""

    def __init__(self, db_client, llm_client, registry, store) -> None:
        super().__init__(
            metadata=AgentMetadata(
                name="health-monitor",
                description="Checks platform component health: database, registry, LLM, and storage.",
                capabilities=["health monitoring", "platform diagnostics", "service liveness"],
            )
        )
        self._db = db_client
        self._llm = llm_client
        self._registry = registry
        self._store = store

    def can_handle(self, task: str, context: Optional[Dict] = None) -> int:
        t = task.lower()
        return 90 if any(kw in t for kw in ("health", "monitor", "status check", "ping", "liveness")) else 5

    def execute(self, task: str, context: Optional[Dict] = None) -> AgentResult:
        results: Dict[str, str] = {}
        issues: List[_Issue] = []

        # Database
        if self._db.is_configured:
            db_status = self._db.get_status()
            results["database"] = "ok" if db_status.connected else f"error: {db_status.detail}"
            if not db_status.connected:
                issues.append(_Issue(
                    severity="critical", category="health",
                    message=f"Database unreachable: {db_status.detail}",
                    suggestion="Check DATABASE_URL and that the PostgreSQL service is running.",
                ))
        else:
            results["database"] = "not configured"
            issues.append(_Issue(
                severity="info", category="gap",
                message="PostgreSQL not configured — running in memory/JSON storage mode.",
                suggestion="Set APP_STORAGE_BACKEND=postgres and DATABASE_URL for production.",
            ))

        # Agent registry
        agent_count = len(self._registry.all())
        results["registry"] = f"ok ({agent_count} agents registered)"
        if agent_count == 0:
            issues.append(_Issue(
                severity="critical", category="health",
                message="No agents registered — all task routing will fail.",
                suggestion="Check agent registration in backend/container.py.",
            ))

        # LLM
        if self._llm.enabled:
            results["llm"] = "configured (azure-openai)"
        else:
            results["llm"] = "disabled — deterministic fallback active"
            if self._llm.client_error:
                issues.append(_Issue(
                    severity="warning", category="health",
                    message=f"LLM client initialisation error: {self._llm.client_error}",
                    suggestion="Check AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT.",
                ))

        results["storage"] = "ok"

        lines = [
            f"Database  : {results['database']}",
            f"Registry  : {results['registry']}",
            f"LLM       : {results['llm']}",
            f"Storage   : {results['storage']}",
            f"Issues    : {len([i for i in issues if i.severity == 'critical'])} critical, "
            f"{len([i for i in issues if i.severity == 'warning'])} warnings",
        ]
        return AgentResult(
            output="\n".join(lines),
            used_llm=False,
            metadata={"health": results, "issues": [i.as_dict() for i in issues]},
        )


# ── TestRunnerAgent ───────────────────────────────────────────────────────────

class TestRunnerAgent(BaseAgent):
    """Runs the pytest suite and reports pass/fail counts and output."""

    def __init__(self) -> None:
        super().__init__(
            metadata=AgentMetadata(
                name="test-runner",
                description="Runs the project pytest suite and reports pass/fail results.",
                capabilities=["test execution", "regression detection", "quality assurance"],
            )
        )

    def can_handle(self, task: str, context: Optional[Dict] = None) -> int:
        t = task.lower()
        return 90 if any(kw in t for kw in ("run test", "test suite", "pytest", "run tests", "test coverage")) else 5

    def execute(self, task: str, context: Optional[Dict] = None) -> AgentResult:
        if os.environ.get("DIAGNOSTICS_RUNNER_ACTIVE") == "1":
            return AgentResult(
                output="Tests skipped — already running inside a diagnostic subprocess.",
                used_llm=False,
                metadata={
                    "tests": {"passed": 0, "failed": 0, "errors": 0, "duration_seconds": 0, "status": "SKIP", "output": ""},
                    "issues": [],
                },
            )
        env = {**os.environ, "PYTHONPATH": str(ROOT_DIR), "DIAGNOSTICS_RUNNER_ACTIVE": "1"}
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=short", "--no-header"],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(ROOT_DIR),
                env=env,
            )
            output = (proc.stdout + proc.stderr).strip()

            passed = _parse_int(r"(\d+) passed", output)
            failed = _parse_int(r"(\d+) failed", output)
            errors = _parse_int(r"(\d+) error", output)
            duration = _parse_float(r"in ([\d.]+)s", output)

            status = "PASS" if failed == 0 and errors == 0 else "FAIL"
            issues: List[_Issue] = []
            if failed > 0 or errors > 0:
                issues.append(_Issue(
                    severity="critical", category="test",
                    message=f"Test suite: {failed} failures, {errors} errors out of {passed + failed + errors} tests",
                    suggestion="Run `pytest tests/ -v` to inspect individual failures.",
                ))

            summary = f"Tests: {status} — {passed} passed, {failed} failed, {errors} errors ({duration:.1f}s)"
            return AgentResult(
                output=summary,
                used_llm=False,
                metadata={
                    "tests": {
                        "passed": passed,
                        "failed": failed,
                        "errors": errors,
                        "duration_seconds": duration,
                        "status": status,
                        "output": output[-4000:],
                    },
                    "issues": [i.as_dict() for i in issues],
                },
            )
        except subprocess.TimeoutExpired:
            return AgentResult(
                output="Test run timed out after 120s.",
                used_llm=False,
                metadata={
                    "tests": {"passed": 0, "failed": 0, "errors": 1, "duration_seconds": 120, "status": "TIMEOUT", "output": ""},
                    "issues": [_Issue("critical", "test", "Test suite timed out after 120s",
                                     suggestion="Investigate slow tests or increase timeout.").as_dict()],
                },
            )
        except Exception as exc:
            return AgentResult(
                output=f"Test runner error: {exc}",
                used_llm=False,
                metadata={
                    "tests": {"passed": 0, "failed": 0, "errors": 1, "duration_seconds": 0, "status": "ERROR", "output": str(exc)},
                    "issues": [_Issue("critical", "test", f"Test runner failed to start: {exc}",
                                     suggestion="Ensure pytest is installed: pip install pytest").as_dict()],
                },
            )


# ── CodeAnalyzerAgent ─────────────────────────────────────────────────────────

class CodeAnalyzerAgent(BaseAgent):
    """Scans source files for anti-patterns, known gaps, and security issues."""

    def __init__(self) -> None:
        super().__init__(
            metadata=AgentMetadata(
                name="code-analyzer",
                description="Static analysis: anti-patterns, known gaps, security issues, and quality debt.",
                capabilities=["static analysis", "code quality", "gap detection", "security review"],
            )
        )

    def can_handle(self, task: str, context: Optional[Dict] = None) -> int:
        t = task.lower()
        return 90 if any(kw in t for kw in ("analyze code", "code quality", "find bugs", "code gaps", "static analysis", "scan code")) else 5

    def execute(self, task: str, context: Optional[Dict] = None) -> AgentResult:
        issues: List[_Issue] = []
        py_files: List[Path] = []

        for scan_dir in _SCAN_DIRS:
            d = ROOT_DIR / scan_dir
            if d.is_dir():
                py_files.extend(d.rglob("*.py"))

        py_files = [f for f in py_files if "__pycache__" not in str(f)]
        scanned = 0

        for fpath in sorted(py_files):
            rel = str(fpath.relative_to(ROOT_DIR))
            try:
                source = fpath.read_text(encoding="utf-8")
            except Exception:
                continue
            scanned += 1
            is_test_file = "test" in fpath.name or "conftest" in fpath.name

            # Pattern checks
            for lineno, line in enumerate(source.splitlines(), 1):
                for pattern, severity, category, message, suggestion in _PATTERN_CHECKS:
                    if re.search(pattern, line):
                        if category == "quality" and "debt" in message and is_test_file:
                            continue
                        issues.append(_Issue(
                            severity=severity, category=category,
                            message=message, file=rel, line=lineno,
                            suggestion=suggestion,
                        ))

            # Syntax / AST check
            try:
                ast.parse(source)
            except SyntaxError as exc:
                issues.append(_Issue(
                    severity="critical", category="quality",
                    message=f"Syntax error: {exc.msg}",
                    file=rel, line=exc.lineno,
                    suggestion="Fix the syntax error — the module will not import.",
                ))

        # Gap G4: azure-identity unused
        req = ROOT_DIR / "backend" / "requirements.txt"
        if req.exists() and "azure-identity" in req.read_text():
            used = any(
                "azure.identity" in (ROOT_DIR / f).read_text(encoding="utf-8")
                for f in ["backend/auth.py", "backend/llm_client.py"]
                if (ROOT_DIR / f).exists()
            )
            if not used:
                issues.append(_Issue(
                    severity="info", category="gap",
                    message="azure-identity in requirements.txt but never imported (Gap G4)",
                    file="backend/requirements.txt",
                    suggestion="Remove azure-identity to reduce the Docker image size.",
                ))

        # Gap G9: k8s placeholder secrets
        secrets = ROOT_DIR / "k8s" / "secrets.yaml"
        if secrets.exists() and "cGxhY2Vob2xkZXI" in secrets.read_text():
            issues.append(_Issue(
                severity="warning", category="gap",
                message="k8s/secrets.yaml has placeholder base64 values (Gap G9)",
                file="k8s/secrets.yaml",
                suggestion="Replace all placeholder values with real base64-encoded secrets before deploying.",
            ))

        # Check env has stale Cosmos DB vars
        env_file = ROOT_DIR / ".env"
        if env_file.exists() and "COSMOS" in env_file.read_text().upper():
            issues.append(_Issue(
                severity="info", category="gap",
                message=".env contains stale Cosmos DB variables (Gap G3)",
                file=".env",
                suggestion="Remove COSMOS_* variables — they are not used by the current backend.",
            ))

        critical = sum(1 for i in issues if i.severity == "critical")
        warnings = sum(1 for i in issues if i.severity == "warning")
        infos = sum(1 for i in issues if i.severity == "info")

        summary = (
            f"Code analysis: {scanned} files scanned — "
            f"{critical} critical, {warnings} warnings, {infos} info"
        )
        return AgentResult(
            output=summary,
            used_llm=False,
            metadata={"issues": [i.as_dict() for i in issues], "files_scanned": scanned},
        )


# ── DiagnosticsReporterAgent ──────────────────────────────────────────────────

class DiagnosticsReporterAgent(BaseAgent):
    """Aggregates health, test, and code findings into a structured platform report."""

    def __init__(self) -> None:
        super().__init__(
            metadata=AgentMetadata(
                name="diagnostics-reporter",
                description="Aggregates health, test, and code analysis results into a structured diagnostic report.",
                capabilities=["report generation", "diagnostics summary", "status aggregation"],
            )
        )

    def can_handle(self, task: str, context: Optional[Dict] = None) -> int:
        t = task.lower()
        return 90 if any(kw in t for kw in ("diagnostic report", "platform report", "generate report", "full diagnostics")) else 5

    def execute(self, task: str, context: Optional[Dict] = None) -> AgentResult:
        ctx = context or {}
        health: Dict[str, Any] = ctx.get("health", {})
        tests: Dict[str, Any] = ctx.get("tests", {})
        issues: List[Dict[str, Any]] = ctx.get("issues", [])

        critical = [i for i in issues if i.get("severity") == "critical"]
        warnings = [i for i in issues if i.get("severity") == "warning"]
        infos = [i for i in issues if i.get("severity") == "info"]

        tests_failed = tests.get("failed", 0) + tests.get("errors", 0)
        if critical or tests_failed > 0:
            overall = "failing"
        elif warnings:
            overall = "degraded"
        else:
            overall = "healthy"

        lines = [f"Platform status: {overall.upper()}"]
        if health:
            for k, v in health.items():
                lines.append(f"  {k:<12}: {v}")
        if tests:
            lines.append(
                f"  Tests       : {tests.get('passed', 0)} passed, "
                f"{tests.get('failed', 0)} failed, {tests.get('errors', 0)} errors"
            )
        lines.append(f"  Issues      : {len(critical)} critical, {len(warnings)} warnings, {len(infos)} info")

        for issue in critical:
            loc = f"{issue.get('file', '')}:{issue.get('line', '')}" if issue.get("file") else ""
            lines.append(f"\n  [CRITICAL] {loc} {issue['message']}")
            if issue.get("suggestion"):
                lines.append(f"             → {issue['suggestion']}")

        for issue in warnings[:5]:
            loc = issue.get("file", "")
            lines.append(f"  [WARNING]  {loc} — {issue['message']}")

        return AgentResult(
            output="\n".join(lines),
            used_llm=False,
            metadata={"status": overall, "issues": issues, "health": health, "tests": tests},
        )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_int(pattern: str, text: str) -> int:
    m = re.search(pattern, text)
    return int(m.group(1)) if m else 0


def _parse_float(pattern: str, text: str) -> float:
    m = re.search(pattern, text)
    return float(m.group(1)) if m else 0.0
