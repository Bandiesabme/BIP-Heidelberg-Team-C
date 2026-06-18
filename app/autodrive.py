import time

# Settings adjustable in real-time
autodrive_enabled = False
target_speed = 8
max_steering_angle = 25
camera_pan = 0
camera_tilt = 0
turn_frames = 30


# Steering smoothing / PD tuning (adjust on the track)
steering_smoothing = 0.6   # 0 = no smoothing (raw), 0.9 = very smooth/laggy. Start 0.6
kd = 8.0                   # derivative gain: damps wobble. Raise if it oscillates
lost_lane_grace_frames = 6 # how many missing-lane frames to coast before stopping

# Dynamic status
current_speed = 0
current_angle = 0.0

# Internal state
_smoothed_error = 0.0
_last_error = 0.0
_lost_counter = 0
_last_sent_speed = None
_stopped_for_sign = False   # latched True permanently once a close stop sign is seen
_turning_state = None       # None, 'left', or 'right'
_turn_frames_remaining = 0

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
    """Force a turn in the given direction ('left' or 'right') for the set duration."""
    global _turning_state, _turn_frames_remaining, turn_frames
    _turning_state = direction
    _turn_frames_remaining = turn_frames
    print(f"[Autodrive] Triggering forced {direction} turn for {turn_frames} frames.")

def update(lane_found, steering_error):
    global current_speed, current_angle
    global _smoothed_error, _last_error, _lost_counter
    global _turning_state, _turn_frames_remaining

    if not px:
        return

    # Permanent stop: a stop sign was seen up close. End of run.
    if _stopped_for_sign:
        _drive(0)
        current_speed = 0
        px.set_dir_servo_angle(0.0)
        current_angle = 0.0
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
        _turning_state = None
        _turn_frames_remaining = 0
        return

    # Handle forced turn maneuver
    if _turning_state is not None:
        _turn_frames_remaining -= 1
        if _turn_frames_remaining <= 0:
            _turning_state = None
            print("[Autodrive] Forced turn complete, returning to lane following.")
        else:
            # Force steering
            steering_angle = -max_steering_angle if _turning_state == 'left' else max_steering_angle
            current_angle = steering_angle
            px.set_dir_servo_angle(current_angle)
            _drive(target_speed)
            current_speed = target_speed
            
            if _turn_frames_remaining % 5 == 0:
                print(f"[Autodrive] State: TURNING {_turning_state.upper()} | Angle: {current_angle} | Frames left: {_turn_frames_remaining}")
            
            # Keep the error history somewhat zeroed so it doesn't snap back violently
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
        
        # Throttled print (approx every 30 frames)
        if int(time.time() * 10) % 10 == 0:
            print(f"[Autodrive] State: LANE_TRACKING | Angle: {current_angle:.2f} | Error: {steering_error:.2f}")

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
    global _turning_state, _turn_frames_remaining
    autodrive_enabled = enabled
    if enabled:
        # fresh run: clear any latched stop from the previous run
        _stopped_for_sign = False
        _turning_state = None
        _turn_frames_remaining = 0
    if not enabled and px:
        _drive(0)
        current_speed = 0
        _smoothed_error = 0.0
        _last_error = 0.0
        _lost_counter = 0
        _turning_state = None
        _turn_frames_remaining = 0


def set_speed(speed):
    global target_speed
    target_speed = speed


def set_max_angle(angle):
    global max_steering_angle
    max_steering_angle = angle

def set_turn_frames(frames):
    global turn_frames
    turn_frames = frames