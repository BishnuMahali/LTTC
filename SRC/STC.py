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
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pydub import AudioSegment
import pysrt

# Core Config
SARVAM_URL = "https://api.sarvam.ai/speech-to-text"

# Path Logic: Ensure we use the project root even if run from SRC/
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR) if os.path.basename(SCRIPT_DIR).upper() == "SRC" else SCRIPT_DIR

CONFIG_DIR = os.path.join(BASE_DIR, "CONFIG")
TEMP_DIR = os.path.join(BASE_DIR, "TEMP")
CONFIG_FILE = os.path.join(CONFIG_DIR, ".stc_config.json")

# Ensure core directories exist
os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

def cleanup_temp():
    """Wipes the TEMP directory to keep root clean."""
    if os.path.exists(TEMP_DIR):
        for f in os.listdir(TEMP_DIR):
            try:
                path = os.path.join(TEMP_DIR, f)
                if os.path.isfile(path): os.remove(path)
                elif os.path.isdir(path): shutil.rmtree(path)
            except: pass

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
    except: pass
    return info

def extract_audio(video_path, audio_path):
    command = ["ffmpeg", "-y", "-i", video_path, "-map", "0:a:0", "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", audio_path]
    try:
        subprocess.run(command, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        return True
    except: return False

def check_whisper_model_cached(model_name):
    try:
        cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "whisper")
        if not os.path.exists(cache_dir):
            return False
        for f in os.listdir(cache_dir):
            if f.startswith(model_name) and f.endswith(".pt"):
                return True
    except:
        pass
    return False

