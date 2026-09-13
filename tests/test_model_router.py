"""
Model router tests — routing correctness and stub fallback.
Run: pytest -v
"""
from app import model_router
from app import config


class TestRouting:
    def test_code_tasks_route_to_code_model(self):
        target = model_router.route_task("code")
        assert target["name"] == config.CODE_MODEL_NAME
        assert "8081" in target["url"]

    def test_reasoning_tasks_route_to_reasoning_model(self):
        target = model_router.route_task("reasoning")
        assert target["name"] == config.REASONING_MODEL_NAME
        assert "8080" in target["url"]

    def test_ocr_routes_to_local_tool_not_an_llm(self):
        target = model_router.route_task("ocr")
        assert target["url"] is None
        assert "Tesseract" in target["name"]

    def test_code_and_reasoning_use_different_endpoints(self):
        """This is the multi-model claim — the two must not collapse
        into calling the same server."""
        assert (
            model_router.route_task("code")["url"]
            != model_router.route_task("reasoning")["url"]
        )

    def test_unknown_task_defaults_to_reasoning(self):
        assert model_router.route_task("anything_else")["name"] == config.REASONING_MODEL_NAME


class TestStubFallback:
    """With USE_REAL_MODEL=false (the default), every call must still
    return usable output so a teammate with no model installed can run
    the full app."""

    def test_findings_stub_extracts_something(self):
        text = (
            "Minor corrosion noted on pipeline segment PL-204B. "
            "Pressure gauge PG-11 shows a deviation of 4 percent. "
            "Vibration levels on pump P-7 were within normal tolerance."
        )
        findings, source = model_router.summarize_findings(text)
        assert len(findings) > 0
        assert source in ("model", "stub")

    def test_code_stub_returns_runnable_code(self):
        code, source = model_router.generate_code("compute the average of numbers")
        assert "average" in code
        assert source in ("model", "stub")

    def test_code_stub_handles_unknown_prompt(self):
        code, _ = model_router.generate_code("do something completely unexpected")
        assert "print" in code

    def test_unreachable_server_falls_back_not_crashes(self, monkeypatch):
        """Even in real mode, a dead model server must degrade to the
        stub rather than 500 the whole request."""
        monkeypatch.setattr(config, "USE_REAL_MODEL", True)
        monkeypatch.setattr(config, "REASONING_MODEL_URL", "http://localhost:9/dead")
        monkeypatch.setattr(config, "MODEL_TIMEOUT_SEC", 1)

        findings, source = model_router.summarize_findings("Corrosion on PL-204B.")
        assert source == "stub"
        assert len(findings) > 0


class TestResponseParsing:
    def test_strips_markdown_fences(self):
        raw = "Here you go:\n```python\nprint('hi')\n```"
        assert model_router._strip_code_fences(raw) == "print('hi')"

    def test_parses_bulleted_findings(self):
        raw = "- Corrosion on PL-204B\n* Gasket wear at flange\n1. PG-11 deviation"
        parsed = model_router._parse_findings(raw)
        assert len(parsed) == 3
        assert parsed[0] == "Corrosion on PL-204B"
        assert parsed[2] == "PG-11 deviation"
