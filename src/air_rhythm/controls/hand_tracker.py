"""Webcam hand tracking in a background thread.

The camera gives ~30-60 frames per second, but the game draws at 120. Running
MediaPipe in its own thread means the game never waits for the camera.

Output (read by the game):
  - cursor: (u, v) in 0..1 inside the active zone, smoothed
  - pinched: True while thumb and index tips touch
  - events: a queue of ("press" | "release", capture_time, (u, v))
The capture time is taken right when the frame arrives, so a hit is judged at
the moment the pinch was *seen*, not when processing finished.
"""
import collections
import hashlib
import logging
import os
import queue
import threading
import time
import urllib.request

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions, vision

from air_rhythm.system import config

log = logging.getLogger(__name__)

# Pinned to version 1 (not "latest"), so the checksum below can never go stale.
MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
             "hand_landmarker/float16/1/hand_landmarker.task")
MODEL_SHA256 = "fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1"
MODEL_TIMEOUT_S = 30

THUMB_TIP, INDEX_TIP, WRIST, MIDDLE_MCP = 4, 8, 0, 9


class ModelError(Exception):
    """The hand model is missing and couldn't be downloaded. The message is shown to the player."""


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_model():
    """Path to a verified hand model, downloading it if needed. The download goes to a
    .part file and is only renamed once complete and checked, so an interrupted
    download can never leave a broken model behind."""
    if config.BUNDLED_MODEL and os.path.exists(config.BUNDLED_MODEL) \
            and _sha256(config.BUNDLED_MODEL) == MODEL_SHA256:
        return config.BUNDLED_MODEL           # shipped with the packaged build: no download
    path = os.path.join(config.MODELS_DIR, "hand_landmarker.task")
    if os.path.exists(path):
        if _sha256(path) == MODEL_SHA256:
            return path
        log.warning("Hand model %s is damaged, downloading it again", path)
        os.remove(path)
    part = path + ".part"
    log.info("Downloading hand landmark model (~8 MB) from %s", MODEL_URL)
    try:
        os.makedirs(config.MODELS_DIR, exist_ok=True)
        with urllib.request.urlopen(MODEL_URL, timeout=MODEL_TIMEOUT_S) as r, open(part, "wb") as f:
            while chunk := r.read(1 << 16):
                f.write(chunk)
        if _sha256(part) != MODEL_SHA256:
            raise ModelError("The downloaded hand-tracking model is damaged. Restart to try again.")
        os.replace(part, path)
    except ModelError:
        raise
    except OSError as e:                # no internet, timeout, DNS, disk full... (URLError is an OSError)
        log.warning("Hand model download failed: %s", e)
        raise ModelError("Couldn't download the hand-tracking model (no internet?).") from e
    finally:
        if os.path.exists(part):
            os.remove(part)
    log.info("Hand model saved to %s", path)
    return path


