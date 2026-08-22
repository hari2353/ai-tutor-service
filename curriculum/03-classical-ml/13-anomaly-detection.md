# Anomaly Detection: Statistical, Isolation Forest, Autoencoder, and the Pipeline

> **Track:** T03 Classical ML · **Time:** 2.5h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T03-anomaly-detection` · **Tags:** models,critical

## The 30-second version

Anomaly detection is fundamentally a labeling problem in disguise: supervised when you have enough labeled anomalies to train a classifier (rare, because anomalies are by definition rare), semi-supervised when you train only on normal data and flag deviations (the common real-world case — you have plenty of "normal," almost no "abnormal"), and unsupervised when you have no labels at all and rely purely on structural assumptions about what "normal" looks like. Isolation Forest exploits the fact that anomalies are easier to isolate with fewer random splits; LOF catches anomalies defined by local density rather than global distance, which Isolation Forest and z-score both miss; autoencoders learn to reconstruct normal data well and flag high reconstruction error, working on complex, high-dimensional, non-tabular data where the other methods don't extend cleanly. Under extreme class imbalance — and real anomaly rates are routinely under 1% — accuracy is meaningless and even ROC-AUC can look deceptively strong while precision is unusable in practice; PR-AUC and precision-at-k are the metrics that don't lie to you. None of this matters without a production pipeline: a scoring service, an alert threshold tuned against a real cost function, and a human-review loop that feeds confirmed labels back into retraining, because a model that only ever flags and never learns from being right or wrong degrades silently as the anomaly distribution drifts.

## Why this gets asked

Because anomaly detection is the place where a candidate's metric literacy gets tested hardest — someone who reports "our fraud model has 99.7% accuracy" without being asked has usually just told you they don't know their fraud rate is 0.3% and their model might be doing nothing. The interviewer has watched a fraud, intrusion-detection, or manufacturing-QA system get shipped with a beautiful offline ROC-AUC, then flood the review team with false positives in week one because nobody set the threshold against the actual cost of a false positive versus a false negative, or nobody built the human-review feedback loop that would have let the model improve instead of decaying. They're checking whether you think about anomaly detection as a full operational system, not a `.fit()` call.

---

## Lineage: past → present → future

**What came before.** Classical statistical process control (Shewhart control charts, 1920s-30s) is the ancestor of modern anomaly detection — flag a measurement as out-of-control if it falls outside `mean ± 3σ`, built for manufacturing quality assurance where the underlying process was assumed roughly Gaussian and univariate. This broke down as data became high-dimensional and multivariate: a point can look perfectly normal on every individual dimension while being a clear outlier in the joint distribution (two features individually in-range but never co-occurring together in normal operation), which univariate control charts structurally cannot see. Distance- and density-based methods (k-nearest-neighbor distance, LOF — Breunig et al., 2000) addressed the multivariate case but inherited the curse of dimensionality and needed a meaningful distance metric, which real high-dimensional data often doesn't have.

**Where it stands now.** Isolation Forest (Liu, Ting & Zhou, 2008) reframed the problem: instead of modeling what "normal" density looks like and measuring deviation from it, it directly measures how *easy* a point is to isolate via random recursive splitting, exploiting the fact that anomalies, being few and different, typically separate from the rest of the data in fewer splits. This sidesteps needing a distance metric or a density estimate entirely and scales roughly linearly, which is why it's become close to a default first choice for tabular anomaly detection at moderate-to-large scale. Deep learning approaches — autoencoders, variational autoencoders, GANs (GAIN and its anomaly-detection descendants) — dominate when the data is high-dimensional, unstructured, or has complex nonlinear structure (images, sensor time series, network traffic embeddings) that tree-based isolation and shallow density methods don't capture well. The live disagreement is less about which algorithm is "best" in the abstract — benchmark comparisons genuinely disagree by dataset and dimensionality, with Isolation Forest generally winning on speed and scale and One-Class SVM sometimes winning on precision in smaller, lower-dimensional settings — and more about **evaluation**: the field has converged hard on the position that accuracy and even ROC-AUC are actively misleading under the extreme imbalance anomaly detection always involves, and PR-AUC or precision/recall at a fixed operating point are the only honest metrics, but a meaningful fraction of published work and production dashboards still report ROC-AUC as if it settles the question.

**Where it's heading.** Foundation-model-style anomaly detection — pretraining a general-purpose time-series or tabular anomaly detector on large, diverse corpora and fine-tuning or zero-shotting to a new domain — is an active research direction (time-series foundation models like those from several 2024-2025 papers) but is not yet standard production practice for most teams; treat it as promising and early rather than deployed-by-default. What is more settled and already shipping: the shift from "one static threshold, tuned once" to continuously recalibrated, cost-aware thresholds that adapt to concept drift, paired with active-learning-style human review loops where analyst feedback on flagged cases becomes labeled training data for periodic retraining — this closes the loop that most anomaly detection postmortems find was missing.

---

## Mental model

```
                     HOW MUCH LABEL INFORMATION DO YOU HAVE?

  Plenty of labeled          Plenty of labeled           No labels at all,
  anomalies AND normal       NORMAL data, few/no         or too few to trust
  examples (rare in          labeled anomalies           any of them
  practice — anomalies       (the COMMON case)
  are rare by definition)
        │                          │                            │
        ▼                          ▼                            ▼
   SUPERVISED               SEMI-SUPERVISED               UNSUPERVISED
   train a classifier       train on "normal" ONLY,       assume normal points
   (often with class        flag deviations from what     cluster / are dense,
   weighting or SMOTE       the model learned as          anomalies are rare AND
   for the imbalance)       "normal" (autoencoder          different structurally
                            reconstruction error,          (Isolation Forest, LOF,
                            one-class SVM boundary)         One-Class SVM, z-score/IQR)

  ┌───────────────────────────────────────────────────────────────────────┐
  │  WHAT KIND OF "DIFFERENT" DOES YOUR METHOD ACTUALLY DETECT?           │
  │                                                                       │
  │  z-score / IQR        far from the GLOBAL mean/median (univariate)   │
  │  Isolation Forest     easy to ISOLATE via random splits (multivariate,│
  │                       structural, doesn't need a distance metric)    │
  │  LOF                  far from its LOCAL neighborhood density         │
  │                       (catches anomalies invisible to global methods) │
  │  One-Class SVM        outside a learned boundary around normal data   │
  │  Autoencoder          reconstructs POORLY (the model never learned    │
  │                       this input pattern) — scales to high-dim, non-  │
  │                       tabular data the others don't reach cleanly     │
  └───────────────────────────────────────────────────────────────────────┘
```

**The LOF-specific case worth internalizing:** a point can sit in a moderately dense region of the overall data and still be a clear local anomaly if its *immediate* neighborhood is far denser — imagine a sparse cluster of legitimate low-volume users sitting near a dense cluster of high-volume power users; a global method might not flag a slightly-too-high point within the sparse cluster because globally it's not extreme, but LOF, which compares local density to the local neighborhood's density, catches it because relative to *its own neighbors* it's an outlier.

---

## How it actually works

### Statistical methods — z-score, IQR (the univariate baseline)

Already covered mechanically in the EDA module; the relevant point for anomaly detection specifically is that these are single-feature methods, and real anomalies (fraud, intrusion, defects) are usually multivariate — a value normal on every individual dimension can be jointly anomalous. Use these as a fast first pass or a monitoring layer on individual metrics, not as your primary detector for multivariate anomalies.

### Isolation Forest — the mechanism, precisely

Build an ensemble of trees where each tree is constructed by **recursively selecting a random feature and a random split value** between that feature's min and max, until every point is isolated in its own leaf. The **path length** — number of splits needed to isolate a point — is the signal: anomalies, being few and differently-distributed, tend to get isolated in *fewer* splits than normal points, because random splitting is more likely to separate an outlier from the bulk of the data quickly.

```python
from sklearn.ensemble import IsolationForest

# defaults: n_estimators=100, max_samples='auto' (min(256, n_samples)),
# contamination='auto', max_features=1.0, bootstrap=False
iso = IsolationForest(n_estimators=100, contamination=0.01, random_state=0)
iso.fit(X_train)                      # unsupervised — no labels needed
scores = iso.decision_function(X)     # higher = more normal; negative = anomalous
predictions = iso.predict(X)          # 1 = normal, -1 = anomaly
```
[IsolationForest — scikit-learn 1.9 documentation](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html) — accessed 2026-08-01

**Why `max_samples='auto'` defaults to `min(256, n_samples)`, and why that's not a bug:** the original paper (Liu, Ting & Zhou, 2008) found that isolation trees don't need to see the full dataset to isolate anomalies effectively — a small subsample per tree is sufficient because anomalies isolate quickly regardless of how much of the rest of the data is present, and using a small subsample actually *reduces* the "swamping" and "masking" effects where dense normal regions or clusters of anomalies interfere with isolating individual points. This is a genuine algorithmic insight, not just a speed optimization. [Isolation-based Anomaly Detection — Liu, Ting & Zhou](https://www.lamda.nju.edu.cn/publication/tkdd11.pdf) — accessed 2026-08-01

**Benchmark reality, not folklore:** empirical comparisons consistently show Isolation Forest as fastest and most scalable for datasets above roughly a thousand points and largely insensitive to dimensionality growth, while One-Class SVM can edge it out on precision in smaller, lower-dimensional, precision-critical settings but degrades sharply on large or high-dimensional data, especially with non-linear kernels. Neither dominates universally — the honest answer states this rather than picking one as "the best."

### Local Outlier Factor (LOF) — density relative to neighbors

```python
from sklearn.neighbors import LocalOutlierFactor

# defaults: n_neighbors=20, contamination='auto', novelty=False
# novelty=False means LOF is fit-and-predict only (outlier detection on the training set);
# set novelty=True to call .predict() on NEW data after fitting on clean training data
lof = LocalOutlierFactor(n_neighbors=20, contamination=0.01)
predictions = lof.fit_predict(X)      # -1 = outlier, 1 = inlier
scores = lof.negative_outlier_factor_ # more negative = more anomalous
```
[LocalOutlierFactor — scikit-learn 1.9 documentation](https://scikit-learn.org/stable/modules/generated/sklearn.neighbors.LocalOutlierFactor.html) — accessed 2026-08-01

LOF computes, for each point, the ratio of its local density to the average local density of its `k` nearest neighbors (`n_neighbors=20` by default). A ratio near 1 means the point's density matches its neighbors (normal); a ratio significantly greater than 1 means the point sits in a notably sparser region than its neighbors, flagging it as a local anomaly regardless of how the point looks globally. **This is the method's entire value proposition over Isolation Forest and z-score:** it catches anomalies defined by *local* context that global methods structurally cannot see, at the cost of `novelty=False` by default (meaning it's naturally an outlier-detection-on-training-set tool, not out-of-the-box a scorer for new incoming points without explicitly setting `novelty=True`).

### One-Class SVM — a learned boundary

```python
from sklearn.svm import OneClassSVM

# defaults: kernel='rbf', gamma='scale', nu=0.5
# nu is simultaneously an upper bound on the fraction of training errors and a lower
# bound on the fraction of support vectors — set nu ≈ expected contamination rate, NOT 0.5
oc_svm = OneClassSVM(kernel="rbf", nu=0.01, gamma="scale")
oc_svm.fit(X_train)                    # train on (mostly) normal data
predictions = oc_svm.predict(X)        # 1 = normal, -1 = anomaly
```
[OneClassSVM — scikit-learn 1.9 documentation](https://scikit-learn.org/stable/modules/generated/sklearn.svm.OneClassSVM.html) — accessed 2026-08-01. Learns a boundary (a hyperplane in a kernel-transformed feature space) that encloses the normal data as tightly as possible, controlled by `nu`. **The default `nu=0.5` is a trap** — it assumes roughly half your data is contamination, wildly wrong for most real anomaly detection where the actual rate is under 1-5%; leaving it at default silently produces a boundary calibrated to the wrong assumption.

### Autoencoders — reconstruction error as the anomaly signal

Train a neural network to compress input to a low-dimensional bottleneck and reconstruct it, using **only normal data** for training. The network learns the structure of normal examples; when it sees an anomaly at inference time, it reconstructs poorly (high reconstruction error) because it never learned that pattern.

```python
import torch
import torch.nn as nn

class Autoencoder(nn.Module):
    def __init__(self, input_dim: int, bottleneck_dim: int = 8):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 32), nn.ReLU(),
            nn.Linear(32, bottleneck_dim),
        )
        self.decoder = nn.Sequential(
            nn.Linear(bottleneck_dim, 32), nn.ReLU(),
            nn.Linear(32, input_dim),
        )

    def forward(self, x):
        return self.decoder(self.encoder(x))

