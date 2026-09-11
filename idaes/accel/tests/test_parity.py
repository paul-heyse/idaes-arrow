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


def _guard_allows(accelerated, args, kwargs):
    """Whether the acceleration precondition admits these arguments."""
    try:
        return bool(accelerated.guard(*args, **kwargs))
    except Exception:  # a guard that raises means "not accelerable"
        return False


def _assert_falls_back(accelerated, case, args, kwargs):
    """A guard-rejected input must behave exactly like the Python implementation.

    Compared through the dispatcher, not the kernel: this asserts the routing
    decision, which is the thing that can regress when a guard is loosened.
    """
    python_exc = dispatch_exc = None
    try:
        expected = accelerated.python_impl(*deepcopy(args), **deepcopy(kwargs))
    except BaseException as exc:  # comparing failure modes, so catch everything
        python_exc, expected = exc, None
    try:
        actual = accelerated(*args, **kwargs)
    except BaseException as exc:  # comparing failure modes, so catch everything
        dispatch_exc, actual = exc, None

    if python_exc is not None or dispatch_exc is not None:
        assert type(python_exc) is type(dispatch_exc), (
            f"{case.id}: guard-rejected input diverged -- python raised "
            f"{type(python_exc).__name__ if python_exc else None}, dispatch raised "
            f"{type(dispatch_exc).__name__ if dispatch_exc else None}"
        )
        return
    compare.auto(expected, actual)


def _assert_raises_alike(accelerated, rust, case, args, kwargs):
    """Both implementations must fail, and fail as the same exception type.

    A port that turns a `PyomoException` into a `TypeError` breaks every caller
    with `except PyomoException` around it, and no value comparison can see that.
    """
    python_exc = rust_exc = None
    try:
        result = accelerated.python_impl(*deepcopy(args), **deepcopy(kwargs))
    except BaseException as exc:  # comparing failure modes, so catch everything
        python_exc = exc
    else:
        pytest.fail(
            f"{case.id}: python implementation returned {result!r}, expected a raise"
        )

    try:
        rust(*args, **kwargs)
    except BaseException as exc:  # comparing failure modes, so catch everything
        rust_exc = exc
    else:
        pytest.fail(
            f"{case.id}: rust implementation returned normally, expected a raise"
        )

    assert type(python_exc) is type(rust_exc), (
        f"{case.id}: exception type differs -- "
        f"python raised {type(python_exc).__name__}({python_exc}), "
        f"rust raised {type(rust_exc).__name__}({rust_exc})"
    )


def run_case(case):
    """Assert the Python and Rust implementations agree for one case."""
    accelerated = registry().get(case.key)
    assert accelerated is not None, (
        f"parity case {case.id!r} targets unknown accel key {case.key!r}"
    )
    rust = accelerated.rust_impl
    if rust is None:
        pytest.skip(f"no Rust implementation for {case.key!r}")

    args, kwargs = case.make_args()
    python_args, python_kwargs = deepcopy(args), deepcopy(kwargs)

    # An input the guard rejects must not be compared against the Rust kernel --
    # the whole point of the guard is that the kernel is NOT equivalent there.
    # What has to hold instead is that the dispatcher actually falls back, which
    # is the behaviour users get.
    if accelerated.guard is not None and not _guard_allows(accelerated, args, kwargs):
        _assert_falls_back(accelerated, case, args, kwargs)
        return

    if case.raises:
        _assert_raises_alike(accelerated, rust, case, args, kwargs)
        return

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
