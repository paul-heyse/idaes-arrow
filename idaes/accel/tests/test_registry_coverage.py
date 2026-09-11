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
"""Guards keeping the registry and the parity suite in step."""

import inspect

import pytest

from idaes.accel import _discovery, parity, registry

_discovery.discover()


@pytest.mark.unit
def test_every_accelerated_function_has_a_parity_case():
    """An accelerated function with no parity case is an untested divergence."""
    covered = {case.key for case in parity.cases()}
    missing = sorted(set(registry()) - covered)
    assert not missing, f"registered but not parity-tested: {missing}"


@pytest.mark.unit
def test_every_parity_case_targets_a_real_key():
    unknown = sorted({case.key for case in parity.cases()} - set(registry()))
    assert not unknown, f"parity cases for unknown keys: {unknown}"


@pytest.mark.unit
def test_signatures_survive_wrapping():
    """Sphinx renders ``(*args, **kwargs)`` if the signature is not preserved."""
    for key, accelerated in registry().items():
        assert inspect.signature(accelerated) == inspect.signature(
            accelerated.python_impl
        ), f"{key}: wrapper signature differs from the Python implementation"


@pytest.mark.unit
def test_wrappers_remain_resolvable_by_name():
    """``pickle`` and spawn-based parallelism resolve functions by qualified name."""
    for key, accelerated in registry().items():
        module = inspect.getmodule(accelerated.python_impl)
        resolved = getattr(module, accelerated.python_impl.__name__, None)
        assert resolved is accelerated, (
            f"{key}: {module.__name__}.{accelerated.python_impl.__name__} "
            "no longer resolves to the wrapper; pickling would break"
        )


@pytest.mark.unit
def test_accelerate_rejects_classes():
    """Wrapping a class would break issubclass() and getattr-by-name lookups."""
    from idaes.accel import accelerate  # pylint: disable=import-outside-toplevel

    with pytest.raises(TypeError, match="wraps functions, not classes"):

        @accelerate("test.rejects.classes")
        class _Sampler:  # pylint: disable=too-few-public-methods
            pass
