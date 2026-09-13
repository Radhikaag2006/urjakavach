from unittest.mock import patch
from app import orchestrator


class TestRetryLogic:
    def test_retries_once_on_sandbox_failure(self):
        """Force the first generated code to fail, confirm the
        orchestrator tries again rather than giving up immediately."""
        call_count = {"n": 0}

        def fake_generate_code(prompt):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return "raise ValueError('forced failure')", "stub"
            return "print('recovered')", "stub"

        with patch("app.orchestrator.model_router.generate_code", side_effect=fake_generate_code):
            result = orchestrator.run_code_flow("anything")

        assert call_count["n"] == 2
        assert result["result"]["ok"] is True
        assert "recovered" in result["result"]["stdout"]