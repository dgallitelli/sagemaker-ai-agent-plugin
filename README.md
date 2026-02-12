# SageMaker LLM Training Skill

A Claude Code skill for training and fine-tuning Large Language Models on Amazon SageMaker. This skill provides a guided wizard workflow that takes you from intent to executable training launcher.

## Features

- **Guided Wizard**: Step-by-step questions to gather all required parameters
- **Multiple Training Objectives**: Instruction SFT, Continued Pretraining (CPT), Preference Optimization (DPO)
- **Flexible Techniques**: QLoRA, LoRA, Spectrum, Full Fine-tuning
- **Infrastructure Options**: SageMaker Training Jobs or HyperPod clusters
- **Accelerator Support**: NVIDIA GPUs and AWS Trainium
- **Neuron Compatibility Testing**: Verify custom model architectures before training
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

## Neuron Compilation Testing

For models not in the [official Neuron supported architectures](https://huggingface.co/docs/optimum-neuron/en/supported_architectures), the skill can deploy a test EC2 instance to verify compatibility before committing to a full training job.

**Cost**: ~$0.30 per test (trn1.2xlarge for ~15 minutes)

**Expected successful output**:
```
Compiler status PASS
...
  Forward pass completed in XXX.Xs
  Output logits shape: torch.Size([1, N, vocab_size])

============================================================
RESULT: Neuron compilation test PASSED
============================================================
```

**Commands**:
```bash
# Deploy test instance
aws cloudformation create-stack --stack-name neuron-compile-test \
  --template-body file://templates/trainium/cfn-neuron-compile-test.yaml \
  --parameters ParameterKey=KeyPairName,ParameterValue=<key-name> \
  --region us-east-1

# Run test (one-liner)
IP=$(aws cloudformation describe-stacks --stack-name neuron-compile-test \
  --query 'Stacks[0].Outputs[?OutputKey==`PublicIP`].OutputValue' --output text --region us-east-1)
ssh -i <key>.pem ubuntu@$IP "source /opt/aws_neuronx_venv_pytorch_2_5_nxd_training/bin/activate && \
  pip install -q 'transformers>=5.0' && cd ~/neuron-test && \
  MODEL_ID='<model-id>' python test_neuron_compile.py"

# Cleanup
aws cloudformation delete-stack --stack-name neuron-compile-test --region us-east-1
```

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
│   ├── neuron-compile-test.md  # Trainium compatibility testing
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
    │   ├── sft_neuron.py       # Full SFT for Neuron
    │   └── cfn-neuron-compile-test.yaml  # EC2 test instance
    └── hyperpod/
        ├── recipe_config.yaml  # HyperPod configuration
        └── submit_slurm.sh     # Slurm submission script
```

## Supported Model Families

| Model Family | QLoRA | LoRA | Spectrum | Full | Trainium |
|--------------|-------|------|----------|------|----------|
| Llama | Yes | Yes | Yes | Yes | Yes |
| Qwen | Yes | Yes | Yes | Yes | Yes |
| Gemma | Yes | Yes | No | Yes | Yes |
| Phi | Yes | Yes | Yes | Yes | Check |
| DeepSeek | Yes | Yes | Yes | Yes | Check |
| Mistral | Yes | Yes | Yes | Yes | Yes |

*"Check" = Use Neuron compilation test to verify compatibility*

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
