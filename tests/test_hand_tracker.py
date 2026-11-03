"""Hand tracking logic that needs no camera: pinch detection, filtering, cursor smoothing
and the hand model download (hand_tracker.py)."""
import hashlib
import http.server
import json
import os
import statistics
import threading
from itertools import pairwise
from types import SimpleNamespace as Point

import numpy as np
import pytest

import config
import hand_tracker
from conftest import UNREACHABLE_URL

HERE = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------- pinch
def hand(gap, scale=1.0, at=(0.5, 0.5)):
    """21 fake landmarks: hand size (wrist -> middle knuckle) = 0.2 * scale,
    thumb tip and index tip `gap` apart (also scaled)."""
    cx, cy = at
    lm = [Point(x=cx, y=cy) for _ in range(21)]
    lm[hand_tracker.WRIST] = Point(x=cx, y=cy + 0.1 * scale)
    lm[hand_tracker.MIDDLE_MCP] = Point(x=cx, y=cy - 0.1 * scale)
    lm[hand_tracker.THUMB_TIP] = Point(x=cx - gap * scale / 2, y=cy)
    lm[hand_tracker.INDEX_TIP] = Point(x=cx + gap * scale / 2, y=cy)
    return lm


def test_pinch_ratio_ignores_distance_to_the_camera():
    near, far = hand(0.06, scale=2.0), hand(0.06, scale=0.5)
    assert hand_tracker.pinch_ratio(near, 640, 640) == pytest.approx(hand_tracker.pinch_ratio(far, 640, 640))
    assert hand_tracker.pinch_ratio(hand(0.06), 640, 640) == pytest.approx(0.3)


def test_pinch_hysteresis():
    p = hand_tracker.PinchDetector(close=0.28, open_=0.40)
    assert p.update(0.5) is None
    assert p.update(0.27) == "press"
    assert p.update(0.35) is None          # between the thresholds: stays pinched
    assert p.update(0.41) == "release"


def test_hovering_at_a_threshold_presses_only_once():
    p = hand_tracker.PinchDetector(close=0.28, open_=0.40)
    events = [p.update(r) for r in [0.279, 0.281, 0.279, 0.281, 0.279, 0.3, 0.279]]
    assert events.count("press") == 1 and "release" not in events


def test_map_to_zone_scales_and_clamps():
    zone = (0.2, 0.15, 0.8, 0.8)
    assert hand_tracker.map_to_zone(0.5, 0.475, zone) == pytest.approx((0.5, 0.5))
    assert hand_tracker.map_to_zone(0.0, 1.0, zone) == (0.0, 1.0)


# ---------------------------------------------------------------- One Euro filter
def test_one_euro_smooths_jitter_when_still():
    rng = np.random.default_rng(0)
    f = hand_tracker.OneEuroFilter(1.5, 8.0, 1.0)
    noisy = 0.5 + rng.normal(0, 0.01, 300)
    out = [f(x, i / 30) for i, x in enumerate(noisy)]
    # With the game's settings (tuned to react fast, FILTER_BETA = 8) jitter is about halved
    assert np.std(out[30:]) < 0.6 * np.std(noisy[30:])


def test_one_euro_follows_fast_moves():
    f = hand_tracker.OneEuroFilter(1.5, 8.0, 1.0)
    for i in range(30):
        f(0.2, i / 30)
    out = [f(0.8, (30 + i) / 30) for i in range(6)]       # a big jump
    assert out[-1] > 0.75                                   # caught up within 0.2 s


# ---------------------------------------------------------------- cursor smoothing
def frame_times():
    """Real frame arrival times recorded from a ~30 fps laptop webcam (12-88 ms apart)."""
    return json.load(open(os.path.join(HERE, "data", "camera_frame_times.json")))["arrival_s"]


def drawn_steps(smoothing_ms, monkeypatch):
    """Feeds the real camera timing (hand moving at constant speed) into display_cursor
    and samples it at 60 fps. Returns how far the cursor moved on each screen frame."""
    monkeypatch.setattr(config, "CURSOR_SMOOTHING_MS", smoothing_ms)
    arrivals = [t + 1.0 for t in frame_times()]
    tr = hand_tracker.HandTracker()                         # thread not started
    tr.visible = True
    xs, k, now = [], 0, arrivals[20]
    while now < arrivals[-1] - 0.2:
        while k < len(arrivals) and arrivals[k] <= now:
            tr._samples.append((arrivals[k], (0.1 * arrivals[k], 0.5)))
            k += 1
        xs.append(tr.display_cursor(now)[0])
        now += 1 / 60
    return [b - a for a, b in pairwise(xs)]


def uneven_share(steps):
    ideal = statistics.mean(steps)
    return sum(abs(s - ideal) > 0.5 * ideal for s in steps) / len(steps)


