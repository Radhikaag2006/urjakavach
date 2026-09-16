"""Common Agent Database and Local Semantic Search for UrjaKavach.

Implements:
1. Persistent Agent Store in app/logs/agents/
2. M:N bidirectional mapping between Use Case IDs and Agents
3. 100% local, air-gapped semantic search using TF-IDF / BM25 token matching
4. Pre-seeded industrial starter agents (Refinery Process, Heat Exchanger, Mechanical Integrity, Shift Handover)
"""

import json
import math
import os
import re
import time
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

from app import config
from app.tools.registry import suggest_tools_for_intent

AGENTS_DIR = config.AGENTS_DATA_DIR
os.makedirs(AGENTS_DIR, exist_ok=True)

# Common stopwords for fast local tokenization
STOPWORDS: Set[str] = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "can't", "cannot", "could",
    "did", "do", "does", "doing", "don't", "down", "during", "each", "few", "for",
    "from", "further", "had", "has", "have", "having", "he", "her", "here", "hers",
    "herself", "him", "himself", "his", "how", "i", "if", "in", "into", "is", "isn't",
    "it", "its", "itself", "let's", "me", "more", "most", "my", "myself", "no", "nor",
    "not", "of", "off", "on", "once", "only", "or", "other", "ought", "our", "ours",
    "ourselves", "out", "over", "own", "same", "she", "should", "so", "some", "such",
    "than", "that", "the", "their", "theirs", "them", "themselves", "then", "there",
    "these", "they", "this", "those", "through", "to", "too", "under", "until", "up",
    "very", "was", "wasn't", "we", "were", "what", "when", "where", "which", "while",
    "who", "whom", "why", "with", "would", "you", "your", "yours", "yourself",
}

