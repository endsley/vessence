"""
GPU/CPU auto-detection and accelerated matrix operations.
Falls back to NumPy on CPU if no GPU available.
"""

import numpy as np

_USE_GPU = False
_DEVICE = "cpu"

try:
    import torch
    if torch.cuda.is_available():
        _USE_GPU = True
        _DEVICE = "cuda"
        # Pre-warm GPU
        torch.zeros(1, device="cuda")
except ImportError:
    pass


def get_device() -> str:
    return _DEVICE


def is_gpu_available() -> bool:
    return _USE_GPU


def matrix_vector_multiply(W: np.ndarray, x: np.ndarray) -> np.ndarray:
    """
    Compute W @ x (or W @ X.T for batched).
    Uses GPU if available, otherwise CPU numpy.
    """
    if _USE_GPU:
        import torch
        W_t = torch.from_numpy(W).float().cuda()
        x_t = torch.from_numpy(x).float().cuda()
        if x_t.ndim == 1:
            result = W_t @ x_t
        else:
            result = (x_t @ W_t.T)  # batch: (N, d) @ (D, d).T = (N, D)
        return result.cpu().numpy()
    else:
        if x.ndim == 1:
            return W @ x
        else:
            return x @ W.T


def rff_transform(X: np.ndarray, W: np.ndarray, b: np.ndarray, scale: float) -> np.ndarray:
    """
    Full RFF transform: φ(x) = scale * cos(X @ W.T + b)
    GPU-accelerated if available.

    X: (n_samples, input_dim) or (input_dim,)
    W: (rff_dim, input_dim)
    b: (rff_dim,)
    scale: sqrt(2/D)

    Returns: (n_samples, rff_dim) or (rff_dim,)
    """
    single = X.ndim == 1
    if single:
        X = X.reshape(1, -1)

    if _USE_GPU:
        import torch
        X_t = torch.from_numpy(X).float().cuda()
        W_t = torch.from_numpy(W).float().cuda()
        b_t = torch.from_numpy(b).float().cuda()
        projection = X_t @ W_t.T + b_t
        result = (scale * torch.cos(projection)).cpu().numpy()
    else:
        projection = X @ W.T + b
        result = scale * np.cos(projection)

    return result[0] if single else result


# Report on import
if _USE_GPU:
    import torch
    _gpu_name = torch.cuda.get_device_name(0)
    print(f"[WakeWord] GPU detected: {_gpu_name} — using CUDA acceleration")
else:
    print(f"[WakeWord] No GPU — using CPU (NumPy)")
