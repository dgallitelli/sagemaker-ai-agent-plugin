# SageMaker SDK v3 — Inference Patterns

Inference hook implementations and endpoint deployment patterns for XGBoost, SKLearn, and PyTorch.

---

## The Four Inference Hooks

SageMaker calls these in sequence for every prediction request:

```
Request bytes → input_fn → predict_fn → output_fn → Response bytes
                                ↑
                           model_fn (called once at startup)
```

| Hook | Required | Default behavior if omitted |
|------|----------|-----------------------------|
| `model_fn(model_dir)` | YES | None — always implement |
| `input_fn(body, content_type)` | No | Deserializes JSON or CSV automatically |
| `predict_fn(data, model)` | YES | None — always implement |
| `output_fn(prediction, accept)` | No | Serializes to JSON automatically |

---

## XGBoost Inference Hooks

```python
import io
import json
import os

import numpy as np
import xgboost as xgb


def model_fn(model_dir):
    """Load XGBoost model. Called once at container startup."""
    model_path = os.path.join(model_dir, "model.ubj")
    model = xgb.Booster()
    model.load_model(model_path)
    return model


def input_fn(request_body, content_type):
    """Deserialize request body into numpy array."""
    if isinstance(request_body, bytes):
        request_body = request_body.decode("utf-8")
    if content_type == "text/csv":
        data = np.loadtxt(io.StringIO(request_body), delimiter=",")
        if data.ndim == 1:
            data = data.reshape(1, -1)
        return data
    elif content_type == "application/json":
        payload = json.loads(request_body)
        return np.array(payload["instances"])
    raise ValueError(f"Unsupported content type: {content_type}")


def predict_fn(input_data, model):
    """Run XGBoost prediction."""
    dmatrix = xgb.DMatrix(input_data)
    return model.predict(dmatrix)


def output_fn(prediction, accept):
    """Serialize prediction to response."""
    if accept in ("application/json", "*/*"):
        return json.dumps({"predictions": prediction.tolist()}), "application/json"
    elif accept == "text/csv":
        return ",".join(str(p) for p in prediction.tolist()), "text/csv"
    raise ValueError(f"Unsupported accept type: {accept}")
```

---

## SKLearn Inference Hooks

```python
import io
import json
import os

import joblib
import numpy as np


def model_fn(model_dir):
    """Load SKLearn model. Called once at container startup."""
    model_path = os.path.join(model_dir, "model.joblib")
    return joblib.load(model_path)


def input_fn(request_body, content_type):
    """Deserialize request body into numpy array."""
    if isinstance(request_body, bytes):
        request_body = request_body.decode("utf-8")
    if content_type == "text/csv":
        data = np.loadtxt(io.StringIO(request_body), delimiter=",")
        if data.ndim == 1:
            data = data.reshape(1, -1)
        return data
    elif content_type == "application/json":
        payload = json.loads(request_body)
        return np.array(payload["instances"])
    raise ValueError(f"Unsupported content type: {content_type}")


def predict_fn(input_data, model):
    """Run SKLearn prediction. Returns class labels."""
    return model.predict(input_data)


def output_fn(prediction, accept):
    """Serialize prediction."""
    if accept in ("application/json", "*/*"):
        return json.dumps({"predictions": prediction.tolist()}), "application/json"
    elif accept == "text/csv":
        return ",".join(str(p) for p in prediction.tolist()), "text/csv"
    raise ValueError(f"Unsupported accept type: {accept}")
```

> **SKLearn variant — return probabilities instead of labels:**
> ```python
> def predict_fn(input_data, model):
>     return model.predict_proba(input_data)
> ```

---

## PyTorch Inference Hooks

```python
import json
import os

import numpy as np
import torch
import torch.nn as nn


class MLP(nn.Module):
    """Copy this class from train_pytorch.py — must match training architecture."""
    def __init__(self, input_dim, hidden_dim, num_layers, dropout):
        super().__init__()
        layers = []
        in_dim = input_dim
        for _ in range(num_layers):
            layers.extend([nn.Linear(in_dim, hidden_dim), nn.ReLU(), nn.Dropout(dropout)])
            in_dim = hidden_dim
        layers.append(nn.Linear(hidden_dim, 1))
        self.net = nn.Sequential(*layers)

    def forward(self, x):
        return self.net(x).squeeze(-1)


def model_fn(model_dir):
    """Load PyTorch model. Called once at container startup."""
    config_path = os.path.join(model_dir, "model_config.json")
    with open(config_path) as f:
        config = json.load(f)
    model = MLP(**config)
    model_path = os.path.join(model_dir, "model.pt")
    model.load_state_dict(torch.load(model_path, map_location="cpu", weights_only=True))
    model.eval()
    return model


def input_fn(request_body, content_type):
    """Deserialize request body into numpy array."""
    if isinstance(request_body, bytes):
        request_body = request_body.decode("utf-8")
    if content_type == "text/csv":
        import io
        data = np.loadtxt(io.StringIO(request_body), delimiter=",")
        if data.ndim == 1:
            data = data.reshape(1, -1)
        return data.astype(np.float32)
    elif content_type == "application/json":
        payload = json.loads(request_body)
        return np.array(payload["instances"], dtype=np.float32)
    raise ValueError(f"Unsupported content type: {content_type}")


def predict_fn(input_data, model):
    """Run PyTorch inference. Returns probabilities."""
    with torch.no_grad():
        x = torch.tensor(input_data, dtype=torch.float32)
        logits = model(x)
        probs = torch.sigmoid(logits)
    return probs.numpy()


def output_fn(prediction, accept):
    """Serialize prediction."""
    if accept in ("application/json", "*/*"):
        return json.dumps({"predictions": prediction.tolist()}), "application/json"
    elif accept == "text/csv":
        return ",".join(str(p) for p in prediction.tolist()), "text/csv"
    raise ValueError(f"Unsupported accept type: {accept}")
```