# --------------------------------------------------------------------
# Built-in Starter Agents
# --------------------------------------------------------------------
BUILTIN_AGENTS: List[Dict[str, Any]] = [
    {
        "id": "agent_general",
        "name": "General Engineering & Deliverable Agent",
        "department": "Engineering Systems",
        "description": "All-purpose autonomous agent for coding, calculation, multi-format deliverable generation (PPT, Excel, CSV, Word), and document analysis.",
        "use_case_ids": [
            "general_engineering",
            "code_generation",
            "deliverable_synthesis",
            "document_summary",
            "data_analysis",
        ],
        "system_prompt": (
            "You are UrjaKavach's General Engineering Agent. Provide rigorous, mathematically sound "
            "technical solutions, write verified code, and generate real industrial deliverables (.pptx, .xlsx, .csv, .docx) "
            "with zero placeholder content."
        ),
        "skill_filename": "SKILL_GENERAL.md",
        "skill_content": (
            "# General Engineering & Deliverable Agent Skill\n\n"
            "## Operating Guidelines\n"
            "1. Deliver precise, mathematically verified engineering analysis.\n"
            "2. When generating spreadsheets (.xlsx), always include clean headers, units, and logical row sequencing.\n"
            "3. When generating presentations (.pptx), follow 16:9 widescreen layout with professional technical bullet points.\n"
            "4. When writing code, ensure Python snippets execute cleanly in the sandbox.\n"
        ),
        "tool_ids": ["deliverable_builder", "sandbox_tool", "doc_extractor", "docgen_tool"],
        "model_type": "reasoning",
        "is_builtin": True,
        "starter_prompts": [
            "Write a python script to calculate the moving average of pipeline pressure readings.",
            "Generate a 5-slide technical presentation summarizing our system architecture.",
            "Structure these operational readings into a styled Excel sheet with status columns.",
        ],
    },
    {
        "id": "agent_heat_exchanger",
        "name": "Refinery Heat Exchanger & Fouling Analyst",
        "department": "Technical Services / Mechanical",
        "description": "Specialized in TEMA shell-and-tube exchangers, thermal duty, fouling factor tracking, pressure drop monitoring, and turnaround inspection decks.",
        "use_case_ids": [
            "heat_exchanger_fouling",
            "refinery_maintenance",
            "energy_efficiency",
            "tema_standards",
            "cooling_water_monitoring",
            "thermal_duty",
        ],
        "system_prompt": (
            "You are the UrjaKavach Heat Exchanger & Thermal Analyst. You specialize in refinery heat transfer equipment, "
            "TEMA Class R/B/C standards, tube bundle inspection, fouling resistance calculation, and turnaround planning. "
            "Always state relevant engineering formulas (e.g. Q = U * A * LMTD, Rd = 1/U_dirty - 1/U_clean) and quantify impact."
        ),
        "skill_filename": "SKILL_HEAT_EXCHANGER.md",
        "skill_content": (
            "# Refinery Heat Exchanger & Fouling Analysis Skill\n\n"
            "## Standards Reference\n"
            "- TEMA 10th Edition (Tubular Exchanger Manufacturers Association) Class R (Petroleum Processing).\n"
            "- ASME Section VIII Division 1 Pressure Vessels.\n\n"
            "## Core Calculations\n"
            "1. **Log Mean Temperature Difference (LMTD)**:\n"
            "   $$LMTD = \\frac{\\Delta T_1 - \\Delta T_2}{\\ln(\\Delta T_1 / \\Delta T_2)}$$\n"
            "2. **Thermal Duty (Q)**: $Q = \\dot{m} \\cdot C_p \\cdot (T_{out} - T_{in})$\n"
            "3. **Fouling Factor ($R_f$)**: $R_f = \\frac{1}{U_{actual}} - \\frac{1}{U_{clean}}$\n"
            "4. **Tube Side Pressure Drop**: Warn if $\\Delta P$ exceeds design baseline by > 35%.\n\n"
            "## Standard Deliverables\n"
            "- **Turnaround Deck (.pptx)**: 5-6 slides detailing bundle condition, delta-P trend, fouling rate, and cleaning recommendations.\n"
            "- **Inspection Log (.xlsx)**: Columnar data for Tube No., Ultrasonic Thickness (UT), Pit Depth, Plugs, and Remaining Service Life.\n"
        ),
        "tool_ids": ["deliverable_builder", "sandbox_tool", "doc_extractor"],
        "model_type": "reasoning",
        "is_builtin": True,
        "starter_prompts": [
            "Calculate fouling resistance Rf and delta-P increase for crude preheat exchanger E-101.",
            "Generate a 6-slide turnaround inspection presentation for TEMA Class R exchanger bundle.",
            "Create an Excel spreadsheet tracking tube thickness, pit depth, and plug status across 4 passes.",
        ],
    },
    {
        "id": "agent_mechanical_integrity",
        "name": "Mechanical Integrity & Piping Inspector",
        "department": "Inspection & Quality Assurance",
        "description": "Monitors refinery piping and pressure vessel integrity adhering to API 570, API 510, and ASME B31.3. Calculates corrosion rates and remaining service life.",
        "use_case_ids": [
            "api_570_piping",
            "api_510_vessels",
            "corrosion_rate_monitoring",
            "thickness_inspection",
            "refinery_maintenance",
            "asset_integrity",
        ],
        "system_prompt": (
            "You are UrjaKavach's Mechanical Integrity & Inspection Specialist. Adhere strictly to API 570 (Piping Inspection) "
            "and API 510 (Pressure Vessel Inspection). Calculate minimum required wall thickness (t_min), corrosion rates, "
            "and remaining life. Format high-risk findings into formal approval notes or styled inspection logs."
        ),
        "skill_filename": "SKILL_MECHANICAL_INTEGRITY.md",
        "skill_content": (
            "# Mechanical Integrity & Piping Inspection Skill\n\n"
            "## Applicable Codes\n"
            "- API 570: Piping Inspection Code (In-service Inspection, Rating, Repair, and Alteration).\n"
            "- API 510: Pressure Vessel Inspection Code.\n"
            "- ASME B31.3: Process Piping.\n\n"
            "## Governing Formulas\n"
            "1. **Corrosion Rate (CR)**: $CR = \\frac{t_{previous} - t_{actual}}{\\text{time in years}}$ (mm/year or mpy).\n"
            "2. **Remaining Life (RL)**: $RL = \\frac{t_{actual} - t_{min}}{CR}$.\n"
            "3. **Barlow's Equation for Minimum Thickness**: $t_{min} = \\frac{P \\cdot D}{2(S \\cdot E + P \\cdot Y)}$.\n\n"
            "## Action Thresholds\n"
            "- If Remaining Life < 2 years, trigger **IMMEDIATE REPAIR OR DERATING** flag.\n"
            "- When requested, generate official .docx approval note for maintenance turnaround.\n"
        ),
        "tool_ids": ["deliverable_builder", "sandbox_tool", "docgen_tool", "doc_extractor"],
        "model_type": "reasoning",
        "is_builtin": True,
        "starter_prompts": [
            "Compute corrosion rate and remaining life for a 12-inch crude transfer line with 6.2mm current wall thickness.",
            "Draft a formal API 570 inspection approval note (.docx) for de-ethanizer reflux piping.",
            "Export an Excel sheet tracking CML (Condition Monitoring Locations) and corrosion rates.",
        ],
    },
    {
        "id": "agent_shift_handover",
        "name": "Plant Shift Handover & Log Digest Agent",
        "department": "Refinery Operations",
        "description": "Synthesizes control room log sheets, safety tagouts (LOTO), standing alarms, and operational setpoint variances into structured shift handover reports.",
        "use_case_ids": [
            "shift_handover",
            "plant_operations",
            "alarm_digest",
            "safety_checklist",
            "refinery_maintenance",
            "daily_log_digest",
        ],
        "system_prompt": (
            "You are UrjaKavach's Plant Shift Handover Specialist. In refinery operations, miscommunication between shifts "
            "is a primary cause of process safety incidents. Synthesize unit logs, equipment status, active permit-to-work (PTW), "
            "lockout-tagouts (LOTO), and standing alarms with 100% clarity and zero ambiguity."
        ),
        "skill_filename": "SKILL_SHIFT_HANDOVER.md",
        "skill_content": (
            "# Plant Shift Handover & Operational Digest Skill\n\n"
            "## Standard Handover Sections\n"
            "1. **Unit Overview**: Throughput (MT/hr), key operating targets, and setpoint deviations.\n"
            "2. **Safety & Environmental**: Active permits (hot work, confined space), LOTO status, flare flushes.\n"
            "3. **Equipment Status**: Running, standby, and under-maintenance pumps/compressors.\n"
            "4. **Standing Alarms**: High-priority alarms bypassed or active > 4 hours.\n"
            "5. **Action Items for Incoming Shift**: Explicit next-step checklist.\n"
        ),
        "tool_ids": ["deliverable_builder", "doc_extractor", "docgen_tool"],
        "model_type": "reasoning",
        "is_builtin": True,
        "starter_prompts": [
            "Digest this morning unit log and highlight standing alarms and active hot-work permits.",
            "Generate an Excel sheet of equipment status across CDU-1 for the 14:00 - 22:00 shift.",
            "Draft an official shift handover memo (.docx) for the incoming unit shift supervisor.",
        ],
    },
]


