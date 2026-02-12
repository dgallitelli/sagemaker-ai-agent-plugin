#!/usr/bin/env python3
"""Fetch current SageMaker ML instance availability and provide sizing recommendations.

Usage:
    python scripts/fetch_instance_info.py --model-size 8 --technique qlora --context-len 8192

Provides instance recommendations based on the decision tree in instance-sizing.md.
"""
import argparse
import json

# Instance specifications with current GPU/accelerator hardware
INSTANCE_SPECS = {
    # GPU instances - NVIDIA A10G (24GB each)
    "ml.g5.xlarge":    {"gpus": 1, "gpu_mem_gb": 24,  "vcpus": 4,   "mem_gb": 16,   "gpu_type": "A10G"},
    "ml.g5.2xlarge":   {"gpus": 1, "gpu_mem_gb": 24,  "vcpus": 8,   "mem_gb": 32,   "gpu_type": "A10G"},
    "ml.g5.4xlarge":   {"gpus": 1, "gpu_mem_gb": 24,  "vcpus": 16,  "mem_gb": 64,   "gpu_type": "A10G"},
    "ml.g5.8xlarge":   {"gpus": 1, "gpu_mem_gb": 24,  "vcpus": 32,  "mem_gb": 128,  "gpu_type": "A10G"},
    "ml.g5.12xlarge":  {"gpus": 4, "gpu_mem_gb": 96,  "vcpus": 48,  "mem_gb": 192,  "gpu_type": "A10G"},
    "ml.g5.16xlarge":  {"gpus": 1, "gpu_mem_gb": 24,  "vcpus": 64,  "mem_gb": 256,  "gpu_type": "A10G"},
    "ml.g5.24xlarge":  {"gpus": 4, "gpu_mem_gb": 96,  "vcpus": 96,  "mem_gb": 384,  "gpu_type": "A10G"},
    "ml.g5.48xlarge":  {"gpus": 8, "gpu_mem_gb": 192, "vcpus": 192, "mem_gb": 768,  "gpu_type": "A10G"},

    # GPU instances - NVIDIA L40S (48GB each)
    "ml.g6e.xlarge":   {"gpus": 1, "gpu_mem_gb": 48,  "vcpus": 4,   "mem_gb": 32,   "gpu_type": "L40S"},
    "ml.g6e.2xlarge":  {"gpus": 1, "gpu_mem_gb": 48,  "vcpus": 8,   "mem_gb": 64,   "gpu_type": "L40S"},
    "ml.g6e.4xlarge":  {"gpus": 1, "gpu_mem_gb": 48,  "vcpus": 16,  "mem_gb": 128,  "gpu_type": "L40S"},
    "ml.g6e.8xlarge":  {"gpus": 1, "gpu_mem_gb": 48,  "vcpus": 32,  "mem_gb": 256,  "gpu_type": "L40S"},
    "ml.g6e.12xlarge": {"gpus": 4, "gpu_mem_gb": 192, "vcpus": 48,  "mem_gb": 384,  "gpu_type": "L40S"},
    "ml.g6e.16xlarge": {"gpus": 1, "gpu_mem_gb": 48,  "vcpus": 64,  "mem_gb": 512,  "gpu_type": "L40S"},
    "ml.g6e.24xlarge": {"gpus": 4, "gpu_mem_gb": 192, "vcpus": 96,  "mem_gb": 768,  "gpu_type": "L40S"},
    "ml.g6e.48xlarge": {"gpus": 8, "gpu_mem_gb": 384, "vcpus": 192, "mem_gb": 1536, "gpu_type": "L40S"},

    # GPU instances - NVIDIA A100 (40GB/80GB)
    "ml.p4d.24xlarge": {"gpus": 8, "gpu_mem_gb": 320, "vcpus": 96,  "mem_gb": 1152, "gpu_type": "A100-40GB"},
    "ml.p4de.24xlarge":{"gpus": 8, "gpu_mem_gb": 640, "vcpus": 96,  "mem_gb": 1152, "gpu_type": "A100-80GB"},

    # GPU instances - NVIDIA H100
    "ml.p5.48xlarge":  {"gpus": 8, "gpu_mem_gb": 640, "vcpus": 192, "mem_gb": 2048, "gpu_type": "H100"},
    "ml.p5e.48xlarge": {"gpus": 8, "gpu_mem_gb": 640, "vcpus": 192, "mem_gb": 2048, "gpu_type": "H100"},
    "ml.p5en.48xlarge":{"gpus": 8, "gpu_mem_gb": 640, "vcpus": 192, "mem_gb": 2048, "gpu_type": "H100"},

    # Trainium instances
    "ml.trn1.2xlarge":  {"accelerators": 1,  "accel_mem_gb": 32,   "vcpus": 8,   "mem_gb": 32,   "accel_type": "Trainium"},
    "ml.trn1.32xlarge": {"accelerators": 16, "accel_mem_gb": 512,  "vcpus": 128, "mem_gb": 512,  "accel_type": "Trainium"},
    "ml.trn1n.32xlarge":{"accelerators": 16, "accel_mem_gb": 512,  "vcpus": 128, "mem_gb": 512,  "accel_type": "Trainium"},

    # Trainium2 instances
    "ml.trn2.48xlarge": {"accelerators": 16, "accel_mem_gb": 1536, "vcpus": 192, "mem_gb": 1536, "accel_type": "Trainium2"},
}


