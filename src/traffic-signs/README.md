# Traffic Sign Recognition (PiCar-X)

YOLOv8n model detecting 3 classes: `left-sign`, `right-sign`, `stop-sign`.
Exported to NCNN for lightweight inference on the Raspberry Pi.

## Files
- `best_ncnn_model/` — the model to run on the Pi (NCNN, ~12 MB, no torch needed)
- `best.pt` — original PyTorch weights (for re-export / retraining only)
- `get_data.py` — pulls the dataset from Roboflow
- `train.py` — trains the model (laptop with GPU)
- `export.py` — converts `best.pt` → NCNN

## To use in the pipeline (on the Pi)

1. Copy `best_ncnn_model/` onto the Pi.
2. Inside the project venv: `pip install ncnn` (do NOT install full ultralytics on the Pi — it pulls torch+CUDA and is too heavy).
3. Load and run inference on a camera frame (BGR numpy array, e.g. from picamera2).

The detection call returns, per detected sign: the **class label** (`left-sign` / `right-sign` / `stop-sign`), the **confidence**, and the **bounding box**.

## What the integration code needs to do
- Run detection every N frames (not every frame — it's the slow part).
- Only act on a detection if **confidence ≥ ~0.6**.
- Use **bounding box size** as a distance proxy: only trigger the action when the box is large enough (sign is close).
- Debounce: require the sign in 2–3 consecutive checks before acting, then ignore further detections briefly (cooldown) so the same sign isn't triggered twice.
- The model only outputs label + box. The **physical action** (stop / turn) is the integrator's job.

## Notes
- Trained on real PiCar-X camera frames (dark track lighting, small signs) to match race conditions.
- Set your Roboflow API key via env var before running `get_data.py`: `ROBOFLOW_API_KEY`.
- To retrain: `python get_data.py` → `python train.py` → `python export.py`.