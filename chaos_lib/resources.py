"""
Decide how many analysis workers this machine can run at once.

Each analysis worker is a separate process holding its own EasyOCR reader and
Whisper model. On an NVIDIA GPU the limit is VRAM: we add up what one worker's
models cost, divide the free VRAM (minus headroom) by that, and cap by CPU
cores since every worker also decodes video on the CPU. Without CUDA, workers
run on the CPU and the limit is physical cores and free RAM.

Costs are expressed as functions of model size, calibrated from measurements
on one machine (RTX 3070 8 GB, Windows 11, torch 2.5 + cu121): the drop in free
VRAM / growth in RSS after loading each model and running real inference.
These are properties of the models and libraries, not of that machine, so the
same numbers apply anywhere; only the free VRAM / RAM / cores they're divided
into are read from the user's machine at run time.

    measured                      VRAM      RAM (CPU mode)
    CUDA context (per process)    160 MB    -
    EasyOCR (killfeed crops)      155 MB    ~560 MB (+ ~460 MB torch/cv2 imports)
    Whisper base  (74M params)    365 MB    small
    Whisper small (244M params)   1500 MB   -

    PANNs Cnn14_16k laughter      690 MB    ~450 MB (est.)

The laughter tagger is loaded only with voice-chat moments on; with subtitles
on, each worker also holds a second Whisper for re-transcribing clip windows.
"""

import os
import shutil
import subprocess
from dataclasses import dataclass

_MB = 1
_GB = 1024 * _MB

# Whisper parameter counts (millions), from the openai/whisper model card.
WHISPER_PARAMS_M = {'tiny': 39, 'base': 74, 'small': 244, 'medium': 769, 'turbo': 809, 'large': 1550}

CUDA_CONTEXT_VRAM_MB = 160     # per-process CUDA context + caching allocator
EASYOCR_VRAM_MB = 160          # CRAFT + recognizer working on killfeed-row-sized crops
WORKER_RAM_MB = 1100           # torch + cv2 + EasyOCR resident set, before Whisper
GPU_WORKER_EXTRA_RAM_MB = 500  # host-side CUDA/cuDNN libraries per GPU process (est.)
LAUGHTER_VRAM_MB = 690         # Cnn14_16k: 311 MB fp32 weights + batch-of-8 activations, measured
LAUGHTER_RAM_MB = 450          # same model on the CPU (est.)

SAFETY_FACTOR = 1.25           # fragmentation, driver overhead, longer audio than we measured on
VRAM_HEADROOM_MB = 1 * _GB     # left free for the desktop compositor, OBS, the browser…
RAM_HEADROOM_MB = 2 * _GB


def whisper_vram_mb(params_m: float) -> float:
    """Whisper weights + inference working set on CUDA. Linear fit through the
    measured base (74M → 365 MB) and small (244M → 1500 MB): ~6.65 MB per
    million params, floored at the bare fp16 weights for very small models."""
    return max(2 * params_m, 6.65 * params_m - 122)


def whisper_ram_mb(params_m: float) -> float:
    """Whisper on CPU holds fp32 weights: 4 bytes per parameter."""
    return 4 * params_m


def _whisper_params_m(name: str) -> int:
    name = name.lower().removesuffix('.en')
    if 'turbo' in name:
        return WHISPER_PARAMS_M['turbo']
    if name.startswith('large'):
        return WHISPER_PARAMS_M['large']
    return WHISPER_PARAMS_M.get(name, WHISPER_PARAMS_M['large'])  # unknown → assume the worst


def cuda_available() -> bool:
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


def query_gpu() -> tuple[str, int, int] | None:
    """(name, total_mb, free_mb) for GPU 0, read via nvidia-smi so the calling
    process never creates a CUDA context of its own (that alone would eat
    ~160 MB of VRAM in the GUI process for its whole lifetime)."""
    smi = shutil.which('nvidia-smi')
    if smi:
        try:
            out = subprocess.run(
                [smi, '--query-gpu=name,memory.total,memory.free', '--format=csv,noheader,nounits'],
                capture_output=True, text=True, timeout=10,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
            ).stdout.strip().splitlines()
            if out:
                name, total, free = [s.strip() for s in out[0].split(',')]
                return name, int(total), int(free)
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
    try:
        import torch
        free, total = torch.cuda.mem_get_info(0)
        return torch.cuda.get_device_name(0), total // 2**20, free // 2**20
    except Exception:
        return None


