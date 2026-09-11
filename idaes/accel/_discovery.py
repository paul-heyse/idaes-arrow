#################################################################################
# The Institute for the Design of Advanced Energy Systems Integrated Platform
# Framework (IDAES IP) was produced under the DOE Institute for the
# Design of Advanced Energy Systems (IDAES).
#
# Copyright (c) 2018-2026 by the software owners: The Regents of the
# University of California, through Lawrence Berkeley National Laboratory,
# National Technology & Engineering Solutions of Sandia, LLC, Carnegie Mellon
# University, West Virginia University Research Corporation, et al.
# All rights reserved.  Please see the files COPYRIGHT.md and LICENSE.md
# for full copyright and license information.
#################################################################################
"""Explicit list of modules that register accelerated functions.

Registration is a side effect of importing the module that applies
:func:`idaes.accel.accelerate`, so anything enumerating the registry -- the
parity suite, the coverage guard, diagnostics -- has to make sure those modules
are imported first.

An explicit list is used rather than package walking. Walking ``idaes`` imports
hundreds of modules, pulls in every optional dependency, and makes the contents
of the registry depend on import order. Add one line here per call site.
"""

import importlib
import logging

_log = logging.getLogger(__name__)

CALL_SITES = ("idaes.core.surrogate.pysmo.sampling",)
"""Modules whose import registers accelerated functions and parity cases."""

_done = False


def discover(force: bool = False) -> None:
    """Import every call-site module, tolerating optional-dependency failures.

    An ``ImportError`` here means a module needs something that is not installed.
    That is not an error for discovery: its cases simply will not be registered,
    and the parity suite will not claim to have covered them.
    """
    global _done  # pylint: disable=global-statement
    if _done and not force:
        return
    for name in CALL_SITES:
        try:
            importlib.import_module(name)
        except ImportError as exc:
            _log.debug("idaes.accel: call site %s not importable: %s", name, exc)
    _done = True
