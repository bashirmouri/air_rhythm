"""Air Rhythm: an osu!-style rhythm game played with your hand in front of a webcam.

Layers (see docs/architecture.md): core (game rules) -> content (generated songs/maps)
-> controls (hand/mouse) -> ui (widgets and screens) -> app (startup and main loop),
with system (config, settings, logging) used by all of them.

The version below is the only place it is written down. It is shown in the menu, written
to the log, and read by pyproject.toml and the build/release tools. Update CHANGELOG.md with it.
"""
__version__ = "0.1.0"
