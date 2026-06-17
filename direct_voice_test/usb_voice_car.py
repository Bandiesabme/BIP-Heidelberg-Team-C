import time
from picarx import Picarx
from picarx.stt import Vosk

px = Picarx()
SPEED = 20


def stop_car():
    px.stop()
    px.set_dir_servo_angle(0)


def parse_command(text):
    text = text.lower().strip()

    if "start" in text:
        return "start"

    if "stop" in text:
        return "stop"

    if "pause" in text:
        return "pause"

    if "continue" in text:
        return "continue"

    return None


def execute_command(command):
    if command == "start":
        px.set_dir_servo_angle(0)
        px.forward(SPEED)
        print("[CAR] start -> moving forward")

    elif command == "continue":
        px.set_dir_servo_angle(0)
        px.forward(SPEED)
        print("[CAR] continue -> moving forward")

    elif command == "pause":
        stop_car()
        print("[CAR] pause -> stopped")

    elif command == "stop":
        stop_car()
        print("[CAR] stop -> stopped")


try:
    print("[VOICE] Loading Vosk...")
    vosk = Vosk(language="en-us")

    print("[VOICE] Ready.")
    print("Say: start, stop, pause, continue")

    stop_car()

    while True:
        print("\nListening...")
        result = vosk.listen(stream=False)

        print("[HEARD]", result)

        command = parse_command(result)

        if command is not None:
            print("[COMMAND]", command)
            execute_command(command)
        else:
            print("[VOICE] No valid command detected.")

        time.sleep(0.2)

except KeyboardInterrupt:
    print("\nExiting...")

finally:
    stop_car()
    print("Car stopped safely.")
