"""Bash tool: execute shell commands under run_dir."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from src.agent.tools import BaseTool

_OUTPUT_LIMIT = 50_000
_DEFAULT_TIMEOUT = 120


def _subprocess_env() -> dict[str, str]:
    """Return an env dict with the project venv bin prepended to PATH.

    When swarm workers run `python3 ...` via bash, they should use the venv's
    Python (3.12 + real OpenSSL) rather than the macOS system python3 (3.9 +
    LibreSSL 2.8.3 which breaks urllib3 v2).
    """
    env = os.environ.copy()
    venv = env.get("VIRTUAL_ENV", "")
    if not venv:
        # bash_tool.py lives at agent/src/tools/ → project root is 3 levels up
        project_root = Path(__file__).resolve().parents[3]
        candidate = project_root / ".venv"
        if candidate.is_dir():
            venv = str(candidate)
    if venv:
        venv_bin = str(Path(venv) / "bin")
        current_path = env.get("PATH", "")
        if venv_bin not in current_path.split(":"):
            env["PATH"] = f"{venv_bin}:{current_path}"
    return env


class BashTool(BaseTool):
    """Execute shell commands in the working directory."""

    name = "bash"
    description = "Execute a shell command in the working directory. Use for installing packages, running scripts, or inspecting files."
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Shell command to execute"},
        },
        "required": ["command"],
    }
    repeatable = True
    is_readonly = False

    def execute(self, **kwargs: Any) -> str:
        """Execute a shell command.

        Args:
            **kwargs: Must include command. Optional run_dir used as cwd.

        Returns:
            JSON string with stdout, stderr, and exit_code.
        """
        command = kwargs["command"]
        cwd = kwargs.get("run_dir")

        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                env=_subprocess_env(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=_DEFAULT_TIMEOUT,
                encoding="utf-8",
                errors="replace",
            )
            stdout = result.stdout[:_OUTPUT_LIMIT] if len(result.stdout) > _OUTPUT_LIMIT else result.stdout
            stderr = result.stderr[:_OUTPUT_LIMIT] if len(result.stderr) > _OUTPUT_LIMIT else result.stderr
            return json.dumps({
                "status": "ok" if result.returncode == 0 else "error",
                "exit_code": result.returncode,
                "stdout": stdout,
                "stderr": stderr,
            }, ensure_ascii=False)
        except subprocess.TimeoutExpired:
            return json.dumps({
                "status": "error",
                "error": f"Command timed out after {_DEFAULT_TIMEOUT}s",
            }, ensure_ascii=False)
        except Exception as exc:
            return json.dumps({
                "status": "error",
                "error": str(exc),
            }, ensure_ascii=False)
