"""Whisper local con faster-whisper (CTranslate2): precisión de Whisper, sin internet.

GPU NVIDIA: large-v3-turbo en int8_float16 (~1 GB de VRAM, <1 s por frase).
Solo CPU: modelo "small" en int8 (más lento y algo menos preciso).
Variables: WHISPER_MODEL, WHISPER_DEVICE (auto|cuda|cpu), WHISPER_COMPUTE, STT_PROMPT.
"""
import os
import sys
import threading
from pathlib import Path

import numpy as np

MODELS_DIR = Path(__file__).parent / "models" / "whisper"
_model = None
_device = None
_lock = threading.Lock()
_load_error = None


def _register_cuda_dlls():
    """En Windows, las DLL de cuBLAS/cuDNN instaladas por pip no están en el PATH."""
    if sys.platform != "win32":
        return
    try:
        import nvidia
    except ImportError:
        return
    for base in getattr(nvidia, "__path__", []):
        for bin_dir in Path(base).glob("*/bin"):
            os.add_dll_directory(str(bin_dir))
            os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ.get("PATH", "")


def _pick_device():
    wanted = os.getenv("WHISPER_DEVICE", "auto").lower()
    if wanted in ("cuda", "cpu"):
        return wanted
    import ctranslate2
    return "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"


def available() -> bool:
    try:
        import faster_whisper  # noqa: F401
        return _load_error is None
    except ImportError:
        return False


def load():
    """Carga el modelo una sola vez (la primera vez lo descarga a server_pc/models/whisper)."""
    global _model, _device, _load_error
    with _lock:
        if _model is not None:
            return _model
        _register_cuda_dlls()
        from faster_whisper import WhisperModel
        _device = _pick_device()
        name = os.getenv("WHISPER_MODEL", "large-v3-turbo" if _device == "cuda" else "small")
        compute = os.getenv("WHISPER_COMPUTE", "int8_float16" if _device == "cuda" else "int8")
        try:
            _model = WhisperModel(name, device=_device, compute_type=compute, download_root=str(MODELS_DIR))
        except Exception as exc:
            if _device == "cuda":  # Drivers/DLL de CUDA con problemas: seguir en CPU.
                print(f"[Whisper] CUDA falló ({exc}); usando CPU.", flush=True)
                _device = "cpu"
                _model = WhisperModel(os.getenv("WHISPER_MODEL", "small"), device="cpu",
                                      compute_type="int8", download_root=str(MODELS_DIR))
            else:
                _load_error = str(exc)
                raise
        print(f"[Whisper] Modelo {name} listo en {_device}.", flush=True)
        return _model


def preload_in_background():
    def run():
        try:
            load()
        except Exception as exc:
            print(f"[Whisper] No se pudo precargar: {exc}", flush=True)
    if os.getenv("WHISPER_PRELOAD", "1") == "0" or "pytest" in sys.modules:
        return
    if available():
        threading.Thread(target=run, daemon=True, name="whisper-preload").start()


def transcribe(pcm: bytes, rate: int, language: str = "es") -> str:
    audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
    if rate != 16000:
        target = np.linspace(0, len(audio), int(len(audio) * 16000 / rate), endpoint=False)
        audio = np.interp(target, np.arange(len(audio)), audio).astype(np.float32)
    model = load()
    segments, _ = model.transcribe(
        audio,
        language=language.split("-")[0],
        beam_size=5 if _device == "cuda" else 1,
        vad_filter=True,  # Ignora silencios: evita "alucinaciones" de Whisper.
        condition_on_previous_text=False,
        initial_prompt=os.getenv("STT_PROMPT") or None,
    )
    return " ".join(segment.text.strip() for segment in segments).strip()