# Training loop trains ONLY on normal-labeled (or presumed-normal) data.
# Reconstruction loss (MSE) at inference IS the anomaly score.
def reconstruction_error(model, x):
    with torch.no_grad():
        return ((model(x) - x) ** 2).mean(dim=1)   # per-sample MSE
```

**Setting the threshold — the step that actually determines whether this works in production.** Three common approaches, in increasing order of rigor:
1. `mean(reconstruction_error on validation set) + 3 × std` — the "three-sigma rule" applied to reconstruction error rather than the raw feature; inherits the same skew problems z-score has if reconstruction error itself is skewed (it usually is, since error is non-negative and often long-tailed).
2. A high percentile (commonly the 99th) of reconstruction error on a **known-clean** validation set — more robust to skew than the mean+3σ rule since it doesn't assume near-normality.
3. Optimize the threshold directly against a **held-out set that includes some known/labeled anomalies**, choosing the point on the precision-recall curve that matches your actual cost tradeoff between false positives (wasted review time) and false negatives (missed fraud/failure/intrusion) — this is the rigorous version and the one production systems should converge to once any labeled anomalies exist.
[Computing Anomaly Score Threshold with Autoencoders Pipeline — Springer](https://link.springer.com/chapter/10.1007/978-3-030-13469-3_28) — accessed 2026-08-01 confirms threshold selection is a genuinely non-trivial step even for practitioners, not a mechanical afterthought — it is documented as the most common production failure point in autoencoder-based anomaly systems.

### The extreme-imbalance evaluation problem — why accuracy and ROC-AUC mislead

**Accuracy fails obviously:** at a 0.1% true anomaly rate, a model that predicts "normal" for everything scores 99.9% accuracy while catching zero anomalies.

**ROC-AUC fails less obviously, which is why it's more dangerous.** ROC-AUC plots true positive rate against *false positive rate*, and false positive rate is computed relative to the (huge) number of true negatives — under extreme imbalance, even a large *absolute* number of false positives is a tiny *fraction* of the negative class, so the false positive rate stays low and ROC-AUC stays high, even when the model is producing so many false positives in absolute terms that the alert queue is unusable. Concretely: with 1,000,000 normal transactions and 1,000 fraudulent ones (0.1% rate), a model with a 1% false positive rate generates 10,000 false alarms — ten times the actual fraud count — while that 1% FPR barely dents the ROC-AUC calculation, which is dominated by the million true negatives.

**PR-AUC fixes this by construction:** precision is computed as `TP / (TP + FP)`, directly exposing how the false-positive volume compares to the true-positive volume, with no huge true-negative denominator to hide behind. [ROC AUC vs Precision-Recall for Imbalanced Data — MachineLearningMastery](https://machinelearningmastery.com/roc-auc-vs-precision-recall-for-imbalanced-data/) — accessed 2026-08-01

```python
from sklearn.metrics import average_precision_score, roc_auc_score

