from setuptools import setup

setup(
    name="sarvam-timed-captions",
    version="1.0.0",
    package_dir={"": "SRC"},
    py_modules=["STC"],
    install_requires=[
        "numpy<2.0",
        "openai-whisper",
        "pydub",
        "pysrt",
        "requests",
        "customtkinter",
        "tkinterdnd2",
    ],
    entry_points={
        "console_scripts": [
            "stc=STC:main",
        ],
    },
    author="Bishnu Mahali",
    description="Professional Transcription Toolkit (Powered by Sarvam AI)",
    license="MIT",
    url="https://github.com/bishnumahali/Sarvam-Timed-Captions",
)
