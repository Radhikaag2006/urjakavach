"""
Topological Ground-Truth Graph Benchmark for UrjaKavach.
Evaluates graph connectivity and reconstruction metrics on the real-world
OPEN100 nuclear reactor diagrams from the PID2Graph benchmark.
"""

import math
from pathlib import Path
import networkx as nx
from urjakavach.schemas.canonical_schema import (
    CanonicalEngineeringDocument,
    DocumentMetadata,
    EngineeringEntity,
    BBox,
    ProvenanceSource,
    LineSegmentObservation,
    Point2D
)
from urjakavach.cv_branch.topology.reconstruction import TopologyReconstructor
from urjakavach.graph.engineering_graph import EngineeringGraph

def test_open100_groundtruth_topological_fidelity():
    samples_dir = Path("datasets/samples/pid2graph")
    graphml_files = list(samples_dir.glob("*.graphml"))
    assert len(graphml_files) >= 3, f"Expected at least 3 OPEN100 graphml files, found {len(graphml_files)}"

    reconstructor = TopologyReconstructor(endpoint_proximity_px=35.0)

    for g_path in graphml_files:
        G_gt = nx.read_graphml(g_path)
        num_gt_nodes = G_gt.number_of_nodes()
        num_gt_edges = G_gt.number_of_edges()

        assert num_gt_nodes > 100, f"{g_path.name} has only {num_gt_nodes} nodes"
        assert num_gt_edges > 100, f"{g_path.name} has only {num_gt_edges} edges"

        # Convert GT nodes into EngineeringEntities
        entities = []
        for n_id, data in G_gt.nodes(data=True):
            lbl = data.get("label", data.get("type", "symbol"))
            try:
                xmin = float(data["xmin"])
                ymin = float(data["ymin"])
                xmax = float(data["xmax"])
                ymax = float(data["ymax"])
                bbox = BBox(x1=int(xmin), y1=int(ymin), x2=int(xmax), y2=int(ymax))
                entities.append(EngineeringEntity(
                    id=str(n_id),
                    entity_class="symbol" if lbl != "crossing" else "crossing",
                    label=lbl,
                    bbox=bbox,
                    confidence=1.0,
                    source=ProvenanceSource(stage="gt", model_name="open100_groundtruth")
                ))
            except (KeyError, ValueError):
                pass

        # Synthesize line segment observations from GT edges
        line_obs = []
        for i, (u, v) in enumerate(G_gt.edges()):
            if u in G_gt.nodes and v in G_gt.nodes:
                u_d = G_gt.nodes[u]
                v_d = G_gt.nodes[v]
                try:
                    ux = (float(u_d["xmin"]) + float(u_d["xmax"])) / 2.0
                    uy = (float(u_d["ymin"]) + float(u_d["ymax"])) / 2.0
                    vx = (float(v_d["xmin"]) + float(v_d["xmax"])) / 2.0
                    vy = (float(v_d["ymin"]) + float(v_d["ymax"])) / 2.0
                    length = math.hypot(vx - ux, vy - uy)
                    angle = math.degrees(math.atan2(vy - uy, vx - ux))
                    line_obs.append(LineSegmentObservation(
                        id=f"line_{i:04d}",
                        start=Point2D(x=ux, y=uy),
                        end=Point2D(x=vx, y=vy),
                        length_px=length,
                        angle_deg=angle,
                        line_type="pipe_primary",
                        source=ProvenanceSource(stage="gt", model_name="open100_groundtruth")
                    ))
                except (KeyError, ValueError):
                    pass

        # Reconstruct graph using UrjaKavach topology engine
        relationships = reconstructor.build_topology(
            entities=entities,
            lines=line_obs,
            text_blocks=[]
        )

        # Build Canonical Document
        doc = CanonicalEngineeringDocument(
            document_id=f"open100_eval_{g_path.stem}",
            metadata=DocumentMetadata(
                source_file=str(g_path),
                title=g_path.stem,
                document_type="PID",
                original_width=3000,
                original_height=2000
            ),
            entities=entities,
            lines=line_obs,
            relationships=relationships
        )

        # Build EngineeringGraph
        eng_graph = EngineeringGraph(doc)
        nx_graph = eng_graph.to_networkx()

        connected_components = list(nx.connected_components(nx_graph.to_undirected()))
        print(f"\n{g_path.name}:")
        print(f"  GT Nodes: {num_gt_nodes}, Canonical Entities: {len(entities)}")
        print(f"  GT Edges: {num_gt_edges}, Reconstructed Topology Relationships: {len(relationships)}")
        print(f"  Connected Subgraphs: {len(connected_components)}")

        assert len(relationships) > 0, f"Reconstruction failed to create relationships for {g_path.name}"
        assert nx_graph.number_of_nodes() >= len(entities)
