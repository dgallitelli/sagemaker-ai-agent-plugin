# Instance Sizing Guide

Use this decision tree to quickly select the right instance for your model and technique.

## Quick Decision Tree

```
START HERE
    ↓
Is your model < 4B parameters?
    YES → ml.g5.2xlarge (PeFT/QLoRA)
    NO  → Continue
    ↓
Is your model 4-14B parameters?
    YES → ml.g6e.2xlarge (PeFT/Spectrum)
    NO  → Continue
    ↓
Is your model 17-32B parameters?
    YES → ml.p4de.24xlarge (PeFT/Spectrum)
    NO  → Continue
    ↓
Is your model 32-120B parameters?
    YES → ml.p5e.48xlarge (PeFT/Full)
    NO  → Continue
    ↓
Is your model 600B+ parameters?
    YES → ml.p5en.48xlarge (PeFT/Spectrum/Full)
```

## Instance Specifications

| Instance | GPU | VRAM | Best For |
|----------|-----|------|----------|
| **ml.g5.2xlarge** | 1× A10G | 24 GB | <4B models, QLoRA |
| **ml.g6e.2xlarge** | 1× L40S | 48 GB | 4-14B models, LoRA/Spectrum |
| **ml.g6e.4xlarge** | 1× L40S | 48 GB | 7-14B with larger batch |
| **ml.g6e.12xlarge** | 4× L40S | 192 GB | 7-14B Full fine-tuning |
| **ml.p4de.24xlarge** | 8× A100-80GB | 640 GB | 17-32B models |
| **ml.p5e.48xlarge** | 8× H100 | 640 GB | 32-120B models |
| **ml.p5en.48xlarge** | 8× H100 | 640 GB | 600B+ models |

## Technique Selection by Model Size

### PeFT/QLoRA (Most Memory-Efficient)
| Model Size | Recommended Instance |
|------------|---------------------|
| 1-4B | ml.g5.2xlarge |
| 4-14B | ml.g6e.2xlarge |
| 17-32B | ml.p4de.24xlarge |
| 32-70B | ml.p4de.24xlarge |
| 70B+ | ml.p5e.48xlarge |

### Spectrum Training (Balanced)
| Model Size | Recommended Instance |
|------------|---------------------|
| 1-4B | ml.g6e.2xlarge |
| 7-14B | ml.g6e.2xlarge or ml.g6e.4xlarge |
| 17-32B | ml.p4de.24xlarge |

### Full Fine-Tuning (Maximum Quality)
| Model Size | Recommended Instance |
|------------|---------------------|
| 1-4B | ml.g6e.2xlarge |
| 7-14B | ml.g6e.2xlarge or ml.g6e.12xlarge |
| 17-32B | ml.p4de.24xlarge or ml.p5e.48xlarge |

**Note**: Full fine-tuning typically needs 2-4× more memory than PeFT.

## Training Time Estimates

Reference for 1 epoch with ~10,000 samples:

| Model Size | Technique | Instance | Time |
|------------|-----------|----------|------|
| 1-4B | QLoRA | ml.g5.2xlarge | 2-4 hours |
| 7-14B | QLoRA | ml.g6e.2xlarge | 4-8 hours |
| 17-32B | QLoRA | ml.p4de.24xlarge | 6-12 hours |
| 70B+ | QLoRA | ml.p5e.48xlarge | 12-24 hours |

## Multimodal Models

Vision-language and audio models need **one tier higher** instance than equivalent text-only models:
- 7B VLM → Use instance for ~14B text model
- 13B VLM → Use instance for ~27B text model

## Trainium Instances

| Instance | Accelerators | Memory | Best For |
|----------|--------------|--------|----------|
| **ml.trn1.2xlarge** | 1× Trainium | 32 GB | <8B models, testing |
| **ml.trn1.32xlarge** | 16× Trainium | 512 GB | 8-32B models |
| **ml.trn1n.32xlarge** | 16× Trainium | 512 GB | 8-32B (better network) |
| **ml.trn2.48xlarge** | 16× Trainium2 | 1.5 TB | 32B+ models |

**Note**: Trainium does NOT support 4-bit quantization (QLoRA). Use LoRA or Full FT.

### Trainium Decision Tree

```
START HERE (Trainium)
    ↓
Is your model < 8B parameters?
    YES → ml.trn1.2xlarge (LoRA/SFT)
    NO  → Continue
    ↓
Is your model 8-32B parameters?
    YES → ml.trn1.32xlarge (LoRA/SFT)
    NO  → Continue
    ↓
Is your model 32B+ parameters?
    YES → ml.trn2.48xlarge (LoRA/Full)
```

### Trainium Instance Selection by Technique

| Model Size | LoRA | Full Fine-Tuning |
|------------|------|------------------|
| <8B | ml.trn1.2xlarge | ml.trn1.32xlarge |
| 8-32B | ml.trn1.32xlarge | ml.trn2.48xlarge |
| 32B+ | ml.trn2.48xlarge | Multi-node |

## Dynamic Recommendations

Run the sizing script for automated recommendations:
```bash
# For GPU instances
python scripts/llm-training/fetch_instance_info.py --model-size 8 --technique lora --context-len 8192

# For Trainium instances
python scripts/llm-training/fetch_instance_info.py --model-size 8 --technique lora --accelerator trainium
```

## Instance Availability

**Important**: Instance availability varies by region. Always verify before launching:
```bash
aws service-quotas get-service-quota \
    --service-code sagemaker \
    --quota-code L-... \
    --region us-east-1
```

## Cost Optimization

- **Spot instances**: 50-70% savings for fault-tolerant workloads
- **Warm pools**: Set `keep_alive_period_in_seconds=1800` for iterative training
- **Start small**: Test on smaller instances/datasets before production scale
