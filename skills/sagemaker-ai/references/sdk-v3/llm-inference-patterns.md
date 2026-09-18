# SageMaker SDK v3 — LLM Inference Patterns

Deployment patterns for LLMs and multimodal models using DJL LMI with vLLM, Core API, and ModelBuilder.
All code is SDK v3 compatible. Do not use SDK v2 patterns.

---

## Container Selection

### Decision Tree

1. Standard text LLM (Llama, Mistral, Qwen, DeepSeek) → DJL LMI with vLLM backend
2. Multimodal/Vision model (Idefics3, LLaVA, Qwen-VL) → DJL LMI with vLLM backend
3. Simple HF pipeline model (classification, NER) → HuggingFace Inference DLC
4. Custom model with custom handler → HuggingFace Inference DLC + custom `inference.py` in `model.tar.gz`

### DJL LMI with vLLM Backend (Recommended for LLMs)

Best for: LLMs, multimodal models, any model supported by vLLM.

Image pattern: `763104351884.dkr.ecr.<region>.amazonaws.com/djl-inference:<version>-lmi<lmi_version>-cu<cuda>`

Key env vars:
- `HF_MODEL_ID` — HuggingFace model ID (e.g., `meta-llama/Llama-3.1-8B-Instruct`)
- `OPTION_ROLLING_BATCH=vllm` — Use vLLM as the inference backend
- `OPTION_DTYPE=fp16` or `bf16` — Model precision (critical for fitting on GPU)
- `OPTION_MAX_MODEL_LEN=4096` — Maximum sequence length
- `OPTION_TENSOR_PARALLEL_DEGREE=1` — Number of GPUs for tensor parallelism

### HuggingFace Inference DLC

Best for: Simple HF pipeline models (classification, NER, summarization) or models with custom `inference.py` handlers.

Image pattern: `763104351884.dkr.ecr.<region>.amazonaws.com/huggingface-pytorch-inference:<pt_version>-transformers<tf_version>-gpu-py<py>-cu<cuda>-ubuntu<os>`

Limitations:
- Default handler loads models in FP32 — no env var to override dtype
- For 8B+ models on 24GB GPUs, this will OOM
- Custom `inference.py` must be packaged in `model.tar.gz` at `code/inference.py`

### HuggingFace vLLM DLC

Image pattern: `763104351884.dkr.ecr.<region>.amazonaws.com/huggingface-vllm:<vllm_version>-transformers<tf_version>-gpu-py<py>-cu<cuda>-ubuntu<os>`

Note: As of the latest release, this DLC only ships with cu129 which does not work on ml.g5 instances. Use the DJL LMI container with vLLM backend instead for g5 instances.

### Where to Find Latest DLC Images

The canonical source for AWS Deep Learning Container images is:
`https://aws.github.io/deep-learning-containers/reference/available_images/`

The HuggingFace docs page (`huggingface.co/docs/sagemaker/en/reference`) is outdated and only lists images up to transformers 4.26. Do not use it.

---

## CUDA Version Compatibility

This is critical and easy to get wrong:

| CUDA Version | Works On | Fails On |
|---|---|---|
| cu124 | g5, g6, p5 | — |
| cu128 | g5, g6, p5 | — |
| cu129 | g6, p5 | g5 (driver version mismatch → CannotStartContainerError) |

Note: cu129 failure on g5 is due to the DLC requiring a newer GPU driver than what's installed on g5 instances. Inferentia2 (inf2) instances do not use CUDA — use Neuron SDK containers instead.

### Instance Family Quick Reference

| Instance Family | GPU | VRAM | Max CUDA | Recommended DLC |
|---|---|---|---|---|
| ml.g5.* | A10G (24GB) | 24GB per GPU | cu128 | `djl-inference:0.36.0-lmi20.0.0-cu128` |
| ml.g6.* | L4 (24GB) | 24GB per GPU | cu129 | `djl-inference:0.36.0-lmi22.0.0-cu129` |
| ml.p5.* | H100 (80GB) | 80GB per GPU | cu129 | `djl-inference:0.36.0-lmi22.0.0-cu129` |

Always check the DLC images page for the latest versions — the versions above are examples.

---

## Core API Deployment Pattern (Recommended for DJL/vLLM)

