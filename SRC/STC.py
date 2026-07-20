"""
Copyright (c) 2026 Bishnu Mahali
Licensed under the MIT License. See LICENSE for details.

Sarvam Timed Captions (STC) - v1.0.0
Dual-Engine Edition (Sarvam AI & Whisper)
"""

import os
import shutil
import subprocess
import threading
import queue
import requests
import json
import base64
import time
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from tkinterdnd2 import TkinterDnD, DND_FILES
from pydub import AudioSegment
from pydub.silence import detect_silence
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

# Set customtkinter appearance and theme
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

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

def split_audio_fixed(audio, target_len_ms):
    total_len = len(audio)
    chunks = []
    for i in range(0, total_len, target_len_ms):
        p_start = i
        p_end = min(total_len, i + target_len_ms)
        chunks.append({
            "audio": audio[p_start:p_end],
            "start_sec": p_start / 1000.0,
            "duration_sec": (p_end - p_start) / 1000.0
        })
    return chunks

def split_audio_smart(audio, target_len_ms, min_silence_len=200, silence_thresh=-40):
    total_len = len(audio)
    cut_points = [0]
    current_start = 0
    
    # We search for silence in a window around the target cut point
    # Search window: from target - 1500ms to target + 1500ms
    window_half = 1500
    
    while current_start + target_len_ms < total_len:
        target_cut = current_start + target_len_ms
        
        # Ensure we don't make a segment shorter than 1000ms
        search_start = max(current_start + 1000, target_cut - window_half)
        search_end = min(total_len - 1000, target_cut + window_half)
        
        cut_point = target_cut
        
        if search_start < search_end:
            search_segment = audio[search_start:search_end]
            silences = detect_silence(search_segment, min_silence_len=min_silence_len, silence_thresh=silence_thresh)
            
            if not silences:
                # Try higher threshold (softer background noise / louder parts)
                silences = detect_silence(search_segment, min_silence_len=min_silence_len, silence_thresh=silence_thresh + 8)
                
            if silences:
                # Find the silence interval closest to the target cut relative point
                target_rel = target_cut - search_start
                closest_mid = None
                min_diff = float('inf')
                
                for start_rel, end_rel in silences:
                    mid_rel = (start_rel + end_rel) / 2
                    diff = abs(mid_rel - target_rel)
                    if diff < min_diff:
                        min_diff = diff
                        closest_mid = search_start + mid_rel
                
                if closest_mid is not None:
                    cut_point = int(closest_mid)
                    
        cut_points.append(cut_point)
        current_start = cut_point
        
    cut_points.append(total_len)
    
    # Generate chunk dicts
    chunks = []
    for i in range(len(cut_points) - 1):
        p_start = cut_points[i]
        p_end = cut_points[i+1]
        chunks.append({
            "audio": audio[p_start:p_end],
            "start_sec": p_start / 1000.0,
            "duration_sec": (p_end - p_start) / 1000.0
        })
    return chunks

