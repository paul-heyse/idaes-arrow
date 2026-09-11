---
description: The acceleration dispatch layer and its parity contract
paths:
  - "idaes/accel/**"
  - "idaes/core/surrogate/pysmo/**"
---

# The acceleration layer

## The decorator contract

`@accelerate("key")` wraps a **module-level function**, never a method. A bound
method's `self` would cross the FFI boundary as the first positional argument.
To accelerate something that is currently a method: extract the body to a
module-level function, decorate that, and have the method delegate. The
`accelerate-not-on-method` ast-grep rule enforces this.

Accelerate at the outermost stable boundary. The dispatcher costs ~80 ns per
call; wrapping a function that is itself called in a loop pays that N times.

## Parity is the whole point

Register a `ParityCase` beside the implementation. Bit-exact (`rtol=atol=0`) is
the default and a loosened tolerance requires a `note` — `parity.register()`
refuses one without it.

Cover the argument **types** callers actually pass, not just values. The one bug
that shipped here was `prime_number_generator(2.9)`: the Python function is
untyped and its own test suite calls it with a float.

Parity tests never read `IDAES_ACCEL`; they call both implementations directly.
The env var is a CI-job concern. That is what lets the same file run under `off`
and `force` with no duplicated code.

## Markers

`idaes/conftest.py` hard-fails any test without exactly one of
`unit`/`component`/`integration`/`performance`. The parity suite is split into
three functions by tier for this reason — a function-level marker plus a
param-level marker counts as two.

## Never import the extension directly

Only `idaes/accel/` may `import idaes_accel`. Everything else goes through the
dispatcher, which owns the mode, the ABI check and the fallback. Enforced by the
`no-direct-accel-import` rule.