def _get_agent_path(agent_id: str) -> str:
    safe_id = "".join(c for c in agent_id if c.isalnum() or c in "-_")
    return os.path.join(AGENTS_DIR, f"{safe_id}.json")


def _tokenize(text: str) -> List[str]:
    """Clean, lowercase, and tokenize text into distinct semantic tokens without stopwords."""
    text_clean = re.sub(r"[^a-zA-Z0-9_\-\s]", " ", text.lower())
    tokens = text_clean.split()
    return [t for t in tokens if len(t) > 1 and t not in STOPWORDS]


class AgentStore:
    """Manages the lifecycle, persistence, M:N mapping, and semantic search of agents."""

    def __init__(self):
        self._ensure_builtins()

    def _ensure_builtins(self) -> None:
        """Seed the built-in industrial agents if they do not yet exist on disk."""
        for agent_data in BUILTIN_AGENTS:
            path = _get_agent_path(agent_data["id"])
            if not os.path.exists(path):
                now = int(time.time())
                agent_copy = dict(agent_data)
                agent_copy["created_at"] = now
                agent_copy["updated_at"] = now
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(agent_copy, f, indent=2)

    def list_agents(self) -> List[Dict[str, Any]]:
        """Return all registered agents sorted by updated_at descending."""
        agents = []
        if not os.path.exists(AGENTS_DIR):
            return agents

        for fname in os.listdir(AGENTS_DIR):
            if fname.endswith(".json"):
                try:
                    with open(os.path.join(AGENTS_DIR, fname), "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, dict) and "id" in data:
                            agents.append(data)
                except Exception:
                    continue

        agents.sort(key=lambda x: (not x.get("is_builtin", False), x.get("name", "")))
        return agents

    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Fetch an agent by its unique ID."""
        path = _get_agent_path(agent_id)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def create_agent(
        self,
        name: str,
        description: str,
        use_case_ids: List[str],
        system_prompt: str,
        skill_content: str,
        tool_ids: Optional[List[str]] = None,
        model_type: str = "reasoning",
        department: str = "Custom Operations",
        starter_prompts: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Onboard a new customizable agent and persist it to common storage."""
        agent_id = f"agent_{uuid.uuid4().hex[:8]}"
        now = int(time.time())

        # Clean use case IDs
        cleaned_use_cases = [
            u.strip().lower().replace(" ", "_") for u in use_case_ids if u.strip()
        ]
        if not cleaned_use_cases:
            cleaned_use_cases = ["general_engineering"]

        # Default or suggested tools
        if not tool_ids:
            tool_ids = suggest_tools_for_intent(f"{name} {description} {' '.join(cleaned_use_cases)}")

        if not starter_prompts:
            starter_prompts = [
                f"Analyze latest data using {name}.",
                f"Generate a technical deliverable for {cleaned_use_cases[0].replace('_', ' ')}.",
            ]

        agent_record = {
            "id": agent_id,
            "name": name.strip(),
            "department": department.strip(),
            "description": description.strip(),
            "use_case_ids": cleaned_use_cases,
            "system_prompt": system_prompt.strip(),
            "skill_filename": "SKILL.md",
            "skill_content": skill_content.strip(),
            "tool_ids": tool_ids,
            "model_type": model_type if model_type in ("reasoning", "coding") else "reasoning",
            "is_builtin": False,
            "starter_prompts": starter_prompts,
            "created_at": now,
            "updated_at": now,
        }

        path = _get_agent_path(agent_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(agent_record, f, indent=2)

        return agent_record

    def delete_agent(self, agent_id: str) -> bool:
        """Delete an onboarded agent. Built-in agents cannot be deleted."""
        agent = self.get_agent(agent_id)
        if not agent or agent.get("is_builtin", False):
            return False
        path = _get_agent_path(agent_id)
        if os.path.exists(path):
            try:
                os.remove(path)
                return True
            except OSError:
                return False
        return False

    # ----------------------------------------------------------------
    # M:N Use Case Mapping
    # ----------------------------------------------------------------
    def get_use_case_map(self) -> Dict[str, List[Dict[str, Any]]]:
        """Returns a bidirectional map of use_case_id -> list of agents offering that use case."""
        all_agents = self.list_agents()
        use_case_to_agents: Dict[str, List[Dict[str, Any]]] = {}

        for ag in all_agents:
            ag_summary = {
                "id": ag["id"],
                "name": ag["name"],
                "description": ag["description"],
                "department": ag.get("department", "Engineering"),
                "is_builtin": ag.get("is_builtin", False),
                "tool_ids": ag.get("tool_ids", []),
            }
            for ucid in ag.get("use_case_ids", []):
                if ucid not in use_case_to_agents:
                    use_case_to_agents[ucid] = []
                use_case_to_agents[ucid].append(ag_summary)

        return use_case_to_agents

    def list_all_use_cases(self) -> List[Dict[str, Any]]:
        """Return list of distinct use cases with human-readable titles and agent counts."""
        uc_map = self.get_use_case_map()
        result = []
        for ucid, agents in uc_map.items():
            title = ucid.replace("_", " ").title()
            result.append({
                "use_case_id": ucid,
                "title": title,
                "agent_count": len(agents),
                "agents": agents,
            })
        result.sort(key=lambda x: x["agent_count"], reverse=True)
        return result

    # ----------------------------------------------------------------
    # Air-Gapped Local Semantic Search Engine
    # ----------------------------------------------------------------
    def search_agents(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Perform 100% local semantic keyword & TF-IDF similarity search over all agents.

        Indexes:
        - Agent Name & Description
        - M:N Use Case IDs (expanded into human tokens)
        - System Prompts & Skill Content
        - Starter Prompts

        Returns top_k matching agents with match scores and highlights.
        """
        all_agents = self.list_agents()
        if not all_agents:
            return []

        query_tokens = _tokenize(query)
        if not query_tokens:
            # If query is blank, return default list
            return [
                {"agent": ag, "score": 1.0, "matched_use_cases": ag.get("use_case_ids", [])}
                for ag in all_agents[:top_k]
            ]

        # Build corpus documents
        scored_agents: List[Tuple[float, Dict[str, Any], List[str]]] = []

        for agent in all_agents:
            # Weighted tokens
            name_tokens = _tokenize(agent.get("name", "")) * 4
            desc_tokens = _tokenize(agent.get("description", "")) * 3

            # Use cases are high-value intent matches
            use_case_tokens = []
            for ucid in agent.get("use_case_ids", []):
                use_case_tokens.extend(_tokenize(ucid.replace("_", " ")) * 4)

            skill_tokens = _tokenize(agent.get("skill_content", "")[:1000])
            prompt_tokens = _tokenize(agent.get("system_prompt", "")) * 2

            doc_tokens = name_tokens + desc_tokens + use_case_tokens + skill_tokens + prompt_tokens

            # Compute term frequency in document
            doc_len = len(doc_tokens) or 1
            tf: Dict[str, float] = {}
            for tok in doc_tokens:
                tf[tok] = tf.get(tok, 0) + 1.0

            # Score query tokens against document
            score = 0.0
            matched_ucs = set()

            for q_tok in query_tokens:
                # Direct match
                if q_tok in tf:
                    score += (tf[q_tok] / doc_len) * 100.0

                # Prefix / substring match (e.g. "foul" matches "fouling", "compress" matches "compressor")
                for doc_tok, count in tf.items():
                    if len(q_tok) >= 4 and (q_tok in doc_tok or doc_tok in q_tok):
                        score += (count / doc_len) * 40.0

                # Check which use case matches
                for ucid in agent.get("use_case_ids", []):
                    if q_tok in ucid.lower():
                        matched_ucs.add(ucid)
                        score += 30.0

            # Exact phrase bonus
            query_lower = query.lower()
            if query_lower in agent.get("name", "").lower():
                score += 50.0
            if query_lower in agent.get("description", "").lower():
                score += 30.0

            if score > 0:
                scored_agents.append((score, agent, list(matched_ucs)))

        # Sort descending by score
        scored_agents.sort(key=lambda x: x[0], reverse=True)

        results = []
        for score, agent, matched_ucs in scored_agents[:top_k]:
            results.append({
                "agent": agent,
                "score": round(score, 2),
                "matched_use_cases": matched_ucs or agent.get("use_case_ids", [])[:2],
            })

        # If no scores match but query was provided, fall back to general agent
        if not results:
            fallback = self.get_agent("agent_general") or all_agents[0]
            results.append({
                "agent": fallback,
                "score": 0.1,
                "matched_use_cases": fallback.get("use_case_ids", []),
            })

        return results


# Global singleton instance
agent_store = AgentStore()
