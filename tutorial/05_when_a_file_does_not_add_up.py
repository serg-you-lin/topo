"""
05_when_a_file_does_not_add_up.py — the inspector and the messages
==================================================================

What you learn
    topo_dxf.inspect_file    prints three levels: the raw DXF, what the loader understood, what topo produced
    topo.Diagnostic          every message: level, code, message, points (where), help (a suggestion)
    warnings / notes / errors   look at it / what topo did by itself / nothing to read

doubles_and_crossings.dxf is a rectangle drawn carelessly: one side twice, a
short copy 0.02 mm above it, two sides running 5 mm past the corners, and a
cross drawn over the hole. Read what topo says before you change anything.
The `help` of a message is a suggestion (experimental): judge it before you use it.

Open afterwards
    tutorial/files/doubles_and_crossings.dxf next to
    tutorial_output/05_when_a_file_does_not_add_up/<name>_read.dxf: what became a
    contour, and what stayed on the Trash layer (loose).

Your own file
    set INPUT; INSPECT = True prints the long three-level dump too.
"""
import _paths  # noqa: F401

from pathlib import Path

import topo
import topo_dxf

# --- CONFIG ------------------------------------------------------------------
INPUT = r"tutorial/files/doubles_and_crossings.dxf"
INSPECT = True
# -----------------------------------------------------------------------------

if INSPECT:
    topo_dxf.inspect_file(INPUT)
    print("=" * 80)

doc = topo_dxf.load_dxf(INPUT)
network = topo.heal(doc)
result = network.faces()

print(f"\n{INPUT}")
print(f"  network: {len(network.edges)} edges, {len(network.free_ends)} free end(s), {len(network.crossings)} crossing(s)")
print(f"  faces(): valid={result.is_valid}, {len(result.clusters)} part(s), {len(result.loose)} loose curve(s)\n")

for message in doc.notes + doc.warnings + result.errors + result.warnings:
    print(f"[{message.level}] {message.code}")
    print(f"    {message.message}")
    for x, y in message.points[:3]:
        print(f"    at ({x:.3f}, {y:.3f})")
    if message.help:
        print(f"    help: {message.help}")

print(f"\n{len(result.notes)} note(s) on what topo did by itself: {sorted({n.code for n in result.notes})}")

path = _paths.out("05_when_a_file_does_not_add_up") / f"{Path(INPUT).stem}_read.dxf"
topo_dxf.to_dxf(result, doc).saveas(path)
print(f"written {path}")
