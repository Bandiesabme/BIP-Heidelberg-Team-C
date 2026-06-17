import numpy as np
import cv2
import ncnn
import os
import sys
import time

def test_inference(image_path=None):
    # Locate the model files
    model_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "vision", "models", "yolo")
    param_path = os.path.join(model_dir, "model.ncnn.param")
    bin_path = os.path.join(model_dir, "model.ncnn.bin")

    if not os.path.exists(param_path) or not os.path.exists(bin_path):
        print(f"❌ Error: Model files not found in {model_dir}")
        return

    print("🚀 Loading NCNN model...")
    net = ncnn.Net()
    net.opt.use_vulkan_compute = False
    net.opt.num_threads = 2
    net.load_param(param_path)
    net.load_model(bin_path)
    print("✅ Model loaded successfully.")

    if image_path and os.path.exists(image_path):
        print(f"\n🖼️ Reading image: {image_path}")
        frame = cv2.imread(image_path)
    else:
        print("\n⚠️ No image provided or file not found. Using a dummy 320x240 black image.")
        frame = np.zeros((240, 320, 3), dtype=np.uint8)

    print("⚙️ Preprocessing...")
    start_time = time.time()
    
    mat_in = ncnn.Mat.from_pixels_resize(
        frame, 
        ncnn.Mat.PixelType.PIXEL_BGR2RGB, 
        frame.shape[1], 
        frame.shape[0], 
        320,  # Ensure this matches what you used in sign_detector.py
        320
    )
    
    mean_vals = [0.0, 0.0, 0.0]
    norm_vals = [1/255.0, 1/255.0, 1/255.0]
    mat_in.substract_mean_normalize(mean_vals, norm_vals)

    print("🧠 Running inference...")
    ex = net.create_extractor()
    ex.input("in0", mat_in)
    ret, mat_out = ex.extract("out0")
    
    inf_time = time.time() - start_time
    print(f"⏱️ Inference took: {inf_time * 1000:.2f} ms")

    if ret == 0 and mat_out:
        out_np = np.squeeze(np.array(mat_out))
        print(f"📊 Raw output shape: {out_np.shape}")
        
        # Handle flattening
        if len(out_np.shape) == 1:
            num_features = 7
            num_anchors = out_np.shape[0] // num_features
            out_np = out_np.reshape(num_anchors, num_features)
        elif out_np.shape[0] == 7 and len(out_np.shape) == 2:
            out_np = out_np.T

        print(f"📐 Processed output shape: {out_np.shape}")
        
        if len(out_np.shape) == 2 and out_np.shape[1] >= 7:
            scores = out_np[:, 4:]
            max_scores_per_anchor = np.max(scores, axis=1)
            class_ids_per_anchor = np.argmax(scores, axis=1)
            
            best_anchor_idx = np.argmax(max_scores_per_anchor)
            best_conf = float(max_scores_per_anchor[best_anchor_idx])
            best_class = int(class_ids_per_anchor[best_anchor_idx])
            
            class_names = {0: "LEFT", 1: "RIGHT", 2: "STOP"}
            print(f"\n--- 🎯 RESULTS ---")
            print(f"  Class:      {class_names.get(best_class, 'UNKNOWN')} (ID: {best_class})")
            print(f"  Confidence: {best_conf:.4f}")
            if best_conf >= 0.5:
                print("  Status:     ✅ PASSED threshold (>= 0.5)")
            else:
                print("  Status:     ❌ REJECTED threshold (< 0.5)")
        else:
            print("❌ Output shape is invalid for extraction.")
    else:
        print("❌ Inference failed to extract 'out0'")

if __name__ == "__main__":
    img_arg = sys.argv[1] if len(sys.argv) > 1 else None
    test_inference(img_arg)
