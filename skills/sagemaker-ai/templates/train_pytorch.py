"""
PyTorch training script for SageMaker (tabular data / MLP).

SageMaker passes hyperparameters as strings — all numeric args MUST declare type=int/float.
Model MUST be saved to /opt/ml/model/ — SageMaker archives that directory automatically.
Data MUST be read from SM_CHANNEL_* env vars (set automatically by SageMaker).
"""
import argparse
import json
import os

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset


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
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--hidden-dim", type=int, default=128)
    parser.add_argument("--num-layers", type=int, default=2)
    parser.add_argument("--dropout", type=float, default=0.2)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--target-column", type=str, default="label")

    return parser.parse_args()


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------
class TabularDataset(Dataset):
    """Simple Dataset for tabular CSV data."""

    def __init__(self, directory, target_column):
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

        self.X = torch.tensor(
            df.drop(columns=[target_column]).values, dtype=torch.float32
        )
        self.y = torch.tensor(df[target_column].values, dtype=torch.float32)

    def __len__(self):
        return len(self.y)

    def __getitem__(self, idx):
        return self.X[idx], self.y[idx]


# ---------------------------------------------------------------------------
# Model (MLP)
# ---------------------------------------------------------------------------
class MLP(nn.Module):
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


# ---------------------------------------------------------------------------
# Metric logging (CloudWatch-parseable)
# ---------------------------------------------------------------------------
def log_metric(name, value, step=None):
    record = {"metric": name, "value": float(value)}
    if step is not None:
        record["step"] = step
    print(json.dumps(record))


# ---------------------------------------------------------------------------
# Training loop
# ---------------------------------------------------------------------------
def train(args):
    torch.manual_seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    print(f"Loading training data from {TRAIN_DIR}")
    train_dataset = TabularDataset(TRAIN_DIR, args.target_column)
    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True)
    print(f"Training samples: {len(train_dataset)}")

    val_loader = None
    if os.path.exists(VALIDATION_DIR) and os.listdir(VALIDATION_DIR):
        print(f"Loading validation data from {VALIDATION_DIR}")
        val_dataset = TabularDataset(VALIDATION_DIR, args.target_column)
        val_loader = DataLoader(val_dataset, batch_size=args.batch_size, shuffle=False)
        print(f"Validation samples: {len(val_dataset)}")

    input_dim = train_dataset.X.shape[1]
    model = MLP(
        input_dim=input_dim,
        hidden_dim=args.hidden_dim,
        num_layers=args.num_layers,
        dropout=args.dropout,
    ).to(device)

    criterion = nn.BCEWithLogitsLoss()
    optimizer = torch.optim.Adam(
        model.parameters(), lr=args.lr, weight_decay=args.weight_decay
    )

    for epoch in range(1, args.epochs + 1):
        # Train
        model.train()
        total_loss = 0.0
        for X_batch, y_batch in train_loader:
            X_batch, y_batch = X_batch.to(device), y_batch.to(device)
            optimizer.zero_grad()
            logits = model(X_batch)
            loss = criterion(logits, y_batch)
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * len(y_batch)

        avg_train_loss = total_loss / len(train_dataset)
        log_metric("train_loss", avg_train_loss, step=epoch)

        # Validate
        if val_loader is not None:
            model.eval()
            val_loss = 0.0
            with torch.no_grad():
                for X_batch, y_batch in val_loader:
                    X_batch, y_batch = X_batch.to(device), y_batch.to(device)
                    logits = model(X_batch)
                    loss = criterion(logits, y_batch)
                    val_loss += loss.item() * len(y_batch)
            avg_val_loss = val_loss / len(val_dataset)
            log_metric("validation_loss", avg_val_loss, step=epoch)
            print(
                f"Epoch {epoch}/{args.epochs} — "
                f"train_loss: {avg_train_loss:.4f}, val_loss: {avg_val_loss:.4f}"
            )
        else:
            print(f"Epoch {epoch}/{args.epochs} — train_loss: {avg_train_loss:.4f}")

    # Save model — MUST be /opt/ml/model/
    os.makedirs(MODEL_DIR, exist_ok=True)

    # Save state dict
    model_path = os.path.join(MODEL_DIR, "model.pt")
    torch.save(model.state_dict(), model_path)
    print(f"Model weights saved to {model_path}")

    # Save config (needed to reconstruct model architecture at inference time)
    config_path = os.path.join(MODEL_DIR, "model_config.json")
    config = {
        "input_dim": input_dim,
        "hidden_dim": args.hidden_dim,
        "num_layers": args.num_layers,
        "dropout": args.dropout,
    }
    with open(config_path, "w") as f:
        json.dump(config, f)
    print(f"Model config saved to {config_path}")

    return model


# ---------------------------------------------------------------------------
# Inference hooks (optional — used when this image serves the endpoint too)
# ---------------------------------------------------------------------------
def model_fn(model_dir):
    """Load model for inference. Called once at endpoint startup."""
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


def predict_fn(input_data, model):
    """Run prediction. input_data comes from input_fn (numpy array)."""
    with torch.no_grad():
        x = torch.tensor(input_data, dtype=torch.float32)
        logits = model(x)
        probs = torch.sigmoid(logits)
    return probs.numpy()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    args = parse_args()
    train(args)
