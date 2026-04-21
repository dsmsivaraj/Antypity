"""Self-monitoring diagnostic agents.

Four agents, all extending BaseAgent, that plug into the standard registry
and orchestrator so they can also be triggered ad-hoc via POST /execute.

- HealthCheckAgent          — inspects DB, LLM, registry, storage
- TestRunnerAgent           — runs the pytest suite via subprocess
- CodeAnalyzerAgent         — static analysis for anti-patterns and known gaps
- DiagnosticsReporterAgent  — aggregates findings into a structured summary
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

ROOT_DIR = Path(__file__).resolve().parent.parent

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
        "Code debt marker",
        "Resolve the issue or move to the issue tracker.",
    ),
]


@dataclass
class _Issue:
    severity: str
    category: str
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


def _parse_int(pattern: str, text: str) -> int:
    m = re.search(pattern, text)
    return int(m.group(1)) if m else 0


def _parse_float(pattern: str, text: str) -> float:
    m = re.search(pattern, text)
    return float(m.group(1)) if m else 0.0


# ── HealthCheckAgent ──────────────────────────────────────────────────────────

class HealthCheckAgent(BaseAgent):
    """Inspects database, LLM client, agent registry, and storage health."""

    def __init__(self, db_client, llm_client, registry, store) -> None:
        super().__init__(
            metadata=AgentMetadata(
                name="health-monitor",
                description="Checks database connectivity, LLM availability, registry size, and storage health.",
                capabilities=["health check", "liveness probe", "monitoring", "status"],
            )
        )
        self._db = db_client
        self._llm = llm_client
        self._registry = registry
        self._store = store

    def can_handle(self, task: str, context: Optional[Dict] = None) -> int:
        t = task.lower()
        if any(kw in t for kw in ("health", "liveness", "readiness", "monitor", "status check")):
            return 90
        return 5

    def execute(self, task: str, context: Optional[Dict] = None) -> AgentResult:
        issues: List[_Issue] = []
        health: Dict[str, str] = {}

        # Database
        if self._db and getattr(self._db, "is_configured", False):
            try:
                db_status = self._db.get_status()
                if db_status.connected:
                    health["database"] = "ok"
                else:
                    health["database"] = f"error: {db_status.detail}"
                    issues.append(_Issue(
                        severity="critical", category="infrastructure",
                        message=f"Database unreachable: {db_status.detail}",
                        suggestion="Check POSTGRES_HOST, POSTGRES_USER, and POSTGRES_PASSWORD env vars.",
                    ))
            except Exception as exc:
                health["database"] = f"exception: {exc}"
                issues.append(_Issue(
                    severity="critical", category="infrastructure",
                    message=f"Database status check raised: {exc}",
                    suggestion="Investigate database connectivity.",
                ))
        else:
            health["database"] = "not configured"

        # LLM
        if self._llm:
            if getattr(self._llm, "enabled", False):
                err = getattr(self._llm, "client_error", None)
                if err:
                    health["llm"] = f"error: {err}"
                    issues.append(_Issue(
                        severity="warning", category="llm",
                        message=f"LLM client initialised with error: {err}",
                        suggestion="Verify AZURE_OPENAI_* environment variables.",
                    ))
                else:
                    health["llm"] = "configured"
            else:
                health["llm"] = "disabled (no Azure credentials)"
        else:
            health["llm"] = "not available"

        # Registry
        if self._registry:
            agents = self._registry.all()
            count = len(agents)
            if count == 0:
                health["registry"] = "empty"
                issues.append(_Issue(
                    severity="critical", category="registry",
                    message="No agents registered — orchestrator cannot route any tasks.",
                    suggestion="Ensure build_container() registers at least GeneralistAgent.",
                ))
            else:
                health["registry"] = f"ok ({count})"
        else:
            health["registry"] = "not available"

        # Storage
        if self._store is not None:
            health["storage"] = "ok"
        else:
            health["storage"] = "in-memory (no store)"

        critical = [i for i in issues if i.severity == "critical"]
        warnings = [i for i in issues if i.severity == "warning"]

        if critical:
            status_text = f"CRITICAL — {len(critical)} critical issue(s) detected."
        elif warnings:
            status_text = f"DEGRADED — {len(warnings)} warning(s) detected."
        else:
            status_text = "ok — all systems healthy."

        return AgentResult(
            output=status_text,
            used_llm=False,
            metadata={
                "health": health,
                "issues": [i.as_dict() for i in issues],
            },
        )


# ── TestRunnerAgent ───────────────────────────────────────────────────────────

class TestRunnerAgent(BaseAgent):
    """Runs the pytest suite in a subprocess and reports pass/fail metrics."""

    def __init__(self) -> None:
        super().__init__(
            metadata=AgentMetadata(
                name="test-runner",
                description="Executes the full pytest test suite and reports pass/fail counts and duration.",
                capabilities=["run tests", "pytest", "test coverage", "CI verification"],
            )
        )

    def can_handle(self, task: str, context: Optional[Dict] = None) -> int:
        t = task.lower()
        return 90 if any(kw in t for kw in ("run test", "test suite", "pytest", "run tests", "test coverage")) else 5

    def execute(self, task: str, context: Optional[Dict] = None) -> AgentResult:
        if context and context.get("skip_subprocess"):
            return AgentResult(
                output="Tests skipped for diagnostic run in controlled environment.",
                used_llm=False,
                metadata={
                    "tests": {"passed": 0, "failed": 0, "errors": 0, "duration_seconds": 0, "status": "SKIP", "output": ""},
                    "issues": [],
                },
            )
        # Guard: don't run recursively when already inside a diagnostic subprocess.
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
        return 90 if any(kw in t for kw in ("analyze code", "static analysis", "code gaps", "code issues", "security scan")) else 5

    def execute(self, task: str, context: Optional[Dict] = None) -> AgentResult:
        issues: List[_Issue] = []
        files_scanned = 0

        _SKIP_DIRS = {"venv", ".venv", "__pycache__", "site-packages", ".git", "node_modules", "dist", "build"}
        _SKIP_FILES = {"diagnostics_agent.py"}  # skip self — pattern strings trigger their own checks

        for scan_dir in _SCAN_DIRS:
            base = ROOT_DIR / scan_dir
            if not base.exists():
                continue
            for py_file in sorted(base.rglob("*.py")):
                # Skip virtual-env and generated directories
                if any(part in _SKIP_DIRS for part in py_file.parts):
                    continue
                if py_file.name in _SKIP_FILES:
                    continue
                rel = str(py_file.relative_to(ROOT_DIR))
                files_scanned += 1
                try:
                    source = py_file.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue

                # Pattern checks
                for lineno, line in enumerate(source.splitlines(), start=1):
                    for pattern, severity, category, message, suggestion in _PATTERN_CHECKS:
                        if re.search(pattern, line):
                            issues.append(_Issue(
                                severity=severity, category=category,
                                message=message, file=rel, line=lineno,
                                suggestion=suggestion,
                            ))

                # AST syntax check
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

        # Gap G3: stale Cosmos DB vars in .env
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
            f"Scanned {files_scanned} files: "
            f"{critical} critical, {warnings} warnings, {infos} info issues."
        )
        return AgentResult(
            output=summary,
            used_llm=False,
            metadata={
                "files_scanned": files_scanned,
                "issues": [i.as_dict() for i in issues],
            },
        )


# ── DiagnosticsReporterAgent ──────────────────────────────────────────────────

class DiagnosticsReporterAgent(BaseAgent):
    """Aggregates health, test, and code analysis results into a final report."""

    def __init__(self) -> None:
        super().__init__(
            metadata=AgentMetadata(
                name="diagnostics-reporter",
                description="Aggregates health checks, test results, and code analysis into a diagnostic report.",
                capabilities=["diagnostic report", "full diagnostics", "status summary"],
            )
        )

    def can_handle(self, task: str, context: Optional[Dict] = None) -> int:
        t = task.lower()
        return 90 if any(kw in t for kw in ("diagnostic report", "full diagnostics", "generate report", "platform report")) else 5

    def execute(self, task: str, context: Optional[Dict] = None) -> AgentResult:
        ctx = context or {}
        health = ctx.get("health", {})
        tests = ctx.get("tests", {})
        issues = ctx.get("issues", [])

        critical = [i for i in issues if i.get("severity") == "critical"]
        warnings = [i for i in issues if i.get("severity") == "warning"]
        infos = [i for i in issues if i.get("severity") == "info"]

        test_failed = tests.get("failed", 0)
        test_errors = tests.get("errors", 0)

        if critical or test_failed > 0 or test_errors > 0:
            status = "failing"
        elif warnings:
            status = "degraded"
        else:
            status = "healthy"

        lines = [f"Platform Status: {status.upper()}"]
        if health:
            lines.append("\nHealth:")
            for k, v in health.items():
                lines.append(f"  {k}: {v}")
        if tests:
            passed = tests.get("passed", 0)
            failed = tests.get("failed", 0)
            lines.append(f"\nTests: {passed} passed, {failed} failed (status={tests.get('status', 'unknown')})")
        if issues:
            lines.append(f"\nIssues: {len(critical)} critical, {len(warnings)} warnings, {len(infos)} info")
            for issue in critical[:5]:
                lines.append(f"  [CRITICAL] {issue.get('message', '')}")
            for issue in warnings[:5]:
                lines.append(f"  [WARNING]  {issue.get('message', '')}")

        report_text = "\n".join(lines)
        return AgentResult(
            output=report_text,
            used_llm=False,
            metadata={
                "status": status,
                "issue_counts": {
                    "critical": len(critical),
                    "warnings": len(warnings),
                    "info": len(infos),
                },
            },
        )
