"""
Abstract interface for Vision Foundation Backbones (e.g. DINOv3).
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple
import numpy as np

class BaseVisualBackbone(ABC):
    """Abstract visual backbone providing dense spatial feature representations."""

    @abstractmethod
    def extract_dense_features(self, image_rgb: np.ndarray) -> np.ndarray:
        """
        Extracts dense spatial feature map.
        Returns:
            np.ndarray of shape (H_feat, W_feat, C_channels)
        """
        pass

    @abstractmethod
    def get_feature_dim(self) -> int:
        """Returns the channel dimension C of the feature representation."""
        pass

    @abstractmethod
    def get_patch_size(self) -> int:
        """Returns the spatial patch stride in pixels."""
        pass
