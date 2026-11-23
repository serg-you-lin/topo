"""
tests/package/test_english_only.py
----------------------------------
The code is written in English, and decisions are not cited in it. In every
`.py` file of the packages, the tests and the tutorial, the comments, the
docstrings and the names (functions, classes, arguments) carry no Italian word
of `ITALIAN` and no decision number (`D` and two or three digits). In the
packages every string is checked too: their messages reach the caller. In the
tests and the tutorial the other strings are data (a drawing's texts, a
fixture's labels) and are not checked, nor are file names and snake_case names
quoted in a text (a fixture is named as it is). `scripts/` is out of scope.
`ITALIAN` holds only words that are not English too ("per", "non", "come" are).
"""

import ast
import io
import re
import tokenize
import unittest

from tests.paths import PROJECT_ROOT

FOLDERS = ("topo", "topo_dxf", "topo_pdf", "tests", "tutorial")
PACKAGES = ("topo", "topo_dxf", "topo_pdf")

# words that are Italian and not English: one is enough
ITALIAN = frozenset("""
il gli della delle dello degli dei nella nelle nello negli sulla sulle sullo
alla alle allo agli dalla dalle dallo dagli che sono questo questa questi queste
quello quella quando perché perche cioè ogni anche dove già più però essere
viene vengono resta restano deve devono punto punti lato lati catena spigolo
spigoli curva retta rette arco archi cerchio cerchi capo capi diventa
tratto pezzo pezzi uguale uguali sempre mai niente nessun nessuna altrimenti
genera generano figli figlio figlia padre padri altro altra altri altre striscia
strisce contorno contorni foro fori piega pieghe foglio fogli disegno disegni
con una uno del nel nei tra fra sia poi ancora trovato trovata trovati
manca mancano chiuso chiusa aperto aperta vicino vicini lungo lunga errore
attenzione valore valori esterno interno esterni interni sinistra destra sopra
sotto pagina pagine
""".split())
DECISION = re.compile(r"\bD\d{2,3}\b")
WORD = re.compile(r"[A-Za-zÀ-ÿ]+")
QUOTED_NAME = re.compile(r"\S+\.[A-Za-z]{2,4}|\w+(?:_\w+)+")
NAME_PART = re.compile(r"_|(?<=[a-z])(?=[A-Z])")

# the documents a reader finds on GitHub: the decision log and the to-do list are
# not published, so they cannot be cited there (`CLAUDE.md` is the working
# agreement of the sessions and names them on purpose)
PUBLISHED_DOCUMENTS = ("README.md", "README_IT.md", "SCRIPTS.md", "tutorial/README.md",
                       "docs/API.md", "docs/ARCHITECTURE.md", "docs/LIMITS.md", "docs/LIMITS_IT.md",
                       "docs/LLM.md", "docs/TEXTS.md")
LOCAL_FILE = re.compile(r"\b(?:MAP|TODO)(?:_ARCHIVE)?\.md\b")


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
                docstrings = set()
                for node in ast.walk(tree):
                    if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        doc = ast.get_docstring(node, clean=False)
                        if doc:
                            docstrings.add(id(node.body[0].value))
                            texts.append((node.body[0].lineno, doc, WORD.findall(QUOTED_NAME.sub(" ", doc))))
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        texts.append((node.lineno, node.name, NAME_PART.split(node.name)))
                    elif isinstance(node, ast.arg):
                        texts.append((node.lineno, node.arg, NAME_PART.split(node.arg)))
                if folder in PACKAGES:
                    texts += [(node.lineno, node.value, WORD.findall(QUOTED_NAME.sub(" ", node.value)))
                              for node in ast.walk(tree)
                              if isinstance(node, ast.Constant) and isinstance(node.value, str)
                              and id(node) not in docstrings]
                for line, text, words in texts:
                    bad = sorted({w for w in words if w.lower() in ITALIAN}) + DECISION.findall(text)
                    if bad:
                        found.append(f"{path.relative_to(PROJECT_ROOT).as_posix()}:{line}: {' '.join(bad)}")
        self.assertEqual(found, [], "\n" + "\n".join(found))

    def test_published_documents_cite_no_decision_and_no_local_file(self):
        found = []
        for path in PUBLISHED_DOCUMENTS:
            for number, line in enumerate((PROJECT_ROOT / path).read_text(encoding="utf-8").splitlines(), 1):
                bad = DECISION.findall(line) + LOCAL_FILE.findall(line)
                if bad:
                    found.append(f"{path}:{number}: {' '.join(bad)}")
        self.assertEqual(found, [], "\n" + "\n".join(found))


if __name__ == "__main__":
    unittest.main()
