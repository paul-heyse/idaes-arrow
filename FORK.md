# About this fork

This repository is a fork of [IDAES/idaes-pse](https://github.com/IDAES/idaes-pse), the IDAES
Process Systems Engineering Framework, forked at tag `2.13.0rc0` (commit `70a8f4fe1`).

It is **not** an official IDAES release and is not affiliated with or endorsed by the IDAES
Institute, its sponsors, or the U.S. Department of Energy. For the supported project, use upstream.

## What is different here

The purpose of this fork is to integrate Rust-based [Apache Arrow](https://arrow.apache.org/) and
[DataFusion](https://datafusion.apache.org/) capability into data-heavy parts of the framework.

* The existing Python tree under `idaes/` keeps its upstream folder structure, so changes stay easy
  to map back to upstream and upstream merges stay cheap.
* All Rust lives in a single Cargo workspace under `rust/`.
* Acceleration ships as a **separate** distribution, `idaes-accel`, built with
  [maturin](https://www.maturin.rs/). The `idaes-pse` distribution itself remains a pure-Python
  wheel built exactly as upstream builds it.
* Accelerated code paths keep their original pure-Python implementation. `idaes/accel/` dispatches
  between the two, and every accelerated function is covered by a Python-vs-Rust parity test.
  Set `IDAES_ACCEL=off` to force the pure-Python path, or `force` to require the Rust one.

Installing `idaes-pse` from this fork without `idaes-accel` behaves exactly like upstream.

## Staying current with upstream

```bash
git remote add upstream https://github.com/IDAES/idaes-pse.git   # if not already present
just sync-upstream        # git fetch upstream --tags && git merge upstream/main
just divergence           # git diff --stat upstream-main..main
```

The `upstream-main` branch is a pristine mirror of upstream's `main` and is never committed to
directly; it exists to give a clean merge base and an honest measure of how far this fork has drifted.

## Licensing

Upstream code remains under the BSD-3-Clause license in `LICENSE.md`, with the copyright and
government-rights notice in `COPYRIGHT.md`; upstream Python files keep their original headers.

New Rust source files added by this fork are also BSD-3-Clause but carry their own short header,
because the upstream header asserts copyright held by institutions that did not author them:

```rust
// SPDX-License-Identifier: BSD-3-Clause
// Copyright (c) 2026 Paul Heyse.
// Part of a fork of the IDAES Integrated Platform (IDAES IP);
// see LICENSE.md and COPYRIGHT.md at the repository root.
```

## Upstream CI in this fork

Upstream's workflows are retained but guarded with
`if: github.repository == 'IDAES/idaes-pse'` where they would publish to PyPI or need upstream
secrets, and the daily cron jobs are likewise limited to upstream. Push and pull-request CI runs
normally here.
