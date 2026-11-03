"""The layer rules from docs/architecture.md, checked by reading every module's imports.

Lower layers never import higher ones, so game rules can't break because the interface
changed, and they stay testable without a window or camera."""
import ast
import os

from conftest import SRC

PACKAGE = os.path.join(SRC, "air_rhythm")

# layer -> the air_rhythm layers it may import (besides itself and the package's __version__)
ALLOWED = {
    "system": set(),
    "core": {"system"},
    "content": {"core", "system"},
    "controls": {"system"},
    "ui": {"core", "content", "system"},
    "app": {"core", "content", "controls", "ui", "system"},
    "__main__": {"app"},
    "__init__": set(),
}


def modules():
    """(path relative to the package, its layer, its parsed source) for every module."""
    for folder, _, files in os.walk(PACKAGE):
        for f in files:
            if f.endswith(".py"):
                path = os.path.join(folder, f)
                rel = os.path.relpath(path, PACKAGE).replace(os.sep, "/")
                tree = ast.parse(open(path, encoding="utf-8").read())
                yield rel, rel.split("/")[0].removesuffix(".py"), tree


def air_rhythm_imports(tree):
    """The air_rhythm layers a module imports (e.g. "core" for air_rhythm.core.gameplay)."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names = [node.module]
        else:
            continue
        for name in names:
            parts = name.split(".")
            if parts[0] == "air_rhythm" and len(parts) > 1:
                yield parts[1]


def test_every_module_belongs_to_a_known_layer():
    unknown = {layer for _, layer, _ in modules()} - set(ALLOWED)
    assert not unknown, f"new top-level module or folder: add it to ALLOWED: {unknown}"


def test_layers_only_import_downwards():
    problems = [f"{rel} imports air_rhythm.{used}"
                for rel, layer, tree in modules()
                for used in sorted(set(air_rhythm_imports(tree)))
                if used != layer and used not in ALLOWED[layer]]
    assert problems == []


def test_no_relative_imports():
    # absolute imports (from air_rhythm.core import ...) keep every file readable on its own
    relative = [rel for rel, _, tree in modules()
                if any(isinstance(n, ast.ImportFrom) and n.level for n in ast.walk(tree))]
    assert relative == []
