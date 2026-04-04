"""
Random Fourier Features (standard + Fastfood structured) + kernel mean embedding + MMD.
"""

import numpy as np
from sklearn.kernel_approximation import RBFSampler
from scipy.spatial.distance import pdist
from scipy.linalg import hadamard
from config import WakeWordConfig


def median_heuristic(features: np.ndarray, max_samples: int = 5000) -> float:
    if len(features) > max_samples:
        idx = np.random.choice(len(features), max_samples, replace=False)
        features = features[idx]
    dists = pdist(features, metric="euclidean")
    sigma = float(np.median(dists)) / np.sqrt(2.0)
    return max(sigma, 1e-6)


def sigma_to_gamma(sigma: float) -> float:
    return 1.0 / (2.0 * sigma ** 2)


# ── Fastfood Structured RFF ─────────────────────────────────────────────────
# O(D log D) instead of O(D²) for the RFF transform.
# Uses Walsh-Hadamard + diagonal Gaussian + permutation.

class FastfoodRFF:
    """
    Structured RFF using the Fastfood approximation.
    φ(x) = √(2/D) · cos(SHGΠx / σ + b)

    Where:
    - Π = random permutation
    - G = diagonal with entries ~ N(0,1)
    - H = Walsh-Hadamard matrix (applied via fast transform, O(d log d))
    - S = diagonal scaling to match Gaussian kernel
    - b = random phase ~ Uniform(0, 2π)

    For input dim d not a power of 2, zero-pads to next power of 2.
    For D > d, stacks multiple independent Fastfood blocks.
    """

    def __init__(self, input_dim: int, rff_dim: int, sigma: float, seed: int = 42):
        self.input_dim = input_dim
        self.rff_dim = rff_dim
        self.sigma = sigma
        self.gamma = sigma_to_gamma(sigma)

        rng = np.random.RandomState(seed)

        # Pad input dim to next power of 2
        self.d = 1 << (input_dim - 1).bit_length()
        # Number of Fastfood blocks needed
        self.n_blocks = max(1, (rff_dim + self.d - 1) // self.d)
        actual_dim = self.n_blocks * self.d

        # Pre-generate parameters for each block
        self.perms = []   # permutation indices
        self.G = []       # diagonal Gaussian
        self.S = []       # diagonal scaling
        self.b = rng.uniform(0, 2 * np.pi, actual_dim).astype(np.float32)

        for _ in range(self.n_blocks):
            self.perms.append(rng.permutation(self.d))
            g = rng.randn(self.d).astype(np.float32)
            self.G.append(g)
            # S_ii = ||g||_2 / sqrt(d) * chi_draw (simplified: just scale by sigma)
            s = np.sqrt(self.d) * rng.chisquare(self.d, self.d).astype(np.float32) ** 0.5 / self.d
            self.S.append(s / sigma)

        self.scale = np.sqrt(2.0 / rff_dim).astype(np.float32)

        # For sklearn compatibility
        self.n_components = rff_dim

    def _fwht(self, x: np.ndarray) -> np.ndarray:
        """Fast Walsh-Hadamard Transform (in-place, iterative)."""
        n = len(x)
        h = 1
        while h < n:
            for i in range(0, n, h * 2):
                for j in range(i, i + h):
                    a = x[j]
                    b = x[j + h]
                    x[j] = a + b
                    x[j + h] = a - b
            h *= 2
        return x / np.sqrt(n)

    def transform(self, X: np.ndarray) -> np.ndarray:
        """Transform input features to Fastfood RFF space."""
        single = X.ndim == 1
        if single:
            X = X.reshape(1, -1)

        n_samples = X.shape[0]
        results = np.zeros((n_samples, self.n_blocks * self.d), dtype=np.float32)

        for sample_idx in range(n_samples):
            x = X[sample_idx]
            # Zero-pad to power of 2
            if len(x) < self.d:
                x_pad = np.zeros(self.d, dtype=np.float32)
                x_pad[:len(x)] = x
            else:
                x_pad = x[:self.d].copy()

            for block_idx in range(self.n_blocks):
                z = x_pad.copy()
                # Π: permute
                z = z[self.perms[block_idx]]
                # G: diagonal Gaussian
                z *= self.G[block_idx]
                # H: Walsh-Hadamard
                z = self._fwht(z)
                # S: scaling
                z *= self.S[block_idx]
                # Store
                start = block_idx * self.d
                results[sample_idx, start:start + self.d] = z

        # Trim to rff_dim, apply cos(z + b)
        results = results[:, :self.rff_dim]
        results = self.scale * np.cos(results + self.b[:self.rff_dim])

        return results[0] if single else results

    def save_params(self) -> dict:
        return {
            "input_dim": self.input_dim,
            "rff_dim": self.rff_dim,
            "sigma": self.sigma,
            "d": self.d,
            "n_blocks": self.n_blocks,
            "perms": [p.tolist() for p in self.perms],
            "G": [g.tolist() for g in self.G],
            "S": [s.tolist() for s in self.S],
            "b": self.b.tolist(),
        }


def create_rff_mapper(input_dim: int, rff_dim: int, sigma: float,
                      use_fastfood: bool = False) -> RBFSampler | FastfoodRFF:
    if use_fastfood:
        return FastfoodRFF(input_dim, rff_dim, sigma)
    gamma = sigma_to_gamma(sigma)
    mapper = RBFSampler(gamma=gamma, n_components=rff_dim, random_state=42)
    mapper.fit(np.zeros((1, input_dim)))
    return mapper


def compute_mean_embedding(
    features: np.ndarray, cfg: WakeWordConfig, sigma: float = 0.0,
    use_fastfood: bool = False,
) -> tuple[np.ndarray, RBFSampler | FastfoodRFF, float]:
    if sigma <= 0:
        sigma = median_heuristic(features)
        print(f"Median heuristic σ = {sigma:.4f}")

    mapper = create_rff_mapper(cfg.feature_dim, cfg.rff_dim, sigma, use_fastfood)
    embeddings = mapper.transform(features)
    mean_embedding = embeddings.mean(axis=0)
    return mean_embedding, mapper, sigma


def mmd_distance(mean_embedding: np.ndarray, test_embedding: np.ndarray) -> float:
    diff = mean_embedding - test_embedding
    return float(np.dot(diff, diff))


def save_model(mapper, mean_emb: np.ndarray, sigma: float,
               threshold: float, cfg: WakeWordConfig, path: str,
               n_pos: int, n_aug: int,
               centroids: np.ndarray = None, neg_mean: np.ndarray = None,
               neg_centroids: np.ndarray = None):
    """Save model with optional multi-centroid UBM."""
    data = dict(
        mean_embedding=mean_emb,
        sigma=np.array([sigma]),
        threshold=np.array([threshold]),
        rff_dim=np.array([mapper.n_components if hasattr(mapper, 'n_components') else mapper.rff_dim]),
        sample_rate=np.array([cfg.sample_rate]),
        frame_ms=np.array([cfg.frame_ms]),
        hop_ms=np.array([cfg.hop_ms]),
        n_dct_coeffs=np.array([cfg.n_dct_coeffs]),
        utterance_duration_s=np.array([cfg.utterance_duration_s]),
        detection_stride_ms=np.array([cfg.detection_stride_ms]),
        n_positive_samples=np.array([n_pos]),
        n_augmented_samples=np.array([n_aug]),
    )
    # Store RFF weights (sklearn RBFSampler)
    if isinstance(mapper, RBFSampler):
        data["rff_weights"] = mapper.random_weights_
        data["rff_offset"] = mapper.random_offset_
        data["rff_gamma"] = np.array([mapper.gamma])
        data["rff_type"] = np.array([0])  # 0 = standard
    else:
        # Fastfood — store as flat arrays
        data["rff_gamma"] = np.array([mapper.gamma])
        data["rff_type"] = np.array([1])  # 1 = fastfood
        data["ff_d"] = np.array([mapper.d])
        data["ff_n_blocks"] = np.array([mapper.n_blocks])
        data["ff_b"] = mapper.b
        for i in range(mapper.n_blocks):
            data[f"ff_perm_{i}"] = mapper.perms[i]
            data[f"ff_G_{i}"] = mapper.G[i]
            data[f"ff_S_{i}"] = mapper.S[i]

    if centroids is not None:
        data["centroids"] = centroids
    if neg_mean is not None:
        data["neg_mean"] = neg_mean
    if neg_centroids is not None:
        data["neg_centroids"] = neg_centroids
    np.savez_compressed(path, **data)


def load_model(path: str):
    """Load model. Returns (mean_embedding, mapper, threshold, config)."""
    data = np.load(path, allow_pickle=False)
    mean_emb = data["mean_embedding"]
    threshold = float(data["threshold"][0])

    n_dct_coeffs = int(data["n_dct_coeffs"][0])
    rff_dim = int(data["rff_dim"][0])

    cfg = WakeWordConfig(
        sample_rate=int(data["sample_rate"][0]),
        frame_ms=float(data["frame_ms"][0]),
        hop_ms=float(data["hop_ms"][0]),
        n_dct_coeffs=n_dct_coeffs,
        utterance_duration_s=float(data["utterance_duration_s"][0]),
        detection_stride_ms=float(data["detection_stride_ms"][0]),
        rff_dim=rff_dim,
    )

    rff_type = int(data.get("rff_type", np.array([0]))[0])
    sigma = float(np.sqrt(1.0 / (2.0 * float(data["rff_gamma"][0]))))

    if rff_type == 0:
        # Standard RBFSampler
        gamma = float(data["rff_gamma"][0])
        mapper = RBFSampler(gamma=gamma, n_components=rff_dim)
        mapper.fit(np.zeros((1, cfg.feature_dim)))
        mapper.random_weights_ = data["rff_weights"]
        mapper.random_offset_ = data["rff_offset"]
    else:
        # Fastfood
        mapper = FastfoodRFF(cfg.feature_dim, rff_dim, sigma)
        mapper.d = int(data["ff_d"][0])
        mapper.n_blocks = int(data["ff_n_blocks"][0])
        mapper.b = data["ff_b"]
        mapper.perms = [data[f"ff_perm_{i}"] for i in range(mapper.n_blocks)]
        mapper.G = [data[f"ff_G_{i}"] for i in range(mapper.n_blocks)]
        mapper.S = [data[f"ff_S_{i}"] for i in range(mapper.n_blocks)]

    return mean_emb, mapper, threshold, cfg
