"""
XGBoost training script for SageMaker.

SageMaker passes hyperparameters as strings — all numeric args MUST declare type=int/float.
Model MUST be saved to /opt/ml/model/ — SageMaker archives that directory automatically.
Data MUST be read from SM_CHANNEL_* env vars (set automatically by SageMaker).
"""
import argparse
import json
import os

import numpy as np
import pandas as pd
import xgboost as xgb


# ---------------------------------------------------------------------------
# Paths — use env vars with fallbacks for local testing
# ---------------------------------------------------------------------------
TRAIN_DIR = os.environ.get("SM_CHANNEL_TRAIN", "/opt/ml/input/data/train")
VALIDATION_DIR = os.environ.get("SM_CHANNEL_VALIDATION", "/opt/ml/input/data/validation")
MODEL_DIR = os.environ.get("SM_MODEL_DIR", "/opt/ml/model")


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
def parse_args():
    parser = argparse.ArgumentParser()

    # Hyperparameters — all must match what launcher.py sends
    # SageMaker passes them as strings; type= handles conversion
    parser.add_argument("--n-estimators", type=int, default=100)
    parser.add_argument("--max-depth", type=int, default=5)
    parser.add_argument("--learning-rate", type=float, default=0.1)
    parser.add_argument("--subsample", type=float, default=0.8)
    parser.add_argument("--colsample-bytree", type=float, default=0.8)
    parser.add_argument("--objective", type=str, default="binary:logistic")
    parser.add_argument("--eval-metric", type=str, default="auc")
    parser.add_argument("--target-column", type=str, default="label")
    parser.add_argument("--seed", type=int, default=42)

    return parser.parse_args()


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_data(directory, target_column):
    """Load all CSV or Parquet files from a directory, return X and y arrays."""
    csv_files = [f for f in os.listdir(directory) if f.endswith(".csv")]
    parquet_files = [f for f in os.listdir(directory) if f.endswith(".parquet")]

    if parquet_files:
        dfs = [pd.read_parquet(os.path.join(directory, f)) for f in parquet_files]
    elif csv_files:
        dfs = [pd.read_csv(os.path.join(directory, f)) for f in csv_files]
    else:
        raise FileNotFoundError(f"No CSV or Parquet files found in {directory}")

    df = pd.concat(dfs, ignore_index=True)

    if target_column not in df.columns:
        raise ValueError(
            f"Target column '{target_column}' not found. "
            f"Available: {list(df.columns)}"
        )

    X = df.drop(columns=[target_column]).values
    y = df[target_column].values
    return X, y


# ---------------------------------------------------------------------------
# Metric logging (CloudWatch-parseable)
# ---------------------------------------------------------------------------
def log_metric(name, value, step=None):
    record = {"metric": name, "value": float(value)}
    if step is not None:
        record["step"] = step
    print(json.dumps(record))


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------
def train(args):
    print(f"Loading training data from {TRAIN_DIR}")
    X_train, y_train = load_data(TRAIN_DIR, args.target_column)
    dtrain = xgb.DMatrix(X_train, label=y_train)
    print(f"Training samples: {len(y_train)}")

    evals = [(dtrain, "train")]

    # Load validation data if available
    if os.path.exists(VALIDATION_DIR) and os.listdir(VALIDATION_DIR):
        print(f"Loading validation data from {VALIDATION_DIR}")
        X_val, y_val = load_data(VALIDATION_DIR, args.target_column)
        dval = xgb.DMatrix(X_val, label=y_val)
        evals.append((dval, "validation"))
        print(f"Validation samples: {len(y_val)}")

    params = {
        "max_depth": args.max_depth,
        "learning_rate": args.learning_rate,
        "subsample": args.subsample,
        "colsample_bytree": args.colsample_bytree,
        "objective": args.objective,
        "eval_metric": args.eval_metric,
        "seed": args.seed,
    }

    print(f"Training params: {json.dumps(params)}")

    evals_result = {}
    model = xgb.train(
        params=params,
        dtrain=dtrain,
        num_boost_round=args.n_estimators,
        evals=evals,
        evals_result=evals_result,
        verbose_eval=10,
    )

    # Log final metrics in CloudWatch-parseable format
    for dataset_name, metrics in evals_result.items():
        for metric_name, values in metrics.items():
            log_metric(f"{dataset_name}_{metric_name}", values[-1])

    # Save model — MUST be /opt/ml/model/
    os.makedirs(MODEL_DIR, exist_ok=True)
    model_path = os.path.join(MODEL_DIR, "model.ubj")
    model.save_model(model_path)
    print(f"Model saved to {model_path}")

    return model


# ---------------------------------------------------------------------------
# Inference hooks (optional — used when this image serves the endpoint too)
# ---------------------------------------------------------------------------
def model_fn(model_dir):
    """Load model for inference. Called once at endpoint startup."""
    model_path = os.path.join(model_dir, "model.ubj")
    model = xgb.Booster()
    model.load_model(model_path)
    return model


def predict_fn(input_data, model):
    """Run prediction. input_data comes from input_fn."""
    dmatrix = xgb.DMatrix(input_data)
    return model.predict(dmatrix)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    args = parse_args()
    train(args)
