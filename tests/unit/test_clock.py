"""Song clock: song time comes from a high-precision clock, pausing freezes it and
resuming carries on exactly where it stopped (time spent paused never counts)."""
import time

import pygame
import pytest

from air_rhythm.core.clock import SYNC_SAMPLES, SongClock


class FakeTime:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


@pytest.fixture
def clock(monkeypatch):
    fake = FakeTime()
    monkeypatch.setattr(time, "perf_counter", fake)
    c = SongClock()
    c.start_t = fake.now          # as if the music started just now (no audio needed)
    return c, fake


def test_song_time_follows_the_clock(clock):
    c, t = clock
    t.now += 1.5
    assert c.now_ms() == pytest.approx(1500)
    assert c.now_ms(t.now - 0.25) == pytest.approx(1250)       # a press seen 250 ms ago


def test_pausing_freezes_song_time(clock):
    c, t = clock
    t.now += 2.0
    c.pause()
    t.now += 30.0                                              # half a minute in the pause menu
    assert c.paused and c.now_ms() == pytest.approx(2000)


def test_resuming_carries_on_where_it_stopped(clock):
    c, t = clock
    t.now += 2.0
    c.pause()
    t.now += 30.0
    c.resume()
    assert not c.paused and c.now_ms() == pytest.approx(2000)
    t.now += 0.5
    assert c.now_ms() == pytest.approx(2500)                   # the pause added nothing
    assert c.now_ms(t.now) == pytest.approx(2500)              # presses are timed the same way


def test_several_pauses_add_up(clock):
    c, t = clock
    for _ in range(3):
        t.now += 1.0
        c.pause()
        c.pause()                                              # pausing twice changes nothing
        t.now += 10.0
        c.resume()
    c.resume()                                                 # neither does resuming twice
    assert c.now_ms() == pytest.approx(3000)


def test_pause_during_the_lead_in_keeps_the_lead_in(clock):
    c, t = clock
    c.start_t = t.now + 2.0                                    # music starts in 2 s
    c._pending = True
    t.now += 0.5
    c.pause()
    t.now += 10.0
    c.update()                                                 # paused: the music must not start
    assert c._pending
    c.resume()
    assert c.now_ms() == pytest.approx(-1500)                  # still 1.5 s of lead-in left


class FakeMusic:
    """pygame.mixer.music stand-in: get_pos() is the ms of music played (not counting pauses),
    and each unpause can come in late, like a real mixer waiting for its next audio buffer."""
    def __init__(self, t):
        self.t, self.played, self.since, self.late_ms = t, 0.0, None, 0.0

    def load(self, path):
        pass

    def play(self):
        self.played, self.since = 0.0, self.t.now

    def pause(self):
        self.played += (self.t.now - self.since) * 1000
        self.since = None

    def unpause(self):
        self.since = self.t.now - self.late_ms / 1000   # music resumes `late_ms` ahead of the clock

    def get_pos(self):
        return int(self.played + ((self.t.now - self.since) * 1000 if self.since is not None else 0))

    def stop(self):
        pass


@pytest.fixture
def with_music(monkeypatch):
    t = FakeTime()
    monkeypatch.setattr(time, "perf_counter", t)
    music = FakeMusic(t)
    for name in ("load", "play", "pause", "unpause", "get_pos", "stop"):
        monkeypatch.setattr(pygame.mixer.music, name, getattr(music, name))
    monkeypatch.setattr(pygame.mixer, "get_init", lambda: (44100, -16, 2))
    c = SongClock()
    c.start("song.wav", 0)
    return c, t, music


def frames(c, t, n):
    for _ in range(n):
        t.now += 1 / 60
        c.update()


def test_clock_corrects_itself_when_the_music_resumes_off_time(with_music):
    c, t, music = with_music
    frames(c, t, 1 + SYNC_SAMPLES)                      # music starts, offset measured
    for _ in range(5):
        music.late_ms = 10.0                            # every unpause lands 10 ms off
        c.pause()
        t.now += 1.0
        c.resume()
        frames(c, t, SYNC_SAMPLES + 5)
    # without the correction the clock would be 50 ms behind the music by now
    assert c.now_ms() - music.get_pos() == pytest.approx(0, abs=1.5)


def test_pausing_while_measuring_starts_the_measurement_again(with_music):
    c, t, music = with_music
    frames(c, t, 1 + SYNC_SAMPLES)
    music.late_ms = 10.0
    c.pause()
    c.resume()
    frames(c, t, 5)
    c.pause()                                           # paused again half-way through measuring
    t.now += 1.0
    music.late_ms = 0.0
    c.resume()
    frames(c, t, SYNC_SAMPLES + 5)
    # the first resume's 10 ms is still corrected, by the full measurement after the second
    assert c.now_ms() - music.get_pos() == pytest.approx(0, abs=1.5)
