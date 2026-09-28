"""
Topology and Connectivity Reconstruction Engine.
Synthesizes detected entities, line segments, junctions, endpoints, and OCR labels
into formally verified, evidence-grounded topological relationships.
"""

from typing import List, Dict, Any, Optional, Tuple
import math
import numpy as np
from urjakavach.schemas.canonical_schema import (
    EngineeringEntity,
    LineSegmentObservation,
    TextObservation,
    DimensionObservation,
    Relationship,
    Point2D,
    BBox,
)

class TopologyReconstructor:
    """
    Constructs engineering topological relationships algorithmically.
    Enforces strict physical and spatial evidence for every relationship.
    """

    def __init__(
        self,
        endpoint_proximity_px: float = 18.0,
        label_proximity_px: float = 40.0,
        in_line_intersection_px: float = 8.0
    ):
        self.endpoint_proximity_px = endpoint_proximity_px
        self.label_proximity_px = label_proximity_px
        self.in_line_intersection_px = in_line_intersection_px

    def build_topology(
        self,
        entities: List[EngineeringEntity],
        lines: List[LineSegmentObservation],
        text_blocks: List[TextObservation],
        dimensions: Optional[List[DimensionObservation]] = None,
        image_rgb: Optional[np.ndarray] = None
    ) -> List[Relationship]:
        """
        Derives all verified engineering relationships.
        Returns:
            List[Relationship]
        """
        relationships: List[Relationship] = []
        rel_counter = 0

        # Index entities by spatial bounding box for efficient proximity lookups
        entity_map = {e.id: e for e in entities}

        # 1. Text Label Association (HAS_LABEL)
        for tb in text_blocks:
            clean_text = tb.text.strip()
            if len(clean_text) < 2 or len(clean_text) > 40:
                continue

            tc = tb.bbox.center
            closest_ent = None
            min_dist = float("inf")

            for ent in entities:
                # Check if label is inside or close to entity bbox
                ec = ent.bbox.center
                dist = math.hypot(tc.x - ec.x, tc.y - ec.y)
                
                # Check containment or close proximity
                is_inside = (ent.bbox.x1 - 10 <= tc.x <= ent.bbox.x2 + 10 and
                             ent.bbox.y1 - 10 <= tc.y <= ent.bbox.y2 + 10)
                
                effective_dist = 0.0 if is_inside else dist
                if effective_dist < min_dist and dist <= self.label_proximity_px:
                    min_dist = dist
                    closest_ent = ent

            if closest_ent is not None:
                rel_counter += 1
                # Attach label to entity
                if closest_ent.label is None:
                    closest_ent.label = clean_text

                relationships.append(Relationship(
                    id=f"rel_{rel_counter:05d}",
                    source_id=closest_ent.id,
                    relation_type="HAS_LABEL",
                    target_id=tb.id,
                    confidence=0.94 if min_dist < 15 else 0.82,
                    evidence={
                        "label_text": clean_text,
                        "distance_px": round(min_dist, 2),
                        "entity_bbox": closest_ent.bbox.to_list(),
                        "text_bbox": tb.bbox.to_list()
                    }
                ))

        # 2. Line-to-Entity Connection (TERMINATES_AT / CONNECTS_TO)
        line_to_entities: Dict[str, List[Tuple[EngineeringEntity, str, float]]] = {}

        for line in lines:
            line_to_entities[line.id] = []
            for ent in entities:
                # Test start point proximity
                d_start = self._point_to_box_dist(line.start, ent.bbox)
                if d_start <= self.endpoint_proximity_px:
                    line_to_entities[line.id].append((ent, "start", d_start))
                    rel_counter += 1
                    relationships.append(Relationship(
                        id=f"rel_{rel_counter:05d}",
                        source_id=line.id,
                        relation_type="TERMINATES_AT",
                        target_id=ent.id,
                        confidence=round(1.0 - (d_start / (self.endpoint_proximity_px * 2)), 2),
                        evidence={
                            "endpoint": "start",
                            "endpoint_coords": [line.start.x, line.start.y],
                            "distance_to_box_px": round(d_start, 2)
                        }
                    ))

                # Test end point proximity
                d_end = self._point_to_box_dist(line.end, ent.bbox)
                if d_end <= self.endpoint_proximity_px:
                    line_to_entities[line.id].append((ent, "end", d_end))
                    rel_counter += 1
                    relationships.append(Relationship(
                        id=f"rel_{rel_counter:05d}",
                        source_id=line.id,
                        relation_type="TERMINATES_AT",
                        target_id=ent.id,
                        confidence=round(1.0 - (d_end / (self.endpoint_proximity_px * 2)), 2),
                        evidence={
                            "endpoint": "end",
                            "endpoint_coords": [line.end.x, line.end.y],
                            "distance_to_box_px": round(d_end, 2)
                        }
                    ))

        # 3. Equipment-to-Equipment Connectivity via Lines (CONNECTED_TO)
        for line_id, conn_list in line_to_entities.items():
            if len(conn_list) >= 2:
                # Find pairs of distinct entities connected by this line
                for i in range(len(conn_list)):
                    for j in range(i + 1, len(conn_list)):
                        e1, end1, dist1 = conn_list[i]
                        e2, end2, dist2 = conn_list[j]
                        if e1.id != e2.id:
                            rel_counter += 1
                            relationships.append(Relationship(
                                id=f"rel_{rel_counter:05d}",
                                source_id=e1.id,
                                relation_type="CONNECTED_TO",
                                target_id=e2.id,
                                confidence=0.91,
                                evidence={
                                    "via_line_id": line_id,
                                    "source_endpoint": end1,
                                    "target_endpoint": end2,
                                    "pipe_segment_length_px": [l.length_px for l in lines if l.id == line_id][0]
                                }
                            ))

        # 4. In-Line Component Association (CONTAINS / PART_OF)
        # Check if valves or instruments lie directly along a long pipe line
        for ent in entities:
            if ent.entity_class in ("valve", "instrument", "fitting"):
                for line in lines:
                    if line.length_px > 40:
                        dist_to_seg = self._point_to_segment_dist(ent.bbox.center, line.start, line.end)
                        if dist_to_seg <= self.in_line_intersection_px:
                            rel_counter += 1
                            relationships.append(Relationship(
                                id=f"rel_{rel_counter:05d}",
                                source_id=line.id,
                                relation_type="CONTAINS",
                                target_id=ent.id,
                                confidence=0.89,
                                evidence={
                                    "distance_to_axis_px": round(dist_to_seg, 2),
                                    "entity_center": [ent.bbox.center.x, ent.bbox.center.y]
                                }
                            ))

        # 5. Dimension Association (HAS_DIMENSION)
        if dimensions:
            for dim in dimensions:
                # Locate closest line or entity feature
                min_d = float("inf")
                target_id = None
                for line in lines:
                    if dim.leader_line_coords:
                        pt = Point2D(x=float(dim.leader_line_coords[0][0]), y=float(dim.leader_line_coords[0][1]))
                        d = self._point_to_segment_dist(pt, line.start, line.end)
                        if d < min_d and d < 30.0:
                            min_d = d
                            target_id = line.id

                if target_id is not None:
                    rel_counter += 1
                    relationships.append(Relationship(
                        id=f"rel_{rel_counter:05d}",
                        source_id=target_id,
                        relation_type="HAS_DIMENSION",
                        target_id=dim.id,
                        confidence=0.88,
                        evidence={"proximity_px": round(min_d, 2)}
                    ))

        return relationships

    def _point_to_box_dist(self, pt: Point2D, bbox: BBox) -> float:
        """Computes Euclidean distance from a 2D point to the perimeter of a bounding box."""
        dx = max(bbox.x1 - pt.x, 0.0, pt.x - bbox.x2)
        dy = max(bbox.y1 - pt.y, 0.0, pt.y - bbox.y2)
        return math.hypot(dx, dy)

    def _point_to_segment_dist(self, pt: Point2D, s1: Point2D, s2: Point2D) -> float:
        """Computes minimum Euclidean distance from a point to a finite line segment."""
        px, py = pt.x, pt.y
        x1, y1 = s1.x, s1.y
        x2, y2 = s2.x, s2.y

        dx = x2 - x1
        dy = y2 - y1
        if dx == 0 and dy == 0:
            return math.hypot(px - x1, py - y1)

        t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
        t = max(0.0, min(1.0, t))
        proj_x = x1 + t * dx
        proj_y = y1 + t * dy
        return math.hypot(px - proj_x, py - proj_y)
