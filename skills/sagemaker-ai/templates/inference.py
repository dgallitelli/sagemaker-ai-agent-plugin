"""
SageMaker inference script — multi-framework.

Copy the section for your framework into your inference.py.
All four hooks follow the SageMaker Python SDK contract:
  model_fn    → load the model once at startup
  input_fn    → deserialize request bytes into model input
  predict_fn  → run the model
  output_fn   → serialize predictions to response bytes

Only model_fn and predict_fn are required. input_fn and output_fn have
sensible defaults (JSON in/out) but are included here for full control.

Note: request_body may arrive as bytes or str depending on the serving
container version. All input_fn implementations below handle both.
"""

# ===========================================================================
# FRAMEWORK: XGBoost
# ===========================================================================
# Required: pip install xgboost in your inference container
# Model file: model.ubj (saved with model.save_model())

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
    """Deserialize request into a numpy array."""
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
    raise ValueError(f"Unsupported content type: {content_type}. Use text/csv or application/json")


def predict_fn(input_data, model):
    """Run XGBoost inference."""
    dmatrix = xgb.DMatrix(input_data)
    return model.predict(dmatrix)


def output_fn(prediction, accept):
    """Serialize predictions."""
    if accept in ("application/json", "*/*"):
        return json.dumps({"predictions": prediction.tolist()}), "application/json"
    elif accept == "text/csv":
        return ",".join(str(p) for p in prediction.tolist()), "text/csv"
    raise ValueError(f"Unsupported accept type: {accept}")


# ===========================================================================
# FRAMEWORK: SKLearn (Scikit-learn)
# ===========================================================================
# Required: pip install scikit-learn joblib in your inference container
# Model file: model.joblib

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
    """Deserialize request into a numpy array."""
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
    raise ValueError(f"Unsupported content type: {content_type}. Use text/csv or application/json")


def predict_fn(input_data, model):
    """Run SKLearn inference. Returns class labels."""
    return model.predict(input_data)


def output_fn(prediction, accept):
    """Serialize predictions."""
    if accept in ("application/json", "*/*"):
        return json.dumps({"predictions": prediction.tolist()}), "application/json"
    elif accept == "text/csv":
        return ",".join(str(p) for p in prediction.tolist()), "text/csv"
    raise ValueError(f"Unsupported accept type: {accept}")


# ===========================================================================
# FRAMEWORK: PyTorch
# ===========================================================================
# Required: pip install torch in your inference container
# Model files: model.pt (state dict) + model_config.json (architecture params)

import io
import json
import os

import numpy as np
import torch
import torch.nn as nn


class MLP(nn.Module):
    """Must match architecture used in train_pytorch.py."""
    def __init__(self, input_dim, hidden_dim, num_layers, dropout):
        super().__init__()
        layers = []
        in_dim = input_dim
        for _ in range(num_layers):
            layers.extend([
                nn.Linear(in_dim, hidden_dim),
                nn.ReLU(),
                nn.Dropout(dropout),
            ])
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

    model = MLP(
        input_dim=config["input_dim"],
        hidden_dim=config["hidden_dim"],
        num_layers=config["num_layers"],
        dropout=config["dropout"],
    )
    model_path = os.path.join(model_dir, "model.pt")
    model.load_state_dict(torch.load(model_path, map_location="cpu", weights_only=True))
    model.eval()
    return model


def input_fn(request_body, content_type):
    """Deserialize request into a numpy array."""
    if isinstance(request_body, bytes):
        request_body = request_body.decode("utf-8")
    if content_type == "text/csv":
        data = np.loadtxt(io.StringIO(request_body), delimiter=",")
        if data.ndim == 1:
            data = data.reshape(1, -1)
        return data.astype(np.float32)
    elif content_type == "application/json":
        payload = json.loads(request_body)
        return np.array(payload["instances"], dtype=np.float32)
    raise ValueError(f"Unsupported content type: {content_type}. Use text/csv or application/json")


def predict_fn(input_data, model):
    """Run PyTorch inference. Returns probabilities."""
    with torch.no_grad():
        x = torch.tensor(input_data, dtype=torch.float32)
        logits = model(x)
        probs = torch.sigmoid(logits)
    return probs.numpy()


def output_fn(prediction, accept):
    """Serialize predictions."""
    if accept in ("application/json", "*/*"):
        return json.dumps({"predictions": prediction.tolist()}), "application/json"
    elif accept == "text/csv":
        return ",".join(str(p) for p in prediction.tolist()), "text/csv"
    raise ValueError(f"Unsupported accept type: {accept}")
