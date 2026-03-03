# session_store.py — Thread-safe in-memory workout session history

import time
import threading
from datetime import datetime
from config import EXERCISES


class SessionStore:

    def __init__(self):
        self._sessions = []
        self._lock = threading.Lock()

    def save(self, active):
        ex_key = active.get("exercise", "")
        record = {
            "id":           f"s{int(time.time()*1000)}",
            "patient":      active.get("patient", ""),
            "exercise":     EXERCISES.get(ex_key, {}).get("name", ex_key),
            "exercise_key": ex_key,
            "reps":         active.get("reps", 0),
            "target":       active.get("target_reps", 0),
            "duration":     active.get("duration", 0),
            "calories":     round(active.get("calories", 0), 1),
            "date":         datetime.now().strftime("%Y-%m-%d"),
            "time":         datetime.now().strftime("%H:%M"),
            "score":        min(100, round(
                active.get("reps", 0) / max(1, active.get("target_reps", 1)) * 100
            )),
        }
        with self._lock:
            self._sessions.append(record)
        return record

    def get_history(self, patient=""):
        with self._lock:
            data = list(reversed(self._sessions[-50:]))
        if patient:
            key = patient.lower().strip()
            data = [s for s in data if s["patient"].lower() == key]
        return data

    def get_stats(self):
        with self._lock:
            sessions = list(self._sessions)
        breakdown = {}
        for s in sessions:
            breakdown[s["exercise"]] = breakdown.get(s["exercise"], 0) + s["reps"]
        return {
            "total_sessions":     len(sessions),
            "total_reps":         sum(s["reps"]     for s in sessions),
            "total_calories":     round(sum(s["calories"] for s in sessions), 1),
            "exercise_breakdown": breakdown,
        }
