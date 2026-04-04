"""
Data augmentation: take a small set of voice samples and generate many variants
by mixing with background noise, applying transformations.
"""

import numpy as np
from pathlib import Path
from config import WakeWordConfig


# --- Synthetic noise generators ---

def white_noise(length: int, amplitude: float = 0.02) -> np.ndarray:
    return np.random.randn(length).astype(np.float32) * amplitude


def pink_noise(length: int, amplitude: float = 0.02) -> np.ndarray:
    """Approximate 1/f noise via filtering white noise."""
    white = np.random.randn(length).astype(np.float32)
    # Simple IIR approximation
    b = np.array([0.049922035, -0.095993537, 0.050612699, -0.004709510], dtype=np.float32)
    a = np.array([1.0, -2.494956002, 2.017265875, -0.522189400], dtype=np.float32)
    from scipy.signal import lfilter
    pink = lfilter(b, a, white).astype(np.float32)
    pink = pink / (np.abs(pink).max() + 1e-8) * amplitude
    return pink


def brownian_noise(length: int, amplitude: float = 0.02) -> np.ndarray:
    """Cumulative sum of white noise."""
    white = np.random.randn(length).astype(np.float32) * 0.01
    brown = np.cumsum(white)
    brown = brown / (np.abs(brown).max() + 1e-8) * amplitude
    return brown.astype(np.float32)


def hum_noise(length: int, sample_rate: int = 16000, amplitude: float = 0.01) -> np.ndarray:
    """60Hz electrical hum + harmonics."""
    t = np.arange(length, dtype=np.float32) / sample_rate
    hum = np.zeros(length, dtype=np.float32)
    for harmonic in [60, 120, 180]:
        hum += np.sin(2 * np.pi * harmonic * t) * (amplitude / (harmonic / 60))
    return hum


def babble_noise(length: int, amplitude: float = 0.03) -> np.ndarray:
    """Simulate crowd babble by summing multiple shifted pink noise streams."""
    result = np.zeros(length, dtype=np.float32)
    for _ in range(5):
        noise = pink_noise(length, amplitude=amplitude / 5)
        shift = np.random.randint(0, length)
        result += np.roll(noise, shift)
    return result


SYNTHETIC_NOISES = {
    "white": white_noise,
    "pink": pink_noise,
    "brownian": brownian_noise,
    "hum": hum_noise,
    "babble": babble_noise,
}


# --- Audio file noise loading ---

def load_noise_files(noise_dir: str, sample_rate: int = 16000) -> dict[str, np.ndarray]:
    """Load .wav noise files from a directory. Returns dict of name → audio array."""
    import wave
    noises = {}
    noise_path = Path(noise_dir)
    if not noise_path.exists():
        return noises
    for wav_file in noise_path.glob("*.wav"):
        try:
            with wave.open(str(wav_file), "r") as wf:
                assert wf.getsampwidth() == 2  # 16-bit
                data = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
                audio = data.astype(np.float32) / 32768.0
                # Resample if needed (simple nearest-neighbor for now)
                if wf.getframerate() != sample_rate:
                    ratio = sample_rate / wf.getframerate()
                    indices = np.arange(0, len(audio), 1.0 / ratio).astype(int)
                    indices = indices[indices < len(audio)]
                    audio = audio[indices]
                noises[wav_file.stem] = audio
        except Exception as e:
            print(f"Warning: could not load {wav_file}: {e}")
    return noises


# --- Augmentation transforms ---

def add_noise(audio: np.ndarray, noise: np.ndarray, snr_db: float) -> np.ndarray:
    """Mix audio with noise at a given SNR (dB)."""
    signal_power = np.mean(audio ** 2) + 1e-10
    noise_power = np.mean(noise ** 2) + 1e-10
    target_noise_power = signal_power / (10 ** (snr_db / 10))
    scale = np.sqrt(target_noise_power / noise_power)

    # Trim or tile noise to match audio length
    if len(noise) < len(audio):
        noise = np.tile(noise, int(np.ceil(len(audio) / len(noise))))
    noise = noise[:len(audio)]

    return (audio + noise * scale).astype(np.float32)


def time_shift(audio: np.ndarray, max_shift_ms: float = 100, sample_rate: int = 16000) -> np.ndarray:
    """Random time shift."""
    max_shift = int(sample_rate * max_shift_ms / 1000)
    shift = np.random.randint(-max_shift, max_shift + 1)
    return np.roll(audio, shift)


def speed_perturb(audio: np.ndarray, factor: float) -> np.ndarray:
    """Change speed by resampling (affects pitch too)."""
    indices = np.arange(0, len(audio), factor)
    indices = indices[indices < len(audio)].astype(int)
    return audio[indices]


def volume_perturb(audio: np.ndarray, gain_db: float) -> np.ndarray:
    """Adjust volume."""
    gain = 10 ** (gain_db / 20)
    return (audio * gain).astype(np.float32)


# --- Main augmentation pipeline ---

def augment_samples(
    samples: list[np.ndarray],
    cfg: WakeWordConfig,
    noise_dir: str = "noise",
    snr_range: tuple[float, float] = (5.0, 20.0),
    augment_factor: int = 50,
) -> list[np.ndarray]:
    """
    Take N clean samples and produce N * augment_factor augmented samples.

    Each augmented sample gets a random combination of:
    - Background noise (synthetic or from files) at random SNR
    - Time shift (±100ms)
    - Speed perturbation (0.9x - 1.1x)
    - Volume perturbation (±6dB)
    """
    # Collect all available noise sources
    file_noises = load_noise_files(noise_dir, cfg.sample_rate)
    all_noise_sources = list(SYNTHETIC_NOISES.keys()) + list(file_noises.keys())

    augmented = []
    for sample in samples:
        # Always include the original
        augmented.append(sample.copy())

        for _ in range(augment_factor - 1):
            aug = sample.copy()

            # Random speed perturbation (0.9 - 1.1)
            if np.random.random() < 0.5:
                factor = np.random.uniform(0.9, 1.1)
                aug = speed_perturb(aug, factor)

            # Random time shift
            if np.random.random() < 0.5:
                aug = time_shift(aug, max_shift_ms=100, sample_rate=cfg.sample_rate)

            # Random volume
            if np.random.random() < 0.5:
                gain = np.random.uniform(-6, 6)
                aug = volume_perturb(aug, gain)

            # Add noise (always — this is the main augmentation)
            noise_name = np.random.choice(all_noise_sources)
            snr = np.random.uniform(snr_range[0], snr_range[1])
            if noise_name in SYNTHETIC_NOISES:
                noise = SYNTHETIC_NOISES[noise_name](len(aug), amplitude=0.05)
            else:
                noise = file_noises[noise_name]
            aug = add_noise(aug, noise, snr)

            augmented.append(aug)

    print(f"Augmented {len(samples)} samples → {len(augmented)} "
          f"(factor={augment_factor}, noise sources={len(all_noise_sources)})")
    return augmented