def test_smoothed_cursor_moves_evenly_with_a_real_webcam(monkeypatch):
    smooth = drawn_steps(60, monkeypatch)
    raw = drawn_steps(0, monkeypatch)
    assert uneven_share(raw) > 0.5            # the raw cursor stutters (81% measured)
    assert uneven_share(smooth) < 0.05        # smoothed: almost every frame even (1.8% measured)


def test_cursor_hidden_without_a_hand():
    tr = hand_tracker.HandTracker()
    tr._samples.append((0.0, (0.5, 0.5)))
    assert tr.display_cursor(1.0) is None


def test_cursor_does_not_slide_across_after_the_hand_was_lost(monkeypatch):
    monkeypatch.setattr(config, "CURSOR_SMOOTHING_MS", 60)
    tr = hand_tracker.HandTracker()
    tr.visible = True
    tr._samples.extend([(0.0, (0.1, 0.5)), (0.5, (0.9, 0.5))])   # 0.5 s gap
    assert tr.display_cursor(0.3) == (0.9, 0.5)


def test_cursor_holds_still_when_the_camera_is_late(monkeypatch):
    monkeypatch.setattr(config, "CURSOR_SMOOTHING_MS", 60)
    tr = hand_tracker.HandTracker()
    tr.visible = True
    tr._samples.extend([(0.0, (0.1, 0.5)), (0.033, (0.2, 0.5))])
    assert tr.display_cursor(0.5) == (0.2, 0.5)


# ---------------------------------------------------------------- model download
FAKE_MODEL = os.urandom(300_000)


@pytest.fixture
def model_server(monkeypatch, tmp_path):
    """A local web server serving a fake model, so the download is tested without the
    internet. mode: "ok", "truncated" (connection drops halfway) or "corrupt"."""
    state = {"mode": "ok"}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = FAKE_MODEL if state["mode"] != "corrupt" else FAKE_MODEL[::-1]
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body[:len(body) // 2] if state["mode"] == "truncated" else body)

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setattr(hand_tracker, "MODEL_URL", f"http://127.0.0.1:{server.server_port}/model.task")
    monkeypatch.setattr(hand_tracker, "MODEL_SHA256", hashlib.sha256(FAKE_MODEL).hexdigest())
    monkeypatch.setattr(config, "MODELS_DIR", str(tmp_path / "models"))
    monkeypatch.setattr(config, "BUNDLED_MODEL", None)
    yield state
    server.shutdown()


def model_files():
    return sorted(os.listdir(config.MODELS_DIR)) if os.path.isdir(config.MODELS_DIR) else []


def test_model_download(model_server):
    path = hand_tracker.ensure_model()
    assert open(path, "rb").read() == FAKE_MODEL
    assert model_files() == ["hand_landmarker.task"]                  # no .part left


def test_existing_model_is_reused(model_server):
    hand_tracker.ensure_model()
    model_server["mode"] = "corrupt"                                    # would fail if downloaded again
    assert open(hand_tracker.ensure_model(), "rb").read() == FAKE_MODEL


def test_offline_gives_a_clear_message_and_no_broken_file(model_server, monkeypatch):
    monkeypatch.setattr(hand_tracker, "MODEL_URL", UNREACHABLE_URL)
    with pytest.raises(hand_tracker.ModelError, match=r"no internet\?"):
        hand_tracker.ensure_model()
    assert model_files() == []


def test_interrupted_download_leaves_no_broken_file(model_server):
    model_server["mode"] = "truncated"
    with pytest.raises(hand_tracker.ModelError):
        hand_tracker.ensure_model()
    assert model_files() == []


def test_corrupt_download_is_rejected(model_server):
    model_server["mode"] = "corrupt"
    with pytest.raises(hand_tracker.ModelError, match="damaged"):
        hand_tracker.ensure_model()
    assert model_files() == []


def test_damaged_model_on_disk_is_downloaded_again(model_server):
    os.makedirs(config.MODELS_DIR)
    with open(os.path.join(config.MODELS_DIR, "hand_landmarker.task"), "wb") as f:
        f.write(b"half a model")
    assert open(hand_tracker.ensure_model(), "rb").read() == FAKE_MODEL


def test_bundled_model_is_used_in_place(model_server, monkeypatch, tmp_path):
    bundled = tmp_path / "bundle" / "hand_landmarker.task"
    bundled.parent.mkdir()
    bundled.write_bytes(FAKE_MODEL)
    monkeypatch.setattr(config, "BUNDLED_MODEL", str(bundled))
    monkeypatch.setattr(hand_tracker, "MODEL_URL", UNREACHABLE_URL)    # must not download
    assert hand_tracker.ensure_model() == str(bundled)
    assert model_files() == []


def test_pinned_model_url_and_checksum():
    # "latest" could change under us and break the checksum; version 1 never changes
    assert "/float16/1/" in hand_tracker.MODEL_URL
    assert len(hand_tracker.MODEL_SHA256) == 64
