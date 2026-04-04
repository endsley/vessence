"""
Feature extraction: Raw PCM → frames → mel filterbank → log → DCT (= MFCCs)
→ delta + delta-delta → CMVN → VAD → energy weighting → concatenated vector.
"""

import numpy as np
from scipy.fft import dct, rfft
from config import WakeWordConfig


def frame_audio(audio: np.ndarray, cfg: WakeWordConfig) -> np.ndarray:
    """Split audio into overlapping frames. Returns shape (n_frames, frame_samples)."""
    n = len(audio)
    frame_len = cfg.frame_samples
    hop = cfg.hop_samples
    n_frames = max(1, 1 + (n - frame_len) // hop)

    # Vectorized framing using strided view (zero-copy)
    required_len = (n_frames - 1) * hop + frame_len
    if n < required_len:
        audio = np.pad(audio, (0, required_len - n))

    shape = (n_frames, frame_len)
    strides = (hop * audio.itemsize, audio.itemsize)
    return np.lib.stride_tricks.as_strided(audio, shape=shape, strides=strides).copy()


def mel_filterbank(n_fft: int, n_filters: int, sample_rate: int,
                   fmin: float = 0, fmax: float = None) -> np.ndarray:
    """Build a mel-scale triangular filterbank matrix. Returns shape (n_filters, n_fft//2+1)."""
    if fmax is None:
        fmax = sample_rate / 2.0

    def hz_to_mel(hz):
        return 2595.0 * np.log10(1.0 + hz / 700.0)

    def mel_to_hz(mel):
        return 700.0 * (10.0 ** (mel / 2595.0) - 1.0)

    mel_min = hz_to_mel(fmin)
    mel_max = hz_to_mel(fmax)
    mel_points = np.linspace(mel_min, mel_max, n_filters + 2)
    hz_points = mel_to_hz(mel_points)

    bin_points = np.floor((n_fft + 1) * hz_points / sample_rate).astype(int)
    n_freqs = n_fft // 2 + 1
    filters = np.zeros((n_filters, n_freqs), dtype=np.float32)

    for i in range(n_filters):
        left, center, right = bin_points[i], bin_points[i + 1], bin_points[i + 2]
        if center > left:
            filters[i, left:center] = np.linspace(0, 1, center - left, endpoint=False)
        if right > center:
            filters[i, center:right] = np.linspace(1, 0, right - center, endpoint=False)

    return filters


_mel_cache = {}


def _get_mel_filterbank(n_fft: int, n_filters: int, sample_rate: int) -> np.ndarray:
    key = (n_fft, n_filters, sample_rate)
    if key not in _mel_cache:
        _mel_cache[key] = mel_filterbank(n_fft, n_filters, sample_rate)
    return _mel_cache[key]


# Pre-compute DCT basis matrix for given mel filter count
_dct_basis_cache = {}


def _get_dct_basis(n_mel: int, n_keep: int) -> np.ndarray:
    """Pre-computed DCT-II basis matrix. Returns shape (n_keep, n_mel)."""
    key = (n_mel, n_keep)
    if key not in _dct_basis_cache:
        # DCT basis: D[k,n] = cos(pi*(n+0.5)*k/N) * norm
        n = np.arange(n_mel)
        k = np.arange(1, n_keep + 1)  # skip k=0 (DC)
        basis = np.cos(np.pi * np.outer(k, n + 0.5) / n_mel)
        # Ortho normalization
        basis *= np.sqrt(2.0 / n_mel)
        _dct_basis_cache[key] = basis.astype(np.float32)
    return _dct_basis_cache[key]


def _compute_deltas(coeffs: np.ndarray, width: int = 2) -> np.ndarray:
    """Vectorized delta computation using regression formula."""
    n_frames = coeffs.shape[-2]
    deltas = np.zeros_like(coeffs)
    denom = 2 * sum(t * t for t in range(1, width + 1))
    if denom == 0:
        return deltas
    for w in range(1, width + 1):
        t_plus = np.clip(np.arange(n_frames) + w, 0, n_frames - 1)
        t_minus = np.clip(np.arange(n_frames) - w, 0, n_frames - 1)
        deltas += w * (coeffs.take(t_plus, axis=-2) - coeffs.take(t_minus, axis=-2))
    return deltas / denom


def _apply_cmvn(coeffs: np.ndarray) -> np.ndarray:
    """Cepstral Mean and Variance Normalization."""
    mean = coeffs.mean(axis=-2, keepdims=True)
    std = coeffs.std(axis=-2, keepdims=True)
    return (coeffs - mean) / (std + 1e-8)


def _compute_mfccs_batch(frames: np.ndarray, window: np.ndarray,
                         n_fft: int, mel_fb: np.ndarray,
                         dct_basis: np.ndarray,
                         vad_mask: np.ndarray) -> np.ndarray:
    """
    Vectorized MFCC extraction for multiple frames.
    Uses rfft (real FFT) and pre-computed DCT basis matrix.

    frames: (N, frame_len) or (batch, N, frame_len)
    Returns: same leading dims + (n_dct_coeffs,)
    """
    n_coeffs = dct_basis.shape[0]
    orig_shape = frames.shape[:-1]
    flat_frames = frames.reshape(-1, frames.shape[-1])
    flat_mask = vad_mask.ravel()

    result = np.zeros((flat_frames.shape[0], n_coeffs), dtype=np.float32)
    if not np.any(flat_mask):
        return result.reshape(*orig_shape, n_coeffs)

    active = flat_frames[flat_mask]
    windowed = active * window
    # rfft: only computes positive frequencies — 2x faster than fft
    spectrums = np.abs(rfft(windowed, n=n_fft, axis=1)) ** 2
    mel_energies = spectrums @ mel_fb.T
    log_mel = np.log(mel_energies + 1e-10)
    # Matrix multiply with pre-computed DCT basis instead of calling dct()
    mfccs = (log_mel @ dct_basis.T).astype(np.float32)
    result[flat_mask] = mfccs
    return result.reshape(*orig_shape, n_coeffs)


def extract_dct_features(audio: np.ndarray, cfg: WakeWordConfig) -> np.ndarray:
    """
    Extract MFCC + delta + delta-delta with CMVN, VAD, energy weighting.
    Fully vectorized, uses rfft and pre-computed DCT basis.
    """
    target_len = cfg.utterance_samples
    if len(audio) < target_len:
        audio = np.pad(audio, (0, target_len - len(audio)))
    else:
        audio = audio[:target_len]

    frames = frame_audio(audio, cfg)
    if len(frames) > cfg.n_frames:
        frames = frames[:cfg.n_frames]
    elif len(frames) < cfg.n_frames:
        frames = np.concatenate([frames,
            np.zeros((cfg.n_frames - len(frames), cfg.frame_samples), dtype=np.float32)])

    n_fft = 1 << (cfg.frame_samples - 1).bit_length()
    mel_fb = _get_mel_filterbank(n_fft, 26, cfg.sample_rate)
    dct_basis = _get_dct_basis(26, cfg.n_dct_coeffs)
    window = np.hanning(cfg.frame_samples).astype(np.float32)

    # Energies + VAD mask
    energies = np.sqrt(np.mean(frames ** 2, axis=1)).astype(np.float32)
    energy_threshold = np.percentile(energies[energies > 0], 10) if np.any(energies > 0) else 0
    vad_mask = energies >= energy_threshold

    # Static MFCCs (vectorized rfft + DCT basis matmul)
    static_coeffs = _compute_mfccs_batch(frames, window, n_fft, mel_fb, dct_basis, vad_mask)

    # Deltas
    delta_coeffs = _compute_deltas(static_coeffs)
    delta2_coeffs = _compute_deltas(delta_coeffs)

    # CMVN on ALL features (static + delta + delta-delta) — fixes distribution mismatch
    all_coeffs = np.concatenate([static_coeffs, delta_coeffs, delta2_coeffs], axis=1)
    all_coeffs = _apply_cmvn(all_coeffs)

    # Energy weighting
    w = energies.copy()
    w[~vad_mask] = 0
    all_coeffs *= w[:, np.newaxis]

    # Flatten + unit normalize
    flat = all_coeffs.ravel()
    norm = np.linalg.norm(flat)
    return flat / (norm + 1e-8) if norm > 1e-6 else flat


def batch_extract(audio_segments: list[np.ndarray], cfg: WakeWordConfig) -> np.ndarray:
    """Batch extraction for multiple utterances."""
    if not audio_segments:
        return np.zeros((0, cfg.feature_dim), dtype=np.float32)
    return np.array([extract_dct_features(seg, cfg) for seg in audio_segments])


class IncrementalMFCC:
    """
    Stateful MFCC extractor that maintains a raw audio ring buffer.
    Frames the full utterance window each time (same boundaries as batch),
    but only computes MFCCs for frames whose audio changed since last check.

    Guarantees batch/incremental parity: identical feature vectors.
    """

    def __init__(self, cfg: WakeWordConfig):
        self.cfg = cfg
        self.n_fft = 1 << (cfg.frame_samples - 1).bit_length()
        self.mel_fb = _get_mel_filterbank(self.n_fft, 26, cfg.sample_rate)
        self.dct_basis = _get_dct_basis(26, cfg.n_dct_coeffs)
        self.window = np.hanning(cfg.frame_samples).astype(np.float32)

        # Raw audio ring buffer — holds exactly one utterance window
        self.audio_buffer = np.zeros(cfg.utterance_samples, dtype=np.float32)
        self.audio_filled = 0

        # Cached per-frame MFCCs and energies
        self.mfcc_cache = np.zeros((cfg.n_frames, cfg.n_dct_coeffs), dtype=np.float32)
        self.energy_cache = np.zeros(cfg.n_frames, dtype=np.float32)

        # Track which frames need recomputation
        self.frames_valid = 0  # how many frames from the END are already computed

    def _compute_mfccs_for_frames(self, frames: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Vectorized MFCC computation for a batch of frames."""
        energies = np.sqrt(np.mean(frames ** 2, axis=1)).astype(np.float32)
        windowed = frames * self.window
        spectrums = np.abs(rfft(windowed, n=self.n_fft, axis=1)) ** 2
        mel_energies = spectrums @ self.mel_fb.T
        log_mel = np.log(mel_energies + 1e-10)
        mfccs = (log_mel @ self.dct_basis.T).astype(np.float32)
        return mfccs, energies

    def feed_audio(self, new_audio: np.ndarray) -> np.ndarray | None:
        """
        Feed one stride of audio. Returns feature vector or None if buffer not full.
        Recomputes all MFCCs from the audio buffer — guarantees exact batch parity.
        """
        cfg = self.cfg
        n_new = len(new_audio)

        # Shift audio buffer left, append new audio at the end
        if self.audio_filled >= cfg.utterance_samples:
            self.audio_buffer[:-n_new] = self.audio_buffer[n_new:]
            self.audio_buffer[-n_new:] = new_audio
        else:
            space = cfg.utterance_samples - self.audio_filled
            if n_new <= space:
                self.audio_buffer[self.audio_filled:self.audio_filled + n_new] = new_audio
                self.audio_filled += n_new
            else:
                self.audio_buffer[self.audio_filled:self.audio_filled + space] = new_audio[:space]
                self.audio_filled = cfg.utterance_samples
            if self.audio_filled < cfg.utterance_samples:
                return None

        # Just call extract_dct_features on the buffer — guaranteed parity
        return extract_dct_features(self.audio_buffer, cfg)
        energy_threshold = np.percentile(
            self.energy_cache[self.energy_cache > 0], 10
        ) if np.any(self.energy_cache > 0) else 0
        vad_mask = self.energy_cache >= energy_threshold

        # Zero out VAD-off frames BEFORE deltas (matches batch: FFT skipped for those)
        static_coeffs = self.mfcc_cache.copy()
        static_coeffs[~vad_mask] = 0

        delta_coeffs = _compute_deltas(static_coeffs)
        delta2_coeffs = _compute_deltas(delta_coeffs)

        all_coeffs = np.concatenate([static_coeffs, delta_coeffs, delta2_coeffs], axis=1)
        all_coeffs = _apply_cmvn(all_coeffs)

        # Energy weighting
        w = self.energy_cache.copy()
        w[~vad_mask] = 0
        all_coeffs *= w[:, np.newaxis]

        flat = all_coeffs.ravel()
        norm = np.linalg.norm(flat)
        return flat / (norm + 1e-8) if norm > 1e-6 else flat

    def reset(self):
        self.audio_buffer.fill(0)
        self.audio_filled = 0
        self.mfcc_cache.fill(0)
        self.energy_cache.fill(0)
