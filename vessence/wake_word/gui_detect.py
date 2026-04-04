#!/usr/bin/env python3
"""
GUI for live wake word detection testing.
Shows real-time distance meter, flashes BIG RED when triggered.
Displays stats: check time, stage0 skip rate, trigger count.
"""

import sys
import threading
import time

import numpy as np
import sounddevice as sd
import tkinter as tk

from detect import WakeWordDetector


class DetectorApp:
    def __init__(self, root: tk.Tk, model_path: str = "model.npz"):
        self.root = root
        self.root.title("Hey Jane — Live Detection Test")
        self.root.geometry("800x550")
        self.root.configure(bg="#1a1a2e")

        self.detector = WakeWordDetector(model_path)
        self.running = False
        self.detection_count = 0
        self.check_count = 0
        self.check_times = []

        self._build_ui()

    def _build_ui(self):
        # Big trigger flash area
        self.flash_frame = tk.Frame(self.root, bg="#1a1a2e", height=200)
        self.flash_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(20, 10))
        self.flash_frame.pack_propagate(False)

        self.trigger_label = tk.Label(
            self.flash_frame, text="LISTENING...",
            font=("Helvetica", 48, "bold"), fg="#333333", bg="#1a1a2e",
        )
        self.trigger_label.pack(expand=True)

        # Distance meter
        meter_frame = tk.Frame(self.root, bg="#1a1a2e")
        meter_frame.pack(fill=tk.X, padx=20, pady=5)

        tk.Label(meter_frame, text="Score:", font=("Helvetica", 12),
                 fg="#aaaaaa", bg="#1a1a2e").pack(side=tk.LEFT)

        self.meter_canvas = tk.Canvas(
            meter_frame, width=500, height=30, bg="#0f3460", highlightthickness=0)
        self.meter_canvas.pack(side=tk.LEFT, padx=10)

        self.dist_var = tk.StringVar(value="--")
        tk.Label(meter_frame, textvariable=self.dist_var, font=("Courier", 12, "bold"),
                 fg="#00d2ff", bg="#1a1a2e", width=12).pack(side=tk.LEFT)

        # Stats bar
        stats_frame = tk.Frame(self.root, bg="#1a1a2e")
        stats_frame.pack(fill=tk.X, padx=20, pady=5)

        self.stats_var = tk.StringVar(
            value=f"Threshold: {self.detector.threshold:.4f} | "
                  f"Pos centroids: {len(self.detector.centroids) if self.detector.centroids is not None else 1} | "
                  f"Neg centroids: {len(self.detector.neg_centroids) if self.detector.neg_centroids is not None else 0}")
        tk.Label(stats_frame, textvariable=self.stats_var, font=("Helvetica", 10),
                 fg="#666666", bg="#1a1a2e").pack(side=tk.LEFT)

        self.count_var = tk.StringVar(value="Triggers: 0 | Checks: 0")
        tk.Label(stats_frame, textvariable=self.count_var, font=("Helvetica", 10, "bold"),
                 fg="#e94560", bg="#1a1a2e").pack(side=tk.RIGHT)

        # Performance bar
        perf_frame = tk.Frame(self.root, bg="#1a1a2e")
        perf_frame.pack(fill=tk.X, padx=20, pady=2)

        self.perf_var = tk.StringVar(value="Avg: -- ms | Stage0 skip: --%")
        tk.Label(perf_frame, textvariable=self.perf_var, font=("Courier", 10),
                 fg="#555555", bg="#1a1a2e").pack(side=tk.LEFT)

        # Controls
        ctrl_frame = tk.Frame(self.root, bg="#1a1a2e")
        ctrl_frame.pack(fill=tk.X, padx=20, pady=(10, 20))

        self.start_btn = tk.Button(
            ctrl_frame, text="START", font=("Helvetica", 16, "bold"),
            bg="#27ae60", fg="white", width=10, height=2,
            command=self._toggle, activebackground="#229954")
        self.start_btn.pack(side=tk.LEFT, padx=10)

        # Threshold slider
        tk.Label(ctrl_frame, text="Threshold:", font=("Helvetica", 11),
                 fg="#aaaaaa", bg="#1a1a2e").pack(side=tk.LEFT, padx=(20, 5))

        self.thresh_scale = tk.Scale(
            ctrl_frame, from_=-0.5, to=0.5, resolution=0.001,
            orient=tk.HORIZONTAL, length=200,
            bg="#1a1a2e", fg="#aaaaaa", troughcolor="#0f3460",
            highlightthickness=0, command=self._on_threshold_change)
        self.thresh_scale.set(self.detector.threshold)
        self.thresh_scale.pack(side=tk.LEFT)

        # Energy gate slider
        tk.Label(ctrl_frame, text="Energy gate:", font=("Helvetica", 11),
                 fg="#aaaaaa", bg="#1a1a2e").pack(side=tk.LEFT, padx=(15, 5))

        self.gate_scale = tk.Scale(
            ctrl_frame, from_=0.001, to=0.1, resolution=0.001,
            orient=tk.HORIZONTAL, length=120,
            bg="#1a1a2e", fg="#aaaaaa", troughcolor="#0f3460",
            highlightthickness=0, command=self._on_gate_change)
        self.gate_scale.set(self.detector.energy_gate_threshold)
        self.gate_scale.pack(side=tk.LEFT)

    def _on_threshold_change(self, val):
        self.detector.threshold = float(val)

    def _on_gate_change(self, val):
        self.detector.energy_gate_threshold = float(val)

    def _toggle(self):
        if not self.running:
            self.running = True
            self.start_btn.configure(text="STOP", bg="#e74c3c")
            self.trigger_label.configure(text="LISTENING...", fg="#333333")
            self._reset_bg()
            threading.Thread(target=self._listen_thread, daemon=True).start()
        else:
            self.running = False
            self.start_btn.configure(text="START", bg="#27ae60")
            self.trigger_label.configure(text="STOPPED", fg="#333333")

    def _listen_thread(self):
        stride = self.detector.cfg.detection_stride_samples
        sr = self.detector.cfg.sample_rate

        try:
            with sd.InputStream(samplerate=sr, channels=1,
                                dtype=np.float32, blocksize=stride) as stream:
                while self.running:
                    audio, _ = stream.read(stride)
                    audio = audio.flatten()
                    self.check_count += 1

                    t0 = time.perf_counter()
                    detected, score = self.detector.feed(audio)
                    check_ms = (time.perf_counter() - t0) * 1000
                    self.check_times.append(check_ms)

                    if detected:
                        self.detection_count += 1

                    self.root.after(0, self._update_ui, score, detected, check_ms)

        except Exception as e:
            self.root.after(0, lambda: self.trigger_label.configure(
                text=f"ERROR: {e}", fg="#e94560"))
            self.running = False

    def _update_ui(self, score: float, detected: bool, check_ms: float):
        self.dist_var.set(f"{score:.6f}")

        # Update meter
        self.meter_canvas.delete("all")
        w, h = 500, 30
        max_score = abs(self.detector.threshold) * 5
        # Score is negative when close to positive, normalize for display
        normalized = (score - self.detector.threshold * 3) / (max_score * 2)
        bar_x = int(w * max(0, min(1, 0.5 - normalized)))

        if score <= self.detector.threshold:
            color = "#e74c3c"
        elif score <= self.detector.threshold * 2:
            color = "#f39c12"
        else:
            color = "#27ae60"

        self.meter_canvas.create_rectangle(0, 0, bar_x, h, fill=color, outline="")
        thresh_x = int(w * 0.5)
        self.meter_canvas.create_line(thresh_x, 0, thresh_x, h, fill="white", width=2)

        # Stats
        self.count_var.set(f"Triggers: {self.detection_count} | Checks: {self.check_count}")

        avg_ms = np.mean(self.check_times[-50:]) if self.check_times else 0
        skip = self.detector.stage0_skip_rate
        self.perf_var.set(f"Avg: {avg_ms:.2f} ms | Stage0 skip: {skip:.0%}")

        if detected:
            self._flash_trigger()

    def _flash_trigger(self):
        self.root.configure(bg="#e74c3c")
        self.flash_frame.configure(bg="#e74c3c")
        self.trigger_label.configure(text="TRIGGERED!", fg="white", bg="#e74c3c",
                                     font=("Helvetica", 64, "bold"))
        self.root.after(1200, self._reset_bg)

    def _reset_bg(self):
        self.root.configure(bg="#1a1a2e")
        self.flash_frame.configure(bg="#1a1a2e")
        self.trigger_label.configure(text="LISTENING...", fg="#333333", bg="#1a1a2e",
                                     font=("Helvetica", 48, "bold"))


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="model.npz")
    args = parser.parse_args()

    root = tk.Tk()
    app = DetectorApp(root, args.model)
    root.mainloop()


if __name__ == "__main__":
    main()
