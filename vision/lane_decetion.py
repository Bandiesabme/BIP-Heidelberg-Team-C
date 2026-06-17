"""
Core logic for lane detection: follow the right-hand lane
(between the dashed center line and the solid white right edge line).

Pure OpenCV - no machine learning, no camera dependency.
tested on single images or video without the robot connected.

Pipeline (simplified, no perspective warp):
  1. Crop to the lower part of the frame (the road right in front of the robot)
  2. Threshold to isolate white pixels (the lines)
  3. Sliding window directly on the cropped frame to find
     left (center line) and right (edge line) pixels
  4. Compute the lane center from the lowest point found on each line
  5. Compute the offset from the image center -> steering error

We do not warp to a bird's-eye view. This is a simplification that is
good enough for computing a steering error (we don't need real-world
coordinates, just a consistent pixel position to steer toward), and it's
much easier to calibrate correctly in a short amount of time than a
precise perspective transform.
"""

import cv2
import numpy as np
from dataclasses import dataclass
from typing import Optional


@dataclass
class LaneResult:
    """Result from a lane detection analysis of one frame."""
    steering_error: float          # negative = steer left, positive = steer right (normalized -1..1)
    lane_found: bool                # did we find enough info to navigate
    left_line_found: bool           # center line (dashed) found
    right_line_found: bool          # right edge line found
    debug_image: Optional[np.ndarray] = None  # visualization for debugging


class LaneDetector:
    def __init__(
        self,
        frame_width: int = 640,
        frame_height: int = 480,
        white_thresh: int = 170,
        roi_top_ratio: float = 0.54,    # crop away the top 54% of the frame (room/horizon)
        n_windows: int = 8,              # number of sliding windows vertically within the ROI
        window_margin: int = 60,         # half-width of the search window in pixels
        min_pixels: int = 25,            # min pixels in a window to count as "found"
        estimated_lane_width: Optional[float] = None,  # pixels; default = 0.55*width
    ):
        self.w = frame_width
        self.h = frame_height
        self.white_thresh = white_thresh
        self.roi_top_ratio = roi_top_ratio
        self.n_windows = n_windows
        self.window_margin = window_margin
        self.min_pixels = min_pixels
        self.estimated_lane_width = (
            estimated_lane_width if estimated_lane_width is not None else self.w * 0.55
        )

        self.roi_top_y = int(self.h * self.roi_top_ratio)
        self.roi_height = self.h - self.roi_top_y

    # ------------------------------------------------------------------
    def preprocess(self, frame_bgr: np.ndarray) -> np.ndarray:
        """Returns a binary (0/255) mask of white pixels, cropped to the ROI."""
        frame = cv2.resize(frame_bgr, (self.w, self.h))
        roi = frame[self.roi_top_y:self.h, 0:self.w]

        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        _, binary = cv2.threshold(blur, self.white_thresh, 255, cv2.THRESH_BINARY)
        return binary

    # ------------------------------------------------------------------
    def _sliding_window_search(self, binary_roi: np.ndarray, x_start: int):
        """
        Searches upward (toward the horizon) from x_start and finds the pixel
        center in each window. Returns a list of (x, y) midpoints (y in ROI
        coordinates, where y=0 is the top of the ROI / near the horizon, and
        y=roi_height is the bottom / closest to the robot), plus the number
        of windows with a hit.
        """
        roi_h = binary_roi.shape[0]
        window_height = max(1, roi_h // self.n_windows)
        x_current = x_start
        points = []
        hits = 0

        for i in range(self.n_windows):
            y_low = roi_h - (i + 1) * window_height
            y_high = roi_h - i * window_height
            y_low = max(0, y_low)
            x_low = max(0, x_current - self.window_margin)
            x_high = min(self.w, x_current + self.window_margin)

            window = binary_roi[y_low:y_high, x_low:x_high]
            ys, xs = np.nonzero(window)

            if len(xs) >= self.min_pixels:
                mean_x = int(np.mean(xs)) + x_low
                mean_y = (y_low + y_high) // 2
                points.append((mean_x, mean_y))
                x_current = mean_x  # follow the line upward
                hits += 1
            # if not enough pixels: keep x_current (the line is temporarily
            # invisible, e.g. between segments of the dashed center line)

        return points, hits

    # ------------------------------------------------------------------
    def detect(self, frame_bgr: np.ndarray) -> LaneResult:
        binary_roi = self.preprocess(frame_bgr)
        roi_h = binary_roi.shape[0]

        # Starting search positions: histogram over the lower third of the ROI
        # (closest to the robot) to find where the left (center) and right
        # (edge) line start.
        search_band = binary_roi[int(roi_h * 0.66):, :]
        histogram = np.sum(search_band, axis=0)
        midpoint = self.w // 2

        left_region = histogram[:midpoint]
        right_region = histogram[midpoint:]

        left_x_start = int(np.argmax(left_region)) if left_region.max() > 0 else midpoint // 2
        right_x_start = (
            int(np.argmax(right_region)) + midpoint if right_region.max() > 0
            else midpoint + midpoint // 2
        )

        left_points, left_hits = self._sliding_window_search(binary_roi, left_x_start)
        right_points, right_hits = self._sliding_window_search(binary_roi, right_x_start)

        left_found = left_hits >= 2
        right_found = right_hits >= 2

        # Compute the lane center based on the lowest available point on each line
        # (points[0] is the bottom-most window since we search upward from the bottom)
        lane_center = None
        if left_found and right_found:
            lx = left_points[0][0]
            rx = right_points[0][0]
            lane_center = (lx + rx) / 2.0
        elif right_found and not left_found:
            # Lost the center line (common, it's dashed) hold a fixed
            # offset from the right line instead
            rx = right_points[0][0]
            lane_center = rx - self.estimated_lane_width / 2.0
        elif left_found and not right_found:
            lx = left_points[0][0]
            lane_center = lx + self.estimated_lane_width / 2.0

        image_center = self.w / 2.0
        lane_found = lane_center is not None

        if lane_found:
            raw_error = (lane_center - image_center)
            steering_error = float(np.clip(raw_error / (self.w / 2.0), -1.0, 1.0))
        else:
            steering_error = 0.0  # no line found, let the controller decide the fallback

        debug_img = self._draw_debug(binary_roi, left_points, right_points, lane_center)

        return LaneResult(
            steering_error=steering_error,
            lane_found=lane_found,
            left_line_found=left_found,
            right_line_found=right_found,
            debug_image=debug_img,
        )

    # ------------------------------------------------------------------
    def _draw_debug(self, binary_roi, left_points, right_points, lane_center):
        debug = cv2.cvtColor(binary_roi, cv2.COLOR_GRAY2BGR)

        for (x, y) in left_points:
            cv2.circle(debug, (x, y), 5, (0, 0, 255), -1)   # red = center line
        for (x, y) in right_points:
            cv2.circle(debug, (x, y), 5, (0, 255, 0), -1)   # green = edge line

        h = binary_roi.shape[0]
        if lane_center is not None:
            cv2.line(debug, (int(lane_center), 0), (int(lane_center), h), (255, 0, 0), 2)  # blue = desired center
        cv2.line(debug, (self.w // 2, 0), (self.w // 2, h), (0, 255, 255), 1)  # yellow = image center

        return debug