class STCGui:
    def __init__(self, root):
        self.root = root
        self.root.title("Sarvam Timed Captions - Dashboard")
        self.root.geometry("750x780")
        self.root.minsize(650, 650)
        
        self.log_queue = queue.Queue()
        
        # 1. Initialize ALL variables first
        self.engine_var = tk.StringVar(value="Sarvam AI (Cloud)")
        self.lang_var = tk.StringVar(value="Bengali")
        self.model_var = tk.StringVar(value="base")
        self.key_var = tk.StringVar()
        self.path_var = tk.StringVar()
        
        self.sarvam_plan_var = tk.StringVar(value="Starter (60 RPM)")
        self.sarvam_custom_rpm_var = tk.StringVar(value="60")
        self.chunk_len_var = tk.StringVar(value="5")
        self.chunking_mode_var = tk.StringVar(value="throttle")
        self.enable_chunking_var = tk.BooleanVar(value=True)

        self.setup_styles()
        self.build_ui()
        
        # 2. Load settings into variables
        self.load_settings()
        
        # 3. Setup UI based on loaded settings
        self.toggle_engine_ui()
        
        # 4. Bind auto-save to changes
        for var in [self.engine_var, self.lang_var, self.model_var, self.key_var,
                    self.sarvam_plan_var, self.sarvam_custom_rpm_var, self.chunk_len_var,
                    self.chunking_mode_var, self.enable_chunking_var]:
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
        style.configure("TCheckbutton", background=card_color, foreground=text_color, font=("Segoe UI", 10))
        style.configure("TRadiobutton", background=card_color, foreground=text_color, font=("Segoe UI", 10))

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
        
        # Automatic defaults when engine is changed by user interaction
        if event is not None:
            if "Sarvam" in engine:
                self.enable_chunking_var.set(True)
            else:
                self.enable_chunking_var.set(False)

        if "Sarvam" in engine:
            # 1. API Key Row
            row_key = ttk.Frame(self.dynamic_frame, style="Card.TFrame")
            row_key.pack(fill="x", pady=2)
            ttk.Label(row_key, text="Sarvam API Key:").pack(side="left", padx=5)
            ttk.Entry(row_key, textvariable=self.key_var, show="*").pack(side="left", fill="x", expand=True, padx=5)
            
            # 2. Plan Row
            row_plan = ttk.Frame(self.dynamic_frame, style="Card.TFrame")
            row_plan.pack(fill="x", pady=2)
            ttk.Label(row_plan, text="API Plan Limit:").pack(side="left", padx=5)
            plan_combo = ttk.Combobox(row_plan, textvariable=self.sarvam_plan_var, 
                                      values=["Starter (60 RPM)", "Pro (200 RPM)", "Business (1000 RPM)", "Custom Limit"], 
                                      state="readonly")
            plan_combo.pack(side="left", fill="x", expand=True, padx=5)
            plan_combo.bind("<<ComboboxSelected>>", lambda e: self.update_custom_rpm_visibility())
            
            # 3. Custom RPM Row
            self.row_custom = ttk.Frame(self.dynamic_frame, style="Card.TFrame")
            ttk.Label(self.row_custom, text="Custom RPM:").pack(side="left", padx=5)
            ttk.Entry(self.row_custom, textvariable=self.sarvam_custom_rpm_var, width=10).pack(side="left", padx=5)
            
            self.update_custom_rpm_visibility()
            
            # 4. Enable Chunking Checkbox
            row_chk = ttk.Frame(self.dynamic_frame, style="Card.TFrame")
            row_chk.pack(fill="x", pady=4)
            ttk.Checkbutton(row_chk, text="Enable Chunking (REST API requires this for >30s)", 
                            variable=self.enable_chunking_var, 
                            command=self.update_chunking_controls_visibility).pack(side="left", padx=5)
            
            # 5. Chunking Settings Frame (contains length and radio buttons)
            self.chunking_settings_frame = ttk.Frame(self.dynamic_frame, style="Card.TFrame")
            
            row_len = ttk.Frame(self.chunking_settings_frame, style="Card.TFrame")
            row_len.pack(fill="x", pady=2)
            ttk.Label(row_len, text="Chunk Length (seconds):").pack(side="left", padx=5)
            ttk.Entry(row_len, textvariable=self.chunk_len_var, width=8).pack(side="left", padx=5)
            
            row_radio = ttk.Frame(self.chunking_settings_frame, style="Card.TFrame")
            row_radio.pack(fill="x", pady=2)
            ttk.Radiobutton(row_radio, text="Smart adjust chunk length to complete in one go (No Waiting)", 
                            variable=self.chunking_mode_var, value="smart").pack(anchor="w", padx=5, pady=2)
            ttk.Radiobutton(row_radio, text="Maintain fixed chunk length and wait to respect rate limit", 
                            variable=self.chunking_mode_var, value="throttle").pack(anchor="w", padx=5, pady=2)
            
            self.update_chunking_controls_visibility()
            
        else:
            # Whisper Engine Settings
            row_model = ttk.Frame(self.dynamic_frame, style="Card.TFrame")
            row_model.pack(fill="x", pady=2)
            ttk.Label(row_model, text="Whisper Model:").pack(side="left", padx=5)
            model_combo = ttk.Combobox(row_model, textvariable=self.model_var, values=WHISPER_MODELS, state="readonly")
            model_combo.pack(side="left", fill="x", expand=True, padx=5)
            model_combo.bind("<<ComboboxSelected>>", lambda e: self.update_whisper_status_label())
            
            # Hardware and Status info
            row_info = ttk.Frame(self.dynamic_frame, style="Card.TFrame")
            row_info.pack(fill="x", pady=2)
            
            hw = detect_hardware_acceleration()
            hw_text = f"Hardware: {hw['recommended'].upper()}"
            if hw['cuda_available'] and hw['devices']:
                hw_text += f" ({hw['devices'][0]})"
            
            ttk.Label(row_info, text=hw_text, font=("Segoe UI", 9, "italic")).pack(side="left", padx=5)
            
            self.model_status_label = ttk.Label(row_info, text="Status: Checking...", font=("Segoe UI", 9, "bold"))
            self.model_status_label.pack(side="right", padx=10)
            self.update_whisper_status_label()
            
            # Check & Download button
            row_btn = ttk.Frame(self.dynamic_frame, style="Card.TFrame")
            row_btn.pack(fill="x", pady=2)
            self.download_btn = ttk.Button(row_btn, text="Check & Download Model", command=self.check_download_model)
            self.download_btn.pack(fill="x", padx=5, pady=2)
            
            # Enable Chunking Checkbox
            row_chk = ttk.Frame(self.dynamic_frame, style="Card.TFrame")
            row_chk.pack(fill="x", pady=4)
            ttk.Checkbutton(row_chk, text="Enable Chunking (Not recommended for Whisper)", 
                            variable=self.enable_chunking_var, 
                            command=self.update_chunking_controls_visibility).pack(side="left", padx=5)
            
            # Chunking Settings Frame
            self.chunking_settings_frame = ttk.Frame(self.dynamic_frame, style="Card.TFrame")
            row_len = ttk.Frame(self.chunking_settings_frame, style="Card.TFrame")
            row_len.pack(fill="x", pady=2)
            ttk.Label(row_len, text="Chunk Length (seconds):").pack(side="left", padx=5)
            ttk.Entry(row_len, textvariable=self.chunk_len_var, width=8).pack(side="left", padx=5)
            
            self.update_chunking_controls_visibility()

    def update_custom_rpm_visibility(self):
        if self.sarvam_plan_var.get() == "Custom Limit":
            self.row_custom.pack(fill="x", pady=2)
        else:
            self.row_custom.pack_forget()

    def update_chunking_controls_visibility(self):
        if self.enable_chunking_var.get():
            self.chunking_settings_frame.pack(fill="x", pady=2)
        else:
            self.chunking_settings_frame.pack_forget()

    def update_whisper_status_label(self):
        model_name = self.model_var.get()
        try:
            cached = check_whisper_model_cached(model_name)
            if cached:
                self.model_status_label.configure(text="Status: Cached (Ready)", foreground="#10b981")
            else:
                self.model_status_label.configure(text="Status: Needs Download", foreground="#ef4444")
        except:
            self.model_status_label.configure(text="Status: Unknown", foreground="#cbd5e1")

    def check_download_model(self):
        self.download_btn.state(["disabled"])
        self.model_status_label.configure(text="Status: Checking...", foreground="#38bdf8")
        threading.Thread(target=self._check_download_worker, daemon=True).start()
        
    def _check_download_worker(self):
        model_name = self.model_var.get()
        try:
            self.write_log(f"Checking/Downloading Whisper '{model_name}' model...")
            self.root.after(0, lambda: self.model_status_label.configure(text="Status: Downloading...", foreground="#38bdf8"))
            
            import whisper
            hw = detect_hardware_acceleration()
            device = hw["recommended"]
            
            # This downloads the model to cache if not already present
            whisper.load_model(model_name, device=device)
            
            self.write_log(f"Whisper '{model_name}' model is loaded and ready on {device.upper()}.")
            self.root.after(0, lambda: self.model_status_label.configure(text="Status: Cached (Ready)", foreground="#10b981"))
        except Exception as e:
            self.write_log(f"Error checking/downloading model: {str(e)}")
            self.root.after(0, lambda: self.model_status_label.configure(text="Status: Failed to load", foreground="#ef4444"))
        finally:
            self.root.after(0, lambda: self.download_btn.state(["!disabled"]))

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
                    self.sarvam_plan_var.set(cfg.get("sarvam_plan", "Starter (60 RPM)"))
                    self.sarvam_custom_rpm_var.set(cfg.get("sarvam_custom_rpm", "60"))
                    self.chunk_len_var.set(cfg.get("chunk_len_sec", "5"))
                    self.chunking_mode_var.set(cfg.get("chunking_mode", "throttle"))
                    self.enable_chunking_var.set(cfg.get("enable_chunking", True))
        except: pass

    def save_settings(self):
        try:
            cfg = {
                "engine": self.engine_var.get(), 
                "lang": self.lang_var.get(),
                "model": self.model_var.get(),
                "sarvam_plan": self.sarvam_plan_var.get(),
                "sarvam_custom_rpm": self.sarvam_custom_rpm_var.get(),
                "chunk_len_sec": self.chunk_len_var.get(),
                "chunking_mode": self.chunking_mode_var.get(),
                "enable_chunking": self.enable_chunking_var.get()
            }
            key = self.key_var.get().strip()
            if key: cfg["key_enc"] = base64.b64encode(key.encode()).decode()
            with open(CONFIG_FILE, "w") as f: json.dump(cfg, f)
        except: pass

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

    def ask_fallback(self, event, result_dict):
        msg = ("Sarvam AI API rate limit or quota exceeded.\n\n"
               "Would you like to fallback to Local AI (Whisper) to transcribe the remaining chunks?\n"
               "Click 'Yes' to Fallback, or 'No' to STOP the process.")
        ans = messagebox.askyesno("API Quota/Limit Exceeded", msg)
        result_dict["fallback"] = ans
        event.set()

    def worker(self, f):
        cleanup_temp()
        temp_audio = os.path.join(TEMP_DIR, "temp_audio_full.wav")
        try:
            self.write_log("Extracting audio...")
            extract_audio(f, temp_audio)
            
            engine = self.engine_var.get()
            lang_code = LANG_MAP[self.lang_var.get()]
            subs = pysrt.SubRipFile()
            
            audio = AudioSegment.from_wav(temp_audio)
            total_duration_sec = len(audio) / 1000.0
            enable_chunking = self.enable_chunking_var.get()
            
            # API Request limits config (only relevant for Sarvam)
            plan = self.sarvam_plan_var.get()
            rpm_limit = 60
            if "Starter" in plan: rpm_limit = 60
            elif "Pro" in plan: rpm_limit = 200
            elif "Business" in plan: rpm_limit = 1000
            elif "Custom" in plan:
                try: rpm_limit = int(self.sarvam_custom_rpm_var.get().strip())
                except: rpm_limit = 60
            
            chunk_len_sec = 5.0
            try: chunk_len_sec = float(self.chunk_len_var.get().strip())
            except: chunk_len_sec = 5.0
            
            # Setup chunk length based on mode
            if enable_chunking:
                if self.chunking_mode_var.get() == "smart" and "Sarvam" in engine:
                    # Smart calculation: total_duration / rpm_limit
                    smart_len = total_duration_sec / rpm_limit
                    # Clamp between 5s and 30s to respect REST API constraints
                    chunk_len_sec = min(30.0, max(5.0, smart_len))
                    self.write_log(f"Smart chunk length calculated: {chunk_len_sec:.2f}s (based on {total_duration_sec:.1f}s file duration and {rpm_limit} RPM)")
                else:
                    # For Sarvam, clamp user value to max 30s because of API constraints
                    if "Sarvam" in engine:
                        chunk_len_sec = min(30.0, max(1.0, chunk_len_sec))
                        
                chunk_len_ms = int(chunk_len_sec * 1000)
                chunks = [audio[i:i+chunk_len_ms] for i in range(0, len(audio), chunk_len_ms)]
            else:
                chunks = [audio]
                chunk_len_sec = total_duration_sec
                
            total_chunks = len(chunks)
            self.write_log(f"Processing {total_chunks} segments via {engine}...")
            
            whisper_model = None
            hw = None
            if "Whisper" in engine:
                import whisper
                hw = detect_hardware_acceleration()
                self.write_log(f"Loading Whisper {self.model_var.get()}...")
                whisper_model = whisper.load_model(self.model_var.get(), device=hw["recommended"])
            
            # Sliding window request history for rate limit tracking
            request_times = []
            
            for idx, chunk in enumerate(chunks):
                chunk_start_sec = (idx * chunk_len_sec) if enable_chunking else 0.0
                self.root.after(0, lambda p=((idx+1)/total_chunks)*100: self.progress.configure(value=p))
                
                c_file = os.path.join(TEMP_DIR, f"temp_c_{idx}.wav")
                chunk.export(c_file, format="wav")
                
                segments = []
                
                # We use a loop for transcription to allow fallback retry in the same iteration
                transcribed = False
                while not transcribed:
                    if "Sarvam" in engine:
                        # Throttling/Wait logic (both in smart and throttle mode as safety check)
                        now = time.time()
                        request_times = [t for t in request_times if now - t < 60]
                        if len(request_times) >= rpm_limit:
                            sleep_time = (request_times[0] + 60) - now
                            if sleep_time > 0:
                                self.write_log(f"Rate limit safety: sleeping for {sleep_time:.2f}s to respect the {rpm_limit} RPM limit...")
                                time.sleep(sleep_time)
                            now = time.time()
                            request_times = [t for t in request_times if now - t < 60]
                        request_times.append(now)
                        
                        key = self.key_var.get().strip()
                        resp = requests.post(
                            SARVAM_URL, 
                            headers={'api-subscription-key': key}, 
                            data={"model": "saaras:v3", "language_code": lang_code, "with_timestamps": "true"}, 
                            files=[('file', (c_file, open(c_file, 'rb'), 'audio/wav'))]
                        )
                        
                        is_quota_error = False
                        if resp.status_code == 429:
                            is_quota_error = True
                        elif resp.status_code in [400, 401, 403]:
                            err_msg = resp.text.lower()
                            if any(x in err_msg for x in ["quota", "limit exceeded", "credit", "balance", "rate limit", "too many requests"]):
                                is_quota_error = True
                                
                        if resp.status_code == 200:
                            data = resp.json()
                            segments = data.get("segments", [{"text": data.get("transcript", ""), "start_time_seconds": 0, "end_time_seconds": len(chunk)/1000.0}])
                            transcribed = True
                        elif is_quota_error:
                            self.write_log("API rate limit or quota exceeded!")
                            event = threading.Event()
                            result_dict = {"fallback": False}
                            self.root.after(0, lambda: self.ask_fallback(event, result_dict))
                            event.wait() # Block worker until choice is made
                            
                            if result_dict["fallback"]:
                                self.write_log("User selected fallback to Whisper (Local). Switching...")
                                engine = "Whisper (Local)"
                                self.root.after(0, lambda: self.engine_var.set("Whisper (Local)"))
                                self.root.after(0, self.toggle_engine_ui)
                                
                                if whisper_model is None:
                                    import whisper
                                    hw = detect_hardware_acceleration()
                                    self.write_log(f"Loading Whisper {self.model_var.get()}...")
                                    whisper_model = whisper.load_model(self.model_var.get(), device=hw["recommended"])
                            else:
                                self.write_log("Process stopped by user.")
                                raise Exception("API rate limit or quota exceeded. Process stopped.")
                        else:
                            self.write_log(f"API Error on segment {idx}: {resp.text}")
                            raise Exception(f"API Error: {resp.text}")
                    else:
                        # Local Whisper Mode
                        res = whisper_model.transcribe(c_file, language=lang_code[:2], task="transcribe")
                        segments = [{"text": s["text"], "start_time_seconds": s["start"], "end_time_seconds": s["end"]} for s in res.get("segments", [])]
                        transcribed = True
                
                if os.path.exists(c_file): os.remove(c_file)
                
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
