"""Input sources. The game only talks to this interface, so the webcam and the
mouse are interchangeable:
  cursor()        -> (x, y) in osu! playfield coordinates, or None
  is_down()       -> True while pressing
  take_presses()  -> list of (perf_counter time, (x, y)) since the last call
  status_text()   -> a message to show the player, or None
  apply(settings) -> use changed settings now; False if the input must be recreated
"""
import time

import pygame

from air_rhythm.system import config


class MouseInput:
    """Mouse to aim, left click or Z / X to hit (osu!-style). For testing without a camera."""
    kind = "mouse"

    def __init__(self, playfield):
        self.playfield = playfield
        self._presses = []
        self._held = set()

    def handle_events(self, events):
        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                self._press("mouse")
            elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
                self._held.discard("mouse")
            elif e.type == pygame.KEYDOWN and e.key in (pygame.K_z, pygame.K_x):
                self._press(e.key)
            elif e.type == pygame.KEYUP and e.key in (pygame.K_z, pygame.K_x):
                self._held.discard(e.key)

    def _press(self, source):
        self._held.add(source)
        self._presses.append((time.perf_counter(), self.cursor()))

    def cursor(self):
        return self.playfield.to_osu(*pygame.mouse.get_pos())

    def is_down(self):
        return bool(self._held)

    def take_presses(self):
        presses, self._presses = self._presses, []
        return presses

    def status_text(self):
        return None

    def preview_surface(self):
        return None

    def apply(self, settings):
        return True                 # no mouse settings yet

    def close(self):
        pass


class HandInput:
    """Webcam: pinch point to aim, pinch to hit."""
    kind = "hand"

    def __init__(self, playfield, settings=None):
        from air_rhythm.controls.hand_tracker import (
            HandTracker,  # imported here so mouse mode works without a camera
        )
        self.playfield = playfield
        s = settings or {}
        self.camera_index = s.get("camera_index", config.CAMERA_INDEX)
        self.tracker = HandTracker(self.camera_index)
        self.apply(s)
        self.tracker.start()
        self._presses = []
        self._preview, self._preview_id = None, -1

    def apply(self, settings):
        """Use the player's hand settings (hand area, pinch, smoothing) right away.
        Returns False if the camera changed: that needs a new HandInput."""
        tr = self.tracker
        tr.zone = config.HAND_AREAS.get(settings.get("hand_area"), config.ACTIVE_ZONE)
        tr.set_pinch(*config.PINCH_SENSITIVITY.get(settings.get("pinch_sensitivity"),
                                                   (config.PINCH_CLOSE, config.PINCH_OPEN)))
        tr.smoothing_ms = config.CURSOR_SMOOTHINGS.get(settings.get("cursor_smoothing"),
                                                       config.CURSOR_SMOOTHING_MS)
        return settings.get("camera_index", self.camera_index) == self.camera_index

    @staticmethod
    def _to_osu(uv):
        if uv is None:
            return None
        m = config.CURSOR_MARGIN
        return (-m + uv[0] * (config.PLAYFIELD_W + 2 * m),
                -m + uv[1] * (config.PLAYFIELD_H + 2 * m))

    def handle_events(self, events):
        q = self.tracker.events
        while not q.empty():
            kind, t, uv = q.get_nowait()
            if kind == "press":
                self._presses.append((t, self._to_osu(uv)))

    def cursor(self):
        return self._to_osu(self.tracker.display_cursor())

    def is_down(self):
        return self.tracker.pinched

    def take_presses(self):
        presses, self._presses = self._presses, []
        return presses

    def status_text(self):
        tr = self.tracker
        if tr.error:
            return f"{tr.error}  (click Input or press I for mouse mode)"
        if not tr.ready:
            return "Starting camera..."
        if not tr.visible:
            return "Show your hand to the camera"
        return None

    def preview_surface(self):
        with self.tracker.lock:
            img, img_id = self.tracker.preview, self.tracker.preview_id
        if img is None:
            return None
        if img_id != self._preview_id:      # convert only when the camera sent a new image
            h, w = img.shape[:2]
            self._preview = pygame.image.frombuffer(img.tobytes(), (w, h), "RGB")
            self._preview_id = img_id
        return self._preview

    def close(self):
        self.tracker.stop()
