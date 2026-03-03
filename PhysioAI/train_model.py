# train_model.py — Data collection & classifier training
#
# Usage:
#   python train_model.py --collect --exercise bicep_curl --samples 300
#   python train_model.py --train
#   python train_model.py --evaluate

import os, csv, json, argparse
import numpy as np
from datetime import datetime
from config import EXERCISES

DATA_FILE  = os.path.join("data",   "exercise_data.csv")
MODEL_FILE = os.path.join("models", "exercise_classifier.pkl")
os.makedirs("data",   exist_ok=True)
os.makedirs("models", exist_ok=True)


def collect(exercise_label, n_samples=300):
    try:
        import cv2
        import mediapipe as mp
    except ImportError:
        print("ERROR: pip install opencv-python mediapipe"); return

    mp_pose = mp.solutions.pose
    mp_draw = mp.solutions.drawing_utils
    cap  = cv2.VideoCapture(0)
    pose = mp_pose.Pose(min_detection_confidence=0.7, min_tracking_confidence=0.7)

    collected  = 0
    recording  = False
    csv_exists = os.path.exists(DATA_FILE)
    f = open(DATA_FILE, "a", newline="")
    w = csv.writer(f)
    if not csv_exists:
        w.writerow([f"{c}{i}" for i in range(33) for c in "xyzv"] + ["label"])

    print(f"\n[Collect] {exercise_label} | SPACE=record  Q=quit\n")
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret: break
        frame = cv2.flip(frame, 1)
        res   = pose.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        color = (0,200,100) if recording else (100,100,200)
        cv2.rectangle(frame, (0,0), (frame.shape[1],50), (0,0,0), -1)
        cv2.putText(frame, f"{exercise_label}  {collected}/{n_samples}", (10,32),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        if recording: cv2.circle(frame, (frame.shape[1]-20,20), 8, (0,0,255), -1)
        if res.pose_landmarks:
            mp_draw.draw_landmarks(frame, res.pose_landmarks, mp_pose.POSE_CONNECTIONS)
            if recording:
                row = [v for lm in res.pose_landmarks.landmark for v in [lm.x,lm.y,lm.z,lm.visibility]]
                w.writerow(row + [exercise_label])
                collected += 1
                if collected >= n_samples:
                    print(f"[Collect] Done — {collected} samples saved"); break
        cv2.imshow("PhysioAI Data Collector", frame)
        key = cv2.waitKey(10) & 0xFF
        if key == ord(" "): recording = not recording; print("Recording…" if recording else "Paused")
        elif key == ord("q"): break

    f.close(); cap.release(); cv2.destroyAllWindows(); pose.close()
    print(f"[Collect] {collected} samples → {DATA_FILE}")


def train():
    try:
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.model_selection import train_test_split, cross_val_score
        from sklearn.preprocessing import StandardScaler
        from sklearn.metrics import classification_report, accuracy_score
        import pickle
    except ImportError:
        print("ERROR: pip install scikit-learn"); return

    if not os.path.exists(DATA_FILE):
        print(f"ERROR: No data at {DATA_FILE}. Run --collect first."); return

    data = np.genfromtxt(DATA_FILE, delimiter=",", skip_header=1, dtype=str)
    X = data[:,:-1].astype(float); y = data[:,-1]
    labels, counts = np.unique(y, return_counts=True)
    print(f"[Train] Classes: {dict(zip(labels,counts))}  Total: {len(y)}")

    X_tr,X_te,y_tr,y_te = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    scaler = StandardScaler()
    X_tr_s = scaler.fit_transform(X_tr); X_te_s = scaler.transform(X_te)

    clf = RandomForestClassifier(n_estimators=150, max_depth=15, random_state=42, n_jobs=-1)
    clf.fit(X_tr_s, y_tr)
    acc = accuracy_score(y_te, clf.predict(X_te_s))
    print(f"\n[Train] Test accuracy: {acc:.2%}")
    print(classification_report(y_te, clf.predict(X_te_s)))

    cv = cross_val_score(clf, scaler.transform(X), y, cv=5)
    print(f"[Train] 5-fold CV: {cv.mean():.2%} ± {cv.std():.2%}")

    with open(MODEL_FILE, "wb") as f:
        pickle.dump({"classifier":clf,"scaler":scaler,"labels":list(labels),
                     "accuracy":float(acc),"trained_at":datetime.now().isoformat()}, f)
    print(f"\n[Train] Model saved → {MODEL_FILE}")


def evaluate():
    import pickle
    if not os.path.exists(MODEL_FILE):
        print(f"ERROR: No model at {MODEL_FILE}. Run --train first."); return
    with open(MODEL_FILE,"rb") as f: d = pickle.load(f)
    print(f"\n[Evaluate] Trained : {d.get('trained_at')}")
    print(f"[Evaluate] Accuracy: {d.get('accuracy',0):.2%}")
    print(f"[Evaluate] Classes : {d.get('labels')}")
    top = np.argsort(d['classifier'].feature_importances_)[::-1][:10]
    print("\n[Evaluate] Top-10 features:")
    for i,j in enumerate(top,1):
        print(f"  {i:2d}. feature #{j}: {d['classifier'].feature_importances_[j]:.4f}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--collect",  action="store_true")
    p.add_argument("--train",    action="store_true")
    p.add_argument("--evaluate", action="store_true")
    p.add_argument("--exercise", default="bicep_curl", choices=list(EXERCISES.keys()))
    p.add_argument("--samples",  type=int, default=300)
    args = p.parse_args()
    if   args.collect:  collect(args.exercise, args.samples)
    elif args.train:    train()
    elif args.evaluate: evaluate()
    else: p.print_help()
