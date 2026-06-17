"""config/settings.py — All tunable parameters in one place."""

# ── Camera ──
FRAME_WIDTH = 640
FRAME_HEIGHT = 480
CAMERA_INDEX = 0

# ── Lane Detection ──
ROI_TOP_PERCENT = 0.5          # Crop top 50% of frame
CANNY_LOW = 50
CANNY_HIGH = 150
HOUGH_THRESHOLD = 50
HOUGH_MIN_LINE_LENGTH = 50
HOUGH_MAX_LINE_GAP = 150

# ── Sign Detection ──
YOLO_INPUT_SIZE = 320
SIGN_CONFIDENCE_THRESHOLD = 0.6
SIGN_MODEL_PATH = "models/yolo/best_ncnn_model"

# ── PID ──
PID_KP = 0.8
PID_KI = 0.01
PID_KD = 0.3

# ── Driving ──
BASE_SPEED = 30
MIN_SPEED = 15
MAX_SPEED = 50
MAX_STEERING_ANGLE = 30        # degrees
FALLBACK_SPEED = 15

# ── Obstacle ──
OBSTACLE_STOP_CM = 25.0
OBSTACLE_SLOW_CM = 50.0

# ── Timing ──
TICK_RATE_HZ = 30
STOP_SIGN_WAIT_SEC = 3.0
TURN_DURATION_SEC = 2.0

# ── Voice ──
VOSK_MODEL_PATH = "models/vosk/vosk-model-small-en-us-0.15"
VOICE_SAMPLE_RATE = 16000
