from ultralytics import YOLO
model = YOLO("runs/detect/picarx_signs-4/weights/best.pt")
model.export(format="ncnn")