def _physical_cores() -> int:
    try:
        import psutil
        return psutil.cpu_count(logical=False) or os.cpu_count() or 1
    except ImportError:
        return max(1, (os.cpu_count() or 2) // 2)


def _available_ram_mb() -> int | None:
    try:
        import psutil
        return psutil.virtual_memory().available // 2**20
    except ImportError:
        return None


@dataclass
class WorkerPlan:
    device: str          # 'cuda' or 'cpu'
    max_workers: int     # most workers this machine can hold right now
    workers: int         # what to start with (requested, clamped to max_workers)
    torch_threads: int   # intra-op threads per worker so workers don't oversubscribe the CPU
    summary: str         # one line for the log explaining the numbers


def plan_analysis_workers(config: dict, requested=None, n_videos: int | None = None) -> WorkerPlan:
    """Size the analysis pool from the models in config and this machine's free memory.

    `requested` is the user's worker count; None, 0 or "auto" means "as many as fit".
    """
    from chaos_lib import moments, subtitles
    whisper_name = config.get('whisper_model', 'base')
    params_m = _whisper_params_m(whisper_name)
    # Optional models every worker loads alongside OCR + Whisper
    extra_vram = extra_ram = 0.0
    extras = []
    if moments.enabled(config):
        extra_vram += LAUGHTER_VRAM_MB
        extra_ram += LAUGHTER_RAM_MB
        extras.append('laughter')
    caption_model = subtitles.caption_model_name(config)
    if caption_model:
        extra_vram += whisper_vram_mb(_whisper_params_m(caption_model))
        extra_ram += whisper_ram_mb(_whisper_params_m(caption_model))
        extras.append(f'subtitle whisper {caption_model}')
    extras_note = ''.join(f' + {e}' for e in extras)
    cores = _physical_cores()
    logical = os.cpu_count() or cores
    ram_free = _available_ram_mb()
    gpu = query_gpu() if cuda_available() else None
    per_worker_vram = int((CUDA_CONTEXT_VRAM_MB + EASYOCR_VRAM_MB + whisper_vram_mb(params_m) + extra_vram)
                          * SAFETY_FACTOR)
    by_vram = (gpu[2] - VRAM_HEADROOM_MB) // per_worker_vram if gpu else 0

    if gpu and by_vram >= 1:
        name, total_mb, free_mb = gpu
        # Weights load on the host first, so GPU workers still need their RAM briefly
        per_worker_ram = int(WORKER_RAM_MB + GPU_WORKER_EXTRA_RAM_MB + whisper_ram_mb(params_m))
        # Each GPU worker still decodes video and runs ffmpeg on the CPU; past
        # about one worker per two physical cores they just queue on the GPU.
        by_cpu = max(1, cores // 2)
        limits = {'VRAM': by_vram, 'CPU': by_cpu}
        device = 'cuda'
        detail = (f"{name}: {free_mb / _GB:.1f} of {total_mb / _GB:.1f} GB free, "
                  f"~{per_worker_vram / _GB:.2f} GB per worker (whisper {whisper_name} + EasyOCR{extras_note} + CUDA context)")
    else:
        per_worker_ram = int(WORKER_RAM_MB + whisper_ram_mb(params_m) + extra_ram)
        limits = {'CPU': cores}
        device = 'cpu'
        if gpu:
            # Not even one worker fits (big model, or a game is holding the
            # VRAM): run on the CPU rather than crash out of memory.
            detail = (f"{gpu[0]} has {gpu[2] / _GB:.1f} GB free but a worker needs ~{per_worker_vram / _GB:.1f} GB, "
                      f"so using the CPU ({cores} physical cores)")
        else:
            detail = f"no CUDA GPU, {cores} physical cores"

    if ram_free is not None:
        limits['RAM'] = (ram_free - RAM_HEADROOM_MB) // per_worker_ram
        detail += f", {ram_free / _GB:.1f} GB RAM free (~{per_worker_ram / _GB:.1f} GB per worker)"

    binding = min(limits, key=limits.get)
    max_workers = max(1, int(limits[binding]))
    if n_videos:
        max_workers = min(max_workers, n_videos)

    if requested in (None, 0, 'auto', 'Auto', 'AUTO'):
        workers = max_workers
    else:
        workers = max(1, min(int(requested), max_workers))

    # Split the CPU between workers. On GPU torch barely uses CPU threads, so
    # one each is plenty; on CPU each worker gets an equal share of the cores.
    torch_threads = 1 if device == 'cuda' else max(1, logical // workers)

    if limits[binding] < 1:
        detail += f". WARNING: not enough free {binding} for even one worker; running 1 anyway"
    summary = (f"{device.upper()}: {workers} analysis worker{'s' if workers != 1 else ''} "
               f"(max {max_workers}, limited by {binding}). {detail}")
    return WorkerPlan(device, max_workers, workers, torch_threads, summary)
