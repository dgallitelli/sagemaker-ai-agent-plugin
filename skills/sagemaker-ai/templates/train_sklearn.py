"""
Scikit-learn training script for SageMaker.

SageMaker passes hyperparameters as strings — all numeric args MUST declare type=int/float.
Model MUST be saved to /opt/ml/model/ — SageMaker archives that directory automatically.
Data MUST be read from SM_CHANNEL_* env vars (set automatically by SageMaker).
"""
import argparse
import json
import os

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, roc_auc_score


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

    # Hyperparameters — SageMaker passes them as strings; type= handles conversion
    parser.add_argument("--n-estimators", type=int, default=100)
    parser.add_argument("--max-depth", type=str, default="None")  # "None" = unlimited
    parser.add_argument("--min-samples-split", type=int, default=2)
    parser.add_argument("--min-samples-leaf", type=int, default=1)
    parser.add_argument("--max-features", type=str, default="sqrt")
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--n-jobs", type=int, default=-1)
    parser.add_argument("--target-column", type=str, default="label")

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
def log_metric(name, value):
    print(json.dumps({"metric": name, "value": float(value)}))


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------
def train(args):
    print(f"Loading training data from {TRAIN_DIR}")
    X_train, y_train = load_data(TRAIN_DIR, args.target_column)
    print(f"Training samples: {len(y_train)}, features: {X_train.shape[1]}")

    # Handle max_depth: SageMaker passes all HPs as strings, so we accept str
    # and convert. "None" or "none" → None (unlimited depth).
    max_depth = None if args.max_depth.lower() == "none" else int(args.max_depth)

    model = RandomForestClassifier(
        n_estimators=args.n_estimators,
        max_depth=max_depth,
        min_samples_split=args.min_samples_split,
        min_samples_leaf=args.min_samples_leaf,
        max_features=args.max_features,
        random_state=args.random_state,
        n_jobs=args.n_jobs,
    )

    print("Fitting model...")
    model.fit(X_train, y_train)

    # Training metrics
    train_preds = model.predict(X_train)
    train_acc = accuracy_score(y_train, train_preds)
    log_metric("train_accuracy", train_acc)

    # Validation metrics if available
    if os.path.exists(VALIDATION_DIR) and os.listdir(VALIDATION_DIR):
        print(f"Loading validation data from {VALIDATION_DIR}")
        X_val, y_val = load_data(VALIDATION_DIR, args.target_column)
        val_preds = model.predict(X_val)
        val_acc = accuracy_score(y_val, val_preds)
        log_metric("validation_accuracy", val_acc)

        # AUC if binary classification
        n_classes = len(np.unique(y_train))
        if n_classes == 2:
            val_proba = model.predict_proba(X_val)[:, 1]
            val_auc = roc_auc_score(y_val, val_proba)
            log_metric("validation_auc", val_auc)

    # Save model — MUST be /opt/ml/model/
    os.makedirs(MODEL_DIR, exist_ok=True)
    model_path = os.path.join(MODEL_DIR, "model.joblib")
    joblib.dump(model, model_path)
    print(f"Model saved to {model_path}")

    return model


# ---------------------------------------------------------------------------
# Inference hooks (optional — used when this image serves the endpoint too)
# ---------------------------------------------------------------------------
def model_fn(model_dir):
    """Load model for inference. Called once at endpoint startup."""
    model_path = os.path.join(model_dir, "model.joblib")
    return joblib.load(model_path)


def predict_fn(input_data, model):
    """Run prediction. input_data comes from input_fn."""
    return model.predict(input_data)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    args = parse_args()
    train(args)
