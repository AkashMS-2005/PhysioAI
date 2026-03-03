# PhysioAI — AI-Based Remote Rehabilitation Assistant

An AI-powered physiotherapy platform that uses your **webcam + MediaPipe pose detection** to track exercises, count reps in real time, and give voice feedback — all running locally in your browser.

![PhysioAI Dashboard](https://img.shields.io/badge/Python-3.10+-blue?logo=python) ![Flask](https://img.shields.io/badge/Flask-3.0-green?logo=flask) ![MediaPipe](https://img.shields.io/badge/MediaPipe-0.10-orange) ![OpenCV](https://img.shields.io/badge/OpenCV-4.8-red?logo=opencv)

---

## Features

- **Live webcam pose detection** via OpenCV + MediaPipe (33 body landmarks)
- **6 exercises** — Bicep Curl, Squat, Lateral Raise, Bench Press, Leg Raise, Shoulder Press
- **Real-time rep counting** using joint angle state machine (UP→DOWN→UP)
- **Random Forest classifier** — identifies exercise from pose landmarks
- **Voice feedback** — announces reps, motivational messages, set completion
- **Session history** — tracks reps, calories, duration per patient
- **Demo mode** — animated skeleton when no webcam available

---

## Project Structure

```
PhysioAI/
├── app.py              # Flask server & API routes
├── config.py           # Exercise definitions & constants
├── ml_engine.py        # Random Forest classifier + RepCounter
├── webcam.py           # OpenCV capture + MediaPipe + MJPEG stream
├── session_store.py    # In-memory session history & stats
├── train_model.py      # Data collection & model training CLI
├── requirements.txt
├── templates/
│   └── index.html      # Dashboard UI
├── static/
│   ├── css/style.css   # Styling
│   └── js/app.js       # Frontend logic
├── models/             # Trained model files (auto-downloaded)
└── data/               # Training data CSV
```

---

## Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Run
```bash
python app.py
```
Browser opens automatically at **http://localhost:5000**

---

## How to Use

1. Enter **patient name**
2. Select an **exercise** from the grid
3. Set **target reps** with the slider
4. Click **▶ START SESSION**
5. Allow camera access when prompted
6. Perform the exercise — reps are counted automatically!

---

## Training Your Own Model

Collect real pose data for better accuracy:

```bash
# Step 1: Record 300 samples per exercise
python train_model.py --collect --exercise bicep_curl --samples 300
python train_model.py --collect --exercise squat --samples 300
# ... repeat for all 6 exercises

# Step 2: Train the classifier
python train_model.py --train

# Step 3: Evaluate
python train_model.py --evaluate
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Dashboard |
| GET | `/video_feed` | MJPEG webcam stream |
| POST | `/api/start` | Start workout session |
| POST | `/api/stop` | Stop session |
| GET | `/api/status` | Live workout state |
| POST | `/api/landmarks` | Send pose landmarks (browser fallback) |
| GET | `/api/history` | Session history |
| GET | `/api/stats` | Aggregate statistics |
| GET | `/api/cam_status` | Camera & model status |

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.10+, Flask |
| Pose Detection | MediaPipe Tasks (PoseLandmarker) |
| Computer Vision | OpenCV |
| ML Classifier | scikit-learn RandomForest |
| Frontend | HTML5, CSS3, Vanilla JS |
| Video Stream | MJPEG over HTTP |
| Voice | Web Speech API |
