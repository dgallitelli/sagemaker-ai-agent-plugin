# Trainium / Neuron Validation SOP

Before recommending Trainium instances, verify model architecture compatibility.

**CRITICAL**: Only offer Trainium if the model architecture is explicitly supported.

## Authoritative Source for Supported Architectures

**Always check the official optimum-neuron documentation:**
- **URL**: https://huggingface.co/docs/optimum-neuron/en/supported_architectures

This page contains the definitive list of supported model architectures for training on Trainium.

## Verification Steps

### 1. Check Supported Architectures (Required)

Use WebFetch to verify model support:
```
WebFetch: https://huggingface.co/docs/optimum-neuron/en/supported_architectures
Prompt: "Is <model_type> supported for training on Trainium/Neuron? List all supported training architectures."
```

### 2. Check Model Architecture Type

```python
from transformers import AutoConfig

config = AutoConfig.from_pretrained("model-id")
print(f"Architecture: {config.architectures}")
print(f"Model type: {config.model_type}")
```

Then verify the `model_type` against the supported architectures page.

### 3. Test Compilation (Optional)

For uncertain cases, test Neuron compilation:

```python
import torch_neuronx

# Attempt to trace model
try:
    traced_model = torch_neuronx.trace(model, example_input)
    print("✓ Model compiles successfully")
except Exception as e:
    print(f"✗ Compilation failed: {e}")
```

## Decision Matrix

| Scenario | Recommendation |
|----------|----------------|
| Llama/Mistral/Qwen + standard fine-tuning | ✅ Trainium recommended |
| Custom architecture | ⚠️ Verify first, default to GPU |
| Uses bitsandbytes (4-bit) | ❌ GPU only (no Neuron support) |
| Uses FlashAttention-2 | ⚠️ Use Neuron attention instead |
| Vision-language model | ⚠️ Check specific model support |

## Requirements Detection

The `scripts/inspect_requirements.py` script detects these packages:

### GPU-Only Indicators
- `bitsandbytes` - 4-bit quantization
- `flash-attn` - FlashAttention (GPU-specific)
- `xformers` - GPU memory optimization
- CUDA-specific wheels

### Trainium Indicators
- `torch-neuronx` - Neuron PyTorch
- `neuronx-distributed` - Distributed training on Neuron
- `optimum-neuron` - HuggingFace Optimum for Neuron
- `neuronx-cc` - Neuron compiler

## Container Selection for Trainium

Use AWS Deep Learning Containers for Neuron:

```bash
# Fetch latest Neuron container
python scripts/fetch_dlc_images.py --framework neuron --region us-east-1
```

Example URI pattern:
```
763104351884.dkr.ecr.<region>.amazonaws.com/pytorch-training-neuronx:2.1-neuronx-py310-sdk2.20-ubuntu20.04
```

## Common Issues and Solutions

### Issue: Model not compiling
- **Cause**: Unsupported operations in model
- **Solution**: Use GPU instances instead, or check for Neuron-compatible model variants

### Issue: Performance worse than expected
- **Cause**: Suboptimal batch size or sequence length
- **Solution**: Trainium prefers larger batches; adjust batch size and gradient accumulation

### Issue: Out of memory on Trainium
- **Cause**: Model too large for single chip
- **Solution**: Use ml.trn1.32xlarge with distributed training (neuronx-distributed)

## When to Default to GPU

Recommend GPU over Trainium when:
1. Model architecture not explicitly supported
2. Requirements include GPU-specific packages
3. User needs QLoRA (4-bit training)
4. Time-to-first-result is critical (Neuron compilation adds overhead)
5. Model uses custom CUDA kernels
