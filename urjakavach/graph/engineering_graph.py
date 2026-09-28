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
        self.canonical_doc = doc
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
                    status=rel.status,
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
                        status=rel.status,
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
                "status": data.get("status", "OBSERVATION"),
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
        instruments = []
        valves = []

        for n, d in self.graph.nodes(data=True):
            if d.get("node_type") == "entity":
                c = d.get("entity_class", "")
                lbl = d.get("label", n)
                attrs = d.get("attributes", {})
                item = {
                    "id": n,
                    "class": c,
                    "label": lbl,
                    "bbox": d.get("bbox"),
                    "confidence": d.get("confidence", 1.0),
                    "attributes": attrs
                }
                entities.append(item)
                if c == "instrument" or any(lbl.startswith(pfx) for pfx in ("LT-", "PI-", "TI-", "TV-", "TR-", "FT-", "PT-")):
                    instruments.append(lbl)
                elif c == "valve" or any(lbl.startswith(pfx) for pfx in ("XV-", "LV-", "CV-", "FV-", "PSV-")):
                    valves.append(lbl)

        connections = []
        for u, v, d in self.graph.edges(data=True):
            if d.get("relation_type") == "CONNECTED_TO":
                connections.append({
                    "from": self.graph.nodes[u].get("label", u),
                    "to": self.graph.nodes[v].get("label", v),
                    "relation": d.get("relation_type"),
                    "status": d.get("status", "OBSERVATION"),
                    "evidence": d.get("evidence")
                })

        return {
            "document_id": self.doc_id,
            "metadata": self.metadata,
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
            "verified_entities": entities,
            "verified_instruments": sorted(list(set(instruments))),
            "verified_valves": sorted(list(set(valves))),
            "verified_connections": connections
        }

    def get_drawing_evidence_package(self) -> Dict[str, Any]:
        """Builds a complete, drawing-isolated evidence package for the local LLM."""
        if not hasattr(self, "canonical_doc") or not self.canonical_doc:
            return self.get_evidence_summary()

        doc = self.canonical_doc
        h = doc.metadata.original_height or 1000
        w = doc.metadata.original_width or 1000

        # 1. Regional OCR text grouping
        regional_ocr = {
            "title_block": [],
            "notes_and_standards": [],
            "drawing_diagram_area": []
        }
        notes_list = []
        specs_list = []

        for tb in doc.text_blocks:
            t = tb.text.strip()
            if not t:
                continue
            b = tb.bbox
            entry = {"text": t, "bbox": b.to_list(), "confidence": tb.confidence}
            
            # Categorize region
            if (b.y2 > h * 0.70 and b.x2 > w * 0.50) or (b.y1 < h * 0.15 and b.x2 > w * 0.40):
                regional_ocr["title_block"].append(entry)
            elif "note" in t.lower() or "spec" in t.lower() or "material" in t.lower() or "astm" in t.lower():
                regional_ocr["notes_and_standards"].append(entry)
                notes_list.append(t)
            else:
                regional_ocr["drawing_diagram_area"].append(entry)

            if any(k in t.lower() for k in ("astm", "cs", "carbon steel", "14c-ins", "spec", "bar(g)", "kg/cm")):
                specs_list.append(t)

        # 2. Discrete Entities & Attributes
        discrete_entities = []
        equipment_list = []
        instruments_list = []
        valves_list = []

        for ent in doc.entities:
            tag = ent.label or ent.id
            ent_type = ent.entity_class
            attrs = ent.attributes
            rec = {
                "id": ent.id,
                "tag": tag,
                "label": tag,
                "entity_class": ent_type,
                "type": ent_type,
                "attributes": attrs,
                "confidence": ent.confidence,
                "bbox": ent.bbox.to_list()
            }
            discrete_entities.append(rec)
            if ent_type in ("pump", "tank", "vessel", "heat_exchanger", "column", "compressor", "equipment"):
                equipment_list.append(rec)
            elif ent_type == "instrument" or any(tag.startswith(pfx) for pfx in ("LT-", "PI-", "TI-", "TV-", "TR-", "FT-")):
                instruments_list.append(rec)
            elif ent_type in ("valve", "pressure_safety_valve") or any(tag.startswith(pfx) for pfx in ("PSV-", "XV-", "LV-", "CV-", "FV-")):
                valves_list.append(rec)

        # 3. Streams & Boundaries
        stream_keywords = ["fuel supply", "steam in", "to process", "to flare", "condensate to drain", "drain", "flare", "feed", "effluent"]
        streams_list = []
        for tb in doc.text_blocks:
            t_clean = tb.text.strip().upper()
            if any(k in t_clean.lower() for k in stream_keywords):
                streams_list.append({
                    "name": t_clean,
                    "source": "ocr_text",
                    "bbox": tb.bbox.to_list()
                })

        # 4. Specifications & Facts
        spec_entries = []
        for ef in doc.evidence_facts:
            spec_entries.append({
                "fact": ef.fact,
                "confidence": ef.confidence,
                "evidence_text": ef.evidence_text or ef.fact,
                "status": ef.status,
                "source_region": ef.source_region
            })
        for s in specs_list:
            if not any(s in e["fact"] for e in spec_entries):
                spec_entries.append({
                    "fact": s,
                    "confidence": 0.95,
                    "evidence_text": s,
                    "status": "ENGINEERING_FACT"
                })

        # 5. Topological Observations vs Inferences
        topo_observations = []
        topo_inferences = []
        for rel in doc.relationships:
            src = next((e.label or e.id for e in doc.entities if e.id == rel.source_id), rel.source_id)
            tgt = next((e.label or e.id for e in doc.entities if e.id == rel.target_id), rel.target_id)
            item = {
                "source": src,
                "target": tgt,
                "source_entity": src,
                "target_entity": tgt,
                "relation": rel.relation_type,
                "relation_type": rel.relation_type,
                "confidence": rel.confidence,
                "status": rel.status,
                "evidence": rel.evidence
            }
            if rel.status == "INFERENCE" or rel.relation_type == "FLOWS_TO":
                topo_inferences.append(item)
            else:
                topo_observations.append(item)

        all_text = " ".join([tb.text for tb in doc.text_blocks])

        return {
            "document_id": doc.document_id,
            "metadata": {
                "document_type": doc.metadata.document_type,
                "title": doc.metadata.title,
                "unit_number": doc.metadata.unit_number,
                "drawing_number": doc.metadata.drawing_number,
                "system_name": doc.metadata.system_name or doc.metadata.title,
                "project_name": doc.metadata.project_name,
                "classification_confidence": doc.metadata.classification_confidence,
                "classification_evidence": doc.metadata.classification_evidence,
                "source_file": doc.metadata.source_file,
            },
            "discrete_entities": discrete_entities,
            "equipment": equipment_list,
            "instrument_list": instruments_list,
            "instrumentation": instruments_list,
            "valve_list": valves_list,
            "valves_and_safety": valves_list,
            "specifications": spec_entries,
            "specifications_and_measurements": specs_list,
            "streams_and_boundaries": streams_list,
            "notes_and_standards": notes_list,
            "topology_observations": topo_observations,
            "topology_inferences": topo_inferences,
            "all_ocr_text": all_text,
            "regional_ocr": {
                "title_block_snippets": [x["text"] for x in regional_ocr["title_block"][:8]],
                "notes_snippets": [x["text"] for x in regional_ocr["notes_and_standards"][:10]]
            },
            "evidence_facts": [f.model_dump() for f in doc.evidence_facts]
        }
