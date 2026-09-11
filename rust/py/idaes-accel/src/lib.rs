// SPDX-License-Identifier: BSD-3-Clause
// Copyright (c) 2026 Paul Heyse.
// Part of a fork of the IDAES Integrated Platform (IDAES IP);
// see LICENSE.md and COPYRIGHT.md at the repository root.

//! `idaes_accel._core` -- the PyO3 boundary for the `idaes-accel` distribution.
//!
//! This module is deliberately thin. It marshals arguments, releases the GIL,
//! calls into `idaes_accel_core`, and maps errors. No algorithm lives here.
//!
//! # Naming convention
//!
//! Symbols are exported with their registry key, `.` replaced by `__`, so
//! `idaes.accel` can resolve them mechanically from the key alone:
//! `pysmo.sampling.prime_number_generator` -> `pysmo__sampling__prime_number_generator`.

use pyo3::prelude::*;

/// Bumped on ANY change to argument or return marshalling, kernel semantics, or
/// exported symbol names.
///
/// `idaes-pse` and `idaes-accel` version independently, so this integer -- not a
/// version string -- is the compatibility contract. `idaes/accel/compat.py`
/// requires **exact equality**, because breakage is bidirectional: a new
/// `idaes-pse` with an old `idaes-accel` is just as wrong as the reverse.
const ABI_VERSION: u32 = 1;

/// First `n` primes. See `idaes_accel_core::sampling::prime_number_generator`.
///
/// Returns a Python `list[int]`, not a NumPy array: `HaltonSampling.sample_points`
/// indexes this and feeds the element into integer arithmetic.
#[pyfunction]
#[pyo3(name = "pysmo__sampling__prime_number_generator")]
fn pysmo_sampling_prime_number_generator(py: Python<'_>, n: i64) -> Vec<u64> {
    // Pure Rust, no Python objects touched: safe to drop the GIL.
    py.detach(|| idaes_accel_core::sampling::prime_number_generator(n))
}

#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("__abi_version__", ABI_VERSION)?;
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    m.add_function(wrap_pyfunction!(pysmo_sampling_prime_number_generator, m)?)?;
    Ok(())
}
