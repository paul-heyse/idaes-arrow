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
"""Comparators for Python-versus-Rust parity assertions.

Bit-exact is the default. ``rtol``/``atol`` of zero is not pedantry: users
baseline results from the pure-Python implementations, so a last-ULP difference
is a silent regression rather than a rounding detail. A case that needs a
tolerance must justify it in its ``note``.
"""

import numpy as np


def auto(expected, actual, rtol=0.0, atol=0.0):
    """Compare two results, dispatching on the type of ``expected``."""
    if _is_pandas(expected, "DataFrame"):
        return frames(expected, actual, rtol, atol)
    if _is_pandas(expected, "Series"):
        return series(expected, actual, rtol, atol)
    if type(expected).__module__.split(".")[0] == "pyarrow":
        return arrow(expected, actual)
    if isinstance(expected, dict):
        assert list(expected) == list(
            actual
        ), f"dict key order differs: {list(expected)} != {list(actual)}"
        for key in expected:
            auto(expected[key], actual[key], rtol, atol)
        return None
    if isinstance(expected, (list, tuple)):
        assert type(expected) is type(
            actual
        ), f"container type differs: {type(expected)} != {type(actual)}"
        assert len(expected) == len(
            actual
        ), f"length differs: {len(expected)} != {len(actual)}"
        for exp, act in zip(expected, actual):
            auto(exp, act, rtol, atol)
        return None
    return numeric(expected, actual, rtol, atol)


def _is_pandas(obj, name):
    cls = type(obj)
    return cls.__module__.split(".")[0] == "pandas" and cls.__name__ == name


def numeric(expected, actual, rtol=0.0, atol=0.0):
    """Compare scalars or arrays, exactly unless a tolerance is given."""
    exp = np.asarray(expected)
    act = np.asarray(actual)
    assert exp.dtype == act.dtype, f"dtype differs: {exp.dtype} != {act.dtype}"
    assert exp.shape == act.shape, f"shape differs: {exp.shape} != {act.shape}"
    if rtol == 0.0 and atol == 0.0:
        assert np.array_equal(
            exp, act, equal_nan=exp.dtype.kind == "f"
        ), f"values differ; first mismatch at {_first_diff(exp, act)}"
        if exp.dtype.kind == "f":
            # 0.0 == -0.0 compares equal but serializes differently, and the sign
            # of zero survives into JSON that users diff.
            assert np.array_equal(
                np.signbit(exp), np.signbit(act)
            ), "signed zero differs"
        return None
    np.testing.assert_allclose(act, exp, rtol=rtol, atol=atol, equal_nan=True)
    return None


def _first_diff(expected, actual):
    """Index and values of the first differing element, for the failure message."""
    flat_exp = np.asarray(expected).ravel()
    flat_act = np.asarray(actual).ravel()
    for index, (exp, act) in enumerate(zip(flat_exp, flat_act)):
        if exp != act and not (exp != exp and act != act):
            return f"flat index {index}: {exp!r} != {act!r}"
    return "no elementwise difference found"


def ulp_diff(expected, actual):
    """Distance in representable float64 steps. For diagnosing near-misses."""
    exp = np.asarray(expected, dtype="float64").view("int64")
    act = np.asarray(actual, dtype="float64").view("int64")
    floor = np.int64(np.iinfo(np.int64).min)
    exp = np.where(exp < 0, floor - exp, exp)
    act = np.where(act < 0, floor - act, act)
    return np.abs(exp - act)


def frames(expected, actual, rtol=0.0, atol=0.0):
    """Compare DataFrames including dtype, index, and column order.

    ``check_dtype`` is load-bearing: an Arrow round-trip turns nullable columns
    into ``Int64``/``string[pyarrow]``, which silently changes what
    ``DataFrame.to_dict(orient="tight")`` writes into users' JSON files.
    """
    import pandas.testing as pdt  # pylint: disable=import-outside-toplevel

    exact = rtol == 0.0 and atol == 0.0
    kwargs = {} if exact else {"rtol": rtol, "atol": atol}
    pdt.assert_frame_equal(
        actual,
        expected,
        check_dtype=True,
        check_index_type="equiv",
        check_column_type="equiv",
        check_names=True,
        check_like=False,
        check_exact=exact,
        **kwargs,
    )


def series(expected, actual, rtol=0.0, atol=0.0):
    """Compare Series including dtype, index, and name."""
    import pandas.testing as pdt  # pylint: disable=import-outside-toplevel

    exact = rtol == 0.0 and atol == 0.0
    kwargs = {} if exact else {"rtol": rtol, "atol": atol}
    pdt.assert_series_equal(
        actual, expected, check_dtype=True, check_exact=exact, **kwargs
    )


def arrow(expected, actual):
    """Compare Arrow tables including schema metadata, ignoring chunking."""
    exp = expected.combine_chunks()
    act = actual.combine_chunks()
    assert exp.schema.equals(
        act.schema, check_metadata=True
    ), f"schema differs:\n{exp.schema}\n---\n{act.schema}"
    assert exp.equals(act), "table contents differ"
