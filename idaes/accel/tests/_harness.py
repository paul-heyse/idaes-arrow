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
"""Turn registered parity cases into pytest parameters."""

import importlib.util

import pytest

from idaes.accel import _discovery, parity


def to_params(tier):
    """Parameters for one tier, each carrying its own optional-import skips.

    Optional dependencies are gated per case with ``skipif`` rather than through
    the ``Importorskipper`` plugin in ``idaes/conftest.py``: that plugin skips an
    entire module, which would silently drop every parity case if one case
    happened to need something that was not installed.

    ``skipif`` is safe to attach per parameter because it is not one of the
    required markers that ``idaes/conftest.py`` counts.
    """
    _discovery.discover()
    params = []
    for case in parity.cases(tier):
        marks = [
            pytest.mark.skipif(
                importlib.util.find_spec(module) is None,
                reason=f"{module} is not installed",
            )
            for module in case.requires
        ]
        params.append(pytest.param(case, id=case.id, marks=marks))
    return params
