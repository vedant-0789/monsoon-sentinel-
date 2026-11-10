"""Step 11: photo verification - does a citizen's photo show flooding?

Transfer learning on Flood10k (10,419 social-media / web photos, CC BY-NC 4.0):
  1. MobileNetV3-Small pre-trained on ImageNet turns every photo into a 576-d feature vector.
  2. Classical heads are compared on those features (logistic regression, linear SVM, KNN,
     random forest) against a no-deep-learning baseline (colour histograms + LR).
  3. The best head is folded into the network and exported to ONNX (~6 MB): the same
     model runs in the browser (instant feedback) and on the server (authoritative score).

Usage:  python scripts/train_photo_verifier.py
Outputs: models/photo_verifier.onnx, web/public/models/photo_verifier.onnx, reports/photo/*
"""

import json
import shutil
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torchvision
from PIL import Image
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import LinearSVC
from torch import nn

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "flood10k"
OUT = ROOT / "reports" / "photo"
SEED = 42
IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
MEAN = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)
STD = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)


def extract():
    ex = RAW / "extracted"
    if not ex.exists():
        with zipfile.ZipFile(RAW / "Flood10k.zip") as z:
            for m in z.infolist():  # guard against path traversal; skip macOS resource forks
                if m.filename.startswith("__MACOSX"):
                    continue
                target = (ex / m.filename).resolve()
                if not str(target).startswith(str(ex.resolve())):
                    continue
                z.extract(m, ex)
    return ex


def index_images(ex: Path) -> pd.DataFrame:
    rows = []
    for p in ex.rglob("*"):
        if p.suffix.lower() not in IMG_EXT:
            continue
        parts = [x.lower() for x in p.relative_to(ex).parts[:-1]]
        if any(x.startswith("__macosx") for x in parts) or p.name.startswith("._"):
            continue
        joined = "/".join(parts)
        if "non" in joined or "normal" in joined:
            label = 0
        elif "flood" in joined:
            label = 1
        else:
            continue
        rows.append({"path": str(p), "label": label, "group": joined})
    return pd.DataFrame(rows)


class Backbone(nn.Module):
    """ImageNet MobileNetV3-Small -> 576-d pooled features; normalisation built in (input 0-1 RGB)."""

    def __init__(self):
        super().__init__()
        m = torchvision.models.mobilenet_v3_small(weights=torchvision.models.MobileNet_V3_Small_Weights.IMAGENET1K_V1)
        self.features, self.pool = m.features, m.avgpool

    def forward(self, x):
        x = (x - MEAN) / STD
        return torch.flatten(self.pool(self.features(x)), 1)


class Verifier(nn.Module):
    def __init__(self, backbone, w, b):
        super().__init__()
        self.backbone = backbone
        self.head = nn.Linear(w.shape[0], 1)
        with torch.no_grad():
            self.head.weight.copy_(torch.tensor(w, dtype=torch.float32)[None])
            self.head.bias.copy_(torch.tensor([b], dtype=torch.float32))

    def forward(self, x):
        return torch.sigmoid(self.head(self.backbone(x)))  # P(photo shows flooding)


def load(path):
    from monsoon_sentinel.photo import preprocess
    try:
        return preprocess(Image.open(path))[0]
    except Exception:  # unreadable / corrupt image
        return None


def colour_hist(x):
    """Baseline without deep learning: 8x8x8 RGB histogram."""
    h, _ = np.histogramdd(x.reshape(3, -1).T, bins=8, range=[(0, 1)] * 3)
    return (h / h.sum()).ravel()


