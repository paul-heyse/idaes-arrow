# `rust/` — the idaes-arrow Rust workspace

Everything Rust in this fork lives here. The Python tree under `idaes/` keeps its
upstream layout so merges from `IDAES/idaes-pse` stay cheap; nothing in this
directory changes how upstream Python is organised.

## Layout

```
rust/
├── crates/               pure-Rust rlib crates -- all real logic
│   └── idaes-accel-core  numeric kernels, no Python awareness
├── py/
│   └── idaes-accel       the single PyO3 cdylib + its maturin project
├── Cargo.toml            workspace, pins, lints, profiles
├── rust-toolchain.toml   pinned stable; nightly only via explicit `+nightly`
├── clippy.toml           lint config (test exemptions, prose idents)
├── deny.toml             license / advisory / source / duplicate-version policy
├── bacon.toml            background check jobs
└── .config/nextest.toml  test profiles, retries, timeouts, JUnit
```

Two rules shape this:

1. **The cdylib stays thin.** sccache cannot cache `cdylib`, `bin`, `dylib` or
   `proc-macro` crates -- they invoke the system linker. It caches `rlib` crates.
   So `py/idaes-accel` marshals arguments and nothing else.
2. **One type universe.** When Arrow/DataFusion land, exactly one version of each
   of `arrow`, `parquet`, `object_store` and `datafusion` may exist in the graph.
   Two majors make `downcast_ref` return `None` with no compile error. `just
   one-type-universe` and `cargo deny check bans` both enforce this.

Crates deliberately *not* created yet: `idaes-arrow` (schema contracts) and
`idaes-engine` (`SessionContext` factory, UDF registry). They arrive with the
first query-shaped target. Packages are not created to organise concepts.

## Commands

Run everything through `just` from the repository root -- `just --list`. The
useful entry points are `just ci-fast` (fmt, check, clippy, tests, doctests,
dependency hygiene, spelling) and `just accel-wheel-verify` (build a wheel and
install it into a throwaway venv, which is the only thing that actually validates
packaging -- `maturin develop` does not).

## Pins

See the header comment in `Cargo.toml`. Short version: `datafusion 55.0.0`,
`arrow`/`parquet` `59.3.0`, `object_store 0.13.2` (**not** the newer 0.14.x --
DataFusion 55 requires `^0.13.2`), `pyo3 0.29`, `pyo3-arrow 0.19.0`.
MSRV is 1.94.0, set by DataFusion.

## Licensing

New Rust sources carry a four-line SPDX header rather than the twelve-line IDAES
block, because that block asserts copyright held by institutions that did not
author them. `just headers-rust` checks it. See `FORK.md`.
