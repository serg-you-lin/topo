# topo tutorial

Thirteen short lessons, from drawing a part in code to reading a folder of your
own drawings. Each one is a script you run as it is (VS Code's Run button, or
`python tutorial/01_build_a_part.py`): no arguments. To use your own drawing,
change the path in the `CONFIG` block at the top of the lesson.

Every lesson prints what it found and writes its files to
`tutorial_output/<lesson>/`. Open them in your CAD next to the original: topo's
results are meant to be judged by eye. The drawings the lessons read are in
`tutorial/files/`.

| # | lesson | what you learn |
|---|---|---|
| 01 | `01_build_a_part.py` | draw a part in code (`topo.geometry`), read it with `heal().faces()`, write a DXF |
| 02 | `02_read_the_shapes.py` | area, centroid, nesting depth, which shape each contour is |
| 03 | `03_open_a_dxf.py` | open a DXF, what the loader understood, `is_valid` before writing |
| 04 | `04_z_levels.py` | a drawing with heights brought onto the plane, one layer per case |
| 05 | `05_when_a_file_does_not_add_up.py` | the three-level inspector and topo's messages (warnings, notes, errors) |
| 06 | `06_close_the_gaps.py` | `tolerance` and `max_gap`: which gaps topo closes |
| 07 | `07_circles_from_segments.py` | when many short lines are rebuilt as a circle |
| 08 | `08_split_into_parts.py` | one file per part, named by the text inside it; JSON facts |
| 09 | `09_roles.py` | tell topo what is not the part: by name, by dashed line, by colour |
| 10 | `10_faces_and_outlines.py` | two readings of the same drawing |
| 11 | `11_geometry_facts.py` | intersections, cuts, union and difference of contours, concentric circles |
| 12 | `12_from_plain_data.py` | geometry from plain dicts, no file |
| 13 | `13_your_drawings.py` | a whole folder of your drawings, with a report |

Needs: `pip install g-topo[dxf]` (or the repository installed with its `dxf` extra).

Found something that looks wrong? Lesson 13's `report.txt` and the drawing
(only if you may share it) are what we need to look at it.
