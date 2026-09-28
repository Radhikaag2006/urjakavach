"""Visual backbone modules."""

from urjakavach.cv_branch.backbone.base import BaseVisualBackbone
from urjakavach.cv_branch.backbone.dinov3 import DINOv3Backbone

__all__ = ["BaseVisualBackbone", "DINOv3Backbone"]
