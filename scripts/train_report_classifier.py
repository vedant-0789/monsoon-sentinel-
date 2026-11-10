"""Step 9: classify citizen reports (category + urgency) with Multinomial Naive Bayes.

Character n-grams (2-5) work across English, Hinglish, Marathi and Hindi without a
tokenizer per language. Evaluated with GroupKFold over templates, so every test
sentence comes from a phrasing the model never saw.

Usage:  python scripts/train_report_classifier.py
Outputs: models/report_classifier.joblib, reports/citizen/*
"""

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import FeatureUnion
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.naive_bayes import ComplementNB, MultinomialNB
from sklearn.pipeline import make_pipeline
from sklearn.svm import LinearSVC

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from monsoon_sentinel.text import normalise  # noqa: E402


def vec():
    """Character 2-5 grams (spelling / script variation) + word 1-2 grams, place names masked."""
    return FeatureUnion([
        ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=2, sublinear_tf=True,
                                 preprocessor=normalise)),
        ("word", TfidfVectorizer(analyzer="word", ngram_range=(1, 2), min_df=1, sublinear_tf=True,
                                 preprocessor=normalise, token_pattern=r"(?u)[\wऀ-ॿ]+")),
    ])


MODELS = {
    "Multinomial Naive Bayes": lambda: make_pipeline(vec(), MultinomialNB(alpha=0.1)),
    "Complement Naive Bayes": lambda: make_pipeline(vec(), ComplementNB(alpha=0.3)),
    "Logistic Regression": lambda: make_pipeline(vec(), LogisticRegression(C=5, max_iter=3000)),
    "Linear SVM": lambda: make_pipeline(vec(), LinearSVC(C=0.5)),
}

if __name__ == "__main__":
    df = pd.read_csv(ROOT / "data" / "labels" / "report_texts_seed.csv")
    out = ROOT / "reports" / "citizen"
    out.mkdir(parents=True, exist_ok=True)
    cv = GroupKFold(n_splits=5)
    rows = []
    for name, make in MODELS.items():
        pc = cross_val_predict(make(), df.text, df.category, groups=df.template, cv=cv)
        pu = cross_val_predict(make(), df.text, df.urgent, groups=df.template, cv=cv)
        row = {"model": name, "category_macro_F1": f1_score(df.category, pc, average="macro"),
               "urgent_F1": f1_score(df.urgent, pu)}
        for lang in df.lang.unique():
            m = df.lang == lang
            row[f"category_F1_{lang}"] = f1_score(df.category[m], pc[m], average="macro")
        rows.append(row)
        if name == "Multinomial Naive Bayes":
            (out / "nb_category_report.txt").write_text(classification_report(df.category, pc), encoding="utf-8")
    bench = pd.DataFrame(rows).sort_values("category_macro_F1", ascending=False)
    bench.to_csv(out / "classifier_benchmark.csv", index=False)
    print(bench.round(3).to_string(index=False))

    # Deploy Multinomial NB (fast, tiny, gives calibrated-enough class probabilities)
    cat = MODELS["Multinomial Naive Bayes"]().fit(df.text, df.category)
    urg = MODELS["Multinomial Naive Bayes"]().fit(df.text, df.urgent)
    joblib.dump({"category": cat, "urgent": urg, "trained_on": len(df),
                 "note": "seed set from templates; retrain on real reports"},
                ROOT / "models" / "report_classifier.joblib")
    nb = bench.set_index("model").loc["Multinomial Naive Bayes"]
    (out / "summary.json").write_text(json.dumps({"deployed": "Multinomial Naive Bayes",
                                                  "examples": len(df), "templates": int(df.template.nunique()),
                                                  "cv": "GroupKFold(5) over templates",
                                                  "metrics": nb.round(3).to_dict()}, indent=2))
    for s in ["water up to knees near Karve Road, bikes stuck", "कात्रज येथे झाड पडले",
              "Hadapsar mein naali band hai", "स्ट्रीट लाइट बंद है"]:
        p = cat.predict_proba([s])[0]
        print(f"{s!r:55} -> {cat.classes_[np.argmax(p)]} ({p.max():.2f}), urgent={urg.predict_proba([s])[0][1]:.2f}")