Use `Model.create` + `EndpointConfig.create` + `Endpoint.create` for full control over the container and env vars. Do NOT use `ModelBuilder` with DJL/vLLM containers — it overrides container behavior.

```python
from sagemaker.core.resources import Model, EndpointConfig, Endpoint
from sagemaker.core.shapes.shapes import ContainerDefinition, ProductionVariant
from sagemaker.core.helper.session_helper import Session, get_execution_role
import boto3

sess = Session()
region = sess.boto_region_name
role_arn = get_execution_role()

model_name = "llama-31-8b"
endpoint_name = "llama-31-8b-endpoint"

# Step 1: Create model
Model.create(
    model_name=model_name,
    primary_container=ContainerDefinition(
        image=f"763104351884.dkr.ecr.{region}.amazonaws.com/djl-inference:0.36.0-lmi20.0.0-cu128",
        environment={
            "HF_MODEL_ID": "meta-llama/Llama-3.1-8B-Instruct",
            "OPTION_ROLLING_BATCH": "vllm",
            "OPTION_DTYPE": "fp16",
            "OPTION_MAX_MODEL_LEN": "4096",
            "OPTION_TENSOR_PARALLEL_DEGREE": "1",
        },
    ),
    execution_role_arn=role_arn,
)

# Step 2: Create endpoint config
EndpointConfig.create(
    endpoint_config_name=endpoint_name,
    production_variants=[
        ProductionVariant(
            variant_name="AllTraffic",
            model_name=model_name,
            initial_instance_count=1,
            instance_type="ml.g5.2xlarge",
            initial_variant_weight=1.0,
            container_startup_health_check_timeout_in_seconds=900,
            model_data_download_timeout_in_seconds=900,
        )
    ],
)

# Step 3: Create endpoint
Endpoint.create(
    endpoint_name=endpoint_name,
    endpoint_config_name=endpoint_name,
)

# Step 4: Wait for InService
sm = boto3.client("sagemaker", region_name=region)
waiter = sm.get_waiter("endpoint_in_service")
waiter.wait(EndpointName=endpoint_name, WaiterConfig={"Delay": 30, "MaxAttempts": 60})
print(f"Endpoint {endpoint_name} is InService")
```

---

## ModelBuilder for JumpStart Models

Use `ModelBuilder` only for JumpStart models or simple HF models. Do NOT use it for DJL/vLLM containers.

```python
from sagemaker.serve import ModelBuilder
from sagemaker.serve.builder.schema_builder import SchemaBuilder

builder = ModelBuilder(
    model="meta-textgeneration-llama-3-1-8b",  # JumpStart model ID
    schema_builder=SchemaBuilder(
        {"inputs": "Hello", "parameters": {"max_new_tokens": 32}},
        [{"generated_text": "sample"}],
    ),
    instance_type="ml.g5.2xlarge",
)
builder.build()
endpoint = builder.deploy(
    initial_instance_count=1,
    instance_type="ml.g5.2xlarge",
    endpoint_name="my-jumpstart-endpoint",
)
```

### ModelBuilder Pitfalls

1. `dependencies={"auto": True}` scans your local Python environment and installs those exact versions in the container. If your local machine has `torch==2.10` but the DLC has `torch==2.6`, it will overwrite the DLC's torch and break CUDA/NCCL. Fix: Always use `dependencies={"auto": False}`.

2. `model=` string parameter makes ModelBuilder use the HF default handler regardless of `image_uri`. It ignores your DJL/vLLM container. Fix: Use the Core API directly for DJL/vLLM containers.

3. `InferenceSpec` serializes your Python class via cloudpickle. The container needs `cloudpickle` and `sagemaker` installed to deserialize it. Fix: Avoid InferenceSpec for LLM production. Use the Core API with container-native env vars.

4. `deploy()` returns an `Endpoint` object (SDK v3), not a `Predictor` (SDK v2).

5. `SchemaBuilder` must be a `SchemaBuilder(sample_input, sample_output)` object, not a plain dict.

---

## Invocation Patterns

### Via boto3 (Recommended)

Always use boto3 `sagemaker-runtime` for invocation — the SDK v3 `Endpoint.get().invoke()` hits a Pydantic `kms_key_id` bug:

