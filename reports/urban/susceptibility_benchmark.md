| model                           |   ROC_AUC |   AUC_fold_mean |   AUC_fold_std |   capture_top5pct |   capture_top10pct |   capture_top20pct |
|:--------------------------------|----------:|----------------:|---------------:|------------------:|-------------------:|-------------------:|
| Baseline: near nala             |     0.77  |           0.775 |          0.069 |             0.188 |              0.375 |              0.5   |
| Monotone LightGBM (physics 6)   |     0.761 |           0.778 |          0.113 |             0.156 |              0.344 |              0.562 |
| Baseline: near river/nala       |     0.742 |           0.739 |          0.118 |             0.156 |              0.281 |              0.469 |
| Random Forest (physics 6)       |     0.737 |           0.751 |          0.121 |             0.219 |              0.375 |              0.562 |
| Logistic Regression (physics 6) |     0.733 |           0.755 |          0.119 |             0.25  |              0.406 |              0.5   |
| LightGBM (all 15)               |     0.696 |           0.726 |          0.078 |             0.062 |              0.188 |              0.375 |
| Logistic Regression (all 15)    |     0.674 |           0.709 |          0.143 |             0.25  |              0.344 |              0.438 |
| Random Forest (all 15)          |     0.669 |           0.715 |          0.16  |             0.125 |              0.188 |              0.375 |
| Gaussian Naive Bayes (all 15)   |     0.64  |           0.651 |          0.159 |             0.062 |              0.375 |              0.438 |
| SVM RBF (all 15)                |     0.594 |           0.626 |          0.172 |             0.156 |              0.25  |              0.375 |
| Baseline: low HAND              |     0.566 |           0.556 |          0.066 |             0.031 |              0.219 |              0.281 |
| KNN k=25 (all 15)               |     0.516 |           0.519 |          0.044 |             0.062 |              0.062 |              0.062 |
| Baseline: high TWI              |     0.504 |           0.518 |          0.053 |             0.094 |              0.125 |              0.125 |
| Baseline: flow accumulation     |     0.492 |           0.497 |          0.102 |             0.094 |              0.094 |              0.125 |