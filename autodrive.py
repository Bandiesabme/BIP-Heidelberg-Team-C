import time

# Settings adjustable in real-time
autodrive_enabled = False
target_speed = 8
max_steering_angle = 25
camera_pan = 0
camera_tilt = 0

# Steering smoothing / PD tuning (adjust on the track)
steering_smoothing = 0.6   # 0 = no smoothing (raw), 0.9 = very smooth/laggy. Start 0.6
kd = 8.0                   # derivative gain: damps wobble. Raise if it oscillates
lost_lane_grace_frames = 6 # how many missing-lane frames to coast before stopping

# Turn maneuver tuning (hardcoded, tune on the track).
# The PiCar-X is Ackermann (front wheels steer like a car), so a "90 turn"
# is: drive straight a bit to reach the corner, then lock steering and drive
# forward through the bend for a set time, then resume lane following.
turn_approach_sec = 3.2    # drive straight this long after trigger (reach the corner).
                           # trigger fires early (small sign), so this covers the
                           # distance from seeing the sign to actually being at the corner
turn_duration_sec = 1.8    # how long to hold the turn (longer = gentler arc)
turn_speed = 5             # speed during the approach + turn (slower = smoother)
turn_lock_angle = 22       # steering angle during the turn (deg). softer than full lock
turn_ramp_sec = 0.5        # ease steering in over this long (and back out at the end)
                           # so the car arcs into the turn instead of snapping to lock

# Dynamic status
current_speed = 0
current_angle = 0.0

# Internal state
_smoothed_error = 0.0
_last_error = 0.0
_lost_counter = 0
_last_sent_speed = None
_stopped_for_sign = False   # latched True permanently once a close stop sign is seen

# Turn state machine: None (normal) -> "approach" -> "turning" -> back to None
_turn_phase = None
_turn_dir = 0               # +1 = right, -1 = left
_turn_phase_start = 0.0

px = None


def set_pan(angle):
    global camera_pan
    camera_pan = angle
    if not px:
        return
    if hasattr(px, 'set_cam_pan_angle'):
        px.set_cam_pan_angle(angle)
    elif hasattr(px, 'set_camera_servo1_angle'):
        px.set_camera_servo1_angle(angle)
    else:
        print("[Picarx] No pan servo method found.")


def set_tilt(angle):
    global camera_tilt
    camera_tilt = angle
    if not px:
        return
    if hasattr(px, 'set_cam_tilt_angle'):
        px.set_cam_tilt_angle(angle)
    elif hasattr(px, 'set_camera_servo2_angle'):
        px.set_camera_servo2_angle(angle)
    else:
        print("[Picarx] No tilt servo method found.")


def init_picarx():
    global px
    try:
        from picarx import Picarx
        px = Picarx()
        print("[Picarx] Picarx client initialized successfully.")
        try:
            set_pan(camera_pan)
            set_tilt(camera_tilt)
        except Exception as e:
            print(f"Error setting initial camera angle: {e}")
    except Exception as e:
        print(f"[Picarx] Could not initialize Picarx ({e}). Using mock client.")
        class MockPicarx:
            def __init__(self):
                print("[MockPicarx] Mock client active.")
            def set_dir_servo_angle(self, angle):
                pass
            def set_motor_speed(self, motor, speed):
                pass
            def forward(self, speed):
                pass
            def stop(self):
                pass
            def set_camera_servo1_angle(self, angle):
                pass
            def set_camera_servo2_angle(self, angle):
                pass
            def set_cam_pan_angle(self, angle):
                pass
            def set_cam_tilt_angle(self, angle):
                pass
        px = MockPicarx()


def _drive(speed):
    """Only send forward() when the speed actually changes (avoids stutter)."""
    global _last_sent_speed
    if speed != _last_sent_speed:
        if speed == 0:
            px.stop()
        else:
            px.forward(speed)
        _last_sent_speed = speed


def trigger_stop():
    """Latch a permanent stop (called when a close stop sign is detected)."""
    global _stopped_for_sign
    _stopped_for_sign = True


def trigger_turn(direction):
    """Begin a turn maneuver. direction: 'right' or 'left'.
    Ignored if a turn is already in progress or we're stopped."""
    global _turn_phase, _turn_dir, _turn_phase_start
    if _turn_phase is not None or _stopped_for_sign:
        return
    _turn_dir = 1 if direction == "right" else -1
    _turn_phase = "approach"
    _turn_phase_start = time.time()
    print(f"[Turn] Starting {direction} turn (approach).")


