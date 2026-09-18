# SageMaker Python SDK v3 — API Reference

Authoritative reference for SDK v3 imports, class signatures, and known gotchas.
Verified against SDK v3.8.0 source. Do not rely on memory or training data — use this file.

---

## Correct Imports

```python
# Core session and role helpers
from sagemaker.train import ModelTrainer
from sagemaker.core.helper.session_helper import Session, get_execution_role

# Image URI lookup
from sagemaker.core import image_uris

# Training configs (canonical paths)
from sagemaker.core.training.configs import (
    Compute,
    SourceCode,
    Networking,
    InputData,
    OutputDataConfig,
    CheckpointConfig,
    TensorBoardOutputConfig,
    StoppingCondition,
)

# Training mode
from sagemaker.train.model_trainer import Mode  # Mode.LOCAL_CONTAINER, Mode.SAGEMAKER_TRAINING_JOB

# Distributed training
from sagemaker.train.distributed import Torchrun, MPI, SMP

# Specialized trainers (fine-tuning)
from sagemaker.train.sft_trainer import SFTTrainer
from sagemaker.train.dpo_trainer import DPOTrainer
from sagemaker.train.rlvr_trainer import RLVRTrainer
from sagemaker.train.rlaif_trainer import RLAIFTrainer

# Deployment (ModelBuilder — V3 preferred for classical ML and JumpStart)
from sagemaker.serve import ModelBuilder, InferenceSpec, ModelServer
from sagemaker.serve.builder.schema_builder import SchemaBuilder
from sagemaker.serve.bedrock_model_builder import BedrockModelBuilder

# Core resources (Model, Endpoint — used for Core API LLM deployments)
from sagemaker.core.resources import Model, EndpointConfig, Endpoint, TrainingJob
from sagemaker.core.shapes.shapes import ContainerDefinition, ProductionVariant

# Core shapes (API-level types shared across SDK)
from sagemaker.core.shapes import (
    TrainingImageConfig,
    TrainingRepositoryAuthConfig,
    AlgorithmSpecification,
    MetricDefinition,
    Tag,
)

# Hyperparameter tuning
from sagemaker.train.tuner import (
    HyperparameterTuner,
    ContinuousParameter,
    IntegerParameter,
    CategoricalParameter,
)

# Processing jobs
from sagemaker.core.processing import ScriptProcessor, ProcessingInput, ProcessingOutput

# Pipelines
from sagemaker.mlops.workflow import Pipeline, TrainingStep, ProcessingStep, CacheConfig
from sagemaker.core.workflow.pipeline_context import PipelineSession
from sagemaker.core.workflow.parameters import ParameterString, ParameterInteger, ParameterFloat
from sagemaker.core.workflow.conditions import ConditionGreaterThanOrEqualTo
from sagemaker.core.workflow.functions import JsonGet
from sagemaker.core.workflow.properties import PropertyFile

# Evaluation
from sagemaker.train import (
    BaseEvaluator, BenchMarkEvaluator, CustomScorerEvaluator,
    LLMAsJudgeEvaluator, EvaluationPipelineExecution,
    get_benchmarks, get_builtin_metrics,
)

# Batch transform
from sagemaker.core.transformer import Transformer

# JumpStart (pretrained model catalog)
from sagemaker.core.jumpstart.notebook_utils import list_jumpstart_models

# Analytics
from sagemaker.core.analytics import TrainingJobAnalytics, ExperimentAnalytics

# Unassigned sentinel (for advanced shape manipulation)
from sagemaker.core.utils.utils import Unassigned
```

> **Note**: If you see imports from `sagemaker.workflow.*`, `sagemaker.estimator`,
> `sagemaker.model`, `sagemaker.processing`, or `sagemaker.transformer`
> — those are SDK v2. Do not use them. V3 moved them to `sagemaker.core.*` or `sagemaker.mlops.*`.

---

## `image_uris.retrieve()` — Framework Reference

### XGBoost
```python
image_uri = image_uris.retrieve(
    framework="xgboost",
    region=region,
    version="1.7-1",      # also: "1.5-1"
    # No py_version needed for XGBoost
    # No instance_type needed for XGBoost
)
```

