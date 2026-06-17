from ultralytics import YOLO

if __name__ == '__main__':
    model = YOLO("yolov8n.pt")
    model.train(data="picarx-traffic-signs-1/data.yaml", epochs=80, imgsz=640, batch=16, name="picarx_signs")