from ultralytics import YOLO
import time

model = YOLO("best.pt")          # adjust path if best.pt is elsewhere
print("model loaded, classes:", model.names)

# time a single inference on a dummy image
import numpy as np
dummy = np.zeros((480, 640, 3), dtype=np.uint8)
# warm-up run (first one is always slow)
model(dummy, verbose=False)
t = time.time()
for _ in range(5):
    model(dummy, verbose=False)
print("avg inference time:", round((time.time() - t) / 5, 3), "seconds/frame")