### SKLearn (Scikit-learn)
```python
image_uri = image_uris.retrieve(
    framework="sklearn",
    region=region,
    version="1.2-1",      # also: "1.0-1"
    # No py_version needed for SKLearn
    # No instance_type needed for SKLearn
)
```

### PyTorch
```python
image_uri = image_uris.retrieve(
    framework="pytorch",
    region=region,
    version="2.1",        # also: "2.0"
    py_version="py310",   # REQUIRED for PyTorch
    instance_type="ml.m5.xlarge",  # REQUIRED for PyTorch — affects image selection
    image_scope="training",
)
```

---

## `ModelTrainer` — Constructor Parameters

```python
from sagemaker.train import ModelTrainer

trainer = ModelTrainer(
    # REQUIRED (one of training_image or algorithm_name, not both)
    training_image=image_uri,           # str — from image_uris.retrieve()
    role=role_arn,                       # str — IAM role ARN

    # Source code
    source_code=SourceCode(
        source_dir="./training",         # local dir with train.py + requirements.txt
        entry_script="train.py",         # MUST be "entry_script", NOT "entry_point"
        requirements="requirements.txt", # path relative to source_dir
        command=None,                    # optional custom command (overrides entry_script)
    ),

    # Compute
    compute=Compute(
        instance_type="ml.m5.xlarge",
        instance_count=1,
        volume_size_in_gb=30,
        keep_alive_period_in_seconds=0,  # 0 = no warm pool (avoids idle billing)
        enable_managed_spot_training=None,
    ),

    # Output
    output_data_config=OutputDataConfig(
        s3_output_path="s3://bucket/output/",  # MUST use this, not output_path=
    ),

    # Optional
    base_job_name="my-training-job",
    hyperparameters={"n-estimators": 100, "max-depth": 5},
    stopping_condition=StoppingCondition(max_runtime_in_seconds=3600),
    training_mode=Mode.SAGEMAKER_TRAINING_JOB,  # or Mode.LOCAL_CONTAINER
    training_image_config=None,          # TrainingImageConfig for private Docker registries
    networking=None,                     # Networking(subnets=..., security_group_ids=...)
    distributed=None,                    # Torchrun(...) or MPI(...)
    environment={},                      # Dict of env vars
    tags=None,                           # List of Tag objects
    sagemaker_session=Session(),
)
```

### Key Methods

```python
trainer.train(input_data_config=None, wait=True, logs=True)
trainer.with_tensorboard_output_config(config) -> ModelTrainer  # fluent
trainer.with_retry_strategy(strategy) -> ModelTrainer           # fluent
trainer.with_checkpoint_config(config) -> ModelTrainer           # fluent
trainer.with_metric_definitions(metrics) -> ModelTrainer         # fluent
ModelTrainer.from_recipe(recipe_id, session=None, role=None)     # static
ModelTrainer.from_jumpstart_config(config, session=None)         # static
```

---

## `.train()` — Launch Parameters

```python
trainer.train(
    input_data_config=[
        {
            "channel_name": "train",
            "data_source": {
                "s3_data_source": {
                    "s3_uri": "s3://bucket/data/train/",
                    "s3_data_type": "S3Prefix",
                }
            },
        },
    ],
    wait=True,    # True = block until complete
    logs=True,    # MUST be boolean True — NOT the string 'All'
)
```

Dict form and `InputData` class both work for `input_data_config`. Dict form is simpler.

---

## Private Docker Registry (Undocumented but Supported)

`training_image_config` is a first-class parameter on ModelTrainer but is NOT documented in any AWS blog or readthedocs. It is passed directly to `AlgorithmSpecification`.

```python
from sagemaker.core.shapes import TrainingImageConfig, TrainingRepositoryAuthConfig

trainer = ModelTrainer(
    training_image="my-registry.example.com/training:latest",
    training_image_config=TrainingImageConfig(
        training_repository_access_mode="Vpc",
        training_repository_auth_config=TrainingRepositoryAuthConfig(
            training_repository_credentials_provider_arn="arn:aws:lambda:us-west-2:123456789012:function:get-creds"
        ),
    ),
    # ...
)
```

---

## IAM Role Discovery

`get_execution_role()` only works inside SageMaker Studio. Outside Studio, use:

