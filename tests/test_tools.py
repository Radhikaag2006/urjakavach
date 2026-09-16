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


class TestComputerVision:
    def test_analyzes_drawing_image(self, tmp_path):
        from PIL import Image, ImageDraw
        from app.tools.cv_tool import analyze_engineering_image

        img_path = str(tmp_path / "cad_drawing.png")
        im = Image.new("RGB", (500, 400), color=(250, 250, 250))
        draw = ImageDraw.Draw(im)
        draw.rectangle([60, 60, 250, 180], outline=(0, 0, 0), width=3)
        draw.ellipse([300, 80, 380, 160], outline=(0, 0, 0), width=3)
        im.save(img_path)

        res = analyze_engineering_image(img_path)
        assert res["ok"] is True
        assert res["is_drawing"] is True
        assert res["analysis_mode"] == "mechanical_drawing"
        assert os.path.exists(os.path.join(config.OUTPUTS_DIR, res["annotated_filename"]))

    def test_analyzes_corrosion_inspection_photo(self, tmp_path):
        from PIL import Image, ImageDraw
        from app.tools.cv_tool import analyze_engineering_image

        img_path = str(tmp_path / "pipe_corrosion.png")
        # Dark metallic background with reddish/brown rust patches
        im = Image.new("RGB", (400, 300), color=(70, 75, 80))
        draw = ImageDraw.Draw(im)
        draw.ellipse([80, 80, 180, 180], fill=(165, 42, 42))  # Rust patch
        draw.ellipse([220, 120, 290, 190], fill=(180, 70, 30))  # Oxide pit
        im.save(img_path)

        res = analyze_engineering_image(img_path)
        assert res["ok"] is True
        assert res["analysis_mode"] == "surface_defect_inspection"
        assert res["corrosion_area_percentage"] > 0
        assert res["defect_count"] >= 1
        assert res["severity"] in ("Minor", "Major", "Critical", "Observation")
        assert os.path.exists(os.path.join(config.OUTPUTS_DIR, res["annotated_filename"]))

    def test_rejects_non_engineering_natural_image(self, tmp_path):
        from PIL import Image, ImageDraw
        from app.tools.cv_tool import analyze_engineering_image

        img_path = str(tmp_path / "natural_flower.png")
        # Vibrant green foliage background with pink/red floral elements
        im = Image.new("RGB", (300, 300), color=(34, 139, 34))  # Forest green
        draw = ImageDraw.Draw(im)
        draw.ellipse([50, 50, 250, 250], fill=(255, 20, 147))  # Vibrant pink/magenta petal
        draw.ellipse([100, 100, 200, 200], fill=(255, 105, 180))
        im.save(img_path)

        res = analyze_engineering_image(img_path)
        assert res["ok"] is True
        assert res["domain"] == "non_engineering"
        assert res["analysis_mode"] == "non_engineering_rejected"
        assert res["is_engineering_image"] is False
        assert res["corrosion_area_percentage"] == 0.0
        assert "Non-Engineering" in res["summary"]



class TestDiagramGenerator:
    def test_generates_heat_exchanger_diagram(self):
        from app.tools.diagram_generator import generate_engineering_diagram

        res = generate_engineering_diagram("Heat Exchanger E-101 Shell and Tube bundle")
        assert res["ok"] is True
        assert "Heat Exchanger" in res["title"]
        assert res["filename"].endswith(".png")
        assert os.path.exists(os.path.join(config.OUTPUTS_DIR, res["filename"]))

    def test_generates_corrosion_chart(self):
        from app.tools.diagram_generator import generate_engineering_diagram

        res = generate_engineering_diagram("Piping wall thickness degradation API 570")
        assert res["ok"] is True
        assert "Degradation" in res["title"]
        assert os.path.exists(os.path.join(config.OUTPUTS_DIR, res["filename"]))

