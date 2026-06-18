"""
Center-line lane following.

Track ONLY the dashed center line and keep a fixed distance to the RIGHT of
it (the car drives in the right-hand lane, so it sits right of center). We do
not look for the right edge line at all. Tracking one line means the detector
can never lock onto the wrong one.

The center line is dashed, so it disappears between dashes. That's expected:
the motor controller's grace period coasts through the short gaps.

Pipeline:
  1. Crop to the lower part of the frame
  2. Threshold to isolate white pixels
  3. Sliding-window search for the center line, starting from the middle-ish
  4. Target = center line + a fixed offset to the right
  5. steering_error = how far the car is from that target
"""

import cv2
import numpy as np
from dataclasses import dataclass
from typing import Optional


@dataclass
class LaneResult:
    steering_error: float
    lane_found: bool
    left_line_found: bool          # center line (dashed)
    right_line_found: bool         # kept for dashboard compatibility (always False)
    debug_image: Optional[np.ndarray] = None


class LaneDetector:
    def __init__(
        self,
        frame_width: int = 640,
        frame_height: int = 480,
        white_thresh: int = 170,
        roi_top_ratio: float = 0.54,
        n_windows: int = 8,
        window_margin: int = 100,        # wide: follow the line through curves
        min_pixels: int = 20,            # a bit lower: dashes are smaller targets
        # how far RIGHT of the center line the car sits, in pixels.
        # bigger = car drives further right of the center line.
        follow_offset: Optional[float] = None,
        estimated_lane_width: Optional[float] = None,  # kept for compatibility
    ):
        self.w = frame_width
        self.h = frame_height
        self.white_thresh = white_thresh
        self._roi_top_ratio = roi_top_ratio
        self.roi_top_y = int(self.h * self._roi_top_ratio)
        self.roi_height = self.h - self.roi_top_y
        self.n_windows = n_windows
        self.window_margin = window_margin
        self.min_pixels = min_pixels
        self.follow_offset = (
            follow_offset if follow_offset is not None else self.w * 0.12
        )
        self.estimated_lane_width = (
            estimated_lane_width if estimated_lane_width is not None else self.w * 0.55
        )

    @property
    def roi_top_ratio(self) -> float:
        return self._roi_top_ratio

    @roi_top_ratio.setter
    def roi_top_ratio(self, value: float):
        self._roi_top_ratio = float(value)
        self.roi_top_y = int(self.h * self._roi_top_ratio)
        self.roi_height = self.h - self.roi_top_y

    # ------------------------------------------------------------------
    def preprocess(self, frame_bgr: np.ndarray) -> np.ndarray:
        frame = cv2.resize(frame_bgr, (self.w, self.h))
        roi = frame[self.roi_top_y:self.h, 0:self.w]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        _, binary = cv2.threshold(blur, self.white_thresh, 255, cv2.THRESH_BINARY)
        return binary

    # ------------------------------------------------------------------
    def _sliding_window_search(self, binary_roi: np.ndarray, x_start: int):
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
                x_current = mean_x
                hits += 1

        return points, hits

    # ------------------------------------------------------------------
    def detect(self, frame_bgr: np.ndarray) -> LaneResult:
        binary_roi = self.preprocess(frame_bgr)
        roi_h = binary_roi.shape[0]

        # Find where the center line starts. Look at the bottom band and pick
        # the strongest white column in the MIDDLE region of the frame (the
        # center line lives near the middle; ignore the far right where the
        # solid edge line would be).
        search_band = binary_roi[int(roi_h * 0.66):, :]
        histogram = np.sum(search_band, axis=0)

        # search the middle 60% of the frame (15% to 75%) for the center line,
        # so the far-right edge line isn't picked instead.
        left_cut = int(self.w * 0.15)
        right_cut = int(self.w * 0.75)
        mid_hist = np.zeros_like(histogram)
        mid_hist[left_cut:right_cut] = histogram[left_cut:right_cut]

        if mid_hist.max() > 0:
            center_x_start = int(np.argmax(mid_hist))
        else:
            center_x_start = self.w // 2  # guess: middle

        center_points, center_hits = self._sliding_window_search(binary_roi, center_x_start)
        # dashed line: 1 hit can be a valid dash. accept >=1 but it'll be noisier.
        center_found = center_hits >= 1

        lane_center = None
        if center_found:
            xs = [p[0] for p in center_points]
            cx = float(np.mean(xs))  # bottom-most point on center line
            lane_center = cx + self.follow_offset  # sit this far RIGHT of it

        image_center = self.w / 2.0
        lane_found = lane_center is not None

        if lane_found:
            raw_error = (lane_center - image_center)
            steering_error = float(np.clip(raw_error / (self.w / 2.0), -1.0, 1.0))
        else:
            steering_error = 0.0

        debug_img = self._draw_debug(binary_roi, center_points, lane_center)

        return LaneResult(
            steering_error=steering_error,
            lane_found=lane_found,
            left_line_found=center_found,
            right_line_found=False,
            debug_image=debug_img,
        )

    # ------------------------------------------------------------------
    def _draw_debug(self, binary_roi, center_points, lane_center):
        debug = cv2.cvtColor(binary_roi, cv2.COLOR_GRAY2BGR)
        for (x, y) in center_points:
            cv2.circle(debug, (x, y), 5, (0, 0, 255), -1)   # red = center line
        h = binary_roi.shape[0]
        if lane_center is not None:
            cv2.line(debug, (int(lane_center), 0), (int(lane_center), h), (255, 0, 0), 2)  # blue = target
        cv2.line(debug, (self.w // 2, 0), (self.w // 2, h), (0, 255, 255), 1)  # yellow = image center
        return debug