```python
import boto3

def get_role(role_name=None):
    iam = boto3.client("iam")
    if role_name:
        return iam.get_role(RoleName=role_name)["Role"]["Arn"]
    paginator = iam.get_paginator("list_roles")
    for page in paginator.paginate():
        for role in page["Roles"]:
            if "SageMaker" in role["RoleName"] or "sagemaker" in role["RoleName"]:
                return role["Arn"]
    raise ValueError("No SageMaker role found. Pass --role explicitly.")
```

---

## Training Script — Environment Variables

SageMaker sets these automatically in the container:

| Variable | Value |
|----------|-------|
| `SM_CHANNEL_TRAIN` | `/opt/ml/input/data/train` |
| `SM_CHANNEL_VALIDATION` | `/opt/ml/input/data/validation` |
| `SM_CHANNEL_TEST` | `/opt/ml/input/data/test` |
| `SM_MODEL_DIR` | `/opt/ml/model` |
| `SM_OUTPUT_DATA_DIR` | `/opt/ml/output/data` |
| `SM_NUM_CPUS` | Number of vCPUs |
| `SM_NUM_GPUS` | Number of GPUs |
| `SM_HP_*` | Each hyperparameter (uppercase, hyphens→underscores) |

```python
import os
train_dir = os.environ.get("SM_CHANNEL_TRAIN", "/opt/ml/input/data/train")
model_dir = os.environ.get("SM_MODEL_DIR", "/opt/ml/model")
```

---

## `ModelBuilder` — V3 Deployment

```python
from sagemaker.serve import ModelBuilder, InferenceSpec, ModelServer

builder = ModelBuilder(
    model="meta-llama/Llama-2-7b",    # HF model ID, local path, ModelTrainer, or JumpStart ID
    model_server=ModelServer.TGI,      # TGI, DJL_SERVING, TORCHSERVE, TRITON, TEI, MMS, SMD
    instance_type="ml.g5.xlarge",
    role_arn=role_arn,
    inference_spec=None,               # InferenceSpec for custom load/invoke
    schema_builder=None,               # SchemaBuilder for serialization
    image_uri=None,                    # auto-detected if omitted
    env_vars={},
    sagemaker_session=Session(),
)

model = builder.build()                # returns sagemaker.core.resources.Model
endpoint = builder.deploy(wait=True)   # returns sagemaker.core.resources.Endpoint (NOT Predictor)
```

### `InferenceSpec` — V3 Inference Contract

```python
class MyInferenceSpec(InferenceSpec):
    def load(self, model_dir: str):
        import joblib
        return joblib.load(os.path.join(model_dir, "model.joblib"))

    def invoke(self, input_object, model):
        return model.predict(input_object)

    def preprocess(self, input_data):   # optional
        return transform(input_data)

    def postprocess(self, predictions): # optional
        return format(predictions)
```

> Container-level hooks (`model_fn`, `input_fn`, `predict_fn`, `output_fn`) still work with framework containers. `InferenceSpec` is the V3-native alternative. Use hooks with built-in framework containers; use `InferenceSpec` with `ModelBuilder`.

### ModelBuilder Pitfalls

1. `dependencies={"auto": True}` scans local Python env and may overwrite DLC's torch/CUDA. Always use `dependencies={"auto": False}`.
2. `model=` string makes ModelBuilder use HF default handler regardless of `image_uri`. Use Core API for DJL/vLLM.
3. `deploy()` returns `Endpoint` (v3), not `Predictor` (v2).
4. `SchemaBuilder` must be a `SchemaBuilder(sample_input, sample_output)` object, not a plain dict.

---

## Core Resources — ORM-like API

600+ auto-generated resource classes with standard CRUD:

```python
from sagemaker.core.resources import TrainingJob, Endpoint, Model

job = TrainingJob.create(session=boto_session, **args)
job = TrainingJob.get("job-name", session=session)
job.refresh()
job.wait_for_status("Completed", poll=5, timeout=3600)
job.delete()
all_jobs = TrainingJob.get_all(created_after=datetime(2024, 1, 1), session=session)
```

---

## Core Shapes — Pydantic v2 Models

All API-level types inherit from `Base` (Pydantic `BaseModel`, strict validation, `extra="forbid"`). Optional fields use `Unassigned()` singleton sentinel (not `None`).

---

## LLM Deployment — Core API Imports

