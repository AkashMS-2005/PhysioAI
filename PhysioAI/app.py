# app.py — PhysioAI Flask application
# Run: python app.py  →  open http://localhost:5000

import sys, os, time, math, random, threading, webbrowser
import importlib.util

# Dependency check
def _check():
    missing = [
        p for p, m in [("flask","flask"),("scikit-learn","sklearn"),("numpy","numpy")]
        if importlib.util.find_spec(m) is None
    ]
    if missing:
        print(f"\n❌ Missing: {', '.join(missing)}\n Run: pip install {' '.join(missing)}\n")
        sys.exit(1)

_check()

import numpy as np
from flask import Flask, render_template, Response, request, jsonify
from config import EXERCISES, MOTIVATIONAL
from ml_engine import ExerciseClassifier, RepCounter
from webcam import WebcamStreamer, CV2_OK, MP_OK
from session_store import SessionStore

app      = Flask(__name__)
_store   = SessionStore()
_cam     = WebcamStreamer()
_clf     = None
_rep_ctr = None
_lock    = threading.Lock()

active = {
    "running": False, "patient": "", "exercise": "",
    "reps": 0, "stage": "ready", "target_reps": 10,
    "start_time": None, "feedback": "Ready to start",
    "angle": 0, "progress": 0, "calories": 0.0,
    "duration": 0, "confidence": 0.0,
}

def get_clf():
    global _clf
    if _clf is None:
        _clf = ExerciseClassifier()
    return _clf


# ── Routes ─────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/exercises")
def api_exercises():
    return jsonify(EXERCISES)


@app.route("/api/cam_status")
def api_cam_status():
    return jsonify({"running": _cam.running, "cv2": CV2_OK, "mediapipe": MP_OK and _cam.mp_running})


@app.route("/api/cam_start", methods=["POST"])
def api_cam_start():
    ok = _cam.start()
    return jsonify({"ok": ok, "cv2": CV2_OK, "mediapipe": MP_OK})


@app.route("/api/cam_stop", methods=["POST"])
def api_cam_stop():
    _cam.stop()
    return jsonify({"ok": True})


@app.route("/video_feed")
def video_feed():
    def gen():
        while True:
            frame = _cam.get_frame()
            if frame:
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            time.sleep(0.033)
    return Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/api/start", methods=["POST"])
def api_start():
    global _rep_ctr
    data    = request.get_json()
    patient = data.get("patient", "Patient").strip()
    ex_key  = data.get("exercise", "bicep_curl")
    target  = int(data.get("target_reps", EXERCISES.get(ex_key, {}).get("target_reps", 10)))

    with _lock:
        active.update({
            "running": True, "patient": patient, "exercise": ex_key,
            "reps": 0, "stage": "up", "target_reps": target,
            "start_time": time.time(),
            "feedback": f"Get ready — {EXERCISES[ex_key]['name']}!",
            "angle": EXERCISES[ex_key]["up_threshold"],
            "progress": 0, "calories": 0.0, "duration": 0, "confidence": 0.0,
        })
        _rep_ctr = RepCounter(ex_key)

    if CV2_OK and not _cam.running:
        _cam.start()
    _cam.set_active(active, _rep_ctr, _lock)

    return jsonify({"status": "started", "exercise": ex_key, "target": target})


@app.route("/api/landmarks", methods=["POST"])
def api_landmarks():
    """Receives pose data from browser (fallback when no server cam)."""
    global _rep_ctr
    if not active["running"]:
        return jsonify(active)

    data      = request.get_json()
    landmarks = data.get("landmarks", [])
    ex_key    = active["exercise"]
    ex_cfg    = EXERCISES.get(ex_key, {})

    # Simulated angle if no real landmarks
    if not landmarks or len(landmarks) < 33:
        up_a  = ex_cfg.get("up_threshold", 155)
        dn_a  = ex_cfg.get("down_threshold", 50)
        angle = round((up_a+dn_a)/2 + (up_a-dn_a)/2 * math.sin(time.time() * math.pi * 0.9), 1)
    else:
        idxs = ex_cfg.get("angle_landmarks", [11, 13, 15])
        def lv(i): l=landmarks[i]; return [l["x"],l["y"],l.get("z",0)]
        a,b,c = lv(idxs[0]),lv(idxs[1]),lv(idxs[2])
        ba = np.array(a[:2])-np.array(b[:2])
        bc = np.array(c[:2])-np.array(b[:2])
        cos = np.dot(ba,bc)/(np.linalg.norm(ba)*np.linalg.norm(bc)+1e-8)
        angle = round(float(np.degrees(np.arccos(np.clip(cos,-1,1)))),1)

    if _rep_ctr is None:
        _rep_ctr = RepCounter(ex_key)

    reps   = _rep_ctr.update(angle)
    stage  = _rep_ctr.stage
    target = active["target_reps"]

    conf = active["confidence"]
    if landmarks and int(time.time()*10)%10 == 0:
        try:
            flat = [v for l in landmarks[:33] for v in [l["x"],l["y"],l.get("z",0)]]
            _, conf = get_clf().predict(flat)
        except: pass

    fb = active["feedback"]
    if reps != active["reps"]:
        if reps >= target:        fb = "🎉 Set complete! Outstanding work!"
        elif reps == target//2:   fb = f"Halfway! {reps} reps done 🔥"
        elif reps == target-1:    fb = "One more rep! You've got this!"
        elif reps%5==0 and reps>0:fb = random.choice(MOTIVATIONAL)
        else:                     fb = f"Rep {reps} ✓"

    cal  = round(reps * ex_cfg.get("calories_per_rep", 0.5), 1)
    dur  = int(time.time() - (active["start_time"] or time.time()))
    prog = min(100, round(reps / max(1, target) * 100))
    done = reps >= target

    with _lock:
        active.update({"reps":reps,"stage":stage,"angle":angle,"feedback":fb,
                        "calories":cal,"duration":dur,"progress":prog,"confidence":conf})
        if done:
            active["running"] = False
            active["stage"]   = "complete"

    if done:
        _store.save(active)

    return jsonify(dict(active))


@app.route("/api/stop", methods=["POST"])
def api_stop():
    with _lock:
        was = active["running"]
        active["running"] = False
        active["stage"]   = "stopped"
    if was and active["reps"] > 0:
        _store.save(active)
    _cam.stop()
    return jsonify({"status": "stopped", "reps": active["reps"]})


@app.route("/api/status")
def api_status():
    return jsonify(dict(active))


@app.route("/api/history")
def api_history():
    return jsonify(_store.get_history(request.args.get("patient","")))


@app.route("/api/stats")
def api_stats():
    return jsonify(_store.get_stats())


# ── Entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║           PhysioAI — Rehabilitation Assistant            ║")
    print("╠══════════════════════════════════════════════════════════╣")

    get_clf()

    print(f"║  {'✓ OpenCV webcam ready' if CV2_OK else '⚠ pip install opencv-python':<54}║")
    print(f"║  {'✓ MediaPipe pose ready' if MP_OK else '⚠ pip install mediapipe':<54}║")

    print("║  ✓ Flask server starting...                              ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()

    # Use dynamic port for cloud deployment
    port = int(os.environ.get("PORT", 10000))

    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
