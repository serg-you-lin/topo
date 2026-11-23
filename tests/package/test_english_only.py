"""
tests/package/test_english_only.py
----------------------------------
The code is written in English, and decisions are not cited in it. In every
`.py` file of the packages, the tests and the tutorial, the comments, the
docstrings and the names (functions, classes, arguments) carry no Italian word
of `ITALIAN` and no decision number (`D` and two or three digits). String
literals that are not docstrings are data (a drawing's texts, a fixture's
labels) and are not checked, nor are file names and snake_case names quoted
in a text (a fixture is named as it is). `scripts/` is out of scope.
"""

import ast
import io
import re
import tokenize
import unittest

from tests.paths import PROJECT_ROOT

FOLDERS = ("topo", "topo_dxf", "topo_pdf", "tests", "tutorial")

# words that are Italian and not English: one is enough
ITALIAN = frozenset("""
il gli della delle dello degli dei nella nelle nello negli sulla sulle sullo
alla alle allo agli dalla dalle dallo dagli che sono questo questa questi queste
quello quella quando perché perche cioè ogni anche dove già più però essere
viene vengono resta restano deve devono punto punti lato lati catena spigolo
spigoli curva retta rette arco archi cerchio cerchi capo capi diventa
tratto pezzo pezzi uguale uguali sempre mai niente nessun nessuna altrimenti
""".split())
DECISION = re.compile(r"\bD\d{2,3}\b")
WORD = re.compile(r"[A-Za-zÀ-ÿ]+")
QUOTED_NAME = re.compile(r"\S+\.[A-Za-z]{2,4}|\w+(?:_\w+)+")
NAME_PART = re.compile(r"_|(?<=[a-z])(?=[A-Z])")


class TestEnglishOnly(unittest.TestCase):

    def test_no_italian_and_no_decision_numbers_in_the_code(self):
        found = []
        for folder in FOLDERS:
            for path in sorted((PROJECT_ROOT / folder).rglob("*.py")):
                source = path.read_text(encoding="utf-8")
                tree = ast.parse(source)
                texts = [(tok.start[0], tok.string, WORD.findall(QUOTED_NAME.sub(" ", tok.string)))
                         for tok in tokenize.generate_tokens(io.StringIO(source).readline)
                         if tok.type == tokenize.COMMENT]
                for node in ast.walk(tree):
                    if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        doc = ast.get_docstring(node, clean=False)
                        if doc:
                            texts.append((node.body[0].lineno, doc, WORD.findall(QUOTED_NAME.sub(" ", doc))))
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        texts.append((node.lineno, node.name, NAME_PART.split(node.name)))
                    elif isinstance(node, ast.arg):
                        texts.append((node.lineno, node.arg, NAME_PART.split(node.arg)))
                for line, text, words in texts:
                    bad = sorted({w for w in words if w.lower() in ITALIAN}) + DECISION.findall(text)
                    if bad:
                        found.append(f"{path.relative_to(PROJECT_ROOT).as_posix()}:{line}: {' '.join(bad)}")
        self.assertEqual(found, [], "\n" + "\n".join(found))


if __name__ == "__main__":
    unittest.main()