def get_trainium_recommendation(model_size_b: float, technique: str) -> dict:
    """Get Trainium instance recommendation.

    Decision Tree for Trainium:
    - < 8B params → ml.trn1.2xlarge (1 chip, 32GB)
    - 8-32B params → ml.trn1.32xlarge (16 chips, 512GB)
    - 32B+ params → ml.trn2.48xlarge (16 chips, 1536GB) or multi-node

    Note: Trainium does NOT support 4-bit quantization (QLoRA).
    """
    technique_normalized = technique.lower().replace("_", "").replace("-", "")

    # QLoRA not supported on Trainium
    if technique_normalized == "qlora":
        return {
            "primary": None,
            "alternatives": [],
            "note": "ERROR: QLoRA (4-bit) is NOT supported on Trainium. Use LoRA or GPU instead.",
            "specs": {},
        }

    if model_size_b < 8:
        primary = "ml.trn1.2xlarge"
        alternatives = ["ml.trn1.32xlarge"]
        note = "Small model - single Trainium chip sufficient for LoRA/SFT"
    elif model_size_b <= 32:
        primary = "ml.trn1.32xlarge"
        alternatives = ["ml.trn1n.32xlarge", "ml.trn2.48xlarge"]
        note = "Medium/large model - 16 Trainium chips for distributed training"
    else:
        primary = "ml.trn2.48xlarge"
        alternatives = ["ml.trn1n.32xlarge"]
        note = "Very large model - Trainium2 recommended; may need multi-node"

    # Adjust for full fine-tuning
    if technique_normalized in ["full", "fullsft", "fullfinetuning"]:
        note += " | Full FT needs more memory - consider larger instance"
        if model_size_b < 8:
            primary = "ml.trn1.32xlarge"
            alternatives = ["ml.trn2.48xlarge"]

    return {
        "primary": primary,
        "alternatives": alternatives,
        "note": note,
        "specs": INSTANCE_SPECS.get(primary, {}),
    }


def get_recommendation_by_decision_tree(model_size_b: float, technique: str) -> dict:
    """Get GPU instance recommendation following the decision tree from instance-sizing.md.

    Decision Tree:
    - < 4B params → ml.g5.2xlarge (PeFT/QLoRA)
    - 4-14B params → ml.g6e.2xlarge (PeFT/Spectrum)
    - 17-32B params → ml.p4de.24xlarge (PeFT/Spectrum)
    - 32-120B params → ml.p5e.48xlarge (PeFT/Full)
    - 600B+ params → ml.p5en.48xlarge (PeFT/Spectrum/Full)
    """
    technique_normalized = technique.lower().replace("_", "").replace("-", "")

    if model_size_b < 4:
        primary = "ml.g5.2xlarge"
        alternatives = ["ml.g5.4xlarge", "ml.g6e.2xlarge"]
        note = "Small model - single A10G sufficient for PeFT"
    elif model_size_b <= 14:
        primary = "ml.g6e.2xlarge"
        alternatives = ["ml.g6e.4xlarge", "ml.g6e.12xlarge"]
        note = "Medium model - L40S (48GB) recommended for PeFT/Spectrum"
    elif model_size_b <= 32:
        primary = "ml.p4de.24xlarge"
        alternatives = ["ml.p5e.48xlarge"]
        note = "Large model - 8x A100-80GB for PeFT/Spectrum"
    elif model_size_b <= 120:
        primary = "ml.p5e.48xlarge"
        alternatives = ["ml.p5en.48xlarge"]
        note = "Very large model - 8x H100 recommended"
    else:  # 600B+
        primary = "ml.p5en.48xlarge"
        alternatives = []
        note = "Massive model - largest available instance"

    # Adjust for full fine-tuning (needs more memory)
    if technique_normalized in ["full", "fullsft", "fullfinetuning"]:
        note += " | Full FT may need larger instance or FSDP"
        if model_size_b <= 14:
            primary = "ml.g6e.12xlarge"  # 4x L40S for full FT
            alternatives = ["ml.p4de.24xlarge"]

    return {
        "primary": primary,
        "alternatives": alternatives,
        "note": note,
        "specs": INSTANCE_SPECS.get(primary, {}),
    }