# On extremely imbalanced data, report BOTH but trust PR-AUC (average_precision_score)
# as the number that reflects operational reality
pr_auc = average_precision_score(y_true, scores)
roc_auc = roc_auc_score(y_true, scores)   # can look deceptively strong; report with caution
```

**Precision-at-k** is often the most operationally honest metric of all: given that a human review team can only investigate `k` flagged cases per day, "what fraction of the top-`k` scored cases are true anomalies" directly answers "is this system worth the analyst time it costs," in a way PR-AUC (which integrates over all thresholds) doesn't directly answer for a specific staffing level.

---

## Build it from scratch

Minimal Isolation Forest — a single isolation tree, to show what the ensemble is actually built from:

```python
import numpy as np

class IsolationTree:
    def __init__(self, max_depth: int):
        self.max_depth = max_depth
        self.split_feature = None
        self.split_value = None
        self.left = None
        self.right = None
        self.size = 0            # number of points at this node — used for path length correction

    def fit(self, X: np.ndarray, depth: int = 0):
        self.size = len(X)
        if depth >= self.max_depth or len(X) <= 1:
            return self
        self.split_feature = np.random.randint(X.shape[1])
        col = X[:, self.split_feature]
        if col.min() == col.max():           # can't split a constant column further
            return self
        self.split_value = np.random.uniform(col.min(), col.max())
        left_mask = col < self.split_value
        self.left = IsolationTree(self.max_depth).fit(X[left_mask], depth + 1)
        self.right = IsolationTree(self.max_depth).fit(X[~left_mask], depth + 1)
        return self

    def path_length(self, x: np.ndarray, depth: int = 0) -> float:
        if self.split_feature is None:       # leaf reached
            return depth + _c(self.size)     # average path length correction for remaining points
        if x[self.split_feature] < self.split_value:
            return self.left.path_length(x, depth + 1)
        return self.right.path_length(x, depth + 1)


