import os
from pathlib import Path

CHECKPOINTS = Path(os.environ.get("ARR_CHECKPOINTS", Path.home() / ".local/share/arr/checkpoints"))


def device() -> str:
    import torch

    return "xpu" if torch.xpu.is_available() else "cpu"


def offline() -> None:
    """Coupe tout accès réseau des bibliothèques de modèles."""
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["ACESTEP_CHECKPOINTS_DIR"] = str(CHECKPOINTS)
    os.environ.setdefault("SYCL_CACHE_PERSISTENT", "1")
