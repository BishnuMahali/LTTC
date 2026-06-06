"""
Copyright (c) 2026 Bishnu Mahali
Licensed under the MIT License. See LICENSE for details.

Sarvam Timed Captions (STC) - v1.0.0
Dual-Engine Edition (Sarvam AI & Whisper)
"""

import os
import sys
import shutil
import subprocess
import threading
import queue
import requests
import json
import base64
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pydub import AudioSegment
import pysrt

# Core Config
SARVAM_URL = "https://api.sarvam.ai/speech-to-text"
CHUNK_LENGTH_MS = 5000 
CONFIG_FILE = ".stc_config.json"

LANG_MAP = {
    "Bengali": "bn-IN",
    "Hindi": "hi-IN",
    "English": "en-IN",
    "Tamil": "ta-IN",
    "Telugu": "te-IN",
    "Kannada": "kn-IN",
    "Malayalam": "ml-IN",
    "Marathi": "mr-IN",
    "Gujarati": "gu-IN",
    "Punjabi": "pa-IN",
    "Odia": "or-IN",
}

WHISPER_MODELS = ["tiny", "base", "small", "medium", "large"]

def detect_hardware_acceleration():
    info = {"recommended": "cpu", "cuda_available": False, "devices": []}
    try:
        import torch
        if torch.cuda.is_available():
            info["cuda_available"] = True
            info["recommended"] = "cuda"
            for i in range(torch.cuda.device_count()):
                info["devices"].append(torch.cuda.get_device_name(i))
    except Exception: pass
    return info

