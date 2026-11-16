"""LSTM regressor for Remaining Useful Life and its deep-ensemble wrapper."""
from __future__ import annotations

import copy

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset


class RULLSTM(nn.Module):
    def __init__(self, n_features: int, hidden: int = 64, layers: int = 2, dropout: float = 0.2):
        super().__init__()
        self.config = dict(n_features=n_features, hidden=hidden, layers=layers, dropout=dropout)
        self.lstm = nn.LSTM(n_features, hidden, num_layers=layers, batch_first=True,
                            dropout=dropout if layers > 1 else 0.0)
        self.head = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(hidden, 32),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(32, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:  # (B, T, F) -> (B,)
        out, _ = self.lstm(x)
        return self.head(out[:, -1]).squeeze(-1)


def train_model(
    X_train: np.ndarray, y_train: np.ndarray, X_val: np.ndarray, y_val: np.ndarray,
    epochs: int = 120, batch_size: int = 128, lr: float = 1e-3, patience: int = 20,
    seed: int = 42, verbose: bool = True,
) -> tuple[RULLSTM, list[dict]]:
    torch.manual_seed(seed)
    np.random.seed(seed)
    model = RULLSTM(X_train.shape[-1])
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    sched = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, factor=0.5, patience=4)
    loss_fn = nn.MSELoss()
    loader = DataLoader(
        TensorDataset(torch.from_numpy(X_train), torch.from_numpy(y_train)),
        batch_size=batch_size, shuffle=True,
    )
    Xv, yv = torch.from_numpy(X_val), torch.from_numpy(y_val)
    best, best_state, wait, history = float("inf"), None, 0, []
    for epoch in range(1, epochs + 1):
        model.train()
        total = 0.0
        for xb, yb in loader:
            opt.zero_grad()
            loss = loss_fn(model(xb), yb)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            total += loss.item() * len(xb)
        model.eval()
        with torch.no_grad():
            val_rmse = torch.sqrt(loss_fn(model(Xv), yv)).item()
        train_rmse = (total / len(loader.dataset)) ** 0.5
        sched.step(val_rmse)
        history.append({"epoch": epoch, "train_rmse": train_rmse, "val_rmse": val_rmse})
        if verbose:
            print(f"epoch {epoch:3d}  train RMSE {train_rmse:6.2f}  val RMSE {val_rmse:6.2f}")
        if val_rmse < best - 1e-3:
            best, best_state, wait = val_rmse, copy.deepcopy(model.state_dict()), 0
        else:
            wait += 1
            if wait >= patience:
                break
    model.load_state_dict(best_state)
    model.eval()
    return model, history


@torch.no_grad()
def predict(model: RULLSTM, X: np.ndarray, batch: int = 4096) -> np.ndarray:
    model.eval()
    out = [model(torch.from_numpy(X[i:i + batch])).numpy() for i in range(0, len(X), batch)]
    return np.clip(np.concatenate(out), 0, None)


class Ensemble(nn.Module):
    """Average of several networks (deep ensemble). Differentiable -> SHAP-able."""

    def __init__(self, members: list[nn.Module]):
        super().__init__()
        self.members = nn.ModuleList(members)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return torch.stack([m(x) for m in self.members]).mean(0)


@torch.no_grad()
def predict_members(models: list[nn.Module], X: np.ndarray) -> np.ndarray:
    """(n_models, n_samples) predictions, used for the ensemble spread."""
    return np.stack([predict(m, X) for m in models])
