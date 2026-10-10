import os
from pathlib import Path

HOME = Path(os.environ.get("ARR_HOME", Path.home() / ".local/share/arr"))
AUDIOCPP = HOME / "audiocpp" / "current" / "audiocpp_cli"  # moteur de YuE2 (Vulkan) ; `current` vise une version
YUE2 = HOME / "yue2"  # poids GGUF de YuE2
SS2_PYTHON = HOME / "envs" / "ss2" / "bin" / "python"  # environnement isolé de SheetSage2


def device() -> str:
    import torch

    return "xpu" if torch.xpu.is_available() else "cpu"


def offline() -> None:
    """Coupe tout accès réseau des bibliothèques de modèles."""
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ.setdefault("SYCL_CACHE_PERSISTENT", "1")