class OneEuroFilter:
    """Adaptive low-pass filter (Casiez et al., 2012).
    When the hand moves slowly, it smooths strongly (kills jitter while aiming).
    When the hand moves fast, it smooths less (no lag on big jumps)."""

    def __init__(self, min_cutoff, beta, d_cutoff):
        self.min_cutoff, self.beta, self.d_cutoff = min_cutoff, beta, d_cutoff
        self.reset()

    def reset(self):
        self.x_prev = None
        self.dx_prev = 0.0
        self.t_prev = None

    @staticmethod
    def _alpha(cutoff, dt):
        tau = 1.0 / (2 * np.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def __call__(self, x, t):
        if self.t_prev is None:
            self.x_prev, self.t_prev = x, t
            return x
        dt = max(t - self.t_prev, 1e-6)
        dx = (x - self.x_prev) / dt
        a_d = self._alpha(self.d_cutoff, dt)
        dx_hat = a_d * dx + (1 - a_d) * self.dx_prev          # smoothed speed
        cutoff = self.min_cutoff + self.beta * abs(dx_hat)    # faster -> higher cutoff
        a = self._alpha(cutoff, dt)
        x_hat = a * x + (1 - a) * self.x_prev
        self.x_prev, self.dx_prev, self.t_prev = x_hat, dx_hat, t
        return x_hat


def pinch_ratio(landmarks, width, height):
    """Thumb-index distance divided by hand size (wrist to middle knuckle).
    Dividing by hand size makes it work whether the hand is near or far."""
    def px(i):
        return np.array([landmarks[i].x * width, landmarks[i].y * height])
    hand_size = np.linalg.norm(px(WRIST) - px(MIDDLE_MCP))
    if hand_size < 1e-6:
        return 1.0
    return np.linalg.norm(px(THUMB_TIP) - px(INDEX_TIP)) / hand_size


class PinchDetector:
    """Hysteresis: close below PINCH_CLOSE, open only above PINCH_OPEN.
    With a single threshold, a hand sitting right at the boundary would
    flicker pinched/unpinched and fire many presses."""

    def __init__(self, close=config.PINCH_CLOSE, open_=config.PINCH_OPEN):
        self.close, self.open = close, open_
        self.pinched = False

    def update(self, ratio):
        if not self.pinched and ratio < self.close:
            self.pinched = True
            return "press"
        if self.pinched and ratio > self.open:
            self.pinched = False
            return "release"
        return None


def map_to_zone(x, y, zone=config.ACTIVE_ZONE):
    left, top, right, bottom = zone
    u = (x - left) / (right - left)
    v = (y - top) / (bottom - top)
    return min(max(u, 0.0), 1.0), min(max(v, 0.0), 1.0)


class HandTracker:
    """`zone`, `smoothing_ms` and the pinch thresholds (set_pinch) can be changed while it runs
    (the Settings screen does); a different `camera_index` needs a new tracker."""
    PREVIEW_SIZE = (240, 180)

    def __init__(self, camera_index=config.CAMERA_INDEX, zone=config.ACTIVE_ZONE,
                 pinch=(config.PINCH_CLOSE, config.PINCH_OPEN), smoothing_ms=config.CURSOR_SMOOTHING_MS):
        self.camera_index = camera_index
        self.zone = zone                 # part of the camera image that maps to the playfield
        self.smoothing_ms = smoothing_ms
        self.lock = threading.Lock()
        self.events = queue.Queue()
        self.cursor = None
        self._samples = collections.deque(maxlen=12)  # (arrival time, cursor) of recent frames
        self.visible = False
        self.pinched = False
        self.preview = None      # small RGB image for the in-game camera view
        self.preview_id = 0      # goes up by one with every new preview image
        self.ready = False
        self.error = None
        self._fu = OneEuroFilter(config.FILTER_MIN_CUTOFF, config.FILTER_BETA, config.FILTER_D_CUTOFF)
        self._fv = OneEuroFilter(config.FILTER_MIN_CUTOFF, config.FILTER_BETA, config.FILTER_D_CUTOFF)
        self._pinch = PinchDetector(*pinch)
        self._last_seen = None   # capture time of the last frame with a hand
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def set_pinch(self, close, open_):
        self._pinch.close, self._pinch.open = close, open_

    def display_cursor(self, now=None):
        """Cursor position for drawing a frame at time `now`.
        Webcams deliver frames unevenly (often 12-90 ms apart instead of a steady 33),
        and the screen shows 60+ frames per second, so a cursor that jumps to each new
        camera position looks choppy. Instead the recent positions are played back
        `smoothing_ms` late, gliding between them: the delay hides the uneven
        arrivals, so the cursor moves at an even speed. Hits still use the exact
        position from the moment the frame was captured."""
        if now is None:
            now = time.perf_counter()
        with self.lock:
            if not self.visible:
                return None
            samples = list(self._samples)
        if not samples:
            return self.cursor
        delay = self.smoothing_ms / 1000
        if delay <= 0:
            return samples[-1][1]
        rt = now - delay
        i = len(samples) - 1
        while i >= 0 and samples[i][0] > rt:     # newest position that is old enough to show
            i -= 1
        if i < 0:                               # hand just appeared: start at its first position
            return samples[0][1]
        if i == len(samples) - 1:               # camera is late: hold the last position
            return samples[-1][1]
        (ta, (ua, va)), (tb, (ub, vb)) = samples[i], samples[i + 1]
        if tb - ta > 0.15:                      # long gap (hand was briefly lost): don't slide across
            return ub, vb
        f = (rt - ta) / (tb - ta)
        return ua + (ub - ua) * f, va + (vb - va) * f

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=2)

    def _run(self):
        try:
            self._loop()
        except ModelError as e:         # show the problem in-game instead of crashing
            self.error = str(e)
        except Exception as e:
            log.exception("Hand tracking stopped")
            self.error = f"Camera problem: {e}"

    def _loop(self):
        options = vision.HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=ensure_model()),
            running_mode=vision.RunningMode.VIDEO,   # detect once, then track
            num_hands=1,
            min_hand_detection_confidence=0.6,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        landmarker = vision.HandLandmarker.create_from_options(options)
        cap = cv2.VideoCapture(self.camera_index)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_W)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_H)
        cap.set(cv2.CAP_PROP_FPS, config.CAMERA_FPS)
        if not cap.isOpened():
            raise RuntimeError(f"Could not open camera {self.camera_index + 1}")
        log.info("Camera %d opened: %dx%d, reports %.0f fps", self.camera_index + 1,
                 cap.get(cv2.CAP_PROP_FRAME_WIDTH), cap.get(cv2.CAP_PROP_FRAME_HEIGHT),
                 cap.get(cv2.CAP_PROP_FPS))

        last_ts, frame_times = -1, []
        fps_logged_at = time.perf_counter() + 5      # log the real camera fps once, after warm-up

        try:
            while not self._stop.is_set():
                ok, frame = cap.read()
                t = time.perf_counter()           # capture time of this frame
                if not ok:
                    raise RuntimeError("The webcam stopped sending frames")
                frame = cv2.flip(frame, 1)        # mirror
                h, w = frame.shape[:2]
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                ts = max(int(t * 1000), last_ts + 1)
                last_ts = ts
                result = landmarker.detect_for_video(
                    mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), ts)

                landmarks = result.hand_landmarks[0] if result.hand_landmarks else None
                self._on_frame(landmarks, w, h, t)

                preview = self._make_preview(rgb, landmarks, self._pinch.pinched)
                frame_times = [ft for ft in frame_times if t - ft < 1.0] + [t]
                with self.lock:
                    self.preview = preview
                    self.preview_id += 1
                    self.ready = True
                if fps_logged_at and t > fps_logged_at:
                    log.info("Camera running at %d fps (with hand tracking)", len(frame_times))
                    fps_logged_at = None
        finally:
            cap.release()
            landmarker.close()

    def _on_frame(self, landmarks, width, height, t, arrived=None):
        """What one camera frame means: where the cursor is, and whether a pinch started or
        ended. `landmarks` is MediaPipe's hand (or None), `t` the frame's capture time,
        `arrived` when the result reached the game (default: now). No camera needed, so
        this is what the tests drive."""
        if landmarks:
            self._last_seen = t
            # Cursor = point between thumb and index tips. When you pinch,
            # both tips move toward each other, so this point stays put
            # (the index tip alone would jump and ruin your aim).
            cx = (landmarks[THUMB_TIP].x + landmarks[INDEX_TIP].x) / 2
            cy = (landmarks[THUMB_TIP].y + landmarks[INDEX_TIP].y) / 2
            u, v = map_to_zone(cx, cy, self.zone)
            u, v = self._fu(u, t), self._fv(v, t)
            event = self._pinch.update(pinch_ratio(landmarks, width, height))
            with self.lock:
                self.cursor, self.visible, self.pinched = (u, v), True, self._pinch.pinched
                self._samples.append((time.perf_counter() if arrived is None else arrived, (u, v)))
            if event:
                self.events.put((event, t, (u, v)))
        elif self._last_seen is None or t - self._last_seen > config.HAND_LOST_GRACE_S:
            if self._pinch.pinched:
                self._pinch.pinched = False
                self.events.put(("release", t, self.cursor))
            self._fu.reset()
            self._fv.reset()
            with self.lock:
                self.visible, self.pinched = False, False
                self._samples.clear()
        # otherwise the hand was lost only briefly: keep everything as it was

    def _make_preview(self, rgb, landmarks, pinched):
        pw, ph = self.PREVIEW_SIZE
        small = cv2.resize(rgb, (pw, ph))
        left, top, right, bottom = self.zone
        cv2.rectangle(small, (int(left * pw), int(top * ph)),
                      (int(right * pw), int(bottom * ph)), (255, 255, 255), 1)
        if landmarks:
            color = (120, 255, 140) if pinched else (255, 255, 255)
            for lm in landmarks:
                cv2.circle(small, (int(lm.x * pw), int(lm.y * ph)), 2, color, -1)
        return small
