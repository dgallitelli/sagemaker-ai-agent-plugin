# Container Selection SOP (SageMaker Training)

Select the appropriate container strategy based on user's code and requirements.

## Authoritative DLC Image Source

**ALWAYS** reference the official AWS Deep Learning Containers page for current images:
- **URL**: https://aws.github.io/deep-learning-containers/reference/available_images/

This page contains the definitive list of available container images, organized by:
- Framework (PyTorch, TensorFlow, etc.)
- Training vs Inference
- GPU vs Neuron (Trainium/Inferentia)
- Region availability

## Dynamic Container Lookup

Fetch current container images using WebFetch:
```
WebFetch: https://aws.github.io/deep-learning-containers/reference/available_images/
Prompt: "Find the latest PyTorch training GPU container image for SageMaker"
```

Or use the helper script (may have stale fallbacks):
```bash
python scripts/fetch_dlc_images.py --framework pytorch --region us-east-1
python scripts/fetch_dlc_images.py --framework neuron --region us-east-1
```

## Step 1: Determine Target Accelerator

Inspect user's `requirements.txt`:
```bash
python scripts/inspect_requirements.py path/to/requirements.txt
```

### GPU Indicators
- `bitsandbytes` → Must use GPU (4-bit quantization)
- `flash-attn` → GPU recommended
- `xformers` → GPU only
- Any CUDA-specific wheels

### Trainium Indicators
- `torch-neuronx` → Use Trainium
- `neuronx-distributed` → Use Trainium
- `optimum-neuron` → Use Trainium

### Neutral (Either works)
- `transformers`, `accelerate`, `peft`, `trl`
- Standard PyTorch packages

## Step 2: Select Container Family

### For GPU Training

Use **SageMaker PyTorch Training DLC**:
```
763104351884.dkr.ecr.<region>.amazonaws.com/pytorch-training:<version>-gpu-py<python>-cu<cuda>-ubuntu<version>-sagemaker
```

Recommended versions (fetch latest with script):
- PyTorch 2.5+ for newest features
- CUDA 12.x for latest GPU support
- Python 3.11 or 3.12

### For Trainium Training

Use **SageMaker Neuron Training DLC**:
```
763104351884.dkr.ecr.<region>.amazonaws.com/pytorch-training-neuronx:<version>-neuronx-py<python>-sdk<sdk>-ubuntu<version>
```

## Step 3: Version Compatibility Checks

### Critical Compatibility Matrix

| Package | GPU Container | Neuron Container |
|---------|---------------|------------------|
| PyTorch | 2.0+ | torch-neuronx version |
| Transformers | 4.36+ | 4.36+ (optimum-neuron) |
| Accelerate | 0.25+ | Via neuronx-distributed |
| PEFT | 0.7+ | 0.7+ |
| TRL | 0.7+ | May need patches |
| bitsandbytes | ✅ | ❌ Not supported |
| DeepSpeed | ✅ | ❌ Use neuronx-distributed |

### Version Pin Sanity

Ensure these are compatible:
1. PyTorch version matches container base
2. Transformers + Accelerate are compatible
3. PEFT version supports the model architecture
4. TRL version matches transformers

## Step 4: Runtime Installation Strategy

### Approach A: Minimal Runtime Install (Recommended)

Install only additional packages at runtime:
```python
# In your requirements.txt
peft>=0.7.0
trl>=0.7.0
datasets
# DON'T pin torch, transformers - use container versions
```

### Approach B: Full Requirements

If user has strict version requirements:
```python
# requirements.txt
torch==2.5.1
transformers==4.46.0
accelerate==0.25.0
peft==0.13.0
trl==0.12.0
```

⚠️ May conflict with container - test before production

## Step 5: Environment Variables

### For GPU Training
```bash
# Recommended env vars
NCCL_DEBUG=INFO
CUDA_DEVICE_MAX_CONNECTIONS=1
TRANSFORMERS_CACHE=/opt/ml/input/data/cache
HF_HOME=/opt/ml/input/data/cache
```

### For Trainium Training
```bash
NEURON_CC_FLAGS="--target=trn1"
NEURON_RT_VISIBLE_CORES=0-15
MALLOC_ARENA_MAX=64
```

### For FlashAttention
```bash
FLASH_ATTENTION_FORCE_BUILD=TRUE  # If not pre-built
```

## Decision Flowchart

```
User has requirements.txt?
├── Yes → Run inspect_requirements.py
│         ├── GPU indicators? → GPU DLC
│         ├── Trainium indicators? → Neuron DLC
│         └── Neutral? → Ask user preference (default: GPU)
└── No → Based on technique:
         ├── QLoRA → GPU DLC (bitsandbytes needed)
         ├── LoRA/Full SFT → Either (default: GPU)
         └── User requests Trainium → Verify model support first
```

## Output to User

Provide:
1. **Container URI**: Full ECR path
2. **Runtime requirements**: What to `pip install`
3. **Environment variables**: Key settings for the container
4. **Compatibility notes**: Any version constraints
