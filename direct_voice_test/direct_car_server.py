from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
from picarx import Picarx
import time

px = Picarx()

SPEED = 20
TURN_ANGLE = 30


def stop_car():
    px.stop()
    px.set_dir_servo_angle(0)


def execute_command(command):
    command = command.lower().strip()

    if command in ["start", "go", "forward", "continue"]:
        px.set_dir_servo_angle(0)
        px.forward(SPEED)
        return "Moving forward"

    if command in ["stop", "pause"]:
        stop_car()
        return "Stopped"

    if command == "left":
        px.set_dir_servo_angle(-TURN_ANGLE)
        px.forward(15)
        return "Turning left"

    if command == "right":
        px.set_dir_servo_angle(TURN_ANGLE)
        px.forward(15)
        return "Turning right"

    if command == "backward":
        px.set_dir_servo_angle(0)
        px.backward(SPEED)
        return "Moving backward"

    return None


class CarHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path != "/cmd":
            self.send_response(404)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b"Use /cmd?value=start")
            return

        params = parse_qs(parsed.query)
        command = params.get("value", [""])[0]

        result = execute_command(command)

        if result is None:
            self.send_response(400)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b"Invalid command")
            return

        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(result.encode())

    def log_message(self, format, *args):
        return


try:
    server = HTTPServer(("0.0.0.0", 5050), CarHandler)
    print("Direct car server running on port 5050")
    print("Example: http://RASPBERRY_PI_IP:5050/cmd?value=start")
    server.serve_forever()

except KeyboardInterrupt:
    print("Stopping server...")

finally:
    stop_car()
    print("Car stopped safely.")
