"""
Code Sandbox tool — REAL, not a stub.

Writes generated code to a temp directory and executes it in an
isolated subprocess with a hard timeout, capturing stdout / stderr /
exit code. This is the lightweight stand-in for the fully containerised
sandbox in the production architecture — same principle: run and verify,
never just print code and hope.

Cross-platform note: uses sys.executable, NOT a hardcoded "python3",
because python3 does not exist on most Windows installs.

Owner: Track B.
"""
import subprocess
import tempfile
import os

from .. import config

MAX_OUTPUT_CHARS = 5000

def _truncate(text: str) -> str:
    if len(text) > MAX_OUTPUT_CHARS:
        return text[:MAX_OUTPUT_CHARS] + f"\n... [truncated, {len(text) - MAX_OUTPUT_CHARS} more characters]"
    return text

def run_in_sandbox(code: str, timeout_sec: int | None = None) -> dict:
    timeout_sec = timeout_sec or config.SANDBOX_TIMEOUT_SEC

    with tempfile.TemporaryDirectory() as tmp:
        script_path = os.path.join(tmp, "task.py")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(code)

        try:
            result = subprocess.run(
                [config.PYTHON_EXECUTABLE, script_path],
                cwd=tmp,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
            )
            return {
                "ok": result.returncode == 0,
                "stdout": _truncate(result.stdout.strip()),
                "stderr": _truncate(result.stderr.strip()),
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "stdout": "",
                "stderr": f"Execution timed out after {timeout_sec}s",
                "returncode": -1,
            }
        except Exception as e:  # noqa: BLE001
            return {
                "ok": False,
                "stdout": "",
                "stderr": f"Sandbox failure: {type(e).__name__}: {e}",
                "returncode": -1,
            }
