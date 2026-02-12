#!/usr/bin/env python3
"""Inspect a requirements.txt and emit container/accelerator hints.

Usage:
  python scripts/inspect_requirements.py requirements.txt
"""
import re
import sys
from pathlib import Path

GPU_MARKERS = {"bitsandbytes", "xformers", "flash-attn", "deepspeed"}
TRN_MARKERS = {"torch-neuronx", "neuronx-distributed", "optimum-neuron", "neuronx-cc"}

def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/inspect_requirements.py path/to/requirements.txt", file=sys.stderr)
        sys.exit(2)

    req_path = Path(sys.argv[1])
    text = req_path.read_text(encoding="utf-8", errors="ignore").lower()

    pkgs = set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        pkg = re.split(r"[<=>\[]", line, maxsplit=1)[0].strip()
        if pkg:
            pkgs.add(pkg)

    gpu_hits = sorted(pkgs.intersection(GPU_MARKERS))
    trn_hits = sorted(pkgs.intersection(TRN_MARKERS))

    print("Detected packages:", ", ".join(sorted(pkgs))[:500] + ("..." if len(", ".join(sorted(pkgs))) > 500 else ""))
    print()

    if trn_hits and gpu_hits:
        print("⚠️ Mixed signals: both GPU-leaning and Trainium/Neuron packages found.")
    if trn_hits:
        print("Trainium/Neuron indicators:", ", ".join(trn_hits))
        print("Suggestion: consider Trainium containers/tooling, but verify architecture support in Neuron docs.")
    if gpu_hits:
        print("GPU/CUDA indicators:", ", ".join(gpu_hits))
        print("Suggestion: use GPU PyTorch training DLC; Trainium is unlikely to work with these deps.")
    if not trn_hits and not gpu_hits:
        print("No strong GPU/Trainium indicators found. Likely generic PyTorch/Transformers.")
        print("Suggestion: start from a recent GPU PyTorch training DLC unless user explicitly wants Trainium.")

if __name__ == "__main__":
    main()
