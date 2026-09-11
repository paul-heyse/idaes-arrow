// SPDX-License-Identifier: BSD-3-Clause
// Copyright (c) 2026 Paul Heyse.
// Part of a fork of the IDAES Integrated Platform (IDAES IP);
// see LICENSE.md and COPYRIGHT.md at the repository root.

//! Pure-Rust numeric kernels behind the `idaes-accel` Python extension.
//!
//! Nothing in this crate knows about Python. The PyO3 layer lives in
//! `rust/py/idaes-accel` and is a thin `#[pymodule]` shell over this crate --
//! partly for testability, and partly because sccache cannot cache `cdylib`
//! crates but does cache `rlib` crates like this one.
//!
//! # Parity contract
//!
//! Every kernel here has a pure-Python counterpart that remains in the `idaes`
//! tree and remains the default. These implementations must agree with it
//! **bit-for-bit** unless a specific [`crate`] item documents otherwise. That is
//! not a stylistic preference: users have baselined results from the Python
//! implementations, and a last-ULP difference is a silent regression.

pub mod sampling;
