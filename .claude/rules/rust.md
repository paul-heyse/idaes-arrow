---
description: Invariants for the Rust workspace
paths:
  - "rust/**"
---

# Working in `rust/`

Run `cargo` from `rust/`, not the repo root — `rust-toolchain.toml` and
`.cargo/config.toml` resolve by ancestry, so the pinned 1.98.1 only applies there.

## One type universe

Exactly one version of `arrow`, `parquet`, `object_store` and `datafusion` may
exist in the dependency graph. Two majors make `downcast_ref` return `None` with
no compile error — the failure is silent and looks like a logic bug.

- Import Arrow through `datafusion::arrow::…`, never the bare `arrow` crate.
  The `arrow-through-datafusion` ast-grep rule enforces this for `rust/crates/**`.
- `rust/py/**` is exempt: the PyO3 boundary must speak `pyo3-arrow`'s types.
- Pins and their reasoning are in the `rust/Cargo.toml` header comment. Note
  `object_store` is `=0.13.2` deliberately — DataFusion 55 requires `^0.13.2`,
  so crates.io's newer 0.14.x would split the graph.

## The FFI boundary

- `panic = "unwind"` is required. PyO3 converts unwinds into Python exceptions;
  `abort` takes the interpreter down. `clippy::panic` and `clippy::unwrap_used`
  are denied for the same reason.
- Release the GIL with `py.detach()` around Arrow kernels, IO and Rayon work.
  **Never touch a Python object, `Bound<'py, _>`, refcount or exception inside
  that closure** — clone Rust-owned values in first.
- Take wrapper types by value in `#[pyfunction]` signatures (`values: PyArray`,
  not `&PyArray`).
- `PyArray::new` panics on a field/type mismatch; use `try_new`.
- Keep the `cdylib` thin. sccache cannot cache `cdylib`/`bin`/`proc-macro`
  crates, so real logic belongs in an `rlib` under `crates/`.

## Before you claim it works

`just ci-fast` covers fmt, clippy `-D warnings`, nextest and doctests. **nextest
does not run doctests** — that is why they are a separate step, not redundancy.
For anything touching `unsafe` or concurrency, `just miri-seeds <pkg> 32`; one
seed proves one interleaving.

Every `.rs` file carries the 4-line SPDX header (`just headers-rust`), not the
12-line IDAES block used for Python.