class STCGui(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self):
        super().__init__()
        # Initialize drag and drop library
        self.TkdndVersion = TkinterDnD._require(self)
        
        self.title("Sarvam Timed Captions - Dashboard")
        self.geometry("820x780")
        self.minsize(760, 680)
        
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
        self.smart_silence_var = tk.BooleanVar(value=True)
        self.file_info_var = tk.StringVar(value="No media file selected")

        self.build_ui()
        
        # 2. Load settings into variables
        self.load_settings()
        
        # 3. Setup UI based on loaded settings
        self.toggle_engine_ui()
        
        # 4. Bind auto-save and UI updates to changes
        self.engine_var.trace_add("write", lambda *args: self.handle_engine_change())
        self.enable_chunking_var.trace_add("write", lambda *args: self.update_chunking_controls_visibility())
        self.sarvam_plan_var.trace_add("write", lambda *args: self.update_custom_rpm_visibility())
        self.model_var.trace_add("write", lambda *args: self.update_whisper_status_label())
        self.smart_silence_var.trace_add("write", lambda *args: self.save_settings())
        
        for var in [self.engine_var, self.lang_var, self.model_var, self.key_var,
                    self.sarvam_plan_var, self.sarvam_custom_rpm_var, self.chunk_len_var,
                    self.chunking_mode_var, self.enable_chunking_var, self.smart_silence_var]:
            var.trace_add("write", lambda *args: self.save_settings())

        # Register Drag and Drop for the whole window
        self.drop_target_register(DND_FILES)
        self.dnd_bind('<<Drop>>', self.on_file_drop)

        self.after(100, self.process_logs)

    def build_ui(self):
        # Main Dashboard Container
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=20)

        # Header section (Title & Subtitle)
        header_frame = ctk.CTkFrame(container, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 15))
        
        title_label = ctk.CTkLabel(header_frame, text="Sarvam Timed Captions", font=("Segoe UI", 20, "bold"), text_color="#f8fafc")
        title_label.pack(anchor="w")
        
        subtitle_label = ctk.CTkLabel(header_frame, text="Dual-Engine Indic Transcription Studio", font=("Segoe UI", 11), text_color="#94a3b8")
        subtitle_label.pack(anchor="w", pady=(2, 0))

        # Main Columns Layout
        cols_frame = ctk.CTkFrame(container, fg_color="transparent")
        cols_frame.pack(fill="both", expand=True)
        
        cols_frame.columnconfigure(0, weight=1, uniform="col")
        cols_frame.columnconfigure(1, weight=1, uniform="col")
        cols_frame.rowconfigure(0, weight=1)

        # Left Column Frame
        left_col = ctk.CTkFrame(cols_frame, fg_color="transparent")
        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        
        # Right Column Frame
        right_col = ctk.CTkFrame(cols_frame, fg_color="transparent")
        right_col.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

        # CARD 1: Media Source (Left Column)
        media_card = ctk.CTkFrame(left_col, corner_radius=12, border_width=1, border_color="#334155", fg_color="#1e293b")
        media_card.pack(fill="x", pady=(0, 15))
        
        lbl = ctk.CTkLabel(media_card, text="MEDIA SOURCE", font=("Segoe UI", 11, "bold"), text_color="#38bdf8")
        lbl.pack(anchor="w", padx=15, pady=(15, 5))
        
        f_row = ctk.CTkFrame(media_card, fg_color="transparent")
        f_row.pack(fill="x", padx=15, pady=5)
        self.entry_path = ctk.CTkEntry(f_row, textvariable=self.path_var, placeholder_text="Select media file...", height=32)
        self.entry_path.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.btn_browse = ctk.CTkButton(f_row, text="Browse...", width=80, height=32, command=self.browse_file, fg_color="#334155", hover_color="#475569")
        self.btn_browse.pack(side="right")
        
        # Drag & Drop Zone
        self.drop_zone = ctk.CTkFrame(media_card, height=65, corner_radius=8, border_width=1, border_color="#475569", fg_color="#0f172a")
        self.drop_zone.pack(fill="x", padx=15, pady=5)
        self.drop_zone.pack_propagate(False) # Keep fixed height
        self.drop_label = ctk.CTkLabel(self.drop_zone, text="Drag & Drop Media File Here", font=("Segoe UI", 10, "italic"), text_color="#94a3b8")
        self.drop_label.pack(expand=True)
        
        # Register DND specifically on the drop zone
        self.drop_zone.drop_target_register(DND_FILES)
        self.drop_zone.dnd_bind('<<Drop>>', self.on_file_drop)
        self.drop_label.drop_target_register(DND_FILES)
        self.drop_label.dnd_bind('<<Drop>>', self.on_file_drop)
        
        self.file_info_label = ctk.CTkLabel(media_card, textvariable=self.file_info_var, font=("Segoe UI", 9, "italic"), text_color="#94a3b8")
        self.file_info_label.pack(anchor="w", padx=15, pady=(5, 15))

        # CARD 2: Engine Settings (Left Column)
        engine_card = ctk.CTkFrame(left_col, corner_radius=12, border_width=1, border_color="#334155", fg_color="#1e293b")
        engine_card.pack(fill="both", expand=True)
        
        lbl_engine = ctk.CTkLabel(engine_card, text="TRANSCRIPTION ENGINE", font=("Segoe UI", 11, "bold"), text_color="#38bdf8")
        lbl_engine.pack(anchor="w", padx=15, pady=(15, 5))
        
        self.engine_combo = ctk.CTkOptionMenu(engine_card, variable=self.engine_var, values=["Sarvam AI (Cloud)", "Whisper (Local)"], height=32)
        self.engine_combo.pack(fill="x", padx=15, pady=5)
        
        self.dynamic_frame = ctk.CTkFrame(engine_card, fg_color="transparent")
        self.dynamic_frame.pack(fill="both", expand=True, padx=15, pady=(10, 15))

        # CARD 3: Language Settings (Right Column)
        settings_card = ctk.CTkFrame(right_col, corner_radius=12, border_width=1, border_color="#334155", fg_color="#1e293b")
        settings_card.pack(fill="x", pady=(0, 15))
        
        lbl_settings = ctk.CTkLabel(settings_card, text="TRANSCRIPTION SETTINGS", font=("Segoe UI", 11, "bold"), text_color="#38bdf8")
        lbl_settings.pack(anchor="w", padx=15, pady=(15, 5))
        
        row_lang = ctk.CTkFrame(settings_card, fg_color="transparent")
        row_lang.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(row_lang, text="Language:").pack(side="left")
        self.lang_combo = ctk.CTkOptionMenu(row_lang, variable=self.lang_var, values=list(LANG_MAP.keys()), height=32)
        self.lang_combo.pack(side="right", fill="x", expand=True, padx=(10, 0))

        # CARD 4: Control Center (Right Column)
        control_card = ctk.CTkFrame(right_col, corner_radius=12, border_width=1, border_color="#334155", fg_color="#1e293b")
        control_card.pack(fill="both", expand=True)
        
        lbl_control = ctk.CTkLabel(control_card, text="CONTROL CENTER", font=("Segoe UI", 11, "bold"), text_color="#38bdf8")
        lbl_control.pack(anchor="w", padx=15, pady=(15, 5))
        
        self.start_btn = ctk.CTkButton(control_card, text="START TASK", font=("Segoe UI", 12, "bold"), fg_color="#6366f1", hover_color="#4f46e5", height=42, command=self.start_task)
        self.start_btn.pack(fill="x", padx=15, pady=(20, 10))
        
        self.progress = ctk.CTkProgressBar(control_card, progress_color="#38bdf8")
        
        status_row = ctk.CTkFrame(control_card, fg_color="transparent")
        status_row.pack(fill="x", padx=15, pady=(10, 15))
        ctk.CTkLabel(status_row, text="Status:", font=("Segoe UI", 10, "bold")).pack(side="left")
        self.status_label = ctk.CTkLabel(status_row, text="READY", text_color="#10b981", font=("Segoe UI", 10, "bold"))
        self.status_label.pack(side="left", padx=10)

        # CARD 5: System Logs (Bottom)
        logs_card = ctk.CTkFrame(container, corner_radius=12, border_width=1, border_color="#334155", fg_color="#1e293b")
        logs_card.pack(fill="both", expand=True, pady=(15, 0))
        
        lbl_logs = ctk.CTkLabel(logs_card, text="SYSTEM LOGS & TERMINAL", font=("Segoe UI", 11, "bold"), text_color="#38bdf8")
        lbl_logs.pack(anchor="w", padx=15, pady=(15, 5))
        
        self.log_text = ctk.CTkTextbox(logs_card, font=("Consolas", 11), fg_color="#0f172a", text_color="#cbd5e1", border_width=1, border_color="#334155")
        self.log_text.pack(fill="both", expand=True, padx=15, pady=(5, 10))
        
        btn_row = ctk.CTkFrame(logs_card, fg_color="transparent")
        btn_row.pack(fill="x", padx=15, pady=(0, 15))
        self.btn_exit = ctk.CTkButton(btn_row, text="Exit Application", width=120, command=self.quit, fg_color="#334155", hover_color="#475569")
        self.btn_exit.pack(side="right")

    def toggle_engine_ui(self):
        for widget in self.dynamic_frame.winfo_children(): widget.destroy()
        engine = self.engine_var.get()
        
        if "Sarvam" in engine:
            # 1. API Key Row
            row_key = ctk.CTkFrame(self.dynamic_frame, fg_color="transparent")
            row_key.pack(fill="x", pady=4)
            ctk.CTkLabel(row_key, text="API Key:", width=80, anchor="w").pack(side="left")
            self.entry_key = ctk.CTkEntry(row_key, textvariable=self.key_var, show="*", height=30)
            self.entry_key.pack(side="left", fill="x", expand=True)
            
            # 2. Plan Row
            row_plan = ctk.CTkFrame(self.dynamic_frame, fg_color="transparent")
            row_plan.pack(fill="x", pady=4)
            ctk.CTkLabel(row_plan, text="API Plan:", width=80, anchor="w").pack(side="left")
            self.plan_combo = ctk.CTkOptionMenu(row_plan, variable=self.sarvam_plan_var, 
                                                values=["Starter (60 RPM)", "Pro (200 RPM)", "Business (1000 RPM)", "Custom Limit"], height=30)
            self.plan_combo.pack(side="left", fill="x", expand=True)
            
            # 3. Custom RPM Row
            self.row_custom = ctk.CTkFrame(self.dynamic_frame, fg_color="transparent")
            ctk.CTkLabel(self.row_custom, text="Custom RPM:", width=80, anchor="w").pack(side="left")
            self.entry_custom = ctk.CTkEntry(self.row_custom, textvariable=self.sarvam_custom_rpm_var, height=30)
            self.entry_custom.pack(side="left", fill="x", expand=True)
            
            self.update_custom_rpm_visibility()
            
            # 4. Enable Chunking Checkbox
            self.chk_chunk = ctk.CTkCheckBox(self.dynamic_frame, text="Enable Chunking (REST requires <30s)", variable=self.enable_chunking_var)
            self.chk_chunk.pack(anchor="w", pady=8)
            
            # 5. Chunking Settings Frame (contains length, silence chk, and radio buttons)
            self.chunking_settings_frame = ctk.CTkFrame(self.dynamic_frame, fg_color="transparent")
            
            row_len = ctk.CTkFrame(self.chunking_settings_frame, fg_color="transparent")
            row_len.pack(fill="x", pady=4)
            ctk.CTkLabel(row_len, text="Length (sec):", width=80, anchor="w").pack(side="left")
            self.entry_len = ctk.CTkEntry(row_len, textvariable=self.chunk_len_var, width=80, height=30)
            self.entry_len.pack(side="left")
            
            self.chk_silence = ctk.CTkCheckBox(self.chunking_settings_frame, text="Align cuts with nearest silence (recommended)", variable=self.smart_silence_var)
            self.chk_silence.pack(anchor="w", pady=6)
            
            self.radio_smart = ctk.CTkRadioButton(self.chunking_settings_frame, text="Smart adjust chunk length (No Waiting)", variable=self.chunking_mode_var, value="smart")
            self.radio_smart.pack(anchor="w", pady=4)
            self.radio_throttle = ctk.CTkRadioButton(self.chunking_settings_frame, text="Maintain fixed length and wait/throttle", variable=self.chunking_mode_var, value="throttle")
            self.radio_throttle.pack(anchor="w", pady=4)
            
            self.update_chunking_controls_visibility()
            
        else:
            # Whisper Engine Settings
            row_model = ctk.CTkFrame(self.dynamic_frame, fg_color="transparent")
            row_model.pack(fill="x", pady=4)
            ctk.CTkLabel(row_model, text="Model:", width=80, anchor="w").pack(side="left")
            self.model_combo = ctk.CTkOptionMenu(row_model, variable=self.model_var, values=WHISPER_MODELS, height=30)
            self.model_combo.pack(side="left", fill="x", expand=True)
            
            # Hardware and Status info
            self.lbl_hw = ctk.CTkLabel(self.dynamic_frame, text="Hardware: CPU", font=("Segoe UI", 9, "italic"), text_color="#94a3b8", anchor="w")
            self.lbl_hw.pack(fill="x", pady=2)
            
            row_status = ctk.CTkFrame(self.dynamic_frame, fg_color="transparent")
            row_status.pack(fill="x", pady=2)
            ctk.CTkLabel(row_status, text="Status:", font=("Segoe UI", 10, "bold")).pack(side="left")
            self.model_status_label = ctk.CTkLabel(row_status, text="Checking...", text_color="#38bdf8", font=("Segoe UI", 10, "bold"))
            self.model_status_label.pack(side="left", padx=5)
            
            hw = detect_hardware_acceleration()
            hw_text = f"Hardware: {hw['recommended'].upper()}"
            if hw['cuda_available'] and hw['devices']:
                hw_text += f" ({hw['devices'][0]})"
            self.lbl_hw.configure(text=hw_text)
            self.update_whisper_status_label()
            
            # Check & Download button
            self.download_btn = ctk.CTkButton(self.dynamic_frame, text="Check & Download Model", command=self.check_download_model, fg_color="#334155", hover_color="#475569", height=32)
            self.download_btn.pack(fill="x", pady=8)
            
            # Enable Chunking Checkbox
            self.chk_chunk = ctk.CTkCheckBox(self.dynamic_frame, text="Enable Chunking (Not recommended)", variable=self.enable_chunking_var)
            self.chk_chunk.pack(anchor="w", pady=8)
            
            # Chunking Settings Frame
            self.chunking_settings_frame = ctk.CTkFrame(self.dynamic_frame, fg_color="transparent")
            
            row_len = ctk.CTkFrame(self.chunking_settings_frame, fg_color="transparent")
            row_len.pack(fill="x", pady=4)
            ctk.CTkLabel(row_len, text="Length (sec):", width=80, anchor="w").pack(side="left")
            self.entry_len = ctk.CTkEntry(row_len, textvariable=self.chunk_len_var, width=80, height=30)
            self.entry_len.pack(side="left")
            
            self.chk_silence = ctk.CTkCheckBox(self.chunking_settings_frame, text="Align cuts with nearest silence (recommended)", variable=self.smart_silence_var)
            self.chk_silence.pack(anchor="w", pady=6)
            
            self.update_chunking_controls_visibility()

    def handle_engine_change(self):
        engine = self.engine_var.get()
        if "Sarvam" in engine:
            self.enable_chunking_var.set(True)
        else:
            self.enable_chunking_var.set(False)
        self.toggle_engine_ui()

    def update_custom_rpm_visibility(self):
        try:
            if self.sarvam_plan_var.get() == "Custom Limit":
                self.row_custom.pack(fill="x", pady=2)
            else:
                self.row_custom.pack_forget()
        except: pass

    def update_chunking_controls_visibility(self):
        try:
            if self.enable_chunking_var.get():
                self.chunking_settings_frame.pack(fill="x", pady=2)
            else:
                self.chunking_settings_frame.pack_forget()
        except: pass

    def update_whisper_status_label(self):
        try:
            model_name = self.model_var.get()
            cached = check_whisper_model_cached(model_name)
            if cached:
                self.model_status_label.configure(text="Cached (Ready)", text_color="#10b981")
            else:
                self.model_status_label.configure(text="Needs Download", text_color="#ef4444")
        except:
            try: self.model_status_label.configure(text="Unknown", text_color="#cbd5e1")
            except: pass

    def check_download_model(self):
        self.download_btn.configure(state="disabled")
        self.model_status_label.configure(text="Checking...", text_color="#38bdf8")
        threading.Thread(target=self._check_download_worker, daemon=True).start()
        
    def _check_download_worker(self):
        model_name = self.model_var.get()
        try:
            self.write_log(f"Checking/Downloading Whisper '{model_name}' model...")
            self.after(0, lambda: self.model_status_label.configure(text="Downloading...", text_color="#38bdf8"))
            
            import whisper
            hw = detect_hardware_acceleration()
            device = hw["recommended"]
            
            whisper.load_model(model_name, device=device)
            
            self.write_log(f"Whisper '{model_name}' model is loaded and ready on {device.upper()}.")
            self.after(0, lambda: self.model_status_label.configure(text="Cached (Ready)", text_color="#10b981"))
        except Exception as e:
            self.write_log(f"Error checking/downloading model: {str(e)}")
            self.after(0, lambda: self.model_status_label.configure(text="Failed to load", text_color="#ef4444"))
        finally:
            self.after(0, lambda: self.download_btn.configure(state="normal"))

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
                    self.smart_silence_var.set(cfg.get("smart_silence", True))
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
                "enable_chunking": self.enable_chunking_var.get(),
                "smart_silence": self.smart_silence_var.get()
            }
            key = self.key_var.get().strip()
            if key: cfg["key_enc"] = base64.b64encode(key.encode()).decode()
            with open(CONFIG_FILE, "w") as f: json.dump(cfg, f)
        except: pass

    def write_log(self, msg): self.log_queue.put(msg)
    def process_logs(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.log_text.insert("end", f"> {msg}\n")
                self.log_text.see("end")
        except queue.Empty: pass
        self.after(100, self.process_logs)

    def browse_file(self):
        p = filedialog.askopenfilename(filetypes=[("Media", "*.mp4 *.mkv *.mov *.avi *.mp3 *.wav *.m4a *.flac"), ("All", "*.*")])
        if p:
            self.path_var.set(p)
            size_mb = os.path.getsize(p) / (1024 * 1024)
            self.file_info_var.set(f"{os.path.basename(p)} ({size_mb:.2f} MB)")
            self.write_log(f"Loaded: {os.path.basename(p)}")

    def on_file_drop(self, event):
        data = event.data.strip()
        # Clean Tcl curly braces or double quotes from path
        if data.startswith('{') and data.endswith('}'):
            data = data[1:-1]
        elif data.startswith('"') and data.endswith('"'):
            data = data[1:-1]
            
        if os.path.isfile(data):
            self.path_var.set(data)
            size_mb = os.path.getsize(data) / (1024 * 1024)
            self.file_info_var.set(f"{os.path.basename(data)} ({size_mb:.2f} MB)")
            self.write_log(f"Dropped: {os.path.basename(data)}")
        else:
            messagebox.showerror("Error", "Dropped item is not a valid file.")

    def start_task(self):
        self.save_settings()
        f = self.path_var.get().strip()
        if not f or not os.path.isfile(f): messagebox.showerror("Error", "Select a valid file."); return
        self.start_btn.configure(state="disabled")
        self.progress.pack(fill="x", padx=15, pady=(10, 0))
        self.progress.set(0.0)
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
            
            # Setup chunk length and slicing method
            if enable_chunking:
                chunk_len_ms = int(chunk_len_sec * 1000)
                if "Sarvam" in engine:
                    if self.chunking_mode_var.get() == "smart":
                        smart_len = total_duration_sec / rpm_limit
                        chunk_len_sec = min(30.0, max(5.0, smart_len))
                        chunk_len_ms = int(chunk_len_sec * 1000)
                        self.write_log(f"Smart chunk length calculated: {chunk_len_sec:.2f}s (based on {total_duration_sec:.1f}s file duration and {rpm_limit} RPM)")
                    else:
                        chunk_len_sec = min(30.0, max(1.0, chunk_len_sec))
                        chunk_len_ms = int(chunk_len_sec * 1000)
                
                # Check for smart silence cut alignment
                if self.smart_silence_var.get():
                    dBFS = audio.dBFS
                    dynamic_thresh = min(-30, max(-50, dBFS - 12))
                    self.write_log(f"Aligning cuts to nearest silence (Threshold: {dynamic_thresh:.1f} dBFS, Audio average: {dBFS:.1f} dBFS)...")
                    chunks = split_audio_smart(audio, chunk_len_ms, silence_thresh=dynamic_thresh)
                else:
                    self.write_log("Using strict fixed-time interval chunking...")
                    chunks = split_audio_fixed(audio, chunk_len_ms)
            else:
                chunks = [{"audio": audio, "start_sec": 0.0, "duration_sec": total_duration_sec}]
                
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
            
            for idx, item in enumerate(chunks):
                chunk = item["audio"]
                chunk_start_sec = item["start_sec"]
                chunk_duration_sec = item["duration_sec"]
                
                self.after(0, lambda p=((idx+1)/total_chunks): self.progress.set(p))
                
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
                            segments = data.get("segments", [{"text": data.get("transcript", ""), "start_time_seconds": 0, "end_time_seconds": chunk_duration_sec}])
                            transcribed = True
                        elif is_quota_error:
                            self.write_log("API rate limit or quota exceeded!")
                            event = threading.Event()
                            result_dict = {"fallback": False}
                            self.after(0, lambda: self.ask_fallback(event, result_dict))
                            event.wait() # Block worker until choice is made
                            
                            if result_dict["fallback"]:
                                self.write_log("User selected fallback to Whisper (Local). Switching...")
                                engine = "Whisper (Local)"
                                self.after(0, lambda: self.engine_var.set("Whisper (Local)"))
                                
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
            self.after(0, lambda: self.status_label.configure(text="COMPLETED", text_color="#10b981"))
        except Exception as e:
            self.write_log(f"FATAL: {str(e)}")
            self.after(0, lambda: self.status_label.configure(text="FAILED", text_color="#ef4444"))
        finally:
            if os.path.exists(temp_audio): os.remove(temp_audio)
            self.after(0, self.progress.pack_forget)
            self.after(0, lambda: self.start_btn.configure(state="normal"))

def main():
    app = STCGui()
    app.mainloop()

if __name__ == "__main__":
    main()
