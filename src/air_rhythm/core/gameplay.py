"""Game rules: judging hits, score, combo, accuracy and health.
No drawing here, so it can be tested without a window."""
import math
import statistics

JUDGE_COLORS = {300: (110, 200, 255), 100: (130, 230, 130), 50: (255, 210, 100), 0: (255, 90, 90)}


class Gameplay:
    BREAK_GAP_MS = 2500       # no health drain when the next circle is this far away

    def __init__(self, beatmap, no_fail=False):
        self.bm = beatmap
        self.objs = beatmap.objects
        self.w300, self.w100, self.w50 = beatmap.hit_windows
        self.radius = beatmap.radius
        n = len(self.objs)
        self.results = [None] * n      # 300 / 100 / 50 / 0 (miss) per circle
        self.errors = [None] * n       # hit time - circle time (ms); + = late
        self.first_unjudged = 0
        self.score = 0
        self.combo = 0
        self.max_combo = 0
        self.counts = {300: 0, 100: 0, 50: 0, 0: 0}
        self.health = 1.0
        self.no_fail = no_fail
        self.failed = False
        self.drain_per_s = 0.01 + 0.004 * beatmap.hp
        self.miss_penalty = 0.06 + 0.012 * beatmap.hp
        self._events = []
        self._last_ms = None

    # ------------------------------------------------------------- input
    def press(self, ms, pos):
        """A pinch/click at song time ms and playfield position pos.
        Hits the earliest unjudged circle that is both in its timing window and
        under the cursor. Returns the judgment, or None if nothing was hit."""
        for i in range(self.first_unjudged, len(self.objs)):
            o = self.objs[i]
            if o.time - ms > self.w50:
                break                       # this and all later circles are too far ahead
            if self.results[i] is not None:
                continue
            if abs(ms - o.time) <= self.w50 and math.hypot(pos[0] - o.x, pos[1] - o.y) <= self.radius:
                err = ms - o.time
                if abs(err) <= self.w300:
                    j = 300
                elif abs(err) <= self.w100:
                    j = 100
                else:
                    j = 50
                self._judge(i, j, ms, err)
                return j
        return None

    # ------------------------------------------------------------- time passing
    def update(self, ms):
        if self.failed:
            return
        # circles whose window has passed without a hit are misses
        for i in range(self.first_unjudged, len(self.objs)):
            o = self.objs[i]
            if ms <= o.time + self.w50:
                break
            if self.results[i] is None:
                self._judge(i, 0, ms, None)
        while self.first_unjudged < len(self.objs) and self.results[self.first_unjudged] is not None:
            self.first_unjudged += 1

        # passive health drain while there is something to play
        if self._last_ms is not None and self.first_unjudged < len(self.objs):
            next_t = self.objs[self.first_unjudged].time
            if ms >= self.objs[0].time and next_t - ms < self.BREAK_GAP_MS:
                self.health -= self.drain_per_s * max(0.0, ms - self._last_ms) / 1000
        self._last_ms = ms
        self.health = min(max(self.health, 0.0), 1.0)
        if self.health <= 0 and not self.no_fail:
            self.failed = True

    def _judge(self, i, j, ms, err):
        self.results[i] = j
        self.errors[i] = err
        self.counts[j] += 1
        if j == 0:
            self.combo = 0
            self.health -= self.miss_penalty
        else:
            self.score += int(j * (1 + self.combo / 25))   # combo multiplies score (osu! style)
            self.combo += 1
            self.max_combo = max(self.max_combo, self.combo)
            self.health += {300: 0.04, 100: 0.015, 50: -0.01}[j]
        self.health = min(max(self.health, 0.0), 1.0)
        self._events.append((i, j, ms, err))

    def drain_events(self):
        """Judgments since the last call, for animations and sounds."""
        events, self._events = self._events, []
        return events

    def finished(self, ms):
        return self.first_unjudged >= len(self.objs) and ms > self.objs[-1].time + 1500

    # ------------------------------------------------------------- stats
    @property
    def judged(self):
        return sum(self.counts.values())

    @property
    def accuracy(self):
        if not self.judged:
            return 1.0
        c = self.counts
        return (300 * c[300] + 100 * c[100] + 50 * c[50]) / (300 * self.judged)

    def hit_errors(self):
        return [e for e in self.errors if e is not None]

    @property
    def mean_error(self):
        e = self.hit_errors()
        return statistics.mean(e) if e else 0.0

    @property
    def unstable_rate(self):
        """osu!'s 'UR': 10 x standard deviation of hit errors. Lower = more consistent."""
        e = self.hit_errors()
        return 10 * statistics.pstdev(e) if len(e) > 1 else 0.0

    def grade(self):
        if self.failed:
            return "F"
        acc = self.accuracy
        if acc >= 1.0:
            return "SS"
        if acc >= 0.95:
            return "S"
        if acc >= 0.90:
            return "A"
        if acc >= 0.80:
            return "B"
        if acc >= 0.70:
            return "C"
        return "D"
