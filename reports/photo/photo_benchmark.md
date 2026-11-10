| model                                                     |   accuracy |    F1 |   precision |   recall |   ROC_AUC |
|:----------------------------------------------------------|-----------:|------:|------------:|---------:|----------:|
| CNN features + Logistic Regression                        |      0.953 | 0.952 |       0.956 |    0.949 |     0.988 |
| CNN features + Linear SVM                                 |      0.952 | 0.951 |       0.955 |    0.948 |     0.987 |
| CNN features + Random Forest                              |      0.949 | 0.949 |       0.938 |    0.96  |     0.985 |
| CNN features + KNN (k=15)                                 |      0.929 | 0.931 |       0.89  |    0.976 |     0.98  |
| Colour histogram + Logistic Regression (no deep learning) |      0.857 | 0.859 |       0.835 |    0.885 |     0.915 |