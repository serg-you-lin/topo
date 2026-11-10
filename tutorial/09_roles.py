"""
09_roles.py — tell topo what is not the part
============================================

What you learn
    topo.RoleRule(role, name=, dashed=, color=)   a rule: every condition true -> that role
    topo.name_rules({name: role})                 shortcut for rules on the name only
    load_dxf(role_rules=...)                      rules are applied when the file is read
    topo.RoleStyle + to_dxf(role_styles=, layers=)   your colour and layer for each role

topo knows three roles: unknown, outer, inner. Any other word is yours: an edge
with your role stays out of the contours and comes back in `loose` with that
role, on its own layer. Here roles.dxf has a part, a frame around it, dashed
axes and cyan marks. Read with no rules, the frame is the outer of the only
part and the real part is a hole inside it. The first rule that matches wins,
in the order you write them.

Open afterwards
    tutorial_output/09_roles/roles_<step>.dxf, one file per step in STEPS.

Your own file
    set INPUT, and write your rules in my_roles(): your layer names, dashed or
    not, the colour.
"""
import _paths  # noqa: F401

from pathlib import Path

import topo
import topo_dxf

# --- CONFIG ------------------------------------------------------------------
INPUT = r"tutorial/files/roles.dxf"
# -----------------------------------------------------------------------------


def my_roles():
    """Your roles in one place: the rules that assign them, a colour and a layer for each."""
    rules = [
        topo.RoleRule("frame", name="Frame"),
        topo.RoleRule("axis", dashed=True),
        topo.RoleRule("reference_mark", color="cyan"),
    ]
    styles = {
        "frame": topo.RoleStyle(color=(128, 128, 128)),
        "axis": topo.RoleStyle(color=(255, 0, 0)),
        "reference_mark": topo.RoleStyle(color=(0, 200, 255)),
    }
    layers = {"frame": "MyFrame", "axis": "MyAxes", "reference_mark": "MyMarks"}
    return rules, styles, layers


rules, styles, layers = my_roles()
STEPS = [
    ("no_rules", []),
    ("by_name", [rules[0]]),
    ("by_dash", [rules[1]]),
    ("by_colour", [rules[2]]),
    ("all", rules),
]

for step, step_rules in STEPS:
    doc = topo_dxf.load_dxf(INPUT, role_rules=step_rules)
    result = topo.heal(doc).faces()
    roles = sorted({e.role for e in doc.edges})
    print(f"{step:10s} roles {roles}")
    for cluster in result.clusters:
        print(f"           part: outer {cluster.outer.bbox}, {len(cluster.inners)} inner(s)")
    by_role = {}
    for curve in result.loose:
        by_role[curve.role] = by_role.get(curve.role, 0) + 1
    print(f"           loose by role {by_role}")
    for message in result.warnings:
        print(f"           {message.level} {message.code}")

    path = _paths.out("09_roles") / f"{Path(INPUT).stem}_{step}.dxf"
    topo_dxf.to_dxf(result, doc, role_styles=styles, layers=layers).saveas(path)
print(f"\nwritten {_paths.out('09_roles')}")
