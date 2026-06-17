# Lane Detection

Detects the road lane markings from the robot's camera and computes how
far the robot is from the center of its driving lane. This module does
not control the motors and does not detect signs,it only tells you
"here is the lane, here is how far off-center you are."

## What it does

The robot drives on the right-hand side of the road, like real traffic.
That means it needs to stay between two lines:

- the **dashed center line** (left side of the robot)
- the **solid right edge line** (right side of the robot)

`lane_detector.py` takes a single camera frame and returns a
`steering_error` value: negative means the robot should steer left,
positive means it should steer right, and `0.0` means it's centered.
It uses classic OpenCV image processing (thresholding + sliding window
search) — no machine learning

## How to use it


from lane_detector import LaneDetector

detector = LaneDetector(frame_width=640, frame_height=480)

# in your own real-time loop, for every frame from the camera:
result = detector.detect(frame_bgr)

result.steering_error   # -1.0 (full left) ... 0.0 (centered) ... 1.0 (full right)
result.lane_found       # False if no line was found at all - you need a fallback for this case
```

That's the whole interface. `result` also has `left_line_found`,
`right_line_found`, and `debug_image`, these are mainly useful for
debugging/logging, not required for driving.

## Things to check before plugging this into the full system

**Image format.** `detect()` expects a BGR image (standard OpenCV
format — this is what you get from Picamera2 after converting with
`cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)`). Make sure whatever
camera loop calls this is passing the same format.

**Frame size.** The detector is calibrated for **640x480**. The ROI
crop and search window sizes are tuned against that resolution. If the
final camera loop runs at a different resolution, either pass matching
`frame_width=` / `frame_height=` values when creating the
`LaneDetector`, or resize the frame to 640x480 before calling
`detect()`.

**Sign logic overrides lane following.** Stop signs and turn signs are
handled by a separate module. This detector has no idea signs exist,
it just keeps producing a `steering_error` every frame regardless. The
motor control code needs to decide when to ignore `steering_error` and
run sign-based logic instead (e.g. stop, or turn a fixed distance).

**Lighting matters.** This uses a fixed brightness threshold
(`white_thresh`) to find white pixels. It was calibrated against photos
taken on the actual track under the actual lighting in the room. If the
lighting changes significantly (different room, different time of day,
lights on/off), this value may need to be re-tuned — see the
parameters below.

**90-degree corners are out of scope.** This detector assumes the lane
lines are roughly vertical in the frame (true on straights and gentle
curves). In a sharp 90-degree turn, the lines run almost horizontally
across the frame and the left/right split breaks down. By team
agreement, handling sharp corners is not required for this module —
gentle curves and straights are.

## Key parameters (in `LaneDetector.__init__`)

| Parameter | Default | What it controls |
|---|---|---|
| `white_thresh` | 170 | Brightness cutoff for "this pixel is a lane line." Lower it if lines aren't being detected; raise it if too much background gets picked up as white. |
| `roi_top_ratio` | 0.54 | How much of the top of the frame gets cropped away (room/horizon). Adjust if the camera angle changes. |
| `window_margin` | 60 | How far sideways the search window can follow a line between steps. Increase if a line gets lost in sharper curves. |
| `min_pixels` | 25 | Minimum white pixels in a window to count it as a hit. |
| `estimated_lane_width` | 0.55 × frame width | Fallback lane width used when only one line is visible (e.g. between dashes on the center line). |

## How it works internally

1. Crop the frame to the lower portion (the road right in front of the
   robot) — `roi_top_ratio` controls how much is cropped.
2. Convert to grayscale and threshold to isolate white pixels.
3. Use a histogram over the bottom of the cropped region to find a
   rough starting x-position for the left and right line.
4. From those starting points, search upward in horizontal strips
   ("sliding windows"), following each line toward the horizon.
5. Take the lowest (closest) point found on each line, average them to
   get the lane center. If one line is missing, fall back to a fixed
   offset from whichever line was found.
6. Compare the lane center to the image's horizontal center to get
   `steering_error`.

No machine learning is used. The track has high-contrast white lines on
a uniform gray background. 