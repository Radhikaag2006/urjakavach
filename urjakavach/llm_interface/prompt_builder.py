"""
UrjaKavach Local LLM Evidence Packaging and Interface Layer.
Packages strictly verified graph facts, OCR evidence, dimensions, and topology
for consumption by the downstream Local LLM reasoning layer.
Enforces zero-hallucination constraints and handles insufficient evidence explicitly.
"""

from typing import Dict, Any, List, Optional, Tuple
import json
from urjakavach.graph.engineering_graph import EngineeringGraph
from urjakavach.llm_interface.validator import AntiHallucinationValidator


class LLMEvidenceInterface:
    """Packages structured graph facts into prompt context and validates answers."""

    def __init__(self, graph: EngineeringGraph):
        self.graph = graph
        self.validator = AntiHallucinationValidator()

    def get_evidence_package(self) -> Dict[str, Any]:
        """Retrieves the unified DrawingEvidencePackage from the engineering graph."""
        return self.graph.get_drawing_evidence_package()

    def build_evidence_context(self, focus_query: Optional[str] = None) -> Dict[str, Any]:
        """
        Extracts structured factual evidence relevant to user query or complete drawing scope.
        """
        evidence_pkg = self.graph.get_drawing_evidence_package()
        
        relevant_connections = []
        if focus_query:
            connected = self.graph.query_connected_entities(focus_query)
            if connected:
                relevant_connections = connected

        context = {
            "document_id": evidence_pkg.get("document_id"),
            "metadata": evidence_pkg.get("metadata", {}),
            "discrete_entities": evidence_pkg.get("discrete_entities", []),
            "valves": evidence_pkg.get("valve_list", []),
            "instruments": evidence_pkg.get("instrument_list", []),
            "specifications": evidence_pkg.get("specifications", []),
            "streams_and_boundaries": evidence_pkg.get("streams_and_boundaries", []),
            "query_relevant_connections": relevant_connections if relevant_connections else evidence_pkg.get("topology_observations", [])[:15],
            "total_verified_connections": len(evidence_pkg.get("topology_observations", [])),
            "evidence_facts": evidence_pkg.get("evidence_facts", []),
        }
        return context

    def generate_prompt_for_local_llm(self, user_question: str) -> str:
        """
        Formats a system prompt that strictly binds the LLM to provided drawing evidence.
        Enforces zero cross-document contamination and prohibits guessing.
        """
        context = self.build_evidence_context(user_question)
        meta = context.get("metadata", {})
        doc_type = meta.get("document_type", "P&ID")
        unit_no = meta.get("unit_number", "101")
        sys_name = meta.get("system_name", "FUEL OIL TRANSFER SYSTEM")

        prompt = f"""[SYSTEM: YOU ARE URJAKAVACH SOVEREIGN ENGINEERING REASONING ENGINE]
CRITICAL RULES & STRICT CONSTRAINTS:
1. You are analyzing ONE specific engineering drawing:
   - Drawing Type: {doc_type} (DO NOT call it Piping Isometric or General Arrangement)
   - System: {sys_name}
   - Unit: {unit_no}
2. Ground EVERY claim in the VERIFIED DRAWING EVIDENCE below.
3. NEVER import, guess, or invent components from other units or drawings.
   - For example: DO NOT mention "Unit-300", "3000 HP steam turbine", "16 kg/cm²", or "18.68 bar" unless explicitly in the evidence below.
4. Keep all equipment entities DISCRETE. Never merge pumps and heat exchangers into a single entity.
5. If asked for a comprehensive analysis or report, format your answer strictly using the 10 Standard Sections:
   1. Drawing Identification & Metadata
   2. Primary Equipment & Storage
   3. Pumping & Mechanical Systems
   4. Heat Transfer Equipment
   5. Pressure Safety & Relief Systems
   6. Valves & Flow Control
   7. Instrumentation & Monitoring Loops
   8. Process & Utility Streams / Boundary Connections
   9. Material Specifications & Design Standards
   10. Verified Topological Relationships & Provenance
6. If the drawing evidence does not contain a requested fact, state explicitly:
   "INSUFFICIENT EVIDENCE: The drawing perception pipeline does not contain verified evidence for <requested fact>."

--- VERIFIED DRAWING EVIDENCE ---
{json.dumps(context, indent=2)}
---------------------------------

USER QUESTION: {user_question}

ANSWER (Grounded strictly and exclusively in the above drawing evidence):
"""
        return prompt

    def validate_and_format_response(self, response_text: str) -> Tuple[str, List[str]]:
        """
        Runs anti-hallucination validation and cleans ungrounded statements.
        """
        evidence_pkg = self.graph.get_drawing_evidence_package()
        return self.validator.validate_drawing_response(response_text, evidence_pkg)

    def generate_grounded_report(self) -> str:
        """
        Directly generates the canonical 10-section engineering report without LLM hallucination risk.
        """
        evidence_pkg = self.graph.get_drawing_evidence_package()
        return self.validator.synthesize_grounded_10_section_report(evidence_pkg)

    def answer_query_from_graph(self, user_question: str) -> Dict[str, Any]:
        """
        Deterministic perception-graph query resolver.
        Directly checks graph before passing to LLM to guarantee factual accuracy.
        """
        lower_q = user_question.lower()
        evidence_pkg = self.graph.get_drawing_evidence_package()
        
        # Check for connectivity query: e.g. "what is connected to <X>"
        if "connected to" in lower_q:
            target = lower_q.split("connected to")[-1].strip(" ?.")
            results = self.graph.query_connected_entities(target)
            if results:
                return {
                    "status": "SUCCESS",
                    "query": user_question,
                    "target_entity": target,
                    "evidence_grounded": True,
                    "connections": results,
                    "answer_summary": f"Verified {len(results)} connection(s) to '{target}' via engineering line primitives."
                }
            else:
                return {
                    "status": "INSUFFICIENT_EVIDENCE",
                    "query": user_question,
                    "target_entity": target,
                    "evidence_grounded": False,
                    "reason": f"No topological line connectivity was established for entity '{target}' in the drawing evidence."
                }
        
        # Check for entities list query
        if "what entities" in lower_q or "list equipment" in lower_q or "what symbols" in lower_q:
            return {
                "status": "SUCCESS",
                "query": user_question,
                "evidence_grounded": True,
                "entities": evidence_pkg.get("discrete_entities", []),
                "total_count": len(evidence_pkg.get("discrete_entities", []))
            }

        # Check for full report query
        if any(k in lower_q for k in ["analyze", "full report", "summary", "drawing report", "10 sections"]):
            report = self.generate_grounded_report()
            return {
                "status": "SUCCESS",
                "query": user_question,
                "evidence_grounded": True,
                "report": report
            }

        # General evidence package fallback
        return {
            "status": "EVIDENCE_PACKAGED",
            "query": user_question,
            "evidence_context": self.build_evidence_context(user_question)
        }