Use for DJL LMI / vLLM deployments. Do NOT use `ModelBuilder` with DJL/vLLM containers.

```python
from sagemaker.core.resources import Model, EndpointConfig, Endpoint
from sagemaker.core.shapes.shapes import ContainerDefinition, ProductionVariant
```

> **When to use Core API vs ModelBuilder:**
> - Core API: DJL LMI, vLLM, any deployment needing full container control
> - ModelBuilder: JumpStart models (pass model ID), simple HuggingFace, classical ML
> - Do NOT use ModelBuilder with DJL/vLLM containers — it overrides container behavior

---

## Model Monitor Imports

All monitoring classes live under `sagemaker.core`:

```python
from sagemaker.core.model_monitor import (
    DefaultModelMonitor,
    ModelQualityMonitor,
    DataCaptureConfig,
    CronExpressionGenerator,
    DatasetFormat,
    EndpointInput,
)
from sagemaker.core.model_monitor.clarify_model_monitoring import (
    ModelBiasMonitor,
    ModelExplainabilityMonitor,
)
from sagemaker.core.model_monitor.model_monitoring import Constraints
from sagemaker.core.clarify import (
    BiasConfig, DataConfig, ModelConfig,
    ModelPredictedLabelConfig, SHAPConfig,
)
```

---

## CUDA Version Compatibility

| CUDA Version | Works On | Fails On |
|---|---|---|
| cu124 | g5, g6, p5 | — |
| cu128 | g5, g6, p5 | — |
| cu129 | g6, p5 | g5 (driver mismatch → CannotStartContainerError) |

---

## Known Gotchas

1. **`entry_script` not `entry_point`** — SourceCode uses `entry_script`. `entry_point` is v2.
2. **`output_data_config` not `output_path`** — ModelTrainer takes `output_data_config=OutputDataConfig(...)`.
3. **`logs=True` not `logs='All'`** — `.train()` takes a boolean.
4. **Hyperparameters arrive as strings** — Always cast with `type=int`/`type=float` in argparse.
5. **`get_execution_role()` outside Studio** — raises exception. Use IAM discovery snippet.
6. **`keep_alive_period_in_seconds` billing** — non-zero keeps instance warm, incurs charges.
7. **Channel name case** — `"train"` in launcher → `SM_CHANNEL_TRAIN` in script (uppercase).
8. **PyTorch requires `instance_type` in `image_uris.retrieve()`** — XGBoost/SKLearn do not.
9. **`sagemaker.__version__` does not exist** — use `importlib.metadata.version("sagemaker")`.
10. **`import sagemaker_core` fails** — use `from sagemaker.core.shapes import ...` (not `sagemaker_core`).
11. **TrainingImageConfig in sagemaker.core.shapes** — not in `sagemaker.train.configs`.
12. **v3 readthedocs are sparse** — inspect installed source when in doubt.
13. **`PipelineSession` vs `Session`** — use `PipelineSession` when building pipeline steps (defers execution).
14. **SDK v3 `Endpoint.get().invoke()` has Pydantic `kms_key_id` bug** — use `boto3.client('sagemaker-runtime').invoke_endpoint()` instead.

---

## SDK Version Detection

```python
from importlib.metadata import version
print(version("sagemaker"))  # e.g., "3.8.0"
```

---

## Training Job Console URL

```python
region = boto3.session.Session().region_name
job_name = trainer.latest_training_job.name
print(f"https://{region}.console.aws.amazon.com/sagemaker/home?region={region}#/jobs/{job_name}")
```

---

## HyperPod SDK Imports

```python
# JumpStart on HyperPod
from sagemaker.hyperpod.inference.config.hp_jumpstart_endpoint_config import (
    Model, Server, SageMakerEndpoint, TlsConfig,
)
from sagemaker.hyperpod.inference.hp_jumpstart_endpoint import HPJumpStartEndpoint

# Custom models on HyperPod
from sagemaker.hyperpod.inference.config.hp_custom_endpoint_config import (
    Model, Server, SageMakerEndpoint, TlsConfig, EnvironmentVariables,
)
from sagemaker.hyperpod.inference.hp_custom_endpoint import HPCustomEndpoint
```

Install: `pip install sagemaker-hyperpod`
CLI: `hyp set-cluster-context --cluster-name <cluster>`
