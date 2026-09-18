# SageMaker SDK v3 — Training Launcher Patterns

Copy-paste ready launcher patterns for each framework. These are complete, working examples.
Start from `templates/launcher.py` and refer here for framework-specific details.

---

## IAM Role Discovery

See `api-reference.md` → "IAM Role Discovery" for the `get_role()` function.
Use it in all launchers below as `role=get_role()`.

---

## XGBoost Launcher

```python
from sagemaker.train import ModelTrainer
from sagemaker.core.helper.session_helper import Session
from sagemaker.core import image_uris
from sagemaker.core.training.configs import Compute, SourceCode, OutputDataConfig, StoppingCondition

region = "us-east-1"  # or: boto3.session.Session().region_name

image_uri = image_uris.retrieve(
    framework="xgboost",
    region=region,
    version="1.7-1",   # also: "1.5-1"
    # No py_version or instance_type needed for XGBoost
)

trainer = ModelTrainer(
    training_image=image_uri,
    role=get_role(),
    source_code=SourceCode(
        source_dir="./training",
        entry_script="train.py",
        requirements="requirements.txt",
    ),
    compute=Compute(
        instance_type="ml.m5.xlarge",  # or ml.m5.2xlarge for larger datasets
        instance_count=1,
        volume_size_in_gb=30,
    ),
    output_data_config=OutputDataConfig(
        s3_output_path="s3://my-bucket/xgboost/output/",
    ),
    hyperparameters={
        "n-estimators": 200,
        "max-depth": 6,
        "learning-rate": 0.05,
        "objective": "binary:logistic",
    },
    base_job_name="xgboost-training",
    stopping_condition=StoppingCondition(max_runtime_in_seconds=3600),
    sagemaker_session=Session(),
)

trainer.train(
    input_data_config=[
        {
            "channel_name": "train",
            "data_source": {
                "s3_data_source": {
                    "s3_uri": "s3://my-bucket/data/train/",
                    "s3_data_type": "S3Prefix",
                }
            },
        },
        {
            "channel_name": "validation",
            "data_source": {
                "s3_data_source": {
                    "s3_uri": "s3://my-bucket/data/validation/",
                    "s3_data_type": "S3Prefix",
                }
            },
        },
    ],
    wait=True,
    logs=True,
)
```

---

## SKLearn (Scikit-learn) Launcher

```python
image_uri = image_uris.retrieve(
    framework="sklearn",
    region=region,
    version="1.2-1",   # also: "1.0-1"
    # No py_version or instance_type needed for SKLearn
)

trainer = ModelTrainer(
    training_image=image_uri,
    role=get_role(),
    source_code=SourceCode(
        source_dir="./training",
        entry_script="train.py",
        requirements="requirements.txt",
    ),
    compute=Compute(
        instance_type="ml.m5.xlarge",
        instance_count=1,
        volume_size_in_gb=30,
    ),
    output_data_config=OutputDataConfig(
        s3_output_path="s3://my-bucket/sklearn/output/",
    ),
    hyperparameters={
        "n-estimators": 100,
        "max-depth": 10,
        "random-state": 42,
    },
    base_job_name="sklearn-training",
    sagemaker_session=Session(),
)

trainer.train(
    input_data_config=[
        {
            "channel_name": "train",
            "data_source": {
                "s3_data_source": {
                    "s3_uri": "s3://my-bucket/data/train/",
                    "s3_data_type": "S3Prefix",
                }
            },
        },
    ],
    wait=True,
    logs=True,
)
```

---

## PyTorch Launcher

```python
# PyTorch REQUIRES py_version and instance_type in image_uris.retrieve()
image_uri = image_uris.retrieve(
    framework="pytorch",
    region=region,
    version="2.1",
    py_version="py310",
    instance_type="ml.m5.xlarge",  # must match Compute.instance_type
    image_scope="training",
)

trainer = ModelTrainer(
    training_image=image_uri,
    role=get_role(),
    source_code=SourceCode(
        source_dir="./training",
        entry_script="train.py",
        requirements="requirements.txt",
    ),
    compute=Compute(
        instance_type="ml.m5.xlarge",   # match instance_type above
        instance_count=1,
        volume_size_in_gb=50,
    ),
    output_data_config=OutputDataConfig(
        s3_output_path="s3://my-bucket/pytorch/output/",
    ),
    hyperparameters={
        "epochs": 20,
        "batch-size": 64,
        "lr": 0.001,
        "hidden-dim": 256,
        "num-layers": 3,
    },
    base_job_name="pytorch-training",
    sagemaker_session=Session(),
)

trainer.train(
    input_data_config=[
        {
            "channel_name": "train",
            "data_source": {
                "s3_data_source": {
                    "s3_uri": "s3://my-bucket/data/train/",
                    "s3_data_type": "S3Prefix",
                }
            },
        },
    ],
    wait=True,
    logs=True,
)
```

