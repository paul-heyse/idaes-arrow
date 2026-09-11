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
"""Python-versus-Rust parity for every registered accelerated function.

Adding an accelerated function adds no test code here: register a
:class:`idaes.accel.parity.ParityCase` next to the implementation and it is
picked up automatically.

These tests never read ``IDAES_ACCEL``. They call both implementations directly,
which is what lets the identical file run under ``off`` and ``force`` without
duplication -- the environment variable is a CI job concern, not a test concern.

Note there are three test functions rather than one with per-parameter markers:
``idaes/conftest.py`` requires *exactly one* of unit/component/integration/
performance per test, and a function-level marker plus a parameter-level marker
would count as two.
"""

from copy import deepcopy

import pytest

from idaes.accel import registry
from idaes.accel.tests import compare
from idaes.accel.tests._harness import to_params


def run_case(case):
    """Assert the Python and Rust implementations agree for one case."""
    accelerated = registry().get(case.key)
    assert (
        accelerated is not None
    ), f"parity case {case.id!r} targets unknown accel key {case.key!r}"
    rust = accelerated.rust_impl
    if rust is None:
        pytest.skip(f"no Rust implementation for {case.key!r}")

    args, kwargs = case.make_args()
    python_args, python_kwargs = deepcopy(args), deepcopy(kwargs)

    expected = accelerated.python_impl(*python_args, **python_kwargs)
    actual = rust(*args, **kwargs)

    comparator = case.compare or compare.auto
    comparator(expected, actual, rtol=case.rtol, atol=case.atol)

    # A Rust implementation taking a mutable view of a NumPy buffer is a classic
    # silent divergence, so require the inputs to survive the call unchanged.
    compare.auto(python_args, args)
    compare.auto(python_kwargs, kwargs)


@pytest.mark.unit
@pytest.mark.parametrize("case", to_params("unit"))
def test_parity_unit(case, require_accel):  # pylint: disable=unused-argument
    run_case(case)


@pytest.mark.component
@pytest.mark.parametrize("case", to_params("component"))
def test_parity_component(case, require_accel):  # pylint: disable=unused-argument
    run_case(case)


@pytest.mark.integration
@pytest.mark.parametrize("case", to_params("integration"))
def test_parity_integration(case, require_accel):  # pylint: disable=unused-argument
    run_case(case)
