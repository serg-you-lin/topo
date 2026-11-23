"""
tests/package/test_deprecations.py
----------------------------------
A deprecated name lives two minors, then goes. Every `FutureWarning` raised in
the packages says in its message "deprecated in A.B" and "removed in A.C" with
C = B + 2; once the version in `pyproject.toml` reaches A.C the test fails until
the old name is removed. With no deprecation the test passes and waits.
"""

import ast
import re
import tomllib
import unittest

from tests.paths import PROJECT_ROOT

PACKAGES = ("topo", "topo_dxf", "topo_pdf")
DEPRECATED = re.compile(r"deprecated in (\d+)\.(\d+)")
REMOVED = re.compile(r"removed in (\d+)\.(\d+)")


class TestDeprecations(unittest.TestCase):

    def test_every_deprecation_says_when_it_goes_and_is_gone_by_then(self):
        version = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
        current = tuple(int(n) for n in version.split(".")[:2])
        found = []
        for package in PACKAGES:
            for path in sorted((PROJECT_ROOT / package).rglob("*.py")):
                tree = ast.parse(path.read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    if not (isinstance(node, ast.Call)
                            and any(isinstance(n, ast.Name) and n.id == "FutureWarning" for n in ast.walk(node))):
                        continue
                    where = f"{path.relative_to(PROJECT_ROOT).as_posix()}:{node.lineno}"
                    # the message: every literal piece of the call, f-strings included
                    text = " ".join(n.value for n in ast.walk(node)
                                    if isinstance(n, ast.Constant) and isinstance(n.value, str))
                    since, until = DEPRECATED.search(text), REMOVED.search(text)
                    if not since or not until:
                        found.append(f"{where}: the message must say 'deprecated in A.B' and 'removed in A.C'")
                        continue
                    since, until = tuple(map(int, since.groups())), tuple(map(int, until.groups()))
                    if until != (since[0], since[1] + 2):
                        found.append(f"{where}: deprecated in {since[0]}.{since[1]} must go in "
                                     f"{since[0]}.{since[1] + 2}, not {until[0]}.{until[1]}")
                    elif current >= until:
                        found.append(f"{where}: version {version} reached {until[0]}.{until[1]}: remove the old name")
        self.assertEqual(found, [], "\n" + "\n".join(found))


if __name__ == "__main__":
    unittest.main()
