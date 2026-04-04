"""
Wake word detection configuration.
All tunable parameters in one place for easy experimentation.
"""

from dataclasses import dataclass, field
import json
from pathlib import Path


@dataclass
class WakeWordConfig:
    # Audio
    sample_rate: int = 16000

    # Framing
    frame_ms: float = 25.0       # frame duration in milliseconds
    hop_ms: float = 10.0         # hop between frames in milliseconds

    # DCT
    n_dct_coeffs: int = 13       # number of DCT coefficients to keep per frame

    # Utterance windowing
    utterance_duration_s: float = 1.5  # matches mean sample duration (1.4s) + margin

    # Random Fourier Features
    rff_dim: int = 2048           # dimension of RFF approximation
    rff_sigma: float = 0.0       # RBF kernel bandwidth (0 = auto via median heuristic)

    # Detection
    detection_threshold: float = 0.0  # MMD distance threshold (0 = auto from enrollment)
    detection_stride_ms: float = 160.0  # how often to check (ms)

    # Paths
    samples_dir: str = "samples"
    model_path: str = "model.json"

    @property
    def frame_samples(self) -> int:
        return int(self.sample_rate * self.frame_ms / 1000)

    @property
    def hop_samples(self) -> int:
        return int(self.sample_rate * self.hop_ms / 1000)

    @property
    def utterance_samples(self) -> int:
        return int(self.sample_rate * self.utterance_duration_s)

    @property
    def n_frames(self) -> int:
        """Number of frames in the fixed utterance window."""
        return 1 + (self.utterance_samples - self.frame_samples) // self.hop_samples

    @property
    def feature_dim(self) -> int:
        """Dimension of feature vector before RFF. 3x for static + delta + delta-delta."""
        return self.n_dct_coeffs * 3 * self.n_frames

    @property
    def detection_stride_samples(self) -> int:
        return int(self.sample_rate * self.detection_stride_ms / 1000)

    def save(self, path: str):
        with open(path, "w") as f:
            json.dump(self.__dict__, f, indent=2)

    @classmethod
    def load(cls, path: str) -> "WakeWordConfig":
        with open(path) as f:
            return cls(**json.load(f))

    def summary(self) -> str:
        return (
            f"Audio: {self.sample_rate}Hz\n"
            f"Frame: {self.frame_ms}ms ({self.frame_samples} samples), "
            f"hop: {self.hop_ms}ms ({self.hop_samples} samples)\n"
            f"DCT coefficients: {self.n_dct_coeffs} per frame\n"
            f"Utterance window: {self.utterance_duration_s}s → {self.n_frames} frames\n"
            f"Feature vector: {self.feature_dim}-dim → RFF {self.rff_dim}-dim\n"
            f"RBF σ: {'auto (median heuristic)' if self.rff_sigma == 0 else self.rff_sigma}\n"
            f"Detection stride: {self.detection_stride_ms}ms\n"
            f"Threshold: {'auto' if self.detection_threshold == 0 else self.detection_threshold}"
        )