---

## Spot Instances + Checkpointing Pattern

Spot training is configured on `Compute.enable_managed_spot_training`. Always pair with
`CheckpointConfig` so training can resume after spot interruptions.

```python
from sagemaker.core.training.configs import Compute, StoppingCondition, CheckpointConfig

trainer = ModelTrainer(
    # ... other params ...
    compute=Compute(
        instance_type="ml.m5.xlarge",
        instance_count=1,
        volume_size_in_gb=30,
        enable_managed_spot_training=True,  # enables Spot
    ),
    stopping_condition=StoppingCondition(
        max_runtime_in_seconds=7200,
        max_wait_time_in_seconds=10800,  # must be >= max_runtime; required for Spot
    ),
    checkpoint_config=CheckpointConfig(
        s3_uri="s3://my-bucket/checkpoints/my-job/",
        local_path="/opt/ml/checkpoints",  # default
    ),
)
```

In your training script, save/load checkpoints from `/opt/ml/checkpoints/`:

```python
import os

CHECKPOINT_DIR = os.environ.get("SM_HP_CHECKPOINT_DIR", "/opt/ml/checkpoints")

# Save checkpoint (e.g., at end of each epoch)
def save_checkpoint(model, optimizer, epoch, checkpoint_dir):
    os.makedirs(checkpoint_dir, exist_ok=True)
    path = os.path.join(checkpoint_dir, f"checkpoint-{epoch}.pt")
    torch.save({"epoch": epoch, "model": model.state_dict(), "optimizer": optimizer.state_dict()}, path)

# Load latest checkpoint (e.g., at training start for spot resume)
def load_latest_checkpoint(checkpoint_dir):
    if not os.path.exists(checkpoint_dir):
        return None
    checkpoints = sorted([f for f in os.listdir(checkpoint_dir) if f.startswith("checkpoint-")])
    if not checkpoints:
        return None
    return torch.load(os.path.join(checkpoint_dir, checkpoints[-1]), weights_only=True)
```

---

## Multiple Input Channels

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
        {
            "channel_name": "validation",
            "data_source": {
                "s3_data_source": {
                    "s3_uri": "s3://bucket/data/validation/",
                    "s3_data_type": "S3Prefix",
                }
            },
        },
        {
            "channel_name": "test",
            "data_source": {
                "s3_data_source": {
                    "s3_uri": "s3://bucket/data/test/",
                    "s3_data_type": "S3Prefix",
                }
            },
        },
    ],
    wait=True,
    logs=True,
)
```

In the training script, access each channel:
```python
train_dir = os.environ.get("SM_CHANNEL_TRAIN", "/opt/ml/input/data/train")
val_dir   = os.environ.get("SM_CHANNEL_VALIDATION", "/opt/ml/input/data/validation")
test_dir  = os.environ.get("SM_CHANNEL_TEST", "/opt/ml/input/data/test")
```

---

## Local Mode (debug before cloud)

Run training locally in a container before submitting to SageMaker. Requires Docker/Finch running.

```python
from sagemaker.train.model_trainer import ModelTrainer, Mode

trainer = ModelTrainer(
    training_mode=Mode.LOCAL_CONTAINER,  # runs locally, no cloud charges
    training_image=image_uri,
    role=get_role(),
    source_code=SourceCode(
        source_dir="./training",
        entry_script="train.py",
        requirements="requirements.txt",
    ),
    hyperparameters={"n-estimators": 10, "max-depth": 3},  # small values for fast iteration
    sagemaker_session=Session(),
)

trainer.train(
    input_data_config=[
        {
            "channel_name": "train",
            "data_source": {
                "s3_data_source": {
                    "s3_uri": "s3://my-bucket/data/train/",
                    "s3_data_type": "S3Prefix",
                }
            },
        },
    ],
    wait=True,
    logs=True,
)
```

> Switch to `Mode.SAGEMAKER_TRAINING_JOB` (default) when ready for full training.

---

## Hyperparameter Tuning (HPO)

```python
from sagemaker.train.tuner import (
    HyperparameterTuner,
    ContinuousParameter,
    IntegerParameter,
    CategoricalParameter,
)

