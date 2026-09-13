"""
API-layer tests — every endpoint, end to end, without a running server.
Run: pytest -v
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestHealth:
    def test_health_ok(self):
        res = client.get("/api/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert data["external_calls"] == 0

    def test_health_reports_model_mode(self):
        data = client.get("/api/health").json()
        assert "use_real_model" in data
        assert "reasoning_model" in data
        assert "code_model" in data


class TestDocumentFlow:
    def test_sample_document_flow(self):
        res = client.post("/api/tasks/document", data={"use_sample": "true"})
        assert res.status_code == 200

        data = res.json()
        assert len(data["task_id"]) == 8
        assert len(data["findings"]) > 0
        assert data["output_file"].endswith(".docx")
        # domain tags must be preserved through the whole pipeline
        assert any("PL-204B" in f for f in data["findings"])

    def test_generated_docx_is_downloadable(self):
        data = client.post("/api/tasks/document", data={"use_sample": "true"}).json()
        res = client.get(f"/api/outputs/{data['output_file']}")
        assert res.status_code == 200
        assert res.content[:2] == b"PK"

    def test_rejects_path_traversal(self):
        res = client.get("/api/outputs/../config.py")
        assert res.status_code in (400, 404)

    def test_missing_output_404s(self):
        res = client.get("/api/outputs/does_not_exist.docx")
        assert res.status_code == 404

    def test_rejects_empty_upload(self):
        res = client.post(
            "/api/tasks/document",
            data={"use_sample": "false"},
            files={"file": ("empty.png", b"", "image/png")},
        )
        assert res.status_code == 400

    def test_rejects_corrupt_image(self):
        res = client.post(
            "/api/tasks/document",
            data={"use_sample": "false"},
            files={"file": ("fake.png", b"this is not a real image", "image/png")},
        )
        assert res.status_code == 400


class TestCodeFlow:
    @pytest.mark.parametrize("prompt", ["average", "prime", "sort"])
    def test_known_prompts_execute_successfully(self, prompt):
        res = client.post("/api/tasks/code", data={"prompt": prompt})
        assert res.status_code == 200

        data = res.json()
        assert data["result"]["ok"] is True
        assert len(data["result"]["stdout"]) > 0

    def test_empty_prompt_rejected(self):
        res = client.post("/api/tasks/code", data={"prompt": "   "})
        assert res.status_code == 400


class TestActivityLog:
    def test_log_captures_every_stage(self):
        client.post("/api/tasks/code", data={"prompt": "average"})
        logs = client.get("/api/logs").json()["logs"]

        stages = [entry["stage"] for entry in logs]
        assert "plan" in stages
        assert "route" in stages
        assert "tool:code_gen" in stages
        assert "tool:code_sandbox" in stages
        assert "done" in stages

    def test_log_entries_well_formed(self):
        client.post("/api/tasks/code", data={"prompt": "sort"})
        logs = client.get("/api/logs").json()["logs"]

        for entry in logs:
            assert {"ts", "task_id", "stage", "detail", "meta"} <= set(entry)

    def test_document_flow_logs_model_routing(self):
        """The ROUTE lines are the demo's visual proof of multi-model
        routing — they must actually be written."""
        client.post("/api/tasks/document", data={"use_sample": "true"})
        logs = client.get("/api/logs").json()["logs"]

        route_lines = [e["detail"] for e in logs if e["stage"] == "route"]
        assert len(route_lines) >= 2
        assert any("Tesseract" in line for line in route_lines)
