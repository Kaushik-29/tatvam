"""
Local speech-to-text for typed-free questions (faster-whisper, Whisper "base", CPU, int8).

Privacy: audio is decoded and transcribed on this machine and is never stored or sent anywhere.
Audio is decoded with the ffmpeg command-line tool into 16 kHz mono samples. faster-whisper's own
decoder (PyAV) is not used: on machines where Windows Application Control blocks PyAV's DLL, a stub
module stands in for it, because faster-whisper only calls PyAV when it is given a file, never for
the numpy arrays passed here.
"""
import os
import shutil
import subprocess
import sys
import threading
import time
import types
from typing import Any, Dict, Optional

import numpy as np

from backend import config

MODEL_NAME = os.environ.get("MEDRESOLVE_WHISPER_MODEL", "base")
MODEL_DIR = config.MODELS_DIR / "whisper"
MAX_SECONDS = 60
SAMPLE_RATE = 16000
_model = None
_lock = threading.Lock()


class SpeechUnavailable(RuntimeError):
    pass


def _ffmpeg() -> str:
    exe = os.environ.get("FFMPEG_PATH") or shutil.which("ffmpeg")
    if not exe and os.environ.get("LOCALAPPDATA"):          # WinGet installs are not always on a service's PATH
        import glob
        hits = glob.glob(os.path.join(os.environ["LOCALAPPDATA"], "Microsoft", "WinGet", "Packages", "*FFmpeg*",
                                      "**", "bin", "ffmpeg.exe"), recursive=True)
        exe = hits[0] if hits else None
    if not exe:
        raise SpeechUnavailable("ffmpeg was not found; install it or set FFMPEG_PATH")
    return exe


def _whisper_model():
    global _model
    with _lock:
        if _model is None:
            try:
                import av  # noqa: F401
            except Exception:          # blocked or missing: faster-whisper never calls it for numpy input
                sys.modules["av"] = types.ModuleType("av")
            try:
                from faster_whisper import WhisperModel
            except Exception as e:
                raise SpeechUnavailable(f"faster-whisper is not available: {e}") from e
            MODEL_DIR.mkdir(parents=True, exist_ok=True)
            _model = WhisperModel(MODEL_NAME, device="cpu", compute_type="int8", download_root=str(MODEL_DIR))
        return _model


def decode(audio: bytes) -> np.ndarray:
    """Any browser recording (webm/ogg/wav/mp4) -> 16 kHz mono float32 samples, via ffmpeg."""
    p = subprocess.run([_ffmpeg(), "-nostdin", "-loglevel", "error", "-i", "pipe:0", "-t", str(MAX_SECONDS),
                        "-f", "s16le", "-ac", "1", "-ar", str(SAMPLE_RATE), "pipe:1"],
                       input=audio, capture_output=True, timeout=60)
    if p.returncode != 0 or not p.stdout:
        raise ValueError("Could not read the recording")
    return np.frombuffer(p.stdout, np.int16).astype(np.float32) / 32768.0


def transcribe(audio: bytes, language: Optional[str] = None) -> Dict[str, Any]:
    t0 = time.time()
    samples = decode(audio)
    if len(samples) < SAMPLE_RATE * 0.3:
        return {"text": "", "language": None, "seconds": round(time.time() - t0, 2)}
    segments, info = _whisper_model().transcribe(samples, language=language, beam_size=3, vad_filter=False,
                                                 condition_on_previous_text=False)
    text = " ".join(s.text.strip() for s in segments).strip()
    return {"text": text, "language": info.language, "seconds": round(time.time() - t0, 2),
            "audio_seconds": round(len(samples) / SAMPLE_RATE, 1), "model": f"whisper-{MODEL_NAME} (local)"}
