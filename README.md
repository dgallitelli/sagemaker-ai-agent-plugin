# SageMaker LLM Training Skill

A Claude Code skill for training and fine-tuning Large Language Models on Amazon SageMaker. This skill provides a guided wizard workflow that takes you from intent to executable training launcher.

## Features

- **Guided Wizard**: Step-by-step questions to gather all required parameters
- **Multiple Training Objectives**: Instruction SFT, Continued Pretraining (CPT), Preference Optimization (DPO)
- **Flexible Techniques**: QLoRA, LoRA, Spectrum, Full Fine-tuning
- **Infrastructure Options**: SageMaker Training Jobs or HyperPod clusters
- **Accelerator Support**: NVIDIA GPUs and AWS Trainium (for supported models)
- **Dynamic Container Selection**: Fetches latest DLC images from AWS
- **Quota Checking**: Validates instance availability in your region

## Installation

Clone this repository to your Claude Code skills directory:

```bash
git clone https://github.com/dgallitelli/sagemaker-llm-training-skill.git \
  ~/.claude/skills/sagemaker-llm-training-skill
```

## Usage

Trigger the skill in Claude Code with phrases like:
- "train llm"
- "fine-tune model"
- "sagemaker training"
- "lora training"
- "qlora"
- "trainium training"

Or invoke directly: `/sagemaker-llm-training-skill`

## Wizard Steps

| Step | Question |
|------|----------|
| 1 | Which model? (HuggingFace ID or S3 path) |
| 2 | Which AWS region? |
| 3 | Training objective? (SFT, CPT, DPO) |
| 4 | Have existing code? |
| 5 | Training technique? (QLoRA, LoRA, Spectrum, Full) |
| 6 | Infrastructure? (Training Jobs vs HyperPod) |
| 7 | Accelerator? (GPU vs Trainium) |
| 8 | Dataset location? |
| 9 | Context length? |
| 10 | Instance type? |
| 11 | Use Spot instances? |
| 12 | S3 output bucket? |
| 13 | IAM execution role? |
| 14 | Output format? (Notebook vs Script) |

## Trainium Support

**Only these exact `model_type` values are supported for training on AWS Trainium:**

| Supported | NOT Supported (variants) |
|-----------|--------------------------|
| `llama` | `llama_vl`, `mllama` |
| `qwen3` | `qwen3_vl`, `qwen2`, `qwen2_5` |
| `granite` | `granite_vl` |

**Important:** Model variants have different architectures! Always check the `model_type` in `config.json`:
- `qwen3` → Supported
- `qwen3_vl` → NOT supported (Vision-Language model)

All other architectures must use GPU (NVIDIA) instances.

**Source**: [Neuron Supported Architectures](https://huggingface.co/docs/optimum-neuron/en/supported_architectures)

## Project Structure

```
sagemaker-llm-training-skill/
├── SKILL.md                    # Main skill instructions
├── references/                 # Detailed guides
│   ├── best-practices.md       # Training recommendations
│   ├── checklist.md            # Pre-delivery verification
│   ├── container-selection.md  # DLC image selection
│   ├── data-contract.md        # Dataset format requirements
│   ├── instance-sizing.md      # Instance recommendations
│   ├── neuron-validation.md    # Neuron architecture support
│   ├── output-artifacts.md     # Generated code format
│   └── recipe-sources.md       # AWS sample recipes
├── scripts/                    # Utility scripts
│   ├── fetch_dlc_images.py     # Get current container images
│   ├── fetch_instance_info.py  # Instance specs lookup
│   ├── inspect_requirements.py # Analyze dependencies
│   └── validate_dataset.py     # Dataset format validation
└── templates/                  # Training code templates
    ├── launch_training_job.py  # SDK v3 ModelTrainer launcher
    ├── lora_peft.py            # LoRA with PEFT
    ├── qlora_peft.py           # QLoRA (4-bit)
    ├── sft_trl.py              # Full SFT with TRL
    ├── dpo_trl.py              # DPO preference training
    ├── cpt_hf.py               # Continued pretraining
    ├── trainium/
    │   ├── lora_neuron.py      # LoRA for Neuron SDK
    │   └── sft_neuron.py       # Full SFT for Neuron
    └── hyperpod/
        ├── recipe_config.yaml  # HyperPod configuration
        └── submit_slurm.sh     # Slurm submission script
```

## Supported Model Families

| Model Family | QLoRA | LoRA | Spectrum | Full | Trainium |
|--------------|-------|------|----------|------|----------|
| Llama | Yes | Yes | Yes | Yes | **Yes** |
| Qwen3 | Yes | Yes | Yes | Yes | **Yes** |
| Granite | Yes | Yes | Yes | Yes | **Yes** |
| Qwen2.5 | Yes | Yes | Yes | Yes | No |
| Gemma | Yes | Yes | No | Yes | No |
| Phi | Yes | Yes | Yes | Yes | No |
| DeepSeek | Yes | Yes | Yes | Yes | No |
| Mistral | Yes | Yes | Yes | Yes | No |

## Requirements

- Python <= 3.13 (SageMaker SDK v3 incompatible with 3.14+)
- AWS CLI configured with appropriate permissions
- SageMaker execution role with S3 and ECR access

## References

- [AWS SageMaker Generative AI Recipes](https://github.com/aws-samples/amazon-sagemaker-generativeai/tree/feature/gpro-rlvr-recipes/0_model_customization_recipes)
- [AWS Deep Learning Containers](https://aws.github.io/deep-learning-containers/reference/available_images/)
- [Neuron Supported Architectures](https://huggingface.co/docs/optimum-neuron/en/supported_architectures)

## License

MIT