# trainer = ModelTrainer(...) — defined as usual

tuner = HyperparameterTuner(
    model_trainer=trainer,
    objective_metric_name="validation_auc",
    hyperparameter_ranges={
        "learning-rate": ContinuousParameter(0.001, 0.3),
        "max-depth": IntegerParameter(3, 10),
        "n-estimators": IntegerParameter(50, 500),
        "subsample": ContinuousParameter(0.5, 1.0),
    },
    metric_definitions=[
        {"Name": "validation_auc", "Regex": r'"metric":\s*"validation_auc",\s*"value":\s*([0-9.]+)'},
    ],
    objective_type="Maximize",
    max_jobs=20,
    max_parallel_jobs=4,
    strategy="Bayesian",
    early_stopping_type="Auto",
)

tuner.fit(
    inputs={
        "train": "s3://my-bucket/data/train/",
        "validation": "s3://my-bucket/data/validation/",
    },
    wait=True,
    logs=True,
)

# Get best training job
print(f"Best job: {tuner.best_training_job()}")
print(f"Best objective: {tuner.best_objective_value()}")
```

> **Metric regex must match** the `log_metric()` output format in your training script.
> The JSON format `{"metric": "validation_auc", "value": 0.95}` requires the regex above.

---

## Distributed Training (PyTorch Torchrun)

```python
from sagemaker.train.distributed import Torchrun

trainer = ModelTrainer(
    training_image=image_uri,
    role=get_role(),
    source_code=SourceCode(
        source_dir="./training",
        entry_script="train.py",
        requirements="requirements.txt",
    ),
    compute=Compute(
        instance_type="ml.p3.8xlarge",   # multi-GPU instance
        instance_count=2,                 # multi-node
        volume_size_in_gb=100,
    ),
    distributed=Torchrun(
        process_count_per_node=4,  # typically = number of GPUs per instance
    ),
    output_data_config=OutputDataConfig(s3_output_path="s3://my-bucket/output/"),
    hyperparameters={"epochs": 10, "batch-size": 256, "lr": 0.001},
    sagemaker_session=Session(),
)
```

In your training script, use PyTorch DDP:
```python
import torch.distributed as dist
from torch.nn.parallel import DistributedDataParallel as DDP

dist.init_process_group(backend="nccl")
local_rank = int(os.environ.get("LOCAL_RANK", 0))
device = torch.device(f"cuda:{local_rank}")
model = DDP(model.to(device), device_ids=[local_rank])
```

---

## Processing Jobs (standalone data preprocessing)

```python
from sagemaker.core.processing import ScriptProcessor, ProcessingInput, ProcessingOutput
from sagemaker.core.helper.session_helper import Session

processor = ScriptProcessor(
    image_uri=image_uri,
    role=role_arn,
    command=["python3"],
    instance_type="ml.m5.xlarge",
    instance_count=1,
    sagemaker_session=Session(),
)

processor.run(
    code="preprocessing.py",
    inputs=[
        ProcessingInput(source="s3://my-bucket/raw-data/", destination="/opt/ml/processing/input"),
    ],
    outputs=[
        ProcessingOutput(output_name="train", source="/opt/ml/processing/train",
                         destination="s3://my-bucket/processed/train/"),
        ProcessingOutput(output_name="validation", source="/opt/ml/processing/validation",
                         destination="s3://my-bucket/processed/validation/"),
    ],
    wait=True,
    logs=True,
)
```

Example `preprocessing.py`:
```python
import os
import pandas as pd
from sklearn.model_selection import train_test_split

input_dir = "/opt/ml/processing/input"
df = pd.concat([pd.read_csv(os.path.join(input_dir, f)) for f in os.listdir(input_dir) if f.endswith(".csv")])

# Your preprocessing: feature engineering, encoding, scaling, etc.
train_df, val_df = train_test_split(df, test_size=0.2, random_state=42)

os.makedirs("/opt/ml/processing/train", exist_ok=True)
os.makedirs("/opt/ml/processing/validation", exist_ok=True)
train_df.to_csv("/opt/ml/processing/train/train.csv", index=False)
val_df.to_csv("/opt/ml/processing/validation/validation.csv", index=False)
```

---

## Console Monitoring URL

```python
import boto3
region = boto3.session.Session().region_name
job_name = trainer.latest_training_job.name
print(f"https://{region}.console.aws.amazon.com/sagemaker/home?region={region}#/jobs/{job_name}")
```
