
import time
import numpy as np
from config import WakeWordConfig
from features import IncrementalMFCC

def benchmark():
    cfg = WakeWordConfig()
    extractor = IncrementalMFCC(cfg)
    
    # 160ms of audio (stride)
    stride_samples = cfg.detection_stride_samples
    dummy_audio = np.random.randn(stride_samples).astype(np.float32)
    
    # Warm up
    for _ in range(10):
        extractor.feed_audio(dummy_audio)
    
    # Benchmark
    n_iters = 100
    start = time.perf_counter()
    for _ in range(n_iters):
        extractor.feed_audio(dummy_audio)
    end = time.perf_counter()
    
    avg_ms = (end - start) * 1000 / n_iters
    print(f"Average time per check: {avg_ms:.3f} ms")

if __name__ == "__main__":
    benchmark()
