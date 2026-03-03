# ml_engine.py — Exercise classifier (Random Forest) + Rep counter

import time
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from config import EXERCISES


class ExerciseClassifier:
    """
    Random Forest trained on synthetic pose data at startup.
    Feature vector: 33 landmarks x 3 (x,y,z) = 99 floats.
    Replace synthetic data with real recordings for production.
    """

    def __init__(self):
        self.labels = list(EXERCISES.keys())
        self.scaler = StandardScaler()
        self.clf = None
        self._train()

    def _make_synthetic(self, ex_key, n=150):
        np.random.seed(hash(ex_key) % 2**32)
        base = np.random.randn(n, 99) * 0.03
        biases = {
            "bicep_curl":     {13*3: 0.35,   14*3: -0.35},
            "squat":          {25*3: -0.4,   26*3: -0.4,   23*3: 0.3},
            "lateral_raise":  {11*3+1: -0.45, 12*3+1: -0.45},
            "bench_press":    {15*3: 0.3,    16*3: 0.3,    13*3: -0.2},
            "leg_raise":      {25*3+1: -0.5,  26*3+1: -0.5},
            "shoulder_press": {15*3+1: -0.55, 16*3+1: -0.55},
        }
        for col, val in biases.get(ex_key, {}).items():
            if col < 99:
                base[:, col] += val + np.random.randn(n) * 0.05
        return base

    def _train(self):
        X_parts, y_parts = [], []
        for label in self.labels:
            X_parts.append(self._make_synthetic(label))
            y_parts.extend([label] * 150)
        X = np.vstack(X_parts)
        y = np.array(y_parts)
        idx = np.random.RandomState(42).permutation(len(y))
        X, y = X[idx], y[idx]
        Xs = self.scaler.fit_transform(X)
        self.clf = RandomForestClassifier(
            n_estimators=120, max_depth=12,
            min_samples_split=3, random_state=42, n_jobs=-1
        )
        self.clf.fit(Xs, y)
        acc = self.clf.score(Xs, y)
        print(f"  [ML] Classifier ready — {len(self.labels)} exercises, accuracy: {acc:.1%}")

    def predict(self, landmarks_flat):
        """
        landmarks_flat: list of 99 floats [x0,y0,z0, x1,y1,z1, ...]
        Returns: (exercise_key, confidence)
        """
        X = np.array(landmarks_flat).reshape(1, -1)
        Xs = self.scaler.transform(X)
        pred = self.clf.predict(Xs)[0]
        conf = float(self.clf.predict_proba(Xs).max())
        return pred, conf


class RepCounter:
    """
    Stage-based rep counter: UP -> DOWN -> UP = 1 rep.
    600ms debounce prevents double-counting.
    """

    def __init__(self, ex_key):
        ex = EXERCISES.get(ex_key, {})
        self.up_thresh   = ex.get("up_threshold",   155)
        self.down_thresh = ex.get("down_threshold",  50)
        self.count = 0
        self.stage = "up"
        self._last_ts = 0.0

    def update(self, angle):
        now = time.time()
        if self.stage == "up" and angle < self.down_thresh:
            self.stage = "down"
        elif self.stage == "down" and angle > self.up_thresh:
            if now - self._last_ts > 0.6:
                self.stage = "up"
                self.count += 1
                self._last_ts = now
        return self.count

    def reset(self):
        self.count = 0
        self.stage = "up"
        self._last_ts = 0.0
