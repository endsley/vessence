#!/usr/bin/env python3
"""
GUI for recording wake word samples.
Big buttons, waveform display, sample management.
"""

import sys
import threading
import time
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd
import tkinter as tk
from tkinter import ttk, messagebox

from config import WakeWordConfig

SAMPLES_DIR = Path("samples")
SAMPLES_DIR.mkdir(exist_ok=True)

cfg = WakeWordConfig()


class RecorderApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Hey Jane — Sample Recorder")
        self.root.geometry("700x600")
        self.root.configure(bg="#1a1a2e")

        self.recording = False
        self.current_audio = None
        self._os_gain_pct = 35  # current OS mic gain percentage
        # Set initial mic level
        import subprocess
        subprocess.run(["amixer", "sset", "Capture", "35%"], capture_output=True)
        subprocess.run(["amixer", "sset", "Front Mic Boost", "0"], capture_output=True)

        self._build_ui()
        self._refresh_samples()

    def _build_ui(self):
        # Title
        tk.Label(
            self.root, text='Say "Hey Jane"',
            font=("Helvetica", 28, "bold"), fg="#e94560", bg="#1a1a2e",
        ).pack(pady=(20, 5))

        # Status
        self.status_var = tk.StringVar(value="Press Record to start")
        tk.Label(
            self.root, textvariable=self.status_var,
            font=("Helvetica", 14), fg="#aaaaaa", bg="#1a1a2e",
        ).pack(pady=5)

        # Waveform canvas
        self.canvas = tk.Canvas(
            self.root, width=660, height=120, bg="#0f3460", highlightthickness=0,
        )
        self.canvas.pack(pady=10)

        # Buttons frame
        btn_frame = tk.Frame(self.root, bg="#1a1a2e")
        btn_frame.pack(pady=10)

        self.record_btn = tk.Button(
            btn_frame, text="🎙 RECORD", font=("Helvetica", 18, "bold"),
            bg="#e94560", fg="white", width=12, height=2,
            command=self._toggle_record, activebackground="#c0392b",
        )
        self.record_btn.pack(side=tk.LEFT, padx=10)

        self.save_btn = tk.Button(
            btn_frame, text="💾 SAVE", font=("Helvetica", 18, "bold"),
            bg="#16213e", fg="white", width=12, height=2,
            command=self._save_sample, state=tk.DISABLED,
            activebackground="#1a5276",
        )
        self.save_btn.pack(side=tk.LEFT, padx=10)

        # Sample list
        list_frame = tk.Frame(self.root, bg="#1a1a2e")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        tk.Label(
            list_frame, text="Recorded Samples:",
            font=("Helvetica", 12, "bold"), fg="#aaaaaa", bg="#1a1a2e",
            anchor="w",
        ).pack(fill=tk.X)

        self.sample_listbox = tk.Listbox(
            list_frame, font=("Courier", 11), bg="#16213e", fg="#e0e0e0",
            selectbackground="#e94560", height=8,
        )
        self.sample_listbox.pack(fill=tk.BOTH, expand=True, pady=5)

        # Bottom buttons
        bottom_frame = tk.Frame(self.root, bg="#1a1a2e")
        bottom_frame.pack(pady=5)

        tk.Button(
            bottom_frame, text="Play Selected", font=("Helvetica", 11),
            bg="#16213e", fg="white", command=self._play_selected,
        ).pack(side=tk.LEFT, padx=5)

        tk.Button(
            bottom_frame, text="Delete Selected", font=("Helvetica", 11),
            bg="#16213e", fg="#e94560", command=self._delete_selected,
        ).pack(side=tk.LEFT, padx=5)

        self.count_var = tk.StringVar(value="0 samples")
        tk.Label(
            bottom_frame, textvariable=self.count_var,
            font=("Helvetica", 12, "bold"), fg="#e94560", bg="#1a1a2e",
        ).pack(side=tk.LEFT, padx=20)

    def _toggle_record(self):
        if not self.recording:
            self.recording = True
            self.record_btn.configure(text="⏹ STOP", bg="#c0392b")
            self.save_btn.configure(state=tk.DISABLED)
            self.status_var.set("Recording... say 'Hey Jane'")
            self.canvas.delete("all")
            threading.Thread(target=self._record_thread, daemon=True).start()
        else:
            self.recording = False

    def _record_thread(self):
        import subprocess
        duration = 2.0

        # Record at 16kHz directly — let sounddevice handle resampling
        audio = sd.rec(
            int(cfg.sample_rate * duration),
            samplerate=cfg.sample_rate,
            channels=1,
            dtype=np.float32,
        )
        sd.wait()
        self.recording = False
        audio = audio.flatten()

        # Auto-reject and reduce OS mic gain if clipping
        peak = np.abs(audio).max()
        clipping_ratio = np.mean(np.abs(audio) > 0.95)
        if clipping_ratio > 0.01:
            self._os_gain_pct = max(5, int(self._os_gain_pct * 0.7))
            subprocess.run(["amixer", "sset", "Capture", f"{self._os_gain_pct}%"],
                           capture_output=True)
            self.current_audio = None
            pct = self._os_gain_pct
            self.root.after(0, lambda: self.status_var.set(
                f"Clipping — mic gain lowered to {pct}%. Try again."))
            self.root.after(0, lambda: self.record_btn.configure(text="🎙 RECORD", bg="#e94560"))
            return

        # Trim silence using RMS energy per 25ms block
        block_size = int(cfg.sample_rate * 0.025)
        n_blocks = len(audio) // block_size
        block_rms = np.array([
            np.sqrt(np.mean(audio[i*block_size:(i+1)*block_size]**2))
            for i in range(n_blocks)
        ])
        # Asymmetric threshold: higher for start (loud "Hey"), lower for end (quiet "Jane")
        peak_rms = block_rms.max()
        start_threshold = peak_rms * 0.25  # need loud onset to find "Hey"
        end_threshold = peak_rms * 0.08    # low to keep trailing "Jane"

        loud_blocks = np.where(block_rms > start_threshold)[0]
        quiet_blocks = np.where(block_rms > end_threshold)[0]

        if len(loud_blocks) > 0 and len(quiet_blocks) > 0:
            pad_blocks = 4  # 100ms padding
            start_block = max(0, loud_blocks[0] - pad_blocks)
            end_block = min(n_blocks - 1, quiet_blocks[-1] + pad_blocks)
            start_sample = start_block * block_size
            end_sample = min(len(audio), (end_block + 1) * block_size)
            trimmed = audio[start_sample:end_sample]
            if len(trimmed) >= int(cfg.sample_rate * 0.3):
                audio = trimmed

        self.current_audio = audio
        self.root.after(0, self._on_recording_done)

    def _on_recording_done(self):
        self.record_btn.configure(text="🎙 RECORD", bg="#e94560")

        if self.current_audio is None or len(self.current_audio) < 100:
            self.status_var.set("Recording failed — try again")
            return

        duration = len(self.current_audio) / cfg.sample_rate
        peak = np.abs(self.current_audio).max()
        if peak < 0.005:
            self.status_var.set(f"Too quiet (peak={peak:.4f}) — speak louder or check mic")
            return

        self.status_var.set(f"Recorded {duration:.2f}s (peak={peak:.3f}) — Save or re-record")
        self.save_btn.configure(state=tk.NORMAL)
        self._draw_waveform(self.current_audio)

    def _draw_waveform(self, audio: np.ndarray):
        self.canvas.delete("all")
        w, h = 660, 120
        mid = h // 2

        # Downsample for display
        n_points = min(len(audio), w)
        step = max(1, len(audio) // n_points)
        display = audio[::step][:n_points]

        # Draw waveform
        points = []
        for i, sample in enumerate(display):
            x = i * w / len(display)
            y = mid - sample * mid * 0.9
            points.append((x, y))

        for i in range(len(points) - 1):
            self.canvas.create_line(
                points[i][0], points[i][1],
                points[i+1][0], points[i+1][1],
                fill="#00d2ff", width=1,
            )

        # Center line
        self.canvas.create_line(0, mid, w, mid, fill="#333333", dash=(4, 4))

    def _save_sample(self):
        if self.current_audio is None:
            return

        existing = sorted(SAMPLES_DIR.glob("hey_jane_*.wav"))
        next_num = len(existing)
        path = SAMPLES_DIR / f"hey_jane_{next_num:03d}.wav"

        audio_int16 = (self.current_audio * 32767).clip(-32768, 32767).astype(np.int16)
        with wave.open(str(path), "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(cfg.sample_rate)
            wf.writeframes(audio_int16.tobytes())

        self.status_var.set(f"Saved: {path.name}")
        self.save_btn.configure(state=tk.DISABLED)
        self.current_audio = None
        self._refresh_samples()

    def _refresh_samples(self):
        self.sample_listbox.delete(0, tk.END)
        wavs = sorted(SAMPLES_DIR.glob("hey_jane_*.wav"))
        for wav in wavs:
            try:
                with wave.open(str(wav), "r") as wf:
                    dur = wf.getnframes() / wf.getframerate()
                self.sample_listbox.insert(tk.END, f"  {wav.name}  ({dur:.2f}s)")
            except Exception:
                self.sample_listbox.insert(tk.END, f"  {wav.name}  (error)")
        self.count_var.set(f"{len(wavs)} samples")

    def _play_selected(self):
        sel = self.sample_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        wavs = sorted(SAMPLES_DIR.glob("hey_jane_*.wav"))
        if idx >= len(wavs):
            return
        with wave.open(str(wavs[idx]), "r") as wf:
            data = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
            audio = data.astype(np.float32) / 32768.0
        self._draw_waveform(audio)
        sd.play(audio, cfg.sample_rate)

    def _delete_selected(self):
        sel = self.sample_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        wavs = sorted(SAMPLES_DIR.glob("hey_jane_*.wav"))
        if idx >= len(wavs):
            return
        wavs[idx].unlink()
        self._refresh_samples()
        self.status_var.set(f"Deleted sample")


def main():
    root = tk.Tk()
    app = RecorderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
