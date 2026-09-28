"""
UrjaKavach Engineering Graph Engine.
Constructs an explicit, queryable topological graph representation (NetworkX)
over the Canonical Engineering Document.
Can be queried independently of any LLM.
"""

from typing import List, Dict, Any, Optional, Set, Tuple
import networkx as nx
from urjakavach.schemas.canonical_schema import CanonicalEngineeringDocument

class EngineeringGraph:
    """Explicit multi-relational engineering graph with independent query capability."""

    def __init__(self, canonical_doc: Optional[CanonicalEngineeringDocument] = None):
        self.graph = nx.MultiDiGraph()
        self.doc_id = ""
        self.metadata = {}
        if canonical_doc:
            self.load_from_canonical(canonical_doc)

    def load_from_canonical(self, doc: CanonicalEngineeringDocument):
        """Loads canonical document entities, lines, text, and relationships into graph nodes & edges."""
        self.graph.clear()
        self.doc_id = doc.document_id
        self.metadata = doc.metadata.model_dump()

        # 1. Add Entity Nodes
        for ent in doc.entities:
            self.graph.add_node(
                ent.id,
                node_type="entity",
                entity_class=ent.entity_class,
                label=ent.label or ent.id,
                bbox=ent.bbox.to_list(),
                confidence=ent.confidence,
                attributes=ent.attributes,
                source_model=ent.source.model_name
            )

        # 2. Add Line Segment / Pipe Nodes
        for line in doc.lines:
            self.graph.add_node(
                line.id,
                node_type="pipe_line",
                line_type=line.line_type,
                length_px=line.length_px,
                angle_deg=line.angle_deg,
                is_orthogonal=line.is_orthogonal,
                confidence=line.confidence,
                start=[line.start.x, line.start.y],
                end=[line.end.x, line.end.y]
            )

        # 3. Add Text Block Nodes
        for txt in doc.text_blocks:
            self.graph.add_node(
                txt.id,
                node_type="text_label",
                text=txt.text,
                block_type=txt.block_type,
                bbox=txt.bbox.to_list(),
                confidence=txt.confidence
            )

        # 4. Add Table Nodes
        for tbl in doc.tables:
            self.graph.add_node(
                tbl.id,
                node_type="table",
                bbox=tbl.bbox.to_list(),
                html_snippet=tbl.table_html[:200]
            )

        # 5. Add Edges (Relationships)
        for rel in doc.relationships:
            if self.graph.has_node(rel.source_id) and self.graph.has_node(rel.target_id):
                self.graph.add_edge(
                    rel.source_id,
                    rel.target_id,
                    key=rel.id,
                    relation_type=rel.relation_type,
                    confidence=rel.confidence,
                    evidence=rel.evidence
                )
                # If relationship is symmetric (CONNECTED_TO, INTERSECTS), add reverse edge
                if rel.relation_type in ("CONNECTED_TO", "INTERSECTS"):
                    self.graph.add_edge(
                        rel.target_id,
                        rel.source_id,
                        key=f"{rel.id}_rev",
                        relation_type=rel.relation_type,
                        confidence=rel.confidence,
                        evidence=rel.evidence
                    )

    def find_entity_by_label_or_id(self, query_str: str) -> Optional[str]:
        """Finds node ID matching label, tag, or ID string case-insensitively."""
        q = query_str.strip().lower()
        if q in self.graph.nodes:
            return q
        for node_id, data in self.graph.nodes(data=True):
            if data.get("label") and data.get("label").strip().lower() == q:
                return node_id
            if q in node_id.lower():
                return node_id
        return None

    def query_connected_entities(self, query_str: str) -> List[Dict[str, Any]]:
        """
        Answers query: "What is connected to <X>?" purely from graph evidence.
        """
        node_id = self.find_entity_by_label_or_id(query_str)
        if not node_id:
            return []

        results = []
        for u, v, data in self.graph.out_edges(node_id, data=True):
            target_data = self.graph.nodes[v]
            results.append({
                "source_id": node_id,
                "source_label": self.graph.nodes[node_id].get("label", node_id),
                "relationship": data.get("relation_type"),
                "connected_id": v,
                "connected_label": target_data.get("label", target_data.get("text", v)),
                "connected_type": target_data.get("node_type", "unknown"),
                "confidence": data.get("confidence", 1.0),
                "evidence": data.get("evidence", {})
            })
        return results

    def query_flow_path(self, start_query: str, end_query: str) -> Optional[List[Dict[str, Any]]]:
        """Finds shortest topological path between two components."""
        start_id = self.find_entity_by_label_or_id(start_query)
        end_id = self.find_entity_by_label_or_id(end_query)
        if not start_id or not end_id:
            return None

        try:
            path_nodes = nx.shortest_path(self.graph, source=start_id, target=end_id)
            path_info = []
            for n in path_nodes:
                ndata = self.graph.nodes[n]
                path_info.append({
                    "id": n,
                    "label": ndata.get("label", ndata.get("text", n)),
                    "type": ndata.get("node_type", "unknown")
                })
            return path_info
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    def to_networkx(self) -> nx.MultiDiGraph:
        """Returns the underlying NetworkX MultiDiGraph instance."""
        return self.graph

    def get_evidence_summary(self) -> Dict[str, Any]:
        """Summarizes all strictly verified graph facts for LLM consumption."""
        entities = []
        for n, d in self.graph.nodes(data=True):
            if d.get("node_type") == "entity":
                entities.append({
                    "id": n,
                    "class": d.get("entity_class"),
                    "label": d.get("label"),
                    "bbox": d.get("bbox")
                })

        connections = []
        for u, v, d in self.graph.edges(data=True):
            if d.get("relation_type") == "CONNECTED_TO":
                connections.append({
                    "from": self.graph.nodes[u].get("label", u),
                    "to": self.graph.nodes[v].get("label", v),
                    "relation": d.get("relation_type"),
                    "evidence": d.get("evidence")
                })

        return {
            "document_id": self.doc_id,
            "metadata": self.metadata,
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
            "verified_entities": entities,
            "verified_connections": connections
        }