def estimate_memory_requirements(model_size_b: float, technique: str, context_len: int) -> dict:
    """Estimate GPU memory requirements for training."""
    technique_normalized = technique.lower().replace("_", "").replace("-", "")

    if technique_normalized == "qlora":
        # 4-bit base model + bf16 adapter gradients
        base_gb = model_size_b * 0.5  # ~0.5 bytes/param for 4-bit
        adapter_gb = 0.5  # Small adapter
        activation_gb = (context_len / 1024) * (model_size_b / 10) * 2
        total_gb = base_gb + adapter_gb + activation_gb + 2  # +2GB buffer
        return {"estimated_gb": round(total_gb, 1), "technique": "QLoRA (4-bit)"}

    elif technique_normalized == "lora":
        # bf16 base model (frozen) + bf16 adapter with gradients
        base_gb = model_size_b * 2  # ~2 bytes/param for bf16
        adapter_gb = 1.0
        activation_gb = (context_len / 1024) * (model_size_b / 10) * 3
        total_gb = base_gb + adapter_gb + activation_gb + 2
        return {"estimated_gb": round(total_gb, 1), "technique": "LoRA (bf16)"}

    else:  # full/full_sft
        # Full model + optimizer states + gradients
        base_gb = model_size_b * 2  # bf16 model
        optimizer_gb = model_size_b * 8  # AdamW: 2x fp32 states
        gradient_gb = model_size_b * 2  # bf16 gradients
        activation_gb = (context_len / 1024) * (model_size_b / 10) * 4
        total_gb = base_gb + optimizer_gb + gradient_gb + activation_gb
        return {"estimated_gb": round(total_gb, 1), "technique": "Full Fine-Tuning"}


def main():
    parser = argparse.ArgumentParser(description="SageMaker instance sizing recommendations")
    parser.add_argument("--region", default="us-east-1", help="AWS region (for info only)")
    parser.add_argument("--family", help="Filter by instance family (g5, g6e, p4d, trn1)")
    parser.add_argument("--model-size", type=float, help="Model size in billions (e.g., 8 for 8B)")
    parser.add_argument("--technique", choices=["full", "full_sft", "lora", "qlora", "spectrum"],
                        default="lora", help="Training technique")
    parser.add_argument("--context-len", type=int, default=8192, help="Target context length")
    parser.add_argument("--accelerator", choices=["gpu", "trainium"], default="gpu",
                        help="Accelerator type (gpu or trainium)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    if args.model_size:
        # Get recommendation based on accelerator type
        if args.accelerator == "trainium":
            rec = get_trainium_recommendation(args.model_size, args.technique)
        else:
            rec = get_recommendation_by_decision_tree(args.model_size, args.technique)
        mem = estimate_memory_requirements(args.model_size, args.technique, args.context_len)

        if args.json:
            print(json.dumps({"recommendation": rec, "memory": mem, "accelerator": args.accelerator}, indent=2))
        else:
            print(f"\n{'='*70}")
            print(f"Model: {args.model_size}B parameters")
            print(f"Technique: {mem['technique']}")
            print(f"Context: {args.context_len} tokens")
            print(f"Accelerator: {args.accelerator.upper()}")
            print(f"{'='*70}")

            # Handle error case (e.g., QLoRA on Trainium)
            if rec['primary'] is None:
                print(f"\n✗ {rec['note']}")
            else:
                print(f"\n✓ RECOMMENDED: {rec['primary']}")
                specs = rec['specs']
                if specs:
                    if args.accelerator == "trainium":
                        accel_count = specs.get('accelerators', '?')
                        accel_type = specs.get('accel_type', '?')
                        accel_mem = specs.get('accel_mem_gb', '?')
                        print(f"  Accelerator: {accel_count}x {accel_type}")
                        print(f"  Accelerator Memory: {accel_mem} GB total")
                    else:
                        gpu_count = specs.get('gpus', '?')
                        gpu_type = specs.get('gpu_type', '?')
                        gpu_mem = specs.get('gpu_mem_gb', '?')
                        print(f"  GPU: {gpu_count}x {gpu_type}")
                        print(f"  GPU Memory: {gpu_mem} GB total")
                    print(f"  Estimated need: ~{mem['estimated_gb']} GB")

                if rec['alternatives']:
                    print(f"\n  Alternatives: {', '.join(rec['alternatives'])}")

                print(f"\n  Note: {rec['note']}")

            print(f"\n  Region: {args.region} (verify availability in console)")

    else:
        # List all instances
        instances = INSTANCE_SPECS
        if args.family:
            instances = {k: v for k, v in instances.items() if args.family in k}

        if args.json:
            print(json.dumps(instances, indent=2))
        else:
            print(f"\nSageMaker Training Instance Specs")
            print("=" * 70)
            for inst, specs in sorted(instances.items()):
                gpu_info = f"{specs.get('gpus', specs.get('accelerators', '?'))}x {specs.get('gpu_type', specs.get('accel_type', '?'))}"
                mem_info = f"{specs.get('gpu_mem_gb', specs.get('accel_mem_gb', '?'))} GB"
                print(f"{inst:25} {gpu_info:20} {mem_info}")


if __name__ == "__main__":
    main()