def _c(n: int) -> float:
    """Average path length of an unsuccessful search in a Binary Search Tree of n points —
    the normalization constant from the original Isolation Forest paper (Liu et al., 2008)."""
    if n <= 1:
        return 0.0
    return 2 * (np.log(n - 1) + 0.5772156649) - 2 * (n - 1) / n   # 0.577... is the Euler-Mascheroni constant


class IsolationForestFromScratch:
    def __init__(self, n_trees: int = 100, sample_size: int = 256):
        self.n_trees = n_trees
        self.sample_size = sample_size
        self.trees: list[IsolationTree] = []

    def fit(self, X: np.ndarray):
        max_depth = int(np.ceil(np.log2(self.sample_size)))   # matches sklearn's depth cap rationale
        for _ in range(self.n_trees):
            idx = np.random.choice(len(X), size=min(self.sample_size, len(X)), replace=False)
            self.trees.append(IsolationTree(max_depth).fit(X[idx]))
        return self

    def anomaly_score(self, X: np.ndarray) -> np.ndarray:
        avg_path_lengths = np.array([
            np.mean([tree.path_length(x) for tree in self.trees]) for x in X
        ])
        c_n = _c(self.sample_size)
        # score in [0, 1]; closer to 1 = more anomalous (shorter average path)
        return 2 ** (-avg_path_lengths / c_n)
```

This matches the score formula from the original paper and, on well-separated synthetic data, produces the same rank ordering as `sklearn.ensemble.IsolationForest`. Reference lab: `(lab pending)` (build if not present) — includes a test comparing this from-scratch implementation's AUC against sklearn's on a synthetic dataset with injected anomalies, plus the autoencoder threshold-selection exercise comparing the three threshold methods above on the same data.

---

## How it's done in production

| Component | Tool | What it does |
|---|---|---|
| Statistical baseline / monitoring | Custom z-score/IQR checks, or a metrics platform (Datadog, Prometheus + alerting rules) | Fast, cheap first line for univariate metric monitoring — request latency, error rate — not for complex multivariate fraud/intrusion patterns |
| Tabular multivariate detection | `sklearn.ensemble.IsolationForest`, `pyod` (a dedicated Python anomaly detection library wrapping dozens of algorithms behind a consistent API) | The default choice for structured/tabular data at moderate-to-large scale |
| High-dimensional / unstructured | Autoencoders, VAEs (PyTorch/TensorFlow), or embedding-based nearest-neighbor methods on top of a pretrained encoder | Images, sensor time series, text/log embeddings — where isolation/density methods on raw features don't capture the right structure |
| Scoring service | A model server (TorchServe, a FastAPI wrapper, or batch scoring in Spark/Airflow) | Turns the fitted model into either real-time or batch anomaly scores at the volume the business needs |
| Alerting | A rules/thresholding layer sitting on top of the raw score, tuned against a cost function, not a fixed statistical threshold picked once and forgotten | This is where "statistically anomalous" becomes "worth paging a human," and the two are not the same threshold |
| Human review loop | A case-management/ticketing interface (often custom, sometimes built on tools like Retool) where analysts confirm or reject flagged cases | The confirmed/rejected labels become training data for the next retraining cycle — this closes the loop that keeps the model from drifting stale |

### End-to-end production pipeline, concretely

```
  raw events ──▶ feature pipeline ──▶ scoring model ──▶ raw anomaly score
                                                              │
                                                              ▼
                                          threshold (tuned against cost function,
                                          recalibrated periodically for drift)
                                                              │
                                       ┌──────────────────────┴──────────────────────┐
                                       ▼                                             ▼
                              below threshold: log,                        above threshold: ALERT
                              no action, but retained                      → human review queue
                              for periodic re-scoring                              │
                              if threshold moves                                   ▼
                                                                          analyst confirms/rejects
                                                                                    │
                                                                                    ▼
                                                                  labeled outcome feeds back into
                                                                  the training set for periodic
                                                                  retraining (this is the loop
                                                                  most production systems skip,
                                                                  and the reason they go stale)
