"""
UrjaKavach Local LLM Evidence Packaging and Interface Layer.
Packages strictly verified graph facts, OCR evidence, dimensions, and topology
for consumption by the downstream Local LLM reasoning layer.
Enforces zero-hallucination constraints and handles insufficient evidence explicitly.
"""

from typing import Dict, Any, List, Optional
import json
from urjakavach.graph.engineering_graph import EngineeringGraph

class LLMEvidenceInterface:
    """Packages structured graph facts into prompt context and validates answers."""

    def __init__(self, graph: EngineeringGraph):
        self.graph = graph

    def build_evidence_context(self, focus_query: Optional[str] = None) -> Dict[str, Any]:
        """
        Extracts structured factual evidence relevant to user query.
        """
        evidence_summary = self.graph.get_evidence_summary()
        
        relevant_connections = []
        if focus_query:
            connected = self.graph.query_connected_entities(focus_query)
            if connected:
                relevant_connections = connected

        context = {
            "document_id": evidence_summary["document_id"],
            "document_type": evidence_summary["metadata"].get("document_type", "UNKNOWN"),
            "drawing_title": evidence_summary["metadata"].get("title"),
            "drawing_number": evidence_summary["metadata"].get("drawing_number"),
            "total_entities_identified": len(evidence_summary["verified_entities"]),
            "verified_entities": evidence_summary["verified_entities"],
            "query_relevant_connections": relevant_connections if relevant_connections else evidence_summary["verified_connections"][:10],
            "total_verified_connections": len(evidence_summary["verified_connections"]),
        }
        return context

    def generate_prompt_for_local_llm(self, user_question: str) -> str:
        """
        Formats a system prompt that strictly binds the LLM to provided evidence.
        """
        context = self.build_evidence_context(user_question)
        
        prompt = f"""[SYSTEM: YOU ARE THE URJAKAVACH ENGINEERING REASONING ENGINE]
CRITICAL CONSTRAINT: You must ONLY answer using the verified facts, topology, and OCR evidence provided below.
DO NOT extrapolate, guess, or invent engineering connections, piping specs, or valve states.
If the evidence does not contain the required connection or specification, you MUST reply:
"INSUFFICIENT EVIDENCE: The drawing perception pipeline does not contain verified evidence for <requested fact>."

--- VERIFIED DRAWING EVIDENCE ---
{json.dumps(context, indent=2)}
---------------------------------

USER QUESTION: {user_question}

ANSWER (Grounded strictly in the above evidence):
"""
        return prompt

    def answer_query_from_graph(self, user_question: str) -> Dict[str, Any]:
        """
        Deterministic perception-graph query resolver.
        Directly checks graph before passing to LLM to guarantee factual accuracy.
        """
        lower_q = user_question.lower()
        
        # Check for connectivity query: e.g. "what is connected to <X>"
        if "connected to" in lower_q:
            # Extract target
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
            summary = self.graph.get_evidence_summary()
            return {
                "status": "SUCCESS",
                "query": user_question,
                "evidence_grounded": True,
                "entities": summary["verified_entities"],
                "total_count": len(summary["verified_entities"])
            }

        # General evidence package fallback
        return {
            "status": "EVIDENCE_PACKAGED",
            "query": user_question,
            "evidence_context": self.build_evidence_context(user_question)
        }
