"""Tests for Common Tools Registry, Agent Database, M:N Use Case Mapping, and Local Semantic Search."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.tools.registry import list_tools, get_tool, suggest_tools_for_intent
from app.agents.agent_store import agent_store
from app import model_router

client = TestClient(app)


def test_tools_registry():
    tools = list_tools()
    assert len(tools) >= 5
    tool_ids = [t["id"] for t in tools]
    assert "deliverable_builder" in tool_ids
    assert "sandbox_tool" in tool_ids
    assert "doc_extractor" in tool_ids
    assert "docgen_tool" in tool_ids
    assert "kb_tool" in tool_ids

    # Test single retrieval
    d_tool = get_tool("deliverable_builder")
    assert d_tool is not None
    assert "pptx" in d_tool["capabilities"]

    # Test intent suggestions
    sug_doc = suggest_tools_for_intent("Analyze scanned PDF report")
    assert "doc_extractor" in sug_doc
    sug_refinery = suggest_tools_for_intent("ASME compliance standard for MRPL refinery")
    assert "kb_tool" in sug_refinery


def test_agent_store_builtins_and_mn_mapping():
    agents = agent_store.list_agents()
    assert len(agents) >= 4
    agent_ids = [a["id"] for a in agents]
    assert "agent_general" in agent_ids
    assert "agent_heat_exchanger" in agent_ids
    assert "agent_mechanical_integrity" in agent_ids
    assert "agent_shift_handover" in agent_ids

    # Verify M:N use case mapping
    uc_map = agent_store.get_use_case_map()
    assert "heat_exchanger_fouling" in uc_map
    assert "refinery_maintenance" in uc_map
    # refinery_maintenance should map to multiple agents!
    assert len(uc_map["refinery_maintenance"]) >= 2

    # Verify distinct use cases list
    all_ucs = agent_store.list_all_use_cases()
    assert len(all_ucs) >= 5
    top_uc = all_ucs[0]
    assert "use_case_id" in top_uc
    assert "agent_count" in top_uc
    assert top_uc["agent_count"] >= 1


def test_local_air_gapped_semantic_search():
    # Search for heat exchanger fouling
    res_hx = agent_store.search_agents("heat exchanger shell fouling", top_k=3)
    assert len(res_hx) > 0
    top_hx = res_hx[0]
    assert top_hx["agent"]["id"] == "agent_heat_exchanger"
    assert "heat_exchanger_fouling" in top_hx["matched_use_cases"]

    # Search for corrosion and wall thickness
    res_corr = agent_store.search_agents("corrosion rate wall thickness inspection", top_k=3)
    assert len(res_corr) > 0
    assert res_corr[0]["agent"]["id"] == "agent_mechanical_integrity"

    # Search for shift log
    res_shift = agent_store.search_agents("shift handover unit alarms LOTO", top_k=3)
    assert len(res_shift) > 0
    assert res_shift[0]["agent"]["id"] == "agent_shift_handover"


def test_dynamic_agent_onboarding_and_lifecycle():
    new_agent = agent_store.create_agent(
        name="Turbomachinery Vibration Specialist",
        description="Monitors centrifugal compressor vibration and bearing temperature excursions.",
        use_case_ids=["compressor_vibration", "bearing_monitoring", "refinery_maintenance"],
        system_prompt="You are a turbomachinery vibration specialist.",
        skill_content="# Vibration Analysis Skill\nApply ISO 10816 vibration severity standards.",
        tool_ids=["deliverable_builder", "sandbox_tool"],
    )

    assert new_agent["id"].startswith("agent_")
    assert new_agent["name"] == "Turbomachinery Vibration Specialist"

    # Verify it appears in search
    search_res = agent_store.search_agents("compressor vibration ISO 10816")
    found_ids = [r["agent"]["id"] for r in search_res]
    assert new_agent["id"] in found_ids

    # Delete custom agent
    deleted = agent_store.delete_agent(new_agent["id"])
    assert deleted is True
    assert agent_store.get_agent(new_agent["id"]) is None

    # Builtin agent cannot be deleted
    assert agent_store.delete_agent("agent_general") is False


def test_meta_agent_skill_drafting():
    draft = model_router.draft_skill_content(
        role_name="Desalter Emulsion Analyst",
        description="Monitors electrostatic desalter water carryover and grid voltage.",
        use_cases=["desalter_efficiency", "salt_in_crude"],
    )
    assert "Desalter Emulsion Analyst" in draft
    assert "Skill Specification" in draft
    assert "Core Calculations" in draft


def test_api_endpoints_tools_and_agents():
    # Tools endpoint
    resp_tools = client.get("/api/tools")
    assert resp_tools.status_code == 200
    assert len(resp_tools.json()["tools"]) >= 5

    # Suggest tools endpoint
    resp_sug = client.get("/api/tools/suggest?intent=extract%20scanned%20image")
    assert resp_sug.status_code == 200
    assert "doc_extractor" in resp_sug.json()["suggested_tools"]

    # Agents endpoint
    resp_agents = client.get("/api/agents")
    assert resp_agents.status_code == 200
    data = resp_agents.json()
    assert "agents" in data
    assert "use_cases" in data

    # Search endpoint
    resp_search = client.get("/api/agents/search?q=fouling")
    assert resp_search.status_code == 200
    results = resp_search.json()["results"]
    assert len(results) > 0
    assert results[0]["agent"]["id"] == "agent_heat_exchanger"

    # Meta-agent skill drafting endpoint
    resp_draft = client.post("/api/agents/draft-skill", json={
        "role_name": "Flare System Inspector",
        "description": "Monitors steam-to-hydrocarbon ratio and tip purge rates.",
        "use_cases": ["flare_monitoring", "emissions_reduction"]
    })
    assert resp_draft.status_code == 200
    assert "Flare System Inspector" in resp_draft.json()["skill_content"]