```

### What breaks in production

| Symptom | Cause | Fix |
|---|---|---|
| Model reports 99.8% accuracy, catches almost no real fraud | Accuracy on a ~0.2% base rate is dominated by trivially-correct "normal" predictions | Report PR-AUC and precision/recall at the actual operating threshold, never accuracy, on imbalanced anomaly data |
| ROC-AUC is 0.95 but analysts are drowning in false positives | ROC-AUC's false-positive-rate denominator (true negatives) is huge under extreme imbalance, hiding a large absolute false-positive count | Report and optimize PR-AUC and precision-at-k instead; size the alert threshold against actual analyst review capacity |
| Autoencoder threshold set once at launch works fine for a month, then floods the queue | Underlying "normal" distribution drifted (seasonality, a legitimate new user behavior pattern, a system upgrade changing normal traffic shape) but the reconstruction-error threshold never got recalibrated | Periodically recompute the threshold against a recent, known-clean window of data; monitor the alert rate itself as a drift signal |
| One-Class SVM never flags anything | `nu` left at the default 0.5, which assumes 50% contamination and produces an overly loose or oddly-shaped decision boundary for the actual ~1% real anomaly rate | Set `nu` close to the expected true contamination rate, not the default |
| Isolation Forest flags an implausibly large fraction of points as anomalous | `contamination` parameter set too high, or left at a value that doesn't match the real base rate, directly shifting the decision threshold | Set `contamination` from a validated estimate of the true anomaly rate, not a guess, and re-validate periodically |
| A LOF-based system misses a fraud pattern the team knows is real | The fraud pattern is a *global* anomaly (extreme value, far from everything) rather than a local-density anomaly, and LOF is specifically tuned for local, not global, anomalies | Combine LOF with a global method (Isolation Forest, z-score/IQR) — no single anomaly definition covers every failure mode |
| Model performance degrades over months with no obvious single cause | No human-review feedback loop — flagged cases are acted on operationally but never fed back into retraining, so the model never learns from its own true/false positive history as the underlying data distribution drifts | Build the confirm/reject loop explicitly into the review tooling and retrain on a cadence using the accumulated labels |

---

## Tradeoffs & when NOT to use it

- **Don't use accuracy, or ROC-AUC alone, to evaluate anomaly detection with realistic base rates.** Both actively mislead under extreme imbalance for the reasons above; PR-AUC and precision-at-k are the honest metrics.
- **Don't leave `nu` (OneClassSVM) or `contamination` (IsolationForest, LOF) at library defaults without checking what they assume.** `nu=0.5` and unvalidated `contamination` values encode an assumption about the anomaly rate that is very likely wrong for your actual data and will silently miscalibrate the whole model.
- **Don't use LOF as your only method if you also need to catch global anomalies, and don't use Isolation Forest/z-score as your only method if the anomalies you care about are local-density anomalies.** These catch structurally different things; production systems needing broad coverage often ensemble multiple detection philosophies rather than picking one.
- **Don't set an autoencoder's reconstruction-error threshold once at launch and leave it.** Concept drift in the "normal" distribution is the norm, not the exception, for most operational systems (seasonality, product changes, user behavior evolution), and a static threshold degrades from either missed anomalies or an unmanageable false-positive rate as drift accumulates.
- **Don't deploy an anomaly detection system without a human-review feedback loop.** A model that only ever outputs alerts and never receives confirmed/rejected labels back cannot detect its own drift or improve, and this is the single most common reason production anomaly systems degrade silently over time.
- **When NOT to use unsupervised/semi-supervised methods at all:** if you genuinely have enough labeled anomalies (hundreds to thousands, not a handful) and the anomaly type is stable, a supervised classifier with appropriate class weighting or resampling usually outperforms unsupervised methods, because it can directly learn the discriminative boundary rather than inferring anomalousness indirectly from "different from normal." Reach for unsupervised/semi-supervised specifically because labeled anomalies are scarce or the anomaly type is expected to be novel (zero-day-style), not by default.
- **Autoencoders are usually overkill for well-structured tabular data with a modest number of features.** Isolation Forest or LOF will often match or beat autoencoder performance on tabular data at a fraction of the engineering and tuning cost; reach for autoencoders when the data is high-dimensional, unstructured, or has complex nonlinear structure that tree/density methods on raw features don't capture.

---

## Interview questions

### Q1 — Supervised, semi-supervised, and unsupervised anomaly detection — define each and say when you'd use which.
**Testing:** whether "anomaly detection" is understood as a spectrum of labeling scenarios, not one algorithm family.
**Answer:** Supervised: you have labeled examples of both normal and anomalous cases and train a standard classifier, typically with class weighting or resampling for the imbalance — use when you have enough confirmed anomaly labels (hundreds+) and the anomaly type is stable. Semi-supervised: you train only on normal (or presumed-normal) data and flag deviations from what the model learned — the common real case, since anomalies are rare almost by definition, and this is what autoencoders and one-class SVM do. Unsupervised: no labels at all, relying purely on structural assumptions (density, isolation ease) about what makes a point unusual — used when you can't even confidently label a training set as "normal."
**Follow-up trap:** *"If you have a small number of confirmed anomaly labels — say 50 out of a million records — do you go supervised?"* — generally no; 50 positive examples is usually too few to train a reliable discriminative classifier, especially if the anomaly type might evolve. Better to use semi-supervised/unsupervised methods for detection and use those 50 labels for threshold calibration and evaluation instead of as classifier training data.

### Q2 — Explain the mechanism behind Isolation Forest — why does isolating a point in fewer splits indicate anomaly?
**Answer:** Each tree recursively picks a random feature and a random split point between that feature's observed min and max. Anomalies are, by definition, few in number and typically differ substantially from the bulk of the data on at least one dimension, so a random split is disproportionately likely to separate an anomaly from everything else quickly — it takes fewer splits to isolate it into its own region. Normal points, being numerous and densely packed together, require many more splits before they end up alone. Average path length across the forest, converted to a score via the paper's normalization constant, is the anomaly score.
**Follow-up trap:** *"Why does sklearn's IsolationForest default max_samples to min(256, n_samples) instead of using the whole dataset per tree?"* — the original paper found that a small subsample per tree is sufficient and actually *improves* results by reducing "swamping" (dense normal regions making it harder to isolate points) and "masking" (clusters of anomalies making each other harder to isolate) — it's a genuine algorithmic choice validated in the paper, not just a speed shortcut, and quoting only "it's faster" misses half the answer.

### Q3 — What does LOF catch that Isolation Forest and z-score miss?
**Answer:** LOF measures density relative to a point's *local* neighborhood rather than the global distribution. A point can sit in a moderately normal-looking global position while being distinctly sparser than its immediate neighbors — for example, a data point in a low-density region adjacent to a high-density cluster, where the point isn't extreme by global standards but is clearly anomalous relative to the cluster right next to it. Global methods (Isolation Forest via random splits over the whole feature range, z-score via the global mean/std) don't have a concept of "relative to this specific local neighborhood" and can miss these local anomalies entirely.
**Follow-up trap:** *"Does that mean LOF is strictly better?"* — no; LOF specifically can miss anomalies that ARE extreme globally but sit in a locally sparse-but-consistent region (e.g., a whole cluster of similar anomalies far from everything else might look locally "normal" to each other under LOF's local-density lens). No single method covers both local and global anomaly definitions; production systems commonly ensemble both philosophies.

### Q4 — Your autoencoder-based anomaly detector needs a reconstruction-error threshold. Walk through three ways to set it, in order of rigor.
**Answer:** Least rigorous: mean reconstruction error on a validation set plus 3 standard deviations (a three-sigma rule applied to the error, not the raw feature) — this inherits the same skew vulnerability z-score has on raw data, since reconstruction error is non-negative and typically right-skewed. More robust: use a high percentile (commonly the 99th) of reconstruction error on a known-clean validation set, which doesn't assume near-normality of the error distribution. Most rigorous: if you have any labeled anomalies at all, optimize the threshold directly against the precision-recall tradeoff that matches your actual cost function for false positives versus false negatives, rather than picking a statistical rule that ignores operational cost entirely.
**Follow-up trap:** *"You set the threshold at launch using the 99th percentile method and it worked well for a month, then false positives spiked. What happened?"* — the underlying "normal" distribution almost certainly drifted (seasonality, a product change, evolving user behavior), and the threshold, computed once from a training-time snapshot, is now miscalibrated against current normal behavior. Thresholds need periodic recalibration against a recent known-clean window, not a set-once value.

### Q5 — Why is accuracy meaningless for anomaly detection, with actual numbers?
**Answer:** Real anomaly rates are typically well under 1-2%. At a 0.1% true anomaly rate, a trivial model that predicts "normal" for every single input scores 99.9% accuracy while catching zero anomalies — the metric rewards doing nothing because the majority class dominates the calculation.
**Follow-up trap:** *"Isn't ROC-AUC the standard fix for this?"* — it's an improvement but not a full fix. ROC-AUC's false positive rate is computed against the (enormous) count of true negatives, so under extreme imbalance even a substantial *absolute* number of false positives is a small *fraction* of the negative class and barely moves ROC-AUC — a model can report 0.95 ROC-AUC while generating ten times more false alarms than true positives in absolute terms. PR-AUC, computed from precision (`TP/(TP+FP)`, no huge negative-class denominator to hide behind), is the metric that actually reflects operational reality.

### Q6 — Concretely, with numbers, explain why ROC-AUC can look strong while a fraud model is operationally useless.
**Answer:** Say 1,000,000 legitimate transactions and 1,000 fraudulent ones (0.1% base rate). A model with a 1% false positive rate produces 10,000 false alarms — ten times the actual fraud count — meaning only about 1 in 11 flagged transactions is real fraud even before accounting for the true positive rate. That 1% FPR barely registers against the million-transaction true-negative base, so ROC-AUC stays high, while the review team is drowning in noise and the precision an analyst actually experiences is under 10%.
**Follow-up trap:** *"What operating point would you actually recommend, and how would you justify it?"* — pick the threshold from the precision-recall curve at the point matching real review team capacity (precision-at-k, where k is the number of cases the team can realistically investigate per day/shift), and justify it explicitly against the cost of a missed fraud case versus the cost of analyst time on a false alarm — this is a business cost-function decision, not a purely statistical one, and saying so is the senior signal.

### Q7 — `OneClassSVM`'s default `nu` is 0.5. Why is this dangerous if left unchanged, and what should you set it to?
**Answer:** `nu` acts simultaneously as an upper bound on the fraction of training points allowed to be margin errors and a lower bound on the fraction of support vectors — effectively, it's your assumption about the contamination rate in the training data. Leaving it at 0.5 assumes roughly half your training data is anomalous, which is wildly wrong for essentially every real anomaly detection scenario (typically well under 5%, often under 1%), and produces a decision boundary calibrated to that false assumption — likely far too loose, flagging far more as "normal" than it should, or shaped incorrectly relative to the true data structure.
**Follow-up trap:** *"How would you actually determine what to set nu to if you have zero labeled anomalies?"* — start from domain knowledge or industry benchmarks for the expected anomaly rate in this specific problem (fraud rates, defect rates, and intrusion rates all have rough published ranges by industry), set nu near that estimate, and treat it as something to refine once even a small number of confirmed labels accumulate from the human review loop — it's a starting estimate, not a one-time guess to leave forever.

### Q8 — Design the end-to-end production pipeline for a manufacturing defect detection system using sensor data, from raw signal to a human decision.
**Testing:** whether you think about anomaly detection as a system, not a model.
**Answer:** Feature pipeline extracts relevant signal statistics (or feeds raw/windowed signal into an autoencoder if the pattern space is complex and nonlinear). Scoring happens either in real time (streaming inference per unit) or in short batches depending on latency requirements. The raw anomaly score passes through a threshold tuned against the real cost tradeoff (cost of a missed defect shipped to a customer versus cost of a false-alarm inspection), not a fixed statistical rule picked once. Anything above threshold routes to a human inspection queue; the inspector's confirm/reject decision is logged as a label. Those labels feed a periodic retraining cadence, and the alert rate itself is monitored as a drift signal — a sudden shift in flagged-rate without a corresponding shift in true defect rate is itself informative and should trigger threshold recalibration or investigation.
**Follow-up trap:** *"The inspection team says they're overwhelmed and want fewer false positives, even if it means missing a few more real defects. How do you actually implement that tradeoff?"* — move along the precision-recall curve toward higher precision by raising the threshold, but be explicit and document the resulting drop in recall (more real defects will now pass through undetected) as a deliberate business decision with a stated expected cost, not a free efficiency win — every threshold move is a real tradeoff, and pretending otherwise is the failure mode here.

### Q9 — When would you deliberately NOT use an autoencoder for anomaly detection, even though it's the most flexible method on this list?
**Answer:** For well-structured tabular data with a modest number of features, an autoencoder is usually more engineering and tuning cost (architecture choice, training stability, threshold calibration on a genuinely non-obvious reconstruction-error distribution) than it's worth — Isolation Forest or LOF typically match or beat it on this kind of data with far less setup and no neural network training pipeline to maintain. Reach for autoencoders specifically when the data is high-dimensional, unstructured (images, raw sensor time series, embeddings), or has complex nonlinear structure that tree/density methods operating on raw features genuinely can't capture.
**Follow-up trap:** *"Your team wants to use a deep autoencoder on a 12-feature tabular fraud dataset because 'deep learning is more accurate.' How do you respond?"* — push back with the actual tradeoff: on 12 tabular features, an Isolation Forest is very likely to match the autoencoder's detection quality at a fraction of the engineering cost, with no reconstruction-error-threshold calibration problem to solve and no risk of the autoencoder overfitting its reconstruction to noise in a small feature space. "More complex model" is not the same claim as "more accurate model," and on simple tabular data the complexity often buys nothing.

### Q10 — Your anomaly detection system has been running in production for eight months with no retraining. What's your first hypothesis for why performance is degrading, and how do you confirm it?
**Answer:** Concept drift in the "normal" distribution combined with the absence of a feedback loop — the underlying data (user behavior, transaction patterns, sensor baselines) has almost certainly shifted over eight months, and without a mechanism feeding confirmed/rejected human review outcomes back into retraining, the model has no way to adapt. Confirm by comparing the current feature distributions against the training-time snapshot (the same train-serving-skew check from the EDA module, applied here), and by checking whether the alert rate itself has drifted independent of any known change in the true underlying anomaly rate.
**Follow-up trap:** *"What if the feature distributions look stable but performance still degraded?"* — then suspect the anomaly *type* itself has evolved rather than the baseline "normal" distribution — fraud patterns, intrusion techniques, and defect modes adapt specifically because they're adversarial or because upstream processes changed in ways not captured by the features you're monitoring. This points toward needing new features or an expanded label set from recent confirmed cases, not just a threshold recalibration.

### Q11 — How would you evaluate two anomaly detection models (Isolation Forest vs. an autoencoder) to decide which to deploy, given a small set of confirmed historical anomalies?
**Answer:** Compute PR-AUC on the labeled evaluation set for both, since it reflects the actual precision/recall tradeoff under the real (imbalanced) class distribution rather than being distorted by the negative class size like ROC-AUC. Also compute precision-at-k at the specific `k` matching realistic review team capacity, since that's the number that determines whether either model is actually usable operationally, not just statistically better. Prefer the simpler model (typically Isolation Forest) unless the more complex one (autoencoder) shows a meaningful, not marginal, improvement on these operationally-relevant metrics, given the added engineering and threshold-maintenance cost of the more complex option.
**Follow-up trap:** *"Your labeled evaluation set only has 30 confirmed anomalies. How much do you trust the PR-AUC comparison?"* — not very much on its own; PR-AUC computed from only 30 positive examples has high variance, and a marginal difference between models could easily be noise. Report confidence intervals or bootstrap the comparison, and weight the decision more heavily toward engineering simplicity and maintainability when the statistical evidence is this thin, rather than treating a small numerical edge as decisive.

---

## Red flags that fail you

- Reporting accuracy as the headline metric for an anomaly detection system.
- Not knowing that ROC-AUC can look strong while precision is operationally unusable under extreme imbalance.
- Leaving `nu` or `contamination` at library defaults without connecting them to the actual expected anomaly rate.
- Treating LOF and Isolation Forest as interchangeable — not knowing one catches local, the other global/structural anomalies.
- Setting an autoencoder threshold once and never revisiting it.
- Proposing a full production system with no human-review feedback loop.
- Reaching for a deep autoencoder on simple, low-dimensional tabular data without justifying the added complexity.
- No answer for how the threshold should be chosen relative to actual cost of false positives vs false negatives.

---

## Cheat card

```
FRAMING     supervised (labeled both classes, rare) · semi-supervised (train on NORMAL only,
            flag deviation — the common real case) · unsupervised (no labels, structural assumption)

