# webcam.py — OpenCV webcam + MediaPipe pose detection + MJPEG stream

import os, math, time, threading, random
import numpy as np

try:
    import cv2
    CV2_OK = True
except ImportError:
    CV2_OK = False

try:
    import mediapipe as mp
    _PoseLandmarker     = mp.tasks.vision.PoseLandmarker
    _PoseLandmarkerOpts = mp.tasks.vision.PoseLandmarkerOptions
    _VisionRunningMode  = mp.tasks.vision.RunningMode
    _BaseOptions        = mp.tasks.BaseOptions
    MP_OK = True
except Exception:
    MP_OK = False

from config import EXERCISES, POSE_CONNECTIONS, MOTIVATIONAL

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task"
)

def _get_model_path():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "pose_landmarker_lite.task")
    if os.path.exists(path):
        return path
    print(f"  [Pose] Downloading model…")
    try:
        import urllib.request
        os.makedirs(os.path.dirname(path), exist_ok=True)
        urllib.request.urlretrieve(MODEL_URL, path)
        print("  [Pose] Model downloaded OK")
        return path
    except Exception as e:
        print(f"  [Pose] Download failed: {e}")
        return None


class WebcamStreamer:
    """
    Opens webcam, runs MediaPipe pose landmarker (async live stream),
    draws skeleton overlay, and streams MJPEG frames via /video_feed.
    Also drives real-time rep counting from detected joint angles.
    """

    def __init__(self):
        self.running    = False
        self.mp_running = False
        self.cap        = None
        self.pose       = None
        self._thread    = None
        self._frame     = None
        self._frame_lock = threading.Lock()
        self._latest_lm  = None
        # set by app.py after /api/start
        self._active    = None
        self._rep_ctr   = None
        self._lock      = None

    def set_active(self, active_dict, rep_counter, lock):
        self._active  = active_dict
        self._rep_ctr = rep_counter
        self._lock    = lock

    def start(self):
        if self.running:
            return True
        if not CV2_OK:
            print("  [Cam] opencv-python not installed — pip install opencv-python")
            return False

        for idx in (0, 1):
            self.cap = cv2.VideoCapture(idx)
            if self.cap.isOpened():
                break
            self.cap.release()
        else:
            print("  [Cam] No webcam found")
            return False

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FPS, 30)

        if MP_OK:
            model_path = _get_model_path()
            if model_path:
                try:
                    def _on_result(result, _img, _ts):
                        if result.pose_landmarks:
                            self._latest_lm = result.pose_landmarks[0]

                    opts = _PoseLandmarkerOpts(
                        base_options=_BaseOptions(model_asset_path=model_path),
                        running_mode=_VisionRunningMode.LIVE_STREAM,
                        result_callback=_on_result,
                        num_poses=1,
                        min_pose_detection_confidence=0.5,
                        min_pose_presence_confidence=0.5,
                        min_tracking_confidence=0.5,
                    )
                    self.pose = _PoseLandmarker.create_from_options(opts)
                    self.mp_running = True
                    print("  [Pose] MediaPipe pose landmarker active")
                except Exception as e:
                    print(f"  [Pose] Init failed: {e}")

        self.running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print("  [Cam] Webcam stream started")
        return True

    def stop(self):
        self.running    = False
        self.mp_running = False
        if self.cap:
            self.cap.release()
            self.cap = None
        if self.pose:
            try: self.pose.close()
            except: pass
            self.pose = None
        self._latest_lm = None
        self._active    = None
        self._rep_ctr   = None
        self._lock      = None

    def get_frame(self):
        with self._frame_lock:
            return self._frame

    @staticmethod
    def _calc_angle(a, b, c):
        pa = np.array([a.x, a.y])
        pb = np.array([b.x, b.y])
        pc = np.array([c.x, c.y])
        ba, bc = pa - pb, pc - pb
        cos = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-8)
        return round(float(np.degrees(np.arccos(np.clip(cos, -1, 1)))), 1)

    def _loop(self):
        ts_ms = 0
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.033)
                continue

            frame = cv2.flip(frame, 1)
            H, W  = frame.shape[:2]
            ts_ms += 33

            # Send to MediaPipe async
            if self.mp_running and self.pose:
                try:
                    rgb    = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                    self.pose.detect_async(mp_img, ts_ms)
                except Exception:
                    pass

            lm = self._latest_lm

            # Draw skeleton
            if lm:
                for (a, b) in POSE_CONNECTIONS:
                    if a < len(lm) and b < len(lm):
                        if lm[a].visibility > 0.3 and lm[b].visibility > 0.3:
                            p1 = (int(lm[a].x * W), int(lm[a].y * H))
                            p2 = (int(lm[b].x * W), int(lm[b].y * H))
                            cv2.line(frame, p1, p2, (59, 130, 246), 2, cv2.LINE_AA)
                for l in lm:
                    if l.visibility > 0.4:
                        cx, cy = int(l.x * W), int(l.y * H)
                        cv2.circle(frame, (cx, cy), 5, (16, 217, 124), -1, cv2.LINE_AA)
                        cv2.circle(frame, (cx, cy), 7, (16, 217, 124),  1, cv2.LINE_AA)

                # Rep counting from real landmarks
                if self._active and self._active.get("running") and self._rep_ctr:
                    ex_key = self._active["exercise"]
                    ex_cfg = EXERCISES.get(ex_key, {})
                    idxs   = ex_cfg.get("angle_landmarks", [11, 13, 15])
                    if all(i < len(lm) and lm[i].visibility > 0.3 for i in idxs):
                        angle = self._calc_angle(lm[idxs[0]], lm[idxs[1]], lm[idxs[2]])
                        reps  = self._rep_ctr.update(angle)
                        stage = self._rep_ctr.stage
                        tgt   = self._active["target_reps"]
                        cal   = round(reps * ex_cfg.get("calories_per_rep", 0.5), 1)
                        dur   = int(time.time() - (self._active["start_time"] or time.time()))
                        prog  = min(100, round(reps / max(1, tgt) * 100))

                        fb = self._active["feedback"]
                        if reps != self._active["reps"]:
                            if reps >= tgt:         fb = "🎉 Set complete! Outstanding work!"
                            elif reps == tgt // 2:  fb = f"Halfway! {reps} reps 🔥"
                            elif reps == tgt - 1:   fb = "One more rep! You've got this!"
                            elif reps % 5 == 0 and reps > 0: fb = random.choice(MOTIVATIONAL)
                            else:                   fb = f"Rep {reps} ✓"

                        with self._lock:
                            self._active.update({
                                "reps": reps, "stage": stage, "angle": angle,
                                "feedback": fb, "calories": cal,
                                "duration": dur, "progress": prog,
                            })
                            if reps >= tgt:
                                self._active["running"] = False
                                self._active["stage"]   = "complete"

                        # Angle arc
                        jb = lm[idxs[1]]
                        bx, by = int(jb.x * W), int(jb.y * H)
                        a1 = math.atan2(int(lm[idxs[0]].y*H)-by, int(lm[idxs[0]].x*W)-bx)
                        a2 = math.atan2(int(lm[idxs[2]].y*H)-by, int(lm[idxs[2]].x*W)-bx)
                        cv2.ellipse(frame, (bx, by), (28, 28), 0,
                                    int(math.degrees(a1)), int(math.degrees(a2)),
                                    (0, 115, 249), 2, cv2.LINE_AA)
                        cv2.putText(frame, f"{angle:.0f}deg",
                                    (bx+32, by-8), cv2.FONT_HERSHEY_SIMPLEX,
                                    0.55, (249, 115, 22), 2, cv2.LINE_AA)

            # HUD overlay
            if self._active and self._active.get("running"):
                name = EXERCISES.get(self._active["exercise"], {}).get("name", "")
                rn   = self._active["reps"]
                tg   = self._active["target_reps"]
                st   = self._active.get("stage", "").upper()
                prog = self._active.get("progress", 0)
                cv2.rectangle(frame, (0, 0), (W, 44), (6, 10, 16), -1)
                cv2.putText(frame, name,            (12, 28),      cv2.FONT_HERSHEY_SIMPLEX, 0.75, (96, 165, 250), 2, cv2.LINE_AA)
                cv2.putText(frame, f"REPS:{rn}/{tg}", (W//2-60,28), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (16, 217, 124), 2, cv2.LINE_AA)
                cv2.putText(frame, st,              (W-120, 28),   cv2.FONT_HERSHEY_SIMPLEX, 0.65, (249, 115, 22), 2, cv2.LINE_AA)
                cv2.rectangle(frame, (0, H-6), (W, H), (22, 33, 50), -1)
                cv2.rectangle(frame, (0, H-6), (int(W*prog/100), H), (16, 217, 124), -1)

            _, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            with self._frame_lock:
                self._frame = jpeg.tobytes()

            time.sleep(0.01)