```python
import boto3, json
from botocore.config import Config

runtime = boto3.client("sagemaker-runtime", config=Config(read_timeout=600))

# Simple text generation
response = runtime.invoke_endpoint(
    EndpointName="my-endpoint",
    ContentType="application/json",
    Body=json.dumps({
        "inputs": "What is machine learning?",
        "parameters": {"max_new_tokens": 256, "temperature": 0.7},
    }),
)
result = json.loads(response["Body"].read())
print(result)
```

### Multimodal Invocation (Image + Text)

DJL LMI with vLLM backend accepts:

```python
payload = {
    "inputs": "User: <image>Describe this image.\nAssistant:",
    "parameters": {"max_new_tokens": 256},
    "images": ["data:image/png;base64,<BASE64_DATA>"],
}
```

### First Invocation Notes

The first invocation after deploy may timeout because:
- The model loads lazily on first request (DJL LMI behavior)
- Model weights download from HuggingFace Hub

Solutions:
- Add a warm-up wait (120-180s) after endpoint goes InService
- Use `boto3` with `Config(read_timeout=600)` for the first call
- Implement retry logic in your client

---

## Endpoint Configuration

### Timeouts

For models that download from HuggingFace Hub at container startup:

```python
ProductionVariant(
    variant_name="AllTraffic",
    model_name="my-model",
    initial_instance_count=1,
    instance_type="ml.g5.2xlarge",
    initial_variant_weight=1.0,
    container_startup_health_check_timeout_in_seconds=900,  # 15 min
    model_data_download_timeout_in_seconds=900,             # 15 min
)
```

Default is 300s which is too short for large models.

---

## Model Memory Sizing

Quick reference for GPU memory requirements:

| Model Size | FP32 | FP16/BF16 | INT8 | Fits On |
|---|---|---|---|---|
| 7-8B | ~32GB | ~16GB | ~8GB | g5.xlarge (FP16), g6.xlarge (FP16) |
| 13B | ~52GB | ~26GB | ~13GB | g5.12xlarge (4x A10G, TP=2+), g6.12xlarge, p5 (any) |
| 70B | ~280GB | ~140GB | ~70GB | p5.48xlarge (8x H100), g5.48xlarge (8x A10G, TP=8) |

Note: 13B FP16 (~26GB) exceeds single A10G capacity (24GB). Use multi-GPU instances with tensor parallelism.

Always use FP16 or BF16 for inference — FP32 is wasteful and often won't fit.

---

## Cleanup

```python
import boto3
sm = boto3.client("sagemaker")
sm.delete_endpoint(EndpointName="my-endpoint")
sm.delete_endpoint_config(EndpointConfigName="my-endpoint")
sm.delete_model(ModelName="my-model")
```

---

## Troubleshooting

### CannotStartContainerError
**Cause:** CUDA version incompatibility between container and instance.
**Fix:** Use cu128 for g5 instances, cu129 only for g6/p5.

### Worker died / Load model failed
**Cause:** Out of memory — model too large for GPU.
**Fix:**
- Use `OPTION_DTYPE=fp16` or `bf16` (DJL LMI)
- Use a larger instance type
- Reduce `OPTION_MAX_MODEL_LEN`
- For HF DLC: the default handler loads in FP32 with no override — switch to DJL LMI

### ncclCommShrink undefined symbol
**Cause:** `ModelBuilder` `auto:True` dependencies overwrote the DLC's PyTorch with an incompatible version.
**Fix:** Use `dependencies={"auto": False}`.

### bitsandbytes not found
**Cause:** Using a quantized model revision (e.g., `quantized8bit`) but the DLC doesn't include bitsandbytes.
**Fix:** Use the `main` revision with `OPTION_DTYPE=fp16` instead.

### No inference script implementation found
**Cause:** Custom `inference.py` not placed where the HF DLC expects it (`/opt/ml/model/code/inference.py`).
**Fix:** Package as `model.tar.gz` with `code/inference.py` inside, upload to S3, and set `model_data_url`. Or switch to DJL LMI which doesn't need custom handlers.

### Invocation timeout (server error 0)
**Cause:** Model still loading on first request.
**Fix:** Wait 120-180s after InService before first invocation. Use `Config(read_timeout=600)` in boto3.

### SSO session expired during long deployments
**Cause:** AWS SSO tokens expire (typically 1-8 hours).
**Fix:** Run `aws sso login` before long operations. For automated scripts, use IAM roles or long-lived credentials.
