"""
conftest.py
-----------
Every diagnostic code must fire somewhere in the suite. It is counted as the
suite runs, and only a full run (no path, `-k`, `-m` or `--lf`) is judged: if a
code never fired, or a code in `UNREACHED_CODES` fired, the run fails and says
which. A warning that dies, or a branch no test reaches, turns the suite red.
"""

import functools
import os

import pytest

from topo.model.diagnostic import Diagnostic
from tests.invariants import UNREACHED_CODES, all_codes

_fired: set = set()
_original_new = Diagnostic.__new__


@functools.wraps(_original_new)
def _recording_new(cls, code, *args, **kwargs):
    _fired.add(code)
    return _original_new(cls, code, *args, **kwargs)


Diagnostic.__new__ = _recording_new


def _is_full_run(config) -> bool:
    option = config.option
    narrowed = option.keyword or option.markexpr or getattr(option, "lf", False) or getattr(option, "failedfirst", False)
    paths = [a for a in config.invocation_params.args if os.path.exists(a) or "::" in a]
    return not (narrowed or paths)


def pytest_sessionfinish(session, exitstatus):
    if exitstatus != 0 or not _is_full_run(session.config):
        return
    never = sorted(all_codes() - _fired - UNREACHED_CODES)
    fired_unreached = sorted(UNREACHED_CODES & _fired)
    if never or fired_unreached:
        out = session.config.pluginmanager.get_plugin("terminalreporter")
        if never:
            out.write_line(f"diagnostic codes that never fired in the suite: {never}", red=True)
        if fired_unreached:
            out.write_line(f"codes listed as unreached that fired (take them out of UNREACHED_CODES): "
                           f"{fired_unreached}", red=True)
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
