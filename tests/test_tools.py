"""
Tool-layer tests. These must pass on every teammate's machine.
Run: pytest -v
"""
import os
import pytest

from app import config
from app.tools.sandbox_tool import run_in_sandbox
from app.tools.docgen_tool import draft_approval_note, _infer_severity


class TestSandbox:
    def test_runs_valid_code(self):
        result = run_in_sandbox("print('hello')")
        assert result["ok"] is True
        assert result["stdout"] == "hello"
        assert result["returncode"] == 0

    def test_captures_error(self):
        result = run_in_sandbox("raise ValueError('boom')")
        assert result["ok"] is False
        assert "ValueError" in result["stderr"]

    def test_enforces_timeout(self):
        result = run_in_sandbox("import time; time.sleep(30)", timeout_sec=1)
        assert result["ok"] is False
        assert "timed out" in result["stderr"].lower()

    def test_isolated_from_project_files(self):
        """Sandbox runs in a temp dir, so it must not see project files."""
        result = run_in_sandbox("import os; print(os.path.exists('main.py'))")
        assert result["stdout"] == "False"
    def test_truncates_huge_output(self):
        result = run_in_sandbox("for i in range(100000): print('x' * 100)")
        assert len(result["stdout"]) < 6000
        assert "truncated" in result["stdout"]


class TestDocGen:
    def test_creates_real_docx(self, tmp_path):
        findings = ["Minor corrosion on PL-204B", "PG-11 deviation of 4 percent"]
        path = draft_approval_note("test_report.png", findings, "testid01")

        assert os.path.exists(path)
        assert path.endswith(".docx")
        # A real docx is a zip archive - check the magic bytes
        with open(path, "rb") as f:
            assert f.read(2) == b"PK"

        os.remove(path)

    def test_handles_empty_findings(self):
        path = draft_approval_note("empty.png", [], "testid02")
        assert os.path.exists(path)
        os.remove(path)

    def test_severity_inference(self):
        assert _infer_severity(["active leak detected"]) == "Critical"
        assert _infer_severity(["corrosion noted on segment"]) == "Major"
        assert _infer_severity(["gasket shows wear"]) == "Minor"
        assert _infer_severity(["readings were nominal"]) == "Observation"


class TestOCR:
    @pytest.mark.skipif(
        not os.path.exists(os.path.join(config.SAMPLES_DIR, "inspection_report.png")),
        reason="sample image not present",
    )
    def test_reads_sample_report(self):
        from app.tools.ocr_tool import ocr_image

        text = ocr_image(os.path.join(config.SAMPLES_DIR, "inspection_report.png"))
        assert len(text) > 100
        # Key domain terms must survive OCR
        assert "PL-204B" in text
        assert "corrosion" in text.lower()
