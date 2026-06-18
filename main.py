"""
main.py — Orchestrator process.

Spawns all worker processes, runs the 30Hz control loop,
and is the ONLY process that sends commands to the PiCar-X hardware.
"""

import time
import multiprocessing as mp
from multiprocessing import shared_memory
from ctypes import c_double, c_bool, c_int

from contracts import SensorState, ActionCommand, SystemState
from brain.subsumption import SubsumptionBrain
from vision.lane_detector import lane_detection_process
from vision.sign_detector import sign_detection_process
from sensors.voice import voice_listener
from sensors.ultrasonic import ultrasonic_reader
from web_server import web_server_process


TICK_RATE = 30  # Hz
TICK_INTERVAL = 1.0 / TICK_RATE


def main():
    # ── Shared Memory ──────────────────────────────────────
    lane_offset     = mp.Value(c_double, 0.0)
    lane_curvature  = mp.Value(c_double, 0.0)
    lane_detected   = mp.Value(c_bool, False)
    sign_id         = mp.Value(c_int, 0)
    sign_confidence = mp.Value(c_double, 0.0)
    obstacle_dist   = mp.Value(c_double, 999.0)
    voice_command   = mp.Value(c_int, 0)
    system_running  = mp.Value(c_bool, True)

    current_speed_shm    = mp.Value(c_double, 0.0)
    current_steering_shm = mp.Value(c_double, 0.0)

    # Frame sharing via SharedMemory (zero-copy numpy, ~0.5ms vs ~100ms with Array)
    FRAME_W, FRAME_H = 640, 480
    shm = shared_memory.SharedMemory(create=True, size=FRAME_W * FRAME_H * 3)
    frame_lock = mp.Lock()

    # ── Spawn Worker Processes ─────────────────────────────
    workers = [
        mp.Process(
            target=lane_detection_process,
            args=(lane_offset, lane_curvature, lane_detected,
                  system_running, shm.name, frame_lock, FRAME_W, FRAME_H),
            daemon=True, name="P1-LaneDetect"
        ),
        mp.Process(
            target=sign_detection_process,
            args=(sign_id, sign_confidence, system_running,
                  shm.name, frame_lock, FRAME_W, FRAME_H),
            daemon=True, name="P2-SignDetect"
        ),
        mp.Process(
            target=voice_listener,
            args=(voice_command, system_running),
            daemon=True, name="P3-Voice"
        ),
        mp.Process(
            target=web_server_process,
            args=(current_speed_shm, current_steering_shm, shm.name, frame_lock, FRAME_W, FRAME_H),
            daemon=True, name="P5-WebServer"
        )
        # Note: ultrasonic handled in main loop or separate thread
    ]

    for w in workers:
        w.start()

    # ── Initialize Hardware & Brain ────────────────────────
    # pyrefly: ignore [missing-import]
    from picarx import Picarx
    px = Picarx()
    brain = SubsumptionBrain()
    current_state = SystemState.IDLE
    current_speed = 0.0
    current_steering = 0.0
    last_ultrasonic_read = 0.0  # Throttle ultrasonic to ~10Hz

    print("[Orchestrator] All systems GO. Waiting for START command...")

    try:
        while system_running.value:
            tick_start = time.monotonic()

            # 1. Read ultrasonic (~10Hz — each read can block up to 30ms,
            #    so don't call every tick or it eats the 33ms budget)
            now = time.monotonic()
            if now - last_ultrasonic_read >= 0.1:  # 10Hz
                try:
                    dist = px.ultrasonic.read()
                    if dist is not None and dist > 0:
                        obstacle_dist.value = dist
                except Exception:
                    pass
                last_ultrasonic_read = now

            # 2. Build SensorState DTO from shared memory
            state = SensorState(
                lane_offset=lane_offset.value,
                lane_curvature=lane_curvature.value,
                lane_detected=lane_detected.value,
                sign_id=sign_id.value,
                sign_confidence=sign_confidence.value,
                obstacle_dist_cm=obstacle_dist.value,
                voice_command=voice_command.value,
                current_state=current_state,
                speed=current_speed,
                steering_angle=current_steering,
            )

            # 3. Brain decides
            action: ActionCommand = brain.decide_next_action(state)

            # 4. Execute ActionCommand on hardware
            px.set_dir_servo_angle(action.steering_angle)
            if action.direction == 1:
                px.forward(action.speed)
            elif action.direction == -1:
                px.backward(action.speed)
            else:
                px.stop()

            # 5. Update state
            current_state = action.new_state
            current_speed = action.speed
            current_steering = action.steering_angle

            current_speed_shm.value = action.speed
            current_steering_shm.value = action.steering_angle

            # 6. Consume acknowledged signals
            if action.sign_consumed:
                sign_id.value = 0
                sign_confidence.value = 0.0
            if action.voice_consumed:
                voice_command.value = 0

            # 7. Sleep to maintain tick rate
            elapsed = time.monotonic() - tick_start
            sleep_time = TICK_INTERVAL - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\n[Orchestrator] Shutdown requested.")
    finally:
        system_running.value = False
        px.stop()
        px.set_dir_servo_angle(0)
        for w in workers:
            w.join(timeout=2.0)
        shm.close()
        shm.unlink()  # Free the shared memory block (only the creator calls unlink)
        print("[Orchestrator] All processes terminated. Goodbye.")


if __name__ == "__main__":
    main()
