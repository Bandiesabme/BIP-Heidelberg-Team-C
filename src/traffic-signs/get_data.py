from roboflow import Roboflow
rf = Roboflow(api_key="placeholder-privatekey")
project = rf.workspace("book-project").project("picarx-traffic-signs")
dataset = project.version(1).download("yolov8")
print("data at:", dataset.location)