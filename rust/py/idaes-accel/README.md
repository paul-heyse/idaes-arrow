# idaes-accel

Rust acceleration for the [IDAES Process Systems Engineering
Framework](https://github.com/IDAES/idaes-pse), built from the
[`paul-heyse/idaes-arrow`](https://github.com/paul-heyse/idaes-arrow) fork.

This package ships a compiled extension module and nothing else. It is useless on
its own -- `idaes-pse` from that fork discovers it at runtime through
`idaes.accel` and dispatches to it. With it absent, or with `IDAES_ACCEL=off`,
IDAES runs its original pure-Python implementations unchanged.

```bash
pip install "idaes-pse[accel]"     # from the fork
```

| `IDAES_ACCEL` | Behaviour |
| --- | --- |
| `auto` (default) | Use the Rust path when this package is importable and its ABI matches; otherwise fall back silently. |
| `force` | Require the Rust path; raise if unavailable or if a symbol is unimplemented. |
| `off` | Never import this package. |

Wheels are `abi3-py310`, so one wheel per platform covers CPython 3.10 through
3.14. Free-threaded builds (`cp314t`) cannot load abi3 wheels; `idaes.accel`
detects that and falls back.

Licensed BSD-3-Clause. See `LICENSE.md` and `FORK.md` at the repository root.