def extract_audio(video_path, audio_path):
    command = ["ffmpeg", "-y", "-i", video_path, "-map", "0:a:0", "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", audio_path]
    try:
        subprocess.run(command, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        return True
    except Exception: return False

class STCGui:
    def __init__(self, root):
        self.root = root
        self.root.title("Sarvam Timed Captions - Dashboard")
        self.root.geometry("750x700")
        self.root.minsize(650, 650)
        
        self.log_queue = queue.Queue()
        
        # 1. Initialize ALL variables first
        self.engine_var = tk.StringVar(value="Sarvam AI (Cloud)")
        self.lang_var = tk.StringVar(value="Bengali")
        self.model_var = tk.StringVar(value="base")
        self.key_var = tk.StringVar()
        self.path_var = tk.StringVar()

        self.setup_styles()
        self.build_ui()
        
        # 2. Load settings into variables
        self.load_settings()
        
        # 3. Setup UI based on loaded settings
        self.toggle_engine_ui()
        
        # 4. Bind auto-save to changes
        for var in [self.engine_var, self.lang_var, self.model_var, self.key_var]:
            var.trace_add("write", lambda *args: self.save_settings())

        self.root.after(100, self.process_logs)

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        bg_color, card_color, accent_color, text_color = "#0f172a", "#1e293b", "#38bdf8", "#f8fafc"
        self.root.configure(bg=bg_color)
        style.configure("TFrame", background=bg_color)
        style.configure("Card.TFrame", background=card_color, borderwidth=1, relief="solid")
        style.configure("TLabel", background=card_color, foreground=text_color, font=("Segoe UI", 10))
        style.configure("Header.TLabel", background=card_color, foreground=accent_color, font=("Segoe UI", 12, "bold"))
        style.configure("Status.TLabel", background=bg_color, foreground="#10b981", font=("Segoe UI", 10, "bold"))
        style.configure("Action.TButton", font=("Segoe UI", 10, "bold"), padding=5)
        style.configure("Horizontal.TProgressbar", background=accent_color, troughcolor="#020617")

    def build_ui(self):
        container = ttk.Frame(self.root, padding=20)
        container.pack(fill="both", expand=True)

        # 1. Engine Selection
        engine_card = ttk.Frame(container, style="Card.TFrame", padding=15)
        engine_card.pack(fill="x", pady=(0, 10))
        ttk.Label(engine_card, text="1. SELECT TRANSCRIPTION ENGINE", style="Header.TLabel").pack(anchor="w")
        self.engine_combo = ttk.Combobox(engine_card, textvariable=self.engine_var, values=["Sarvam AI (Cloud)", "Whisper (Local)"], state="readonly")
        self.engine_combo.pack(fill="x", pady=(10, 0))
        self.engine_combo.bind("<<ComboboxSelected>>", self.toggle_engine_ui)

        # 2. Media Selection
        media_card = ttk.Frame(container, style="Card.TFrame", padding=15)
        media_card.pack(fill="x", pady=(0, 10))
        ttk.Label(media_card, text="2. SELECT MEDIA FILE", style="Header.TLabel").pack(anchor="w")
        f_row = ttk.Frame(media_card, style="Card.TFrame")
        f_row.pack(fill="x", pady=(10, 0))
        ttk.Entry(f_row, textvariable=self.path_var).pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Button(f_row, text="Browse...", command=self.browse_file, style="Action.TButton").pack(side="right")

        # 3. Settings Card (Dynamic Content)
        self.settings_card = ttk.Frame(container, style="Card.TFrame", padding=15)
        self.settings_card.pack(fill="x", pady=(0, 10))
        ttk.Label(self.settings_card, text="3. ENGINE SETTINGS", style="Header.TLabel").pack(anchor="w")
        
        self.dynamic_frame = ttk.Frame(self.settings_card, style="Card.TFrame")
        self.dynamic_frame.pack(fill="x", pady=(10, 0))
        
        # 4. Common Settings
        common_card = ttk.Frame(container, style="Card.TFrame", padding=15)
        common_card.pack(fill="x", pady=(0, 10))
        ttk.Label(common_card, text="4. LANGUAGE", style="Header.TLabel").pack(anchor="w")
        self.lang_combo = ttk.Combobox(common_card, textvariable=self.lang_var, values=list(LANG_MAP.keys()), state="readonly")
        self.lang_combo.pack(fill="x", pady=(10, 0))

        # 5. Actions
        btn_row = ttk.Frame(container)
        btn_row.pack(fill="x", pady=10)
        self.start_btn = ttk.Button(btn_row, text="START TASK", command=self.start_task, style="Action.TButton")
        self.start_btn.pack(side="left", fill="x", expand=True, padx=(0, 5))
        ttk.Button(btn_row, text="Exit", command=self.root.quit, style="Action.TButton").pack(side="right")
        
        self.progress = ttk.Progressbar(container, orient="horizontal", mode="determinate", style="Horizontal.TProgressbar")
        self.log_text = tk.Text(container, height=8, bg="#020617", fg="#cbd5e1", font=("Consolas", 9), padx=10, pady=10)
        self.log_text.pack(fill="both", expand=True, pady=10)
        self.status_label = ttk.Label(container, text="READY", style="Status.TLabel")
        self.status_label.pack()

    def toggle_engine_ui(self, event=None):
        for widget in self.dynamic_frame.winfo_children(): widget.destroy()
        engine = self.engine_var.get()
        if "Sarvam" in engine:
            ttk.Label(self.dynamic_frame, text="Sarvam API Key:").pack(anchor="w")
            ttk.Entry(self.dynamic_frame, textvariable=self.key_var, show="*").pack(fill="x", pady=5)
        else:
            row = ttk.Frame(self.dynamic_frame, style="Card.TFrame")
            row.pack(fill="x")
            ttk.Label(row, text="Whisper Model:").pack(side="left", padx=5)
            ttk.Combobox(row, textvariable=self.model_var, values=WHISPER_MODELS, state="readonly").pack(side="left", fill="x", expand=True, padx=5)

    def load_settings(self):
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, "r") as f:
                    cfg = json.load(f)
                    self.engine_var.set(cfg.get("engine", "Sarvam AI (Cloud)"))
                    self.lang_var.set(cfg.get("lang", "Bengali"))
                    if "key_enc" in cfg:
                        decoded_key = base64.b64decode(cfg["key_enc"].encode()).decode()
                        self.key_var.set(decoded_key)
                    if "model" in cfg:
                        self.model_var.set(cfg["model"])
        except Exception: pass

    def save_settings(self):
        try:
            cfg = {"engine": self.engine_var.get(), "lang": self.lang_var.get()}
            key = self.key_var.get().strip()
            if key: cfg["key_enc"] = base64.b64encode(key.encode()).decode()
            cfg["model"] = self.model_var.get()
            with open(CONFIG_FILE, "w") as f: json.dump(cfg, f)
        except Exception: pass

    def write_log(self, msg): self.log_queue.put(msg)
    def process_logs(self):
        try:
            while True:
                self.log_text.insert(tk.END, f"> {self.log_queue.get_nowait()}\n")
                self.log_text.see(tk.END)
        except queue.Empty: pass
        self.root.after(100, self.process_logs)

    def browse_file(self):
        p = filedialog.askopenfilename(filetypes=[("Media", "*.mp4 *.mkv *.mov *.avi *.mp3 *.wav *.m4a *.flac"), ("All", "*.*")])
        if p: self.path_var.set(p); self.write_log(f"Loaded: {os.path.basename(p)}")

    def start_task(self):
        self.save_settings()
        f = self.path_var.get().strip()
        if not f or not os.path.isfile(f): messagebox.showerror("Error", "Select a valid file."); return
        self.start_btn.state(["disabled"])
        self.progress.pack(fill="x", pady=5, before=self.log_text)
        threading.Thread(target=self.worker, args=(f,), daemon=True).start()

    def worker(self, f):
        temp_audio = "temp_audio_full.wav"
        try:
            self.write_log("Extracting audio...")
            extract_audio(f, temp_audio)
            
            engine = self.engine_var.get()
            lang_code = LANG_MAP[self.lang_var.get()]
            subs = pysrt.SubRipFile()
            
            audio = AudioSegment.from_wav(temp_audio)
            chunks = [audio[i:i+CHUNK_LENGTH_MS] for i in range(0, len(audio), CHUNK_LENGTH_MS)]
            total_chunks = len(chunks)
            
            self.write_log(f"Processing {total_chunks} segments via {engine}...")
            
            whisper_model = None
            hw = None
            if "Whisper" in engine:
                import whisper
                hw = detect_hardware_acceleration()
                self.write_log(f"Loading Whisper {self.model_var.get()}...")
                whisper_model = whisper.load_model(self.model_var.get(), device=hw["recommended"])

            for idx, chunk in enumerate(chunks):
                chunk_start_sec = (idx * CHUNK_LENGTH_MS) / 1000.0
                self.root.after(0, lambda p=((idx+1)/total_chunks)*100: self.progress.configure(value=p))
                
                c_file = f"temp_c_{idx}.wav"
                chunk.export(c_file, format="wav")
                
                segments = []
                
                if "Sarvam" in engine:
                    key = self.key_var.get().strip()
                    resp = requests.post(
                        SARVAM_URL, 
                        headers={'api-subscription-key': key}, 
                        data={"model": "saaras:v3", "language_code": lang_code, "with_timestamps": "true"}, 
                        files=[('file', (c_file, open(c_file, 'rb'), 'audio/wav'))]
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        segments = data.get("segments", [{"text": data.get("transcript", ""), "start_time_seconds": 0, "end_time_seconds": len(chunk)/1000.0}])
                    else:
                        self.write_log(f"API Error on segment {idx}: {resp.text}")
                else:
                    res = whisper_model.transcribe(c_file, language=lang_code[:2], task="transcribe")
                    segments = [{"text": s["text"], "start_time_seconds": s["start"], "end_time_seconds": s["end"]} for s in res.get("segments", [])]

                os.remove(c_file)

                for s in segments:
                    text = s["text"].strip()
                    if text:
                        start = chunk_start_sec + s["start_time_seconds"]
                        end = chunk_start_sec + s["end_time_seconds"]
                        subs.append(pysrt.SubRipItem(
                            index=len(subs)+1, 
                            start=pysrt.SubRipTime(seconds=start), 
                            end=pysrt.SubRipTime(seconds=end), 
                            text=text
                        ))

            out = os.path.splitext(f)[0] + ".srt"
            subs.save(out, encoding="utf-8")
            self.write_log(f"SUCCESS: {os.path.basename(out)}")
            self.root.after(0, lambda: self.status_label.configure(text="COMPLETED", foreground="#10b981"))
        except Exception as e:
            self.write_log(f"FATAL: {str(e)}")
            self.root.after(0, lambda: self.status_label.configure(text="FAILED", foreground="#ef4444"))
        finally:
            if os.path.exists(temp_audio): os.remove(temp_audio)
            self.root.after(0, self.progress.pack_forget)
            self.root.after(0, lambda: self.start_btn.state(["!disabled"]))

def main():
    root = tk.Tk(); app = STCGui(root); root.mainloop()

if __name__ == "__main__":
    main()
