from picamera2 import Picamera2
import cv2
import time

picam2 = Picamera2()
picam2.configure(picam2.create_preview_configuration(
    main={"format": "RGB888", "size": (640, 480)}))
picam2.start()
time.sleep(1)   # let auto-exposure settle

frame = picam2.capture_array()        # RGB
print("shape:", frame.shape)
cv2.imwrite("test.jpg", frame)
print("saved test.jpg")

picam2.stop()