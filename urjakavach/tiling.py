"""
High-Resolution Engineering Drawing Preservation and Tiling Engine.
Enables high-resolution tiling without downsampling, and maps detections
back to global original coordinates with rigorous provenance.
"""

from typing import List, Dict, Any, Tuple
import numpy as np
from PIL import Image

class ImageTile:
    """Represents a high-resolution sub-tile with global coordinate mapping."""
    def __init__(self, tile_id: str, image_rgb: np.ndarray, x_offset: int, y_offset: int, width: int, height: int):
        self.tile_id = tile_id
        self.image_rgb = image_rgb
        self.x_offset = x_offset
        self.y_offset = y_offset
        self.width = width
        self.height = height

    def local_to_global_bbox(self, local_bbox: List[int]) -> List[int]:
        """Maps local [x1, y1, x2, y2] tile coordinates to original global drawing coordinates."""
        return [
            local_bbox[0] + self.x_offset,
            local_bbox[1] + self.y_offset,
            local_bbox[2] + self.x_offset,
            local_bbox[3] + self.y_offset,
        ]

    def local_to_global_point(self, x: float, y: float) -> Tuple[float, float]:
        """Maps local (x, y) point to original global coordinates."""
        return (x + self.x_offset, y + self.y_offset)

class HighResTiler:
    """Generates overlapping tiles for multi-gigapixel engineering drawings."""

    def __init__(self, tile_size: int = 1024, overlap_px: int = 128):
        self.tile_size = tile_size
        self.overlap_px = overlap_px

    def tile_image(self, full_image_rgb: np.ndarray) -> List[ImageTile]:
        h, w = full_image_rgb.shape[:2]
        
        # If image fits in single tile, return as single global tile
        if w <= self.tile_size and h <= self.tile_size:
            return [ImageTile("tile_0_0", full_image_rgb, 0, 0, w, h)]

        stride = self.tile_size - self.overlap_px
        tiles = []
        tile_r = 0

        for y in range(0, h, stride):
            tile_c = 0
            for x in range(0, w, stride):
                x_end = min(x + self.tile_size, w)
                y_end = min(y + self.tile_size, h)
                
                # Adjust start if at boundary
                x_start = max(0, x_end - self.tile_size)
                y_start = max(0, y_end - self.tile_size)

                tile_crop = full_image_rgb[y_start:y_end, x_start:x_end]
                tile_id = f"tile_r{tile_r}_c{tile_c}"
                tiles.append(ImageTile(tile_id, tile_crop, x_start, y_start, x_end - x_start, y_end - y_start))
                tile_c += 1
            tile_r += 1

        return tiles