ISOLATION FOREST   random feature + random split, recursively, until isolated.
  Anomalies isolate in FEWER splits (few, different -> easy to separate by chance).
  sklearn defaults: n_estimators=100, max_samples=min(256,n) — small subsample per tree
  REDUCES swamping/masking, it's not just a speed hack (Liu, Ting & Zhou 2008).
  Fastest/most scalable for tabular data > ~1000 points; largely dimension-insensitive.

LOF         density of point vs density of its k-NEAREST NEIGHBORS (default n_neighbors=20).
            Catches LOCAL anomalies global methods miss. novelty=False by default
            (outlier detection on training set; set novelty=True to score new points).

ONE-CLASS SVM   default nu=0.5 is a TRAP — assumes 50% contamination. Set nu ~ true
                anomaly rate (usually <1-5%). Precision-strong on small/low-dim data,
                degrades on large/high-dim, esp. nonlinear kernels.

AUTOENCODER     train on normal only, reconstruction error (MSE) = anomaly score.
  THRESHOLD (increasing rigor):
    1. mean+3*std of val reconstruction error (inherits skew problem)
    2. 99th percentile on known-clean val set (robust to skew)
    3. optimize on precision-recall tradeoff vs actual cost, using any labeled anomalies
  MUST recalibrate periodically — normal distribution drifts, static threshold rots.