def _run_turn():
    """Drive the turn state machine for one tick. Returns True if a turn is
    active (and it handled driving this frame), False if not turning."""
    global _turn_phase, _turn_phase_start, current_speed, current_angle

    if _turn_phase is None:
        return False

    now = time.time()
    elapsed = now - _turn_phase_start

    if _turn_phase == "approach":
        # Keep lane-following during the approach so the car stays on the line
        # until it's time to turn (don't drive blindly straight off the lane).
        if elapsed >= turn_approach_sec:
            _turn_phase = "turning"
            _turn_phase_start = now
            print("[Turn] Turning.")
            return True
        return False  # let normal lane-following handle this frame

    if _turn_phase == "turning":
        # Ease the steering IN at the start and OUT at the end so the car
        # arcs smoothly through the corner instead of snapping to full lock.
        target = _turn_dir * turn_lock_angle
        if elapsed < turn_ramp_sec:
            # ramp in: 0 -> target over turn_ramp_sec
            frac = elapsed / turn_ramp_sec
            angle = target * frac
        elif elapsed > turn_duration_sec - turn_ramp_sec:
            # ramp out: target -> 0 over the last turn_ramp_sec
            remaining = turn_duration_sec - elapsed
            frac = max(0.0, remaining / turn_ramp_sec)
            angle = target * frac
        else:
            # hold full turn angle in the middle
            angle = target
        px.set_dir_servo_angle(angle)
        current_angle = angle
        _drive(turn_speed)
        current_speed = turn_speed
        if elapsed >= turn_duration_sec:
            _turn_phase = None
            print("[Turn] Done, resuming lane following.")
        return True

    return False


def update(lane_found, steering_error):
    global current_speed, current_angle
    global _smoothed_error, _last_error, _lost_counter

    if not px:
        return

    # Permanent stop: a stop sign was seen up close. End of run.
    if _stopped_for_sign:
        _drive(0)
        current_speed = 0
        px.set_dir_servo_angle(0.0)
        current_angle = 0.0
        return

    # Turn maneuver in progress: it overrides lane following entirely.
    if _run_turn():
        return

    if not autodrive_enabled:
        # Autodrive disabled: stop and center wheels
        _drive(0)
        current_speed = 0
        px.set_dir_servo_angle(0.0)
        current_angle = 0.0
        _smoothed_error = 0.0
        _last_error = 0.0
        _lost_counter = 0
        return

    if lane_found:
        _lost_counter = 0

        # Low-pass filter on the error to kill per-frame detection noise
        _smoothed_error = (
            steering_smoothing * _smoothed_error
            + (1.0 - steering_smoothing) * steering_error
        )

        # PD steering: proportional on the smoothed error + derivative damping
        derivative = _smoothed_error - _last_error
        control = _smoothed_error * max_steering_angle + kd * derivative
        _last_error = _smoothed_error

        # Clamp to the servo's safe range
        steering_angle = max(-max_steering_angle, min(max_steering_angle, control))
        current_angle = steering_angle

        px.set_dir_servo_angle(current_angle)
        _drive(target_speed)
        current_speed = target_speed

    else:
        # Lane lost: don't stop instantly. Dashed center lines drop out
        # constantly. Coast on the last steering angle for a few frames.
        _lost_counter += 1
        if _lost_counter <= lost_lane_grace_frames:
            slow = max(1, int(target_speed * 0.7))
            px.set_dir_servo_angle(current_angle)
            _drive(slow)
            current_speed = slow
        else:
            # Genuinely lost: stop
            _drive(0)
            current_speed = 0


def set_autodrive(enabled):
    global autodrive_enabled, current_speed
    global _smoothed_error, _last_error, _lost_counter, _stopped_for_sign
    global _turn_phase, _turn_dir
    autodrive_enabled = enabled
    if enabled:
        # fresh run: clear any latched stop / turn from the previous run
        _stopped_for_sign = False
        _turn_phase = None
        _turn_dir = 0
    if not enabled and px:
        _drive(0)
        current_speed = 0
        _smoothed_error = 0.0
        _last_error = 0.0
        _lost_counter = 0
        _turn_phase = None


def set_speed(speed):
    global target_speed
    target_speed = speed


def set_max_angle(angle):
    global max_steering_angle
    max_steering_angle = angle