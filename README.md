# Sarvam Timed Captions (STC)

A professional desktop transcription studio designed to generate highly accurate timed captions (.srt) from video and audio files. Powered by the **Sarvam AI Cloud API** for state-of-the-art Indic language transcription, with **OpenAI Whisper** as a free local fallback. Built on a modern, high-contrast CustomTkinter interface with drag-and-drop support.

## 🌟 Key Features

- **Modern Slate & Indigo Dashboard**: Overhauled interface built with native CustomTkinter widgets, offering clean typography, responsive layouts, and interactive focus highlighting.
- **Drag & Drop Integration**: Easily load media files by dragging and dropping them anywhere on the application window or into the designated drop zone.
- **API Request Limit Controls**: Configurable plan presets (Starter: 60 RPM, Pro: 200 RPM, Business: 1000 RPM, or Custom Limit) with a sliding-window rate limiter to prevent 429 throttling errors.
- **Waveform Silence Alignment (VAD)**: Intelligently aligns segment cuts with silent gaps between words using pydub's silence detector, ensuring speech is never sliced mid-word.
- **Dynamic Local AI Fallback**: Thread-safe error listener automatically detects cloud quota exhaustion or rate limits, prompting the user to transition to local Whisper model transcription on the fly.
- **Local Model Manager**: Detects PyTorch CUDA hardware acceleration and cached model weights, with a background pre-download utility.
- **Flexible Chunking Modes**:
  - **Smart Mode**: Automatically computes optimal chunk sizes to finish the transcription in one go.
  - **Throttle Mode**: Respects strict rate limits by auto-sleeping between request windows.
  - **No Chunking**: Slices are disabled entirely, allowing Whisper to process full-length audio tracks.

---

## 🚀 Getting Started

### 1. Prerequisite: API Key
To use the high-accuracy cloud engine, you need an API key:
- Sign up at the [Sarvam AI Dashboard](https://dashboard.sarvam.ai/).
- Copy your **API Subscription Key**.

### 2. Installation (Windows)
1. **Install Python**: [Download here](https://www.python.org/) (Ensure you check **"Add Python to PATH"**).
2. **Install FFmpeg**: [Download here](https://ffmpeg.org/download.html) and add it to your PATH.
3. **Download this repo**: Clone or download the ZIP to your computer.

### 3. Launch
Double-click **`Start STC.bat`**.
- The first run will automatically set up your environment (Python Virtual Environment).
- If you plan to use **Whisper (Local)** mode, say `y` when asked about an **NVIDIA GPU** to install PyTorch with CUDA acceleration.

---

## 🔒 Security & Privacy

**IMPORTANT: Make your repository PRIVATE.**
STC saves your API key locally in an encoded format (`CONFIG/.stc_config.json`) for convenience. To prevent your key from being exposed:

1. Go to your repository settings on GitHub/GitLab.
2. Under "Danger Zone", click **Change visibility**.
3. Select **Make private**.

---

## 📺 How to Use

1. **Drop File**: Drag and drop your video or audio file onto the dashboard, or click **Browse...**.
2. **Select Engine**: Choose **Sarvam AI (Cloud)** or **Whisper (Local)**.
3. **Settings**: Enter your **API Key** (for Sarvam) and select target **Language** (e.g. Bengali).
4. **Silence Cut & Limit Settings**: Configure chunk lengths and toggle **Align cuts with nearest silence** (recommended).
5. **Start**: Click **START TASK**. Your `.srt` file will be generated in the same directory as the media file.

---

## License
MIT License - Copyright (c) 2026 Bishnu Mahali

---

# 🔴 STRICT ENGINEERING MANDATES

## 1. PROJECT INTEGRITY FIRST
- **NEVER** remove, simplify, or alter core features, technical logic, or advanced functions unless explicitly instructed by the user.
- All existing functionality must be preserved with 100% fidelity.

## 2. GUI & STYLING PROTOCOLS
- When working on GUI/Design, treat the underlying engine code as **READ-ONLY** unless changes are strictly required for UI data-binding.
- All UI elements must strictly follow system-aware Light/Dark mode themes.

## 3. ARCHITECTURAL PRESERVATION
- Respect the advanced nature of the tools (VMAF, hardware acceleration, multi-pass logic). 

---

## 🤝 Support & Connect

These projects are simple utility scripts built to solve everyday problems. If you find them helpful in your workflow and would like to support me, any small contribution is deeply appreciated! ❤️

<p align="center">
  <a href="https://buymeacoffee.com/Bishnu"><img src="https://img.shields.io/badge/Buy_Me_A_Coffee-FFDD00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black" alt="Buy Me A Coffee"></a>
  <a href="https://ko-fi.com/Bishnu"><img src="https://img.shields.io/badge/Ko--fi-F16061?style=for-the-badge&logo=ko-fi&logoColor=white" alt="Ko-fi"></a>
  <a href="https://patreon.com/Bishnu"><img src="https://img.shields.io/badge/Patreon-F96854?style=for-the-badge&logo=patreon&logoColor=white" alt="Patreon"></a>
  <a href="https://paypal.me/beingaash"><img src="https://img.shields.io/badge/PayPal-00457C?style=for-the-badge&logo=paypal&logoColor=white" alt="PayPal"></a>
</p>

<p align="center">
  <a href="https://github.com/BishnuMahali"><img src="https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=github&logoColor=white" alt="GitHub"></a>
  <a href="https://bmahali.com"><img src="https://img.shields.io/badge/Website-333333?style=for-the-badge&logo=firefox&logoColor=white" alt="Website"></a>
  <a href="https://youtube.com/@BishnuMahaliPro"><img src="https://img.shields.io/badge/YouTube-FF0000?style=for-the-badge&logo=youtube&logoColor=white" alt="YouTube"></a>
  <a href="https://instagram.com/itsBishnuMahali"><img src="https://img.shields.io/badge/Instagram-E4405F?style=for-the-badge&logo=instagram&logoColor=white" alt="Instagram"></a>
  <a href="https://facebook.com/itsBishnuMahali"><img src="https://img.shields.io/badge/Facebook-1877F2?style=for-the-badge&logo=facebook&logoColor=white" alt="Facebook"></a>
  <a href="https://x.com/itsBishnuMahli"><img src="https://img.shields.io/badge/X-000000?style=for-the-badge&logo=x&logoColor=white" alt="X (Twitter)"></a>
  <a href="https://linkedin.com/in/bishnumahali"><img src="https://img.shields.io/badge/LinkedIn-0A66C2?style=for-the-badge&logo=linkedin&logoColor=white" alt="LinkedIn"></a>
</p>