---

## JumpStart Model Deployment (pretrained models)

V3 replaces `JumpStartModel` with `ModelBuilder` accepting a JumpStart model ID:

```python
from sagemaker.serve import ModelBuilder
from sagemaker.core.helper.session_helper import Session
from sagemaker.core.jumpstart.notebook_utils import list_jumpstart_models

# Discover available models
models = list_jumpstart_models(filter_value="task == classification")
print(models[:10])

# Deploy a JumpStart model
builder = ModelBuilder(
    model="huggingface-text2text-flan-t5-base",  # JumpStart model ID
    role_arn=role_arn,
    sagemaker_session=Session(),
    instance_type="ml.g5.xlarge",
)

model = builder.build()
predictor = model.deploy(
    initial_instance_count=1,
    instance_type="ml.g5.xlarge",
)

# Clean up
predictor.delete_endpoint()
```

> **V2 → V3 change**: `JumpStartModel` class no longer exists. Use `ModelBuilder(model="<model-id>")` instead.

---

## Real-Time Endpoint Deployment — ModelBuilder (V3 preferred)

```python
import os
from sagemaker.serve import ModelBuilder, InferenceSpec
from sagemaker.core.helper.session_helper import Session


class MyInferenceSpec(InferenceSpec):
    """Implement load + invoke for your framework."""

    def load(self, model_dir: str):
        import joblib  # or xgboost, torch, etc.
        return joblib.load(os.path.join(model_dir, "model.joblib"))

    def invoke(self, input_object, model):
        return model.predict(input_object)


# Build from training job output
job_name = trainer.latest_training_job.name

builder = ModelBuilder(
    model_path=f"s3://bucket/output/{job_name}/output/model.tar.gz",
    inference_spec=MyInferenceSpec(),
    role_arn=role_arn,
    image_uri=image_uri,
    sagemaker_session=Session(),
    instance_type="ml.m5.large",
)

model = builder.build()
predictor = model.deploy(
    initial_instance_count=1,
    instance_type="ml.m5.large",
    endpoint_name="my-endpoint",  # optional
)

# Invoke
import numpy as np
sample = np.array([[1.2, 3.4, 5.6]])
csv_payload = ",".join(str(v) for v in sample.flatten())
response = predictor.predict(csv_payload, initial_args={"ContentType": "text/csv"})
print(response)

# Clean up (important!)
predictor.delete_endpoint()
```

---

## Real-Time Endpoint Deployment — Legacy Model Class

Still works for simple cases with built-in framework containers + inference hooks:

```python
import boto3
from sagemaker.core.resources import Model
from sagemaker.core.helper.session_helper import Session

# Get training job artifact
job_name = trainer.latest_training_job.name
sm_client = boto3.client("sagemaker")
job_info = sm_client.describe_training_job(TrainingJobName=job_name)
model_uri = job_info["ModelArtifacts"]["S3ModelArtifacts"]

model = Model(
    image_uri=image_uri,
    model_data=model_uri,
    role=role_arn,
    sagemaker_session=Session(),
)

predictor = model.deploy(
    initial_instance_count=1,
    instance_type="ml.m5.large",
    endpoint_name="my-endpoint",
)

# Clean up
predictor.delete_endpoint()
```

---

## Batch Transform (no persistent endpoint)

```python
from sagemaker.core.transformer import Transformer
from sagemaker.core.helper.session_helper import Session

transformer = Transformer(
    model_name="my-model-name",
    instance_count=1,
    instance_type="ml.m5.xlarge",
    output_path="s3://bucket/batch-output/",
    sagemaker_session=Session(),
)

transformer.transform(
    data="s3://bucket/batch-input/",
    data_type="S3Prefix",
    content_type="text/csv",
    split_type="Line",
    wait=True,
)
print(f"Batch output: s3://bucket/batch-output/")
```

---

## Invoking an Endpoint Directly via boto3

```python
import boto3
import json

runtime = boto3.client("sagemaker-runtime")

response = runtime.invoke_endpoint(
    EndpointName="my-endpoint",
    ContentType="application/json",
    Accept="application/json",
    Body=json.dumps({"instances": [[1.2, 3.4, 5.6]]}),
)

result = json.loads(response["Body"].read())
print(result["predictions"])
```
