"""Segmentation modules."""

from urjakavach.cv_branch.segmentation.base import BaseSegmentor
from urjakavach.cv_branch.segmentation.sam3 import SAM3Segmentor

__all__ = ["BaseSegmentor", "SAM3Segmentor"]