def main():
    sys.path.insert(0, str(ROOT / "src"))
    OUT.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(SEED)
    ex = extract()
    idx = index_images(ex)
    print(idx.groupby(["group", "label"]).size().to_string(), flush=True)
    print(f"{len(idx)} images", flush=True)

    feat_file = RAW / "features.npz"
    bb = Backbone().eval()
    if feat_file.exists():
        z = np.load(feat_file, allow_pickle=True)
        F, H, keep = z["F"], z["H"], z["keep"]
    else:
        F, H, keep = [], [], []
        batch, ids = [], []
        with torch.no_grad():
            for i, p in enumerate(idx.path):
                x = load(p)
                if x is None:
                    continue
                batch.append(x)
                ids.append(i)
                if len(batch) == 64 or i == len(idx) - 1:
                    xb = torch.tensor(np.stack(batch))
                    F.append(bb(xb).numpy())
                    H.extend(colour_hist(b) for b in batch)
                    keep.extend(ids)
                    batch, ids = [], []
                if i % 1000 == 0:
                    print(f"  features {i}/{len(idx)}", flush=True)
            if batch:
                xb = torch.tensor(np.stack(batch))
                F.append(bb(xb).numpy())
                H.extend(colour_hist(b) for b in batch)
                keep.extend(ids)
        F, H, keep = np.concatenate(F), np.array(H), np.array(keep)
        np.savez_compressed(feat_file, F=F, H=H, keep=keep)
    y = idx.label.values[keep]
    print(f"usable images: {len(y)} (flooded {int(y.sum())}, normal {int((1 - y).sum())})", flush=True)

    i_tr, i_te = train_test_split(np.arange(len(y)), test_size=0.2, stratify=y, random_state=SEED)
    i_tr, i_va = train_test_split(i_tr, test_size=0.125, stratify=y[i_tr], random_state=SEED)

    heads = {
        "Colour histogram + Logistic Regression (no deep learning)": (H, make_pipeline(StandardScaler(), LogisticRegression(C=1, max_iter=3000))),
        "CNN features + Logistic Regression": (F, make_pipeline(StandardScaler(), LogisticRegression(C=0.1, max_iter=5000))),
        "CNN features + Linear SVM": (F, make_pipeline(StandardScaler(), LinearSVC(C=0.01, max_iter=20000))),
        "CNN features + KNN (k=15)": (F, make_pipeline(StandardScaler(), KNeighborsClassifier(15))),
        "CNN features + Random Forest": (F, RandomForestClassifier(400, n_jobs=-1, random_state=SEED)),
    }
    rows, fitted = [], {}
    for name, (X, m) in heads.items():
        m.fit(X[i_tr], y[i_tr])
        s = m.decision_function(X[i_te]) if hasattr(m, "decision_function") else m.predict_proba(X[i_te])[:, 1]
        yhat = m.predict(X[i_te])
        rows.append({"model": name, "accuracy": accuracy_score(y[i_te], yhat), "F1": f1_score(y[i_te], yhat),
                     "precision": precision_score(y[i_te], yhat), "recall": recall_score(y[i_te], yhat),
                     "ROC_AUC": roc_auc_score(y[i_te], s)})
        fitted[name] = m
        print(f"  {name}: acc {rows[-1]['accuracy']:.3f}", flush=True)
    bench = pd.DataFrame(rows).sort_values("F1", ascending=False)
    bench.to_csv(OUT / "photo_benchmark.csv", index=False)
    (OUT / "photo_benchmark.md").write_text(bench.round(3).to_markdown(index=False), encoding="utf-8")
    print(bench.round(3).to_string(index=False))

    # deploy the logistic head (exact, tiny, gives probabilities); fold the scaler into it
    lr = fitted["CNN features + Logistic Regression"]
    sc, clf = lr[0], lr[-1]
    w = clf.coef_[0] / sc.scale_
    b = float(clf.intercept_[0] - np.sum(clf.coef_[0] * sc.mean_ / sc.scale_))
    model = Verifier(bb, w, b).eval()

    # thresholds chosen on validation: "verified" needs >= 95 % precision
    with torch.no_grad():
        pv = 1 / (1 + np.exp(-(F[i_va] @ w + b)))
    grid = np.linspace(0.3, 0.99, 140)
    prec = [precision_score(y[i_va], pv >= t, zero_division=0) for t in grid]
    t_verified = float(next((t for t, p in zip(grid, prec) if p >= 0.95), 0.9))
    pt = 1 / (1 + np.exp(-(F[i_te] @ w + b)))
    cm = confusion_matrix(y[i_te], pt >= 0.5).tolist()
    test_at_verified = {"precision": precision_score(y[i_te], pt >= t_verified),
                        "recall": recall_score(y[i_te], pt >= t_verified)}

    onnx_path = ROOT / "models" / "photo_verifier.onnx"
    dummy = torch.rand(1, 3, 224, 224)
    torch.onnx.export(model, dummy, str(onnx_path), input_names=["image"], output_names=["p_flood"],
                      dynamic_axes={"image": {0: "batch"}, "p_flood": {0: "batch"}}, opset_version=17,
                      dynamo=False)
    web = ROOT / "web" / "public" / "models"
    web.mkdir(parents=True, exist_ok=True)
    shutil.copy2(onnx_path, web / "photo_verifier.onnx")

    # parity check: ONNX == PyTorch
    import onnxruntime as ort
    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    xs = torch.rand(4, 3, 224, 224)
    diff = float(np.abs(sess.run(None, {"image": xs.numpy()})[0] - model(xs).detach().numpy()).max())

    summary = {"dataset": "Flood10k (Mendeley Data, DOI 10.17632/4sgcd7zdsp.1, CC BY-NC 4.0)",
               "images_used": int(len(y)), "split": "70/10/20 stratified, seed 42",
               "backbone": "MobileNetV3-Small (ImageNet), frozen", "deployed_head": "Logistic Regression",
               "threshold_verified": round(t_verified, 3), "test_at_verified_threshold": test_at_verified,
               "confusion_matrix_at_0.5 [[TN,FP],[FN,TP]]": cm, "onnx_mb": round(onnx_path.stat().st_size / 1e6, 2),
               "onnx_vs_torch_max_abs_diff": diff, "benchmark": bench.round(4).to_dict("records")}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=float))
    (ROOT / "models" / "photo_verifier.json").write_text(json.dumps(
        {"threshold_verified": t_verified, "threshold_possible": 0.5}, indent=2))
    print(json.dumps({k: v for k, v in summary.items() if k != "benchmark"}, indent=2, default=float))


if __name__ == "__main__":
    main()