EVALUATION (the interview-decider)
  accuracy         USELESS at real base rates (0.1% anomaly rate -> predict-nothing = 99.9% acc)
  ROC-AUC          MISLEADING under extreme imbalance — FPR denominator (huge TN count) hides
                   large absolute FP counts. 1M normal + 1K fraud, 1% FPR = 10,000 false alarms,
                   10x the real fraud count, barely dents ROC-AUC.
  PR-AUC           precision = TP/(TP+FP), no huge TN denominator to hide behind — TRUST THIS
  precision-at-k   most operationally honest: % of top-k flagged cases that are real, sized to
                   actual review team capacity

PRODUCTION PIPELINE   raw events -> features -> score -> threshold (cost-tuned, NOT static) ->
                      alert -> human review -> confirm/reject -> feeds retraining
  MISSING FEEDBACK LOOP = #1 reason production anomaly systems silently degrade over time

WHEN NOT TO USE   autoencoder on simple low-dim tabular data (Isolation Forest/LOF cheaper,
                  as good) · unsupervised methods when you already have 100s+ labeled anomalies
                  (supervised classifier usually wins) · LOF alone if you also need global
                  anomaly coverage, or vice versa — ensemble both philosophies when needed
```

## Sources

- [IsolationForest — scikit-learn 1.9 documentation](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html) — accessed 2026-08-01
- [Isolation-based Anomaly Detection — Liu, Ting & Zhou (original paper)](https://www.lamda.nju.edu.cn/publication/tkdd11.pdf) — accessed 2026-08-01
- [LocalOutlierFactor — scikit-learn 1.9 documentation](https://scikit-learn.org/stable/modules/generated/sklearn.neighbors.LocalOutlierFactor.html) — accessed 2026-08-01
- [OneClassSVM — scikit-learn 1.9 documentation](https://scikit-learn.org/stable/modules/generated/sklearn.svm.OneClassSVM.html) — accessed 2026-08-01
- [ROC AUC vs Precision-Recall for Imbalanced Data — MachineLearningMastery](https://machinelearningmastery.com/roc-auc-vs-precision-recall-for-imbalanced-data/) — accessed 2026-08-01
- [Computing Anomaly Score Threshold with Autoencoders Pipeline — Springer](https://link.springer.com/chapter/10.1007/978-3-030-13469-3_28) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
