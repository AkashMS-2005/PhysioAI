# config.py — Exercise definitions, pose connections, motivational messages

EXERCISES = {
    "bicep_curl": {
        "name": "Bicep Curl", "icon": "💪",
        "description": "Strengthen biceps & forearms",
        "target_reps": 12, "calories_per_rep": 0.5,
        "angle_landmarks": [11, 13, 15],
        "up_threshold": 155, "down_threshold": 50,
    },
    "squat": {
        "name": "Squat", "icon": "🦵",
        "description": "Lower body strength & mobility",
        "target_reps": 10, "calories_per_rep": 0.8,
        "angle_landmarks": [23, 25, 27],
        "up_threshold": 165, "down_threshold": 95,
    },
    "lateral_raise": {
        "name": "Lateral Raise", "icon": "🙆",
        "description": "Shoulder mobility & strength",
        "target_reps": 12, "calories_per_rep": 0.4,
        "angle_landmarks": [23, 11, 13],
        "up_threshold": 150, "down_threshold": 35,
    },
    "bench_press": {
        "name": "Bench Press", "icon": "🏋️",
        "description": "Chest & triceps strength",
        "target_reps": 10, "calories_per_rep": 0.9,
        "angle_landmarks": [11, 13, 15],
        "up_threshold": 160, "down_threshold": 85,
    },
    "leg_raise": {
        "name": "Leg Raise", "icon": "🦿",
        "description": "Core & hip flexor rehab",
        "target_reps": 15, "calories_per_rep": 0.6,
        "angle_landmarks": [11, 23, 25],
        "up_threshold": 75, "down_threshold": 15,
    },
    "shoulder_press": {
        "name": "Shoulder Press", "icon": "🏅",
        "description": "Overhead strength & stability",
        "target_reps": 10, "calories_per_rep": 0.7,
        "angle_landmarks": [13, 11, 23],
        "up_threshold": 165, "down_threshold": 90,
    },
}

# MediaPipe skeleton connections
POSE_CONNECTIONS = [
    (0,1),(1,2),(2,3),(3,7),(0,4),(4,5),(5,6),(6,8),
    (9,10),(11,12),(11,13),(13,15),(15,17),(15,19),(17,19),
    (12,14),(14,16),(16,18),(16,20),(18,20),
    (11,23),(12,24),(23,24),
    (23,25),(24,26),(25,27),(26,28),(27,29),(28,30),(29,31),(30,32),
]

MOTIVATIONAL = [
    "Great form! Keep it up!",
    "You're doing amazing!",
    "Halfway there — push through!",
    "Excellent movement!",
    "Your consistency builds strength!",
    "Perfect rep! Stay steady!",
    "Breathe and keep moving!",
    "You've got this!",
]
