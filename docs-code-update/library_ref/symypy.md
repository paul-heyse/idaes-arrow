# 0) SymPy scope, versioning, and mental model — agent-ready deep dive

## 0.0 Version anchor and runtime contract

As checked against current official/public sources: SymPy documentation is at **1.14.0**, PyPI lists **SymPy 1.14.0** files uploaded **Apr. 27, 2025**, and PyPI metadata requires **Python >=3.9**. PyPI classifiers list Python 3.9–3.13, CPython, and PyPy. ([SymPy Documentation][1])

```bash
python -m pip install "sympy==1.14.0"
python - <<'PY'
import sympy as sp
print(sp.__version__)
PY
```

Install surfaces: `pip install sympy`, `conda install sympy`, `conda install --channel conda-forge sympy`, distro packages, nightly wheels, or editable Git installs. For production agents: prefer pinned PyPI/Conda lockfiles; use nightly/Git only for regression triage, upstream bug verification, or capability probing. ([SymPy Documentation][2])

Hard dependency: **mpmath**. SymPy uses mpmath for arbitrary-precision floating-point evaluation paths such as `evalf`; SymPy fails to import if mpmath is missing. Recommended optional dependency: **gmpy2**, automatically used when installed by integer/polynomial-heavy internals and broadly beneficial for performance-sensitive algebra. ([SymPy Documentation][3])

---

## 0.1 Scope contract: what SymPy is

**SymPy = Python-native symbolic mathematics / computer algebra system.** Its primary data model is exact symbolic expression construction and transformation, not approximate numeric array execution. Symbolic computation represents mathematical objects exactly, leaves unevaluated variables in symbolic form, and enables symbolic simplification such as `sqrt(8) -> 2*sqrt(2)` rather than immediate decimal approximation. ([SymPy Documentation][4])

Agent mental contract:

```text
SymPy object graph
  = immutable symbolic expression tree
  = exact math object, not merely string, not merely numeric value
  = transformable by algebra/calculus/logic/codegen algorithms
```

Primary value cases:

| Use case                     | SymPy value                                         | Typical handoff                        |
| ---------------------------- | --------------------------------------------------- | -------------------------------------- |
| exact algebra                | preserve structure, identities, rational arithmetic | simplified expression / proof artifact |
| symbolic derivation          | derivatives, integrals, series, equations           | formula / generated kernel             |
| domain-aware manipulation    | assumptions, sets, exact domains                    | solver output / predicates             |
| code generation              | emit C/Fortran/Python/NumPy-compatible code         | compiled or vectorized numerical path  |
| educational/explanatory math | readable symbolic steps and exact forms             | LaTeX / pretty print                   |
| scientific automation        | derive once, evaluate many times                    | `lambdify`, `ufuncify`, codegen        |

---

## 0.2 SymPy vs NumPy/SciPy/mpmath/JAX: stack boundary

SymPy is **symbolic-first**. NumPy/SciPy/JAX/CuPy are **numeric-first**. SymPy documentation explicitly warns that SymPy is not designed to work directly with NumPy arrays, NumPy does not directly understand SymPy expressions, and the recommended mixed workflow is: build symbolic expression in SymPy, then convert with `lambdify()` or code generation for numeric execution. ([SymPy Documentation][5])

```python
import sympy as sp

x = sp.symbols("x")
expr = sp.diff(sp.sin(x) * sp.exp(x**2), x)   # symbolic derivation

# Numeric bridge: produce a callable for array/machine-float evaluation.
f_np = sp.lambdify(x, expr, modules="numpy")
```

Decision matrix:

| Need                                                           | Use                                                            |
| -------------------------------------------------------------- | -------------------------------------------------------------- |
| exact simplification, identities, formulas, symbolic variables | SymPy                                                          |
| one-off high-precision scalar numeric value                    | SymPy `evalf()` / mpmath                                       |
| repeated scalar numeric evaluation                             | `lambdify(..., "math")` or `lambdify(..., "mpmath")`           |
| vectorized array evaluation                                    | `lambdify(..., "numpy")`                                       |
| large numerical linear algebra / optimization / integration    | SciPy / NumPy; SymPy only for derivation                       |
| autodiff / accelerator / differentiable array programs         | JAX; SymPy for formula generation only if needed               |
| GPU array numeric evaluation                                   | `lambdify(..., "cupy")` when supported by expression functions |
| production compiled numerical kernel                           | SymPy codegen / autowrap / `ufuncify`                          |

Numeric computation docs state that symbolic systems often have poor performance for numeric data, and SymPy provides hooks to ship expressions to numeric systems such as `math`, NumPy, and Fortran/C code generation. `subs(...).evalf()` is described as slow and appropriate only when performance is not an issue. ([SymPy Documentation][6])

---

## 0.3 Core execution model

Canonical pipeline:

```text
declare symbols
  → build expressions
  → apply assumptions/domains
  → transform/rewrite/simplify
  → solve/differentiate/integrate/series/linear algebra
  → evaluate numerically OR print OR generate code
```

Concrete skeleton:

```python
import sympy as sp

# 1) Symbol declaration: semantic variables, not strings.
x, y = sp.symbols("x y", real=True)
a = sp.symbols("a", positive=True)

# 2) Exact expression construction.
expr = sp.sin(x) * sp.exp(x**2) + sp.Rational(2, 7)

# 3) Symbolic transformation.
dexpr = sp.diff(expr, x)
normalized = sp.factor(sp.together(dexpr))

# 4) Substitution / exact specialization.
special = normalized.subs(x, sp.pi)

# 5) Numeric evaluation, if needed.
approx = special.evalf(50)

# 6) Numeric deployment callable.
f = sp.lambdify(x, normalized, modules="numpy")

# 7) External representation.
latex_src = sp.latex(normalized)
c_src = sp.ccode(normalized)
```

Operational invariant: do not conflate these phases. Agents should not generate numeric code while symbolic ambiguity remains unresolved, should not use `float`/`math.pi` in symbolic derivations unless approximation is intentional, and should not use string manipulation as an expression transformation layer.

---

## 0.4 Exact-by-default philosophy

SymPy prioritizes exact objects: `Integer`, `Rational`, symbolic constants (`pi`, `E`, `I`, `oo`), unevaluated forms, assumptions-aware simplification, and exact algebraic structure. The docs explicitly prefer `sympy.pi` over `math.pi` because `math.pi` is a floating approximation, and prefer `Rational(2, 7)` or `S(2)/7` over Python `2/7` when exactness is needed. ([SymPy Documentation][5])

```python
import math
import sympy as sp

x = sp.symbols("x")

bad_1 = sp.sin(math.pi)       # approximate input -> tiny float residue
good_1 = sp.sin(sp.pi)        # exact -> 0

bad_2 = x + 2/7               # Python evaluates 2/7 first -> float
good_2 = x + sp.Rational(2, 7)
good_3 = x + sp.S(2)/7
```

Agent rule:

```text
Exact symbolic layer:
  use sp.Integer, sp.Rational, sp.S(...), sp.pi, sp.E, sp.I
Numeric deployment layer:
  use float, numpy.float64, scipy, jax, cupy, compiled code
```

Important pitfall: once a Python float enters an expression, many exact algorithms become weaker. Example class: `factor(x**2.0 - 1)` cannot behave like `factor(x**2 - 1)` because the exponent is approximate, not exact. ([SymPy Documentation][5])

---

## 0.5 Expression tree model

SymPy expressions are represented as trees. Example: `x**2 + x*y` is structurally `Add(Pow(Symbol('x'), Integer(2)), Mul(Symbol('x'), Symbol('y')))`, visible through `srepr(expr)`. ([SymPy Documentation][7])

```python
import sympy as sp

x, y = sp.symbols("x y")
expr = x**2 + x*y

expr.func      # Add
expr.args      # (x**2, x*y)  modulo canonical ordering
sp.srepr(expr) # structural representation
```

Core invariants for SymPy-compatible object manipulation:

```text
expr is immutable
expr.args contains SymPy Basic objects
expr.func(*expr.args) reconstructs expr
transformations return new expressions
```

SymPy custom-object docs state the `args` invariants explicitly: every arg should be a `Basic`, and `expr.func(*expr.args) == expr`; these invariants are assumed by expression-manipulating functions. ([SymPy Documentation][5])

Immutability contract: all `Basic` objects are immutable; operations return new expressions and leave the original unchanged. This enables hashability, dictionary keys, shared subexpressions, safe caching, and structural equality semantics. ([SymPy Documentation][8])

```python
expr = sp.cos(x)
new_expr = expr.subs(x, 0)

assert expr == sp.cos(x)   # unchanged
assert new_expr == 1
```

---

## 0.6 Equality semantics: structural vs mathematical

Agent-critical distinction:

```python
expr1 = x*(x - 1)
expr2 = x**2 - x

expr1 == expr2             # structural equality -> False
sp.expand(expr1) == expr2  # structural equality after normalization -> True
sp.Eq(expr1, expr2)        # symbolic equation object
expr1.equals(expr2)        # mathematical equivalence attempt
```

SymPy’s best-practices docs state that `==` is structural equality, not mathematical equality; symbolic equations should use `Eq`, and custom classes should not override `__eq__` because SymPy internals assume structural equality is cheap and boolean-valued. ([SymPy Documentation][5])

Deployment rule:

```text
Use == only for exact structural assertions.
Use simplify(lhs-rhs) == 0 only with domain awareness.
Use .equals() for heuristic mathematical equivalence checks.
Use Eq(lhs, rhs) to represent equations.
Use solveset/solve/reduce_inequalities to solve equations/relations.
```

---

## 0.7 Assumptions: semantic constraints and fuzzy logic

Assumptions are attached primarily at symbol construction:

```python
x = sp.Symbol("x")
y = sp.Symbol("y", positive=True)
n = sp.Symbol("n", integer=True, nonnegative=True)
```

They control legal simplifications. `sqrt(x**2)` does not simplify for unconstrained `x` because `x` is not known to be positive or even real; `sqrt(y**2)` simplifies to `y` when `y` is created with `positive=True`. SymPy docs recommend being as precise as possible about assumptions when creating symbols. ([SymPy Documentation][1])

```python
sp.sqrt(x**2)   # sqrt(x**2)
sp.sqrt(y**2)   # y
```

Assumption queries use three-valued fuzzy logic: `True`, `False`, or `None`; `None` means unknown, not contradiction or failure. Any agent-generated code using `.is_positive`, `.is_real`, `.is_zero`, etc. must handle all three outcomes. ([SymPy Documentation][1])

```python
def require_positive(expr):
    if expr.is_positive is True:
        return expr
    if expr.is_positive is False:
        raise ValueError("definitely non-positive")
    raise ValueError("positivity unknown; add assumptions or refine domain")
```

Do not write:

```python
if expr.is_positive:
    ...
else:
    ...
```

because `None` falls into `else` and is semantically distinct from `False`.

Assumption-system deployment note: current user-facing docs describe the core/“old” assumptions system as the one widely used in SymPy and state that the “new” assumptions system is not really used anywhere in SymPy yet and the old system will not be removed. ([SymPy Documentation][1])

---

## 0.8 Evaluation modes

### Symbolic construction

```python
expr = sp.sqrt(8)        # 2*sqrt(2)
expr = sp.Integral(sp.sin(x)/x, (x, 0, sp.oo))  # unevaluated integral object
```

Use symbolic construction when preserving exact structure, derivation trace, or delayed evaluation matters.

### Forced symbolic evaluation

```python
expr.doit()
sp.simplify(expr)
sp.factor(expr)
sp.expand(expr)
sp.cancel(expr)
```

Use targeted transforms before broad `simplify()`. Broad simplification is heuristic and can be expensive; SymPy’s best-practices page explicitly flags avoiding blind `simplify()` as a best-practice topic. ([SymPy Documentation][5])

### Numeric evaluation inside SymPy

```python
expr.evalf()
sp.N(expr, 50)
expr.evalf(subs={x: sp.Rational(1, 3)})
```

`evalf()` / `N()` convert exact expressions to floating-point approximations; default numerical evaluation uses 15 decimal digits and accepts a requested precision. If symbols remain, `evalf` can return a partially evaluated expression. ([SymPy Documentation][9])

### Numeric callable generation

```python
f_math = sp.lambdify(x, expr, modules="math")
f_np = sp.lambdify(x, expr, modules="numpy")
f_mp = sp.lambdify(x, expr, modules="mpmath")
```

`lambdify(args, expr, modules=...)` transforms SymPy expressions into Python functions for fast numerical evaluation; its documented signature includes `modules`, `printer`, `use_imps`, `dummify`, `cse`, and `docstring_limit`. ([SymPy Documentation][10])

### Code generation

```python
sp.ccode(expr)
sp.fcode(expr)
# higher-level: codegen, autowrap, ufuncify
```

SymPy codegen has a layered model: expression → code printers → code generators → autowrap. Code printers translate SymPy objects to target-language code, while `autowrap` can produce importable/evaluable functions in the same Python process. ([SymPy Documentation][11])

---

## 0.9 String-input policy

Avoid string inputs as a default programming-agent tactic. SymPy docs warn that automatic parsing of strings in general SymPy functions is mostly accidental, can hide typos, can lose assumptions, and may silently create different symbols than intended. ([SymPy Documentation][5])

Bad:

```python
sp.diff("z**2", sp.Symbol("z", positive=True))  # string z lacks assumptions
```

Good:

```python
z = sp.Symbol("z", positive=True)
sp.diff(z**2, z)
```

If parsing user-provided strings is unavoidable, use controlled parsing with explicit symbol dictionaries and threat-model it. The tutorial states `sympify()` uses `eval` and should not be used on unsanitized input. ([SymPy Documentation][12])

---

## 0.10 Deployment archetypes

### A) Interactive derivation / notebook

Use:

```python
import sympy as sp
sp.init_printing()
```

Acceptable idioms: `from sympy import *`, `sympy.abc`, quick `simplify`, visual exploration. Programmatic modules should prefer explicit imports; SymPy glossary notes wildcard imports are convenient interactively but frowned upon for programmatic usage. ([SymPy Documentation][8])

### B) Library function returning symbolic expression

Use parameterized symbols; never hardcode symbol names inside reusable functions.

```python
def theta_operator(expr, z):
    return z * sp.diff(expr, z)
```

SymPy docs explicitly recommend passing symbols as parameters instead of hardcoding names, because hardcoded symbols break when callers use different names or assumptions. ([SymPy Documentation][5])

### C) Batch symbolic derivation → persisted formula

Use exact construction, targeted transforms, explicit metadata.

```python
def derive_formula(x):
    expr = sp.sin(x) * sp.exp(x**2)
    dexpr = sp.diff(expr, x)
    return sp.factor(dexpr)

x = sp.Symbol("x", real=True)
formula = derive_formula(x)

payload = {
    "sympy_version": sp.__version__,
    "srepr": sp.srepr(formula),
    "latex": sp.latex(formula),
}
```

### D) Symbolic derivation → NumPy runtime

```python
import numpy as np
import sympy as sp

x = sp.Symbol("x", real=True)
expr = sp.diff(sp.sin(x) * sp.exp(x**2), x)

f = sp.lambdify(x, expr, modules="numpy")
grid = np.linspace(0, 10, 1000)
values = f(grid)
```

Use this when you need repeated machine-precision evaluation over arrays. SymPy docs describe the typical workflow as constructing symbolically in SymPy, converting with `lambdify()`, then evaluating on NumPy arrays. ([SymPy Documentation][5])

### E) Symbolic derivation → compiled kernel

Use when array-size, expression complexity, or latency justifies codegen/autowrap.

```python
from sympy.utilities.autowrap import ufuncify

x = sp.Symbol("x")
expr = sp.sin(x) / x
uf = ufuncify([x], expr)
```

SymPy codegen docs state that `ufuncify` consumes and returns NumPy arrays and can outperform NumPy-backed `lambdify` for complicated expressions. ([SymPy Documentation][11])

---

## 0.11 “When SymPy is right” vs “switch now”

Use SymPy when:

```text
Need exact formula.
Need algebraic simplification.
Need symbolic derivative/integral/series.
Need equation solving with parameters.
Need assumptions/domain-aware manipulation.
Need LaTeX/code output from math.
Need generate numerical kernels from symbolic definitions.
Need arbitrary precision scalar evaluation with exact provenance.
```

Switch to NumPy/SciPy/JAX/CuPy/mpmath when:

```text
Input is already numeric arrays.
Task is large dense/sparse numerical linear algebra.
Task is optimization, ODE/PDE simulation, statistics over data arrays.
Need GPU/TPU/autodiff-first execution.
Need millions of evaluations; symbolic transforms are already complete.
Need approximate high-precision scalar numerics only, not expression algebra.
```

Minimal handoff policy:

```python
# symbolic boundary
expr = symbolic_derivation(...)

# numeric boundary
f = sp.lambdify(args, expr, modules="numpy")  # or "jax", "cupy", "mpmath"
```

Do **not** pass SymPy objects into NumPy ufuncs directly or NumPy arrays into SymPy functions directly; official best-practices docs show both directions failing and recommend `lambdify()` as the bridge. ([SymPy Documentation][5])

---

## 0.12 Agent guardrails: high-priority invariants

1. **Construct symbols explicitly.**

```python
x, y = sp.symbols("x y", real=True)
```

2. **Preserve exactness until numeric boundary.**

```python
sp.Rational(1, 2)     # not 0.5
sp.pi                 # not math.pi
```

3. **Treat expressions as immutable trees.**

```python
expr2 = expr.subs(x, 1)   # assign returned expression
```

4. **Use targeted transforms.**

```python
sp.factor(expr)
sp.cancel(expr)
sp.together(expr)
sp.expand(expr)
sp.trigsimp(expr)
```

5. **Do not use strings as math IR.**

```python
# prefer expression objects over parse/edit/regex strings
expr = x**2 + 3*x - sp.Rational(1, 2)
```

6. **Separate symbolic and numeric code.**

```python
expr = sp.diff(...)
f = sp.lambdify(x, expr, "numpy")
```

7. **Handle fuzzy booleans explicitly.**

```python
if q is True: ...
elif q is False: ...
else: ...  # unknown
```

8. **Pin version in generated artifacts.**

```python
metadata = {"sympy_version": sp.__version__}
```

9. **Use `Eq` for equations, not `==`.**

```python
eq = sp.Eq(lhs, rhs)
```

10. **For deployment speed: install `gmpy2` when feasible, avoid repeated symbolic work in request loops, precompute formulas, then lambdify/codegen.** gmpy2 is not required but is recommended by SymPy docs for better performance in many integer/polynomial-dependent algorithms. ([SymPy Documentation][3])

---

## 0.13 Minimal production skeleton

```python
from __future__ import annotations

import sympy as sp
from dataclasses import dataclass
from typing import Callable, Any


@dataclass(frozen=True)
class SymbolicKernel:
    expr: sp.Expr
    args: tuple[sp.Symbol, ...]
    sympy_version: str

    def numpy_callable(self) -> Callable[..., Any]:
        return sp.lambdify(self.args, self.expr, modules="numpy")

    def exact_at(self, substitutions: dict[sp.Symbol, sp.Expr]) -> sp.Expr:
        return self.expr.subs(substitutions)

    def numeric_at(self, substitutions: dict[sp.Symbol, Any], digits: int = 50) -> sp.Expr:
        return self.expr.evalf(digits, subs=substitutions)

    def latex(self) -> str:
        return sp.latex(self.expr)

    def c_code(self, assign_to: str | None = None) -> str:
        return sp.ccode(self.expr, assign_to=assign_to)


def build_kernel() -> SymbolicKernel:
    x = sp.Symbol("x", real=True)

    # exact symbolic derivation
    expr = sp.diff(sp.sin(x) * sp.exp(x**2) + sp.Rational(2, 7), x)

    # targeted normalization
    expr = sp.factor(expr)

    return SymbolicKernel(
        expr=expr,
        args=(x,),
        sympy_version=sp.__version__,
    )
```

This skeleton enforces: explicit symbols, exact arithmetic, targeted symbolic derivation, delayed numeric conversion, version metadata, and multiple output channels.

[1]: https://docs.sympy.org/latest/guides/assumptions.html "Assumptions - SymPy 1.14.0 documentation"
[2]: https://docs.sympy.org/latest/install.html "Installation - SymPy 1.14.0 documentation"
[3]: https://docs.sympy.org/latest/contributing/dependencies.html "Dependencies - SymPy 1.14.0 documentation"
[4]: https://docs.sympy.org/latest/tutorials/intro-tutorial/intro.html "Introduction - SymPy 1.14.0 documentation"
[5]: https://docs.sympy.org/latest/explanation/best-practices.html "Best Practices - SymPy 1.14.0 documentation"
[6]: https://docs.sympy.org/latest/modules/numeric-computation.html "Numeric Computation - SymPy 1.14.0 documentation"
[7]: https://docs.sympy.org/latest/tutorials/intro-tutorial/manipulation.html "Advanced Expression Manipulation - SymPy 1.14.0 documentation"
[8]: https://docs.sympy.org/latest/explanation/glossary.html "Glossary - SymPy 1.14.0 documentation"
[9]: https://docs.sympy.org/latest/modules/evalf.html "Numerical Evaluation - SymPy 1.14.0 documentation"
[10]: https://docs.sympy.org/latest/modules/utilities/lambdify.html "Lambdify - SymPy 1.14.0 documentation"
[11]: https://docs.sympy.org/latest/modules/codegen.html "Code Generation - SymPy 1.14.0 documentation"
[12]: https://docs.sympy.org/latest/tutorials/intro-tutorial/basic_operations.html "Basic Operations - SymPy 1.14.0 documentation"

# 2) Core object model — symbols, expressions, atoms, expression trees

## 2.0 Operating premise

SymPy core objects are **symbolic expression nodes**. The central invariant: build math as immutable object graphs, not strings; transform by SymPy methods/functions; evaluate only at explicit boundaries. `Basic` is the superclass of SymPy expressions and provides core machinery such as `args`, `func`, equality, immutability, and substitution; `Expr` is the superclass for algebraic expressions usable in `Add`, `Mul`, and `Pow`. Boolean objects, matrices, and other symbolic structures live adjacent to but not always under scalar `Expr`. ([SymPy Documentation][1])

---

## 2.1 Import policy

### Programmatic/library code

```python
import sympy as sp
```

Preferred: namespace-qualified API, explicit symbol ownership, no namespace pollution.

```python
x = sp.Symbol("x", real=True)
expr = sp.sin(x) + sp.Rational(1, 3)
```

### Interactive notebooks / REPL

```python
from sympy import *
```

Acceptable interactively; avoid in production modules. SymPy docs explicitly frame wildcard imports as convenient for interactive use but generally discouraged for programmatic usage. ([SymPy Documentation][1])

---

## 2.2 Object hierarchy map

```text
Basic
├── Expr
│   ├── AtomicExpr
│   │   ├── Symbol
│   │   ├── Dummy
│   │   ├── Number
│   │   │   ├── Integer
│   │   │   ├── Rational
│   │   │   └── Float
│   │   └── NumberSymbol  # pi, E, etc. are not Number
│   ├── Add
│   ├── Mul
│   ├── Pow
│   └── Function          # applied symbolic function base
├── Boolean
│   ├── And / Or / Not / Equivalent / ...
│   └── Relational / Eq / Ne / Lt / Le / Gt / Ge
├── Matrix-like symbolic families
│   ├── MatrixExpr
│   │   ├── MatrixSymbol
│   │   ├── MatAdd
│   │   ├── MatMul
│   │   └── MatPow
│   └── explicit matrices: Matrix / MutableDenseMatrix / ImmutableDenseMatrix
└── other symbolic object families
```

Key distinction: `Number` means explicit numeric objects such as `Integer`, `Rational`, and `Float`; symbolic numeric constants like `pi` are not `Number` instances, although they may be numerically evaluable. Explicit matrices and matrix expressions have separate hierarchy/behavior; `MatrixExpr` represents abstract symbolic matrices, while explicit dense matrices may be mutable or immutable. ([SymPy Documentation][1])

---

## 2.3 Symbol constructors

## 2.3.1 `Symbol(name, **assumptions)`

```python
x = sp.Symbol("x")
x_pos = sp.Symbol("x", positive=True)
n = sp.Symbol("n", integer=True, nonnegative=True)
theta = sp.Symbol("theta", real=True)
```

`Symbol` always creates one symbol. Use it for programmatic generation, unusual names, one-off symbol objects, or explicit assumption control. Assumptions passed to `Symbol` become part of the symbol identity; `Symbol("z")` and `Symbol("z", positive=True)` compare unequal. ([SymPy Documentation][2])

```python
z1 = sp.Symbol("z")
z2 = sp.Symbol("z", positive=True)

assert z1 != z2
assert z1.assumptions0 == {"commutative": True}
assert z2.is_positive is True
assert z2.is_real is True
```

### Agent rule

```text
Never identify symbols by name alone.
Identity = class + name + assumptions.
Pass symbols explicitly into reusable functions.
```

Bad:

```python
def theta_operator(expr):
    z = sp.Symbol("z")       # assumption mismatch risk
    return z * sp.diff(expr, z)
```

Good:

```python
def theta_operator(expr: sp.Expr, z: sp.Symbol) -> sp.Expr:
    return z * sp.diff(expr, z)
```

SymPy best practices explicitly warn against hardcoding symbol names in reusable functions because same-named symbols with different assumptions are distinct. ([SymPy Documentation][2])

---

## 2.3.2 `symbols(names, **assumptions)`

```python
x, y, z = sp.symbols("x y z")
i, j, k = sp.symbols("i j k", integer=True)
x0, x1, x2 = sp.symbols("x:3")
a0, a1, a2, b0, b1, b2 = sp.symbols("a:3 b:3")
```

`sympy.symbols()` is the high-throughput constructor for multiple symbols, numbered symbol ranges, and assumption-batched declarations. It also supports function-class creation via `cls=Function`. ([SymPy Documentation][2])

```python
f, g, h = sp.symbols("f g h", cls=sp.Function)
```

### Return-shape rules

```python
sp.symbols("x")          # Symbol('x')
sp.symbols("x y")        # (x, y)
sp.symbols("x:3")        # (x0, x1, x2)
```

Deployment rule: in APIs, avoid ambiguous return shape by normalizing:

```python
xs = sp.symbols("x:3")
xs = tuple(xs) if isinstance(xs, tuple) else (xs,)
```

---

## 2.3.3 `Dummy(name=None, **assumptions)`

```python
u = sp.Dummy("u")
v = sp.Dummy("u")

assert u != v
```

`Dummy` creates a symbol guaranteed unique relative to other dummy symbols, even when names match. Use it for generated temporary variables, alpha-renaming, bound-variable hygiene, rewrite algorithms, solver internals, and clash-free transformations. ([SymPy Documentation][3])

```python
def hygienic_substitution(expr: sp.Expr, old: sp.Symbol, replacement: sp.Expr) -> sp.Expr:
    tmp = sp.Dummy(old.name)
    return expr.xreplace({old: tmp}).xreplace({tmp: replacement})
```

Bound-variable comparison helper:

```python
u = sp.Dummy("u")
x = sp.Symbol("x")

assert (u**2 + 1) != (x**2 + 1)
assert (u**2 + 1).dummy_eq(x**2 + 1)
```

`dummy_eq()` compares expressions while handling dummy-symbol equivalence. ([SymPy Documentation][3])

---

## 2.3.4 `Wild(name, exclude=(), properties=(), **assumptions)`

```python
a = sp.Wild("a")
b = sp.Wild("b", exclude=[x])
c = sp.Wild("c", properties=[lambda e: e.is_Integer])
```

`Wild` is pattern-matching IR, not a normal algebraic variable. It matches arbitrary subexpressions subject to exclusion lists and predicate filters. Use in `.match()`, `.replace()`, and custom rewrite rules. ([SymPy Documentation][3])

```python
x, y = sp.symbols("x y")
a = sp.Wild("a")
b = sp.Wild("b", exclude=[x])

assert (3*x**2).match(a*x) == {a: 3*x}
assert (3*x**2).match(b*x) is None
```

Pattern design rule:

```text
Wild without exclude/properties is broad and may overmatch.
Constrain aggressively: exclude structural anchors; use properties for numeric/domain filters.
```

---

## 2.3.5 `Function(name, nargs=None, **assumptions)`

```python
x = sp.Symbol("x")
f = sp.Function("f")          # undefined function class
fx = f(x)                     # applied undefined function
g = sp.Function("g", nargs=1)
h = sp.Function("h", real=True)
```

`Function("f")` creates an undefined function class; applying it creates an applied symbolic function expression. Function assumptions describe the function value, not relationships between arguments and value; for semantic relationships, subclass `Function` and implement handlers. ([SymPy Documentation][3])

```python
f = sp.Function("f")
expr = f(x)

assert expr.args == (x,)
assert expr.diff(x) == sp.Derivative(f(x), x)
```

Function arity:

```python
f_any = sp.Function("f")
f_1 = sp.Function("f1", nargs=1)
f_12 = sp.Function("f12", nargs=(1, 2))

assert f_1.nargs == {1}
assert f_12.nargs == {1, 2}
```

Use `symbols(..., cls=Function)` for batch function-class creation:

```python
f, g = sp.symbols("f g", cls=sp.Function)
```

---

## 2.4 Assumptions at construction time

Assumptions constrain the admissible values of a symbol/expression and enable domain-correct simplification. If no assumptions are supplied, symbols are treated as general complex values; SymPy will not apply simplifications unless valid for the full allowed domain. ([SymPy Documentation][1])

```python
x = sp.Symbol("x")
xp = sp.Symbol("xp", positive=True)
n = sp.Symbol("n", integer=True)
r = sp.Symbol("r", real=True)
```

### Common assumption predicates

```text
real=True
positive=True
negative=True
nonnegative=True
nonpositive=True
integer=True
rational=True
irrational=True
finite=True
infinite=True
zero=True
nonzero=True
complex=True
commutative=True|False
```

### Query syntax

```python
x.is_real
x.is_positive
x.is_integer
(x + 1).is_real
```

Return contract:

```text
True  = provably true
False = provably false
None  = unknown under current assumptions
```

Assumptions use three-valued logic; agents must not collapse `None` into `False`. ([SymPy Documentation][1])

```python
def branch_on_positive(expr: sp.Expr):
    q = expr.is_positive
    if q is True:
        return "positive"
    if q is False:
        return "not positive"
    return "unknown"
```

### Value case

```python
a = sp.Symbol("a")
ap = sp.Symbol("a", positive=True)
x = sp.Symbol("x", positive=True)

sp.integrate(sp.exp(-a*x), (x, 0, sp.oo))   # Piecewise / unevaluated fallback
sp.integrate(sp.exp(-ap*x), (x, 0, sp.oo))  # 1/ap
```

The docs show positive assumptions can eliminate conditional/Piecewise output in convergence-sensitive operations. ([SymPy Documentation][2])

---

## 2.5 Expression construction with Python operators

### Operator → core node mapping

```text
x + y      → Add(x, y)
x - y      → Add(x, Mul(-1, y))
x * y      → Mul(x, y)
x / y      → Mul(x, Pow(y, -1))
x ** n     → Pow(x, n)
-f         → Mul(-1, f)
f(x)       → applied Function node
x < y      → StrictLessThan(x, y)
Eq(x, y)   → Equality(x, y)
```

The expression-tree tutorial shows `x**2 + x*y` represented as `Add(Pow(Symbol('x'), Integer(2)), Mul(Symbol('x'), Symbol('y')))`, and explicitly notes that subtraction is represented internally as addition with multiplication by `-1`. ([SymPy Documentation][4])

```python
x, y = sp.symbols("x y")

expr = x**2 + x*y
assert sp.srepr(expr) == "Add(Pow(Symbol('x'), Integer(2)), Mul(Symbol('x'), Symbol('y')))"

sp.srepr(x - y)
# "Add(Symbol('x'), Mul(Integer(-1), Symbol('y')))"
```

### Constructor equivalents

```python
expr1 = x**2 + x*y
expr2 = sp.Add(sp.Pow(x, 2), sp.Mul(x, y))

assert expr1 == expr2
```

### Sympification of Python literals

```python
expr = x + 2
type(expr.args[0])     # Integer or Symbol depending canonical order
```

When Python literals are combined with SymPy objects, they are converted into SymPy objects such as `Integer`; the expression-tree tutorial identifies this conversion as sympification. ([SymPy Documentation][4])

Production rule:

```python
expr = x + sp.Rational(2, 7)  # exact
expr = x + sp.S(2)/7          # exact
```

Avoid:

```python
expr = x + 2/7                # Python float formed before SymPy sees it
```

---

## 2.6 Strings are not expression IR

Avoid string inputs and string manipulation. SymPy best practices say expressions should be built with Python operators and SymPy functions; string/regex manipulation loses symbolic structure and can hide typos/assumption mismatches. ([SymPy Documentation][2])

Bad:

```python
expr = sp.expand("(x**2 + x)/x")
```

Good:

```python
x = sp.Symbol("x")
expr = sp.expand((x**2 + x)/x)
```

If input truly arrives as text:

```python
from sympy.parsing.sympy_parser import parse_expr

x = sp.Symbol("x", positive=True)
expr = parse_expr("x**2 + 1", local_dict={"x": x})
```

Security rule: `sympify()` uses `eval` for strings and should not be used on unsanitized input. ([SymPy Documentation][3])

---

## 2.7 `Basic`, `Expr`, `Function`, `Number`, matrix families

## 2.7.1 `Basic`

`Basic` = structural substrate.

Core properties:

```python
expr.args
expr.func
expr.subs(...)
expr.xreplace(...)
expr.has(...)
expr.atoms(...)
expr.free_symbols
expr.doit()
```

`Basic` provides `args`, `func`, equality, immutability, and substitution; non-`Basic` objects generally cannot participate in SymPy functions unless they can be converted with `sympify()`. ([SymPy Documentation][1])

---

## 2.7.2 `Expr`

`Expr` = algebraic scalar expression substrate.

```python
isinstance(x + 1, sp.Expr)      # True
isinstance(sp.Eq(x, 1), sp.Expr) # usually false; Eq is relational/Boolean-like
```

Use `Expr` annotations when your function accepts scalar algebraic expressions:

```python
def normalize_scalar(expr: sp.Expr) -> sp.Expr:
    expr = sp.sympify(expr)
    if not isinstance(expr, sp.Expr):
        raise TypeError("expected scalar algebraic SymPy Expr")
    return sp.factor(sp.together(expr))
```

`Expr` is the superclass for algebraic expressions that make sense inside `Add`, `Mul`, and `Pow`; Boolean objects are `Basic` but not `Expr`. ([SymPy Documentation][1])

---

## 2.7.3 `Number`

```python
sp.Integer(2)
sp.Rational(2, 7)
sp.Float("1.25")
```

`Number` is the base class for explicit numbers. Use `isinstance(obj, sp.Number)` for explicit numeric atoms; use `expr.is_number` for “can be numerically evaluated” semantics. Symbolic constants like `pi` are not `Number` instances. ([SymPy Documentation][1])

```python
assert isinstance(sp.Integer(2), sp.Number)
assert not isinstance(sp.pi, sp.Number)
assert sp.pi.is_number is True
```

---

## 2.7.4 `Function`

`Function` has two roles:

```text
Function("f")       → undefined function class
Function subclass   → custom symbolic function base
sin(x), exp(x)      → applied symbolic functions
```

Symbolic `Function` objects typically remain unevaluated when passed symbolic arguments; not every SymPy function is a `Function` class, since simplification functions such as `simplify()` are ordinary Python functions returning values. ([SymPy Documentation][1])

---

## 2.7.5 Matrix object caveat

```python
M = sp.Matrix([[1, 2], [3, 4]])          # mutable explicit matrix
IM = sp.ImmutableMatrix([[1, 2], [3, 4]])
A = sp.MatrixSymbol("A", 2, 2)           # symbolic matrix expression
```

Use explicit matrices for concrete element storage and linear algebra operations; use `MatrixSymbol`/`MatrixExpr` for abstract symbolic matrix algebra. Matrix expressions represent abstract matrices and support symbolic matrix operations such as transpose, inverse, matrix multiplication, and expression derivatives. ([SymPy Documentation][5])

---

## 2.8 Structural equality vs mathematical equality

## 2.8.1 `==`: structural equality

```python
expr1 = x*(x - 1)
expr2 = x**2 - x

expr1 == expr2          # False
sp.expand(expr1) == expr2  # True
```

`==` checks structural equality: same type and same `args`; it always returns Python `True` or `False` and does not perform mathematical equivalence proving. SymPy internals rely on this behavior, and custom SymPy objects should not override `__eq__`. ([SymPy Documentation][2])

### Agent rule

```text
Use == for cache keys, exact structural tests, post-normalization checks.
Do not use == to ask “are these formulas equivalent?” unless both sides are canonicalized.
```

---

## 2.8.2 `Eq(lhs, rhs)`: symbolic equation

```python
eq = sp.Eq(x**2, 1)
```

Equations are represented with `Eq`, not `==`; relationals such as `Eq`, `Ne`, `<`, `<=`, `>`, `>=` are symbolic predicates, and trying to coerce symbolic inequalities to Python bool can raise `TypeError`. ([SymPy Documentation][1])

```python
if x > 0:       # wrong for symbolic x
    ...
```

Use:

```python
piece = sp.Piecewise((1, x > 0), (0, True))
```

---

## 2.8.3 `.equals(other)`: mathematical equivalence attempt

```python
expr1.equals(expr2)
```

`.equals()` attempts mathematical equality checking and may return `True`, `False`, or inconclusive depending on expression class and problem difficulty. Use for diagnostics, optional verification, and tests where inconclusive can be handled.

Robust test pattern:

```python
def assert_symbolically_equal(a: sp.Expr, b: sp.Expr) -> None:
    delta = sp.simplify(a - b)
    if delta == 0:
        return
    q = a.equals(b)
    if q is True:
        return
    raise AssertionError(f"not proved equal: {a!s} != {b!s}; delta={delta!s}")
```

---

## 2.9 Expression tree anatomy

## 2.9.1 `.func`

```python
expr = 3*x*y**2

expr.func              # <class 'sympy.core.mul.Mul'>
```

`.func` is the expression’s top-level constructor/function. Prefer `expr.func` over `type(expr)` when rebuilding expressions because `func` may differ from the Python type in special cases. ([SymPy Documentation][1])

---

## 2.9.2 `.args`

```python
expr.args             # (3, x, y**2)  canonical order, not input order
```

`.args` is the tuple of direct subexpressions. Atomic leaves have `args == ()`. The key invariant: every well-formed expression either has empty `args` or satisfies `expr == expr.func(*expr.args)`. ([SymPy Documentation][6])

```python
def rebuild(expr: sp.Basic) -> sp.Basic:
    return expr.func(*expr.args)

assert rebuild(expr) == expr
```

`Add` and `Mul` arguments are canonicalized/sorted for structural consistency; the order is designed to be unique/efficient and has no semantic meaning. ([SymPy Documentation][6])

---

## 2.9.3 `.atoms(*types)`

```python
expr = 1 + x + 2*sp.sin(y + sp.I*sp.pi)

expr.atoms()
expr.atoms(sp.Symbol)
expr.atoms(sp.Number)
expr.atoms(sp.Number, sp.NumberSymbol)
expr.atoms(sp.Function)
```

`.atoms()` returns atomic leaves by default: symbols, numbers, and number symbols such as `I` and `pi`. With type arguments, it recursively selects subexpressions of those types; the docs show examples for `Symbol`, `Number`, `NumberSymbol`, `Function`, and `AppliedUndef`. ([SymPy Documentation][3])

Agent distinction:

```text
expr.atoms(Symbol)       = syntactic symbol atoms
expr.free_symbols        = mathematically free symbols
expr.atoms(Function)     = applied function nodes too, not only leaves
```

---

## 2.9.4 `.free_symbols`

```python
expr = x + 1
expr.free_symbols        # {x}

integral = sp.Integral(x, (x, 0, 1))
integral.free_symbols    # usually excludes bound integration x
```

`.free_symbols` returns the symbols on which an expression mathematically depends. Bound symbols in integrals, derivatives, sums, lambdas, and substitutions require class-specific handling. The docs note not all free symbols are instances of `Symbol`; indexed objects can contribute non-`Symbol` free-symbol entries. ([SymPy Documentation][3])

Use cases:

```python
def validate_univariate(expr: sp.Expr, x: sp.Symbol) -> None:
    extra = expr.free_symbols - {x}
    if extra:
        raise ValueError(f"unexpected free symbols: {extra}")
```

---

## 2.9.5 Tree traversal

```python
from sympy import preorder_traversal, postorder_traversal

for node in preorder_traversal(expr):
    ...
```

Traversal is fundamentally `.args` recursion. SymPy provides `preorder_traversal` and `postorder_traversal` because walking expression trees is common. ([SymPy Documentation][6])

Safe recursive transformer skeleton:

```python
def map_tree(expr: sp.Basic, fn):
    new_args = tuple(map_tree(arg, fn) for arg in expr.args)
    rebuilt = expr.func(*new_args) if new_args else expr
    return fn(rebuilt)
```

Better: use built-ins when possible:

```python
expr.xreplace({old: new})       # exact node replacement
expr.subs(old, new)             # mathematical substitution semantics
expr.replace(query, value)      # pattern/structural replacement
```

---

## 2.10 Immutability and hashability

All `Basic` objects are immutable; operations return new expressions and leave originals unchanged. Immutability makes structurally equal objects interchangeable, enables hashability, and permits SymPy expressions as dictionary keys. ([SymPy Documentation][1])

```python
expr = sp.sin(x) + 1
expr2 = expr.subs(x, 0)

assert expr == sp.sin(x) + 1
assert expr2 == 1
```

Cache pattern:

```python
_cache: dict[sp.Basic, sp.Basic] = {}

def normalized(expr: sp.Basic) -> sp.Basic:
    expr = sp.sympify(expr)
    if expr not in _cache:
        _cache[expr] = sp.factor(sp.together(expr))
    return _cache[expr]
```

Metadata pattern: external side-table, not object mutation.

```python
metadata: dict[sp.Basic, dict[str, object]] = {}
metadata[expr] = {"origin": "generated", "stage": "pre-cse"}
```

SymPy docs recommend external dictionaries for extra metadata because SymPy objects are hashable and immutable. ([SymPy Documentation][2])

---

## 2.11 Evaluation control

## 2.11.1 Automatic simplification

```python
x + x          # 2*x
sp.Add(x, x)   # 2*x
```

Automatic simplification occurs inside constructors to canonicalize expressions; the glossary notes `x + x` is simplified to `2*x` in `Add`, and excessive automatic simplification is discouraged in custom classes because it makes unevaluated forms hard to represent and can be expensive. ([SymPy Documentation][1])

---

## 2.11.2 Constructor-level `evaluate=False`

```python
expr = sp.Add(x, x, evaluate=False)
assert str(expr) == "x + x"
```

Use `evaluate=False` with explicit constructors when preserving syntactic form matters: pedagogy, source-faithful rendering, delayed normalization, transformation debugging, parser output, or tests. The expression-manipulation tutorial identifies `evaluate=False` as one of the two main ways to prevent evaluation. ([SymPy Documentation][6])

Common constructors supporting evaluation control:

```python
sp.Add(a, b, evaluate=False)
sp.Mul(a, b, evaluate=False)
sp.Pow(a, b, evaluate=False)
sp.Derivative(expr, x, evaluate=False)
sp.diff(expr, x, evaluate=False)
```

Caveat: `evaluate=False` usually preserves only construction-time form; later combination can trigger evaluation.

```python
expr = sp.Add(x, x, evaluate=False)  # x + x
expr + x                             # 3*x
```

The docs explicitly warn that `evaluate=False` does not prevent future evaluation in later usages. ([SymPy Documentation][6])

---

## 2.11.3 `UnevaluatedExpr`

```python
u = sp.UnevaluatedExpr(x)
expr = x + u
```

`UnevaluatedExpr` prevents the wrapped expression from interacting with surrounding expressions. Release with `.doit()`. It cannot prevent evaluation that already happened before wrapping; combine with `evaluate=False` if both internal and external evaluation must be suppressed. ([SymPy Documentation][6])

```python
u1 = sp.UnevaluatedExpr(x + x)
# inside argument already evaluated -> 2*x

u2 = sp.UnevaluatedExpr(sp.Add(x, x, evaluate=False))
# preserves internal x + x and external isolation
```

Release:

```python
(u2 + y).doit()
```

---

## 2.11.4 Unevaluated symbolic classes

Common unevaluated classes:

```python
sp.Derivative(f(x), x)
sp.Integral(sp.sin(x)/x, (x, 0, sp.oo))
sp.Sum(1/n**2, (n, 1, sp.oo))
sp.Limit(sp.sin(x)/x, x, 0)
sp.RootOf(...)
sp.Eq(lhs, rhs, evaluate=False)
```

Evaluation boundary:

```python
obj.doit()
obj.doit(deep=False)
```

`doit()` evaluates objects that are not evaluated by default, such as limits, integrals, sums, and products; `deep=False` prevents recursive deep evaluation. ([SymPy Documentation][3])

---

## 2.12 Agent implementation recipes

## Recipe A — robust symbol factory

```python
from __future__ import annotations
import sympy as sp
from dataclasses import dataclass

@dataclass(frozen=True)
class Symbols:
    x: sp.Symbol
    y: sp.Symbol
    n: sp.Symbol
    a: sp.Symbol

def make_symbols() -> Symbols:
    return Symbols(
        x=sp.Symbol("x", real=True),
        y=sp.Symbol("y", real=True),
        n=sp.Symbol("n", integer=True, nonnegative=True),
        a=sp.Symbol("a", positive=True),
    )
```

Value: centralizes assumptions; prevents same-name/different-assumption drift.

---

## Recipe B — expression tree inspector

```python
def inspect_expr(expr: sp.Basic) -> dict[str, object]:
    expr = sp.sympify(expr)
    return {
        "type": type(expr).__name__,
        "func": expr.func.__name__ if hasattr(expr.func, "__name__") else repr(expr.func),
        "args": expr.args,
        "atoms_symbols": expr.atoms(sp.Symbol),
        "free_symbols": expr.free_symbols,
        "srepr": sp.srepr(expr),
        "hash": hash(expr),
    }
```

Value: debugging failed rewrites, verifying canonicalization, detecting hidden floats, diagnosing symbol mismatch.

---

## Recipe C — exact structural transform via `.func/.args`

```python
def replace_powers_of_x2(expr: sp.Basic, x: sp.Symbol) -> sp.Basic:
    expr = sp.sympify(expr)

    if expr == x**2:
        return sp.Symbol("X2")

    if not expr.args:
        return expr

    new_args = tuple(replace_powers_of_x2(arg, x) for arg in expr.args)
    return expr.func(*new_args)
```

Invariant dependency: safe only because well-formed expressions rebuild from `func(*args)`. ([SymPy Documentation][6])

---

## Recipe D — symbolic equality test with escalation

```python
def equivalent(a: sp.Expr, b: sp.Expr) -> bool | None:
    a = sp.sympify(a)
    b = sp.sympify(b)

    if a == b:
        return True

    delta = sp.factor(sp.together(a - b))
    if delta == 0:
        return True

    q = a.equals(b)
    if q is True:
        return True
    if q is False:
        return False

    return None
```

Value: cheap structural fast path, targeted canonicalization, then heuristic equivalence.

---

## Recipe E — pattern rule with `Wild`

```python
A = sp.Wild("A", exclude=[x])
rule_pattern = A*x + A

def factor_common_linear(expr: sp.Expr, x: sp.Symbol) -> sp.Expr:
    m = expr.match(rule_pattern)
    if not m:
        return expr
    return m[A] * (x + 1)
```

Value: controlled structural rewrite without fragile string parsing.

---

## Recipe F — evaluation-suppressed source-faithful expression

```python
def source_form_add(*terms: sp.Expr) -> sp.Expr:
    return sp.Add(*(sp.sympify(t) for t in terms), evaluate=False)

expr = source_form_add(x, x, sp.Integer(1))
```

Value: preserve pedagogical/intermediate expression form, then release with targeted transforms when ready.

---

## 2.13 Failure modes and guardrails

| Failure mode                                | Symptom                                                 | Corrective action                                                             |
| ------------------------------------------- | ------------------------------------------------------- | ----------------------------------------------------------------------------- |
| Same name, different assumptions            | `z + z`, derivative returns `0`, substitutions miss     | central symbol registry; pass symbols explicitly                              |
| String parsing drift                        | typos become undefined functions/symbols                | build expressions with operators; parse once with explicit local dict         |
| Misusing `==`                               | equivalent formulas compare `False`                     | use `Eq`, canonicalization, `.equals()`                                       |
| Python `if x > 0`                           | `TypeError: cannot determine truth value of Relational` | use assumptions, `Piecewise`, or numeric input validation                     |
| Assuming `.args` order is input order       | rewrite grabs wrong term                                | use semantic helpers: `.as_coeff_mul`, `.as_ordered_terms`, `.as_powers_dict` |
| Mutating expressions                        | no effect or impossible                                 | reassign returned expression                                                  |
| Overbroad `Wild`                            | bad rewrites                                            | add `exclude` and `properties`                                                |
| Blind `evaluate=False`                      | expression later collapses                              | use `UnevaluatedExpr` for external isolation                                  |
| Treating `.atoms(Symbol)` as dependency set | bound variables included/missed semantics               | use `.free_symbols` for dependency analysis                                   |
| Using mutable `Matrix` as symbolic scalar   | hashing/cache mismatch                                  | use `ImmutableMatrix` or `MatrixSymbol`/`MatrixExpr` where appropriate        |

---

## 2.14 Deployment advisory

### Library APIs

```python
def api(expr: sp.Expr, *, x: sp.Symbol) -> sp.Expr:
    expr = sp.sympify(expr)
    if x not in expr.free_symbols:
        ...
    return ...
```

Rules:

```text
Accept SymPy objects, not expression strings.
Accept symbols as parameters.
Sympify numeric literals at API boundary.
Reject or explicitly parse strings.
Return new expressions; never mutate caller-owned state.
```

### Rewrite engines

```text
Use .args/.func for structural recursion.
Use .xreplace for exact node replacement.
Use .subs for mathematical substitution.
Use Wild/match for declarative structural patterns.
Use Dummy for temporary/generated symbols.
```

### Testing

```python
assert expr.func(*expr.args) == expr
assert all(isinstance(arg, sp.Basic) for arg in expr.args)
assert transformed.free_symbols <= expected_symbols
assert equivalent(transformed, expected) is True
```

### Caching

```python
cache: dict[tuple[sp.Basic, ...], sp.Basic] = {}
key = (expr, x, y)
```

SymPy expressions are immutable and hashable, so they are valid dictionary keys. ([SymPy Documentation][1])

---

## 2.15 Minimal agent-ready object-model harness

```python
from __future__ import annotations

import sympy as sp
from dataclasses import dataclass


@dataclass(frozen=True)
class ExprAudit:
    expr: sp.Basic
    srepr: str
    func_name: str
    args: tuple[sp.Basic, ...]
    atoms: set[sp.Basic]
    symbol_atoms: set[sp.Symbol]
    free_symbols: set[sp.Basic]
    structurally_rebuilds: bool
    hash_value: int


def audit(expr) -> ExprAudit:
    expr = sp.sympify(expr)

    rebuilt = expr.func(*expr.args) if expr.args else expr

    return ExprAudit(
        expr=expr,
        srepr=sp.srepr(expr),
        func_name=getattr(expr.func, "__name__", repr(expr.func)),
        args=expr.args,
        atoms=expr.atoms(),
        symbol_atoms=expr.atoms(sp.Symbol),
        free_symbols=expr.free_symbols,
        structurally_rebuilds=(rebuilt == expr),
        hash_value=hash(expr),
    )


def safe_symbols():
    return {
        "x": sp.Symbol("x", real=True),
        "y": sp.Symbol("y", real=True),
        "n": sp.Symbol("n", integer=True, nonnegative=True),
        "a": sp.Symbol("a", positive=True),
    }


def structural_normalize(expr: sp.Expr) -> sp.Expr:
    expr = sp.sympify(expr)
    return sp.factor(sp.together(expr))


def math_equal(a: sp.Expr, b: sp.Expr) -> bool | None:
    a = sp.sympify(a)
    b = sp.sympify(b)

    if a == b:
        return True

    d = structural_normalize(a - b)
    if d == 0:
        return True

    return a.equals(b)


def preserve_addition(*terms) -> sp.Expr:
    return sp.Add(*(sp.sympify(t) for t in terms), evaluate=False)


def isolate(expr) -> sp.Expr:
    return sp.UnevaluatedExpr(sp.sympify(expr))
```

This harness encodes the core object-model contract: explicit symbols, exact object construction, tree inspection, structural rebuild invariants, safe equality escalation, and evaluation control.

[1]: https://docs.sympy.org/latest/explanation/glossary.html "Glossary - SymPy 1.14.0 documentation"
[2]: https://docs.sympy.org/latest/explanation/best-practices.html "Best Practices - SymPy 1.14.0 documentation"
[3]: https://docs.sympy.org/latest/modules/core.html "Core - SymPy 1.14.0 documentation"
[4]: https://docs.sympy.org/latest/tutorials/intro-tutorial/manipulation.html?utm_source=chatgpt.com "Advanced Expression Manipulation"
[5]: https://docs.sympy.org/latest/modules/matrices/expressions.html?utm_source=chatgpt.com "Matrix Expressions - SymPy 1.14.0 documentation"
[6]: https://docs.sympy.org/latest/tutorials/intro-tutorial/manipulation.html "Advanced Expression Manipulation - SymPy 1.14.0 documentation"

# 3) Assumptions system and symbolic truth values — agent-ready deep dive

## 3.0 Contract surface

SymPy has two related assumptions systems. The **core/old assumptions system** attaches predicates to `Symbol` objects and queries predicates through `is_*` attributes. The **new assumptions system** uses predicate objects such as `Q.positive(x)` and evaluates them with `ask()`. Current SymPy docs state that the old/core system is the one widely used inside SymPy, that the new system is not really used anywhere in SymPy yet, and that users should generally prefer the old system for ordinary symbolic programming. ([docs.sympy.org](https://docs.sympy.org/latest/guides/assumptions.html))

```python id="mzx7oa"
import sympy as sp
from sympy import Q, ask, assuming, refine
```

Core value case:

```text id="9onxni"
assumptions = semantic domain constraints
             → safer simplification
             → smaller solver output
             → fewer Piecewise conditions
             → valid branch/absolute-value decisions
             → stronger codegen preconditions
             → explicit uncertainty handling via True/False/None
```

---

## 3.1 Old/core assumptions system

## 3.1.1 Declaration side: symbol construction

Primary syntax:

```python id="wmpzjv"
x = sp.Symbol("x")
xp = sp.Symbol("x", positive=True)
r = sp.Symbol("r", real=True)
n = sp.Symbol("n", integer=True)
k = sp.Symbol("k", integer=True, nonnegative=True)
a = sp.Symbol("a", positive=True, finite=True)
z = sp.Symbol("z", complex=True)
```

Batch syntax:

```python id="r6kk77"
x, y = sp.symbols("x y", real=True)
i, j, k = sp.symbols("i j k", integer=True)
a0, a1, a2 = sp.symbols("a:3", positive=True)
```

Old/core assumptions have two sides: declare assumptions on symbols during construction, then query assumptions on symbols or expressions using corresponding `is_*` attributes. Example: `x = Symbol("x", positive=True)` gives `x.is_positive == True`; an expression such as `1 + x**2` can also infer positivity under that symbol assumption. ([docs.sympy.org](https://docs.sympy.org/latest/guides/assumptions.html))

---

## 3.1.2 Query side: `is_*` attributes

```python id="w3u6kn"
x = sp.Symbol("x")
xp = sp.Symbol("xp", positive=True)
n = sp.Symbol("n", integer=True)

x.is_positive      # None
xp.is_positive     # True
xp.is_real         # True
n.is_integer       # True
n.is_rational      # True
n.is_real          # True
```

Expression queries:

```python id="3ruzxu"
x = sp.Symbol("x", positive=True)
expr = 1 + x**2

expr.is_positive   # True
expr.is_negative   # False
expr.is_real       # True
expr.is_zero       # False
```

Assumption implication rules infer derived facts. The docs describe logical relationships such as `integer -> rational -> real -> complex`, and a predicate like `positive=True` can infer other predicate values such as `negative=False`. ([docs.sympy.org](https://docs.sympy.org/latest/guides/assumptions.html))

---

## 3.1.3 Common old-assumption predicates

```text id="zeb28x"
numeric set/domain:
  integer, rational, irrational, algebraic, transcendental, real, complex

sign:
  positive, negative, zero, nonzero, nonpositive, nonnegative

extended real/infinite:
  finite, infinite, extended_real, extended_positive, extended_negative,
  extended_nonzero, extended_nonpositive, extended_nonnegative

integer refinements:
  even, odd, prime, composite

misc:
  commutative, hermitian, imaginary
```

Canonical query style:

```python id="nxyylu"
if expr.is_zero is True:
    ...
elif expr.is_zero is False:
    ...
else:
    ...
```

Do **not** write assumption-control code as `if expr.is_zero:` unless `None` is intentionally grouped with `False`.

---

## 3.2 Three-valued fuzzy logic

Every old-assumption query can return exactly one of:

```text id="u61bde"
True   = definitely true under known assumptions
False  = definitely false under known assumptions
None   = unknown / not implemented / undecidable / not worth proving cheaply
```

The assumptions guide explicitly states that queries use three-valued fuzzy logic and that `None` means unknown. It also says `None` is expected, not a bug, and code using assumptions must handle all three outcomes rather than presuming a definite answer. ([docs.sympy.org](https://docs.sympy.org/latest/guides/assumptions.html))

### Fuzzy-safe branch template

```python id="6wg45f"
def require_definitely_real(expr: sp.Expr) -> sp.Expr:
    q = expr.is_real
    if q is True:
        return expr
    if q is False:
        raise TypeError(f"expected real expression, got definitely non-real: {expr}")
    raise TypeError(f"realness unknown; add assumptions or refine domain: {expr}")
```

### Fuzzy-safe permissive validation

```python id="rd7aph"
def reject_definitely_nonreal(expr: sp.Expr) -> sp.Expr:
    q = expr.is_real
    if q is False:
        raise TypeError(f"definitely non-real: {expr}")
    return expr  # allow True or None
```

Use permissive validation for symbolic APIs that should accept vanilla symbols; use strict validation for codegen/runtime contracts.

### Fuzzy logic helpers

```python id="m2usrz"
from sympy.core.logic import fuzzy_and, fuzzy_or, fuzzy_not

fuzzy_and([True, True])       # True
fuzzy_and([True, None])       # None
fuzzy_and([True, False])      # False

fuzzy_or([False, None])       # None
fuzzy_or([False, True])       # True

fuzzy_not(None)               # None
```

Custom assumptions handlers should preserve fuzzy logic. SymPy’s custom-function guide demonstrates `_eval_is_*` handlers using structural decomposition and `fuzzy_and`/`fuzzy_not`, and it emphasizes careful handling of `True`, `False`, and `None`. ([docs.sympy.org](https://docs.sympy.org/latest/guides/custom-functions.html))

---

## 3.3 Vanilla symbols: weak semantic knowledge

```python id="4sywfk"
x = sp.Symbol("x")

x.assumptions0      # {'commutative': True}
x.is_real           # None
x.is_complex        # None
x.is_finite         # None
x.is_integer        # None
```

A vanilla symbol has very little formal information attached. SymPy docs show a vanilla symbol’s `assumptions0` containing only `commutative: True` and explain that it is generally better to declare assumptions explicitly because many manipulations are difficult when a symbol is not even known to be finite or complex. ([docs.sympy.org](https://docs.sympy.org/latest/guides/assumptions.html))

Agent default policy:

```text id="ji1pjx"
Symbolic derivation:
  declare the narrowest correct domain early.

Library API:
  accept caller-provided symbols; do not recreate them internally.

Codegen / numeric deployment:
  record domain preconditions explicitly; validate before lambdify/codegen.
```

---

## 3.4 Assumptions-driven simplification

## 3.4.1 `sqrt(x**2)` canonical example

```python id="976dhw"
x = sp.Symbol("x")
sp.sqrt(x**2)
# sqrt(x**2)

y = sp.Symbol("y", positive=True)
sp.sqrt(y**2)
# y
```

SymPy refuses to simplify `sqrt(x**2)` for unconstrained `x` because the simplification is not valid for every possible value allowed by the assumptions; with `positive=True`, the simplification is valid and happens automatically. ([docs.sympy.org](https://docs.sympy.org/latest/guides/assumptions.html))

More granular refinement:

```python id="l0l1tp"
x = sp.Symbol("x")

refine(sp.sqrt(x**2), Q.real(x))
# Abs(x)

refine(sp.sqrt(x**2), Q.positive(x))
# x
```

`refine(expr, assumptions=True)` transforms an expression into a form valid under supplied assumptions; docs distinguish it from `simplify()` and show `refine(sqrt(x**2), Q.real(x)) -> Abs(x)` and `refine(..., Q.positive(x)) -> x`. ([docs.sympy.org](https://docs.sympy.org/latest/modules/assumptions/refine.html))

---

## 3.4.2 Integral convergence / Piecewise reduction

```python id="lgy6gp"
x = sp.Symbol("x", positive=True)

a = sp.Symbol("a")
sp.integrate(sp.exp(-a*x), (x, 0, sp.oo))
# Piecewise((1/a, Abs(arg(a)) < pi/2), (Integral(exp(-a*x), (x, 0, oo)), True))

ap = sp.Symbol("a", positive=True)
sp.integrate(sp.exp(-ap*x), (x, 0, sp.oo))
# 1/ap
```

SymPy best practices show that declaring `a` positive removes a conditional `Piecewise` result for `∫₀∞ exp(-a*x) dx`, because convergence depends on the sign/domain of `a`. ([docs.sympy.org](https://docs.sympy.org/latest/explanation/best-practices.html))

Deployment implication:

```text id="jmfnx8"
Missing assumptions → larger conditional expressions, unevaluated objects, weaker simplification.
Correct assumptions → smaller formulas, cleaner codegen, fewer runtime branches.
Wrong assumptions → mathematically invalid generated results.
```

---

## 3.5 Symbol identity and same-name hazards

```python id="1rbshw"
z1 = sp.Symbol("z")
z2 = sp.Symbol("z", positive=True)

z1 == z2       # False
z1 + z2        # z + z  (two distinct symbols with identical print name)
```

SymPy allows the same printed symbol name with different assumptions, but those symbols are unequal; the best-practices docs recommend always using the same assumptions for each symbol name when assumptions are used. ([docs.sympy.org](https://docs.sympy.org/latest/explanation/best-practices.html))

### Agent-safe symbol registry

```python id="bgqr2q"
from dataclasses import dataclass
import sympy as sp

@dataclass(frozen=True)
class DomainSymbols:
    x: sp.Symbol
    y: sp.Symbol
    n: sp.Symbol
    a: sp.Symbol

def make_domain_symbols() -> DomainSymbols:
    return DomainSymbols(
        x=sp.Symbol("x", real=True),
        y=sp.Symbol("y", real=True),
        n=sp.Symbol("n", integer=True, nonnegative=True),
        a=sp.Symbol("a", positive=True),
    )
```

### API anti-pattern

```python id="3fvrs1"
def bad(expr):
    x = sp.Symbol("x")        # may not be caller's x
    return sp.diff(expr, x)
```

### API pattern

```python id="jd5qte"
def good(expr: sp.Expr, x: sp.Symbol) -> sp.Expr:
    return sp.diff(expr, x)
```

---

## 3.6 `Q`, `ask`, `assuming`: new predicate query surface

## 3.6.1 `Q`: predicate namespace

```python id="yit07y"
Q.positive(x)
Q.integer(n)
Q.real(x)
Q.even(n)
Q.zero(expr)
Q.rational(sp.pi)
```

In the assumptions module, predicates are accessed through `Q`; applying a predicate such as `Q.integer(1)` creates an `AppliedPredicate` object, and `ask()` evaluates that applied predicate to a truth value when possible. ([docs.sympy.org](https://docs.sympy.org/latest/modules/assumptions/index.html))

```python id="db284v"
p = Q.integer(x + 1)

p.function     # Q.integer
p.arguments    # (x + 1,)
ask(p)         # True / False / None
```

---

## 3.6.2 `ask(proposition, assumptions=True, context=...)`

```python id="55u92b"
ask(Q.rational(sp.pi))
# False

x, y = sp.symbols("x y")
ask(Q.even(x*y), Q.even(x) & Q.integer(y))
# True

ask(Q.prime(4*x), Q.integer(x))
# False

print(ask(Q.odd(3*x)))
# None
```

`ask()` returns `True`, `False`, or `None`; it raises `ValueError` for inconsistent assumptions. Its optional assumptions argument should be a boolean expression made from predicates such as `Q.integer(x)`, `Q.positive(x)`, or combinations using `&`. ([docs.sympy.org](https://docs.sympy.org/latest/modules/assumptions/index.html))

### Inconsistency handling

```python id="h8kqiw"
try:
    ask(Q.integer(x), Q.even(x) & Q.odd(x))
except ValueError as exc:
    # inconsistent assumption set
    ...
```

### Relation caveat

```python id="4d77kp"
ask(Q.positive(x), x > 0)   # not a reliable relational-assumption pattern
```

The assumptions docs state that relations in `ask` assumptions are not implemented yet and that `ask(Q.positive(x), x > 0)` will not give a meaningful result. ([docs.sympy.org](https://docs.sympy.org/latest/modules/assumptions/index.html))

Use predicate assumptions instead:

```python id="it88wm"
ask(Q.positive(x), Q.positive(x))
```

---

## 3.6.3 `assuming(*facts)`

```python id="g0ltpk"
x, y = sp.symbols("x y")

with assuming(Q.positive(x), Q.positive(y)):
    ask(Q.positive(2*x + y))
    # True
```

`assuming` creates a context so repeated `ask()` calls can use facts without passing them explicitly every time; docs show `with assuming(Q.positive(x), Q.positive(y)):` followed by `ask(Q.positive(2*x + y)) -> True`. ([docs.sympy.org](https://docs.sympy.org/latest/modules/assumptions/index.html))

Agent deployment rule:

```text id="n6tics"
Use assuming() for local proof/query contexts.
Do not use it as a substitute for Symbol(..., positive=True) when constructor-time simplification is needed.
```

Reason: many simplifications happen at expression construction time through old assumptions; `assuming()` does not retroactively reconstruct already-built expression trees.

---

## 3.7 `refine`: assumption-specific expression transformation

```python id="hbwdga"
x = sp.Symbol("x")

refine(sp.sqrt(x**2), Q.real(x))
# Abs(x)

refine(sp.sqrt(x**2), Q.positive(x))
# x

refine(Q.real(x), Q.positive(x))
# True

refine(Q.positive(x), Q.real(x))
# Q.positive(x)
```

`refine()` simplifies expressions using assumptions and can also reduce boolean expressions to symbolic `S.true` or `S.false`; unlike `ask()`, it does not return Python `None` for undetermined propositions and may leave expressions unreduced. ([docs.sympy.org](https://docs.sympy.org/latest/modules/assumptions/refine.html))

Decision surface:

| Need                                    | Use                                                       |
| --------------------------------------- | --------------------------------------------------------- |
| Boolean truth query → `True/False/None` | `ask(Q.pred(expr), facts)`                                |
| Expression rewrite under facts          | `refine(expr, facts)`                                     |
| Constructor-time domain semantics       | `Symbol(..., assumptions)`                                |
| Heuristic algebraic simplification      | targeted `factor/cancel/trigsimp/...`; maybe `simplify()` |
| Contextual repeated predicate queries   | `with assuming(...): ask(...)`                            |

---

## 3.8 Old `is_*` vs `Q/ask`: selection rules

### Use old/core `is_*` when

```text id="ossno7"
Need fast local property query.
Need constructor-time simplification.
Need class-level assumption handler integration.
Need compatibility with most SymPy internals.
Need standard user-facing symbolic code.
```

```python id="3ynxs3"
if expr.is_positive is True:
    ...
```

### Use `Q/ask` when

```text id="rgorvb"
Need a temporary assumption context.
Need proposition composition: Q.integer(x) & Q.positive(x).
Need query facts that are not attached to Symbol construction.
Need predicate-expression objects as logic IR.
```

```python id="q7zs7q"
facts = Q.integer(n) & Q.positive(n)
ask(Q.even(n**2 + n), facts)
```

### Use `refine` when

```text id="ybv5d5"
Need expression-level output rewritten under facts.
Need Abs/sign/power/argument/boolean simplification under predicates.
```

```python id="oz79zd"
refine(expr, Q.positive(x))
```

---

## 3.9 Other `is_*` properties: not all are assumptions

Not every `is_*` attribute belongs to the old assumptions system. The assumptions guide distinguishes assumption predicates from other semantic or structural properties: for example, matrices use `is_zero_matrix` rather than `is_zero` for zero-matrix semantics, and structural properties such as `is_Number` always return `True`/`False` rather than fuzzy booleans. ([docs.sympy.org](https://docs.sympy.org/latest/guides/assumptions.html))

```python id="bwobep"
M = sp.Matrix([[0, 0], [0, 0]])

M.is_zero          # False
M.is_zero_matrix   # True
```

Agent classification:

```text id="fou7mc"
Semantic fuzzy predicates:
  .is_positive, .is_real, .is_zero, .is_integer → True/False/None

Non-assumption semantic properties:
  .is_zero_matrix, Set.is_empty → often fuzzy-like, but not old assumptions

Structural type flags:
  .is_Number, .is_Add, .is_Mul → type/structure, usually True/False only
```

---

## 3.10 Custom function integration

For a custom `Function`, assumptions are implemented with:

```text id="2b1w6w"
class attributes:
  is_real = True
  is_integer = False
  is_nonnegative = True

dynamic handlers:
  _eval_is_real(self)
  _eval_is_positive(self)
  _eval_is_zero(self)
  _eval_is_finite(self)
  ...
```

Example:

```python id="dfqsoa"
class sqr(sp.Function):
    @classmethod
    def eval(cls, x):
        if x.is_zero is True:
            return sp.Integer(0)

    def _eval_is_nonnegative(self):
        x, = self.args
        if x.is_real is True:
            return True

    def _eval_is_zero(self):
        x, = self.args
        return x.is_zero
```

Custom-function assumptions rules:

```text id="kul1vf"
Return True/False only when definitely known.
Return None or fall through when unknown.
Use self.args; avoid rebuilding expressions inside _eval_is_* handlers.
Do not query assumptions on self inside its own _eval_is_* handlers.
Use fuzzy_and/fuzzy_or/fuzzy_not for compound predicates.
Do not define is_<assumption> as @property.
```

The custom-functions guide warns not to create new expressions in assumptions handlers because expression construction can trigger further assumption queries and even infinite recursion; it recommends structural decomposition such as `as_independent()`. It also warns never to define `is_<assumption>` as a property; use class variables for fixed facts and `_eval_is_*` methods for argument-dependent facts. ([docs.sympy.org](https://docs.sympy.org/latest/guides/custom-functions.html))

---

## 3.11 New assumptions system: current practical position

New assumptions primitives:

```python id="24cgbn"
from sympy import Q, ask, assuming, refine

Q.positive(x)       # predicate application
ask(Q.positive(x))  # truth query
with assuming(Q.real(x)):
    ...
refine(expr, Q.positive(x))
```

Current caveats:

```text id="swsozv"
Old/core assumptions:
  mature, widely used inside SymPy, constructor-integrated, is_* API.

New assumptions:
  predicate-logic surface, supports richer theoretical model,
  useful for ask/refine contexts,
  less integrated with general SymPy internals,
  relational-assumption support not generally implemented,
  exact relational API still not fully settled.
```

The assumptions guide states that the new system has theoretical capability for relational assumptions, but algorithms to use that information are not yet implemented and the exact API for relational assumptions is undecided. ([docs.sympy.org](https://docs.sympy.org/latest/guides/assumptions.html))

Migration advisory:

```text id="emlf4x"
Do not rewrite existing old-assumption code to new assumptions just for modernity.
Use old assumptions for Symbol construction and core expression behavior.
Use Q/ask/refine as an adjunct query/refinement layer.
Treat relation-based ask assumptions as non-production unless explicitly tested.
Pin SymPy version and regression-test assumptions-sensitive outputs.
```

---

## 3.12 Deployment patterns

## Pattern A — domain registry

```python id="oonb6g"
@dataclass(frozen=True)
class Domain:
    x: sp.Symbol
    y: sp.Symbol
    t: sp.Symbol
    n: sp.Symbol
    a: sp.Symbol

def domain() -> Domain:
    return Domain(
        x=sp.Symbol("x", real=True),
        y=sp.Symbol("y", real=True),
        t=sp.Symbol("t", real=True),
        n=sp.Symbol("n", integer=True, nonnegative=True),
        a=sp.Symbol("a", positive=True),
    )
```

Value: prevents same-name assumption drift; centralizes codegen preconditions; makes solver/simplifier behavior stable.

---

## Pattern B — strict symbolic API input contract

```python id="u8620w"
def positive_power_kernel(x: sp.Symbol) -> sp.Expr:
    if x.is_positive is not True:
        raise TypeError("x must be constructed with positive=True")
    return sp.sqrt(x**2)
```

Use when output correctness depends on constructor-time simplification.

---

## Pattern C — permissive symbolic API input contract

```python id="xz6uiq"
def safe_sqrt_square(x: sp.Expr) -> sp.Expr:
    q = x.is_positive
    if q is True:
        return x
    if q is False:
        return sp.Abs(x) if x.is_real is True else sp.sqrt(x**2)
    return sp.sqrt(x**2)
```

Use when unknown domains must remain symbolic, not rejected.

---

## Pattern D — temporary assumption query

```python id="jv94xy"
def maybe_positive(expr: sp.Expr, facts=True) -> bool | None:
    return ask(Q.positive(expr), facts)

facts = Q.positive(x) & Q.real(y)
maybe_positive(x + y**2, facts)
```

Use for local logic without recreating symbols.

---

## Pattern E — refinement boundary before codegen

```python id="5os2kc"
def prepare_for_codegen(expr: sp.Expr, facts=True) -> sp.Expr:
    expr = refine(expr, facts)
    expr = sp.factor(sp.together(expr))
    return expr

x = sp.Symbol("x")
expr = sp.sqrt(x**2) + 1

prepared = prepare_for_codegen(expr, Q.positive(x))
# x + 1
```

Value: declare deployment-domain facts once; produce simpler generated code.

---

## Pattern F — assumption-aware validation report

```python id="us8i4p"
def assumption_report(expr: sp.Expr) -> dict[str, bool | None]:
    return {
        "real": expr.is_real,
        "finite": expr.is_finite,
        "zero": expr.is_zero,
        "positive": expr.is_positive,
        "negative": expr.is_negative,
        "integer": expr.is_integer,
        "rational": expr.is_rational,
    }
```

Use in agent debugging, symbolic pipeline linting, and codegen precondition reports.

---

## 3.13 Testing and QA matrix

Assumption-sensitive code requires tests over **positive**, **negative**, **zero**, **real unknown**, **complex unknown**, and **symbolically unknown** cases.

```python id="glh4yx"
def test_sqrt_square_contract():
    xp = sp.Symbol("x", positive=True)
    xr = sp.Symbol("x", real=True)
    xv = sp.Symbol("x")

    assert sp.sqrt(xp**2) == xp
    assert refine(sp.sqrt(xr**2), Q.real(xr)) == sp.Abs(xr)
    assert sp.sqrt(xv**2) == sp.sqrt(xv**2)
```

Same-name hazard test:

```python id="pp37nq"
def test_no_same_name_assumption_drift():
    z_plain = sp.Symbol("z")
    z_pos = sp.Symbol("z", positive=True)
    assert z_plain != z_pos
```

Fuzzy-handler test:

```python id="9apcee"
def assert_fuzzy(q):
    assert q in (True, False, None)

for e in [sp.Symbol("x"), sp.Symbol("x", positive=True), sp.Integer(0)]:
    assert_fuzzy(e.is_positive)
```

Codegen precondition test:

```python id="k7hm0e"
def require_known_real(expr):
    if expr.is_real is not True:
        raise AssertionError(f"not definitely real: {expr}")

x = sp.Symbol("x", real=True)
require_known_real(sp.sin(x))
```

---

## 3.14 Anti-pattern inventory

| Anti-pattern                                           | Failure mode                                        | Correct pattern                                        |
| ------------------------------------------------------ | --------------------------------------------------- | ------------------------------------------------------ |
| `if expr.is_positive:`                                 | treats `None` as `False`                            | `is True` / `is False` / unknown branch                |
| recreate `Symbol("x")` inside helper                   | caller assumptions lost                             | pass `x` into helper                                   |
| same printed symbol with different assumptions         | hidden distinct variables                           | centralized symbol registry                            |
| relying on `assuming()` for constructor simplification | already-built tree unchanged                        | construct symbols with assumptions; or use `refine`    |
| `ask(Q.positive(x), x > 0)`                            | relational assumptions not implemented meaningfully | use `Q.positive(x)` facts                              |
| overusing vanilla symbols                              | weaker simplification, more Piecewise               | declare precise assumptions                            |
| hard rejection on `None` in generic symbolic libraries | rejects valid symbolic inputs                       | reject only `is False` unless strict contract          |
| custom `_eval_is_*` creates expressions                | recursion/performance hazards                       | structural decomposition via `.args`, `as_independent` |
| custom assumption property with `@property`            | breaks automatic deduction                          | class variable or `_eval_is_*` method                  |
| treating all `is_*` as assumptions                     | matrix/set/structural mismatch                      | distinguish assumptions vs semantic/structural flags   |

---

## 3.15 Minimal assumptions harness

```python id="1a7l2u"
from __future__ import annotations

from dataclasses import dataclass
import sympy as sp
from sympy import Q, ask, refine, assuming
from sympy.core.logic import fuzzy_and, fuzzy_not


@dataclass(frozen=True)
class AssumptionFacts:
    real: bool | None
    finite: bool | None
    zero: bool | None
    nonzero: bool | None
    positive: bool | None
    negative: bool | None
    nonnegative: bool | None
    integer: bool | None
    rational: bool | None


def facts(expr: sp.Expr) -> AssumptionFacts:
    expr = sp.sympify(expr)
    return AssumptionFacts(
        real=expr.is_real,
        finite=expr.is_finite,
        zero=expr.is_zero,
        nonzero=expr.is_nonzero,
        positive=expr.is_positive,
        negative=expr.is_negative,
        nonnegative=expr.is_nonnegative,
        integer=expr.is_integer,
        rational=expr.is_rational,
    )


def definitely(q: bool | None) -> bool:
    return q is True


def definitely_not(q: bool | None) -> bool:
    return q is False


def unknown(q: bool | None) -> bool:
    return q is None


def require(expr: sp.Expr, predicate_name: str) -> sp.Expr:
    q = getattr(expr, f"is_{predicate_name}")
    if q is True:
        return expr
    if q is False:
        raise TypeError(f"{expr} is definitely not {predicate_name}")
    raise TypeError(f"{expr}: {predicate_name} unknown")


def reject_if_false(expr: sp.Expr, predicate_name: str) -> sp.Expr:
    q = getattr(expr, f"is_{predicate_name}")
    if q is False:
        raise TypeError(f"{expr} is definitely not {predicate_name}")
    return expr


def query(expr: sp.Expr, pred, assumptions=True) -> bool | None:
    return ask(pred(sp.sympify(expr)), assumptions)


def positive_refinement(expr: sp.Expr, x: sp.Symbol) -> sp.Expr:
    return refine(expr, Q.positive(x))


def safe_sqrt_square(x: sp.Expr) -> sp.Expr:
    x = sp.sympify(x)
    if x.is_positive is True:
        return x
    if x.is_real is True:
        return sp.Abs(x)
    return sp.sqrt(x**2)


class squared_norm(sp.Function):
    @classmethod
    def eval(cls, x):
        if x.is_zero is True:
            return sp.Integer(0)

    def _eval_is_nonnegative(self):
        x, = self.args
        if x.is_real is True:
            return True

    def _eval_is_positive(self):
        x, = self.args
        return fuzzy_and([x.is_real, fuzzy_not(x.is_zero)])

    def _eval_is_zero(self):
        x, = self.args
        return x.is_zero
```

This harness encodes: construction-time assumptions, fuzzy-safe branching, old `is_*` queries, new `Q/ask` query composition, `refine` transformation, and custom-function assumption handlers.

# 4) Basic expression operations and manipulation primitives — agent-ready deep dive

## 4.0 Manipulation model

SymPy expression manipulation is **tree transformation over immutable `Basic`/`Expr` nodes**. Correct agent behavior: choose the narrowest primitive that matches the intended semantics: substitution, exact-node replacement, pattern replacement, targeted expansion, rational normalization, coefficient extraction, traversal, or numeric evaluation. Prefer targeted transforms over `simplify()` in production because SymPy’s docs describe `simplify()` as heuristic, potentially slow, and without guaranteed output form; targeted functions such as `factor()` and `cancel()` have explicit output contracts. ([SymPy Documentation][1])

```python
import sympy as sp

x, y, z = sp.symbols("x y z")
```

---

## 4.1 Primitive selection map

| Intent                                             | Primitive                                                         | Contract                                                             |
| -------------------------------------------------- | ----------------------------------------------------------------- | -------------------------------------------------------------------- |
| substitute mathematically meaningful subexpression | `.subs(old, new)` / `.subs(dict)` / `.subs(list)`                 | object-defined substitution; may match powers/derived subexpressions |
| exact expression-tree node replacement             | `.xreplace({old_node: new_node})`                                 | replaces only full matched nodes                                     |
| structural/pattern replacement                     | `.replace(query, value, ...)`                                     | type, pattern, or predicate-driven rewrite                           |
| evaluate unevaluated symbolic objects              | `.doit(deep=True/False)`                                          | evaluates `Integral`, `Sum`, `Limit`, `Derivative`, `Subs`, etc.     |
| numeric approximation                              | `.evalf(n, subs=...)`, `.n(...)`, `N(expr, n)`                    | arbitrary-precision floating evaluation                              |
| expand algebraic/log/trig/complex/function forms   | `expand(...)`, `expand_*`                                         | hint-controlled expansion                                            |
| polynomial/rational canonicalization               | `factor`, `cancel`, `together`, `apart`, `collect`                | targeted algebraic forms                                             |
| coefficient/term extraction                        | `.coeff`, `.as_coeff_*`, `.as_numer_denom`                        | structural extraction, usually no factoring                          |
| pattern matching                                   | `.match(pattern)`, `Wild`                                         | structural match dictionary or `None`                                |
| traversal/introspection                            | `preorder_traversal`, `postorder_traversal`, `srepr`, `count_ops` | tree diagnostics and rewrite scaffolding                             |

---

## 4.2 Substitution family: `.subs()`, `.xreplace()`, `.replace()`

## 4.2.1 `.subs(...)`: semantic substitution

Signatures used most often:

```python
expr.subs(old, new)
expr.subs({old1: new1, old2: new2})
expr.subs([(old1, new1), (old2, new2)])
expr.subs(replacements, simultaneous=True)
```

`.subs()` replaces instances/subexpressions according to SymPy object substitution semantics. It accepts pair form, dict form, and ordered list-of-pairs form; list order matters. SymPy docs show `(x + y).subs([(y, x**2), (x, 2)]) -> 6`, but reversing the pair order gives `x**2 + 2`. ([SymPy Documentation][2])

```python
expr = sp.cos(x) + 1

expr.subs(x, y)
# cos(y) + 1

expr.subs(x, 0)
# 2

(x + y).subs([(y, x**2), (x, 2)])
# 6

(x + y).subs([(x, 2), (y, x**2)])
# x**2 + 2
```

### Mathematical subexpression behavior

```python
(x**2 + x**4).subs(x**2, y)
# y**2 + y
```

`.subs(x**2, y)` rewrites both `x**2` and the `x**4 == (x**2)**2` occurrence. Use `.xreplace()` for exact node replacement only. ([SymPy Documentation][2])

### Simultaneous substitution

```python
(x / y).subs([(x, 0), (y, 0)])
# 0

(x / y).subs([(x, 0), (y, 0)], simultaneous=True)
# nan
```

`simultaneous=True` delays evaluation until all substitutions have been made and prevents later substitutions from modifying earlier replacement results. ([SymPy Documentation][2])

```python
expr = (x + y) / y

expr.subs({x + y: y, y: x + y})
# 1

expr.subs({x + y: y, y: x + y}, simultaneous=True)
# y/(x + y)
```

### Deployment guidance

```text
Use .subs when:
  - replacing variables with values;
  - specializing symbolic formulas;
  - applying mathematically meaningful substitutions;
  - evaluating expressions at points;
  - order/simultaneity is intentional.

Avoid .subs when:
  - exact tree-node replacement is required;
  - bound variables must be protected with strict alpha hygiene;
  - performance-critical bulk exact replacement is needed.
```

---

## 4.2.2 `.xreplace(rule)`: exact node replacement

Signature:

```python
expr.xreplace({old_node: new_node})
```

`.xreplace()` replaces only complete nodes in the expression tree. It does **not** perform algebraic matching, power recognition, or semantic substitution. Docs show `(x*y + z).xreplace({x*y: pi}) -> z + pi`, while `(x*y*z).xreplace({x*y: pi})` remains unchanged because `x*y` is not an entire node in that tree. ([SymPy Documentation][2])

```python
(x**2 + x**4).xreplace({x**2: y})
# x**4 + y

(x*y + z).xreplace({x*y: sp.pi})
# z + pi

(x*y*z).xreplace({x*y: sp.pi})
# x*y*z
```

### Bound-symbol caveat

`.xreplace()` does not distinguish free and bound symbols. Docs contrast it with `.subs()`: replacing `x` inside an `Integral` changes bound variables too, and replacing a bound variable with a non-symbolic expression can produce invalid limits. ([SymPy Documentation][2])

```python
sp.Integral(x, (x, 1, 2*x)).xreplace({x: y})
# Integral(y, (y, 1, 2*y))

sp.Integral(x, (x, 1, 2*x)).xreplace({x: 2*y})
# ValueError: Invalid limits ...
```

### Deployment guidance

```text
Use .xreplace when:
  - exact DAG/tree node replacement is required;
  - using match dictionaries: pattern.xreplace(expr.match(pattern));
  - replacing generated temporaries / CSE symbols;
  - deterministic no-math rewrite is required.

Avoid .xreplace when:
  - you need bound-variable safety;
  - you expect algebraic matching;
  - replacement could violate binder/limit structure.
```

---

## 4.2.3 `.replace(query, value, map=False, simultaneous=True, exact=None)`

`.replace()` performs structural/pattern replacement. It supports type→type, type→function, pattern→expression, pattern→function, and predicate→function replacement. If `map=True`, it also returns the `{old: new}` map. For patterns with multiple `Wild` symbols, `exact` controls zero-match behavior and can produce non-intuitive results if set loosely. ([SymPy Documentation][2])

### Type → type

```python
f = sp.log(sp.sin(x)) + sp.tan(sp.sin(x**2))

f.replace(sp.sin, sp.cos)
# log(cos(x)) + tan(cos(x**2))
```

### Type → function

```python
f.replace(sp.sin, lambda arg: sp.sin(2*arg))
# log(sin(2*x)) + tan(sin(2*x**2))
```

### Pattern → expression

```python
a = sp.Wild("a")
f.replace(sp.sin(a), sp.tan(a))
# log(tan(x)) + tan(tan(x**2))

f.replace(sp.sin(a), a)
# log(x) + tan(x**2)
```

### Predicate → function

```python
g = 2 * sp.sin(x**3)

g.replace(lambda e: e.is_Number, lambda e: e**2)
# 4*sin(x**9)
```

### Map output

```python
sp.sin(x).replace(sp.sin, sp.cos, map=True)
# (cos(x), {sin(x): cos(x)})
```

### Deployment guidance

```text
Use .replace when:
  - matching by class/type;
  - applying structural pattern rewrites;
  - applying predicate-driven local transforms;
  - needing old→new rewrite map.

Guardrails:
  - constrain Wild patterns;
  - test exact=True/False explicitly;
  - avoid broad predicates that transform too much;
  - snapshot output for production rewrite rules.
```

---

## 4.3 Evaluation: `.doit()`, `.evalf()`, `N()`

## 4.3.1 `.doit(**hints)`

Signature:

```python
expr.doit(**hints)
expr.doit(deep=False)
```

`.doit()` evaluates objects that are unevaluated by default, including limits, integrals, sums, and products; by default it evaluates recursively unless a hint excludes a class or `deep=False` is used. ([SymPy Documentation][2])

```python
obj = 2 * sp.Integral(x, x)

obj
# 2*Integral(x, x)

obj.doit()
# x**2

obj.doit(deep=False)
# 2*Integral(x, x)
```

`Subs` objects represent unevaluated substitution, commonly for derivatives evaluated at a point; docs note `.doit()` effects possible substitutions inside the object. ([SymPy Documentation][2])

```python
f = sp.Function("f")
Sobj = sp.Subs(f(x) * sp.sin(y) + z, (x, y), (0, 1))

Sobj.doit()
# z + f(0)*sin(1)
```

### Deployment guidance

```text
Use .doit at phase boundaries:
  - after constructing unevaluated calculus objects;
  - after symbolic manipulations that intentionally delay evaluation;
  - before numeric evaluation/codegen, if unevaluated objects are not supported downstream.

Use deep=False when:
  - only top-level evaluation should occur;
  - inner unevaluated objects encode constraints or delayed operations.
```

---

## 4.3.2 `.evalf(...)`, `.n(...)`, `N(...)`

Signatures:

```python
expr.evalf(n=15, subs=None, maxn=100, chop=False, strict=False, quad=None, verbose=False)
expr.n(n=15, subs=None, maxn=100, chop=False, strict=False, quad=None, verbose=False)
sp.N(expr, n=15, **options)
```

`evalf()` evaluates to `n` digits; `subs` must be a dictionary for numerical substitution; `.n()` and `N()` are equivalent convenience forms over `evalf()`. ([SymPy Documentation][2])

```python
expr = sp.pi * x + sp.E

expr.evalf()
# 15-digit default

expr.evalf(50)
# 50-digit approximation

expr.evalf(30, subs={x: sp.Rational(1, 3)})
# numerical value after exact symbolic substitution

sp.N(expr, 80)
# calls expr.evalf(80)
```

### Float precision trap

`evalf()` can increase working/display precision, but it cannot recover accuracy lost when an inexact `Float` entered the expression too early. Docs show that a low-precision `Float(.1, 1)` cannot be made accurate merely by asking for five digits. ([SymPy Documentation][2])

```python
bad = sp.Float(0.1, 1)
bad.evalf(20)
# more digits, not more source accuracy
```

### Deployment guidance

```text
Use evalf/N when:
  - scalar arbitrary-precision approximation is needed;
  - numeric report/diagnostics required;
  - symbolic formula remains exact until final evaluation.

Prefer lambdify/codegen when:
  - repeated evaluation;
  - arrays/vectors;
  - production numeric kernels;
  - performance-sensitive loops.
```

---

## 4.4 Expansion: `expand`, `expand_trig`, `expand_log`, `expand_func`, `expand_complex`

## 4.4.1 `expand(...)`

Signature:

```python
sp.expand(
    e,
    deep=True,
    modulus=None,
    power_base=True,
    power_exp=True,
    mul=True,
    log=True,
    multinomial=True,
    basic=True,
    **hints,
)
```

`expand()` applies hint-driven expansions. Default active hints include `basic`, `log`, `multinomial`, `mul`, `power_base`, and `power_exp`; non-default hints include `complex`, `func`, and `trig`. `deep=True` recursively expands inside function arguments; `deep=False` restricts to the top-level. `force=True` can ignore assumptions for some expansions. ([SymPy Documentation][2])

```python
sp.expand((x + 1)**2)
# x**2 + 2*x + 1

sp.expand(sp.exp(x + y))
# exp(x)*exp(y)

sp.expand((x*y)**z)
# (x*y)**z

sp.expand((x*y)**z, force=True)
# x**z*y**z
```

### Expansion controls

```python
expr = sp.exp(x + y) * (x + y)

sp.expand(expr)
# x*exp(x)*exp(y) + y*exp(x)*exp(y)

sp.expand(expr, power_exp=False)
# x*exp(x + y) + y*exp(x + y)

sp.expand(expr, mul=False)
# (x + y)*exp(x)*exp(y)
```

Docs warn that expand hints are applied in an arbitrary but consistent order in the current implementation, and that this may change; use `expand_hint` helper functions or disable hints for fine control. ([SymPy Documentation][2])

### Rational targets

```python
expr = (x + y)*y/x/(x + 1)

sp.expand(expr, frac=True)
# (x*y + y**2)/(x**2 + x)

sp.expand(expr, numer=True)
# (x*y + y**2)/(x*(x + 1))

sp.expand(expr, denom=True)
# y*(x + y)/(x**2 + x)
```

### Modulus

```python
sp.expand((3*x + 1)**2, modulus=5)
# 4*x**2 + x + 1
```

---

## 4.4.2 Dedicated wrappers

Dedicated wrappers call `expand()` with exactly one hint, reducing output drift and making intent explicit. Docs list wrappers such as `expand_mul`, `expand_log`, `expand_func`, `expand_trig`, `expand_complex`, `expand_power_exp`, and `expand_power_base`. ([SymPy Documentation][2])

```python
sp.expand_trig(sp.sin(x + y))
# sin(x)*cos(y) + sin(y)*cos(x)

sp.expand_log(sp.log(x*y**2))      # requires assumptions unless force=True
sp.expand_log(sp.log(x*y**2), force=True)

sp.expand_func(sp.gamma(x + 2))
# x*(x + 1)*gamma(x)

sp.expand_complex(sp.exp(z))
# I*exp(re(z))*sin(im(z)) + exp(re(z))*cos(im(z))
```

### Assumption-sensitive log expansion

```python
x0, y0 = sp.symbols("x y")
sp.expand_log(sp.log(x0**2*y0))
# log(x**2*y)

xp, yp = sp.symbols("xp yp", positive=True)
sp.expand_log(sp.log(xp**2*yp))
# 2*log(xp) + log(yp)
```

Log expansion requires positivity/realness assumptions unless `force=True` is used. ([SymPy Documentation][2])

### Deployment guidance

```text
Use expand_* wrappers in production:
  - expand_mul for distributive expansion only;
  - expand_trig for trig identities only;
  - expand_log only with assumptions or force explicitly documented;
  - expand_func for special-function identities;
  - expand_complex for real/imag decomposition.

Avoid full expand() when:
  - expression swell risk is high;
  - downstream needs factored or rational form;
  - exact output shape must be stable.
```

---

## 4.5 Collection, factoring, rational forms

## 4.5.1 `collect(expr, syms, ...)`

```python
sp.collect(expr, x)
expr.collect(x)
```

`collect()` groups common powers of a term; docs specifically pair `collect()` with `.coeff(x, n)` for coefficient extraction. ([SymPy Documentation][3])

```python
expr = x*y + x - 3 + 2*x**2 - z*x**2 + x**3

collected = sp.collect(expr, x)
# x**3 + x**2*(2 - z) + x*(y + 1) - 3

collected.coeff(x, 2)
# 2 - z
```

### `evaluate=False`

```python
sp.collect(expr, x, evaluate=False)
# {x**3: 1, x**2: 2 - z, x: y + 1, 1: -3}  # shape depends on expression
```

Use for structured coefficient dictionaries; validate output shape in tests.

---

## 4.5.2 `factor(expr, *gens, **opts)`

```python
sp.factor(expr)
sp.factor(expr, x)
sp.factor(expr, modulus=2)
sp.factor(expr, extension=sp.sqrt(2))
sp.factor(expr, gaussian=True)
sp.factor(expr, deep=True)
```

For polynomials with rational coefficients, `factor()` returns irreducible factors over the rationals; docs describe it as the opposite of `expand()` for polynomial expressions. The polynomial reference adds that factorization defaults to rationals and can use `extension`, `modulus`, or `domain` options for other domains. ([SymPy Documentation][3])

```python
sp.factor(x**3 - x**2 + x - 1)
# (x - 1)*(x**2 + 1)

sp.factor(x**2 + 1)
# x**2 + 1

sp.factor(x**2 + 1, modulus=2)
# (x + 1)**2

sp.factor(x**2 - 2, extension=sp.sqrt(2))
# (x - sqrt(2))*(x + sqrt(2))
```

### Structured factorization

```python
sp.factor_list(x**2*z + 4*x*y*z + 4*y**2*z)
# (1, [(z, 1), (x + 2*y, 2)])
```

### Deployment guidance

```text
Use factor when:
  - polynomial irreducible factor form is required;
  - solver preprocessing;
  - codegen branch simplification after cancellation;
  - exact domain control matters.

Use factor_list when:
  - multiplicities matter;
  - downstream agents need structured factors;
  - avoiding string parsing of factored output.
```

---

## 4.5.3 `cancel(expr)`

```python
sp.cancel(expr)
expr.cancel()
```

`cancel()` converts a rational function into canonical `p/q` form where `p` and `q` are expanded polynomials with no common factors and normalized leading coefficients. Docs note `cancel()` is more efficient than `factor()` if the only goal is canceled rational form. ([SymPy Documentation][3])

```python
expr = (x**2 + 2*x + 1)/(x**2 + x)

sp.cancel(expr)
# (x + 1)/x
```

### Deployment guidance

```text
Use cancel when:
  - canonical rational function required;
  - equality checks over rational expressions;
  - generated code should avoid removable factors;
  - denominator/numerator inspection follows.

Prefer cancel over factor for rational normal form.
```

---

## 4.5.4 `together(expr, deep=False, fraction=True)`

```python
sp.together(expr)
sp.together(expr, deep=True)
```

`together()` denests and combines rational subexpressions while preserving as much input structure as possible and performing no expansion; docs say to use `cancel()` for complete reduction/minimized numerator/denominator degree. It is described as a complement to `apart()`, with `apart(together(expr))` intended to return the original expression unchanged in suitable cases. ([SymPy Documentation][4])

```python
sp.together(1/x + 1/y)
# (x + y)/(x*y)

sp.together(1/(1 + 1/x) + 1/(1 + 1/y))
# (x*(y + 1) + y*(x + 1))/((x + 1)*(y + 1))

sp.together(sp.exp(1/x + 1/y))
# exp(1/y + 1/x)

sp.together(sp.exp(1/x + 1/y), deep=True)
# exp((x + y)/(x*y))
```

### Deployment guidance

```text
Use together when:
  - common-denominator form is needed;
  - expression structure should remain minimally disturbed;
  - later apart/cancel step may be optional.

Use cancel(together(expr)) when:
  - canonical reduced rational form is required.
```

---

## 4.5.5 `apart(f, x=None, full=False, **options)`

```python
sp.apart(expr, x)
sp.apart(expr, x, full=True)
```

`apart()` computes partial fraction decomposition. The default algorithm uses undetermined coefficients and polynomial factorization; `full=True` selects Bronstein’s algorithm and may return `RootSum`, with `.doit()` yielding a more human-readable result in some cases. ([SymPy Documentation][3])

```python
expr = (4*x**3 + 21*x**2 + 10*x + 12)/(x**4 + 5*x**3 + 5*x**2 + 4*x)

sp.apart(expr, x)
# partial fractions
```

### Deployment guidance

```text
Use apart when:
  - integration preprocessing;
  - residue/partial fraction workflows;
  - rational expression decomposition for analysis.

Use together/cancel afterward if:
  - returning to common-denominator or reduced rational form.
```

---

## 4.6 Term and coefficient access

## 4.6.1 `.as_coeff_add(*deps)`

```python
c, terms = expr.as_coeff_add(*deps)
```

Treats expression as an additive object and returns `(c, args)` where `c` is the rational/additive part independent of `deps`, and `args` are the remaining additive terms. Use when expression may or may not be an `Add`. ([SymPy Documentation][2])

```python
(3 + x + y).as_coeff_add()
# (3, (x, y))

(3 + x + y).as_coeff_add(x)
# (y + 3, (x,))

(3 + y).as_coeff_add(x)
# (y + 3, ())
```

---

## 4.6.2 `.as_coeff_mul(*deps)`

```python
c, factors = expr.as_coeff_mul(*deps)
```

Treats expression as multiplicative and returns `(c, args)` where `c` contains rational and dependency-independent factors, and `args` are dependent factors. Use when expression may or may not be a `Mul`. ([SymPy Documentation][2])

```python
(3*x*y).as_coeff_mul()
# (3, (x, y))

(3*x*y).as_coeff_mul(x)
# (3*y, (x,))

(3*y).as_coeff_mul(x)
# (3*y, ())
```

---

## 4.6.3 `.as_numer_denom()`

```python
num, den = expr.as_numer_denom()
```

Returns numerator and denominator components. Docs show direct decomposition such as `(x*y/z).as_numer_denom() -> (x*y, z)`. ([SymPy Documentation][2])

```python
(x*y/z).as_numer_denom()
# (x*y, z)

(x*(y + 1)/y**7).as_numer_denom()
# (x*(y + 1), y**7)
```

Use after `together()` or `cancel()` if a normalized numerator/denominator contract is needed.

---

## 4.6.4 `.coeff(x, n=1, right=False)`

```python
expr.coeff(x)
expr.coeff(x, n)
expr.coeff(x, 0)
expr.coeff(noncomm_symbol, right=True)
```

`.coeff(x, n)` returns the coefficient from terms containing `x**n`; `n=0` returns terms independent of `x`. Matching is exact and no factoring is done; docs show that `(z*(x + y)**2).coeff(x + y)` returns `0` while `.coeff((x + y)**2)` returns `z`. ([SymPy Documentation][2])

```python
expr = 3 + 2*x + 4*x**2

expr.coeff(x)
# 2

expr.coeff(x, 2)
# 4

expr.coeff(x, 0)
# 3

(z*(x + y)**2).coeff((x + y)**2)
# z

(z*(x + y)**2).coeff(x + y)
# 0
```

If factoring is desired before coefficient extraction:

```python
expr = x + z*(x + x*y)

expr.coeff(x)
# 1

sp.factor_terms(expr).coeff(x)
# z*(y + 1) + 1
```

### Deployment guidance

```text
Use coeff for exact structural coefficient extraction.
Use collect(...).coeff(...) for polynomial-like coefficient extraction.
Use Poly(expr, x).coeff_monomial(...) for strict polynomial workflows.
Use factor_terms before coeff if hidden common factors must be exposed.
```

---

## 4.7 Pattern matching: `.match()`, `Wild`, replacement rules

## 4.7.1 `.match(pattern, old=False)`

```python
expr.match(pattern)
expr.match(pattern, old=True)
```

`.match()` performs structural pattern matching. It returns `None` on failure or a dictionary such that `pattern.xreplace(expr.match(pattern)) == expr`. It is purely structural; expressions equivalent up to bound-symbol renaming do not necessarily match. ([SymPy Documentation][2])

```python
p = sp.Wild("p")
q = sp.Wild("q")
r = sp.Wild("r")

e = (x + y)**(x + y)

e.match(p**p)
# {p_: x + y}

e.match(p**q)
# {p_: x + y, q_: x + y}

e = (2*x)**2
m = e.match(p*q**r)
# {p_: 4, q_: x, r_: 2}

(p*q**r).xreplace(m)
# 4*x**2
```

### `old=True`

```python
(x - 2).match(p - x, old=True)
# {p_: 2*x - 2}

(2/x).match(p*x, old=True)
# {p_: 2/x**2}
```

Use `old=True` only when solver-like matching is explicitly intended; production rewrite rules should prefer precise structural patterns.

---

## 4.7.2 `Wild(name, exclude=(), properties=())`

```python
a = sp.Wild("a")
b = sp.Wild("b", exclude=[x, y])
n = sp.Wild("n", properties=[lambda k: k.is_Integer])
```

`Wild` matches arbitrary expressions, optionally excluding expressions or enforcing predicate properties. Docs warn that unconstrained `Wild` patterns can technically match expressions agents likely did not intend; `exclude` improves precision and removes ambiguity. ([SymPy Documentation][2])

```python
a, b = sp.symbols("a b", cls=sp.Wild)

(2 + 3*y).match(a*x + b*y)
# {a_: 2/x, b_: 3}   # technically valid, often unwanted

a = sp.Wild("a", exclude=[x, y])
b = sp.Wild("b", exclude=[x, y])

(2 + 3*y).match(a*x + b*y)
# None
```

### Property-constrained match

```python
n = sp.Wild("n", properties=[lambda k: k.is_Integer])
E = 2*x**3*y*z

E.match(n * b)
# n_ matches integer 2 if b is unconstrained
```

### Deployment guidance

```text
Pattern rewrite rule hygiene:
  - constrain Wild with exclude;
  - constrain numeric/domain matches with properties;
  - assert match is not None before xreplace;
  - unit-test non-matches, not only matches;
  - avoid broad patterns on canonicalized Add/Mul without checking output.
```

---

## 4.8 Traversal, structure rendering, and operation counting

## 4.8.1 `srepr(expr)`

`srepr()` emits the internal constructor-style representation of an expression tree. The expression-manipulation tutorial shows `x**2 + x*y` as `Add(Pow(Symbol('x'), Integer(2)), Mul(Symbol('x'), Symbol('y')))`. ([SymPy Documentation][5])

```python
expr = x**2 + x*y

sp.srepr(expr)
# "Add(Pow(Symbol('x'), Integer(2)), Mul(Symbol('x'), Symbol('y')))"
```

Use cases:

```text
debug rewrite mismatch
detect hidden Float/Rational/Integer nodes
snapshot internal structure
teach/inspect expression tree shape
```

---

## 4.8.2 `preorder_traversal(node, keys=None)`

```python
from sympy import preorder_traversal

list(preorder_traversal(expr))
list(preorder_traversal(expr, keys=True))
```

Preorder traversal yields current node first, then descendants. Traversal order depends on `.args`; passing `keys=True` gives deterministic ordering using default ordering keys. ([SymPy Documentation][2])

```python
for node in sp.preorder_traversal((x + y)*z, keys=True):
    ...
```

Use for:

```text
top-down analysis
early pruning
detect first matching node
collect structural features
```

---

## 4.8.3 `postorder_traversal(node, keys=None)`

```python
from sympy import postorder_traversal

list(postorder_traversal(expr))
list(postorder_traversal(expr, keys=True))
```

Postorder traversal yields children before parent. Docs state `keys=True` guarantees unique traversal ordering. ([SymPy Documentation][2])

Use for:

```text
bottom-up rewrite construction
child-derived annotations
manual rebuild transforms
normalization passes
```

---

## 4.8.4 `bottom_up(expr, F, atoms=False, nonbasic=False)`

```python
from sympy.core.traversal import bottom_up

bottom_up(expr, lambda e: ...)
```

`bottom_up` applies a function to nodes from leaves toward the root; `atoms=True` applies to atoms too; `nonbasic=True` attempts non-`Basic` objects. ([SymPy Documentation][2])

```python
from sympy.core.traversal import bottom_up

def square_integers(e):
    if e.is_Integer:
        return e**2
    return e

bottom_up(expr, square_integers, atoms=True)
```

---

## 4.8.5 `count_ops(expr, visual=False)`

```python
sp.count_ops(expr)
sp.count_ops(expr, visual=True)
expr.count_ops(visual=True)
```

`count_ops()` returns either an integer operation count or a symbolic visual expression of operation types. It handles expressions and iterables; docs show `visual=True` distinguishes operations such as `ADD`, `MUL`, `POW`, and `SIN`. ([SymPy Documentation][2])

```python
expr = sp.sin(x)*x + sp.sin(x)**2

sp.count_ops(expr)
# 5

sp.count_ops(expr, visual=True)
# ADD + MUL + POW + 2*SIN
```

Use for:

```text
expression-size heuristic
rewrite acceptance criterion
codegen cost proxy
simplification regression metrics
CSE-before/after diagnostics
```

---

## 4.9 Normalization strategies

## 4.9.1 General production rule

```text
Never normalize with blind simplify() as a default.
Choose a normal form based on downstream consumer:
  polynomial solver → expand/factor/Poly
  rational equality → together/cancel
  coefficient extraction → collect/coeff/Poly
  trig identity analysis → expand_trig/trigsimp/fu
  codegen → cancel/together/cse/count_ops
```

SymPy docs explicitly recommend specific simplification functions when the desired transformation is known, because targeted functions have clearer guarantees than `simplify()`. ([SymPy Documentation][3])

---

## 4.9.2 Rational canonical form

```python
def rational_canonical(expr: sp.Expr) -> sp.Expr:
    expr = sp.sympify(expr)
    return sp.cancel(sp.together(expr))
```

Use for:

```text
rational expression equality
denominator/numerator inspection
stable symbolic regression tests
pre-codegen removable-factor elimination
```

Validation:

```python
num, den = rational_canonical(expr).as_numer_denom()
```

---

## 4.9.3 Polynomial expanded form

```python
def polynomial_expanded(expr: sp.Expr, *gens: sp.Symbol) -> sp.Expr:
    expr = sp.sympify(expr)
    expr = sp.expand(expr)
    if gens and not expr.is_polynomial(*gens):
        raise ValueError("not polynomial in requested generators")
    return expr
```

Use for:

```text
monomial coefficient extraction
term enumeration
polynomial equality via structural equality
Poly conversion
```

---

## 4.9.4 Polynomial factored form

```python
def polynomial_factored(expr: sp.Expr, *gens: sp.Symbol) -> sp.Expr:
    expr = sp.sympify(expr)
    return sp.factor(expr, *gens)
```

Use for:

```text
root structure
symbolic cancellation candidates
human-readable factored output
solver preprocessing
```

---

## 4.9.5 Coefficient dictionary form

```python
def coefficient_map(expr: sp.Expr, x: sp.Symbol) -> dict[sp.Expr, sp.Expr]:
    expr = sp.collect(sp.expand(expr), x, evaluate=False)
    return dict(expr)
```

Alternative strict polynomial path:

```python
def poly_coeffs(expr: sp.Expr, x: sp.Symbol) -> dict[tuple[int, ...], sp.Expr]:
    P = sp.Poly(expr, x)
    return dict(zip(P.monoms(), P.coeffs()))
```

Use `Poly` when polynomial-ness is a contract, not a hope.

---

## 4.9.6 Source-faithful structural replacement

```python
def exact_node_rewrite(expr: sp.Basic, mapping: dict[sp.Basic, sp.Basic]) -> sp.Basic:
    return sp.sympify(expr).xreplace(mapping)
```

Use for:

```text
CSE symbol replacement
AST-level generated-variable substitution
temporary marker replacement
no algebraic matching
```

---

## 4.9.7 Pattern rewrite with guarded `Wild`

```python
A = sp.Wild("A", exclude=[x])
pattern = A*x + A

def rewrite_Ax_plus_A(expr: sp.Expr) -> sp.Expr:
    m = expr.match(pattern)
    if m is None:
        return expr
    return A.xreplace(m) * (x + 1)
```

Better with `.replace()` for recursive application:

```python
A = sp.Wild("A", exclude=[x])
expr.replace(A*x + A, A*(x + 1))
```

Guardrail: unit-test intended non-matches.

---

## 4.9.8 Cost-aware rewrite acceptance

```python
def accept_if_cheaper(old: sp.Expr, new: sp.Expr) -> sp.Expr:
    old_cost = sp.count_ops(old)
    new_cost = sp.count_ops(new)
    return new if new_cost <= old_cost else old
```

Use for:

```text
auto-simplification pipelines
rewrite search
codegen pre-optimization
LLM-generated transform validation
```

---

## 4.10 Deployment recipes

## Recipe A — safe substitution boundary

```python
def specialize(
    expr: sp.Expr,
    substitutions: dict[sp.Symbol, sp.Expr | int | float],
    *,
    exact_numeric: bool = True,
) -> sp.Expr:
    expr = sp.sympify(expr)

    if exact_numeric:
        substitutions = {
            k: sp.sympify(v) if not isinstance(v, float) else sp.Float(v)
            for k, v in substitutions.items()
        }

    return expr.subs(substitutions, simultaneous=True)
```

Use `simultaneous=True` when replacement dependencies might cross-contaminate.

---

## Recipe B — exact DAG rewrite after `.match()`

```python
def rewrite_power(expr: sp.Expr) -> sp.Expr:
    p = sp.Wild("p")
    q = sp.Wild("q")

    m = expr.match(p**q)
    if m is None:
        return expr

    # Rebuild from match dictionary with xreplace, preserving exact matched nodes.
    return sp.Function("PowNode")(m[p], m[q])
```

---

## Recipe C — rational equality predicate

```python
def rational_equal(a: sp.Expr, b: sp.Expr) -> bool:
    diff = sp.cancel(sp.together(sp.sympify(a) - sp.sympify(b)))
    return diff == 0
```

Works best for rational functions; do not silently apply to branch-cut-sensitive transcendental equivalence.

---

## Recipe D — coefficient extraction pipeline

```python
def coeff(expr: sp.Expr, x: sp.Symbol, n: int) -> sp.Expr:
    expr = sp.collect(sp.expand(sp.sympify(expr)), x)
    return expr.coeff(x, n)
```

For strict polynomial systems:

```python
def poly_coeff(expr: sp.Expr, x: sp.Symbol, n: int) -> sp.Expr:
    return sp.Poly(expr, x).coeff_monomial(x**n)
```

---

## Recipe E — controlled expansion profile

```python
def expand_for_polynomial_collection(expr: sp.Expr) -> sp.Expr:
    return sp.expand(expr, log=False, trig=False, func=False, complex=False)

def expand_for_trig_identities(expr: sp.Expr) -> sp.Expr:
    return sp.expand_trig(expr)

def expand_for_complex_parts(expr: sp.Expr) -> sp.Expr:
    return sp.expand_complex(expr)
```

---

## Recipe F — codegen-prep normalization

```python
def prepare_for_codegen(expr: sp.Expr) -> sp.Expr:
    expr = sp.sympify(expr)

    # combine rational fragments without gratuitous expansion
    expr = sp.together(expr)

    # remove common rational factors
    expr = sp.cancel(expr)

    # optional factor for smaller generated code; accept only if cheaper
    factored = sp.factor(expr)
    if sp.count_ops(factored) <= sp.count_ops(expr):
        expr = factored

    return expr
```

---

## Recipe G — rewrite audit record

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class RewriteAudit:
    before: sp.Expr
    after: sp.Expr
    before_srepr: str
    after_srepr: str
    before_ops: int
    after_ops: int
    changed: bool

def audit_rewrite(expr: sp.Expr, fn) -> RewriteAudit:
    before = sp.sympify(expr)
    after = fn(before)
    return RewriteAudit(
        before=before,
        after=after,
        before_srepr=sp.srepr(before),
        after_srepr=sp.srepr(after),
        before_ops=sp.count_ops(before),
        after_ops=sp.count_ops(after),
        changed=(before != after),
    )
```

---

## 4.11 Failure-mode matrix

| Failure mode                                                | Symptom                                  | Correct primitive                               |
| ----------------------------------------------------------- | ---------------------------------------- | ----------------------------------------------- |
| `.subs(x**2, y)` rewrites `x**4` too                        | `x**4 -> y**2`                           | `.xreplace({x**2: y})`                          |
| `.xreplace()` rewrites bound variable                       | invalid integral/sum limits              | `.subs()` or alpha-rename with `Dummy`          |
| broad `.replace()` predicate mutates nested nodes twice     | unexpected expression growth             | use exact query or `map=True` audit             |
| unconstrained `Wild` overmatches                            | match includes `2/x` or unwanted symbols | `Wild(..., exclude=[...])`                      |
| `.coeff()` misses hidden factor                             | returns `1` not full coefficient         | `factor_terms()` or `collect()` first           |
| full `expand()` explodes expression                         | huge tree / slow codegen                 | hint-specific `expand_mul`, `expand_trig`, etc. |
| `expand_log(..., force=True)` invalid under complex domains | branch errors                            | require positive/real assumptions               |
| `evalf()` after early `Float` gives false precision         | many digits, poor accuracy               | keep exact until numeric boundary               |
| `together()` not fully reduced                              | common factors remain                    | `cancel(together(expr))`                        |
| `apart()` returns `RootSum`                                 | non-rational roots / full decomposition  | `.doit()` or specify extension/domain strategy  |
| traversal order unstable                                    | nondeterministic rewrite output          | `keys=True`                                     |
| `simplify()` output unstable                                | tests/codegen drift                      | targeted normalization pipeline                 |

---

## 4.12 Minimal manipulation harness

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping

import sympy as sp


@dataclass(frozen=True)
class NormalForms:
    original: sp.Expr
    expanded: sp.Expr
    factored: sp.Expr
    togethered: sp.Expr
    canceled: sp.Expr
    rational_canonical: sp.Expr
    operation_count: int
    srepr: str


def normal_forms(expr: sp.Expr) -> NormalForms:
    expr = sp.sympify(expr)

    togethered = sp.together(expr)
    canceled = sp.cancel(expr)
    rational_canonical = sp.cancel(togethered)

    return NormalForms(
        original=expr,
        expanded=sp.expand(expr),
        factored=sp.factor(expr),
        togethered=togethered,
        canceled=canceled,
        rational_canonical=rational_canonical,
        operation_count=sp.count_ops(expr),
        srepr=sp.srepr(expr),
    )


def exact_replace(expr: sp.Basic, mapping: Mapping[sp.Basic, sp.Basic]) -> sp.Basic:
    return sp.sympify(expr).xreplace(dict(mapping))


def semantic_substitute(
    expr: sp.Expr,
    substitutions: Mapping[sp.Basic, sp.Basic],
    *,
    simultaneous: bool = True,
) -> sp.Expr:
    return sp.sympify(expr).subs(dict(substitutions), simultaneous=simultaneous)


def rational_canonical(expr: sp.Expr) -> sp.Expr:
    return sp.cancel(sp.together(sp.sympify(expr)))


def rational_equal(a: sp.Expr, b: sp.Expr) -> bool:
    return rational_canonical(sp.sympify(a) - sp.sympify(b)) == 0


def coefficient(expr: sp.Expr, x: sp.Symbol, n: int) -> sp.Expr:
    return sp.collect(sp.expand(sp.sympify(expr)), x).coeff(x, n)


def safe_expand(expr: sp.Expr, *, profile: str = "algebra") -> sp.Expr:
    expr = sp.sympify(expr)

    if profile == "algebra":
        return sp.expand(expr, log=False, trig=False, func=False, complex=False)
    if profile == "trig":
        return sp.expand_trig(expr)
    if profile == "log":
        return sp.expand_log(expr)
    if profile == "func":
        return sp.expand_func(expr)
    if profile == "complex":
        return sp.expand_complex(expr)

    raise ValueError(f"unknown expansion profile: {profile}")


def cost_guard(expr: sp.Expr, transform: Callable[[sp.Expr], sp.Expr]) -> sp.Expr:
    expr = sp.sympify(expr)
    candidate = transform(expr)
    return candidate if sp.count_ops(candidate) <= sp.count_ops(expr) else expr


def traverse_nodes(expr: sp.Basic, *, order: str = "pre", deterministic: bool = True) -> tuple[sp.Basic, ...]:
    keys = True if deterministic else None
    if order == "pre":
        return tuple(sp.preorder_traversal(expr, keys=keys))
    if order == "post":
        return tuple(sp.postorder_traversal(expr, keys=keys))
    raise ValueError("order must be 'pre' or 'post'")
```

This harness encodes the section’s deployment policy: exact vs semantic replacement separation, targeted expansion, rational canonicalization, coefficient extraction after normalization, cost-aware transforms, deterministic traversal, and debug-friendly structural output.

[1]: https://docs.sympy.org/latest/explanation/best-practices.html "Best Practices - SymPy 1.14.0 documentation"
[2]: https://docs.sympy.org/latest/modules/core.html "Core - SymPy 1.14.0 documentation"
[3]: https://docs.sympy.org/latest/tutorials/intro-tutorial/simplification.html "Simplification - SymPy 1.14.0 documentation"
[4]: https://docs.sympy.org/latest/modules/polys/reference.html "Polynomials Manipulation Module Reference - SymPy 1.14.0 documentation"
[5]: https://docs.sympy.org/latest/tutorials/intro-tutorial/manipulation.html "Advanced Expression Manipulation - SymPy 1.14.0 documentation"

# 5) Simplification strategy and expression rewriting — agent-ready deep dive

Continuing the same advanced technical-doc structure as the uploaded reference template. 

## 5.0 Simplification contract

SymPy simplification is not a single canonical operation. It is a family of **targeted transforms** over immutable expression trees: rational normalization, factorization, trig identity reduction, logarithm combination, power denesting, radical rationalization, combinatorial simplification, hypergeometric expansion, and structural rewriting. The general `simplify()` function is heuristic: it tries many transformations, measures candidate complexity, and returns a selected result; docs explicitly state that “simplest” is not well-defined, `simplify()` may miss known simplifications, may be unnecessarily slow, and gives no output-form guarantee. ([docs.sympy.org][1])

```python
import sympy as sp

x, y, z = sp.symbols("x y z")
```

Core production rule:

```text
Interactive exploration:
  simplify(expr)

Production pipeline:
  targeted_transform_1(expr)
  → targeted_transform_2(expr)
  → cost_guard(...)
  → output-shape assertion
```

---

## 5.1 Automatic simplification vs manual simplification

Automatic simplification happens inside constructors, for example `x + x -> 2*x` in `Add`. SymPy’s glossary explicitly discourages excessive automatic simplification because it can make unsimplified forms unrepresentable without `evaluate=False` and can make constructors expensive; manual simplification/canonicalization is preferred for nontrivial transformations. ([docs.sympy.org][2])

```python
x + x
# 2*x

sp.Add(x, x, evaluate=False)
# x + x
```

Deployment interpretation:

```text
automatic simplification:
  constructor-level canonicalization
  cheap, local, usually unavoidable unless evaluate=False

manual simplification:
  explicit API call
  domain-sensitive
  potentially expensive
  should be selected by target form
```

Agent guardrail:

```python
def no_auto_eval_add(*terms):
    return sp.Add(*(sp.sympify(t) for t in terms), evaluate=False)
```

Use `evaluate=False` for source-faithful rendering, pedagogical steps, parsers, rule-debugging, and proof traces; do not assume it survives later algebraic combination.

---

## 5.2 `simplify()` — catchall heuristic

## 5.2.1 API surface

```python
sp.simplify(expr, ratio=1.7, measure=sp.count_ops, rational=False, inverse=False, doit=True)
expr.simplify(**kwargs)
```

`ratio` bounds expression growth: if `(result length)/(input length) > ratio`, the input is returned. The default measure is `count_ops()`. `ratio=1` prevents longer output; `ratio=oo` allows growth. `measure` can be customized. `rational=True` recasts floats as rationals before simplification; `rational=None` recasts floats to rationals internally then recasts result to floats; `inverse=True` permits inverse-function cancellations such as `asin(sin(x)) -> x` without checking domain validity. `simplify()` also calls `doit()` on the final expression unless `doit=False`. ([docs.sympy.org][3])

```python
expr = (x + x**2)/(x*sp.sin(y)**2 + x*sp.cos(y)**2)

sp.simplify(expr)
# x + 1

sp.trigsimp(expr)
# (x**2 + x)/x

sp.cancel(sp.trigsimp(expr))
# x + 1
```

The docs show this exact pattern to demonstrate that a `simplify()` result can often be reproduced by a known targeted sequence such as `trigsimp()` followed by `cancel()`. ([docs.sympy.org][3])

---

## 5.2.2 When to use `simplify()`

```text
Use simplify() when:
  - exploratory / notebook workflow;
  - expression structure unknown;
  - broad catchall needed;
  - final human-readable preview;
  - output shape is not contractual.

Avoid simplify() when:
  - codegen output shape matters;
  - coefficient extraction follows;
  - rational denominator/numerator contract needed;
  - runtime latency matters;
  - tests depend on exact form;
  - branch-cut/domain correctness must be explicit.
```

SymPy’s tutorial says `simplify()` is best for interactive use or when expression form is unknown, but targeted functions are better when the desired simplification class is known because targeted functions have clearer guarantees. ([docs.sympy.org][1])

---

## 5.2.3 Custom measure example

```python
def penalize_powers(expr):
    POW = sp.Symbol("POW")
    score = sp.count_ops(expr, visual=True).subs(POW, 10)
    score = score.replace(sp.Symbol, type(sp.S.One))
    return score

g = sp.log(x) + sp.log(y) + sp.log(x)*sp.log(1/y)

candidate = sp.simplify(g, measure=penalize_powers)
```

The official docs show `count_ops(..., visual=True)` being used to weight operation classes differently, e.g. penalizing `POW`, because the default operation count may prefer a shorter expression that is visually or computationally undesirable. ([docs.sympy.org][3])

---

## 5.3 Targeted simplification map

| Target form                         |                         Primary function | Value case                                                    |
| ----------------------------------- | ---------------------------------------: | ------------------------------------------------------------- |
| polynomial factor form              |                                 `factor` | roots, human-readable algebra, exact factorization            |
| rational reduced form               |                                 `cancel` | canonical rational equality, denominator/numerator extraction |
| common denominator                  |                    `together`, `ratsimp` | rational aggregation, later `cancel`/`apart`                  |
| partial fractions                   |                                  `apart` | integration, residues, rational decomposition                 |
| trig/hyperbolic identity reduction  |                               `trigsimp` | compact trig/hyperbolic forms                                 |
| power combination                   |                                `powsimp` | combine bases/exponents where valid                           |
| power denesting                     |                              `powdenest` | flatten nested powers/log-exp forms                           |
| radical denominator rationalization |                                `radsimp` | remove radicals from denominators                             |
| nested sqrt simplification          |                             `sqrtdenest` | denest square roots where possible                            |
| logarithm combination               |                             `logcombine` | combine sums of logs into single logs                         |
| combinatorial simplification        |                               `combsimp` | factorial/binomial/Pochhammer reduction                       |
| gamma simplification                |                              `gammasimp` | gamma-function identities                                     |
| special-function rewrite            | `.rewrite`, `expand_func`, `hyperexpand` | convert function families                                     |
| common subexpression extraction     |                                    `cse` | generated-code size/runtime reduction                         |
| cost measurement                    |                              `count_ops` | expression swell guard                                        |

---

## 5.4 Rational and polynomial simplification

## 5.4.1 `factor(expr, *gens, **opts)`

```python
sp.factor(expr)
sp.factor(expr, x)
sp.factor(expr, modulus=2)
sp.factor(expr, extension=sp.sqrt(2))
sp.factor(expr, gaussian=True)
```

Use `factor()` for polynomial factorization and algebraic structure exposure. SymPy’s tutorial states that for polynomials with rational coefficients, `factor()` is guaranteed to factor into irreducible factors, while `simplify()` has no such output guarantee. ([docs.sympy.org][1])

```python
sp.factor(x**3 - x**2 + x - 1)
# (x - 1)*(x**2 + 1)

sp.factor(x**2 + 1, modulus=2)
# (x + 1)**2

sp.factor(x**2 - 2, extension=sp.sqrt(2))
# (x - sqrt(2))*(x + sqrt(2))
```

Structured output:

```python
coeff, factors = sp.factor_list(x**2*z + 4*x*y*z + 4*y**2*z)
# coeff = 1
# factors = [(z, 1), (x + 2*y, 2)]
```

Deployment rule:

```text
Use factor when downstream wants multiplicative structure.
Do not use factor when downstream wants expanded coefficients.
Prefer factor_list for machine consumption.
```

---

## 5.4.2 `cancel(expr)`

```python
sp.cancel(expr)
expr.cancel()
```

`cancel()` reduces rational functions to canonical numerator/denominator form. In the simplification tutorial, `cancel()` is recommended when the goal is rational cancellation because it is more direct than factorization for that purpose. ([docs.sympy.org][4])

```python
expr = (x**2 + 2*x + 1)/(x**2 + x)

sp.cancel(expr)
# (x + 1)/x
```

Canonical rational equality:

```python
def rational_canonical(expr):
    return sp.cancel(sp.together(sp.sympify(expr)))

def rational_equal(a, b):
    return rational_canonical(sp.sympify(a) - sp.sympify(b)) == 0
```

---

## 5.4.3 `together(expr)`, `ratsimp(expr)`, `apart(expr)`

```python
sp.together(1/x + 1/y)
# (x + y)/(x*y)

sp.ratsimp(1/x + 1/y)
# (x + y)/(x*y)

sp.apart((x + 1)/(x*(x - 1)), x)
```

`ratsimp()` puts an expression over a common denominator, cancels, and reduces. `ratsimpmodprime()` can simplify rational expressions modulo a prime ideal generated by a Groebner basis; its `polynomial=True` path is faster but may produce worse results. ([docs.sympy.org][3])

Rational deployment profiles:

```python
def common_denominator_form(expr):
    return sp.together(sp.sympify(expr))

def reduced_rational_form(expr):
    return sp.cancel(sp.together(sp.sympify(expr)))

def partial_fraction_form(expr, x):
    return sp.apart(sp.cancel(sp.together(expr)), x)
```

---

## 5.5 Trigonometric simplification

## 5.5.1 `trigsimp(expr, inverse=False, **opts)`

```python
sp.trigsimp(expr)
sp.trigsimp(expr, method="matching")
sp.trigsimp(expr, method="groebner")
sp.trigsimp(expr, method="combined")
sp.trigsimp(expr, method="fu")
sp.trigsimp(expr, method="old")
sp.trigsimp(expr, inverse=True)
```

`trigsimp()` returns a reduced expression using known trig identities. It simplifies recursively wherever trig functions occur, including inside other functions. Methods include pattern matching, experimental Groebner-basis simplification, combined mode, Fu transformations, and the old routine. `inverse=True` permits inverse-composition cancellation without verifying the input is in a valid domain; docs warn that this can cancel `asin(sin(x))` to `x` without checking domain membership. ([docs.sympy.org][3])

```python
e = 2*sp.sin(x)**2 + 2*sp.cos(x)**2

sp.trigsimp(e)
# 2

sp.trigsimp(sp.log(e))
# log(2)
```

Method escalation:

```python
def trig_reduce(expr):
    expr = sp.sympify(expr)

    # cheap/default first
    a = sp.trigsimp(expr)

    # optionally try a heavier method only if expression still contains trig
    if a.has(sp.sin, sp.cos, sp.tan, sp.sinh, sp.cosh, sp.tanh):
        b = sp.trigsimp(a, method="fu")
        return b if sp.count_ops(b) <= sp.count_ops(a) else a

    return a
```

Deployment rule:

```text
Default method:
  production-safe baseline.

method="groebner"/"combined":
  try for difficult trig-polynomial identities;
  cost-guard output.

method="fu":
  powerful trig transformation family;
  cost-guard and regression-test exact output.

inverse=True:
  use only when domain preconditions are guaranteed externally.
```

---

## 5.5.2 Expansion vs reduction

```python
sp.expand_trig(sp.sin(x + y))
# sin(x)*cos(y) + sin(y)*cos(x)

sp.trigsimp(sp.sin(x)*sp.cos(y) + sp.sin(y)*sp.cos(x))
# sin(x + y)
```

The simplification tutorial notes that `expand_trig()` tends to make trig expressions larger, while `trigsimp()` tends to make them smaller and can apply identities in the reverse direction. ([docs.sympy.org][5])

Pipeline pattern:

```python
def normalize_trig_for_matching(expr):
    return sp.expand_trig(expr)

def normalize_trig_for_output(expr):
    return sp.trigsimp(expr)
```

---

## 5.6 Power simplification

## 5.6.1 `powsimp(expr, deep=False, combine="all", force=False, measure=count_ops)`

```python
sp.powsimp(expr)
sp.powsimp(expr, deep=True)
sp.powsimp(expr, combine="exp")
sp.powsimp(expr, combine="base", force=True)
sp.powsimp(expr, combine="all", force=True)
```

`powsimp()` reduces expressions by combining powers with similar bases and exponents. `deep=True` also simplifies inside function arguments. `combine="exp"` combines exponents, `combine="base"` combines bases, and `combine="all"` does both with exponent-combination first. `force=True` combines bases without checking assumptions, e.g. `sqrt(x)*sqrt(y) -> sqrt(x*y)`, which is not valid if both variables are negative. ([docs.sympy.org][3])

```python
sp.powsimp(x**y * x**z * y**z, combine="all")
# x**(y + z)*y**z

sp.powsimp(x**y * x**z * y**z, combine="base", force=True)
# x**y*(x*y)**z
```

Deep behavior:

```python
xp, yp = sp.symbols("xp yp", positive=True)

sp.powsimp(sp.log(sp.exp(xp)*sp.exp(yp)))
# log(exp(xp)*exp(yp))

sp.powsimp(sp.log(sp.exp(xp)*sp.exp(yp)), deep=True)
# xp + yp
```

The docs show this exact `deep=True` distinction for simplifying inside `log(exp(x)*exp(y))`. ([docs.sympy.org][3])

Deployment rule:

```text
combine="exp":
  safer default; combine x**a*x**b.

combine="base":
  requires stronger assumptions; use force only with external domain proof.

deep=True:
  changes function arguments; use when inner-expression normalization is desired.

force=True:
  codegen/domain-sensitive; document preconditions.
```

---

## 5.6.2 `powdenest(eq, force=False, polar=False)`

```python
sp.powdenest(expr)
sp.powdenest(expr, force=True)
sp.powdenest(expr, polar=True)
```

`powdenest()` collects exponents on powers when assumptions allow. For `(bb**be)**e`, it can simplify to `bb**(be*e)` when the base is positive, the outer exponent is integer, or `abs(be) < 1`. `force=True` treats symbols not explicitly negative as positive, causing more denesting; `polar=True` performs simplifications on the Riemann surface of the logarithm. ([docs.sympy.org][3])

```python
sp.powdenest((x**(2*y/3))**(3*x))
# unchanged

sp.powdenest(sp.exp(3*x*sp.log(2)))
# 2**(3*x)

p = sp.symbols("p", positive=True)
sp.powdenest(sp.sqrt(p**2))
# p
```

Log-exp collapse examples:

```python
sp.powdenest(sp.exp(3*y*sp.log(x)))
# x**(3*y)

sp.powdenest(sp.exp(y*(sp.log(x) + sp.log(z))))
# (x*z)**y
```

Docs state `powdenest()` does no other expansion beyond its denesting behavior; use it as a narrow transform, not as a general simplifier. ([docs.sympy.org][3])

---

## 5.7 Logarithmic simplification

## 5.7.1 `logcombine(expr, force=False)`

```python
sp.logcombine(expr)
sp.logcombine(expr, force=True)
```

`logcombine()` combines logarithms using `log(x)+log(y)=log(x*y)` when both arguments are positive, and `a*log(x)=log(x**a)` when `x` is positive and `a` is real. With `force=True`, missing assumptions are treated as if valid unless existing assumptions contradict the transformation. ([docs.sympy.org][3])

```python
a = sp.Symbol("a")
x, y, z = sp.symbols("x y z")

sp.logcombine(a*sp.log(x) + sp.log(y) - sp.log(z))
# unchanged

sp.logcombine(a*sp.log(x) + sp.log(y) - sp.log(z), force=True)
# log(x**a*y/z)
```

Assumption-safe form:

```python
xp, yp, zp = sp.symbols("xp yp zp", positive=True)
ar = sp.Symbol("a", real=True)

sp.logcombine(ar*sp.log(xp) + sp.log(yp) - sp.log(zp))
# log(xp**a*yp/zp)
```

The docs note that `logcombine()` only acts on factors/terms containing logs, so the result depends on the initial expansion state; for example, expanding a complex coefficient can expose terms that are then combined differently. ([docs.sympy.org][3])

Deployment rule:

```text
Use logcombine when:
  - all log arguments are positive or domain-preconditioned;
  - log-expression compactness matters;
  - preparing exponent/log algebra.

Avoid force=True unless:
  - deployment domain guarantees positivity/realness;
  - transformation is guarded by assumptions or tests.
```

---

## 5.7.2 `expand_log(...)` as inverse direction

```python
sp.expand_log(sp.log(xp*yp**2))
# log(xp) + 2*log(yp)

sp.expand_log(sp.log(x*y**2), force=True)
```

`expand_log()` is the opposite directional transform of `logcombine()`, expanding logarithms of products and powers under assumptions or force. The `logcombine()` docs explicitly reference `expand_log` as the opposite operation. ([docs.sympy.org][3])

---

## 5.8 Radical simplification

## 5.8.1 `radsimp(expr, symbolic=True, max_terms=4)`

```python
sp.radsimp(expr)
sp.radsimp(expr, symbolic=False)
sp.radsimp(expr, max_terms=8)
```

`radsimp()` rationalizes denominators by removing square roots. The docs warn that symbolic denominators require caution: transformed results can become invalid under later substitutions that violate assumptions used during rationalization, and `symbolic=False` disables transformation for symbolic denominators while still processing numeric denominators. If more than `max_terms` radical terms appear, the expression is returned unchanged. ([docs.sympy.org][3])

```python
sp.radsimp(1/(2 + sp.sqrt(2)))
# (2 - sqrt(2))/2

a, b, c = sp.symbols("a b c")
eq = 1/(a + b*sp.sqrt(c))

sp.radsimp(eq)
# transformed, but substitution-sensitive

sp.radsimp(eq, symbolic=False)
# 1/(a + b*sqrt(c))
```

Substitution hazard shown in docs:

```python
eq = 1/(a + b*sp.sqrt(c))

eq.subs(a, b*sp.sqrt(c))
# 1/(2*b*sqrt(c))

sp.radsimp(eq).subs(a, b*sp.sqrt(c))
# nan
```

Use `symbolic=False` for production pipelines unless symbolic denominator non-vanishing constraints are explicitly tracked. ([docs.sympy.org][3])

---

## 5.8.2 `sqrtdenest(expr, max_iter=3)`

```python
from sympy.simplify.sqrtdenest import sqrtdenest

sqrtdenest(sp.sqrt(5 + 2*sp.sqrt(6)))
# sqrt(2) + sqrt(3)
```

`sqrtdenest()` denests nested square roots when possible and returns the original expression unchanged otherwise. ([docs.sympy.org][3])

Deployment rule:

```text
Use sqrtdenest for nested radical readability.
Use radsimp for denominator rationalization.
Use cost guards because radical “simpler” is presentation-dependent.
```

---

## 5.9 Combinatorial and gamma simplification

## 5.9.1 `combsimp(expr)`

```python
from sympy.simplify import combsimp

n, k = sp.symbols("n k", integer=True)

combsimp(sp.factorial(n)/sp.factorial(n - 3))
# n*(n - 2)*(n - 1)

combsimp(sp.binomial(n + 1, k + 1)/sp.binomial(n, k))
# (n + 1)/(k + 1)
```

`combsimp()` simplifies expressions containing factorials, binomials, Pochhammer symbols, and related combinatorial functions. Docs state it rewrites combinatorial functions as gamma functions, applies `gammasimp()` except for steps that may make integer arguments non-integer, then rewrites back toward factorials/binomials. If gamma or combinatorial functions have non-integer arguments, the expression is automatically passed to `gammasimp()`. ([docs.sympy.org][3])

Deployment rule:

```text
Use combsimp when:
  - factorial/binomial/Pochhammer terms dominate;
  - symbols have integer assumptions;
  - output should preserve combinatorial notation when possible.

Use gammasimp when:
  - gamma-function expression is primary;
  - non-integer arguments dominate;
  - analytic continuation identities are desired.
```

---

## 5.10 Function rewriting

## 5.10.1 `.rewrite(rule)` and `.rewrite(pattern, rule)`

```python
expr.rewrite(sp.exp)
expr.rewrite(sp.sin, sp.exp)
expr.rewrite([sp.sin, sp.cos], sp.exp)
expr.rewrite(sp.gamma)
expr.rewrite(sp.factorial)
```

`.rewrite()` transforms an expression to a mathematically equivalent but structurally different form. If the pattern is omitted, all possible expressions are considered; otherwise the pattern can be a type or iterable of types. Docs give examples rewriting `cos(x)+I*sin(x)` to `exp(I*x)` and selectively rewriting only `sin` or only `cos`. Custom classes should implement `_eval_rewrite`; `_eval_rewrite_as_*` exists for backwards compatibility but is discouraged. ([docs.sympy.org][6])

```python
expr = sp.cos(x) + sp.I*sp.sin(x)

expr.rewrite(sp.exp)
# exp(I*x)

expr.rewrite(sp.sin, sp.exp)
# exp(I*x)/2 + cos(x) - exp(-I*x)/2

expr.rewrite([sp.sin, sp.cos], sp.exp)
# exp(I*x)
```

Deployment rule:

```text
Use rewrite when:
  - target function family is known;
  - solver/codegen/backend prefers a different basis;
  - expression-family conversion is required.

Avoid rewrite as “simplification” unless:
  - target structural form is desired;
  - output is normalized afterward;
  - branch/domain behavior is tested.
```

---

## 5.10.2 `expand_func(expr)`

```python
sp.expand_func(expr)
```

`expand_func()` expands named/special functions using implemented identities. Official special-function docs show `expand_func(x*hyper([1, 1], [2], -x)) -> log(x + 1)` and `expand_func(meijerg(...)) -> exp(x)` for recognized special-function cases. ([docs.sympy.org][7])

```python
sp.expand_func(sp.gamma(x + 2))
# x*(x + 1)*gamma(x)
```

Use when:

```text
Need function identity expansion.
Need special functions rewritten to elementary/named forms.
Need preprocessing before simplification or codegen.
```

---

## 5.10.3 `hyperexpand(f, allow_hyper=False, rewrite="default", place=None)`

```python
from sympy.simplify.hyperexpand import hyperexpand
from sympy.functions import hyper, meijerg

hyperexpand(hyper([], [], z))
# exp(z)

hyperexpand(hyper([1, 1, 1], [], z))
# unchanged if unrecognized
```

`hyperexpand()` expands hypergeometric functions. `allow_hyper=True` permits partial simplification that still contains hypergeometric functions. For Meijer G-functions with expansions at both zero and infinity, `place=0` or `place=zoo` selects a preferred expansion. Unrecognized hypergeometric expressions and non-hypergeometric parts are left unchanged. ([docs.sympy.org][3])

Special-function docs state that hypergeometric functions generalize many named special functions, and `hyperexpand()` tries to express them using named special functions; Meijer G-functions also subsume many named functions and may be rewritten with `expand_func()` or `hyperexpand()`. ([docs.sympy.org][7])

Deployment rule:

```text
Use hyperexpand when:
  - expression contains hyper(...) or meijerg(...);
  - named elementary/special-function form is preferable;
  - codegen/backend does not support hyper/meijerg.

Guard:
  - output may remain hypergeometric;
  - output can grow;
  - branch/convergence conditions may be subtle;
  - cost-guard and numeric regression-test.
```

---

## 5.11 Canonical form vs visually simple form

```text
canonical form:
  stable, algorithmic, domain-specific, machine-oriented
  examples: cancel(together(expr)), Poly(expr).terms(), factor_list(expr)

visually simple form:
  shorter/readable/human-preferred
  examples: trigsimp(expr), factor(expr), logcombine(expr), sqrtdenest(expr)
```

SymPy’s `simplify()` docs show that the default `count_ops` measure can prefer an expression with fewer operations even if the user dislikes the visual form, and custom measures can change which candidate is returned. This proves “simple” is metric-dependent rather than absolute. ([docs.sympy.org][3])

Production pattern:

```python
def normalize_for_task(expr, task):
    expr = sp.sympify(expr)

    if task == "rational_equality":
        return sp.cancel(sp.together(expr))

    if task == "human_polynomial":
        return sp.factor(expr)

    if task == "coefficients":
        return sp.expand(expr)

    if task == "trig_output":
        return sp.trigsimp(expr)

    if task == "codegen":
        return codegen_pre_simplify(expr)

    raise ValueError(f"unknown normalization task: {task}")
```

---

## 5.12 Measuring cost and expression swell

## 5.12.1 `count_ops(expr, visual=False)`

```python
sp.count_ops(expr)
sp.count_ops(expr, visual=True)
expr.count_ops(visual=True)
```

`count_ops()` returns either an integer operation count or, with `visual=True`, an expression showing operation classes such as `ADD`, `MUL`, `POW`, and function names. Docs note that it counts normalized SymPy structure, not exactly what a user typed; for example `1/x/y` becomes `1/(x*y)`, so the operation count reflects the internal expression. ([docs.sympy.org][6])

```python
expr = sp.sin(x)*x + sp.sin(x)**2

sp.count_ops(expr)
# 5

sp.count_ops(expr, visual=True)
# ADD + MUL + POW + 2*SIN
```

Cost guard:

```python
def cost_guard(old, new, *, ratio=1.25, measure=sp.count_ops):
    old = sp.sympify(old)
    new = sp.sympify(new)

    old_cost = measure(old)
    new_cost = measure(new)

    if old_cost == 0:
        return new

    return new if new_cost <= ratio * old_cost else old
```

---

## 5.12.2 Weighted measure

```python
def weighted_ops(expr):
    POW = sp.Symbol("POW")
    SIN = sp.Symbol("SIN")
    COS = sp.Symbol("COS")
    LOG = sp.Symbol("LOG")

    cost = sp.count_ops(expr, visual=True)
    cost = cost.subs({
        POW: 8,
        SIN: 3,
        COS: 3,
        LOG: 4,
    })
    cost = cost.replace(sp.Symbol, type(sp.S.One))
    return int(cost)
```

Use weighted measures when downstream cost differs from SymPy’s default metric: generated C code may make `pow()` expensive, embedded targets may prefer multiplication over powers, GPU kernels may prefer fused vectorized functions, and readability may penalize nested powers/logs.

---

## 5.12.3 Expression-swell audit

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class RewriteCost:
    before_ops: int
    after_ops: int
    ratio: float
    before_len: int
    after_len: int
    changed: bool

def audit_cost(before, after) -> RewriteCost:
    before = sp.sympify(before)
    after = sp.sympify(after)

    b_ops = sp.count_ops(before)
    a_ops = sp.count_ops(after)

    return RewriteCost(
        before_ops=b_ops,
        after_ops=a_ops,
        ratio=float(a_ops / b_ops) if b_ops else float("inf"),
        before_len=len(str(before)),
        after_len=len(str(after)),
        changed=(before != after),
    )
```

Do not use `len(str(expr))` as a default complexity metric inside heavy simplification loops: the `simplify()` docs explicitly caution that string-length measures may slow down simplification for very large expressions, and recommend `count_ops` if no better metric is known. ([docs.sympy.org][3])

---

## 5.13 Pipeline profiles

## 5.13.1 Rational-equality profile

```python
def simplify_rational(expr):
    expr = sp.sympify(expr)
    return sp.cancel(sp.together(expr))
```

Output contract:

```text
common denominator
common factors canceled
suitable for structural zero checks
not necessarily visually factored
```

Use for equality testing:

```python
def is_rational_zero(expr):
    return simplify_rational(expr) == 0
```

---

## 5.13.2 Polynomial-human profile

```python
def simplify_polynomial_readable(expr):
    expr = sp.sympify(expr)
    expanded = sp.expand(expr)
    factored = sp.factor(expanded)
    return factored if sp.count_ops(factored) <= sp.count_ops(expanded) else expanded
```

Output contract:

```text
tries factored form
falls back if factored expression is costlier
```

---

## 5.13.3 Trig profile

```python
def simplify_trig(expr, *, heavy=False):
    expr = sp.sympify(expr)
    expr = sp.trigsimp(expr)

    if heavy:
        candidate = sp.trigsimp(expr, method="fu")
        expr = cost_guard(expr, candidate, ratio=1.1)

    return expr
```

Output contract:

```text
trig identities reduced
heavy mode tries stronger transformations
cost-guarded output
```

---

## 5.13.4 Power/log profile

```python
def simplify_power_log(expr, *, force=False):
    expr = sp.sympify(expr)

    expr = sp.powsimp(expr, combine="exp", deep=True, force=force)
    expr = sp.powdenest(expr, force=force)
    expr = sp.logcombine(expr, force=force)

    return expr
```

Deployment warning:

```text
force=False:
  assumption-respecting baseline.

force=True:
  only if positive/real/domain preconditions are externally guaranteed.
```

`powsimp(force=True)`, `powdenest(force=True)`, and `logcombine(force=True)` all make stronger assumption-like moves than the conservative default; official docs explicitly describe these force modes as bypassing or assuming missing assumptions. ([docs.sympy.org][3])

---

## 5.13.5 Radical profile

```python
def simplify_radicals(expr, *, symbolic_denominators=False):
    expr = sp.sympify(expr)

    expr = sp.sqrtdenest(expr)

    # Default to avoiding symbolic-denominator hazards.
    expr = sp.radsimp(expr, symbolic=symbolic_denominators)

    return expr
```

Output contract:

```text
tries sqrt denesting
rationalizes radical denominators
symbolic denominator processing disabled by default
```

---

## 5.13.6 Combinatorial profile

```python
def simplify_combinatorial(expr):
    expr = sp.sympify(expr)
    return sp.combsimp(expr)
```

Precondition recommendation:

```python
n, k = sp.symbols("n k", integer=True, nonnegative=True)
```

Integer assumptions improve validity and output shape for factorial/binomial expressions.

---

## 5.13.7 Hypergeometric/special-function profile

```python
def simplify_special(expr, *, allow_hyper=False):
    expr = sp.sympify(expr)

    a = sp.expand_func(expr)
    b = sp.hyperexpand(a, allow_hyper=allow_hyper)

    return cost_guard(a, b, ratio=2.0)
```

Output contract:

```text
tries special-function expansion first
tries hypergeometric expansion next
allows unchanged output
cost-guarded because named-function rewrites can expand heavily
```

---

## 5.13.8 Codegen-prep profile

```python
def codegen_pre_simplify(expr):
    expr = sp.sympify(expr)

    # local rational normalization
    expr = sp.cancel(sp.together(expr))

    # safe power exponent combination; avoid unsafe base forcing
    expr = sp.powsimp(expr, combine="exp", deep=True, force=False)

    # trig compaction
    expr = sp.trigsimp(expr)

    # choose factored form only if cheaper
    factored = sp.factor(expr)
    expr = factored if sp.count_ops(factored) <= sp.count_ops(expr) else expr

    return expr
```

Deployment rule:

```text
Before codegen:
  reduce removable rational factors;
  reduce repeated trig identities;
  avoid force=True unless domain contract is explicit;
  apply cse after simplification;
  compare operation counts before/after.
```

---

## 5.14 CSE as simplification-adjacent optimization

```python
replacements, reduced = sp.cse(expr)
```

Common subexpression elimination is not algebraic simplification, but it is often the decisive codegen-size simplifier. SymPy’s simplify reference lists `cse`, `opt_cse`, and `tree_cse`; `tree_cse` supports `order='canonical'` or `order='none'`, and docs note `order='none'` can be used for large expressions where speed is a concern. ([docs.sympy.org][3])

```python
def codegen_cse(exprs):
    return sp.cse(exprs, order="canonical")
```

Large-expression speed profile:

```python
repls, reduced = sp.cse(exprs, order="none")
```

Tradeoff:

```text
order="canonical":
  deterministic, better for tests/snapshots.

order="none":
  faster for large expressions, less deterministic ordering.
```

---

## 5.15 Rewriting vs simplifying

```text
simplification:
  aims to reduce complexity under some metric or target form.

rewriting:
  changes representation into another mathematically equivalent basis.
```

Examples:

```python
(sp.cos(x) + sp.I*sp.sin(x)).rewrite(sp.exp)
# exp(I*x)

sp.expand_func(sp.gamma(x + 2))
# x*(x + 1)*gamma(x)

sp.hyperexpand(sp.hyper([], [], x))
# exp(x)
```

`.rewrite()` has no inherent “smaller” guarantee; it is a representation-conversion API. `expand_func()` and `hyperexpand()` are directed rewrite/expansion tools for function families, and unrecognized hypergeometric expressions can remain unchanged. ([docs.sympy.org][6])

---

## 5.16 Anti-pattern inventory

| Anti-pattern                                           | Failure mode                                        | Replacement                                   |
| ------------------------------------------------------ | --------------------------------------------------- | --------------------------------------------- |
| `simplify()` in request loop                           | latency spikes, nondeterministic output shape       | precompute targeted pipeline                  |
| `simplify()` before coefficient extraction             | factored/non-expanded terms hide coefficients       | `expand`/`collect`/`Poly`                     |
| `logcombine(..., force=True)` without domain contract  | invalid branch/domain transform                     | positive symbols or `force=False`             |
| `powsimp(..., force=True)` on arbitrary symbols        | invalid radical/power combination                   | assumptions or `combine="exp"`                |
| `powdenest(..., force=True)` on complex/negative bases | invalid denesting                                   | positive/integer assumptions                  |
| `radsimp(symbolic=True)` then arbitrary substitution   | possible `nan` from violated denominator assumption | `symbolic=False` or track nonzero constraints |
| `trigsimp(inverse=True)` on general inputs             | invalid inverse cancellation                        | external domain proof                         |
| `hyperexpand()` assumed total                          | unrecognized functions unchanged                    | check `before == after`; fallback             |
| `count_ops` as only metric                             | visually undesirable output                         | weighted measure                              |
| `len(str(expr))` inside simplify measure               | slow on huge expressions                            | `count_ops` or cheap custom measure           |

---

## 5.17 Test matrix for simplification-sensitive code

```python
def assert_cost_not_exploded(before, after, ratio=2.0):
    b = sp.count_ops(before)
    a = sp.count_ops(after)
    assert b == 0 or a <= ratio*b

def assert_rational_equivalent(before, after):
    assert sp.cancel(sp.together(before - after)) == 0

def assert_numerically_equivalent(before, after, symbols, samples):
    f0 = sp.lambdify(symbols, before, "mpmath")
    f1 = sp.lambdify(symbols, after, "mpmath")
    for sample in samples:
        assert abs(f0(*sample) - f1(*sample)) < sp.mpf("1e-40")
```

Recommended cases:

```text
rational:
  removable factors
  zero denominators excluded
  nested fractions

trig:
  Pythagorean identities
  angle-sum identities
  inverse trig domain cases

log/power:
  positive symbols
  real symbols
  generic complex symbols
  negative symbols

radicals:
  numeric denominators
  symbolic denominators
  substitution after radsimp

combinatorial:
  integer symbols
  non-integer symbols
  factorial/binomial ratios

hyper:
  recognized hyper functions
  unrecognized hyper functions
  Meijer G examples
```

---

## 5.18 Minimal simplification harness

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal

import sympy as sp


Measure = Callable[[sp.Expr], int | float]
Profile = Literal[
    "rational",
    "polynomial",
    "trig",
    "power_log",
    "radical",
    "combinatorial",
    "special",
    "codegen",
]


@dataclass(frozen=True)
class SimplificationAudit:
    profile: str
    before: sp.Expr
    after: sp.Expr
    before_ops: int
    after_ops: int
    ratio: float
    changed: bool
    structurally_equivalent_after_rational_check: bool | None


def default_measure(expr: sp.Expr) -> int:
    return int(sp.count_ops(expr))


def weighted_codegen_measure(expr: sp.Expr) -> int:
    POW = sp.Symbol("POW")
    LOG = sp.Symbol("LOG")
    SIN = sp.Symbol("SIN")
    COS = sp.Symbol("COS")
    TAN = sp.Symbol("TAN")

    cost = sp.count_ops(expr, visual=True)
    cost = cost.subs({
        POW: 8,
        LOG: 4,
        SIN: 3,
        COS: 3,
        TAN: 5,
    })
    cost = cost.replace(sp.Symbol, type(sp.S.One))
    return int(cost)


def accept_if_cheaper(
    before: sp.Expr,
    candidate: sp.Expr,
    *,
    ratio: float = 1.25,
    measure: Measure = default_measure,
) -> sp.Expr:
    before = sp.sympify(before)
    candidate = sp.sympify(candidate)

    b = measure(before)
    c = measure(candidate)

    if b == 0:
        return candidate
    return candidate if c <= ratio * b else before


def rational_normal(expr: sp.Expr) -> sp.Expr:
    return sp.cancel(sp.together(sp.sympify(expr)))


def polynomial_readable(expr: sp.Expr) -> sp.Expr:
    expr = sp.expand(sp.sympify(expr))
    factored = sp.factor(expr)
    return accept_if_cheaper(expr, factored, ratio=1.1)


def trig_normal(expr: sp.Expr, *, heavy: bool = False) -> sp.Expr:
    expr = sp.trigsimp(sp.sympify(expr))
    if heavy:
        candidate = sp.trigsimp(expr, method="fu")
        expr = accept_if_cheaper(expr, candidate, ratio=1.2)
    return expr


def power_log_normal(expr: sp.Expr, *, force: bool = False) -> sp.Expr:
    expr = sp.sympify(expr)
    expr = sp.powsimp(expr, combine="exp", deep=True, force=force)
    expr = sp.powdenest(expr, force=force)
    expr = sp.logcombine(expr, force=force)
    return expr


def radical_normal(expr: sp.Expr, *, symbolic_denominators: bool = False) -> sp.Expr:
    expr = sp.sympify(expr)
    expr = sp.sqrtdenest(expr)
    expr = sp.radsimp(expr, symbolic=symbolic_denominators)
    return expr


def combinatorial_normal(expr: sp.Expr) -> sp.Expr:
    return sp.combsimp(sp.sympify(expr))


def special_normal(expr: sp.Expr, *, allow_hyper: bool = False) -> sp.Expr:
    expr = sp.sympify(expr)
    expanded = sp.expand_func(expr)
    hypered = sp.hyperexpand(expanded, allow_hyper=allow_hyper)
    return accept_if_cheaper(expanded, hypered, ratio=2.0)


def codegen_normal(expr: sp.Expr) -> sp.Expr:
    expr = sp.sympify(expr)

    expr = rational_normal(expr)
    expr = sp.powsimp(expr, combine="exp", deep=True, force=False)
    expr = sp.trigsimp(expr)

    factored = sp.factor(expr)
    expr = accept_if_cheaper(
        expr,
        factored,
        ratio=1.1,
        measure=weighted_codegen_measure,
    )

    return expr


def simplify_profile(expr: sp.Expr, profile: Profile, **kwargs) -> sp.Expr:
    if profile == "rational":
        return rational_normal(expr)
    if profile == "polynomial":
        return polynomial_readable(expr)
    if profile == "trig":
        return trig_normal(expr, **kwargs)
    if profile == "power_log":
        return power_log_normal(expr, **kwargs)
    if profile == "radical":
        return radical_normal(expr, **kwargs)
    if profile == "combinatorial":
        return combinatorial_normal(expr)
    if profile == "special":
        return special_normal(expr, **kwargs)
    if profile == "codegen":
        return codegen_normal(expr)
    raise ValueError(f"unknown simplification profile: {profile}")


def audit_simplification(expr: sp.Expr, profile: Profile, **kwargs) -> SimplificationAudit:
    before = sp.sympify(expr)
    after = simplify_profile(before, profile, **kwargs)

    b_ops = sp.count_ops(before)
    a_ops = sp.count_ops(after)

    equiv: bool | None
    try:
        equiv = rational_normal(before - after) == 0
    except Exception:
        equiv = None

    return SimplificationAudit(
        profile=profile,
        before=before,
        after=after,
        before_ops=int(b_ops),
        after_ops=int(a_ops),
        ratio=float(a_ops / b_ops) if b_ops else float("inf"),
        changed=(before != after),
        structurally_equivalent_after_rational_check=equiv,
    )
```

This harness encodes the deployment policy: targeted simplification, explicit `force` opt-in, radical-denominator caution, cost guards, rational equivalence checks, weighted codegen metrics, and profile-specific output contracts.

[1]: https://docs.sympy.org/latest/tutorials/intro-tutorial/simplification.html "Simplification - SymPy 1.14.0 documentation"
[2]: https://docs.sympy.org/latest/explanation/glossary.html "Glossary - SymPy 1.14.0 documentation"
[3]: https://docs.sympy.org/latest/modules/simplify/simplify.html "Simplify - SymPy 1.14.0 documentation"
[4]: https://docs.sympy.org/latest/tutorials/intro-tutorial/simplification.html?utm_source=chatgpt.com "Simplification - SymPy 1.14.0 documentation"
[5]: https://docs.sympy.org/latest/_sources/tutorials/intro-tutorial/simplification.rst.txt?utm_source=chatgpt.com "View this page"
[6]: https://docs.sympy.org/latest/modules/core.html "Core - SymPy 1.14.0 documentation"
[7]: https://docs.sympy.org/latest/modules/functions/special.html "Special - SymPy 1.14.0 documentation"

# 6) Numbers, exact arithmetic, precision, and numerical evaluation — agent-ready deep dive

Continuing the same dense technical-doc style as the uploaded planning/reference artifact. 

## 6.0 Numeric model contract

SymPy distinguishes **exact symbolic numbers** from **approximate floating-point numbers**. Exact numeric inputs preserve algebraic structure and enable exact simplification, factorization, solving, equality checks, and code generation. Approximate floats encode finite-precision numerical data and can poison exact algorithms if introduced before the numeric boundary. SymPy’s own best-practices docs explicitly recommend exact values such as `Rational(1, 2)` and `sympy.pi` over `0.5` and `math.pi` when the exact value is known. ([docs.sympy.org][1])

```python id="q0mg2i"
import sympy as sp

x = sp.Symbol("x")
```

Core policy:

```text id="j5lf8a"
symbolic layer:
  Integer, Rational, S(...), pi, E, I, oo, exact radicals, AlgebraicNumber

numeric approximation boundary:
  Float, evalf, N, lambdify(..., "mpmath"/"numpy"), Python float/complex

never:
  introduce Python floats or math.pi into exact derivation unless approximation is intentional
```

---

## 6.1 Core number classes and constants

## 6.1.1 `Number`, `Integer`, `Rational`, `Float`

SymPy’s `Number` class represents atomic numeric objects. `Integer`, `Rational`, and `Float` are the main explicit atomic numeric classes; `Integer` is a subclass of `Rational`, and both `Float` and `Rational` are subclasses of `Number`. Algebraic expressions such as `sqrt(2)` and complex expressions such as `3 + 4*I` are not `Number` instances because they are not atomic expression nodes. ([SymPy Documentation][2])

```python id="gcwa77"
sp.Integer(2)
sp.Rational(2, 7)
sp.Float("1.25", 50)
```

Type checks:

```python id="iavngq"
assert isinstance(sp.Integer(2), sp.Rational)
assert isinstance(sp.Rational(2, 7), sp.Number)
assert isinstance(sp.Float("1.25"), sp.Number)

assert not isinstance(sp.sqrt(2), sp.Number)
assert not isinstance(3 + 4*sp.I, sp.Number)
```

Agent rule:

```text id="ovroqg"
Use isinstance(obj, Number) for explicit atomic numbers.
Use expr.is_number for “contains no free symbols / numerically evaluable” semantics.
```

---

## 6.1.2 `Integer`

```python id="zj9ts5"
sp.Integer(0)
sp.Integer(1)
sp.Integer(10**100)
```

Python `int` values are automatically sympified when they appear in SymPy expressions; explicit `Integer(...)` is mainly useful for API boundaries, exact constructor normalization, and avoiding Python operator pre-evaluation.

```python id="g8nibd"
expr = x + 2
assert isinstance(expr.args[0] if expr.args[0] != x else expr.args[1], sp.Integer)
```

Singletons:

```python id="icq0v5"
sp.S.Zero
sp.S.One
sp.S.NegativeOne
```

SymPy exposes numeric singletons through `S`: `S.Zero`, `S.One`, `S.NegativeOne`, and `S.Half`; for example, `Rational(1, 2) is S.Half`. ([SymPy Documentation][2])

---

## 6.1.3 `Rational(p, q)`

```python id="rqk81x"
sp.Rational(1, 2)
sp.Rational(2, 7)
sp.Rational("-1/3")
sp.S(2) / 7
```

Use `Rational` or `S(integer)/integer` when writing explicit rational literals. Python evaluates `2/7` to a Python float before SymPy can see the exact rational, so `x + 2/7` loses exactness; `x + Rational(2, 7)` and `x + S(2)/7` preserve exact arithmetic. ([docs.sympy.org][1])

```python id="xwd4xi"
bad = x + 2/7
good1 = x + sp.Rational(2, 7)
good2 = x + sp.S(2)/7

bad
# x + 0.285714285714286

good1
# x + 2/7
```

Important boundary rule:

```python id="qjr045"
sp.Rational(2, 7)       # correct
sp.Rational(2, x)       # invalid: Rational is for number/number
2/x                     # symbolic fraction
```

`Rational` is for rational numbers, not symbolic fractions. For symbolic denominator expressions, use ordinary `/` with at least one SymPy object.

---

## 6.1.4 `Float(num, dps=None, precision=None)`

```python id="8g2mrc"
sp.Float(0.1)
sp.Float(0.1, 30)
sp.Float("0.1", 30)
sp.Float("1.23456789123456789")
sp.Float("123 456 789.123_456", "")
```

`Float` represents arbitrary-precision floating-point numbers, but arbitrary precision is not arbitrary accuracy. Creating a `Float` from a Python `float` imports the already-rounded binary float; creating from a string allows SymPy to parse the intended decimal at higher precision. The docs show `Float(0.3, 20)` as `0.29999999999999998890`, while `Float("0.3", 20)` gives `0.30000000000000000000`. ([SymPy Documentation][2])

```python id="p5tccf"
sp.Float(0.3, 20)
# 0.29999999999999998890

sp.Float("0.3", 20)
# 0.30000000000000000000
```

Significant-figure auto-counting:

```python id="7ztyj7"
sp.Float("60.e2", "")    # 2 significant digits
sp.Float("60e2", "")     # 4 significant digits
sp.Float("600e-2", "")   # 3 significant digits
```

Deployment rule:

```text id="anj74q"
Use Float only at numeric boundaries.
For high-precision decimal constants, pass strings, not Python floats.
Do not use Float to encode exact rationals.
Do not expect evalf/Float to restore accuracy lost in earlier binary floats.
```

---

## 6.1.5 `AlgebraicNumber`

```python id="tu6tw0"
a = sp.AlgebraicNumber(sp.sqrt(5))
b = sp.AlgebraicNumber(sp.sqrt(5), [-1, 1])
```

`AlgebraicNumber` represents an element of a number field `Q(theta)` with a chosen embedding into the complex numbers. Internally, it is represented using a primitive element, a minimal polynomial, and coefficients expressing the element as a polynomial in the primitive element. ([SymPy Documentation][2])

```python id="0mw7ys"
a = sp.AlgebraicNumber(sp.sqrt(5), [-1, 1])
# represents 1 - sqrt(5)

b = a.field_element([3, 2])
# represents 2 + 3*sqrt(5)

a.minpoly
a.coeffs()
a.as_poly()
a.to_root()
```

Use cases:

```text id="z2tb6n"
exact algebraic field arithmetic
minimal polynomial workflows
exact root/number-field representation
polynomial algorithms over algebraic extensions
avoiding premature radical/float expansion
```

Guardrail:

```text id="n7j2yc"
sqrt(2) as Expr is often enough.
Use AlgebraicNumber/to_number_field when field structure itself matters.
```

---

## 6.1.6 Symbolic constants: `pi`, `E`, `I`, `oo`, `zoo`, `nan`

```python id="szsij0"
sp.pi
sp.E
sp.I
sp.oo
-sp.oo
sp.zoo
sp.nan
```

`E`, `I`, `pi`, and infinities are singleton symbolic constants. `E` is the natural exponential base, `I` is the imaginary unit, `pi` is the exact symbolic pi constant, `oo` is positive infinity, `zoo` is complex infinity, and `nan` represents an indeterminate numeric value. ([SymPy Documentation][2])

```python id="o96pz5"
sp.sin(sp.pi)
# 0

sp.log(sp.E)
# 1

sp.I**2
# -1

42 / sp.oo
# 0

sp.oo - sp.oo
# nan
```

`math.pi` is a double-precision approximation; `sympy.pi` is exact. The docs show `sympy.sin(math.pi)` producing a tiny nonzero residue, while `sympy.sin(sympy.pi)` returns exactly `0`. ([docs.sympy.org][1])

```python id="m6bghd"
import math

sp.sin(math.pi)
# 1.22464679914735e-16

sp.sin(sp.pi)
# 0
```

---

## 6.2 Exact arithmetic and float leakage

## 6.2.1 Exactness-preserving constructors

```python id="td6s18"
sp.Integer(3)
sp.Rational(1, 3)
sp.S(1) / 3
sp.sqrt(2)
sp.pi
sp.E
sp.I
```

Exact expression:

```python id="6dbhf6"
expr = x**2 + sp.Rational(1, 2)*x + sp.pi
```

Approximate expression:

```python id="k1u9zq"
expr_bad = x**2 + 0.5*x + math.pi
```

Why it matters:

```python id="as2ne5"
sp.factor(x**2.0 - 1)
# x**2.0 - 1

sp.factor(x**2 - 1)
# (x - 1)*(x + 1)
```

SymPy best-practices docs show that floats can block exact algorithms, including polynomial factorization with floating exponents, and can introduce cancellation artifacts; rational numbers preserve the exact structure required by symbolic algorithms. ([docs.sympy.org][1])

---

## 6.2.2 Float contamination detector

```python id="pfr844"
def has_float(expr: sp.Basic) -> bool:
    return bool(sp.sympify(expr).atoms(sp.Float))

def float_atoms(expr: sp.Basic) -> set[sp.Float]:
    return sp.sympify(expr).atoms(sp.Float)
```

Usage:

```python id="ha5bfn"
expr = x + 0.5

assert has_float(expr)
assert float_atoms(expr) == {sp.Float(0.5)}
```

Pipeline guard:

```python id="si32rc"
def require_exact(expr: sp.Expr) -> sp.Expr:
    expr = sp.sympify(expr)
    floats = expr.atoms(sp.Float)
    if floats:
        raise ValueError(f"Float contamination: {floats}")
    return expr
```

---

## 6.2.3 Exact conversion and recovery

Exact binary rational from a Python float:

```python id="s9s9t5"
sp.Rational(0.7)
# 3152519739159347/4503599627370496
```

Human-intended rational approximation:

```python id="k6jfyx"
sp.nsimplify(0.7)
# 7/10
```

SymPy docs explicitly show `Rational(0.7)` producing the exact rational for the binary float and `nsimplify(0.7)` producing `7/10`; the docs still recommend starting with rational numbers directly when possible. ([docs.sympy.org][1])

---

## 6.3 Precision control: `evalf`, `.n`, `N`

## 6.3.1 API surface

```python id="y3zz4h"
expr.evalf(n=15, subs=None, maxn=100, chop=False, strict=False, quad=None, verbose=False)
expr.n(n=15, subs=None, maxn=100, chop=False, strict=False, quad=None, verbose=False)
sp.N(expr, n=15, **options)
```

`evalf()` converts exact SymPy expressions to floating-point approximations; `N(expr, args)` is equivalent to `sympify(expr).evalf(args)`. The default numerical evaluation target is 15 decimal digits, and the requested precision can be passed as an integer. ([SymPy Documentation][3])

```python id="o5tezo"
expr = sp.sqrt(2) * sp.pi

expr.evalf()
# 4.44288293815837

expr.evalf(50)
# 50-digit approximation

sp.N(expr, 5)
# 4.4429

sp.N(expr, 80)
# 80-digit approximation
```

Complex expressions:

```python id="bz5chy"
sp.N(1/(sp.pi + sp.I), 20)
```

Partial evaluation:

```python id="42vevh"
expr = sp.pi*x**2 + x/sp.Integer(3)

expr.evalf()
# 3.14159265358979*x**2 + 0.333333333333333*x
```

If symbols remain, `evalf()` can return a partially evaluated symbolic expression; the numerical evaluation docs show coefficients evaluated while symbolic variables remain symbolic. ([SymPy Documentation][3])

---

## 6.3.2 `subs` inside `evalf`

```python id="c9up98"
expr.evalf(50, subs={x: sp.Rational(1, 3)})
expr.evalf(subs={x: 3.0}, n=21)
```

`evalf(subs=...)` substitutes numerical values during numerical evaluation. The docs state the substitutions must be supplied as a dictionary and show that using `evalf(subs=values)` can avoid precision errors from naive `.subs(values)` followed by evaluation; the example `(x + y - z).subs({x:1e16, y:1, z:1e16})` gives `0`, while `.evalf(subs=...)` gives `1.00000000000000`. ([SymPy Documentation][2])

```python id="2w5wc2"
x, y, z = sp.symbols("x y z")
values = {x: 1e16, y: 1, z: 1e16}

(x + y - z).subs(values)
# 0

(x + y - z).evalf(subs=values)
# 1.00000000000000
```

Deployment rule:

```text id="gxtspg"
For final numeric scalar evaluation with inexact inputs:
  prefer expr.evalf(n, subs=values)

For symbolic specialization:
  use expr.subs(exact_values)

For repeated numeric evaluation:
  use lambdify/codegen, not evalf in loops
```

---

## 6.3.3 `chop`, `strict`, `maxn`, `quad`

```python id="dqc06z"
sp.N(expr, 50, chop=True)
sp.N(expr, 50, chop=sp.S("1e-40"))
expr.evalf(80, maxn=200, strict=True)
integral_expr.evalf(50, quad="osc")
```

`chop` replaces tiny real or imaginary parts with exact zero using a threshold; `strict=True` raises `PrecisionExhausted` if a subresult cannot reach full accuracy; `maxn` controls maximum temporary working precision; `quad` selects numerical quadrature strategy, with `quad="osc"` intended for oscillatory integrals on infinite intervals. ([SymPy Documentation][2])

Use cases:

```text id="9yy56x"
chop=True:
  display cleanup / numerical noise removal

strict=True:
  high-stakes numeric verification

maxn:
  allow more internal precision for difficult evaluation

quad="osc":
  oscillatory improper integrals
```

---

## 6.4 Precision vs accuracy

## 6.4.1 Existing `Float` accuracy is fixed by construction

```python id="tg2ibz"
f = sp.Float(0.1, 1)
f.evalf(20)
```

Increasing precision of an existing inexact `Float` does not increase the accuracy of its underlying stored value. The core docs explicitly state that `evalf` can change precision for calculation purposes but cannot increase the accuracy of an inexact value; they show `Float(.1, 1).evalf(5)` yielding a value reflecting the original low-precision approximation. ([SymPy Documentation][2])

Rule:

```text id="jfzd1r"
precision = number of digits carried/displayed
accuracy  = correctness of those digits relative to intended mathematical value

evalf can increase precision.
evalf cannot recover accuracy already lost.
```

---

## 6.4.2 High-precision decimal literal ingestion

Bad:

```python id="hy378s"
sp.Float(1.23456789123456789)
# Python float already rounded
```

Good:

```python id="xl6nz8"
sp.Float("1.23456789123456789")
```

Docs state that Python `float` input retains only about 15 digits of precision and that high-precision decimal numbers should preferably be entered as strings. ([SymPy Documentation][2])

---

## 6.5 `nsimplify`: recovering exact forms from approximate values

## 6.5.1 API surface

```python id="ml30qt"
sp.nsimplify(expr, constants=(), tolerance=None, full=False, rational=None, rational_conversion="base10")
```

`nsimplify()` finds a simple exact representation for a numeric expression, optionally using supplied constants. For numerical expressions, the input should be evaluable to at least 30 digits; `tolerance` controls match strictness, `full=True` performs a more extensive search, and `rational_conversion` can be `"base10"` or `"exact"` when converting floats to rationals. ([SymPy Documentation][4])

```python id="vptqs0"
sp.nsimplify(0.333333333333333)
# 1/3

sp.nsimplify(sp.pi, tolerance=0.01)
# 22/7

sp.nsimplify(sp.I**sp.I, [sp.pi])
# exp(-pi/2)

sp.nsimplify(4/(1 + sp.sqrt(5)), [sp.GoldenRatio])
# -2 + 2*GoldenRatio
```

Rational conversion modes:

```python id="hpd8oy"
sp.nsimplify(0.333333333333333, rational=True)
# 1/3

sp.nsimplify(0.333333333333333, rational=True, rational_conversion="exact")
# 6004799503160655/18014398509481984
```

Docs show `"base10"` as the default rational conversion, using the base-10 string representation, while `"exact"` uses the exact base-2 representation of the float. ([SymPy Documentation][4])

---

## 6.5.2 `nsimplify` deployment policy

```text id="ni7bbs"
Use nsimplify when:
  - ingesting approximate measurements that likely encode simple rationals/constants;
  - reverse-engineering formulas from numeric results;
  - cleaning user-entered decimal constants;
  - producing exact candidate formulas for later verification.

Avoid nsimplify when:
  - float value is authoritative measurement data;
  - approximation noise is meaningful;
  - exact recovery would invent false structure;
  - production correctness depends on guessed constants without validation.
```

Validation pattern:

```python id="phrdje"
def recover_exact_number(value, *, constants=(), tolerance=None, verify_digits=80):
    exact = sp.nsimplify(value, constants=constants, tolerance=tolerance)
    if abs(sp.N(exact, verify_digits) - sp.N(value, verify_digits)) > sp.Float(10)**(-verify_digits//2):
        raise ValueError("nsimplify candidate failed numeric verification")
    return exact
```

---

## 6.6 mpmath integration and arbitrary precision

SymPy has one hard dependency: **mpmath**. The docs state that mpmath is a pure Python arbitrary-precision arithmetic package used whenever SymPy calculates floating-point values of functions, such as through `evalf`; SymPy fails to import if mpmath is missing. ([SymPy Documentation][5])

```python id="zslv06"
sp.N(sp.sin(sp.pi/7), 100)
```

mpmath-backed deployment surfaces:

```python id="9pa4tj"
# scalar arbitrary-precision evaluation inside SymPy
expr.evalf(100)

# numeric callable using mpmath namespace
f_mp = sp.lambdify(x, expr, modules="mpmath")
```

The dependencies docs also state that `lambdify` can produce mpmath-compatible functions and that mpmath is already required by SymPy. ([SymPy Documentation][5])

Use mpmath-backed paths when:

```text id="tpt9mh"
high-precision scalar numerics
complex special functions
verification oracle for codegen/NumPy/JAX outputs
root/integral/series numeric diagnostics
```

Avoid mpmath-backed paths when:

```text id="46p8dt"
large vectorized arrays
GPU/TPU execution
low-latency repeated machine-float evaluation
```

Use `lambdify(..., "numpy")`, `ufuncify`, codegen, JAX, or CuPy in those cases.

---

## 6.7 gmpy2 performance dependency

`gmpy2` is a recommended optional dependency. SymPy uses it automatically when installed for certain integer-heavy core functions and polynomial domains; docs note that polynomial machinery is used by integration, simplification algorithms such as `collect()` and `factor()`, matrices, and parts of the core, so installing `gmpy2` can speed up many SymPy workflows. ([SymPy Documentation][5])

```bash id="uv95xm"
python -m pip install gmpy2
```

No code enablement needed:

```text id="zn7vgx"
if installed:
  SymPy uses gmpy2 automatically

if absent:
  SymPy falls back to pure Python integers
```

Deployment recommendation:

```text id="1fbwcl"
Install gmpy2 in:
  polynomial-heavy services
  exact rational/algebra workflows
  large integer arithmetic
  symbolic simplification/codegen derivation hosts
  CI performance parity environments
```

---

## 6.8 Numeric conversion boundaries

## 6.8.1 Python `float()` / `complex()`

```python id="fzxnbb"
float(sp.pi)
complex(sp.pi + sp.E*sp.I)
```

`float()` and `complex()` convert SymPy expressions to ordinary Python numeric values, but they fail if the expression contains symbols or otherwise cannot be evaluated to an explicit number. SymPy’s numerical evaluation docs show `float(pi)` and `complex(pi + E*I)` as supported examples and state that failure to evaluate raises an exception. ([SymPy Documentation][3])

```python id="vy8e2k"
float(x + 1)
# TypeError
```

Use policy:

```text id="9mtcs6"
Use float/complex only at external API boundaries requiring Python scalars.
Use evalf/N for precision-controlled SymPy Float outputs.
Use lambdify for repeated numeric execution.
```

---

## 6.8.2 `nfloat(expr, n=15, exponent=False, dkeys=False)`

```python id="adkmpb"
sp.nfloat(x**4 + x/2 + sp.cos(sp.pi/3) + 1 + sp.sqrt(y))
# x**4 + 0.5*x + sqrt(y) + 1.5

sp.nfloat(x**4 + sp.sqrt(y), exponent=True)
# x**4.0 + y**0.5
```

`nfloat()` converts rationals in an expression to `Float`s, except in exponents and undefined functions unless options request otherwise; it preserves container types. This is a bulk approximation primitive, not an exact simplification primitive. ([SymPy Documentation][2])

Use when preparing display/numeric-oriented expressions, not when preserving algebraic exactness.

---

## 6.9 Decision matrix

| Task                               | Recommended representation                            | Avoid                                         |                            |
| ---------------------------------- | ----------------------------------------------------- | --------------------------------------------- | -------------------------- |
| exact symbolic derivation          | `Integer`, `Rational`, `pi`, `E`, exact radicals      | Python `float`, `math.pi`                     |                            |
| exact rational coefficient         | `Rational(p, q)`, `S(p)/q`                            | `p/q` when both are Python ints               |                            |
| high-precision decimal constant    | `Float("decimal", dps)`                               | `Float(python_float, high_dps)`               |                            |
| approximate display                | `N(expr, n)`                                          | converting entire symbolic pipeline to floats |                            |
| repeated numeric scalar evaluation | `lambdify(..., "math"                                 | "mpmath")`                                    | repeated `.subs().evalf()` |
| repeated array evaluation          | `lambdify(..., "numpy")`                              | SymPy objects in NumPy ufuncs                 |                            |
| exact algebraic field arithmetic   | `AlgebraicNumber`, `to_number_field`                  | premature `evalf()`                           |                            |
| recovering exact from decimal      | `nsimplify` with validation                           | blind `Rational(float)`                       |                            |
| large integer/polynomial workflows | install `gmpy2`                                       | assuming pure Python speed is enough          |                            |
| final Python API scalar            | `float(expr)` / `complex(expr)` only after validation | `float(symbolic_expr_with_free_symbols)`      |                            |

---

## 6.10 Agent guardrails

## 6.10.1 Prevent Python division leakage

Bad:

```python id="v44fxp"
expr = x + 1/2
```

Good:

```python id="txkhqa"
expr = x + sp.Rational(1, 2)
expr = x + sp.S(1)/2
expr = x + sp.Integer(1)/2
```

The leak happens before SymPy sees the expression.

---

## 6.10.2 Prevent `math` module leakage

Bad:

```python id="nlrbzf"
import math
expr = sp.sin(math.pi*x)
```

Good:

```python id="jg53v3"
expr = sp.sin(sp.pi*x)
```

Docs recommend avoiding `math` when using SymPy for symbolic work because standard-library constants/functions are numeric, not symbolic. ([docs.sympy.org][1])

---

## 6.10.3 Detect floats before exact algorithms

```python id="rkh4a2"
def assert_no_float_atoms(expr: sp.Basic) -> None:
    floats = sp.sympify(expr).atoms(sp.Float)
    if floats:
        raise ValueError(f"unexpected Float atoms: {sorted(map(str, floats))}")
```

Use before:

```text id="a3skms"
factor
cancel/together equality checks
solve/solveset with exact coefficients
Groebner bases
minimal polynomials
codegen reference generation
formal proof/equivalence testing
```

---

## 6.10.4 Normalize external numeric inputs explicitly

```python id="jkwgbr"
def sympify_numeric(value, *, exact_decimal=False):
    if isinstance(value, str):
        return sp.S(value) if exact_decimal else sp.Float(value)
    if isinstance(value, int):
        return sp.Integer(value)
    if isinstance(value, float):
        return sp.Float(value)
    return sp.sympify(value)
```

Use API-specific intent:

```text id="zbdttn"
configuration says "exact":
  parse decimal strings with Rational/Decimal policy or S("1/10")

configuration says "measurement":
  keep Float; do not nsimplify unless user opts in

configuration says "formula recovery":
  nsimplify with explicit constants/tolerance and verification
```

---

## 6.11 Numeric evaluation recipes

## Recipe A — exact derivation, high-precision scalar evaluation

```python id="mygqok"
def exact_then_evalf():
    x = sp.Symbol("x")
    expr = sp.sin(sp.pi*x) + sp.Rational(1, 3)
    return expr.evalf(80, subs={x: sp.Rational(1, 7)})
```

---

## Recipe B — accurate numeric substitution with cancellation risk

```python id="lm1n5u"
def eval_with_subs(expr, values, digits=50):
    return sp.sympify(expr).evalf(digits, subs=values)
```

Use `evalf(subs=...)` instead of `.subs(values).evalf()` when inexact substitution values can cause cancellation artifacts. ([SymPy Documentation][2])

---

## Recipe C — exact rational cleanup of user decimals

```python id="6ac9y2"
def exactify_decimals(expr, *, constants=(), tolerance=None):
    expr = sp.sympify(expr)
    return sp.nsimplify(expr, constants=constants, tolerance=tolerance)
```

Use only where inferred exactness is desired.

---

## Recipe D — safe high-precision Float constructor

```python id="nv27b2"
def decimal_float(s: str, digits: int) -> sp.Float:
    if not isinstance(s, str):
        raise TypeError("pass decimal as string to avoid Python float rounding")
    return sp.Float(s, digits)
```

---

## Recipe E — exactness-preserving symbolic constants

```python id="c7u1ie"
CONSTANTS = {
    "pi": sp.pi,
    "e": sp.E,
    "I": sp.I,
    "inf": sp.oo,
    "-inf": -sp.oo,
}
```

---

## Recipe F — exact numeric audit report

```python id="pwgav0"
from dataclasses import dataclass

@dataclass(frozen=True)
class NumericAudit:
    expr: sp.Expr
    float_atoms: tuple[sp.Float, ...]
    rational_atoms: tuple[sp.Rational, ...]
    integer_atoms: tuple[sp.Integer, ...]
    number_symbols: tuple[sp.Basic, ...]
    free_symbols: set[sp.Symbol]
    is_number: bool

def audit_numeric(expr) -> NumericAudit:
    expr = sp.sympify(expr)
    return NumericAudit(
        expr=expr,
        float_atoms=tuple(sorted(expr.atoms(sp.Float), key=str)),
        rational_atoms=tuple(sorted(expr.atoms(sp.Rational), key=str)),
        integer_atoms=tuple(sorted(expr.atoms(sp.Integer), key=str)),
        number_symbols=tuple(sorted(expr.atoms(sp.NumberSymbol), key=str)),
        free_symbols=expr.free_symbols,
        is_number=bool(expr.is_number),
    )
```

---

## 6.12 Testing matrix

```python id="m6t79j"
def test_exact_rational_no_float():
    expr = x + sp.Rational(2, 7)
    assert not expr.atoms(sp.Float)
    assert sp.factor(x**2 - 1) == (x - 1)*(x + 1)

def test_float_leak_detected():
    expr = x + 2/7
    assert expr.atoms(sp.Float)

def test_math_pi_artifact():
    import math
    assert sp.sin(sp.pi) == 0
    assert sp.sin(math.pi) != 0

def test_evalf_subs_cancellation():
    x, y, z = sp.symbols("x y z")
    values = {x: 1e16, y: 1, z: 1e16}
    assert (x + y - z).subs(values) == 0
    assert (x + y - z).evalf(subs=values) == 1

def test_nsimplify_recovery():
    assert sp.nsimplify(0.7) == sp.Rational(7, 10)
    assert sp.Rational(0.7) != sp.Rational(7, 10)
```

---

## 6.13 Anti-pattern inventory

| Anti-pattern                              | Failure mode                           | Correct pattern                                                 |
| ----------------------------------------- | -------------------------------------- | --------------------------------------------------------------- |
| `x + 2/7`                                 | Python float formed before SymPy       | `x + Rational(2, 7)` or `x + S(2)/7`                            |
| `sympy.sin(math.pi)`                      | tiny nonzero approximation residue     | `sympy.sin(sympy.pi)`                                           |
| `Float(0.3, 50)`                          | high-precision binary-float artifact   | `Float("0.3", 50)`                                              |
| `evalf(100)` after low-accuracy `Float`   | more digits, same bad underlying value | create exact/string input first                                 |
| `Rational(0.7)` for intended `7/10`       | exact binary-float rational            | `Rational(7, 10)` or validated `nsimplify`                      |
| blind `nsimplify(measurement)`            | false exact structure                  | treat measurements as `Float` unless formula recovery requested |
| `.subs(float_values).evalf()`             | cancellation/rounding artifacts        | `.evalf(subs=float_values)`                                     |
| `float(expr)` with free symbols           | exception                              | validate `expr.free_symbols == set()` first                     |
| exact algorithms with Float atoms         | weak factor/solve/simplify output      | float audit + exact constructors                                |
| assuming `Float` precision means accuracy | misleading numerical trust             | track source precision and input method                         |

---

## 6.14 Minimal numeric harness

```python id="cejxrh"
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import sympy as sp


@dataclass(frozen=True)
class ExactnessReport:
    expr: sp.Expr
    has_float: bool
    floats: tuple[sp.Float, ...]
    rationals: tuple[sp.Rational, ...]
    number_symbols: tuple[sp.NumberSymbol, ...]
    free_symbols: set[sp.Symbol]


def exact_integer(n: int) -> sp.Integer:
    return sp.Integer(n)


def exact_rational(p: int, q: int) -> sp.Rational:
    return sp.Rational(p, q)


def exact_decimal_string(s: str) -> sp.Rational:
    # exact base-10 rational, e.g. "0.125" -> 1/8
    return sp.Rational(s)


def high_precision_float(s: str, digits: int = 50) -> sp.Float:
    if not isinstance(s, str):
        raise TypeError("decimal input must be a string to avoid Python float rounding")
    return sp.Float(s, digits)


def exactness_report(expr: Any) -> ExactnessReport:
    expr = sp.sympify(expr)
    return ExactnessReport(
        expr=expr,
        has_float=bool(expr.atoms(sp.Float)),
        floats=tuple(sorted(expr.atoms(sp.Float), key=str)),
        rationals=tuple(sorted(expr.atoms(sp.Rational), key=str)),
        number_symbols=tuple(sorted(expr.atoms(sp.NumberSymbol), key=str)),
        free_symbols=set(expr.free_symbols),
    )


def require_exact(expr: Any) -> sp.Expr:
    expr = sp.sympify(expr)
    floats = expr.atoms(sp.Float)
    if floats:
        raise ValueError(f"Float contamination detected: {sorted(map(str, floats))}")
    return expr


def numeric_eval(expr: Any, *, digits: int = 50, subs: dict[sp.Symbol, Any] | None = None) -> sp.Expr:
    expr = sp.sympify(expr)
    return expr.evalf(digits, subs=subs)


def recover_exact(
    value: Any,
    *,
    constants: Iterable[sp.Expr] = (),
    tolerance: float | None = None,
    rational: bool | None = None,
) -> sp.Expr:
    return sp.nsimplify(
        value,
        constants=list(constants),
        tolerance=tolerance,
        rational=rational,
    )


def to_python_float(expr: Any) -> float:
    expr = sp.sympify(expr)
    if expr.free_symbols:
        raise ValueError(f"cannot convert expression with free symbols: {expr.free_symbols}")
    return float(expr)


def symbolic_constants() -> dict[str, sp.Expr]:
    return {
        "pi": sp.pi,
        "E": sp.E,
        "I": sp.I,
        "oo": sp.oo,
        "-oo": -sp.oo,
        "zoo": sp.zoo,
        "nan": sp.nan,
    }
```

This harness enforces exact-constructor discipline, decimal-string precision safety, float-contamination auditing, `evalf(subs=...)` numeric evaluation, validated Python scalar conversion, and explicit exact-recovery via `nsimplify`.

[1]: https://docs.sympy.org/latest/explanation/best-practices.html?utm_source=chatgpt.com "Best Practices - SymPy 1.14.0 documentation"
[2]: https://docs.sympy.org/latest/modules/core.html "Core - SymPy 1.14.0 documentation"
[3]: https://docs.sympy.org/latest/modules/evalf.html "Numerical Evaluation - SymPy 1.14.0 documentation"
[4]: https://docs.sympy.org/latest/modules/simplify/simplify.html "Simplify - SymPy 1.14.0 documentation"
[5]: https://docs.sympy.org/latest/contributing/dependencies.html "Dependencies - SymPy 1.14.0 documentation"

# 7) Calculus: differentiation, integration, limits, series — agent-ready deep dive

Continuing the advanced technical-doc pattern from the provided reference artifact. 

## 7.0 Calculus surface map

SymPy’s calculus layer covers symbolic derivatives, integrals, limits, series expansions, finite differences, residues, singularities, integral transforms, and delayed unevaluated calculus objects. The primary workflow: build exact symbolic expression → compute derivative/integral/limit/series → normalize/simplify → validate assumptions/domain → deploy via `evalf`, `lambdify`, `ufuncify`, `autowrap`, or code generation. SymPy’s calculus tutorial explicitly frames the section around derivatives, integrals, limits, and series expansions. ([docs.sympy.org][1])

```python id="nf008l"
import sympy as sp

x, y, z, t = sp.symbols("x y z t")
a, b, n = sp.symbols("a b n")
f, g = sp.symbols("f g", cls=sp.Function)
```

Capability map:

```text id="na593f"
Differentiation:
  diff, Expr.diff, Derivative, idiff, finite differences

Integration:
  integrate, Integral, Integral.doit, Integral.evalf,
  Integral.as_sum, principal_value, transforms

Limits:
  limit, Limit, one-sided/bidirectional limits, infinity limits

Series:
  Expr.series, series, Order/O, removeO, asymptotic expansions

Complex analysis:
  residue, singularities, continuous_domain

Deployment:
  symbolic derivation → targeted simplify → lambdify/codegen
```

---

## 7.1 Differentiation

## 7.1.1 `diff(expr, *symbols, **kwargs)`

Primary forms:

```python id="qwv4ws"
sp.diff(expr, x)
sp.diff(expr, x, 3)
sp.diff(expr, x, x, x)
sp.diff(expr, x, y, 2, z, 4)
sp.diff(expr, (x, n))
sp.diff(expr, x, evaluate=False)
expr.diff(x)
expr.diff(x, y, 2)
```

`diff()` is the top-level differentiation function. It supports repeated variables, `(symbol, order)` tuples, and multiple variables for partial derivatives. `expr.diff(...)` is method syntax equivalent to `diff(expr, ...)`; `Derivative(...)` is the unevaluated counterpart. ([docs.sympy.org][1])

Examples:

```python id="gco35e"
sp.diff(sp.cos(x), x)
# -sin(x)

sp.diff(sp.exp(x**2), x)
# 2*x*exp(x**2)

sp.diff(x**4, x, x, x)
# 24*x

sp.diff(x**4, x, 3)
# 24*x

expr = sp.exp(x*y*z)
sp.diff(expr, x, y, 2, z, 4)
```

Partial derivative ordering:

```python id="yvzm54"
expr = sp.exp(x*y*z)

d1 = sp.diff(expr, x, y, 2, z, 4)
d2 = expr.diff(x, y, y, z, 4)

assert d1 == d2
```

Library-code guardrail: `diff(sin(x))` can infer a variable only in simple cases, but SymPy’s docs state that this shorthand is meant for interactive convenience and should be avoided in library code. Always pass variables explicitly. ([docs.sympy.org][2])

```python id="gnx4m7"
# Avoid in production:
sp.diff(sp.sin(x))

# Prefer:
sp.diff(sp.sin(x), x)
```

---

## 7.1.2 Unevaluated derivative: `Derivative`

```python id="d7fctb"
D = sp.Derivative(expr, x)
D2 = sp.Derivative(expr, x, y, y, z, 4)
D3 = sp.Derivative(expr, (x, 3), (y, 2))
```

`Derivative` stores a derivative object without evaluating it. Evaluate with `.doit()`. Unevaluated derivatives are useful for delayed evaluation, printing, PDE/ODE representation, finite-difference conversion, and for expressions involving undefined functions where a closed derivative remains symbolic. ([docs.sympy.org][1])

```python id="i53isu"
deriv = sp.Derivative(sp.exp(x*y*z), x, y, y, z, 4)
deriv.doit()
```

Delayed evaluation:

```python id="pyn8tu"
d = sp.diff(sp.sin(x), x, evaluate=False)

type(d)
# sympy.core.function.Derivative

d.doit()
# cos(x)
```

Zeroth derivative rule:

```python id="w17e2r"
sp.diff(sp.sin(x), x, 0)
# sin(x)

sp.diff(sp.sin(x), x, 0, evaluate=False)
# sin(x)
```

SymPy’s `diff()` docs note that `evaluate=False` returns an unevaluated `Derivative`, except for zero-order derivatives, which return the original function. ([docs.sympy.org][2])

---

## 7.1.3 Undefined functions and functional derivatives

```python id="z1vaad"
f = sp.Function("f")

sp.diff(f(x), x)
# Derivative(f(x), x)

sp.diff(f(x)**2, x)
# 2*f(x)*Derivative(f(x), x)

sp.diff(f(x, y), x, y)
# Derivative(f(x, y), x, y)
```

Use undefined functions for ODE/PDE symbolic forms, variational derivations, delayed differentiation, and equation construction. When converting to numerical functions, unresolved `Derivative(...)` nodes must be evaluated, replaced, discretized, or converted to user-supplied callable implementations.

Detection:

```python id="a9txvb"
def has_unevaluated_derivative(expr: sp.Basic) -> bool:
    return bool(sp.sympify(expr).atoms(sp.Derivative))
```

---

## 7.1.4 Higher/unspecified order

```python id="lqkp6s"
m, n = sp.symbols("m n")
expr = (a*x + b)**m

sp.diff(expr, (x, n))
# Derivative((a*x + b)**m, (x, n))
```

Tuple syntax `(x, n)` creates derivatives of symbolic/unspecified order. This is useful for recurrence formulas, formal operators, and generated mathematical documents. SymPy’s calculus tutorial shows derivatives of unspecified order using tuple `(x, n)`. ([docs.sympy.org][1])

---

## 7.1.5 Implicit differentiation: `idiff`

```python id="vhz2nd"
from sympy import idiff

y = sp.Function("y")
# or use y as a Symbol depending on context
```

Use `idiff` when an equation implicitly defines one variable as a function of another. Keep separate from ordinary `diff` when symbolic dependence is implicit rather than encoded as `y(x)`.

Canonical pattern:

```python id="rdcjvm"
x, y = sp.symbols("x y")
eq = x**2 + y**2 - 1

dy_dx = sp.idiff(eq, y, x)
# -x/y
```

Deployment rule:

```text id="kkzqza"
Use idiff for implicit curves/surfaces.
Use Function('y')(x) when functional dependence must be explicit.
Use solve/dsolve when deriving full functions/solution families.
```

---

## 7.2 Integration

## 7.2.1 `integrate(f, *vars, **kwargs)`

Primary forms:

```python id="h2fs5j"
sp.integrate(expr, x)                         # indefinite
sp.integrate(expr, (x, a, b))                 # definite
sp.integrate(expr, (x, a, b), (y, c, d))      # multiple
sp.integrate(expr)                            # univariate shortcut
sp.integrate(expr, x, risch=True)
sp.integrate(expr, (x, 0, sp.oo), conds="piecewise")
sp.integrate(expr, (x, 0, sp.oo), conds="separate")
sp.integrate(expr, (x, 0, sp.oo), conds="none")
```

`integrate()` computes definite or indefinite integrals. Indefinite integration takes a symbol; definite integration takes a tuple `(symbol, lower, upper)`; multiple variables perform multiple integration. If an integrand is univariate and the variable is omitted, SymPy may integrate over the single variable. ([docs.sympy.org][3])

Examples:

```python id="xwduka"
sp.integrate(sp.cos(x), x)
# sin(x)

sp.integrate(sp.exp(-x), (x, 0, sp.oo))
# 1

sp.integrate(sp.exp(-x**2 - y**2), (x, -sp.oo, sp.oo), (y, -sp.oo, sp.oo))
# pi
```

Indefinite integrals omit the constant of integration. SymPy’s tutorial explicitly states no constant is included; add one manually or solve a differential equation with `dsolve()` when an integration constant is required. ([docs.sympy.org][1])

```python id="m6x7h9"
C = sp.Symbol("C")
F = sp.integrate(sp.cos(x), x) + C
```

---

## 7.2.2 Unevaluated integral: `Integral`

```python id="rnh0m9"
I = sp.Integral(sp.log(x)**2, x)
J = sp.Integral(sp.exp(-x), (x, 0, sp.oo))
K = sp.Integral(sp.exp(-x**2 - y**2), (x, -sp.oo, sp.oo), (y, -sp.oo, sp.oo))
```

`Integral` represents an unevaluated integral. Evaluate with `.doit()`. If `integrate()` cannot compute an integral, it returns an unevaluated `Integral` object; the docs show `integrate(x**x, x)` returning `Integral(x**x, x)`. ([docs.sympy.org][1])

```python id="v6qy9k"
I = sp.Integral(sp.log(x)**2, x)
I.doit()
# x*log(x)**2 - 2*x*log(x) + 2*x
```

Object-phase pattern:

```python id="yvko64"
integral = sp.Integral(f(x), (x, 0, 1))     # preserve intent
closed = integral.doit()                    # symbolic evaluation
numeric = integral.evalf(50)                # numeric quadrature/eval
```

---

## 7.2.3 Convergence conditions: `conds`

For improper definite integrals, output can include convergence conditions. `conds="piecewise"` returns a `Piecewise` expression, `conds="separate"` returns `(result, condition)`, and `conds="none"` suppresses conditions. The official API reference documents these modes and notes the default is `piecewise`. ([docs.sympy.org][3])

```python id="zaz0n7"
a = sp.Symbol("a")

sp.integrate(x**a * sp.exp(-x), (x, 0, sp.oo))
# Piecewise((gamma(a + 1), re(a) > -1), (..., True))

sp.integrate(x**a * sp.exp(-x), (x, 0, sp.oo), conds="separate")
# (gamma(a + 1), re(a) > -1)

sp.integrate(x**a * sp.exp(-x), (x, 0, sp.oo), conds="none")
# gamma(a + 1)
```

Deployment rule:

```text id="l7k65h"
conds="piecewise":
  safest user-facing symbolic default.

conds="separate":
  best for programmatic condition extraction.

conds="none":
  only when external domain constraints are enforced elsewhere.
```

---

## 7.2.4 Integration algorithms and strategy

SymPy’s integration engine uses multiple strategies, including table/pattern approaches, polynomial/rational/trigonometric methods, partial Risch algorithm support, heuristic Risch, and Meijer G-function methods, especially for definite integrals and special-function outputs. ([docs.sympy.org][1])

Integration-specific APIs:

```python id="y3dbrq"
from sympy.integrals.manualintegrate import manualintegrate, integral_steps
from sympy.integrals.risch import risch_integrate

manualintegrate(sp.log(x), x)
risch_integrate(sp.exp(x)*sp.exp(sp.exp(x)), x)
```

Use profile:

```text id="ft0mfw"
integrate:
  general-purpose, best first-line API

Integral(...).doit:
  delayed computation / object workflow

manualintegrate:
  educational/manual-step-oriented, less broad than integrate

risch_integrate:
  elementary integration decision-procedure workflows

numeric Integral.evalf:
  symbolic integration impractical but numeric value needed
```

---

## 7.2.5 Numeric integration: `Integral.evalf(n)`

```python id="rih6wu"
integral = sp.Integral(sp.sqrt(2)*x, (x, 0, 1))

integral.evalf()
integral.evalf(50)
```

SymPy can numerically evaluate definite integrals using its numeric evaluation stack; the tutorial shows `Integral(sqrt(2)*x, (x, 0, 1)).evalf(50)` producing a high-precision numeric value and notes numeric integration is useful when symbolic integration is impractical or impossible. ([docs.sympy.org][1])

Examples:

```python id="x77l4u"
sp.Integral(sp.exp(-x**2), (x, -sp.oo, sp.oo)).evalf()
# 1.77245385090552

sp.Integral(1/sp.sqrt(x), (x, 0, 1)).evalf()
# 2.00000000000000
```

Deployment rule:

```text id="cb2bcv"
Use Integral.evalf for one-off/high-precision scalar quadrature.
Use scipy/mpmath directly for many numeric integrals or adaptive numerical workflows.
Use symbolic integrate first if exact closed form is valuable.
```

---

## 7.2.6 Approximate integration via `Integral.as_sum`

```python id="x4l983"
I = sp.Integral(sp.sin(x), (x, 3, 7))

I.as_sum(2, method="left")
I.as_sum(2, method="right")
I.as_sum(2, method="midpoint")
I.as_sum(2, method="trapezoid")
I.as_sum(n, method="midpoint", evaluate=False)
```

`Integral.as_sum(n=None, method='midpoint', evaluate=True)` approximates a definite integral by a Riemann-style sum. Supported methods are `left`, `right`, `midpoint`, and `trapezoid`; `evaluate=False` returns an unevaluated `Sum`. The docs also warn that discontinuities can make left/trapezoid approximations diverge where midpoint/right avoid the endpoint singularity. ([docs.sympy.org][3])

Use cases:

```text id="a2af10"
derive quadrature formulas
symbolic error analysis
generate approximate integration kernels
pedagogical output
convert Integral → Sum for discrete approximations
```

---

## 7.2.7 Principal value and change of variables

```python id="qzgagp"
I = sp.Integral(1/x**3, (x, -sp.oo, sp.oo))
I.principal_value()
# 0

J = sp.Integral(expr, (x, a, b))
J.transform(x, u_expr)
```

`Integral.principal_value()` computes Cauchy principal values for real definite integrals on the real axis. `Integral.transform(x, u)` performs change of variables / u-substitution when the mapping is suitable and unique; docs note linear/rational-linear forms and `sqrt(x)` generally work, while more ambiguous transformations can fail or return unchanged. ([docs.sympy.org][3])

Deployment rule:

```text id="rkneay"
Use principal_value only for mathematically intended CPV semantics.
Do not treat CPV as ordinary convergence.
Use transform for symbolic change-of-variable workflows; verify result equivalence.
```

---

## 7.2.8 Integral transforms

Core APIs:

```python id="p1fbv9"
sp.mellin_transform(f(x), x, s)
sp.inverse_mellin_transform(F(s), s, x, strip)

sp.laplace_transform(f(t), t, s)
sp.inverse_laplace_transform(F(s), s, t)

sp.fourier_transform(f(x), x, k)
sp.inverse_fourier_transform(F(k), k, x)

sp.sine_transform(f(x), x, k)
sp.cosine_transform(f(x), x, k)
sp.hankel_transform(f(r), r, k, nu)
```

SymPy has special support for definite integrals and integral transforms. Transform functions can return tuples containing transform result, convergence strip/conditions, or unevaluated transform objects when closed forms cannot be computed. For example, `mellin_transform(exp(-x), x, s)` returns `(gamma(s), (0, oo), True)`, and many transform APIs return unevaluated transform objects on failure. ([docs.sympy.org][3])

Deployment rule:

```text id="a4f4mu"
Use transform APIs for signal/control/PDE/special-function workflows.
Preserve convergence conditions.
Expect unevaluated Transform objects; handle or reject before codegen.
Pin transform convention: SymPy Fourier transform uses ordinary-frequency/unitary convention.
```

---

## 7.3 Limits

## 7.3.1 `limit(e, z, z0, dir='+')`

```python id="ui0y4g"
sp.limit(expr, x, x0)
sp.limit(expr, x, x0, dir="+")
sp.limit(expr, x, x0, dir="-")
sp.limit(expr, x, x0, dir="+-")
sp.limit(expr, x, sp.oo)
sp.limit(expr, x, -sp.oo)
```

`limit(e, z, z0, dir='+')` computes the limit of `e` as `z` approaches `z0`; other symbols are constants, and multivariate limits are not supported by this API. Direction defaults to right-hand `+`; `dir='-'` is left-hand; `dir='+-'` is bidirectional; for infinite points, direction is determined by infinity. ([docs.sympy.org][4])

Examples:

```python id="b66f3e"
sp.limit(sp.sin(x)/x, x, 0)
# 1

sp.limit(1/x, x, 0, dir="+")
# oo

sp.limit(1/x, x, 0, dir="-")
# -oo

sp.limit(1/x, x, 0, dir="+-")
# zoo

sp.limit(x**2/sp.exp(x), x, sp.oo)
# 0
```

Use `limit()` instead of `.subs()` at singularities and infinity. The tutorial explicitly warns that substituting `oo` is unreliable because infinities do not preserve rate-of-growth information; e.g. `x**2/exp(x)).subs(x, oo)` gives `nan`, while `limit(x**2/exp(x), x, oo)` gives `0`. ([docs.sympy.org][1])

---

## 7.3.2 Unevaluated limit: `Limit`

```python id="xgjth6"
L = sp.Limit((sp.cos(x) - 1)/x, x, 0)
L_minus = sp.Limit(1/x, x, 0, dir="-")

L.doit()
```

`Limit` represents an unevaluated limit and evaluates with `.doit()`. Its `.doit(deep=True)` method can recursively call `.doit()` on inner expressions before taking the limit. ([docs.sympy.org][1])

Use cases:

```text id="gnrkwm"
delayed limit evaluation
limit objects in derivations/proofs
print/LaTeX preservation
custom limit-stage pipelines
```

---

## 7.3.3 Gruntz algorithm and heuristic path

`limit()` first tries heuristics for frequent/easy cases and otherwise uses the Gruntz algorithm. The series documentation describes Gruntz as the workhorse for many nontrivial limits and notes it relies heavily on series expansion; `gruntz()` can be called directly but `limit()` is the normal public API. ([docs.sympy.org][4])

```python id="ciq1un"
from sympy.series.gruntz import gruntz

gruntz(expr, x, sp.oo)
```

Deployment rule:

```text id="c6o31b"
Use limit() first.
Use gruntz() only for diagnostics or specialized asymptotic limit work.
For multivariate limits, do not assume iterated limits equal joint limits.
```

---

## 7.4 Series expansions

## 7.4.1 Method form: `expr.series(x, x0=0, n=6, dir='+')`

```python id="wpdce8"
expr.series(x)
expr.series(x, 0, 6)
expr.series(x, x0=2, n=5)
expr.series(x, 0, 4, dir="+")
expr.series(x, 0, 4, dir="-")
expr.series(x, sp.oo, 4)
```

SymPy computes asymptotic series expansions around a point. The tutorial states the method form is `f(x).series(x, x0, n)`, with defaults `x0=0` and `n=6`; the final `O(...)` term is a Landau order term representing omitted powers. ([docs.sympy.org][1])

```python id="op91ht"
expr = sp.exp(sp.sin(x))

expr.series(x, 0, 4)
# 1 + x + x**2/2 + O(x**4)

expr.series(x, 0, 4).removeO()
# x**2/2 + x + 1
```

Do not drop `O(...)` prematurely if later multiplication/addition needs truncation correctness.

---

## 7.4.2 Function wrapper: `series(expr, x=None, x0=0, n=6, dir='+')`

```python id="bywt66"
sp.series(sp.cos(x), x)
sp.series(sp.tan(x), x, 2, 6, "+")
sp.series(sp.tan(x), x, 2, 3, "-")
```

`series(expr, x=None, x0=0, n=6, dir='+')` is a wrapper around `Basic.series()`; it expands `expr` around `x=x0`, with `x0` allowed from `-oo` to `oo`, `n` as the number/order cutoff, and `dir` selecting right/left direction. For infinite expansion points, direction is inferred from the infinity. ([docs.sympy.org][4])

Important parameter semantics:

```text id="dfrh7d"
x:
  expansion variable

x0:
  expansion point

n:
  truncation order / number of terms up to order
  must be integer-like; oo as n is invalid

dir:
  "+" for x → x0+
  "-" for x → x0-
```

---

## 7.4.3 `Order` / `O`

```python id="ufovrl"
sp.O(x**4)
sp.O(x**4, (x, 0))
sp.O((x - 2)**3, (x, 2))
sp.O(x, (x, sp.oo))
```

`Order` represents limiting behavior in Landau big-O notation. It automatically absorbs higher-order terms; e.g. `x + x**3 + x**6 + O(x**4)` becomes `x + x**3 + O(x**4)`. The docs define `Order` as representing limiting behavior about a point and show multivariate and infinity-point behavior. ([docs.sympy.org][1])

```python id="w0yu8q"
x + x**3 + x**6 + sp.O(x**4)
# x + x**3 + O(x**4)

x * sp.O(1)
# O(x)

sp.O(x) * x
# O(x**2)

sp.O(x**2) in sp.O(x)
# True
```

Deployment rule:

```text id="qhbbxl"
Keep O terms during algebraic manipulation.
Use removeO only at final polynomial/numeric/codegen boundary.
Test truncation order explicitly after removeO.
```

---

## 7.4.4 Leading term / asymptotic extraction

```python id="jiznt1"
expr.as_leading_term(x)
sp.series(expr, x, sp.oo, 3)
```

Use leading-term extraction and series at infinity for asymptotic comparisons, dominant-balance analysis, and limit preprocessing. `Order` at infinity behaves differently from order at zero; the docs show `O(x + x**2, (x, oo)) -> O(x**2, (x, oo))`. ([docs.sympy.org][4])

Pattern:

```python id="gv7jk7"
def asymptotic_polynomial(expr, x, x0=0, n=6):
    return sp.series(expr, x, x0, n).removeO()
```

Guardrail: `removeO()` discards error control; only use when the target consumer expects a polynomial approximation.

---

## 7.5 Finite differences and approximations

## 7.5.1 `Derivative.as_finite_difference(points=1, x0=None, wrt=None)`

```python id="kh38fn"
f = sp.Function("f")
h = sp.Symbol("h")

f(x).diff(x).as_finite_difference()
f(x).diff(x).as_finite_difference(h)
f(x).diff(x).as_finite_difference([x, x + h, x + 2*h])
f(x, y).diff(x, y).as_finite_difference(wrt=x)
```

`Derivative.as_finite_difference()` converts an unevaluated derivative to a finite-difference expression. `points` can be a sequence of grid points or a step size; `x0` selects the approximation point; `wrt` is required for some partial-derivative cases. The docs show default first derivative approximation as `-f(x - 1/2) + f(x + 1/2)` and arbitrary symbolic/non-equidistant point support. ([docs.sympy.org][2])

```python id="s2db0f"
dfdx = f(x).diff(x)

dfdx.as_finite_difference()
# -f(x - 1/2) + f(x + 1/2)

dfdx.as_finite_difference(h)
# -f(x - h/2)/h + f(x + h/2)/h

dfdx.as_finite_difference([x, x + h, x + 2*h])
# -3*f(x)/(2*h) + 2*f(x+h)/h - f(x+2*h)/(2*h)
```

---

## 7.5.2 `differentiate_finite(expr, *symbols, points=1, x0=None, wrt=None, evaluate=False)`

```python id="d6uhd2"
from sympy.calculus.finite_diff import differentiate_finite

differentiate_finite(f(x) + sp.sin(x), x, 2)
differentiate_finite(f(x, y), x, y)
differentiate_finite(f(x)*g(x).diff(x), x)
differentiate_finite(f(x)*g(x).diff(x), points=sp.Function("dx")(x))
```

`differentiate_finite()` differentiates an expression and replaces derivatives with finite-difference approximations. It supports partial derivatives and nonconstant discretization steps represented by undefined functions such as `dx(x)`. ([docs.sympy.org][5])

Use case:

```text id="eqkk3e"
symbolic PDE/ODE operator → finite-difference stencil
continuous model → discrete approximation
delayed derivative nodes → finite-difference kernel generation
```

---

## 7.5.3 `finite_diff_weights(order, x_list, x0=1)`

```python id="xyp14u"
from sympy.calculus.finite_diff import finite_diff_weights

weights = finite_diff_weights(1, [-sp.S(1)/2, sp.S(1)/2, sp.S(3)/2, sp.S(5)/2], 0)

weights[0][-1]  # interpolation / 0th derivative weights
weights[1][-1]  # first derivative weights
```

`finite_diff_weights()` generates weights for arbitrarily spaced one-dimensional grids for derivative orders from `0` through `order`. `order=0` corresponds to interpolation; returned lists include results for increasing derivative order and increasing subsets of `x_list`. Docs state the order of accuracy is at least `len(x_list) - order` if the grid is defined correctly, and recommend ordering points nearest-to-farthest from `x0` for better subset formulas. ([docs.sympy.org][5])

---

## 7.5.4 `apply_finite_diff(order, x_list, y_list, x0=0)`

```python id="n5fzxk"
from sympy.calculus.finite_diff import apply_finite_diff

x_list = [-3, 1, 2]
y_list = sp.symbols("a b c")

apply_finite_diff(1, x_list, y_list, 0)
# -3*a/20 - b/4 + 2*c/5
```

`apply_finite_diff()` directly builds a finite-difference approximation from `x_list`, corresponding function values `y_list`, and target `x0`. It can operate on numeric samples or symbolic indexed data. Docs warn to use only as many points as make sense around `x0` and explicitly mention Runge’s phenomenon. ([docs.sympy.org][5])

Deployment rule:

```text id="jsbzgd"
Finite difference generation:
  use exact Rational/S integers for symbolic stencil coefficients.
  use finite_diff_weights for reusable coefficient tables.
  use differentiate_finite for expression-level discretization.
  use apply_finite_diff for direct sample/value formulas.
  validate stencil consistency and order of accuracy numerically.
```

---

## 7.6 Residues, singularities, continuity-domain utilities

## 7.6.1 `residue(expr, x, x0)`

```python id="dty2vs"
sp.residue(1/x, x, 0)
# 1

sp.residue(1/x**2, x, 0)
# 0

sp.residue(2/sp.sin(x), x, 0)
# 2
```

`residue(expr, x, x0)` finds the coefficient of `1/(x - x0)` in the power-series expansion about `x0`; docs identify it as essential for the residue theorem. ([docs.sympy.org][4])

Use cases:

```text id="jahghr"
complex contour integration
Laurent-series coefficient extraction
singularity classification support
symbolic residue theorem calculations
```

---

## 7.6.2 `singularities(expr, x)`

```python id="mmzc2l"
sp.singularities(1/(x + 1), x)
# {-1}

sp.singularities(sp.log(x), x)
# {0}
```

`singularities()` returns singular points for univariate continuous real or complex functions in supported cases. Docs show examples for rational functions and logarithms and state currently supported functions are univariate continuous functions over real or complex domains. ([docs.sympy.org][5])

Use pattern:

```python id="s04i1u"
def reject_singular_point(expr, x, point):
    sing = sp.singularities(expr, x)
    if point in sing:
        raise ValueError(f"singular at {point}: {expr}")
```

---

## 7.6.3 `continuous_domain(f, symbol, domain)`

```python id="ppghbk"
from sympy.calculus.util import continuous_domain

domain = continuous_domain(expr, x, sp.S.Reals)
```

`continuous_domain()` returns the subset of a supplied domain on which an expression is continuous. Use before numeric quadrature, interval plotting, limit sampling, or generating code with domain restrictions. Its API is listed in the calculus utility module. ([docs.sympy.org][5])

---

## 7.7 Unevaluated calculus objects and `.doit()` policy

Unevaluated objects:

```python id="u6trvw"
sp.Derivative(expr, x)
sp.Integral(expr, x)
sp.Integral(expr, (x, a, b))
sp.Limit(expr, x, x0)
sp.Sum(expr, (n, 0, sp.oo))
sp.Product(expr, (n, 1, sp.oo))
sp.Subs(expr, x, a)
```

Evaluation:

```python id="c5d2rn"
obj.doit()
obj.doit(deep=False)
```

Design contract:

```text id="rm9eyh"
Use unevaluated objects to preserve mathematical intent.
Use .doit() at controlled phase boundaries.
Use .evalf() for numerical approximation of definite objects.
Detect unevaluated calculus nodes before lambdify/codegen.
```

Detection:

```python id="ird2yx"
CALCULUS_NODES = (sp.Derivative, sp.Integral, sp.Limit, sp.Sum, sp.Product)

def has_unevaluated_calculus(expr):
    expr = sp.sympify(expr)
    return any(expr.has(cls) for cls in CALCULUS_NODES)
```

---

## 7.8 Practical symbolic-derive → deploy workflow

SymPy’s numeric-computation docs recommend constructing/manipulating symbolic expressions in SymPy, then shipping them to numeric systems such as `math`, NumPy, CuPy, JAX, C, or Fortran. They also state `.subs(...).evalf()` is the slowest but simplest option and should be used in production only when performance is not an issue; `lambdify` generates numerical Python functions and supports backends such as `math`, `mpmath`, and NumPy. ([docs.sympy.org][6])

```python id="x0zzf6"
def derive_kernel():
    x = sp.Symbol("x", real=True)

    expr = sp.sin(x) * sp.exp(x**2)
    dexpr = sp.diff(expr, x)

    # targeted normalization
    dexpr = sp.factor(sp.together(dexpr))

    return x, dexpr


x, formula = derive_kernel()

# one-off scalar high precision
value = formula.evalf(50, subs={x: sp.Rational(1, 3)})

# repeated numeric execution
f_numpy = sp.lambdify(x, formula, modules="numpy")

# code string / compiled path later
c_expr = sp.ccode(formula)
```

For compiled numerical deployment, SymPy’s codegen/autowrap docs state that `autowrap` generates code, writes it to disk, compiles it, and imports a callable into the current session; `ufuncify` generates binary functions supporting NumPy-style broadcasting and can be faster than `subs/evalf` and `lambdify` for suitable array workflows. ([docs.sympy.org][7])

---

## 7.9 Agent decision matrix

| Task                         | API                                      | Output                               | Guardrails                                       |
| ---------------------------- | ---------------------------------------- | ------------------------------------ | ------------------------------------------------ |
| ordinary derivative          | `diff(expr, x)`                          | `Expr` or `Derivative` if unresolved | pass variables explicitly                        |
| higher derivative            | `diff(expr, x, n)`                       | `Expr` / `Derivative`                | symbolic `n` yields formal derivative            |
| mixed partial                | `diff(expr, x, y, 2)`                    | `Expr`                               | order matters for noncommutative/ambiguous cases |
| delayed derivative           | `Derivative(expr, x)`                    | unevaluated object                   | `.doit()` when ready                             |
| indefinite integral          | `integrate(expr, x)`                     | antiderivative / `Integral`          | no integration constant                          |
| definite integral            | `integrate(expr, (x,a,b))`               | value / `Piecewise` / `Integral`     | handle convergence conditions                    |
| delayed integral             | `Integral(expr, limits...)`              | unevaluated object                   | `.doit()` / `.evalf()`                           |
| improper integral conditions | `conds="separate"`                       | `(result, condition)`                | preserve condition in metadata                   |
| numeric integral             | `Integral(...).evalf(n)`                 | `Float`                              | scalar; not bulk quadrature pipeline             |
| limit at singularity         | `limit(expr, x, x0)`                     | limit value                          | use instead of `.subs()`                         |
| one-sided limit              | `limit(expr, x, x0, dir="+")`            | limit value                          | default is right-hand                            |
| series expansion             | `expr.series(x,x0,n)`                    | expression + `O(...)`                | keep/remove `O` deliberately                     |
| finite-difference derivative | `Derivative(...).as_finite_difference()` | stencil expression                   | specify grid/step                                |
| stencil weights              | `finite_diff_weights(order, grid, x0)`   | nested coefficient lists             | order grid nearest first                         |
| residue                      | `residue(expr,x,x0)`                     | coefficient                          | assumes Laurent/series mechanics                 |
| singularities                | `singularities(expr,x)`                  | set-like output                      | univariate supported cases                       |

---

## 7.10 Normalization profiles after calculus

## 7.10.1 After differentiation

```python id="cfk9yg"
def normalize_derivative(expr):
    expr = sp.sympify(expr)
    expr = sp.diff(expr, x)
    expr = sp.factor(sp.together(expr))
    return expr
```

Use:

```text id="dtzoj4"
factor/together:
  compact product/rational form

expand:
  coefficient extraction / polynomial matching

trigsimp:
  trig/hyperbolic derivative cleanup

cse:
  codegen after derivative expansion
```

---

## 7.10.2 After integration

```python id="dsel6p"
def normalize_integral_result(expr):
    expr = sp.sympify(expr)
    expr = sp.powsimp(expr, deep=True)
    expr = sp.logcombine(expr, force=False)
    expr = sp.factor(sp.together(expr))
    return expr
```

Guardrails:

```text id="dzbp2p"
Do not force log/power transforms without domain facts.
Do not drop Piecewise convergence conditions.
For indefinite integrals, manually add integration constant if required.
```

---

## 7.10.3 After series

```python id="uf3vsg"
def series_polynomial(expr, x, x0=0, order=6):
    return sp.series(expr, x, x0, order).removeO().expand()
```

Guardrails:

```text id="ygg9eq"
removeO only at final approximation boundary.
Track x0 and order in metadata.
Do not compare truncated series as exact formulas.
```

---

## 7.10.4 Before `lambdify` / codegen

```python id="ankqpy"
def prepare_calculus_expr_for_deployment(expr):
    expr = sp.sympify(expr)

    if has_unevaluated_calculus(expr):
        raise ValueError(f"unevaluated calculus object remains: {expr}")

    expr = sp.cancel(sp.together(expr))
    expr = sp.trigsimp(expr)
    expr = sp.powsimp(expr, combine="exp", deep=True, force=False)

    return expr
```

---

## 7.11 Anti-pattern inventory

| Anti-pattern                                | Failure mode                               | Correct pattern                                       |
| ------------------------------------------- | ------------------------------------------ | ----------------------------------------------------- |
| `diff(expr)` in library code                | ambiguous variable inference / error       | `diff(expr, x)`                                       |
| assuming indefinite integral includes `+ C` | missing constant in equations              | add `C` or use `dsolve`                               |
| suppressing integral conditions             | invalid formula outside convergence domain | `conds="separate"` or keep `Piecewise`                |
| `.subs(x, oo)` for limits                   | `nan`, no growth-rate reasoning            | `limit(expr, x, oo)`                                  |
| dropping `O(...)` early                     | invalid truncated algebra                  | keep `O`; `.removeO()` only at boundary               |
| treating `series` as equality               | approximation used as exact                | mark approximation metadata                           |
| using `evalf` in hot loop                   | SymPy-speed bottleneck                     | `lambdify` / `ufuncify` / codegen                     |
| unresolved `Derivative` in lambdify         | backend cannot evaluate                    | `.doit`, finite difference, or implementation mapping |
| broad finite-difference grid                | Runge / poor local approximation           | choose local grid near `x0`                           |
| ignoring singularities before quadrature    | `zoo`, divergent approximations            | `singularities` / `continuous_domain`                 |
| using CPV as ordinary integral              | hides divergence                           | call `.principal_value()` only intentionally          |
| assuming transform output only expression   | loses convergence strips/conditions        | parse tuple / unevaluated object                      |

---

## 7.12 Testing matrix

```python id="r6k8y3"
def assert_derivative(expr, x, expected):
    got = sp.diff(expr, x)
    assert sp.simplify(got - expected) == 0

def assert_antiderivative(F, f, x):
    assert sp.simplify(sp.diff(F, x) - f) == 0

def assert_definite_integral(expr, x, a, b, expected):
    got = sp.integrate(expr, (x, a, b))
    assert sp.simplify(got - expected) == 0

def assert_limit(expr, x, x0, expected, dir="+"):
    got = sp.limit(expr, x, x0, dir=dir)
    assert got == expected or sp.simplify(got - expected) == 0

def assert_series_matches(expr, x, x0, order):
    s = expr.series(x, x0, order)
    p = s.removeO()
    # residual should be absorbed by stated order
    residual = expr - p
    assert sp.O(residual, (x, x0)) in sp.O((x - x0)**order, (x, x0))
```

Recommended cases:

```text id="ow9ey8"
Differentiation:
  elementary, product/chain, mixed partial, undefined Function

Integration:
  elementary, failed integral -> Integral, improper with conditions, numeric evalf

Limits:
  singular finite point, one-sided, infinity, bidirectional

Series:
  around 0, around nonzero x0, at infinity, with removeO

Finite differences:
  uniform grid, nonuniform grid, partial derivative, symbolic h

Complex:
  residue at simple pole, double pole, removable singularity

Deployment:
  no unevaluated calculus nodes before lambdify/codegen
```

---

## 7.13 Minimal calculus harness

```python id="ga68ky"
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Iterable, Any

import sympy as sp
from sympy.calculus.finite_diff import (
    differentiate_finite,
    finite_diff_weights,
    apply_finite_diff,
)


CALCULUS_NODES = (sp.Derivative, sp.Integral, sp.Limit, sp.Sum, sp.Product)


@dataclass(frozen=True)
class CalculusAudit:
    expr: sp.Basic
    derivative_nodes: tuple[sp.Derivative, ...]
    integral_nodes: tuple[sp.Integral, ...]
    limit_nodes: tuple[sp.Limit, ...]
    has_unevaluated: bool
    free_symbols: set[sp.Symbol]
    operation_count: int


def audit_calculus(expr: Any) -> CalculusAudit:
    expr = sp.sympify(expr)
    return CalculusAudit(
        expr=expr,
        derivative_nodes=tuple(expr.atoms(sp.Derivative)),
        integral_nodes=tuple(expr.atoms(sp.Integral)),
        limit_nodes=tuple(expr.atoms(sp.Limit)),
        has_unevaluated=any(expr.has(cls) for cls in CALCULUS_NODES),
        free_symbols=set(expr.free_symbols),
        operation_count=int(sp.count_ops(expr)),
    )


def derivative(
    expr: sp.Expr,
    *vars: sp.Symbol | tuple[sp.Symbol, int],
    evaluate: bool = True,
) -> sp.Expr:
    if not vars:
        raise ValueError("explicit differentiation variables required")
    return sp.diff(sp.sympify(expr), *vars, evaluate=evaluate)


def delayed_derivative(expr: sp.Expr, *vars) -> sp.Derivative:
    if not vars:
        raise ValueError("explicit differentiation variables required")
    return sp.Derivative(sp.sympify(expr), *vars)


def antiderivative(expr: sp.Expr, x: sp.Symbol, *, add_constant: bool = False) -> sp.Expr:
    F = sp.integrate(sp.sympify(expr), x)
    if add_constant:
        C = sp.Symbol("C")
        F = F + C
    return F


def definite_integral(
    expr: sp.Expr,
    x: sp.Symbol,
    a: sp.Expr,
    b: sp.Expr,
    *,
    conds: Literal["piecewise", "separate", "none"] = "piecewise",
) -> sp.Expr:
    return sp.integrate(sp.sympify(expr), (x, a, b), conds=conds)


def delayed_integral(expr: sp.Expr, *limits) -> sp.Integral:
    return sp.Integral(sp.sympify(expr), *limits)


def numeric_integral(expr: sp.Expr, *limits, digits: int = 50) -> sp.Expr:
    return sp.Integral(sp.sympify(expr), *limits).evalf(digits)


def limit_at(
    expr: sp.Expr,
    x: sp.Symbol,
    x0: sp.Expr,
    *,
    direction: Literal["+", "-", "+-"] = "+",
) -> sp.Expr:
    return sp.limit(sp.sympify(expr), x, x0, dir=direction)


def delayed_limit(
    expr: sp.Expr,
    x: sp.Symbol,
    x0: sp.Expr,
    *,
    direction: Literal["+", "-", "+-"] = "+",
) -> sp.Limit:
    return sp.Limit(sp.sympify(expr), x, x0, dir=direction)


def series_with_order(
    expr: sp.Expr,
    x: sp.Symbol,
    x0: sp.Expr = sp.S.Zero,
    order: int = 6,
    *,
    direction: Literal["+", "-"] = "+",
) -> sp.Expr:
    return sp.series(sp.sympify(expr), x, x0, order, dir=direction)


def series_polynomial(
    expr: sp.Expr,
    x: sp.Symbol,
    x0: sp.Expr = sp.S.Zero,
    order: int = 6,
    *,
    direction: Literal["+", "-"] = "+",
) -> sp.Expr:
    return series_with_order(expr, x, x0, order, direction=direction).removeO().expand()


def finite_difference_derivative(
    expr: sp.Expr,
    *vars,
    points: Any = 1,
    x0: Any = None,
    wrt: sp.Symbol | None = None,
) -> sp.Expr:
    return differentiate_finite(sp.sympify(expr), *vars, points=points, x0=x0, wrt=wrt)


def derivative_as_stencil(
    derivative_obj: sp.Derivative,
    *,
    points: Any = 1,
    x0: Any = None,
    wrt: sp.Symbol | None = None,
) -> sp.Expr:
    if not isinstance(derivative_obj, sp.Derivative):
        raise TypeError("expected Derivative")
    return derivative_obj.as_finite_difference(points=points, x0=x0, wrt=wrt)


def fd_weights(order: int, x_list: Iterable[Any], x0: Any = sp.S.One):
    return finite_diff_weights(order, list(x_list), x0)


def fd_apply(order: int, x_list: Iterable[Any], y_list: Iterable[Any], x0: Any = sp.S.Zero):
    return apply_finite_diff(order, list(x_list), list(y_list), x0)


def residue_at(expr: sp.Expr, x: sp.Symbol, x0: sp.Expr) -> sp.Expr:
    return sp.residue(sp.sympify(expr), x, x0)


def singular_points(expr: sp.Expr, x: sp.Symbol):
    return sp.singularities(sp.sympify(expr), x)


def normalize_calculus_output(expr: sp.Expr) -> sp.Expr:
    expr = sp.sympify(expr)
    expr = sp.cancel(sp.together(expr))
    expr = sp.trigsimp(expr)
    expr = sp.powsimp(expr, combine="exp", deep=True, force=False)
    return expr


def prepare_for_numeric_backend(expr: sp.Expr) -> sp.Expr:
    expr = normalize_calculus_output(expr)
    remaining = audit_calculus(expr)

    if remaining.has_unevaluated:
        raise ValueError(
            "unevaluated calculus nodes remain: "
            f"Derivative={remaining.derivative_nodes}, "
            f"Integral={remaining.integral_nodes}, "
            f"Limit={remaining.limit_nodes}"
        )

    return expr
```

This harness enforces explicit-variable differentiation, controlled unevaluated-object phases, convergence-condition awareness, series truncation discipline, finite-difference generation, residue/singularity utilities, and pre-deployment rejection of unresolved calculus nodes.

[1]: https://docs.sympy.org/latest/tutorials/intro-tutorial/calculus.html "Calculus - SymPy 1.14.0 documentation"
[2]: https://docs.sympy.org/latest/modules/core.html "Core - SymPy 1.14.0 documentation"
[3]: https://docs.sympy.org/latest/modules/integrals/integrals.html "Integrals - SymPy 1.14.0 documentation"
[4]: https://docs.sympy.org/latest/modules/series/series.html "Series Expansions - SymPy 1.14.0 documentation"
[5]: https://docs.sympy.org/latest/modules/calculus/index.html "Calculus - SymPy 1.14.0 documentation"
[6]: https://docs.sympy.org/latest/modules/numeric-computation.html?utm_source=chatgpt.com "Numeric Computation - SymPy 1.14.0 documentation"
[7]: https://docs.sympy.org/latest/modules/codegen.html?utm_source=chatgpt.com "Code Generation - SymPy 1.14.0 documentation"

# 8) Solving: equations, systems, inequalities, ODEs, PDEs, roots — agent-ready deep dive

SymPy’s solving layer is not one API. It is a **solver family**: legacy generalized `solve`, set-oriented `solveset`, linear-system `linsolve`, nonlinear-system `nonlinsolve`, numerical `nsolve`, differential-equation `dsolve`/`pdsolve`, inequality `reduce_inequalities`, integer-domain `diophantine`, and polynomial-root APIs. Official SymPy guidance explicitly warns that `solve()` may or may not be the right function and recommends selecting a task-specific solver when the problem class is known. ([SymPy Docs][1])

```python id="4p01qc"
import sympy as sp

x, y, z = sp.symbols("x y z")
a, b, c = sp.symbols("a b c")
n = sp.symbols("n", integer=True)
f = sp.Function("f")
```

---

## 8.0 Solver selection map

| Problem class                                |                                Preferred API | Output model                                               | Primary value                                     |
| -------------------------------------------- | -------------------------------------------: | ---------------------------------------------------------- | ------------------------------------------------- |
| univariate algebraic/transcendental equation |                `solveset(eq, x, domain=...)` | `Set`, `FiniteSet`, `ImageSet`, `ConditionSet`, `EmptySet` | mathematically explicit solution set              |
| general legacy algebraic solving             |                `solve(eqs, vars, dict=True)` | list/dict/tuple/etc.; normalize with `dict=True`           | broad compatibility / mature heuristics           |
| linear equation system                       |                  `linsolve(system, symbols)` | `FiniteSet` of ordered tuples / `EmptySet`                 | exact linear algebra, parametric systems          |
| symbolic matrix equation `A*x=b`             |                 `A.solve(b)`, `A.LUsolve(b)` | `Matrix`                                                   | direct matrix solve, repeated RHS support         |
| nonlinear equation system                    |               `nonlinsolve(system, symbols)` | `FiniteSet` of ordered tuples                              | exact solution sets, positive-dimensional systems |
| numerical scalar/system solve                |                   `nsolve(f, vars, x0, ...)` | number / `Matrix`                                          | approximate roots with initial guess              |
| ODE                                          |                 `dsolve(eq, func, hint=...)` | `Eq` / list / dict for `hint="all"`                        | closed-form ODE solving                           |
| PDE                                          |                `pdsolve(eq, func, hint=...)` | `Eq`                                                       | limited PDE classes                               |
| inequality / inequality system               |              `reduce_inequalities(exprs, x)` | Boolean relational expression                              | algebraic inequality reduction                    |
| Diophantine integer equation                 |                            `diophantine(eq)` | set of tuples with parameters                              | integer-solution families                         |
| polynomial roots exact                       | `roots`, `all_roots`, `real_roots`, `RootOf` | dict/list/exact root objects                               | multiplicities / exact algebraic roots            |
| polynomial roots numeric                     |                                     `nroots` | list of approximations                                     | all approximate roots of polynomial               |

---

## 8.1 Equation input conventions

Most algebraic solvers accept either an expression interpreted as equal to zero or an explicit `Eq(lhs, rhs)`. The solving guide shows both `solve(x**2 - y, x, dict=True)` and `solveset(x**2 - y, x)` as ordinary algebraic equation workflows. ([SymPy Docs][2])

```python id="2gvwts"
eq_expr = x**2 - y          # interpreted as x**2 - y == 0
eq_obj = sp.Eq(x**2, y)     # explicit equation object
```

Agent rule:

```text id="hkvwzj"
For equations:
  use Eq(lhs, rhs) when preserving equation semantics matters.
  use lhs - rhs when building solver-ready normalized expressions.

For systems:
  pass list/tuple of expressions or Eq objects.
  always pass symbols explicitly and in desired output order.
```

---

## 8.2 `solve`: broad legacy solver

## 8.2.1 Syntax

```python id="tpqs3h"
sp.solve(expr, x)
sp.solve(sp.Eq(lhs, rhs), x)
sp.solve([eq1, eq2], [x, y])
sp.solve([eq1, eq2], [x, y], dict=True)
sp.solve([eq1, eq2], [x, y], set=True)
sp.solve(expr, x, check=True)
```

`solve()` is the older, mature, general-purpose facade. Official docs describe it as a general solver with many options that internally selects different methods; if the equation type is known, the docs recommend using more specialized APIs such as `solveset`, `linsolve`, and `nonlinsolve`. ([SymPy Docs][3])

```python id="sfhxy9"
sp.solve(x**2 - 1, x)
# [-1, 1]

sp.solve([x + y - 2, x - y + 2], [x, y])
# {x: 0, y: 2}

sp.solve([x**2 - y, x + y - 6], [x, y], dict=True)
# [{x: -3, y: 9}, {x: 2, y: 4}]
```

## 8.2.2 Deployment contract

```text id="abqv4q"
Use solve when:
  - broad heuristic solving is acceptable;
  - compatibility with legacy examples matters;
  - solving mixed symbolic expressions interactively;
  - dict=True can normalize output enough for your code.

Avoid raw solve output when:
  - programmatic return shape stability matters;
  - all-solution set semantics are needed;
  - domain-specific solve class is known.
```

Always prefer:

```python id="s310ll"
sols = sp.solve(eqs, vars, dict=True)
```

because `solve()` has historically human-interaction-biased output shapes. Official solve-output docs state that output can appear to be one of several types and depends on input form, provided symbols, and flags; `dict=True` and `set=True` control output format. ([SymPy Docs][4])

---

## 8.3 `solve` return-shape taxonomy

Official docs enumerate solve-output classes: empty list, list of values, single dictionary, list of tuples, list of dictionaries, and Boolean/Relational output for inequalities/relations. ([SymPy Docs][4])

| Input shape                      | Raw `solve` output            | Safer option                                                 |
| -------------------------------- | ----------------------------- | ------------------------------------------------------------ |
| no solution                      | `[]`                          | `dict=True` still `[]`; `set=True` gives symbols + empty set |
| univariate / single symbol       | `[-2, 2]`                     | `dict=True -> [{x: -2}, {x: 2}]`                             |
| linear system list               | `{x: 0, y: 2}`                | `dict=True -> [{x: 0, y: 2}]`                                |
| nonlinear system ordered symbols | `[(...), (...)]`              | `dict=True -> [{...}, {...}]`                                |
| ambiguous nonlinear/multivariate | `[{x: ...}, ...]`             | already dict-list-like                                       |
| inequality input                 | Boolean relational expression | prefer `reduce_inequalities`                                 |

Normalization helper:

```python id="w312he"
def solve_dicts(eqs, symbols):
    out = sp.solve(eqs, symbols, dict=True)
    if out is None:
        return []
    if isinstance(out, dict):
        return [out]
    return list(out)
```

---

## 8.4 `solveset`: set-oriented univariate solver

## 8.4.1 Syntax

```python id="t6s914"
sp.solveset(expr, x)
sp.solveset(sp.Eq(lhs, rhs), x)
sp.solveset(expr, x, domain=sp.S.Complexes)
sp.solveset(expr, x, domain=sp.S.Reals)

sp.solveset(sp.sin(x), x, domain=sp.S.Reals)
```

`solveset(equation, variable=None, domain=S.Complexes)` solves univariate equations over an explicit domain. It returns a SymPy `Set`; if it cannot represent all solutions, it can return a `ConditionSet`. The docs emphasize that `solveset` has a consistent input/output interface, returns a `Set`, supports infinitely many solutions, and separates real vs complex domains. ([SymPy Docs][5])

```python id="djxyph"
sp.solveset(x**2 - 1, x)
# {-1, 1}

sp.solveset(sp.exp(x) - 1, x, domain=sp.S.Complexes)
# ImageSet-like infinite complex solution set

sp.solveset(sp.exp(x) - 1, x, domain=sp.S.Reals)
# {0}
```

## 8.4.2 Return handling

```python id="02fc2o"
sol = sp.solveset(x**2 - 2, x, domain=sp.S.Reals)

if sol is sp.S.EmptySet:
    ...
elif isinstance(sol, sp.FiniteSet):
    values = list(sol)
elif isinstance(sol, sp.ConditionSet):
    raise NotImplementedError(f"unsolved condition set: {sol}")
else:
    # Interval, ImageSet, Union, etc.
    ...
```

Deployment rule:

```text id="fl9b8c"
Use solveset for mathematically precise univariate solution sets.
Always inspect Set type before enumerating.
Do not assume finite output.
Choose domain explicitly.
Reject or preserve ConditionSet.
```

---

## 8.5 Linear systems: `linsolve`

## 8.5.1 Syntax

```python id="5pvu20"
sp.linsolve([eq1, eq2], x, y)
sp.linsolve([eq1, eq2], [x, y])
sp.linsolve((A, b), x, y, z)
sp.linsolve(augmented_matrix, x, y, z)
```

`linsolve()` solves `N` linear equations in `M` variables, supports underdetermined and overdetermined systems, and returns a `FiniteSet` containing an ordered tuple of solution values; inconsistent systems return `EmptySet`. Infinite solutions are represented parametrically in terms of the supplied symbols. It uses Gauss-Jordan elimination and supports equation-list, augmented-matrix, and `(A, b)` input forms. ([SymPy Docs][6])

```python id="k54f29"
A = sp.Matrix([[1, 2, 3],
               [4, 5, 6],
               [7, 8, 10]])
bvec = sp.Matrix([3, 6, 9])

sp.linsolve((A, bvec), x, y, z)
# {(-1, 2, 0)}
```

Underdetermined:

```python id="jj51xf"
A = sp.Matrix([[1, 2, 3],
               [4, 5, 6],
               [7, 8, 9]])
bvec = sp.Matrix([3, 6, 9])

sp.linsolve((A, bvec), x, y, z)
# {(z - 1, 2 - 2*z, z)}
```

Nonlinearity is an error, even if removable by simplification; docs state simplification required to eliminate nonlinear terms must happen before calling `linsolve`. ([SymPy Docs][6])

```python id="3vztye"
eqs = [sp.cancel(x*(1/x - 1))]
sp.linsolve(eqs, x)
```

## 8.5.2 Extraction helper

```python id="fpssem"
def one_tuple_from_finiteset(fs):
    if fs is sp.S.EmptySet:
        return None
    if not isinstance(fs, sp.FiniteSet):
        raise TypeError(type(fs))
    if len(fs) != 1:
        raise ValueError(f"expected one solution tuple, got {fs}")
    return next(iter(fs))
```

---

## 8.6 Matrix equation solving

## 8.6.1 Syntax

```python id="mwe9p5"
A.solve(b)
A.solve(b, method="LU")
A.LUsolve(b)
A.gauss_jordan_solve(b)
A.inv() * b
```

For matrix equations in standard form `A*x=b`, SymPy’s matrix guide uses `MatrixBase.solve()`; by default Gauss-Jordan elimination is used, `method='LU'` calls `LUsolve()`, and for repeated right-hand sides with the same matrix, decomposition-based methods such as `LUsolve()` are more efficient. If the matrix and vector are purely numeric rather than symbolic, the guide suggests numeric libraries such as NumPy, SciPy, or mpmath as alternatives. ([SymPy Docs][7])

```python id="r9a8yw"
c, d, e = sp.symbols("c d e")

A = sp.Matrix([[c, d], [1, -e]])
bvec = sp.Matrix([2, 0])

A.solve(bvec)
A.LUsolve(bvec)
```

Deployment rule:

```text id="jrz3xy"
Use Matrix.solve/LUsolve for explicit symbolic matrices.
Use linsolve for equation-system semantics and parametric output.
Use NumPy/SciPy/mpmath for numeric dense/sparse linear algebra at scale.
Cache decompositions for repeated RHS if possible.
```

---

## 8.7 Nonlinear systems: `nonlinsolve`

## 8.7.1 Syntax

```python id="eh07bl"
sp.nonlinsolve([eq1, eq2], [x, y])
sp.nonlinsolve([eq1, eq2, eq3], [x, y, z])
```

`nonlinsolve()` solves systems of nonlinear equations, supports underdetermined and overdetermined systems, and supports positive-dimensional systems where solutions depend on at least one symbol. It returns a `FiniteSet` of ordered tuples whose tuple order matches the provided symbol sequence; it can include real and complex solutions. ([SymPy Docs][6])

```python id="hjluru"
sol = sp.nonlinsolve([x*y - 1, 4*x**2 + y**2 - 5], [x, y])
# {(-1, -1), (-1/2, -2), (1/2, 2), (1, 1)}
```

Positive-dimensional systems can return parametric tuples:

```python id="5olpl5"
sol = sp.nonlinsolve([x*y], [x, y])
# may contain solution components with free parameters / symbolic conditions
```

Deployment rule:

```text id="dsa46o"
Use nonlinsolve for exact nonlinear systems.
Always pass symbols as an ordered sequence.
Expect FiniteSet of ordered tuples, not dictionaries.
Handle parameters, ImageSets, complements, and complex branches.
For numeric-only need, use nsolve.
```

---

## 8.8 Numerical solving: `nsolve`

## 8.8.1 Syntax

```python id="e7m26f"
sp.nsolve(f_expr, x0)
sp.nsolve(f_expr, x, x0)
sp.nsolve((f1, f2), (x1, x2), (x10, x20))
sp.nsolve(f_expr, x0, prec=50)
sp.nsolve(f_expr, x0, verify=False)
sp.nsolve(f_expr, (a, b), solver="bisect")
```

`nsolve()` numerically solves one equation or a system and requires an initial guess or interval. For one-dimensional functions, the variable can be omitted in simplified syntax; systems return a `Matrix`; higher precision is controlled with `prec`; complex roots of real functions require a non-real initial point. The docs also note overdetermined systems are supported. ([SymPy Docs][3])

```python id="p1dg1f"
sp.nsolve(sp.cos(x) - x, 1)
# 0.739085133215161

sp.nsolve(sp.cos(x) - x, 1, prec=50)

sp.nsolve((3*x**2 - 2*y**2 - 1,
           x**2 - 2*x + y**2 + 2*y - 8),
          (x, y),
          (-1, 1))
# Matrix([...])
```

Complex root:

```python id="uvv682"
sp.nsolve(x**2 + 2, sp.I)
# 1.4142135623731*I
```

## 8.8.2 Verification and residual checking

Docs show that `verify=False` can bypass the final verification but may return values with huge residuals unless the method/interval justifies it; one safe skip case is when bounds of the root are known and a bisection method is used. ([SymPy Docs][3])

```python id="6hzji4"
root = sp.nsolve(sp.cos(x) - x, 1, prec=50)
residual = (sp.cos(x) - x).subs(x, root).evalf(30)
```

Production wrapper:

```python id="ls7loo"
def nsolve_checked(expr, var, guess, *, prec=50, tol=sp.S("1e-40")):
    root = sp.nsolve(expr, var, guess, prec=prec)
    residual = abs(sp.N(expr.subs(var, root), prec))
    if residual > tol:
        raise ValueError(f"large residual: root={root}, residual={residual}")
    return root
```

Deployment rule:

```text id="e9oreu"
Use nsolve when:
  - only numeric solution needed;
  - closed form unavailable or too complex;
  - initial guess/interval is known.

Do not use nsolve as all-roots finder.
Scan/bracket roots or use polynomial nroots where appropriate.
Always residual-check in production.
```

Official solving guidance says `solve()`/`solveset()` seek mathematically exact symbolic solutions and will not try to find numeric solutions; use `nsolve()` when numeric solving is desired. ([SymPy Docs][8])

---

## 8.9 ODE solving: `dsolve`

## 8.9.1 Syntax

```python id="neel70"
sp.dsolve(ode)
sp.dsolve(ode, f(x))
sp.dsolve(ode, f(x), hint="default")
sp.dsolve(ode, f(x), hint="all")
sp.dsolve(ode, f(x), ics={f(0): 1})
sp.classify_ode(ode, f(x))
sp.checkodesol(ode, sol)
```

`dsolve()` solves ordinary differential equations. With `hint="all"`, it applies all relevant classification hints and returns a dictionary mapping hints to solutions or exceptions, plus metadata such as `order`, `best`, `best_hint`, and `default`; `all_Integral` avoids evaluating expensive integrals for hints that have an integral form. ([SymPy Docs][9])

```python id="w9617b"
f = sp.Function("f")
ode = sp.Eq(sp.diff(f(x), x), f(x))

sol = sp.dsolve(ode, f(x))
# Eq(f(x), C1*exp(x))

sp.checkodesol(ode, sol)
# (True, 0)
```

Initial conditions:

```python id="71updw"
ode = sp.Eq(sp.diff(f(x), x), f(x))
sp.dsolve(ode, f(x), ics={f(0): 2})
# Eq(f(x), 2*exp(x))
```

Classification:

```python id="b7h9je"
hints = sp.classify_ode(ode, f(x))
```

Deployment rule:

```text id="4bwrjp"
Use dsolve for symbolic ODE solution.
Use classify_ode before selecting hints in automated systems.
Use hint="all" for diagnostics, not routine production.
Use all_Integral if hint="all" hangs on hard integrals.
Always verify with checkodesol.
For numeric ODE simulation, hand off to SciPy/mpmath after deriving equations.
```

---

## 8.10 PDE solving: `pdsolve`

## 8.10.1 Syntax

```python id="ujqu97"
from sympy.solvers.pde import pdsolve, classify_pde, pde_separate

u = f(x, y)
eq = x*u.diff(x) - y*u.diff(y) + y**2*u - y**2

pdsolve(eq)
classify_pde(eq, f(x, y))
```

The PDE module contains `pdsolve`, `classify_pde`, and separation helpers; docs state it is inspired by the ODE module and currently implements selected first-order linear homogeneous/general PDE methods with constant coefficients and first-order linear PDEs with variable coefficients. ([SymPy Docs][10])

```python id="na193y"
f = sp.Function("f")
u = f(x, y)

eq = x*u.diff(x) - y*u.diff(y) + y**2*u - y**2
sp.pdsolve(eq)
# Eq(f(x, y), F(x*y)*exp(y**2/2) + 1)
```

Deployment rule:

```text id="rxjapm"
Use pdsolve for limited exact PDE classes.
Expect NotImplementedError or unevaluated/unsupported cases.
Use classify_pde for solver-routing diagnostics.
For general PDE numerics, derive symbolically then discretize/hand off.
```

---

## 8.11 Inequalities: `reduce_inequalities`

## 8.11.1 Syntax

```python id="4j3oxo"
sp.reduce_inequalities(x**2 <= sp.pi, x)
sp.reduce_inequalities([x >= 0, x**2 <= sp.pi], x)
sp.reduce_inequalities([x > 1, y > 0], [x, y])
```

`reduce_inequalities()` is the top-level algebraic inequality reducer. Official docs recommend it over relying on `solve()` for inequalities because `solve()` currently calls it internally but that behavior may be deprecated or removed. It currently reduces only one symbol of interest per inequality, although a system can contain more than one symbol if each inequality has only one symbol of interest. ([SymPy Docs][11])

```python id="7031ka"
sp.reduce_inequalities([x >= 0, x**2 <= sp.pi], x)
# (0 <= x) & (x <= sqrt(pi))

sp.reduce_inequalities(x**2 <= sp.pi, x)
# (x <= sqrt(pi)) & (-sqrt(pi) <= x)
```

Unsupported multivariate inequality example:

```python id="rrm1wl"
# NotImplementedError for inequality with more than one symbol of interest:
# reduce_inequalities([x + y > 1, y > 0], [x, y])
```

## 8.11.2 Extract bounds

```python id="pphfxb"
from sympy.core.relational import Relational

ineq = sp.reduce_inequalities([3*x >= 1, x**2 <= sp.pi], x)
relations = [r.canonical for r in ineq.atoms(Relational)]

bounds = [(r.lhs, r.rel_op, r.rhs) for r in relations]
```

Official docs show extracting relation atoms and using `.canonical` to put the variable on the left for bound extraction. ([SymPy Docs][11])

Deployment rule:

```text id="l1627o"
Use reduce_inequalities for symbolic inequality reduction.
Pass the variable explicitly.
Expect Boolean And/Or relational output, not dicts.
Use relation atoms to extract bounds.
Use SciPy linprog or numeric methods for unsupported multivariate systems.
```

---

## 8.12 Diophantine equations

## 8.12.1 Syntax

```python id="7yewb6"
from sympy.solvers.diophantine import diophantine

x, y, z = sp.symbols("x y z", integer=True)

diophantine(2*x + 3*y - 5)
diophantine(x**2 + y**2 - z**2)
```

Diophantine equations are integer-variable equations of the form `f(x1, ..., xn) = 0`; SymPy’s module supports selected classes including linear Diophantine equations, binary quadratic equations, homogeneous ternary quadratic equations, extended Pythagorean equations, and general sums of squares. The top-level `diophantine()` factors equations where possible and solves factor equations through internal classification and solver helpers. ([SymPy Docs][12])

```python id="ucrp68"
diophantine(2*x + 3*y - 5)
# {(3*t_0 - 5, 5 - 2*t_0)}
```

Deployment rule:

```text id="j4btu4"
Use diophantine for integer-domain symbolic solution families.
Declare symbols integer=True for clarity.
Pass expression equal to zero.
Expect parameter symbols t_0, t_1, ...
Do not expect arbitrary integer equations to be supported.
```

---

## 8.13 Polynomial roots

## 8.13.1 Root API map

```python id="vxv33x"
sp.roots(poly, x)
sp.ground_roots(poly, x)
sp.nroots(poly, n=15, maxsteps=50)
sp.real_roots(poly)
sp.all_roots(poly)
sp.RootOf(poly, index)
sp.CRootOf(poly, index)
```

Official root-finding guidance distinguishes several root APIs: `solve()` can find roots but does not convey multiplicities and is less efficient than polynomial-specific functions; `roots()` returns symbolic roots of a univariate polynomial but can fail for high-degree polynomials; `nroots()` computes numerical approximations for polynomials whose coefficients can be numerically evaluated; `RootOf()` can represent exact roots of arbitrarily high-degree rational-coefficient polynomials, avoiding ill-conditioning/spurious complex parts at the cost of much slower exact isolation algorithms. ([SymPy Docs][13])

## 8.13.2 `roots`

```python id="ywf9rc"
sp.roots(x**2 - 3*x + 2, x)
# {1: 1, 2: 1}

sp.roots((x - 1)**2 * (x + 3), x)
# {-3: 1, 1: 2}
```

`roots()` returns a dictionary `{root: multiplicity}`. This is machine-friendly for algebraic multiplicity-sensitive work. ([SymPy Docs][14])

## 8.13.3 `nroots`

```python id="x7w48x"
sp.nroots(x**2 - 3, n=15)
# [-1.73205080756888, 1.73205080756888]

sp.nroots(x**2 - 3, n=30)
```

`nroots(f, n=15, maxsteps=50, cleanup=True)` computes numerical approximations of all roots of a polynomial. Polynomial docs show increasing `n` to request more digits. ([SymPy Docs][15])

## 8.13.4 `RootOf`

```python id="ha6kku"
r0 = sp.RootOf(x**5 - x + 1, 0)
r0.evalf(50)
```

Use `RootOf`/`CRootOf` for exact representation of algebraic roots that cannot or should not be expressed in radicals. Root docs explicitly highlight exact representation of high-degree rational-coefficient polynomial roots with isolation-based evaluation. ([SymPy Docs][13])

Deployment rule:

```text id="30m26r"
Use roots:
  exact radicals/multiplicities for simple symbolic polynomial roots.

Use nroots:
  approximate all roots for numeric polynomial coefficients.

Use RootOf/all_roots/real_roots:
  exact algebraic-root representation, high-degree rational polynomials.

Do not use solve for multiplicity-sensitive polynomial root workflows.
```

---

## 8.14 Return-shape normalization

## 8.14.1 `solve(..., dict=True)` normalization

```python id="8hmpmn"
def solve_as_dicts(eqs, vars):
    out = sp.solve(eqs, vars, dict=True)
    return list(out)
```

## 8.14.2 `FiniteSet` of ordered tuples → dicts

```python id="ye20hu"
def finite_tuple_set_to_dicts(solset, symbols):
    if solset is sp.S.EmptySet:
        return []
    if isinstance(solset, sp.ConditionSet):
        raise NotImplementedError(f"ConditionSet: {solset}")
    if not isinstance(solset, sp.FiniteSet):
        raise TypeError(f"expected FiniteSet, got {type(solset).__name__}")

    result = []
    for tup in solset:
        if not isinstance(tup, tuple):
            tup = (tup,)
        result.append(dict(zip(symbols, tup)))
    return result
```

`linsolve` and `nonlinsolve` return `FiniteSet` containing ordered tuples; docs emphasize that although a general `FiniteSet` is unordered, a tuple within it is ordered, and that tuple order maps to the supplied symbol order. ([SymPy Docs][6])

## 8.14.3 `Set` output handling

```python id="msiea5"
def classify_solution_set(sol):
    if sol is sp.S.EmptySet:
        return "empty"
    if isinstance(sol, sp.FiniteSet):
        return "finite"
    if isinstance(sol, sp.ConditionSet):
        return "conditional-or-unsolved"
    if isinstance(sol, sp.Interval):
        return "interval"
    if isinstance(sol, sp.Union):
        return "union"
    if isinstance(sol, sp.ImageSet):
        return "infinite-parametric"
    return type(sol).__name__
```

---

## 8.15 Solver-preprocessing strategy

## 8.15.1 Equation normalization

```python id="l86ua6"
def equation_to_zero(eq):
    if isinstance(eq, sp.Equality):
        return sp.simplify(eq.lhs - eq.rhs)
    return sp.sympify(eq)
```

## 8.15.2 Rational cleanup

```python id="ijtojn"
def solver_normal_form(expr):
    expr = equation_to_zero(expr)
    expr = sp.together(expr)
    expr = sp.factor(expr)
    return expr
```

## 8.15.3 Linear reveal before `linsolve`

```python id="6hm1yw"
def linear_ready(eqs):
    return [sp.cancel(sp.together(equation_to_zero(e))) for e in eqs]
```

Docs for `linear_eq_to_matrix`/`linsolve` warn that simplification needed to eliminate removable nonlinear terms must happen before calling the routine. ([SymPy Docs][6])

---

## 8.16 Deployment recipes

## Recipe A — exact univariate solve with set semantics

```python id="b9zumw"
def solve_univariate_set(eq, var, *, domain=sp.S.Complexes):
    sol = sp.solveset(eq, var, domain=domain)
    if isinstance(sol, sp.ConditionSet):
        raise NotImplementedError(f"unable to solve completely: {sol}")
    return sol
```

## Recipe B — exact linear system → ordered dicts

```python id="rdgh9i"
def solve_linear_system(eqs, symbols):
    eqs = linear_ready(eqs)
    solset = sp.linsolve(eqs, *symbols)
    return finite_tuple_set_to_dicts(solset, symbols)
```

## Recipe C — exact nonlinear system → ordered dicts

```python id="qbo8zv"
def solve_nonlinear_system(eqs, symbols):
    eqs = [equation_to_zero(e) for e in eqs]
    solset = sp.nonlinsolve(eqs, symbols)
    return finite_tuple_set_to_dicts(solset, symbols)
```

## Recipe D — numeric solve with residual validation

```python id="6s8n10"
def numeric_solve_checked(eqs, symbols, guess, *, prec=50, residual_tol=sp.S("1e-40")):
    if isinstance(eqs, (list, tuple)):
        root = sp.nsolve(tuple(eqs), tuple(symbols), tuple(guess), prec=prec)
        residuals = [abs(sp.N(e.subs(dict(zip(symbols, root))), prec)) for e in eqs]
        if any(r > residual_tol for r in residuals):
            raise ValueError(f"large residuals: {residuals}")
        return dict(zip(symbols, list(root)))

    root = sp.nsolve(eqs, symbols, guess, prec=prec)
    residual = abs(sp.N(eqs.subs(symbols, root), prec))
    if residual > residual_tol:
        raise ValueError(f"large residual: {residual}")
    return {symbols: root}
```

## Recipe E — ODE solve and verify

```python id="r1r6u5"
def solve_ode_verified(ode, func, *, ics=None, hint="default"):
    sol = sp.dsolve(ode, func, ics=ics, hint=hint)
    ok, residual = sp.checkodesol(ode, sol)
    if ok is not True:
        raise ValueError(f"ODE solution failed verification: {residual}")
    return sol
```

## Recipe F — polynomial roots with multiplicity

```python id="c77i5k"
def polynomial_roots(poly, var, *, numeric=False, digits=30):
    if numeric:
        return sp.nroots(poly, n=digits)
    return sp.roots(poly, var)
```

## Recipe G — inequality bounds extraction

```python id="xwmppc"
def reduce_and_extract_bounds(ineqs, var):
    from sympy.core.relational import Relational

    reduced = sp.reduce_inequalities(ineqs, var)
    relations = [rel.canonical for rel in reduced.atoms(Relational)]

    return reduced, [(rel.lhs, rel.rel_op, rel.rhs) for rel in relations]
```

---

## 8.17 Anti-pattern inventory

| Anti-pattern                                    | Failure mode                                 | Correct pattern                                             |
| ----------------------------------------------- | -------------------------------------------- | ----------------------------------------------------------- |
| raw `solve()` output in production              | shape drift: list/dict/tuple/relational      | `dict=True`, or use specialized solver                      |
| `solve()` for univariate infinite solution sets | incomplete/legacy finite-style output        | `solveset(..., domain=...)`                                 |
| no domain in `solveset`                         | real/complex ambiguity                       | pass `S.Reals` or `S.Complexes` explicitly                  |
| enumerating arbitrary `Set` output              | infinite/conditional sets mishandled         | inspect `FiniteSet`, `ImageSet`, `ConditionSet`, `Interval` |
| using `linsolve` before simplification          | `NonlinearError` on removable nonlinearities | `cancel/together/simplify` first                            |
| using `nonlinsolve` when numeric answer desired | exact solver cost/failure                    | `nsolve` with guesses                                       |
| `nsolve` without residual check                 | false convergence / wrong branch             | verify residuals                                            |
| expecting `nsolve` to find all roots            | one initial guess → one root                 | bracket/scan or use `nroots` for polynomials                |
| using `solve` for polynomial multiplicities     | multiplicity lost                            | `roots`, `real_roots`, `all_roots`                          |
| ignoring `ConditionSet`                         | silently incomplete solve                    | preserve/reject/report                                      |
| suppressing integration/ODE conditions          | invalid solution domain                      | verify with `checkodesol`, track conditions                 |
| inequality solving via `solve`                  | future behavior risk                         | `reduce_inequalities`                                       |
| multivariate inequality expectations            | `NotImplementedError`                        | SciPy `linprog`/numeric methods                             |
| treating Diophantine as general solver          | unsupported equation classes                 | check supported forms / handle no solution                  |
| symbolic matrix solve for numeric workload      | slow exact algebra                           | NumPy/SciPy/mpmath                                          |

---

## 8.18 Testing matrix

```python id="y620io"
def assert_solution_dicts(eqs, symbols, sols):
    for sol in sols:
        for eq in eqs:
            assert sp.simplify(equation_to_zero(eq).subs(sol)) == 0

def assert_set_solution(eq, var, solset):
    for sol in solset:
        assert sp.simplify(equation_to_zero(eq).subs(var, sol)) == 0

def assert_nsolve_solution(eqs, symbols, sol, tol=sp.S("1e-30")):
    for eq in eqs:
        r = abs(sp.N(equation_to_zero(eq).subs(sol), 50))
        assert r < tol

def assert_ode_solution(ode, sol):
    ok, residual = sp.checkodesol(ode, sol)
    assert ok is True, residual
```

Recommended cases:

```text id="rosfvu"
univariate:
  finite real roots
  complex roots
  infinite periodic solutions
  unsolved ConditionSet

linear systems:
  unique
  underdetermined
  inconsistent
  symbolic coefficients
  removable nonlinearity preprocessing

nonlinear systems:
  finite zero-dimensional
  positive-dimensional
  complex branches

nsolve:
  scalar
  system
  multiple initial guesses
  failed convergence
  complex initial guess

ODE:
  first-order separable/linear
  second-order linear
  initial conditions
  checkodesol verification

PDE:
  supported first-order linear case
  unsupported case path

inequalities:
  one variable
  incompatible constraints -> False
  unsupported multivariate -> error

polynomial roots:
  roots multiplicity
  nroots precision
  RootOf high-degree polynomial

Diophantine:
  linear
  Pythagorean
  unsupported class handling
```

---

## 8.19 Minimal solver harness

```python id="u1wc3o"
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Sequence

import sympy as sp
from sympy.core.relational import Relational


@dataclass(frozen=True)
class SolveAudit:
    solver: str
    equations: tuple[sp.Expr, ...]
    symbols: tuple[sp.Symbol, ...]
    raw_solution: Any
    normalized_solution: Any
    residuals: Any
    complete: bool


def equation_to_zero(eq: Any) -> sp.Expr:
    eq = sp.sympify(eq)
    if isinstance(eq, sp.Equality):
        return sp.simplify(eq.lhs - eq.rhs)
    return eq


def normalize_equations(eqs: Any) -> tuple[sp.Expr, ...]:
    if isinstance(eqs, (list, tuple, set)):
        return tuple(equation_to_zero(e) for e in eqs)
    return (equation_to_zero(eqs),)


def finite_tuple_set_to_dicts(solset: Any, symbols: Sequence[sp.Symbol]) -> list[dict[sp.Symbol, sp.Expr]]:
    if solset is sp.S.EmptySet:
        return []

    if isinstance(solset, sp.ConditionSet):
        raise NotImplementedError(f"conditional/unsolved solution set: {solset}")

    if not isinstance(solset, sp.FiniteSet):
        raise TypeError(f"expected FiniteSet, got {type(solset).__name__}: {solset}")

    out: list[dict[sp.Symbol, sp.Expr]] = []
    for item in solset:
        tup = item if isinstance(item, tuple) else (item,)
        out.append(dict(zip(symbols, tup)))
    return out


def residuals(eqs: Sequence[sp.Expr], solution: dict[sp.Symbol, Any], *, digits: int = 50):
    return [sp.N(eq.subs(solution), digits) for eq in eqs]


def solve_exact_univariate(
    eq: Any,
    var: sp.Symbol,
    *,
    domain=sp.S.Complexes,
    reject_conditions: bool = True,
) -> sp.Set:
    expr = equation_to_zero(eq)
    sol = sp.solveset(expr, var, domain=domain)

    if reject_conditions and isinstance(sol, sp.ConditionSet):
        raise NotImplementedError(f"solveset returned ConditionSet: {sol}")

    return sol


def solve_exact_general(eqs: Any, symbols: Sequence[sp.Symbol]) -> list[dict[sp.Symbol, sp.Expr]]:
    eq_tuple = normalize_equations(eqs)
    return list(sp.solve(eq_tuple, list(symbols), dict=True))


def solve_linear(eqs: Any, symbols: Sequence[sp.Symbol]) -> list[dict[sp.Symbol, sp.Expr]]:
    eq_tuple = tuple(sp.cancel(sp.together(e)) for e in normalize_equations(eqs))
    solset = sp.linsolve(eq_tuple, *symbols)
    return finite_tuple_set_to_dicts(solset, symbols)


def solve_nonlinear(eqs: Any, symbols: Sequence[sp.Symbol]) -> list[dict[sp.Symbol, sp.Expr]]:
    eq_tuple = normalize_equations(eqs)
    solset = sp.nonlinsolve(eq_tuple, list(symbols))
    return finite_tuple_set_to_dicts(solset, symbols)


def solve_numeric(
    eqs: Any,
    symbols: Sequence[sp.Symbol] | sp.Symbol,
    guess: Sequence[Any] | Any,
    *,
    prec: int = 50,
    residual_tol=sp.S("1e-40"),
) -> dict[sp.Symbol, sp.Expr]:
    eq_tuple = normalize_equations(eqs)

    if isinstance(symbols, sp.Symbol):
        root = sp.nsolve(eq_tuple[0], symbols, guess, prec=prec)
        sol = {symbols: root}
    else:
        root = sp.nsolve(tuple(eq_tuple), tuple(symbols), tuple(guess), prec=prec)
        sol = dict(zip(symbols, list(root)))

    rs = [abs(sp.N(eq.subs(sol), prec)) for eq in eq_tuple]
    if any(r > residual_tol for r in rs):
        raise ValueError(f"large residuals: {rs}")

    return sol


def solve_matrix(A: sp.MatrixBase, b: sp.MatrixBase, *, method: str | None = None) -> sp.Matrix:
    if method is None:
        return A.solve(b)
    return A.solve(b, method=method)


def solve_ode(ode: Any, func: Any, *, ics: dict | None = None, hint: str = "default"):
    sol = sp.dsolve(ode, func, ics=ics, hint=hint)
    ok, residual = sp.checkodesol(ode, sol)
    if ok is not True:
        raise ValueError(f"ODE verification failed: {residual}")
    return sol


def solve_pde(eq: Any, func: Any | None = None, *, hint: str = "default"):
    if func is None:
        return sp.pdsolve(eq, hint=hint)
    return sp.pdsolve(eq, func, hint=hint)


def reduce_ineqs(ineqs: Any, var: sp.Symbol):
    reduced = sp.reduce_inequalities(ineqs, var)
    relations = [r.canonical for r in reduced.atoms(Relational)]
    bounds = [(r.lhs, r.rel_op, r.rhs) for r in relations]
    return reduced, bounds


def solve_diophantine(eq: Any):
    from sympy.solvers.diophantine import diophantine
    return diophantine(equation_to_zero(eq))


def polynomial_roots(
    poly: Any,
    var: sp.Symbol,
    *,
    mode: Literal["roots", "nroots", "real_roots", "all_roots"] = "roots",
    digits: int = 30,
):
    poly = sp.sympify(poly)

    if mode == "roots":
        return sp.roots(poly, var)
    if mode == "nroots":
        return sp.nroots(poly, n=digits)
    if mode == "real_roots":
        return sp.real_roots(poly)
    if mode == "all_roots":
        return sp.all_roots(poly)

    raise ValueError(f"unknown root mode: {mode}")


def audit_solution(
    solver: str,
    eqs: Any,
    symbols: Sequence[sp.Symbol],
    raw_solution: Any,
    normalized_solution: Any,
) -> SolveAudit:
    eq_tuple = normalize_equations(eqs)

    if isinstance(normalized_solution, list):
        rs = [residuals(eq_tuple, s) for s in normalized_solution if isinstance(s, dict)]
    elif isinstance(normalized_solution, dict):
        rs = residuals(eq_tuple, normalized_solution)
    else:
        rs = None

    complete = not isinstance(raw_solution, sp.ConditionSet)

    return SolveAudit(
        solver=solver,
        equations=eq_tuple,
        symbols=tuple(symbols),
        raw_solution=raw_solution,
        normalized_solution=normalized_solution,
        residuals=rs,
        complete=complete,
    )
```

This harness encodes solver-routing discipline: explicit equation normalization, domain-aware `solveset`, stable dict output for `solve`, ordered tuple extraction for `linsolve`/`nonlinsolve`, residual-checked `nsolve`, ODE verification, inequality relation extraction, Diophantine integer solving, and polynomial-root mode selection.

[1]: https://docs.sympy.org/latest/guides/solving/index.html?utm_source=chatgpt.com "Solve Equations - SymPy 1.14.0 documentation"
[2]: https://docs.sympy.org/latest/guides/solving/solve-equation-algebraically.html?utm_source=chatgpt.com "Solve an Equation Algebraically"
[3]: https://docs.sympy.org/latest/modules/solvers/solvers.html "Solvers - SymPy 1.14.0 documentation"
[4]: https://docs.sympy.org/latest/explanation/solve_output.html "Solve Output by Type - SymPy 1.14.0 documentation"
[5]: https://docs.sympy.org/latest/tutorials/intro-tutorial/solvers.html?utm_source=chatgpt.com "Solvers - SymPy 1.14.0 documentation"
[6]: https://docs.sympy.org/latest/modules/solvers/solveset.html "Solveset - SymPy 1.14.0 documentation"
[7]: https://docs.sympy.org/latest/guides/solving/solve-matrix-equation.html?utm_source=chatgpt.com "Solve a Matrix Equation Algebraically"
[8]: https://docs.sympy.org/latest/guides/solving/solving-guidance.html?utm_source=chatgpt.com "Solving Guidance - SymPy 1.14.0 documentation"
[9]: https://docs.sympy.org/latest/modules/solvers/ode.html "ODE - SymPy 1.14.0 documentation"
[10]: https://docs.sympy.org/latest/modules/solvers/pde.html "PDE - SymPy 1.14.0 documentation"
[11]: https://docs.sympy.org/latest/guides/solving/reduce-inequalities-algebraically.html?utm_source=chatgpt.com "Reducing a System of Inequalities for a Single Variable ..."
[12]: https://docs.sympy.org/latest/modules/solvers/diophantine.html "Diophantine - SymPy 1.14.0 documentation"
[13]: https://docs.sympy.org/latest/guides/solving/find-roots-polynomial.html?utm_source=chatgpt.com "Find the Roots of a Polynomial Algebraically or Numerically"
[14]: https://docs.sympy.org/latest/explanation/gotchas.html?utm_source=chatgpt.com "Gotchas and Pitfalls - SymPy 1.14.0 documentation"
[15]: https://docs.sympy.org/latest/modules/polys/reference.html "Polynomials Manipulation Module Reference - SymPy 1.14.0 documentation"

# 9) Polynomials, domains, algebraic fields, and exact algebra — agent-ready deep dive

Continuing the same advanced technical-doc pattern as the supplied reference artifact. 

## 9.0 Exact-polynomial mental model

SymPy has two polynomial layers:

```text id="e4d5kc"
Expr layer:
  general symbolic expression tree
  e.g. x**2 + 2*x + 1

Poly/domain layer:
  polynomial object with explicit generators + coefficient domain
  e.g. Poly(x**2 + 2*x + 1, x, domain=ZZ)
```

Use the `Poly`/domain layer when the object is mathematically a polynomial and will be manipulated repeatedly or algorithmically. SymPy’s polynomial docs state that polynomial rings have a coefficient ring called the **domain**, and `Poly` objects store generators, domain, and internal polynomial representation; `Poly` is a `Basic` subclass rather than an `Expr`, and it converts back with `.as_expr()`. ([SymPy Docs][1])

```python id="dgrfxr"
import sympy as sp
from sympy import Poly, ZZ, QQ, GF, groebner
from sympy.polys.matrices import DomainMatrix, DM

x, y, z, t = sp.symbols("x y z t")
```

---

## 9.1 `Expr` vs `Poly`

## 9.1.1 Construction and conversion

```python id="wb7dkf"
expr = (x + y)*(y - 2*z)

P = Poly(expr, x, y, z)
Q = expr.as_poly(x, y, z)

P.as_expr()
```

`Expr.as_poly()` transforms a polynomial expression into a `Poly`; if generators are omitted, SymPy infers them from the expression. If non-integer coefficients occur, the coefficient domain is extended, e.g. integer coefficients produce `ZZ`, rational coefficients produce `QQ`, and symbolic constants can be treated as either generators or coefficients depending on explicit generator/domain choices. ([SymPy Docs][2])

```python id="mz3gz6"
((x + y)*(y - 2*z)).as_poly()
# Poly(x*y - 2*x*z + y**2 - 2*y*z, x, y, z, domain='ZZ')

((sp.Rational(3, 2)*x + y)*(z - 1)).as_poly()
# Poly(3/2*x*z - 3/2*x + y*z - y, x, y, z, domain='QQ')

((x + 2*sp.pi)*y).as_poly()
# Poly(x*y + 2*y*pi, x, y, pi, domain='ZZ')

((x + 2*sp.pi)*y).as_poly(x, y)
# Poly(x*y + 2*pi*y, x, y, domain='ZZ[pi]')
```

## 9.1.2 `Poly` API surface

```python id="y9ws46"
P = Poly(x**5 + 2*x**4 - x**3 - 2*x**2 + x, x, domain=ZZ)

P.gens          # (x,)
P.domain        # ZZ
P.degree()
P.degree(x)
P.LC()          # leading coefficient
P.TC()          # trailing coefficient
P.all_coeffs()
P.terms()
P.monoms()
P.coeffs()
P.as_dict()
P.as_expr()
```

`Poly` stores generator order and coefficient domain explicitly. Examples in the reference docs show `Poly(x*(x**2+x-1)**2)` expanding into a univariate `Poly` over `ZZ`, multivariate construction over `(x, y)`, and specifying a generator to treat other symbols as coefficients, e.g. `Poly(y*x**2 + x*y + 1, x)` gives domain `ZZ[y]`. ([SymPy Docs][3])

```python id="f3f3v7"
Poly(y*x**2 + x*y + 1)
# Poly(x**2*y + x*y + 1, x, y, domain='ZZ')

Poly(y*x**2 + x*y + 1, x)
# Poly(y*x**2 + y*x + 1, x, domain='ZZ[y]')
```

## 9.1.3 Do not mix `Poly` and `Expr`

`Poly` is not an `Expr`; docs note that mixing `Poly` with non-`Poly` objects in binary operations is deprecated and should be avoided by explicitly converting both operands to either `Poly` or `Expr`. ([SymPy Docs][3])

```python id="rsrvsj"
P = Poly(x**2 + 1, x)

# Safe:
(P + Poly(x + 1, x)).as_expr()

# Safe:
P.as_expr() + (x + 1)
```

Deployment rule:

```text id="uap8og"
Use Expr for general symbolic expressions and calculus.
Use Poly for repeated exact polynomial operations.
Do not mix Expr and Poly in arithmetic.
Convert at phase boundaries with Poly(...) / .as_expr().
```

---

## 9.2 Polynomial domains

## 9.2.1 Domain meaning

```text id="go9hla"
domain = coefficient domain / coefficient ring / coefficient field

ZZ       integers
QQ       rationals
ZZ[x]    polynomial ring over integers
QQ[x]    polynomial ring over rationals
QQ(x)    rational function field
GF(p)    finite field of prime order p
QQ<a>    algebraic field extension
```

SymPy’s domain docs define domains as the coefficient systems used by polynomial algorithms; domains provide suitable internal representations for classes of expressions and are used internally by `Poly`. The same docs show domain unification, e.g. `ZZ.unify(QQ) -> QQ`, `ZZ[x].unify(QQ) -> QQ[x]`, and unification of algebraic fields/rational-function fields. ([SymPy Docs][4])

```python id="pi206y"
Pz = Poly(x**2 + 1, x, domain=ZZ)
Pq = Poly(sp.Rational(1, 2)*x + 1, x, domain=QQ)

Pz.domain
Pq.domain
```

## 9.2.2 `ZZ` and `QQ`

```python id="66nvg0"
ZZ(2)
QQ(2, 3)

Poly(x**2 + 1, x, domain=ZZ)
Poly(sp.Rational(2, 3)*x + 1, x, domain=QQ)
```

`ZZ` is not a field; `QQ` is a field. Polynomial rings over fields are still rings, and `QQ[x].get_field()` gives the rational-function field `QQ(x)`. Domain methods such as `quo`, `rem`, `div`, and `exquo` distinguish quotient, remainder, division, and exact quotient; exact quotient fails if divisibility does not hold. ([SymPy Docs][4])

```python id="lwnput"
ZZ.is_Field       # False
QQ.is_Field       # True

QQ[x]             # QQ[x]
QQ[x].get_field() # QQ(x)

ZZ.exquo(ZZ(4), ZZ(2))  # 2
# ZZ.exquo(ZZ(5), ZZ(3)) -> ExactQuotientFailed
```

## 9.2.3 Algebraic extensions

```python id="nzv4ql"
K = QQ.algebraic_field(sp.sqrt(2))
P = Poly(x**2 - 2, x, domain=K)

sp.factor(x**2 - 2, extension=sp.sqrt(2))
# (x - sqrt(2))*(x + sqrt(2))
```

Algebraic field domains represent exact coefficient fields such as `QQ<sqrt(2)>`; the docs show algebraic-field unification, e.g. `QQ.algebraic_field(sqrt(2))[x]` unified with `QQ.algebraic_field(sqrt(3))[y]` yields a common primitive field `QQ<sqrt(2) + sqrt(3)>[x,y]`. ([SymPy Docs][4])

```python id="irlf82"
K1 = QQ.algebraic_field(sp.sqrt(2))[x]
K2 = QQ.algebraic_field(sp.sqrt(3))[y]
K1.unify(K2)
# QQ<sqrt(2) + sqrt(3)>[x,y]
```

## 9.2.4 Finite fields

```python id="iujc7j"
K = GF(5)
P = Poly(x**2 + 1, x, domain=K)

sp.factor(x**2 + 1, modulus=5)
```

SymPy implements finite fields of **prime order** via `GF(p)`/`FF`; finite fields of prime-power order `p**n` for `n != 1` are not implemented. The docs explicitly warn that `GF(6)` or `GF(9)` can be constructed but is merely integers modulo 6 or 9, not a field, with zero divisors and non-invertible elements. ([SymPy Docs][4])

```python id="to0brn"
GF(5)       # finite field of prime order
GF(6)       # modular integer ring, not a field
```

Deployment rule:

```text id="zlgzn4"
Use GF(p) only with prime p for field algorithms.
Do not assume GF(p**n) exists for n > 1.
Avoid GF(composite) when algorithms require field inverses.
```

---

## 9.3 Domain elements vs SymPy expressions

Domain elements are not ordinary `Expr` nodes; they belong to a `Domain`, have domain-specific arithmetic, and can be faster/more exact for polynomial algorithms. The domains docs warn not to depend on concrete Python element types for `ZZ`/`QQ`, because gmpy/gmpy2 can change internal element types; use `domain.of_type()` or domain conversion APIs instead. ([SymPy Docs][4])

```python id="plow99"
a = ZZ(2)
b = QQ(3, 2)

ZZ.of_type(a)
QQ.of_type(b)
QQ.convert_from(a, ZZ)
```

Domain conversion/unification pattern:

```python id="gq8xog"
K = ZZ.unify(QQ)              # QQ
aK = K.convert_from(ZZ(2), ZZ)
bK = K.convert_from(QQ(3, 2), QQ)
aK + bK                       # 7/2
```

Performance rule:

```text id="xjdgxv"
Inside tight polynomial/domain code:
  use domain elements and Poly/DomainMatrix.

At public symbolic API boundary:
  convert to Expr with .as_expr(), domain.to_sympy(...), or Matrix conversion.
```

---

## 9.4 Polynomial arithmetic and exact division

## 9.4.1 Division APIs

```python id="wme9e3"
sp.div(f, g, x, domain=ZZ)
sp.rem(f, g, x, domain=QQ)
sp.quo(f, g, x)
sp.exquo(f, g, x)
```

The polynomial reference documents `div`, `rem`, `quo`, and `exquo`; the result depends on the domain. For example, division of `x**2 + 1` by `2*x - 4` over `ZZ` gives quotient `0` and remainder `x**2 + 1`, while over `QQ` the quotient is `x/2 + 1` and remainder `5`. `exquo` requires exact divisibility and raises `ExactQuotientFailed` otherwise. ([SymPy Docs][3])

```python id="p1adpb"
sp.div(x**2 + 1, 2*x - 4, domain=ZZ)
# (0, x**2 + 1)

sp.div(x**2 + 1, 2*x - 4, domain=QQ)
# (x/2 + 1, 5)

sp.exquo(x**2 - 1, x - 1)
# x + 1
```

## 9.4.2 `Poly` methods

```python id="b8lzge"
P = Poly(x**2 - 1, x, domain=ZZ)
Q = Poly(x - 1, x, domain=ZZ)

P.div(Q)
P.rem(Q)
P.quo(Q)
P.exquo(Q)
P.pdiv(Q)
P.prem(Q)
P.pquo(Q)
P.pexquo(Q)
```

Pseudo-division methods (`pdiv`, `prem`, `pquo`, `pexquo`) operate without leaving coefficient rings such as `ZZ`, useful in subresultant sequences and exact polynomial algorithms. The reference shows `Poly(...).pdiv(...)`, `pexquo(...)`, `pquo(...)`, and pseudo-remainder APIs, including exact pseudo-quotient failure on non-divisible inputs. ([SymPy Docs][3])

---

## 9.5 Factoring, GCD, resultants, discriminants

## 9.5.1 Factoring

```python id="lotgow"
sp.factor(x**3 - x**2 + x - 1)
sp.factor(x**2 + 1, modulus=2)
sp.factor(x**2 - 2, extension=sp.sqrt(2))

Poly(x**3 - x, x).factor_list()
sp.factor_list(x**3 - x)
```

Use `factor`/`factor_list` for irreducible factorization over a selected domain. `factor_system` and related polynomial-system factoring tools return irreducible subsystems and Boolean/conditional decompositions of polynomial systems. ([SymPy Docs][5])

```python id="l3em0f"
sp.factor_list(x**3 - x)
# (1, [(x - 1, 1), (x, 1), (x + 1, 1)])
```

## 9.5.2 GCD and extended GCD

```python id="un9iof"
sp.gcd(f, g, x)
sp.gcdex(f, g, x)
sp.half_gcdex(f, g, x)
sp.invert(f, g, x)
```

`gcdex(f, g)` returns `(s, t, h)` such that `s*f + t*g = h = gcd(f, g)`. `half_gcdex` returns `(s, h)` with `s*f = h mod g`. `invert(f, g)` computes a polynomial inverse modulo `g` when possible and raises when the element is a zero divisor / not invertible. ([SymPy Docs][3])

```python id="krkz03"
f = x**4 - 2*x**3 - 6*x**2 + 12*x + 15
g = x**3 + x**2 - 4*x - 4

s, t, h = sp.gcdex(f, g, x)
sp.expand(s*f + t*g - h) == 0
```

## 9.5.3 Resultant and discriminant

```python id="x0w4cc"
sp.resultant(f, g, x)
sp.discriminant(f, x)
sp.subresultants(f, g, x)
```

`resultant(f, g)` eliminates a variable and detects common roots; `discriminant(f)` detects repeated-root structure; `subresultants` returns the subresultant polynomial remainder sequence. The reference explicitly documents `resultant(x**2 + 1, x**2 - 1) -> 4` and `discriminant(x**2 + 2*x + 3) -> -8`. ([SymPy Docs][3])

```python id="jawkc2"
sp.resultant(x**2 + 1, x**2 - 1, x)
# 4

sp.discriminant(x**2 + 2*x + 3, x)
# -8
```

Deployment uses:

```text id="op9aq9"
resultant:
  eliminate variable
  detect common roots
  implicitization
  algebraic system projection

discriminant:
  repeated root detection
  parameter bifurcation
  branch/singularity analysis

subresultants:
  exact polynomial GCD internals
  robust elimination diagnostics
```

---

## 9.6 Groebner bases and elimination

## 9.6.1 `groebner(F, *gens, order='lex'|'grlex'|'grevlex', method=...)`

```python id="wq1qy5"
F = [x*y - 2*y, 2*y**2 - x**2]

G_lex = groebner(F, x, y, order="lex")
G_grlex = groebner(F, x, y, order="grlex")
G_grevlex = groebner(F, x, y, order="grevlex")
```

`groebner()` computes a reduced Groebner basis. The supported monomial orders documented are `lex`, `grlex`, and `grevlex`, with `lex` as default. The implementation uses an improved Buchberger algorithm by default and can optionally use the `f5b` method. ([SymPy Docs][3])

```python id="dx06hg"
G = groebner([x*y - 2*y, 2*y**2 - x**2], x, y, order="lex")

list(G)
G.polys
G.gens
G.domain
G.order
```

## 9.6.2 Ideal membership and reduction

```python id="lkbxx7"
G.contains(poly)
quotients, remainder = G.reduce(poly)
```

`GroebnerBasis.contains(poly)` tests ideal membership. `GroebnerBasis.reduce(expr)` reduces a polynomial modulo the basis and returns quotients and a reduced remainder satisfying `f = q1*f1 + ... + qn*fn + r`. ([SymPy Docs][3])

```python id="apll99"
G = groebner([x**3 - x, y**3 - y], x, y)

q, r = G.reduce(2*x**4 - x**2 + y**3 + y**2)
r
# reduced normal form modulo ideal
```

Membership pattern:

```python id="lidjtp"
def in_ideal(poly, generators, *gens):
    G = groebner(generators, *gens)
    return G.contains(poly)
```

## 9.6.3 Elimination and monomial order

```python id="idx0vw"
G = groebner([x**2 - 3*y - x + 1, y**2 - 2*x + y - 1], x, y, order="grlex")
G_lex = G.fglm("lex")
```

`GroebnerBasis.fglm(order)` converts a zero-dimensional Groebner basis from one ordering to another using the FGLM algorithm, useful when direct computation in a desired order is expensive. The docs state FGLM is for zero-dimensional ideals and is often used when a direct computation in a particular ordering is infeasible. ([SymPy Docs][3])

Elimination heuristic:

```text id="o8q1b1"
For elimination:
  use lex order with variables ordered so eliminated variables appear before retained variables,
  or compute easier grevlex/grlex basis then convert with fglm('lex') if zero-dimensional.
```

Zero-dimensional check:

```python id="zhyvwf"
G.is_zero_dimensional
sp.is_zero_dimensional(F, x, y)
```

The docs state zero-dimensional checks inspect whether monomials not divisible by leading monomials are bounded. ([SymPy Docs][3])

---

## 9.7 Polynomial systems

## 9.7.1 `solve_poly_system(seq, *gens, strict=False, **args)`

```python id="qpzi24"
from sympy import solve_poly_system

solve_poly_system([x*y - 2*y, 2*y**2 - x**2], x, y)
# [(0, 0), (2, -sqrt(2)), (2, sqrt(2))]
```

`solve_poly_system(seq, *gens, strict=False, **args)` returns a list of solution tuples for a system of polynomial equations or `None`. `seq` is the collection of equations assumed equal to zero; `gens` are the generators to solve for. With `strict=True`, the solver can raise `UnsolvableFactorError` when exact radical solutions cannot be guaranteed for encountered factors. ([SymPy Docs][5])

```python id="pos5ga"
solve_poly_system([x**5 - x + y**3, y**2 - 1], x, y, strict=True)
# UnsolvableFactorError
```

## 9.7.2 Factor polynomial systems

```python id="qiqg28"
from sympy.solvers.polysys import (
    factor_system,
    factor_system_cond,
    factor_system_bool,
    factor_system_poly,
)

factor_system([x**2 - 1, y - 1], [x, y])
factor_system_bool([x**2 - 1, y - 1])
factor_system_cond([a*x*(x - 1), b*y, c], [x, y])
```

The polysys docs describe factor-system APIs that decompose polynomial equation systems into irreducible subsystems, Boolean DNF, or condition-including components. `factor_system` returns only generic solutions; `factor_system_cond` includes degenerate parameter conditions; `factor_system_poly` is the core implementation for `Poly` inputs. ([SymPy Docs][5])

Return-shape meaning:

```text id="z63etk"
[]    = no generic solution / no solution depending function
[[]]  = every value of symbols is a solution
[[...], [...]] = irreducible subsystem components
Boolean expression = DNF equivalent to system
```

## 9.7.3 Polynomial system selection

```text id="vtjfbn"
solve_poly_system:
  exact zero-dimensional polynomial systems, tuple solutions.

nonlinsolve:
  broader nonlinear systems; can represent positive-dimensional solution sets.

groebner:
  ideal-level computation, elimination, membership, reduction.

factor_system:
  component decomposition before solving.

nsolve:
  numeric solutions for specific initial guesses.
```

---

## 9.8 Root isolation, `RootOf`, algebraic roots

## 9.8.1 Exact root APIs

```python id="c2txj2"
sp.roots(poly, x)
sp.ground_roots(poly, x)
sp.all_roots(poly)
sp.real_roots(poly)
sp.rootof(poly, index)
sp.RootOf(poly, x, index)
sp.CRootOf(poly, index)
```

`all_roots()` finds all real and complex roots of a univariate polynomial with rational coefficients of any degree exactly, generally using `RootOf`/`ComplexRootOf`; `real_roots()` computes only real roots and is more efficient when non-real roots are not needed because it avoids costly complex root isolation. `nroots()` is the approximate numerical root API. ([SymPy Docs][3])

```python id="vlqyv6"
p = x**9 + 2*x + 2

sp.real_roots(p)
# [CRootOf(x**9 + 2*x + 2, 0)]

[r.evalf(20) for r in sp.real_roots(p)]
```

## 9.8.2 `RootOf` / `CRootOf`

```python id="v2sefq"
r = sp.rootof(4*x**5 + 16*x**3 + 12*x**2 + 7, 0)
r.evalf(30)
```

`RootOf` represents a numbered root of a univariate polynomial; `CRootOf` can reference roots that cannot be expressed in radicals, and evaluation/refinement uses isolating intervals or rectangles. The docs show `rootof(4*x**5 + 16*x**3 + 12*x**2 + 7, 0)` returning a `CRootOf`, with an isolating interval and numeric evaluation. ([SymPy Docs][3])

Deployment rule:

```text id="jm0dg7"
Use roots:
  exact radical/multiplicity dictionary when available.

Use all_roots:
  exact list of all roots, multiplicities repeated.

Use real_roots:
  exact real roots only; cheaper than all_roots for real-root workloads.

Use nroots:
  approximate roots.

Use RootOf/CRootOf:
  exact algebraic-root handles for high-degree or non-radical roots.
```

---

## 9.9 Algebraic numbers and number fields

## 9.9.1 `AlgebraicNumber`, `to_number_field`, `primitive_element`

```python id="q8l1ws"
from sympy import to_number_field, primitive_element, minpoly

eta = sp.sqrt(2)
theta = sp.sqrt(2) + sp.sqrt(3)

a = to_number_field(eta, theta)
a.root
a.coeffs()
```

`to_number_field(extension, theta=None, gen=None, alias=None)` expresses one algebraic number in the field generated by another or computes a primitive element for a list of algebraic numbers; it returns an `AlgebraicNumber` and raises if the element is not in the specified field. `primitive_element()` solves the primitive element problem by finding a single generator for a field generated by several algebraic numbers and can return representations of the original generators in the primitive field. ([SymPy Docs][6])

```python id="m3l1i6"
f_min, lincomb, reps = primitive_element([sp.sqrt(2), sp.sqrt(3)], x, ex=True)

f_min
# x**4 - 10*x**2 + 1

lincomb
# [1, 1]  => sqrt(2) + sqrt(3)
```

## 9.9.2 AlgebraicField domains

```python id="w8wq64"
K = QQ.algebraic_field(sp.sqrt(2))

P = Poly(x**2 + sp.sqrt(2)*x + 1, x, domain=K)
```

Number-field docs show constructing algebraic fields from polynomials or algebraic expressions, e.g. `QQ.algebraic_field((T, theta))`, and using `minimal_polynomial(..., domain=QQ.algebraic_field(sqrt(2)))` to reflect that `sqrt(2)` is already in the coefficient field. ([SymPy Docs][6])

```python id="o5jmuz"
sp.minimal_polynomial(sp.sqrt(2), x)
# x**2 - 2

sp.minimal_polynomial(sp.sqrt(2), x, domain=QQ.algebraic_field(sp.sqrt(2)))
# x - sqrt(2)
```

Deployment rule:

```text id="j3yagf"
Use algebraic fields when coefficients are exact algebraic numbers.
Use to_number_field for shared primitive field representation.
Use RootOf when root-as-object is sufficient and field arithmetic is unnecessary.
```

---

## 9.10 DomainMatrix

## 9.10.1 Purpose and construction

```python id="rg6l2z"
from sympy.polys.matrices import DomainMatrix, DM

A = DM([[1, 2], [3, 4]], ZZ)
B = DomainMatrix.from_Matrix(sp.Matrix([[1, 2], [3, 4]]))
M = A.to_Matrix()
```

`DomainMatrix` is a matrix with elements in a specific `Domain`; it wraps low-level domain-matrix representations and provides conversions between `Expr`, `Matrix`, and polynomial domains. The docs describe it as analogous to a NumPy array with a `dtype`: each element belongs to a domain such as `ZZ` or `QQ<a>`. It can be faster than ordinary SymPy `Matrix` for many common operations but is not fully compatible with `Matrix`. ([SymPy Docs][7])

## 9.10.2 Use cases

```text id="tw7802"
linear algebra over exact domains
matrix algorithms inside polynomial solvers
linear system solving with domain coefficients
determinants/ranks/inverses over ZZ/QQ/algebraic fields
fast bridge between Matrix and polys domains
```

Matrix docs also surface `DomainMatrix` as a method/backend choice, e.g. determinant method `'domain-ge'`, and solving-matrix guidance notes `DomainMatrix` can be faster because it limits the domain of matrix elements. ([SymPy Docs][8])

Deployment rule:

```text id="jb6s4d"
Use Matrix for ergonomic symbolic linear algebra.
Use DomainMatrix when coefficients have a known exact domain and performance matters.
Convert only at boundaries.
Do not assume DomainMatrix supports every Matrix method.
```

---

## 9.11 AGCA: ideals, modules, quotient rings

```python id="u11n32"
R = QQ.old_poly_ring(x)
I = R.ideal(x**2)
F = R.free_module(2)
Qring = R.quotient_ring(I)
```

SymPy’s AGCA module covers algebraic geometry and commutative algebra structures built on polynomial domains. The AGCA docs show `Ring.free_module(rank)`, `Ring.ideal(*gens)`, and `Ring.quotient_ring(e)`, with examples such as `QQ.old_poly_ring(x).free_module(2) -> QQ[x]**2` and `QQ.old_poly_ring(x).ideal(x**2) -> <x**2>`. ([SymPy Docs][9])

Use cases:

```text id="xqws8r"
ideal/module computations
quotient rings
commutative algebra experiments
symbolic algebra infrastructure
advanced algebraic geometry workflows
```

Deployment caveat:

```text id="esxu47"
AGCA is specialist infrastructure.
Prefer groebner/Poly APIs for ordinary elimination/factor/solve tasks.
Use AGCA when ideals/modules/quotients are first-class objects in the problem.
```

---

## 9.12 Performance rules

## 9.12.1 Choose polynomial APIs for repeated polynomial work

```text id="o8029t"
Bad repeated pattern:
  expand/factor/coeff on Expr every loop iteration

Better:
  P = Poly(expr, gens, domain=...)
  use Poly methods repeatedly
  convert back with P.as_expr() once
```

`Poly` explicitly stores generators and domain; domain docs show internal polynomial representations and domain-backed coefficient storage. This avoids repeated inference of generators/domains and routes computations through polynomial algorithms rather than general expression-tree routines. ([SymPy Docs][4])

```python id="hv74nk"
P = Poly(expr, x, y, domain=QQ)

P.degree(x)
P.coeff_monomial(x**2*y)
P.eval({x: 2})
P.diff(x)
P.gcd(Poly(other, x, y, domain=QQ))
```

## 9.12.2 Pin domains explicitly

```python id="zadl32"
Poly(expr, x, domain=ZZ)
Poly(expr, x, domain=QQ)
Poly(expr, x, domain=QQ.algebraic_field(sp.sqrt(2)))
Poly(expr, x, modulus=5)
```

Default domain inference is convenient but can surprise agents, especially when symbols like `pi` become generators unless explicitly excluded or adjoined to the domain. The polynomial basics docs show `e.as_poly()` treating `pi` as a generator, whereas `e.as_poly(x, y)` treats it as a coefficient in `ZZ[pi]`. ([SymPy Docs][2])

## 9.12.3 Avoid float leakage

```python id="hlesbr"
bad = Poly(1.0*x**2 + x + 1, x)
good = Poly(sp.Rational(1, 1)*x**2 + x + 1, x, domain=QQ)
```

For exact algebra, prefer exact coefficients and exact domains (`ZZ`, `QQ`, algebraic fields, prime `GF(p)`). If floats enter a `Poly`, the coefficient domain may become approximate (`RR`/floating domain), changing available algorithms and exactness.

## 9.12.4 Use domain-specific linear algebra

```python id="s9dg3z"
A = DM([[1, 2], [3, 4]], QQ)
```

`DomainMatrix` can be faster than ordinary `Matrix` for many operations because it works over a known domain; it is a lower-level, domain-aware representation and not a drop-in replacement for every `Matrix` operation. ([SymPy Docs][7])

---

## 9.13 Agent decision matrix

| Task                        | API                                          | Output                             | Advisory                              |
| --------------------------- | -------------------------------------------- | ---------------------------------- | ------------------------------------- |
| polynomial representation   | `Poly(expr, *gens, domain=...)`              | `Poly`                             | pin gens/domain                       |
| expression conversion       | `P.as_expr()`                                | `Expr`                             | use at symbolic boundary              |
| coefficient extraction      | `P.coeff_monomial(...)`, `P.coeffs()`        | exact coeffs                       | avoid `.coeff` on unnormalized `Expr` |
| factorization               | `factor`, `factor_list`, `P.factor_list()`   | factored Expr / structured factors | specify domain/extension/modulus      |
| exact division              | `div/rem/quo/exquo`, `P.div(...)`            | quotient/remainder                 | choose domain explicitly              |
| GCD                         | `gcd`, `gcdex`, `P.gcd(...)`                 | gcd / Bezout tuple                 | exact domains only                    |
| elimination                 | `resultant`, `groebner(..., order='lex')`    | eliminated polynomial / basis      | order variable list intentionally     |
| ideal membership            | `G.contains(f)`, `G.reduce(f)`               | bool / remainder                   | Groebner basis required               |
| polynomial system solve     | `solve_poly_system`                          | list of tuples / `None`            | zero-dimensional exact systems        |
| component decomposition     | `factor_system*`                             | subsystems / Boolean DNF           | parameter degeneracy handling         |
| exact roots                 | `roots`, `all_roots`, `real_roots`, `RootOf` | dict/list/root objects             | avoid `solve` if multiplicity matters |
| numeric roots               | `nroots`                                     | list of approximations             | polynomial-only all-roots numeric     |
| algebraic coefficient field | `QQ.algebraic_field(...)`                    | `AlgebraicField`                   | exact algebraic coefficients          |
| primitive number field      | `to_number_field`, `primitive_element`       | `AlgebraicNumber` / minpoly data   | shared field representation           |
| exact matrix domain ops     | `DomainMatrix`                               | domain matrix                      | performance/solver internals          |
| ideals/modules/quotients    | AGCA APIs                                    | ideal/module/ring objects          | specialist workflows                  |

---

## 9.14 Deployment recipes

## Recipe A — safe `Poly` construction

```python id="w7yiy1"
def make_poly(expr, gens, *, domain=QQ):
    expr = sp.sympify(expr)

    floats = expr.atoms(sp.Float)
    if floats:
        raise ValueError(f"Float contamination in exact polynomial: {floats}")

    return Poly(expr, *gens, domain=domain)
```

## Recipe B — coefficient map

```python id="ygvqwk"
def coeff_map(expr, gens, *, domain=QQ):
    P = make_poly(expr, gens, domain=domain)
    return P.as_dict()
```

## Recipe C — rational polynomial equality

```python id="g1l6du"
def poly_equal(a, b, gens, *, domain=QQ):
    Pa = make_poly(a, gens, domain=domain)
    Pb = make_poly(b, gens, domain=domain)
    return (Pa - Pb).is_zero
```

## Recipe D — elimination by Groebner basis

```python id="xw7607"
def eliminate_with_groebner(eqs, eliminate_vars, keep_vars, *, domain=QQ):
    gens = tuple(eliminate_vars) + tuple(keep_vars)
    G = groebner(eqs, *gens, order="lex", domain=domain)

    keep = set(keep_vars)
    eliminated = [
        g.as_expr()
        for g in G.polys
        if g.as_expr().free_symbols <= keep
    ]

    return G, eliminated
```

## Recipe E — resultant elimination

```python id="tneh53"
def eliminate_one_by_resultant(f, g, var, *, simplify_result=True):
    R = sp.resultant(f, g, var)
    return sp.factor(R) if simplify_result else R
```

## Recipe F — exact root workflow

```python id="00bne0"
def exact_roots(poly_expr, var, *, real_only=False, multiplicities=False):
    P = Poly(poly_expr, var, domain=QQ)

    if real_only:
        return sp.real_roots(P, multiple=not multiplicities)

    if multiplicities:
        return sp.roots(P.as_expr(), var)

    return sp.all_roots(P)
```

## Recipe G — algebraic field coefficient workflow

```python id="772jy6"
def poly_over_algebraic_field(expr, var, *exts):
    K = QQ.algebraic_field(*exts)
    return Poly(expr, var, domain=K)

P = poly_over_algebraic_field(x**2 - 2, x, sp.sqrt(2))
```

## Recipe H — DomainMatrix exact linear algebra

```python id="g9ix49"
def domain_matrix_from_expr_matrix(M, *, domain=QQ):
    M = sp.Matrix(M)
    return DomainMatrix.from_Matrix(M).convert_to(domain)

A = domain_matrix_from_expr_matrix([[1, sp.Rational(1, 2)], [3, 4]], domain=QQ)
```

---

## 9.15 Anti-pattern inventory

| Anti-pattern                                                      | Failure mode                            | Correct pattern                             |
| ----------------------------------------------------------------- | --------------------------------------- | ------------------------------------------- |
| repeated `factor(expr)` in loop                                   | repeated generator/domain inference     | `P = Poly(expr, gens, domain=...)`          |
| omitted gens                                                      | wrong generator set/order               | pass explicit gens                          |
| `pi` accidentally becomes generator                               | wrong polynomial ring                   | pass gens/domain explicitly                 |
| mixing `Poly + Expr`                                              | deprecated/unstable behavior            | convert to `Poly` or `.as_expr()`           |
| floats in exact algebra                                           | approximate domains / weaker algorithms | exact rationals, `QQ`, algebraic fields     |
| `GF(9)` as finite field                                           | not a true field in SymPy               | only `GF(p)` for prime `p`                  |
| lex Groebner directly on huge system                              | combinatorial blowup                    | grevlex/grlex then FGLM if zero-dimensional |
| assuming `solve_poly_system` handles positive-dimensional systems | `None`/failure/incomplete               | use `nonlinsolve` or Groebner analysis      |
| `roots` for high-degree symbolic roots                            | may fail/huge radicals                  | `RootOf`, `all_roots`, `nroots`             |
| `nroots` for exact proof                                          | approximate roots only                  | `RootOf` / exact roots                      |
| `resultant` without factor/square-free cleanup                    | expression swell                        | factor/primitive/sqf preprocessing          |
| `DomainMatrix` as drop-in `Matrix`                                | missing Matrix methods                  | convert at boundary                         |
| AGCA for ordinary polynomial solve                                | unnecessary complexity                  | `Poly`, `groebner`, `solve_poly_system`     |

---

## 9.16 Testing matrix

```python id="mxhj38"
def assert_poly_domain(expr, gens, domain):
    P = Poly(expr, *gens, domain=domain)
    assert P.domain == domain

def assert_factorization(expr, gens, domain=QQ):
    P = Poly(expr, *gens, domain=domain)
    coeff, factors = P.factor_list()
    rebuilt = Poly(coeff, *gens, domain=domain)
    for f, exp in factors:
        rebuilt *= f**exp
    assert rebuilt == P

def assert_groebner_membership(poly, gens, basis_gens):
    G = groebner(basis_gens, *gens)
    assert G.contains(poly) is True

def assert_resultant_eliminates(f, g, var):
    R = sp.resultant(f, g, var)
    assert var not in sp.sympify(R).free_symbols

def assert_exact_roots(poly, var):
    for r in sp.all_roots(poly):
        assert sp.N(poly.subs(var, r), 50).equals(0) or abs(sp.N(poly.subs(var, r), 50)) < sp.S("1e-40")
```

Recommended coverage:

```text id="dh9u5o"
Domains:
  ZZ, QQ, QQ<sqrt(2)>, GF(prime), symbolic coefficient domains

Poly construction:
  explicit gens, omitted gens, symbolic constants, rational coefficients

Operations:
  div/rem/exquo failure, gcdex Bezout identity, discriminant, resultant

Groebner:
  lex/grlex/grevlex order, contains, reduce, zero-dimensional, fglm

Systems:
  solve_poly_system success, strict failure, factor_system decompositions

Roots:
  roots multiplicity, real_roots, all_roots, RootOf evalf, nroots

DomainMatrix:
  Matrix conversion, domain conversion, exact solve/determinant if used

AGCA:
  ideal construction, quotient ring construction, free module construction
```

---

## 9.17 Minimal exact-polynomial harness

```python id="mrw5ln"
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence, Literal

import sympy as sp
from sympy import Poly, QQ, ZZ, GF, groebner
from sympy.polys.matrices import DomainMatrix, DM


@dataclass(frozen=True)
class PolyAudit:
    expr: sp.Expr
    poly: Poly
    gens: tuple[sp.Symbol, ...]
    domain: Any
    degree_list: tuple[int, ...]
    terms: tuple[tuple[tuple[int, ...], sp.Expr], ...]
    has_float: bool


def require_no_float(expr: Any) -> sp.Expr:
    expr = sp.sympify(expr)
    floats = expr.atoms(sp.Float)
    if floats:
        raise ValueError(f"Float atoms not allowed in exact polynomial workflow: {floats}")
    return expr


def make_exact_poly(
    expr: Any,
    gens: Sequence[sp.Symbol],
    *,
    domain=QQ,
) -> Poly:
    expr = require_no_float(expr)
    return Poly(expr, *gens, domain=domain)


def audit_poly(expr: Any, gens: Sequence[sp.Symbol], *, domain=QQ) -> PolyAudit:
    P = make_exact_poly(expr, gens, domain=domain)
    return PolyAudit(
        expr=P.as_expr(),
        poly=P,
        gens=P.gens,
        domain=P.domain,
        degree_list=tuple(P.degree(g) for g in P.gens),
        terms=tuple(P.terms()),
        has_float=bool(P.as_expr().atoms(sp.Float)),
    )


def poly_equal(a: Any, b: Any, gens: Sequence[sp.Symbol], *, domain=QQ) -> bool:
    Pa = make_exact_poly(a, gens, domain=domain)
    Pb = make_exact_poly(b, gens, domain=domain)
    return (Pa - Pb).is_zero


def poly_factor_list(expr: Any, gens: Sequence[sp.Symbol], *, domain=QQ):
    return make_exact_poly(expr, gens, domain=domain).factor_list()


def poly_gcdex(f: Any, g: Any, var: sp.Symbol, *, domain=QQ):
    F = make_exact_poly(f, [var], domain=domain)
    G = make_exact_poly(g, [var], domain=domain)
    s, t, h = sp.gcdex(F, G)
    if s*F + t*G != h:
        raise AssertionError("gcdex Bezout identity failed")
    return s, t, h


def poly_resultant(f: Any, g: Any, var: sp.Symbol, *, factor_output: bool = True):
    R = sp.resultant(require_no_float(f), require_no_float(g), var)
    return sp.factor(R) if factor_output else R


def poly_discriminant(f: Any, var: sp.Symbol):
    return sp.discriminant(require_no_float(f), var)


def groebner_basis(
    equations: Sequence[Any],
    gens: Sequence[sp.Symbol],
    *,
    domain=QQ,
    order: Literal["lex", "grlex", "grevlex"] = "lex",
    method: Literal["buchberger", "f5b"] | None = None,
):
    eqs = [require_no_float(e) for e in equations]
    kwargs = {"domain": domain, "order": order}
    if method is not None:
        kwargs["method"] = method
    return groebner(eqs, *gens, **kwargs)


def groebner_reduce(poly: Any, equations: Sequence[Any], gens: Sequence[sp.Symbol], *, domain=QQ, order="lex"):
    G = groebner_basis(equations, gens, domain=domain, order=order)
    return G, G.reduce(require_no_float(poly))


def groebner_eliminate(
    equations: Sequence[Any],
    eliminate_vars: Sequence[sp.Symbol],
    keep_vars: Sequence[sp.Symbol],
    *,
    domain=QQ,
):
    gens = tuple(eliminate_vars) + tuple(keep_vars)
    G = groebner_basis(equations, gens, domain=domain, order="lex")
    keep = set(keep_vars)
    eliminated = [g.as_expr() for g in G.polys if g.as_expr().free_symbols <= keep]
    return G, eliminated


def solve_polynomial_system(equations: Sequence[Any], gens: Sequence[sp.Symbol], *, strict: bool = False):
    from sympy import solve_poly_system
    eqs = [require_no_float(e) for e in equations]
    return solve_poly_system(eqs, *gens, strict=strict)


def factor_polynomial_system(equations: Sequence[Any], gens: Sequence[sp.Symbol] = ()):
    from sympy.solvers.polysys import factor_system
    eqs = [require_no_float(e) for e in equations]
    return factor_system(eqs, list(gens))


def exact_roots(
    poly_expr: Any,
    var: sp.Symbol,
    *,
    mode: Literal["roots", "all", "real", "nroots", "rootof"] = "roots",
    digits: int = 30,
):
    expr = require_no_float(poly_expr)

    if mode == "roots":
        return sp.roots(expr, var)
    if mode == "all":
        return sp.all_roots(expr)
    if mode == "real":
        return sp.real_roots(expr)
    if mode == "nroots":
        return sp.nroots(expr, n=digits)
    if mode == "rootof":
        return [sp.rootof(expr, i) for i in range(Poly(expr, var).degree())]

    raise ValueError(f"unknown root mode: {mode}")


def algebraic_field_poly(expr: Any, var: sp.Symbol, *extensions):
    K = QQ.algebraic_field(*extensions)
    return Poly(require_no_float(expr), var, domain=K)


def to_common_number_field(*algebraic_exprs):
    from sympy import to_number_field
    if len(algebraic_exprs) == 1:
        return to_number_field(algebraic_exprs[0])
    return to_number_field(list(algebraic_exprs))


def domain_matrix(M: Any, *, domain=QQ) -> DomainMatrix:
    if isinstance(M, DomainMatrix):
        return M.convert_to(domain)
    return DomainMatrix.from_Matrix(sp.Matrix(M)).convert_to(domain)


def gf_poly(expr: Any, var: sp.Symbol, p: int):
    if not sp.isprime(p):
        raise ValueError("GF(p) should use prime p for field semantics")
    return Poly(require_no_float(expr), var, domain=GF(p))
```

This harness enforces exact coefficients, explicit generators/domains, safe `Poly` construction, factor/GCD/resultant/discriminant workflows, Groebner elimination/reduction, polynomial-system solving, exact/numeric root modes, algebraic-field coefficients, shared number-field conversion, `GF(p)` prime validation, and `DomainMatrix` boundary conversion.

[1]: https://docs.sympy.org/latest/modules/polys/basics.html "Basic functionality of the module - SymPy 1.14.0 documentation"
[2]: https://docs.sympy.org/latest/modules/polys/basics.html?utm_source=chatgpt.com "Basic functionality of the module - SymPy 1.14.0 documentation"
[3]: https://docs.sympy.org/latest/modules/polys/reference.html "Polynomials Manipulation Module Reference - SymPy 1.14.0 documentation"
[4]: https://docs.sympy.org/latest/modules/polys/domainsintro.html "Introducing the Domains of the poly module - SymPy 1.14.0 documentation"
[5]: https://docs.sympy.org/latest/modules/solvers/solvers.html "Solvers - SymPy 1.14.0 documentation"
[6]: https://docs.sympy.org/latest/modules/polys/numberfields.html "Number Fields - SymPy 1.14.0 documentation"
[7]: https://docs.sympy.org/latest/modules/polys/domainmatrix.html "Introducing the domainmatrix of the poly module - SymPy 1.14.0 documentation"
[8]: https://docs.sympy.org/latest/modules/matrices/matrices.html?utm_source=chatgpt.com "Matrices (linear algebra) - SymPy 1.14.0 documentation"
[9]: https://docs.sympy.org/latest/modules/polys/agca.html "AGCA - Algebraic Geometry and Commutative Algebra Module - SymPy 1.14.0 documentation"

# 10) Matrices, linear algebra, tensors, vectors, and arrays — agent-ready deep dive

Continuing the same advanced technical-doc pattern as the supplied reference artifact. 

## 10.0 Layer map: related, not interchangeable

SymPy separates **explicit matrices**, **matrix expressions**, **N-dimensional arrays**, **indexed objects**, **abstract tensors**, and **vector calculus** into distinct modules. The matrix module handles explicit/abstract matrix algebra; the tensor module contains N-dimensional arrays, array expressions, indexed objects, tensor methods, abstract tensors, and tensor operators; the vector module handles coordinate systems, basis vectors, scalar/vector fields, and vector calculus operators. ([SymPy Documentation][1])

```python id="zvi7uq"
import sympy as sp

x, y, z, t = sp.symbols("x y z t")
```

Mental split:

```text id="2sgg9k"
explicit Matrix:
  concrete 2-D element storage; exact row/column linear algebra

MatrixExpr:
  abstract symbolic matrix algebra; shapes known; entries not expanded

N-dim Array:
  explicit tensor-like nested element storage, any rank

Array expressions:
  unevaluated AST for tensorproduct/contraction/diagonal/permutation

IndexedBase / Idx:
  index notation over component arrays; repeated indices imply contraction

abstract tensor module:
  Penrose/Einstein-style abstract index tensors, symmetries, canonicalization

sympy.vector:
  3-D coordinate systems, basis vectors, scalar/vector fields, grad/div/curl
```

---

## 10.1 Explicit matrices: dense/sparse, mutable/immutable

## 10.1.1 Class map

```text id="55vzag"
dense mutable:
  Matrix                 alias/common constructor
  MutableDenseMatrix

dense immutable:
  ImmutableMatrix        alias of ImmutableDenseMatrix
  ImmutableDenseMatrix

sparse mutable:
  SparseMatrix           alias of MutableSparseMatrix
  MutableSparseMatrix

sparse immutable:
  ImmutableSparseMatrix
```

`Matrix` is mutable; this is important for performance, but mutable matrices cannot be used where immutability is required, such as keys in dictionaries or inside many SymPy expressions. `ImmutableMatrix` bridges this by inheriting from `Basic` and `MatrixExpr`, letting immutable matrices interact more naturally with the broader SymPy expression and matrix-expression systems. `SparseMatrix` is an alias of `MutableSparseMatrix`, and `ImmutableSparseMatrix` provides immutable sparse storage. ([SymPy Documentation][2])

```python id="23owmc"
M = sp.Matrix([[1, 2], [3, 4]])              # mutable dense
IM = sp.ImmutableMatrix(M)                   # immutable dense
S = sp.SparseMatrix(3, 3, {(0, 0): 1})        # mutable sparse
IS = sp.ImmutableSparseMatrix(S)             # immutable sparse
```

Mutation:

```python id="zd9g1n"
M[0, 0] = 10

# IM[0, 0] = 10
# TypeError
```

Deployment rule:

```text id="5t19wf"
Use Matrix / SparseMatrix:
  construction, mutation, row operations, algorithmic assembly.

Use ImmutableMatrix / ImmutableSparseMatrix:
  caching, dictionary keys, expression embedding, MatrixExpr interoperability.

Use SparseMatrix:
  large symbolic matrices with many zeros.

Use dense Matrix:
  small/medium exact symbolic linear algebra.
```

---

## 10.2 Matrix construction and shape discipline

## 10.2.1 Basic constructors

```python id="ahk432"
M = sp.Matrix([[1, -1], [3, 4], [0, 2]])
col = sp.Matrix([1, 2, 3])         # list -> column vector

Z = sp.zeros(2, 3)
O = sp.ones(3, 2)
I = sp.eye(3)
D = sp.diag(1, 2, 3)
B = sp.diag(sp.Matrix([[1, 2], [3, 4]]), sp.eye(2))
```

`Matrix` can be constructed from a list of row vectors; a flat list is treated as a column vector. Common constructors include `eye`, `zeros`, `ones`, and `diag`; `diag` accepts numbers and matrices and stacks them diagonally. ([SymPy Documentation][2])

## 10.2.2 Shape properties

```python id="ms6vxw"
M.rows
M.cols
M.shape
len(M)          # number of elements
```

## 10.2.3 Indexing and slicing

```python id="q52zsn"
M[0, 0]         # scalar entry
M[0, :]         # first row as Matrix
M[:, 1]         # second column as Matrix
M[0:2, 0:2]     # submatrix
M[3]            # flat indexing
```

Matrix `__getitem__` accepts flat integer indexes, tuple indexes `(i, j)`, slices, and mixed tuple slices. ([SymPy Documentation][3])

## 10.2.4 Assembly helpers

```python id="25h4ps"
A = sp.Matrix([[1, 2], [3, 4]])
B = sp.Matrix([[5, 6], [7, 8]])

A.row_join(B)
A.col_join(B)
sp.Matrix.hstack(A, B)
sp.Matrix.vstack(A, B)
```

Deployment guardrails:

```text id="r50c3j"
Always inspect shape before multiplication/solve.
Use immutable matrices after assembly, not during assembly.
Prefer SparseMatrix construction from DOK/dict for large sparse systems.
Avoid Python lists as long-lived “matrix IR”; convert to Matrix/Array early.
```

---

## 10.3 Matrix arithmetic

```python id="c8bof8"
A + B
A - B
A * B          # matrix product, not elementwise product
3 * A
A ** 2
A ** -1        # inverse if invertible
A.T            # transpose
A.H            # conjugate transpose / Hermitian adjoint
```

Explicit SymPy matrix multiplication uses `*` for matrix product, scalar multiplication uses scalar `*`, powers use `**`, and inversion can be written as `A**-1`; non-invertible matrices raise a non-invertibility error. ([SymPy Documentation][2])

Elementwise multiplication:

```python id="pxxkdc"
sp.matrix_multiply_elementwise(A, B)
```

Agent rule:

```text id="wkn3mb"
Matrix * Matrix:
  linear-algebra product.

matrix_multiply_elementwise:
  Hadamard/entrywise product.

Do not assume NumPy semantics.
```

---

## 10.4 Determinants, inverses, ranks, spaces, eigen-data

## 10.4.1 Determinant

```python id="n3w5sz"
A.det()
sp.det(A)
A.det(method="bareiss")
A.det(method="berkowitz")
A.det(method="domain-ge")
```

`det()` computes a square matrix determinant and raises for non-square matrices; methods include determinant algorithms such as domain Gaussian elimination. ([SymPy Documentation][2])

## 10.4.2 Inverse

```python id="b5ldxw"
A.inv()
A.inv(method="GE")
A.inv(method="LU")
A.inv(method="ADJ")
A.inv(method="CH")
A.inv(method="LDL")
A.inv(method="QR")
A.inv(try_block_diag=True)
A.inv(iszerofunc=lambda e: e.is_zero)
```

`Matrix.inv()` supports methods `'DM'`, `'DMNC'`, `'GE'`, `'LU'`, `'ADJ'`, `'CH'`, `'LDL'`, and `'QR'`; the default is `DM` if a suitable domain is found, otherwise `GE` for dense matrices and `LDL` for sparse matrices. The inverse routine raises if the determinant is zero; hard symbolic zero detection can require simplification or a custom `iszerofunc`. ([SymPy Documentation][3])

Deployment rule:

```text id="t0t51j"
Prefer solve over inverse for Ax=b.
Use inv only when the inverse itself is required.
Use try_block_diag=True for block-diagonal structures.
Use DomainMatrix-backed paths for exact domain-friendly matrices when possible.
```

## 10.4.3 RREF, rank, nullspace, columnspace

```python id="lp7h2s"
rref_matrix, pivots = A.rref()
A.rank()
A.nullspace()
A.columnspace()
A.rowspace()
```

`rref()` returns `(rref_matrix, pivot_columns)`. `nullspace()` returns a list of column vectors spanning the nullspace; `columnspace()` returns a list of column vectors spanning the column space. ([SymPy Documentation][2])

## 10.4.4 Eigenvalues, eigenvectors, diagonalization

```python id="q5ral9"
A.charpoly()
A.eigenvals()
A.eigenvects()
A.diagonalize()
A.is_diagonalizable()
```

`eigenvals()` returns a dictionary `{eigenvalue: algebraic_multiplicity}`. `eigenvects()` returns tuples `(eigenvalue, algebraic_multiplicity, [eigenvectors])`; if only eigenvalues are needed, `eigenvals()` should be preferred because eigenvectors can be more expensive. ([SymPy Documentation][2])

Deployment rule:

```text id="xa69ox"
Use eigenvals for spectrum only.
Use eigenvects when eigenspaces are needed.
Use charpoly for exact polynomial workflows.
Avoid symbolic eigenvectors on large symbolic matrices unless necessary.
For numeric eigenproblems, hand off to NumPy/SciPy/mpmath after substitution.
```

---

## 10.5 Solving linear systems

## 10.5.1 `Matrix.solve`

```python id="plxuqc"
xvec = A.solve(b)
xvec = A.solve(b, method="GJ")
xvec = A.solve(b, method="LU")
```

`Matrix.solve(rhs, method='GJ')` solves `A*x = rhs` when a unique solution exists and returns a solution `Matrix`; it raises `ValueError` if no unique solution exists or if the matrix is not square. ([SymPy Documentation][3])

## 10.5.2 Decomposition solves

```python id="1hjrih"
A.LUsolve(b)
A.QRsolve(b)
A.cholesky_solve(b)
A.LDLsolve(b)
A.diagonal_solve(b)
A.gauss_jordan_solve(b)
A.pinv_solve(b)
A.solve_least_squares(b, method="QR")
```

`LUsolve(rhs)` solves `A*x = rhs` for symbolic matrices; the docs explicitly say real/complex numeric matrices should use mpmath solvers. `QRsolve` solves `A*x=b`, supports matrix `b` with multiple right-hand sides, is slower but more stable for floating-point arithmetic, and is mainly for educational/symbolic use because `LUsolve` usually uses exact arithmetic. ([SymPy Documentation][3])

## 10.5.3 `linsolve`

```python id="fhk5kr"
sp.linsolve((A, b), x, y, z)
sp.linsolve([eq1, eq2], x, y)
```

Use `linsolve` when system-level semantics, underdetermined systems, inconsistent systems, or `FiniteSet` output are desired; use `Matrix.solve`/decomposition solves when you have a square explicit matrix with a unique solution and want a `Matrix` solution.

Deployment matrix:

```text id="0z8zp1"
Unique square explicit system:
  A.solve(b), A.LUsolve(b)

Repeated same A with many b:
  decomposition solve / reuse strategy

Underdetermined or inconsistent symbolic system:
  linsolve

Least-squares:
  solve_least_squares / QR / PINV

Pure numeric large systems:
  NumPy/SciPy/mpmath, not SymPy exact Matrix
```

---

## 10.6 Matrix normal forms

```python id="cw34ej"
from sympy.matrices.normalforms import smith_normal_form, hermite_normal_form

smith_normal_form(M, domain=sp.ZZ)
hermite_normal_form(M)
hermite_normal_form(M, D=known_multiple, check_rank=True)
```

`smith_normal_form(m, domain=...)` returns the Smith normal form over a principal ideal domain; docs show use over `ZZ`. `hermite_normal_form(A, D=None, check_rank=False)` computes the Hermite normal form of an integer matrix; an optional positive integer `D` can enable a modulo-`D` algorithm to help prevent coefficient explosion when rank assumptions hold. ([SymPy Documentation][4])

Deployment rule:

```text id="7l7cqf"
Use Smith normal form:
  finitely generated abelian groups, module invariants, integer diagonal invariants.

Use Hermite normal form:
  integer lattice/row-column canonicalization, Diophantine/lattice preprocessing.

Pin domain=ZZ when required.
Do not expect transformation matrices unless API explicitly returns them.
```

---

## 10.7 Matrix expressions: abstract symbolic matrix algebra

## 10.7.1 Core objects

```python id="m8hdwn"
from sympy import MatrixSymbol, Identity, ZeroMatrix, BlockMatrix

A = MatrixSymbol("A", 3, 3)
B = MatrixSymbol("B", 3, 3)
u = MatrixSymbol("u", 3, 1)

expr = A*B + B.T
expr2 = (A.T*A).I * A * u
```

`MatrixExpr` is the superclass for matrix expression objects. Matrix expressions represent abstract matrices and linear transformations without expanding entries; `MatrixSymbol('A', 3, 3)` represents a named abstract matrix with known shape. ([SymPy Documentation][5])

## 10.7.2 Expression node types

```text id="snwe89"
MatAdd      matrix sum
MatMul      matrix product
MatPow      matrix power
Transpose   A.T
Inverse     A.I
Trace       trace(A)
Determinant det(A)
HadamardProduct / HadamardPower
BlockMatrix
FunctionMatrix
PermutationMatrix
```

Function matrices can represent extremely dense matrices lazily; the docs show a `FunctionMatrix(1000, 1000, Lambda((i, j), i + j))` whose square remains a `MatPow` expression and whose entries are evaluated lazily. ([SymPy Documentation][6])

```python id="f4y7qe"
from sympy.matrices.expressions import FunctionMatrix
i, j = sp.symbols("i j", integer=True)
F = FunctionMatrix(1000, 1000, sp.Lambda((i, j), i + j))
```

## 10.7.3 Explicit conversion

```python id="w647ys"
explicit = expr.as_explicit()
```

Use `.as_explicit()` only when matrix dimensions are small and element expansion is required. Avoid for large abstract matrices.

Deployment rule:

```text id="hbhjpk"
Use MatrixExpr when:
  dimensions known, entries unknown;
  deriving identities;
  keeping matrix algebra lazy;
  avoiding entry explosion;
  emitting symbolic matrix equations.

Use explicit Matrix when:
  entries are known and algorithms require component computation.
```

---

## 10.8 N-dimensional arrays

## 10.8.1 Explicit N-dim array classes

```python id="75do72"
from sympy import Array
from sympy.tensor.array import (
    ImmutableDenseNDimArray,
    ImmutableSparseNDimArray,
    MutableDenseNDimArray,
    MutableSparseNDimArray,
)

A = Array([[1, 2], [3, 4], [5, 6]])
B = Array(range(12), (2, 3, 2))
```

The N-dimensional array module provides four storage/mutability combinations: dense/sparse × mutable/immutable. `Array` is an abbreviation for `ImmutableDenseNDimArray`; it detects shapes from nested lists/tuples, exposes `.shape`, and exposes `.rank()`. Mutable classes allow element assignment after construction. ([SymPy Documentation][7])

```python id="6xtcx0"
A.shape       # (3, 2)
A.rank()      # 2
A.tolist()

M = MutableDenseNDimArray.zeros(2, 2, 2)
M[0, 1, 1] = x
```

## 10.8.2 Elementwise calculus and functions

```python id="33yg3h"
arr = Array([x**3, x*y, z])

arr.diff(x)
arr.applyfunc(lambda e: e/2)
(1 + x) * arr
```

Array differentiation and scalar multiplication apply elementwise; `applyfunc` applies a function to every element. ([SymPy Documentation][7])

## 10.8.3 Tensor products, contractions, diagonals, permutations

```python id="fw5w2p"
from sympy import tensorproduct, tensorcontraction, tensordiagonal, permutedims

C = Array([[x, y], [z, t]])
D = Array([[2, 1], [0, -1]])

P = tensorproduct(C, D)
contracted = tensorcontraction(P, (1, 2))     # matrix product equivalent
diag = tensordiagonal(C, (0, 1))
perm = permutedims(C, (1, 0))
```

`tensorcontraction` sums over specified axes using zero-based axis numbering; matrix trace is contraction of axes `(0, 1)`, and matrix product can be emulated as `tensorcontraction(tensorproduct(A, B), (1, 2))`. `tensorproduct` applied to two matrices returns a rank-4 array, and `tensordiagonal` joins axes using diagonal constraints. ([SymPy Documentation][7])

Deployment rule:

```text id="q89qaz"
Use Array:
  explicit small/medium tensor data.

Use tensorproduct/tensorcontraction:
  component-level tensor algebra.

Use permutedims:
  axis reorder / transpose generalization.

Use sparse NDim arrays:
  high-rank mostly-zero component tensors.
```

---

## 10.9 Array expressions: unevaluated tensor algebra

```python id="gohtob"
from sympy.tensor.array.expressions import (
    ArraySymbol,
    ArrayTensorProduct,
    ArrayContraction,
    ArrayDiagonal,
    PermuteDims,
)

A = ArraySymbol("A", (3, 2, 4))
A[i, j, k]
A.as_explicit()
```

Array expressions represent N-dimensional arrays without evaluating them, as ASTs of tensor operations. Operators correspond to expression objects: `tensorproduct → ArrayTensorProduct`, `tensorcontraction → ArrayContraction`, `tensordiagonal → ArrayDiagonal`, and `permutedims → PermuteDims`. `ArraySymbol` is the N-dimensional equivalent of `MatrixSymbol`. ([SymPy Documentation][8])

Deployment rule:

```text id="qqiawe"
Use array expressions when:
  tensor dimensions known but entries abstract;
  evaluation would explode;
  you need lazy tensor algebra;
  translating indexed/matrix expressions to tensor operations.

Use explicit Array when:
  component values are known and small enough to materialize.
```

---

## 10.10 Indexed objects and Einstein-style notation

## 10.10.1 `IndexedBase`, `Indexed`, `Idx`

```python id="rx1x1o"
from sympy import IndexedBase, Idx

M = IndexedBase("M")
v = IndexedBase("v")
i, j = sp.symbols("i j", cls=Idx)

expr = M[i, j] * v[j]
```

`IndexedBase`, `Indexed`, and `Idx` represent indexed objects such as `M[i, j]`; `IndexedBase` is the base/stem, `Idx` represents an index and optional range, and an `Indexed` object represents the indexed access. Repeated indices in a product imply summation/contraction. Shape information should be supplied for component-based arrays, code printers, or autowrap; otherwise shape can be inferred from index ranges when available. ([SymPy Documentation][9])

```python id="opfyf6"
n, m = sp.symbols("n m", integer=True, positive=True)

i = Idx("i", m)
j = Idx("j", n)

A = IndexedBase("A", shape=(m, n))
A[i, j].shape
A[i, j].ranges
```

## 10.10.2 Index analysis

```python id="x8n1uv"
from sympy.tensor import get_indices, get_contraction_structure

get_indices(A[i, j])
get_contraction_structure(A[i, j] * v[j])
```

`get_contraction_structure(expr)` determines dummy/summation indices and describes conforming contractions; `get_indices()` extracts free/dummy index information for indexed expressions. ([SymPy Documentation][9])

Deployment rule:

```text id="0loajj"
Use IndexedBase/Idx when:
  generating code loops;
  representing Einstein-style scalar component formulas;
  analyzing contraction structure;
  bridging formula notation and codegen/autowrap.

Do not use IndexedBase as a full tensor-symmetry system.
For abstract tensor symmetries, use sympy.tensor.tensor.
```

---

## 10.11 Abstract tensors and tensor canonicalization

```python id="3ggzbx"
from sympy.tensor.tensor import TensorIndexType, tensor_indices, TensorHead

Lorentz = TensorIndexType("Lorentz", dim=4, dummy_name="L")
i, j, k, l = tensor_indices("i j k l", Lorentz)

A = TensorHead("A", [Lorentz, Lorentz])
T = A(i, -j) * A(j, -k)
```

`TensorIndexType` defines an index type with dimension and optional metric; `TensorHead` defines abstract tensor heads, and covariant indices are represented using a minus sign. The tensor module is for symbolic objects with indices and tensor operations; it is distinct from explicit N-dimensional arrays. ([SymPy Documentation][10])

Canonicalization:

```python id="613pgo"
expr = T.canon_bp()
```

Tensor expressions with dummy indices can be represented in many equivalent ways. SymPy uses the Butler–Portugal algorithm to put tensor expressions in canonical form under slot and dummy symmetries; docs emphasize this avoids exponentially hard equality checking without canonicalization. ([SymPy Documentation][11])

Deployment rule:

```text id="b5be2l"
Use abstract tensor module when:
  tensor index types and variance matter;
  symmetries/canonicalization matter;
  dummy-index equivalence must be handled.

Use Array/ArrayExpr when:
  rank/shape/component axes matter;
  contractions/products/axis permutations are explicit.

Use IndexedBase when:
  codegen loop notation or index-expression analysis matters.
```

---

## 10.12 Vector module: coordinate systems and vector calculus

## 10.12.1 Coordinate systems

```python id="iu7i24"
from sympy.vector import CoordSys3D

R = CoordSys3D("R")

scalar = R.x*R.y*R.z
vector = R.x*R.i + R.y*R.j + R.z*R.k
```

`CoordSys3D` defines coordinate systems with base scalars such as `R.x`, `R.y`, `R.z` and basis vectors such as `R.i`, `R.j`, `R.k`. New coordinate systems can be located or oriented relative to existing systems; direct orientation methods include `orient_new_axis`, `orient_new_body`, `orient_new_space`, and `orient_new_quaternion`. ([SymPy Documentation][12])

```python id="fbj6gs"
theta = sp.Symbol("theta")
B = R.orient_new_axis("B", theta, R.k)
M = R.locate_new("M", 3*R.i + 4*R.j + 5*R.k)
```

## 10.12.2 Vector calculus

```python id="dui1pq"
from sympy.vector import gradient, divergence, curl, express

gradient(scalar)
divergence(vector)
curl(vector)

express(B.i, R)
express(R.x, B, variables=True)
```

`gradient(scalar_field, doit=True)` returns the vector gradient; `divergence(vector, doit=True)` returns divergence; `curl(vector, doit=True)` returns curl. If `doit=False`, component derivatives can remain as `Derivative` instances. `express(expr, system, variables=True)` re-expresses vector/dyadic/scalar expressions in another coordinate system and optionally substitutes coordinate variables into the target system. ([SymPy Documentation][13])

```python id="zmzv2v"
R = CoordSys3D("R")
s = R.x*R.y*R.z
v = R.x*R.y*R.z * (R.i + R.j + R.k)

grad_s = gradient(s)
div_v = divergence(v)
curl_v = curl(v)
```

## 10.12.3 Field predicates and potentials

```python id="ys1osl"
from sympy.vector import (
    is_conservative,
    is_solenoidal,
    scalar_potential,
)

is_conservative(gradient(scalar))
is_solenoidal(curl(vector))
scalar_potential(gradient(scalar), R)
```

The vector API includes conservative/solenoidal checks and scalar potential computation; `scalar_potential(field, coord_sys)` returns a potential without an added integration constant. ([SymPy Documentation][13])

Deployment rule:

```text id="67q2b6"
Use sympy.vector when:
  coordinate-system-aware 3-D vector calculus is required;
  basis vectors and coordinate variables matter;
  gradient/divergence/curl identities are central.

Do not use plain Symbol objects as vectors.
Do not confuse Matrix column vectors with CoordSys3D Vector objects.
Use Matrix for linear algebra; use Vector for geometric vector fields.
```

---

## 10.13 Interoperability boundaries

## 10.13.1 Matrix ↔ Array

```python id="lgzrxl"
M = sp.Matrix([[x, y], [z, t]])
A = sp.Array(M)
M2 = A.tomatrix()
```

Explicit arrays can convert rank-2 arrays to matrices using `.tomatrix()`, and docs show matrix multiplication equivalent to tensor product plus contraction. ([SymPy Documentation][7])

## 10.13.2 MatrixExpr ↔ explicit Matrix

```python id="1ch6oi"
A = sp.MatrixSymbol("A", 2, 2)
B = sp.MatrixSymbol("B", 2, 2)

expr = A*B
# expr.as_explicit() only if entries/dimensions permit explicit construction
```

## 10.13.3 Indexed ↔ codegen/loops

```python id="yp372v"
A = sp.IndexedBase("A", shape=(n, n))
i = sp.Idx("i", n)
j = sp.Idx("j", n)

expr = A[i, j] * x
```

Provide shape/ranges when indexed expressions will be printed, autowrapped, or loop-generated; Indexed docs explicitly call out shape information for code printers/autowrap. ([SymPy Documentation][9])

## 10.13.4 Vector ↔ Matrix

```text id="ldmtfj"
Vector:
  basis-aware geometric vector field.

Matrix:
  component column/row array.

Conversion requires choosing a coordinate system and component order.
```

---

## 10.14 Performance and deployment rules

```text id="k35ose"
Exact symbolic dense small/medium:
  Matrix

Mostly zero:
  SparseMatrix / ImmutableSparseMatrix

Hashable/embed/cache:
  ImmutableMatrix / ImmutableSparseMatrix

Abstract shape algebra:
  MatrixSymbol / MatrixExpr

High-rank explicit component tensor:
  Array / MutableDenseNDimArray / sparse NDim classes

High-rank lazy tensor algebra:
  ArraySymbol / ArrayTensorProduct / ArrayContraction

Index-loop/codegen notation:
  IndexedBase / Idx

Abstract tensor symmetry/canonicalization:
  TensorIndexType / TensorHead / canon_bp

3-D vector calculus:
  CoordSys3D / gradient / divergence / curl
```

Additional deployment constraints:

```text id="kgp5od"
Avoid symbolic inverse in generated numerical code:
  solve systems instead.

Avoid explicit expansion of MatrixExpr/ArrayExpr when dimensions are large:
  keep lazy.

Avoid symbolic eigenvectors of large symbolic matrices:
  expensive / expression swell.

Use DomainMatrix-backed methods where exact polynomial/rational domains dominate:
  determinant/inverse internals may use DomainMatrix paths.

Use NumPy/SciPy/mpmath for numeric large-scale linear algebra:
  SymPy Matrix is symbolic/exact first.
```

---

## 10.15 Common anti-patterns

| Anti-pattern                                                    | Failure mode                         | Correct pattern                           |
| --------------------------------------------------------------- | ------------------------------------ | ----------------------------------------- |
| using mutable `Matrix` as dictionary key                        | unhashable / unsafe                  | `ImmutableMatrix`                         |
| treating `Matrix * Matrix` as elementwise                       | wrong algebra                        | `matrix_multiply_elementwise`             |
| using `A.inv()*b` to solve                                      | expression swell, slow               | `A.solve(b)` / `A.LUsolve(b)`             |
| calling `.as_explicit()` on huge `MatrixExpr`                   | entry explosion                      | keep `MatrixExpr` lazy                    |
| using `Matrix` for high-rank tensor                             | rank limited to 2                    | `Array` / tensor array APIs               |
| using `Array` when abstract dimensions/entries should stay lazy | memory blowup                        | `ArraySymbol` / array expressions         |
| using `IndexedBase` without shape for codegen                   | ambiguous loops/shapes               | pass `shape=...` and `Idx` ranges         |
| using plain `Symbol` as vector                                  | no `.dot`, no basis                  | `CoordSys3D` vectors or Matrix components |
| assuming tensor dummy-index equality structurally               | equivalent forms compare differently | `.canon_bp()` / tensor canonicalization   |
| using SymPy exact matrices for large numeric linear algebra     | poor performance                     | NumPy/SciPy/mpmath                        |
| computing eigenvectors when only eigenvalues needed             | expensive                            | `eigenvals()`                             |
| using HNF/SNF without integer/domain validation                 | domain errors                        | ensure `ZZ` / integer matrix              |

---

## 10.16 Testing matrix

```python id="r6amcv"
def assert_matrix_solution(A, b, x):
    assert sp.simplify(A*x - b) == sp.zeros(A.rows, b.cols)

def assert_inverse(A, Ainv):
    assert sp.simplify(A*Ainv - sp.eye(A.rows)) == sp.zeros(A.rows)

def assert_nullspace(A):
    for v in A.nullspace():
        assert A*v == sp.zeros(A.rows, 1)

def assert_eigenpair(A, lam, v):
    assert sp.simplify(A*v - lam*v) == sp.zeros(A.rows, 1)

def assert_array_matrix_product_equivalence(A, B):
    prod = sp.tensorcontraction(sp.tensorproduct(sp.Array(A), sp.Array(B)), (1, 2))
    assert prod.tomatrix() == A*B

def assert_vector_identity_scalar_potential(phi, R):
    from sympy.vector import gradient, scalar_potential
    assert scalar_potential(gradient(phi), R) == phi
```

Recommended coverage:

```text id="9hs3ip"
Matrices:
  mutable assignment
  immutable assignment failure
  sparse construction
  determinant/inverse/rank/nullspace
  unique/nonunique system solve
  eigenvals/eigenvects

MatrixExpr:
  shape mismatch
  lazy product
  transpose/inverse
  explicit conversion small case

Normal forms:
  HNF/SNF over integer matrices
  domain error cases

Arrays:
  dense/sparse
  mutable/immutable
  rank/shape
  tensorproduct/contraction/diagonal/permutation

Indexed:
  repeated-index contraction
  get_indices/get_contraction_structure
  codegen shape availability

Abstract tensors:
  dummy index canonicalization
  covariant/contravariant index positions
  symmetry-driven simplification

Vector:
  gradient/divergence/curl
  coordinate-system orientation
  express(..., variables=True)
  conservative/solenoidal checks
```

---

## 10.17 Minimal matrix/tensor/vector harness

```python id="4fubrt"
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Literal

import sympy as sp
from sympy.tensor.array import (
    ImmutableDenseNDimArray,
    ImmutableSparseNDimArray,
    MutableDenseNDimArray,
    MutableSparseNDimArray,
)
from sympy.tensor.array.expressions import (
    ArraySymbol,
    ArrayTensorProduct,
    ArrayContraction,
    ArrayDiagonal,
    PermuteDims,
)
from sympy.vector import CoordSys3D, gradient, divergence, curl, express


@dataclass(frozen=True)
class MatrixAudit:
    matrix: sp.MatrixBase
    shape: tuple[int, int]
    mutable: bool
    sparse: bool
    rank: int | None
    determinant: sp.Expr | None
    is_square: bool


def matrix_audit(M: Any, *, compute_rank: bool = True, compute_det: bool = False) -> MatrixAudit:
    M = sp.Matrix(M) if not isinstance(M, sp.MatrixBase) else M
    is_square = M.rows == M.cols

    return MatrixAudit(
        matrix=M,
        shape=M.shape,
        mutable=not isinstance(M, (sp.ImmutableMatrix, sp.ImmutableSparseMatrix)),
        sparse=isinstance(M, sp.SparseMatrix),
        rank=M.rank() if compute_rank else None,
        determinant=M.det() if compute_det and is_square else None,
        is_square=is_square,
    )


def immutable_matrix(M: Any) -> sp.ImmutableMatrix:
    return sp.ImmutableMatrix(M)


def sparse_matrix(rows: int, cols: int, entries: dict[tuple[int, int], Any]) -> sp.SparseMatrix:
    return sp.SparseMatrix(rows, cols, entries)


def solve_matrix_system(A: Any, b: Any, *, method: str | None = None) -> sp.Matrix:
    A = sp.Matrix(A)
    b = sp.Matrix(b)

    if method is None:
        return A.solve(b)

    return A.solve(b, method=method)


def solve_matrix_system_lu(A: Any, b: Any) -> sp.Matrix:
    return sp.Matrix(A).LUsolve(sp.Matrix(b))


def inverse_checked(A: Any, *, method: str | None = None) -> sp.Matrix:
    A = sp.Matrix(A)
    if A.rows != A.cols:
        raise ValueError("matrix must be square")
    return A.inv(method=method) if method else A.inv()


def eigen_summary(A: Any) -> dict[str, Any]:
    A = sp.Matrix(A)
    return {
        "charpoly": A.charpoly(),
        "eigenvals": A.eigenvals(),
        "rank": A.rank(),
        "nullspace": A.nullspace(),
        "columnspace": A.columnspace(),
    }


def smith_form(M: Any, *, domain=sp.ZZ) -> sp.Matrix:
    from sympy.matrices.normalforms import smith_normal_form
    return smith_normal_form(sp.Matrix(M), domain=domain)


def hermite_form(M: Any, *, D: int | None = None, check_rank: bool = False) -> sp.Matrix:
    from sympy.matrices.normalforms import hermite_normal_form
    return hermite_normal_form(sp.Matrix(M), D=D, check_rank=check_rank)


@dataclass(frozen=True)
class ArrayAudit:
    array: Any
    shape: tuple[int, ...]
    rank: int
    mutable: bool
    sparse: bool


def array_audit(A: Any) -> ArrayAudit:
    return ArrayAudit(
        array=A,
        shape=tuple(A.shape),
        rank=A.rank(),
        mutable=isinstance(A, (MutableDenseNDimArray, MutableSparseNDimArray)),
        sparse=isinstance(A, (ImmutableSparseNDimArray, MutableSparseNDimArray)),
    )


def dense_array(data: Any, shape: tuple[int, ...] | None = None, *, mutable: bool = False):
    if mutable:
        return MutableDenseNDimArray(data, shape)
    return ImmutableDenseNDimArray(data, shape)


def sparse_array(data: Any = None, shape: tuple[int, ...] | None = None, *, mutable: bool = False):
    if mutable:
        return MutableSparseNDimArray(data, shape)
    return ImmutableSparseNDimArray(data, shape)


def matrix_product_via_arrays(A: Any, B: Any):
    Aarr = sp.Array(A)
    Barr = sp.Array(B)
    return sp.tensorcontraction(sp.tensorproduct(Aarr, Barr), (1, 2))


def array_contract(A: Any, *axes: tuple[int, int]):
    return sp.tensorcontraction(A, *axes)


def array_tensor_product(*args: Any):
    return sp.tensorproduct(*args)


def array_permute(A: Any, permutation: tuple[int, ...]):
    return sp.permutedims(A, permutation)


def lazy_array_symbol(name: str, shape: tuple[int, ...]) -> ArraySymbol:
    return ArraySymbol(name, shape)


def lazy_matrix_symbol(name: str, rows: int, cols: int) -> sp.MatrixSymbol:
    return sp.MatrixSymbol(name, rows, cols)


def indexed_base(name: str, shape: tuple[Any, ...] | None = None) -> sp.IndexedBase:
    if shape is None:
        return sp.IndexedBase(name)
    return sp.IndexedBase(name, shape=shape)


def contraction_structure(expr: Any):
    from sympy.tensor import get_indices, get_contraction_structure
    expr = sp.sympify(expr)
    return {
        "indices": get_indices(expr),
        "contractions": get_contraction_structure(expr),
    }


def vector_system(name: str = "R") -> CoordSys3D:
    return CoordSys3D(name)


def vector_calculus_summary(scalar_field: Any, vector_field: Any, system: CoordSys3D):
    return {
        "gradient": gradient(scalar_field),
        "divergence": divergence(vector_field),
        "curl": curl(vector_field),
        "scalar_field_in_system": express(scalar_field, system, variables=True),
        "vector_field_in_system": express(vector_field, system, variables=True),
    }


def prepare_matrix_for_cache(M: Any):
    if isinstance(M, (sp.ImmutableMatrix, sp.ImmutableSparseMatrix)):
        return M
    if isinstance(M, sp.SparseMatrix):
        return sp.ImmutableSparseMatrix(M)
    return sp.ImmutableMatrix(M)


def reject_explicit_large_matrix_expr(expr: sp.MatrixExpr, *, max_entries: int = 10_000):
    rows, cols = expr.shape
    if rows * cols > max_entries:
        raise ValueError(f"refusing explicit expansion of {rows}x{cols} MatrixExpr")
    return expr.as_explicit()
```

This harness encodes the layer boundaries: mutable vs immutable matrix discipline, explicit solve/inverse/eigen workflows, integer normal forms, dense/sparse N-dimensional arrays, tensorproduct/contraction equivalence, lazy matrix/array symbols, indexed contraction inspection, vector-calculus operations, and safety guards against materializing huge abstract matrix expressions.

[1]: https://docs.sympy.org/latest/modules/matrices/index.html?utm_source=chatgpt.com "Matrices - SymPy 1.14.0 documentation"
[2]: https://docs.sympy.org/latest/tutorials/intro-tutorial/matrices.html "Matrices - SymPy 1.14.0 documentation"
[3]: https://docs.sympy.org/latest/modules/matrices/matrices.html "Matrices (linear algebra) - SymPy 1.14.0 documentation"
[4]: https://docs.sympy.org/latest/modules/matrices/normalforms.html "Matrix Normal Forms - SymPy 1.14.0 documentation"
[5]: https://docs.sympy.org/latest/modules/matrices/expressions.html "Matrix Expressions - SymPy 1.14.0 documentation"
[6]: https://docs.sympy.org/latest/modules/matrices/expressions.html?utm_source=chatgpt.com "Matrix Expressions - SymPy 1.14.0 documentation"
[7]: https://docs.sympy.org/latest/modules/tensor/array.html "N-dim array - SymPy 1.14.0 documentation"
[8]: https://docs.sympy.org/latest/modules/tensor/array_expressions.html "N-dim array expressions - SymPy 1.14.0 documentation"
[9]: https://docs.sympy.org/latest/modules/tensor/indexed.html "Indexed Objects - SymPy 1.14.0 documentation"
[10]: https://docs.sympy.org/latest/modules/tensor/tensor.html?utm_source=chatgpt.com "Tensor - SymPy 1.14.0 documentation"
[11]: https://docs.sympy.org/latest/modules/combinatorics/tensor_can.html "Tensor Canonicalization - SymPy 1.14.0 documentation"
[12]: https://docs.sympy.org/latest/modules/vector/coordsys.html "More about Coordinate Systems - SymPy 1.14.0 documentation"
[13]: https://docs.sympy.org/latest/modules/vector/api/vectorfunctions.html "Essential Functions in sympy.vector (docstrings) - SymPy 1.14.0 documentation"

# 11) Functions: elementary, special, undefined, and custom symbolic functions — agent-ready deep dive

Continuing the same advanced technical-doc pattern as the supplied reference artifact. 

## 11.0 Function-system mental model

SymPy functions are symbolic expression nodes with optional automatic evaluation, differentiation rules, assumptions handlers, rewrites, numerical evaluation hooks, and printing hooks. `Function` has two roles: it is the base class for applied mathematical functions, and it is also a constructor for undefined function classes such as `Function("f")`. Undefined functions hold arguments symbolically; custom functions subclass `Function` and opt into behavior by implementing hooks such as `eval`, `fdiff`, `_eval_rewrite`, `_eval_is_*`, `_eval_evalf`, and printer methods. ([SymPy Documentation][1])

```python id="mfo3z0"
import sympy as sp

x, y, z = sp.symbols("x y z")
n = sp.symbols("n", integer=True)
```

Function taxonomy:

```text id="xmwfak"
built-in elementary:
  sin, cos, tan, sinh, cosh, exp, log, Abs, arg, re, im, Min, Max, floor, ceiling, sqrt

built-in special:
  gamma, beta, erf, besselj, bessely, hyper, meijerg,
  zeta, elliptic_k, legendre, jacobi, hermite, laguerre, ...

undefined functions:
  f = Function("f")
  f(x), f(x, y), Derivative(f(x), x)

custom Function subclasses:
  class MyFunc(Function): ...
```

---

## 11.1 Built-in elementary functions

## 11.1.1 Trigonometric and inverse trigonometric functions

```python id="7sf6v8"
sp.sin(x)
sp.cos(x)
sp.tan(x)
sp.cot(x)
sp.sec(x)
sp.csc(x)

sp.asin(x)
sp.acos(x)
sp.atan(x)
sp.acot(x)
sp.asec(x)
sp.acsc(x)
sp.atan2(y, x)
```

Trigonometric functions evaluate selected exact special values automatically. For example, the `sin` docs state that `sin(x)` automatically evaluates when `x/pi` is rational in cases such as multiples of `pi`, `pi/2`, `pi/3`, `pi/4`, and `pi/6`. ([SymPy Documentation][2])

```python id="gkelr5"
sp.sin(sp.pi)
# 0

sp.cos(sp.pi/3)
# 1/2

sp.tan(sp.pi/4)
# 1

sp.sin(x).diff(x)
# cos(x)
```

Rewrite/simplification tools:

```python id="nnpd1q"
sp.expand_trig(sp.sin(x + y))
sp.trigsimp(sp.sin(x)**2 + sp.cos(x)**2)
sp.sin(x).rewrite(sp.exp)
sp.cos(x).rewrite(sp.exp)
```

Deployment rule:

```text id="zi8rnv"
Use exact arguments with pi/Rational for exact special values.
Use expand_trig for identity expansion.
Use trigsimp for identity reduction.
Use rewrite(exp) for exponential basis, Fourier/algebraic manipulation, or backend compatibility.
```

---

## 11.1.2 Hyperbolic functions

```python id="fhs2wv"
sp.sinh(x)
sp.cosh(x)
sp.tanh(x)
sp.coth(x)
sp.sech(x)
sp.csch(x)

sp.asinh(x)
sp.acosh(x)
sp.atanh(x)
sp.acoth(x)
sp.asech(x)
sp.acsch(x)
```

Hyperbolic functions support differentiation, exact special values, inverse methods, and rewrites. The elementary docs show inverse hyperbolic functions such as `atanh(x)` differentiating to `1/(1 - x**2)` and inverse methods exposed on inverse hyperbolic function classes. ([SymPy Documentation][2])

```python id="rcqiy1"
sp.atanh(x).diff(x)
# 1/(1 - x**2)

sp.sinh(x).rewrite(sp.exp)
# exp(x)/2 - exp(-x)/2
```

---

## 11.1.3 Exponential and logarithmic functions

```python id="geduya"
sp.exp(x)
sp.log(x)
sp.log(x, 2)
sp.LambertW(x)
sp.exp_polar(x)
```

`exp(x)` represents `e**x`, differentiates to itself, and evaluates exact identities such as `exp(I*pi) -> -1`. `log(x)` is the natural logarithm; `log(x, b)` is shorthand for `log(x)/log(b)`. SymPy’s `log` represents the **principal branch** of the natural logarithm and has a branch cut along the negative real axis, returning values with complex argument in `(-pi, pi]`. ([SymPy Documentation][2])

```python id="djm54v"
sp.exp(x).diff(x)
# exp(x)

sp.exp(sp.I*sp.pi)
# -1

sp.log(8, 2)
# 3

sp.log(-1 + sp.I*sp.sqrt(3))
# log(2) + 2*I*pi/3
```

Branch-aware deployment rule:

```text id="6f1egc"
logcombine / expand_log:
  valid only under positivity/real-domain preconditions unless force=True is intentional.

rewrite(exp):
  useful for algebraic transformation;
  branch behavior must be tested for complex-domain expressions.
```

---

## 11.1.4 Complex-component functions: `Abs`, `arg`, `re`, `im`, conjugation

```python id="pdjzbg"
sp.Abs(x)
sp.arg(x)
sp.re(x)
sp.im(x)
sp.conjugate(x)
sp.sign(x)
```

Use these when splitting complex expressions, expressing magnitudes, or controlling assumptions-aware simplifications. `exp(x).as_real_imag()` returns a real/imaginary pair expressed in terms of `re(x)` and `im(x)`, and custom functions can implement `as_real_imag()` to enable `expand_complex()`. ([SymPy Documentation][2])

```python id="l4l9xd"
sp.exp(x).as_real_imag()
# (exp(re(x))*cos(im(x)), exp(re(x))*sin(im(x)))

sp.expand_complex(sp.exp(x))
```

---

## 11.1.5 `Min`, `Max`, `floor`, `ceiling`, `frac`

```python id="lywzpp"
sp.Min(x, y, 0)
sp.Max(x, y, 0)
sp.floor(x)
sp.ceiling(x)
sp.frac(x)
```

These are symbolic functions with assumptions-aware and special-value behavior. `frac(x)` represents the fractional part and returns `0` for integer arguments; it can rewrite as `x - floor(x)`. ([SymPy Documentation][2])

```python id="f4o18j"
n = sp.Symbol("n", integer=True)

sp.frac(n)
# 0

sp.frac(x).rewrite(sp.floor)
# x - floor(x)
```

Deployment rule:

```text id="fhxj6e"
Use Piecewise/Min/Max/floor/ceiling symbolically.
Do not replace them with Python min/max/floor on symbolic inputs.
For numeric deployment, verify lambdify backend supports the target function.
```

---

## 11.2 Special functions

## 11.2.1 Gamma, beta, polygamma family

```python id="olk4xk"
sp.gamma(x)
sp.loggamma(x)
sp.polygamma(0, x)
sp.digamma(x)
sp.trigamma(x)
sp.uppergamma(a, x)
sp.lowergamma(a, x)
sp.beta(x, y)
```

`gamma(x)` extends factorials with `Gamma(n) = (n-1)!` for positive integers and is meromorphic with simple poles at negative integers; it supports exact special values, conjugation, differentiation, and series expansion. The docs show `gamma(4) -> 6`, `gamma(S(3)/2) -> sqrt(pi)/2`, and `diff(gamma(x), x) -> gamma(x)*polygamma(0, x)`. ([SymPy Documentation][3])

```python id="yyv9ri"
sp.gamma(4)
# 6

sp.gamma(sp.S(3)/2)
# sqrt(pi)/2

sp.diff(sp.gamma(x), x)
# gamma(x)*polygamma(0, x)

sp.beta(x, y).rewrite(sp.gamma)
```

Deployment rule:

```text id="evwbhb"
Use gamma/beta functions for exact symbolic special-function formulas.
Use combsimp/gammasimp for factorial/binomial/gamma simplification.
Use evalf/lambdify(mpmath) for high-precision numeric special-function evaluation.
```

---

## 11.2.2 Error functions and Fresnel integrals

```python id="a0wjoi"
sp.erf(x)
sp.erfc(x)
sp.erfi(x)
sp.erfinv(x)
sp.fresnels(x)
sp.fresnelc(x)
```

`erf(x)` is defined by an integral, has exact special values at `0`, `oo`, `-oo`, `I*oo`, supports odd symmetry, conjugation, differentiation, and arbitrary-precision complex numerical evaluation. The docs show `erf(0) -> 0`, `erf(oo) -> 1`, `erf(-z) -> -erf(z)`, and `diff(erf(z), z) -> 2*exp(-z**2)/sqrt(pi)`. ([SymPy Documentation][3])

```python id="uuf5tb"
sp.erf(0)
# 0

sp.erf(-x)
# -erf(x)

sp.diff(sp.erf(x), x)
# 2*exp(-x**2)/sqrt(pi)

sp.erf(4).evalf(30)
```

Fresnel functions behave similarly as special-function objects with exact values, differentiation, rewrites via integration, and arbitrary-precision numeric evaluation. ([SymPy Documentation][3])

---

## 11.2.3 Bessel, Hankel, Airy-type functions

```python id="lbp6jv"
sp.besselj(n, x)
sp.bessely(n, x)
sp.besseli(n, x)
sp.besselk(n, x)
sp.hankel1(n, x)
sp.hankel2(n, x)
sp.jn(n, x)
sp.yn(n, x)
sp.airyai(x)
sp.airybi(x)
```

Bessel-type functions share an abstract base that supports differentiation and rewriting in terms of related Bessel-type functions. The docs show `besselj(n, z).diff(z)` becoming `(besselj(n - 1, z) - besselj(n + 1, z))/2`, and `besselj(n, z).rewrite(jn)` converting to spherical Bessel form. ([SymPy Documentation][3])

```python id="i2y6p9"
b = sp.besselj(n, z)

b.diff(z)
# besselj(n - 1, z)/2 - besselj(n + 1, z)/2

b.rewrite(sp.jn)
# sqrt(2)*sqrt(z)*jn(n - 1/2, z)/sqrt(pi)
```

Deployment rule:

```text id="kzpqau"
Use special-function objects as exact symbolic carriers.
Use rewrite(...) to adapt function basis.
Use evalf/lambdify backend only after verifying backend support for that function.
```

---

## 11.2.4 Hypergeometric and Meijer G functions

```python id="npkbti"
sp.hyper((1, 2), (3,), x)
sp.meijerg(((), ()), ((), ()), x)
```

`hyper(ap, bq, z)` requires upper/lower parameter sequences as iterables; it can remove duplicate parameters unless `evaluate=False` is passed. The constructor does not currently check that parameters yield a well-defined function. `hyperexpand()` and `expand_func()` can express many hypergeometric functions in named elementary/special forms; examples include `hyperexpand(hyper([], [], x)) -> exp(x)` and `expand_func(x*hyper([1, 1], [2], -x)) -> log(x + 1)`. ([SymPy Documentation][3])

```python id="xnxv26"
h = sp.hyper((1, 2, 3), [3, 4], x)
# hyper((1, 2), (4,), x)

h_raw = sp.hyper((3, 1, 2), [3, 4], x, evaluate=False)

sp.hyperexpand(sp.hyper([], [], x))
# exp(x)

sp.expand_func(x*sp.hyper([1, 1], [2], -x))
# log(x + 1)
```

Deployment rule:

```text id="50oc8t"
Hypergeometric objects are exact special-function IR.
Use hyperexpand/expand_func to target named functions.
Expect unchanged output for unsupported cases.
Do not assume constructor validates convergence or well-definedness.
```

---

## 11.2.5 Orthogonal polynomials

```python id="htz8vx"
sp.jacobi(n, a, b, x)
sp.gegenbauer(n, a, x)
sp.chebyshevt(n, x)
sp.chebyshevu(n, x)
sp.legendre(n, x)
sp.assoc_legendre(n, m, x)
sp.hermite(n, x)
sp.laguerre(n, x)
```

The special-functions docs include orthogonal polynomial functions such as `jacobi`, `gegenbauer`, `chebyshevt`, `chebyshevu`, `legendre`, `hermite`, and `laguerre`. For fixed integer degree, many evaluate to explicit polynomials; for symbolic degree, they remain symbolic function nodes. The docs show `jacobi(0, a, b, x) -> 1`, explicit formulas for small degrees, symbolic `jacobi(n, a, b, x)` remaining unevaluated, special reductions such as `jacobi(n, 0, 0, x) -> legendre(n, x)`, and differentiation rules. ([SymPy Documentation][3])

```python id="qxrvv8"
sp.jacobi(2, a, b, x)

sp.jacobi(n, 0, 0, x)
# legendre(n, x)

sp.diff(sp.jacobi(n, a, b, x), x)
# proportional jacobi(n - 1, a + 1, b + 1, x)
```

Deployment rule:

```text id="itpgz7"
Use function form for symbolic degree.
Use polys.orthopolys constructors when explicit Poly/polynomial representation is required.
Use rewrite/expand_func carefully; exact polynomial expansion can grow quickly.
```

---

## 11.3 Undefined symbolic functions

## 11.3.1 Creating undefined functions

```python id="fomkw1"
f = sp.Function("f")
g = sp.Function("g", nargs=1)
h = sp.Function("h", nargs=(1, 2))

f(x)
f(x, y)
g(x)
h(x)
h(x, y)
```

`Function("f")` creates an undefined function class; applying it creates an applied function expression. `nargs` constrains accepted arities; with no `nargs`, the function can take any number of arguments. The applied function’s actual arguments are still accessible through `.args`. ([SymPy Documentation][1])

```python id="i11m38"
f = sp.Function("f")

f.nargs
# Naturals0

f(x).args
# (x,)

sp.Function("g", nargs=1).nargs
# {1}

sp.Function("h", nargs=(1, 2)).nargs
# {1, 2}
```

## 11.3.2 Undefined functions in derivatives

```python id="htas58"
f = sp.Function("f")

sp.diff(f(x), x)
# Derivative(f(x), x)

sp.diff(f(x)**2, x)
# 2*f(x)*Derivative(f(x), x)
```

Undefined functions are argument holders until a behavior is provided. Differentiating `f(x)` yields an unevaluated derivative unless the function is replaced with a known function or a custom subclass implements differentiation. ([SymPy Documentation][1])

## 11.3.3 Detecting undefined functions

```python id="x17pgu"
from sympy.core.function import AppliedUndef

expr = f(x) + sp.cos(x) + 2

expr.atoms(sp.Function)
# {f(x), cos(x)}

expr.atoms(AppliedUndef)
# {f(x)}
```

Use `expr.atoms(Function)` to find all applied function nodes, including built-ins; use `AppliedUndef` to find only user-created undefined function applications. The docs show this exact distinction. ([SymPy Documentation][1])

---

## 11.4 Function assumptions and evaluation

## 11.4.1 Assumptions on undefined functions

```python id="x58m52"
f_real = sp.Function("f", real=True)
f_real(x).is_real
# True

f_pos = sp.Function("f", positive=True)
f_pos(x).is_positive
# True
```

Assumptions can be passed to `Function` similarly to `Symbol`, but those assumptions describe the function value, not relationships between inputs and outputs. The docs explicitly state that assumptions on a function are unrelated to assumptions on its arguments; to encode argument-dependent semantics, subclass `Function` and define assumptions handlers. ([SymPy Documentation][1])

```python id="79hpu2"
f = sp.Function("f", real=True)
u = sp.Symbol("u", complex=True)

f(u).is_real
# True  # by function-value assumption, not argument relation
```

Deployment rule:

```text id="e0m4gk"
Function("f", real=True):
  use only when f(...) is real for all admissible arguments.

Argument-dependent properties:
  subclass Function and implement _eval_is_*.
```

---

## 11.4.2 Automatic evaluation semantics

```python id="l5d2o2"
class MyFunction(sp.Function):
    @classmethod
    def eval(cls, x):
        ...
```

`eval()` is a `@classmethod`; it receives function arguments and should return either a value or `None`. Returning `None` leaves the function unevaluated. The custom-functions guide warns: if a function always evaluates and never stays as a symbolic function node, a normal Python function or a `Piecewise` expression is usually the better design. It also warns not to redefine `__new__` or `__init__` on `Function` subclasses. ([SymPy Documentation][4])

```python id="q0nyit"
class kronecker_like_zero_at_zero(sp.Function):
    @classmethod
    def eval(cls, x):
        if x == 0:
            return sp.Integer(1)
        # return None implicitly => unevaluated
```

Good `eval()` style:

```text id="nfacqb"
evaluate explicit special values only;
return None for generic symbolic input;
avoid expensive computations;
avoid broad assumption-driven evaluation;
do not just return the full mathematical definition for every input.
```

The docs emphasize that `eval()` is not “the mathematical definition” of the function; it specifies when the function automatically evaluates. Over-evaluating in `eval()` prevents representing the custom function as its own node and disables custom hooks from ever being used on that node. ([SymPy Documentation][4])

---

## 11.5 Rewriting functions

## 11.5.1 User-facing `.rewrite(...)`

```python id="a4w2ep"
expr.rewrite(sp.exp)
expr.rewrite(sp.sin, sp.exp)
expr.rewrite([sp.sin, sp.cos], sp.exp)
sp.gamma(x).rewrite(sp.factorial)
sp.beta(x, y).rewrite(sp.gamma)
```

`rewrite()` changes representation into a target function/rule basis. Built-ins implement many rewrite routes, and custom functions implement rewrites with `_eval_rewrite(self, rule, args, **hints)`. The custom-functions guide states that `args` should be used rather than `self.args` because recursive rewrites are already applied to the argument list when deep rewriting is active. ([SymPy Documentation][4])

```python id="otmznl"
(sp.cos(x) + sp.I*sp.sin(x)).rewrite(sp.exp)
# exp(I*x)

sp.beta(x, y).rewrite(sp.gamma)
```

## 11.5.2 Custom `_eval_rewrite`

```python id="8ojfvd"
class versin(sp.Function):
    @classmethod
    def eval(cls, x):
        if x == 0:
            return sp.Integer(0)

    def _eval_rewrite(self, rule, args, **hints):
        x, = args
        if rule == sp.cos:
            return 1 - sp.cos(x)
        if rule == sp.sin:
            return 2*sp.sin(x/2)**2
        return None
```

Unknown rewrite hints should be ignored or propagated. Return `None` when no rewrite applies. ([SymPy Documentation][4])

Deployment rule:

```text id="0731z5"
Use rewrite for:
  backend-compatible function basis,
  simplification enablement,
  integration/solving preprocessing,
  codegen-compatible expression families.

Do not use rewrite as a correctness-neutral “simplify” unless branch/domain effects are tested.
```

---

## 11.6 Custom `Function` subclassing

## 11.6.1 Minimal custom function

```python id="8feqoe"
class versin(sp.Function):
    pass

versin(x)
# versin(x)

isinstance(versin(x), versin)
# True
```

A bare subclass behaves much like an undefined function: all optional behaviors default to remaining unevaluated. The guide states that custom `Function` subclasses opt into behaviors by defining methods; if no differentiation is defined, `diff()` returns an unevaluated `Derivative`. ([SymPy Documentation][4])

---

## 11.6.2 `eval(cls, *args)`: automatic special-value evaluation

```python id="vnr5fi"
class versin(sp.Function):
    @classmethod
    def eval(cls, x):
        n = x / sp.pi
        if isinstance(n, sp.Integer):
            return 1 - (-1)**n
```

```python id="e5xyj2"
versin(sp.pi)
# 2

versin(2*sp.pi)
# 0

versin(x*sp.pi)
# versin(pi*x)
```

Best practices:

```text id="oqoqlx"
eval:
  @classmethod required
  return value for explicit special cases
  return None for generic input
  keep cheap
  avoid recursive expansions
  avoid broad assumption-driven simplification
  do not use for full mathematical definition
```

The guide recommends minimizing automatic evaluation in `eval()`, putting advanced simplifications in `doit()` or rewrite/expand methods, and avoiding expensive operations because SymPy assumes expression construction is cheap. ([SymPy Documentation][4])

---

## 11.6.3 Input-domain validation in `eval`

Bad:

```python id="lrvf2y"
class divides_bad(sp.Function):
    @classmethod
    def eval(cls, m, n):
        if not m.is_integer or not n.is_integer:
            raise TypeError("m and n should be integers")
```

Good:

```python id="zeklnc"
class divides(sp.Function):
    @classmethod
    def eval(cls, m, n):
        if isinstance(m, sp.Integer) and isinstance(n, sp.Integer):
            return sp.Integer(int(n % m == 0))

        if m.is_integer is False or n.is_integer is False:
            raise TypeError("m and n should be integers")
```

When rejecting input domains, fail only on `is_* is False`, not on `None`. The custom-functions guide gives this exact rule: `None` means unknown and should be allowed in type/domain validation contexts; otherwise vanilla symbolic arguments become unusable and valid but undecidable assumptions fail incorrectly. ([SymPy Documentation][4])

---

## 11.6.4 `fdiff(self, argindex=1)`: derivative rule

```python id="ngzz3j"
class versin(sp.Function):
    def fdiff(self, argindex=1):
        if argindex == 1:
            return sp.sin(self.args[0])
        raise sp.core.function.ArgumentIndexError(self, argindex)
```

`fdiff()` returns the derivative with respect to the `argindex`-th argument, without applying the chain rule. `diff()` applies the chain rule automatically. The guide explicitly says `Function` subclasses should use `fdiff()` and should not normally redefine `_eval_derivative()`; non-`Function` `Expr` subclasses use `_eval_derivative()` instead. ([SymPy Documentation][4])

```python id="gydvdv"
versin(x).diff(x)
# sin(x)

versin(x**2).diff(x)
# 2*x*sin(x**2)
```

Multi-argument example:

```python id="sdk3iu"
class FMA(sp.Function):
    """FMA(x, y, z) = x*y + z."""

    def fdiff(self, argindex):
        x, y, z = self.args
        if argindex == 1:
            return y
        if argindex == 2:
            return x
        if argindex == 3:
            return sp.Integer(1)
        raise sp.core.function.ArgumentIndexError(self, argindex)
```

To leave a derivative unevaluated for some argument, raise `ArgumentIndexError`; this is also the default when `fdiff()` is not defined. ([SymPy Documentation][4])

---

## 11.6.5 `_eval_is_*`: assumptions hooks

```python id="q7v1u5"
from sympy.core.logic import fuzzy_and, fuzzy_not

class versin(sp.Function):
    def _eval_is_nonnegative(self):
        x, = self.args
        if x.is_real is True:
            return True

    def _eval_is_positive(self):
        x, = self.args
        coeff, pi_part = x.as_independent(sp.pi, as_Add=False)

        if pi_part == sp.pi:
            return fuzzy_and([x.is_real, fuzzy_not(coeff.is_even)])
        elif x.is_real is False:
            return False
        # else None
```

Assumptions handlers must return `True`, `False`, or `None`; they must handle fuzzy three-valued logic correctly. The guide warns never to define `is_<assumption>` as a `@property`; use a class variable for unconditional facts or `_eval_is_<assumption>` for argument-dependent facts. It also recommends avoiding redundant handlers that the assumptions system can infer from other facts. ([SymPy Documentation][4])

Deployment rules:

```text id="cwmy19"
_eval_is_*:
  access arguments via self.args
  use is True / is False / None handling
  use fuzzy_and/fuzzy_or/fuzzy_not
  return None when unknown
  avoid constructing new expressions unnecessarily
  unit-test True, False, None cases
```

---

## 11.6.6 `_eval_evalf(self, prec)`: numerical evaluation

```python id="rhstis"
class versin(sp.Function):
    def _eval_evalf(self, prec):
        x, = self.args
        return (2*sp.sin(x/2)**2)._eval_evalf(prec)
```

`_eval_evalf(self, prec)` defines how the function numerically evaluates to a floating-point value. `prec` is binary precision in bits, not decimal digits; recursive calls inside `_eval_evalf` should call `expr._eval_evalf(prec)`, not `expr.evalf(prec)`, because `evalf()` interprets its first argument as decimal precision. Once `_eval_evalf()` is defined, floating-point inputs can automatically evaluate. ([SymPy Documentation][4])

```python id="p1vmsy"
versin(1).evalf()
# numerical value if _eval_evalf is implemented
```

Deployment rule:

```text id="3lhmsg"
Prefer reusing existing SymPy numeric evaluation internally.
Use mpmath directly only when necessary.
Respect binary precision.
Do not implement low-precision Python float formulas inside _eval_evalf.
```

---

## 11.6.7 `_eval_expand_*`: expansion hooks

```python id="ueci2c"
class versin(sp.Function):
    def _eval_expand_trig(self, **hints):
        x, = self.args
        return sp.expand_trig(1 - sp.cos(x))
```

Custom expansion hooks implement behavior for `expand(hint=True)` calls. Unknown hints should be ignored; `expand()` itself handles recursive expansion via `deep`, so `_eval_expand_*` methods should not recursively call `expand()` on arguments unless explicitly intended. The docs give `_eval_expand_trig` as the custom hook for trig expansion. ([SymPy Documentation][4])

```python id="m72gzl"
versin(x + y).expand(trig=True)
```

---

## 11.6.8 `as_real_imag(self, deep=True, **hints)`

```python id="ddtsot"
class versin(sp.Function):
    def as_real_imag(self, deep=True, **hints):
        x, = self.args
        return (1 - sp.cos(x)).as_real_imag(deep=deep, **hints)
```

Implementing `as_real_imag()` defines complex splitting and enables `expand_complex()` to work on the custom function. If `deep=True`, recursively call `as_real_imag(deep=True, **hints)` on arguments or reuse existing implementations. ([SymPy Documentation][4])

---

## 11.6.9 `inverse(self, argindex=1)`

```python id="1k7kie"
class aversin(sp.Function):
    def inverse(self, argindex=1):
        return versin
```

`inverse()` should return a function, not an expression, and is used by `solve()` and `solveset()`. It should only be defined for one-to-one functions; defining it for non-injective functions may make solvers miss solutions. ([SymPy Documentation][4])

Deployment rule:

```text id="z20tcp"
Only implement inverse for injective branch/domain.
For multibranch functions, use explicit branch-aware functions or avoid inverse().
```

---

## 11.6.10 Printing hooks

```python id="lb5mah"
class divides(sp.Function):
    def _latex(self, printer):
        m, n = self.args
        return r"\left[%s \middle| %s\right]" % (
            printer._print(m),
            printer._print(n),
        )
```

Custom print methods are named according to a printer’s `printmethod`; for LaTeX this is `_latex(self, printer)`. The docs emphasize using `printer._print()` recursively on arguments rather than raw `str()` or direct printer construction. ([SymPy Documentation][4])

Deployment rule:

```text id="2xuzv6"
For a few user-defined functions:
  define method on class, e.g. _latex.

For many functions / library-grade printers:
  implement a custom printer class.

Always recursively print arguments with printer._print.
```

---

## 11.7 Numerical deployment: `evalf`, `lambdify`, `_imp_`, `implemented_function`

## 11.7.1 `lambdify` backend map

```python id="bpcycf"
f_math = sp.lambdify(x, sp.sin(x), modules="math")
f_mp = sp.lambdify(x, sp.sin(x), modules="mpmath")
f_np = sp.lambdify(x, sp.sin(x), modules="numpy")
f_scipy = sp.lambdify(x, sp.erf(x), modules="scipy")
f_jax = sp.lambdify(x, sp.sin(x) + x**2, modules="jax")
```

`lambdify(args, expr, modules=...)` translates SymPy expressions into fast numerical functions. The docs list supported module strings including `"math"`, `"cmath"`, `"mpmath"`, `"numpy"`, `"numexpr"`, `"scipy"`, `"sympy"`, `"tensorflow"`, and `"jax"`, and allow custom dictionaries or prioritized module lists such as `[{"sin": custom_sin}, "numpy"]`. If `modules` is omitted, it defaults to SciPy/NumPy when available, then NumPy, otherwise math/cmath/mpmath/SymPy. ([SymPy Documentation][5])

```python id="dn6kk4"
def mysin(u):
    return 1000  # demo override

f = sp.lambdify(x, sp.sin(x), modules=[{"sin": mysin}, "numpy"])
```

Deployment rule:

```text id="q9qq5e"
Choose exactly one target numeric backend.
Pass inputs compatible with that backend.
Do not call a NumPy-lambdified function with SymPy objects in production.
Use custom module dict for unsupported custom functions.
```

---

## 11.7.2 `_imp_` and `implemented_function`

```python id="n1lu3e"
from sympy.utilities.lambdify import implemented_function

f_impl = implemented_function(sp.Function("f"), lambda u: u + 1)

numeric = sp.lambdify(x, f_impl(x))
numeric(4)
# 5
```

`implemented_function(symfunc, implementation)` attaches a numerical implementation to an undefined function. The docs explicitly describe it as a quick workaround, not a general method for creating special symbolic functions; for full symbolic behavior, subclass `Function`. `lambdify` prefers implementations attached to the `_imp_` attribute unless `use_imps=False`. ([SymPy Documentation][5])

Use decision:

```text id="xzqp2m"
implemented_function:
  quick numeric implementation for lambdify/evalf
  no symbolic behavior beyond undefined-function shell

Function subclass:
  symbolic evaluation, differentiation, assumptions, rewrite, printing, evalf hooks
```

---

## 11.7.3 `dummify`, CSE, docstring cost

```python id="dtuj3s"
f = sp.lambdify([x], sp.sin(x), dummify=True)
g = sp.lambdify(x, large_expr, modules="numpy", cse=True, docstring_limit=0)
```

`dummify=True` replaces invalid or shadowing argument names with dummy symbols. `cse=True` can speed large expression evaluation by extracting common subexpressions, though it slows lambdify construction. `docstring_limit` can reduce lambdify overhead for large expressions by suppressing huge generated docstrings. ([SymPy Documentation][5])

Deployment rule:

```text id="xaf6ms"
Large generated functions:
  cse=True
  docstring_limit=0
  fixed modules backend
  benchmark construction time and call time separately
```

---

## 11.8 Function-library design rules

## 11.8.1 Choose representation strategy first

```text id="f5dq5a"
If expression always expands to existing SymPy expression:
  use Python def returning expression or Piecewise.

If function must remain symbolic, carry identity, and have custom behavior:
  subclass Function.

If only numeric implementation is needed for lambdify:
  implemented_function or lambdify modules dict.

If function is merely shorthand:
  use Python helper, not Function subclass.
```

The custom-functions guide explicitly says that if a `Function` subclass `eval()` always returns a value and never leaves an unevaluated symbolic node, a normal Python function or a built-in symbolic expression such as `Piecewise` is more appropriate. ([SymPy Documentation][4])

---

## 11.8.2 Minimal reusable symbolic function checklist

```text id="rcbrqj"
For each custom Function:
  docstring with mathematical definition and domain
  eval for explicit special values only
  fdiff for derivatives
  _eval_is_* for nontrivial assumptions
  _eval_evalf for numerical approximation
  _eval_rewrite for basis conversion
  _eval_expand_* if expand(...) should know it
  as_real_imag if complex splitting matters
  _latex for display if notation is nonstandard
  inverse only if injective
  tests for symbolic, numeric, assumptions, rewrite, print
```

---

## 11.9 Anti-pattern inventory

| Anti-pattern                                      | Failure mode                         | Correct pattern                                       |
| ------------------------------------------------- | ------------------------------------ | ----------------------------------------------------- |
| `eval()` always returns definition                | custom node never exists             | Python helper or `Piecewise`                          |
| expensive work in `eval()`                        | expression construction becomes slow | move to `doit`, rewrite, simplification hook          |
| broad assumption evaluation in `eval()`           | irreversible over-evaluation         | explicit special values only                          |
| `if not x.is_integer`                             | rejects `None`/unknown valid inputs  | reject only `x.is_integer is False`                   |
| defining `is_positive` as property                | breaks assumptions deduction         | class var or `_eval_is_positive`                      |
| mishandling `None` in `_eval_is_*`                | wrong simplification                 | fuzzy logic helpers                                   |
| redefining `_eval_derivative` on `Function`       | bypasses function conventions        | implement `fdiff`                                     |
| calling `fdiff` directly in user code             | no chain rule                        | use `diff`                                            |
| using `math` functions in symbolic definition     | floats / numeric-only behavior       | use SymPy functions                                   |
| implementing numeric eval with Python float only  | precision loss                       | `_eval_evalf(prec)` with SymPy/mpmath-aware precision |
| `lambdify` custom function without implementation | NameError/backend failure            | modules dict, `_imp_`, or subclass behavior           |
| custom `_latex` uses `str(arg)`                   | broken nested printing               | `printer._print(arg)`                                 |
| defining inverse for non-injective function       | solver misses branches               | avoid or use branch-specific inverse                  |

---

## 11.10 Testing matrix

```python id="vxspgo"
def assert_special_value(fn, arg, expected):
    assert fn(arg) == expected

def assert_derivative(fn_expr, var, expected):
    assert sp.simplify(sp.diff(fn_expr, var) - expected) == 0

def assert_rewrite(expr, target, expected):
    assert sp.simplify(expr.rewrite(target) - expected) == 0

def assert_evalf_close(expr, expected, digits=50):
    assert abs(sp.N(expr, digits) - sp.N(expected, digits)) < sp.S(10)**(-digits//2)

def assert_latex_contains(expr, token):
    assert token in sp.latex(expr)
```

Recommended cases:

```text id="of31cr"
built-ins:
  exact special values, derivatives, rewrites, branch-sensitive logs

undefined functions:
  arity constraints, derivative remains unevaluated, atoms(AppliedUndef)

custom eval:
  explicit values, generic symbolic unevaluated, invalid domain rejection

assumptions:
  True case, False case, None case, derived facts

derivatives:
  direct argument, chain rule argument, unsupported argindex

rewrite:
  supported target, unsupported target returns unchanged

numeric:
  evalf precision, Float input auto-eval, lambdify backend implementation

printing:
  LaTeX nested arguments, default str/repr unaffected

deployment:
  lambdify with modules dict, use_imps=False if needed, docstring/cse large expression
```

---

## 11.11 Minimal custom-function harness

```python id="4zkz4v"
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import sympy as sp
from sympy.core.logic import fuzzy_and, fuzzy_not
from sympy.core.function import ArgumentIndexError, AppliedUndef
from sympy.utilities.lambdify import implemented_function


class versin(sp.Function):
    r"""
    versin(x) = 1 - cos(x) = 2*sin(x/2)**2.
    """

    @classmethod
    def eval(cls, x):
        # Explicit special values only.
        n = x / sp.pi
        if isinstance(n, sp.Integer):
            return 1 - (-1)**n

    def fdiff(self, argindex=1):
        if argindex == 1:
            return sp.sin(self.args[0])
        raise ArgumentIndexError(self, argindex)

    def _eval_is_nonnegative(self):
        x, = self.args
        if x.is_real is True:
            return True

    def _eval_is_positive(self):
        x, = self.args
        coeff, pi_part = x.as_independent(sp.pi, as_Add=False)

        if pi_part == sp.pi:
            return fuzzy_and([x.is_real, fuzzy_not(coeff.is_even)])
        if x.is_real is False:
            return False

    def _eval_evalf(self, prec):
        x, = self.args
        return (2 * sp.sin(x/2)**2)._eval_evalf(prec)

    def _eval_rewrite(self, rule, args, **hints):
        x, = args
        if rule == sp.cos:
            return 1 - sp.cos(x)
        if rule == sp.sin:
            return 2 * sp.sin(x/2)**2

    def _eval_expand_trig(self, **hints):
        x, = self.args
        return sp.expand_trig(1 - sp.cos(x))

    def as_real_imag(self, deep=True, **hints):
        x, = self.args
        return (1 - sp.cos(x)).as_real_imag(deep=deep, **hints)

    def _latex(self, printer):
        x, = self.args
        return r"\operatorname{versin}{\left(%s\right)}" % printer._print(x)


class divides(sp.Function):
    r"""
    divides(m, n) = 1 if m divides n, else 0.
    """

    @classmethod
    def eval(cls, m, n):
        if isinstance(m, sp.Integer) and isinstance(n, sp.Integer):
            if m == 0:
                raise ZeroDivisionError("divisibility by zero is undefined")
            return sp.Integer(int(n % m == 0))

        if m.is_integer is False or n.is_integer is False:
            raise TypeError("m and n should be integers")

    def _eval_is_integer(self):
        return True

    def _eval_is_nonnegative(self):
        return True

    def _eval_is_zero(self):
        m, n = self.args
        if isinstance(m, sp.Integer) and isinstance(n, sp.Integer) and m != 0:
            return n % m != 0

    def _latex(self, printer):
        m, n = self.args
        return r"\left[%s \middle| %s\right]" % (
            printer._print(m),
            printer._print(n),
        )


@dataclass(frozen=True)
class FunctionAudit:
    expr: sp.Basic
    all_functions: set[sp.Function]
    undefined_functions: set[AppliedUndef]
    derivative_nodes: set[sp.Derivative]
    function_classes: set[type]
    has_unimplemented_undefined: bool


def audit_functions(expr: Any) -> FunctionAudit:
    expr = sp.sympify(expr)
    undefined = expr.atoms(AppliedUndef)
    return FunctionAudit(
        expr=expr,
        all_functions=expr.atoms(sp.Function),
        undefined_functions=undefined,
        derivative_nodes=expr.atoms(sp.Derivative),
        function_classes={type(f) for f in expr.atoms(sp.Function)},
        has_unimplemented_undefined=bool(undefined),
    )


def require_no_undefined_functions(expr: Any) -> sp.Expr:
    expr = sp.sympify(expr)
    undef = expr.atoms(AppliedUndef)
    if undef:
        raise ValueError(f"undefined functions remain: {undef}")
    return expr


def lambdify_with_custom_backend(
    args: Any,
    expr: Any,
    *,
    modules: str | list | dict = "numpy",
    custom: dict[str, Callable] | None = None,
    cse: bool = True,
    docstring_limit: int = 0,
):
    expr = sp.sympify(expr)
    if custom:
        module_spec = [custom, modules]
    else:
        module_spec = modules

    return sp.lambdify(
        args,
        expr,
        modules=module_spec,
        cse=cse,
        docstring_limit=docstring_limit,
    )


def implemented_numeric_function(name: str, implementation: Callable):
    return implemented_function(name, implementation)


def symbolic_function(name: str, *, nargs=None, **assumptions):
    if nargs is None:
        return sp.Function(name, **assumptions)
    return sp.Function(name, nargs=nargs, **assumptions)


def rewrite_to_supported_basis(expr: Any, *, target=sp.exp) -> sp.Expr:
    expr = sp.sympify(expr)
    return expr.rewrite(target)


def normalize_function_expression(expr: Any) -> sp.Expr:
    expr = sp.sympify(expr)
    expr = sp.expand_func(expr)
    expr = sp.trigsimp(expr)
    expr = sp.powsimp(expr, combine="exp", deep=True, force=False)
    return expr


def validate_custom_function_contract(fn_cls: type[sp.Function], sample_arg: sp.Expr) -> dict[str, Any]:
    obj = fn_cls(sample_arg)
    return {
        "object": obj,
        "args": obj.args,
        "evalf": obj.evalf(30),
        "diff": sp.diff(obj, sample_arg) if sample_arg.is_Symbol else None,
        "rewrite_cos": obj.rewrite(sp.cos),
        "latex": sp.latex(obj),
        "is_real": obj.is_real,
        "is_positive": obj.is_positive,
        "functions": obj.atoms(sp.Function),
    }
```

This harness enforces the reusable-function-library contract: undefined-function detection, custom `Function` subclass hooks, arity-controlled symbolic functions, numeric implementation injection, backend-aware `lambdify`, rewrite normalization, LaTeX printing, assumptions testing, derivative behavior, and deployment-time rejection of unresolved undefined functions.

[1]: https://docs.sympy.org/latest/modules/core.html "Core - SymPy 1.14.0 documentation"
[2]: https://docs.sympy.org/latest/modules/functions/elementary.html "Elementary - SymPy 1.14.0 documentation"
[3]: https://docs.sympy.org/latest/modules/functions/special.html "Special - SymPy 1.14.0 documentation"
[4]: https://docs.sympy.org/latest/guides/custom-functions.html "Writing Custom Functions - SymPy 1.14.0 documentation"
[5]: https://docs.sympy.org/latest/modules/utilities/lambdify.html "Lambdify - SymPy 1.14.0 documentation"

# 12) Sets, logic, booleans, and relational mathematics — agent-ready deep dive

Continuing the same advanced technical-doc pattern as the supplied reference artifact. 

## 12.0 Layer map: fuzzy booleans vs symbolic booleans vs sets

SymPy has multiple truth/logic layers. **Fuzzy booleans** are low-level Python `True` / `False` / `None` values returned by assumptions queries such as `x.is_positive`; `None` means “unknown.” **Symbolic booleans** are SymPy expression nodes such as `And`, `Or`, `Not`, `Eq`, and `x > 0`; these can remain unevaluated and participate in symbolic manipulation. **Sets** represent domains and solution collections, with `solveset` returning `Set` objects and `ConditionSet` representing partial/unevaluated solution conditions. ([SymPy Documentation][1])

```python id="du9aaj"
import sympy as sp
from sympy import (
    S, Eq, Ne, Lt, Le, Gt, Ge,
    And, Or, Not, Xor, Implies, Equivalent,
    Interval, FiniteSet, Union, Intersection, Complement,
    ImageSet, Lambda, ConditionSet, Contains,
)

x, y, z = sp.symbols("x y z")
A, B, C, D = sp.symbols("A B C D")
```

Core distinction:

```text id="eew8k0"
fuzzy bool:
  True / False / None
  produced by assumptions: expr.is_real, expr.is_positive, ask(...)

symbolic Boolean:
  S.true / S.false / And / Or / Not / Eq / Relational / Contains
  symbolic expression object; can be simplified, substituted, solved, converted

set:
  Interval / FiniteSet / Union / ImageSet / ConditionSet / S.Reals / S.Complexes
  mathematical collection / domain / solution representation
```

---

## 12.1 Symbolic booleans

## 12.1.1 Constructors and operators

```python id="byx5ig"
And(A, B)
Or(A, B)
Not(A)
Xor(A, B)
Implies(A, B)
Equivalent(A, B, C)
```

Convenience operators:

```python id="wmorxk"
A & B      # And(A, B)
A | B      # Or(A, B)
~A         # Not(A)
A ^ B      # Xor(A, B)
A >> B     # Implies(A, B)
A << B     # ImpliedBy-style direction; use explicit Implies for clarity
```

`And` and `Or` are logical functions; the docs note that `&`, `|`, `~`, and `^` are convenience operators but are Python bitwise operators, so they produce different results when used on Python integers or Python booleans. For example, `~True` is not SymPy logical negation, while `~true` is. ([SymPy Documentation][2])

```python id="y98rhl"
sp.true
sp.false

~sp.true     # False
~True        # Python integer behavior / deprecation path, not symbolic logic
```

Deployment rule:

```text id="qs83jq"
Use explicit And/Or/Not/Implies/Equivalent in generated code.
Use &, |, ~ only with parenthesized SymPy Boolean operands.
Never use Python and/or/not for symbolic booleans.
Never use ~ on Python bools in SymPy logic code.
```

---

## 12.1.2 Boolean evaluation behavior

```python id="o49xce"
And(A, True)
# A

And(A, False)
# False

Or(A, False)
# A

Or(A, True)
# True

Xor(A, A)
# False
```

`And` evaluates to false as soon as any argument is false and true if all arguments are true; `Or` evaluates to true as soon as any argument is true and false if all are false. `Xor` is true when an odd number of arguments are true. `Implies(A, B)` is equivalent to `~A | B`, and `Equivalent(A, B)` is true when all arguments are logically equivalent. ([SymPy Documentation][2])

---

## 12.1.3 Boolean normal forms

```python id="9xfjv2"
from sympy.logic.boolalg import (
    to_cnf, to_dnf, to_nnf, to_anf,
    is_cnf, is_dnf, is_nnf, is_anf,
    simplify_logic, bool_map,
)

to_cnf(~(A | B) | D)
to_dnf(B & (A | C))
to_nnf(Not((~A & ~B) | (C & D)))
to_anf(A ^ B ^ (A & B))

simplify_logic((~A & ~B & ~C) | (~A & ~B & C))
```

Normal-form tools convert symbolic logic expressions to CNF, DNF, NNF, and ANF. `to_nnf` produces expressions with only `And`, `Or`, and `Not`, with `Not` applied only to literals; `simplify_logic` simplifies boolean functions into SOP/POS-like forms and can use `dontcare` conditions. ([SymPy Documentation][2])

Deployment rule:

```text id="o073vn"
Use CNF:
  SAT solving, clause extraction, implication pipelines.

Use DNF:
  case splitting, rule generation, interval/domain branch extraction.

Use NNF:
  push negations to leaves before custom transforms.

Use ANF:
  XOR/algebraic boolean workflows.

Use simplify_logic:
  human-readable/minimized boolean formulas; cost can grow with variables.
```

---

## 12.1.4 Satisfiability

```python id="z671mw"
from sympy.logic.inference import satisfiable

satisfiable(A & ~A)
# False

satisfiable((A | B) & (A | ~B) & (~A | B))
# {A: True, B: True}

models = satisfiable(A | B, all_models=True)
list(models)
```

`satisfiable(expr)` tests whether a propositional sentence has a model; it returns a model dictionary when satisfiable and `False` when unsatisfiable. With `all_models=True`, it returns a generator of models, and for unsatisfiable input the generator contains the single element `False`. ([SymPy Documentation][2])

Deployment rule:

```text id="5u8j3o"
Use satisfiable for propositional logic.
Do not expect full nonlinear arithmetic solving from propositional satisfiable.
For relational arithmetic constraints, use solveset/reduce_inequalities/nsolve or external SMT.
```

---

## 12.2 Relational objects

## 12.2.1 Constructors

```python id="d9jocq"
Eq(x, y)
Ne(x, y)
Lt(x, y)    # x < y
Le(x, y)    # x <= y
Gt(x, y)    # x > y
Ge(x, y)    # x >= y

sp.Rel(x, y, "<")
sp.Relational(x, y, ">=")
```

Python comparison operators create relational objects when a definite truth value cannot be determined:

```python id="z9lmh5"
x < 2       # StrictLessThan(x, 2)
x <= 2      # LessThan(x, 2)
x > 2       # StrictGreaterThan(x, 2)
x >= 2      # GreaterThan(x, 2)
```

The core docs identify `Ge`, `Gt`, `Le`, and `Lt` as convenience wrappers for inequality relationals and state that Python inequality operators can be used directly, while noting operator gotchas. ([SymPy Documentation][3])

---

## 12.2.2 Equality: `==` vs `Eq`

```python id="redxgc"
(x + 1)**2 == x**2 + 2*x + 1
# False: structural equality

Eq((x + 1)**2, x**2 + 2*x + 1)
# symbolic equation, may remain unevaluated

sp.simplify((x + 1)**2 - (x**2 + 2*x + 1)) == 0
# True
```

Use `==` for structural equality of SymPy expression trees. Use `Eq(lhs, rhs)` to represent a mathematical equation. `Eq`/`Ne` can evaluate to `S.true`/`S.false` when equality or inequality is decidable, or remain as symbolic relational objects when not. The broader relational docs identify relationals as symbolic mathematical objects and distinguish them from Python truth evaluation. ([SymPy Documentation][3])

---

## 12.2.3 Relational anatomy

```python id="3nq108"
r = x + 1 <= y

r.lhs
r.rhs
r.rel_op          # '<='
r.canonical
r.reversed
r.negated
```

Useful relational normalization:

```python id="uzeyel"
def relational_to_zero(rel):
    if isinstance(rel, sp.Equality):
        return sp.simplify(rel.lhs - rel.rhs)
    if isinstance(rel, sp.Relational):
        return rel.func(sp.simplify(rel.lhs - rel.rhs), 0)
    return sp.sympify(rel)
```

Deployment rule:

```text id="fd7ly3"
Use .lhs/.rhs/.rel_op for machine parsing.
Use .canonical before bound extraction.
Convert Eq(lhs, rhs) to lhs-rhs only at solver-normalization boundary.
Keep inequalities as relational objects for reduce_inequalities.
```

---

## 12.2.4 Python comparison gotchas

Bad:

```python id="ttd8cp"
x < y < z
(x < y) and (y < z)
```

Good:

```python id="t1ndb2"
And(x < y, y < z)
(x < y) & (y < z)
```

Python chained inequalities use Python `and` internally and cannot be overloaded reliably by SymPy, so `x < y < z` raises a truth-value error for symbolic objects; the docs explicitly state that chained inequalities must be written with `And`. Python `and` also coerces symbolic relationals to `bool`, which raises `TypeError`. ([SymPy Documentation][3])

Operator-precedence guard:

```python id="sb7g2k"
# Bad / ambiguous:
# x > 0 & x < 1

# Good:
(x > 0) & (x < 1)
And(x > 0, x < 1)
```

---

## 12.3 Fuzzy booleans vs symbolic booleans

## 12.3.1 Fuzzy booleans

```python id="7juu2y"
xp = sp.Symbol("xp", positive=True)
xn = sp.Symbol("xn", negative=True)
xu = sp.Symbol("xu")

xp.is_positive   # True
xn.is_positive   # False
xu.is_positive   # None
```

Assumption queries return Python-level `True`, `False`, or `None`; `None` means unknown/maybe. The symbolic-and-fuzzy-booleans guide emphasizes that these are low-level Python objects rather than SymPy symbolic Boolean expressions. ([SymPy Documentation][1])

Correct branch discipline:

```python id="54m2c8"
q = xu.is_positive

if q is True:
    ...
elif q is False:
    ...
else:
    ...   # unknown
```

Do not write:

```python id="4bcu9q"
if xu.is_positive:
    ...
```

---

## 12.3.2 Symbolic boolean result from uncertain comparisons

```python id="rcy3pl"
xu > 0
# xu > 0  symbolic StrictGreaterThan

xp > 0
# True / S.true-like boolean result depending context
```

The booleans guide explains that an inequality internally asks whether `(a-b).is_extended_positive`; if the fuzzy result is `True` or `False`, SymPy returns symbolic `S.true` or `S.false`; if the result is `None`, it returns an unevaluated relational such as `StrictGreaterThan`. ([SymPy Documentation][1])

Deployment rule:

```text id="mjuuyk"
Assumptions query:
  expr.is_positive -> Python True/False/None

Symbolic comparison:
  expr > 0 -> SymPy Boolean / Relational

ask(Q.pred(expr)):
  Python True/False/None

refine(Boolean, facts):
  symbolic Boolean reduction, not None-returning query
```

---

## 12.4 Sets: construction and operations

## 12.4.1 Base `Set` contract

`Set` is the base class for SymPy mathematical sets; it is not intended to behave like Python’s builtin `set`. Use `FiniteSet` for finite symbolic collections, `Interval` for real intervals, `Union` for set unions, and `S.EmptySet` for the empty set singleton. ([SymPy Documentation][4])

```python id="73obla"
S.EmptySet
S.UniversalSet
S.Naturals
S.Naturals0
S.Integers
S.Rationals
S.Reals
S.Complexes
```

---

## 12.4.2 `Interval`

```python id="d61dd5"
Interval(0, 1)                  # closed [0, 1]
Interval.open(0, 1)             # open (0, 1)
Interval.Lopen(0, 1)            # (0, 1]
Interval.Ropen(0, 1)            # [0, 1)
Interval(0, 1, left_open=True, right_open=False)
Interval(-sp.oo, sp.oo)         # real line
```

Common properties/operations:

```python id="2b9lpc"
I = Interval(0, 1, left_open=True)

I.start
I.end
I.left_open
I.right_open
I.boundary
I.closure
I.contains(x)
x in I
I.as_relational(x)
```

Intervals are real sets; boundaries of intervals are their endpoints regardless of open/closed status, and sets expose operations/properties such as boundary, closure, membership, and relational conversion. ([SymPy Documentation][4])

---

## 12.4.3 `FiniteSet`

```python id="7cemhn"
FiniteSet(1, 2, 3)
FiniteSet(x, y, x)
```

`FiniteSet` is the SymPy set class for finite discrete collections. Unlike Python sets, elements are sympified, duplicates collapse, and ordering is not a semantic contract.

```python id="kifkhb"
fs = FiniteSet(1, 2, x)

fs.contains(2)
2 in fs
len(fs)
list(fs)     # order not semantic
```

The sets docs distinguish `FiniteSet` from the base `Set`, and show `FiniteSet` as iterable while `Interval` is not generally iterable. ([SymPy Documentation][4])

---

## 12.4.4 `Union`, `Intersection`, `Complement`, `SymmetricDifference`

```python id="j6e7vf"
Union(Interval(1, 2), Interval(2, 3))
# Interval(1, 3)

Intersection(Interval(1, 3), Interval(2, 4))
# Interval(2, 3)

Complement(S.Reals, Interval(0, 1))
sp.SymmetricDifference(FiniteSet(1, 2, 3), FiniteSet(3, 4, 5))
```

`Union` represents the union of sets and tries to merge overlapping intervals; `Intersection` represents intersections and can also be accessed through `.intersect`; `Complement` represents set difference; `SymmetricDifference` represents elements in either set but not both. ([SymPy Documentation][4])

Method syntax:

```python id="go04tf"
Aset = Interval(1, 3)
Bset = Interval(2, 4)

Aset.union(Bset)
Aset.intersect(Bset)
Aset.complement(S.Reals)
```

---

## 12.4.5 `ProductSet`

```python id="cr69kz"
sp.ProductSet(Interval(0, 1), FiniteSet(1, 2))
Interval(0, 1) * FiniteSet(1, 2)
```

Use product sets for Cartesian products and multivariate domains. `ProductSet` is a compound set class representing Cartesian products. ([SymPy Documentation][4])

---

## 12.4.6 `ImageSet`

```python id="5u8qdy"
n = sp.Symbol("n", integer=True)

ImageSet(Lambda(n, 2*sp.pi*n), S.Integers)
sp.imageset(n, 2*sp.pi*n, S.Integers)
```

`ImageSet` represents the image of a set under a `Lambda`; the docs state the transformation must be given as a `Lambda` whose number of arguments matches the elements of the base set. It is commonly produced by `imageset()` and by `solveset()` for infinite parametric solution families. ([SymPy Documentation][4])

Use cases:

```text id="gc1ka8"
periodic solution families
integer-parametric roots
mapping domains through symbolic functions
set-valued solver output
```

---

## 12.4.7 `ConditionSet`

```python id="czjpes"
ConditionSet(x, Eq(sp.sin(x), x), S.Reals)
ConditionSet(x, x**2 > 2, Interval(0, 10))
```

`ConditionSet(sym, condition, base_set)` represents `{x | condition(x) is True, x in base_set}`. `solveset` returns `ConditionSet` when it cannot solve all parts of an equation while still preserving partial/conditional solution semantics. ([SymPy Documentation][4])

Deployment rule:

```text id="xhcayo"
Do not treat ConditionSet as failure only.
It is a first-class symbolic set representing unresolved conditions.
For production enumeration/codegen:
  preserve, reject, or hand off to numeric solver explicitly.
```

---

## 12.4.8 Membership: `in`, `.contains`, `Contains`

```python id="7fvnas"
2 in S.Integers
S.Reals.contains(sp.pi)

Contains(2, S.Integers)
Contains(x, S.Reals)
```

`Contains(x, s)` is a symbolic assertion that `x` is an element of set `s`; it evaluates to `True`/`False` when decidable and remains symbolic otherwise. The docs show `Contains(Integer(2), S.Integers) -> True`, `Contains(Integer(-2), S.Naturals) -> False`, and symbolic integer membership remaining as `Contains(...)`. ([SymPy Documentation][4])

Deployment rule:

```text id="0hzy74"
Use `in` only when immediate Python membership answer is acceptable.
Use `.contains` for SymPy evaluation.
Use `Contains` when membership should remain a symbolic Boolean.
```

---

## 12.5 Set–logic conversion

## 12.5.1 `as_relational(symbol)`

```python id="qosy3e"
Interval(0, 1).as_relational(x)
# (0 <= x) & (x <= 1)

Union(Interval(0, 1), Interval(2, 3)).as_relational(x)
Intersection(Interval(0, 2), Interval(1, 3)).as_relational(x)
```

Set classes such as `Union`, `Intersection`, and `SymmetricDifference` expose `as_relational(symbol)`, rewriting set membership into equalities/inequalities and logic operators. ([SymPy Documentation][4])

## 12.5.2 Boolean conditions → sets

```python id="09gqy8"
sp.solveset(x**2 <= 1, x, domain=S.Reals)
sp.reduce_inequalities([x >= 0, x <= 1], x)
```

For solving equations, `solveset` returns `Set` outputs; for inequalities, `reduce_inequalities` returns symbolic Boolean combinations of relational objects. `solveset`’s set output can represent finite, infinite, and conditional solutions, while `solve` cannot distinguish all of these cases. ([SymPy Documentation][5])

---

## 12.6 Domain-aware solving with sets

## 12.6.1 `solveset` domain control

```python id="msvnb2"
sp.solveset(sp.exp(x) - 1, x, domain=S.Complexes)
sp.solveset(sp.exp(x) - 1, x, domain=S.Reals)

sp.solveset(sp.sin(x), x, domain=S.Reals)
```

`solveset(equation, variable, domain=...)` returns a `Set`; the docs emphasize consistent set output, `ConditionSet` for partial/unknown solution sets, support for infinitely many solutions, and clear separation between real and complex domains. ([SymPy Documentation][5])

Solver-output rules:

```text id="5rmkty"
FiniteSet:
  finite explicit solutions

ImageSet:
  parametric infinite solution family

Union:
  union of solution families

Interval:
  continuous range

EmptySet:
  provably no solutions in domain

ConditionSet:
  unresolved/conditional solution subset
```

## 12.6.2 Robust set-output handling

```python id="gjwoej"
def handle_solution_set(sol):
    if sol is S.EmptySet:
        return {"kind": "empty", "values": []}

    if isinstance(sol, sp.FiniteSet):
        return {"kind": "finite", "values": tuple(sol)}

    if isinstance(sol, sp.ConditionSet):
        return {"kind": "conditional", "set": sol}

    if isinstance(sol, sp.ImageSet):
        return {"kind": "image", "set": sol}

    if isinstance(sol, sp.Union):
        return {"kind": "union", "args": sol.args}

    if isinstance(sol, sp.Interval):
        return {"kind": "interval", "set": sol}

    return {"kind": type(sol).__name__, "set": sol}
```

Deployment rule:

```text id="ibh2w2"
Never call list(sol) blindly.
FiniteSet is iterable.
Interval/ImageSet/ConditionSet may be infinite or non-enumerable.
```

---

## 12.7 Boolean simplification and satisfiability workflows

## 12.7.1 Propositional simplification

```python id="z24vq7"
expr = (~A & ~B & ~C) | (~A & ~B & C)

simplify_logic(expr)
# ~A & ~B

simplify_logic(expr, form="dnf")
simplify_logic(expr, form="cnf")
simplify_logic(expr, dontcare=C)
```

`simplify_logic` simplifies a boolean function to a simplified SOP/POS form, returning SymPy `Or` or `And` objects, and accepts a `dontcare` condition to simplify under irrelevant input regions. ([SymPy Documentation][2])

## 12.7.2 SAT-style model finding

```python id="nxjd1c"
def one_model(expr):
    model = satisfiable(expr)
    if model is False:
        return None
    return model

def all_models(expr):
    models = satisfiable(expr, all_models=True)
    return list(models)
```

Use `satisfiable` for propositional Boolean formulas; it returns `False` if no model exists and a model dictionary otherwise. With `all_models=True`, it returns a generator. ([SymPy Documentation][2])

---

## 12.8 Relational/inequality reduction workflows

## 12.8.1 Inequality reduction

```python id="qnrdru"
sp.reduce_inequalities([x >= 0, x**2 <= sp.pi], x)
# (0 <= x) & (x <= sqrt(pi))
```

`reduce_inequalities` is the top-level inequality reducer and returns symbolic relational Boolean expressions. The solving docs recommend using it for inequalities rather than depending on `solve`’s inequality behavior. ([SymPy Documentation][6])

## 12.8.2 Extract relational atoms

```python id="4vjxys"
from sympy.core.relational import Relational

cond = sp.reduce_inequalities([3*x >= 1, x**2 <= sp.pi], x)
rels = [r.canonical for r in cond.atoms(Relational)]

bounds = [(r.lhs, r.rel_op, r.rhs) for r in rels]
```

Use `.canonical` before machine extraction so orientation is normalized.

---

## 12.9 Deployment recipes

## Recipe A — symbolic interval guard

```python id="cdjj19"
def interval_guard(var, lo, hi, *, left_open=False, right_open=False):
    interval = Interval(lo, hi, left_open=left_open, right_open=right_open)
    return interval, interval.as_relational(var)

I, cond = interval_guard(x, 0, 1)
# I = Interval(0, 1)
# cond = (0 <= x) & (x <= 1)
```

## Recipe B — solve over explicit domain

```python id="uhh6f3"
def solve_real(eq, var):
    sol = sp.solveset(eq, var, domain=S.Reals)
    if isinstance(sol, sp.ConditionSet):
        raise NotImplementedError(f"unresolved real solution set: {sol}")
    return sol
```

## Recipe C — safe Boolean composition

```python id="tu9tos"
def all_conditions(*conds):
    return And(*[sp.sympify(c) for c in conds])

def any_condition(*conds):
    return Or(*[sp.sympify(c) for c in conds])

cond = all_conditions(x > 0, x < 1, y >= 0)
```

## Recipe D — relational normalization

```python id="jp0t7d"
def relational_atoms(expr):
    expr = sp.sympify(expr)
    from sympy.core.relational import Relational
    return tuple(sorted((r.canonical for r in expr.atoms(Relational)), key=str))
```

## Recipe E — set membership as symbolic constraint

```python id="lhcy92"
def membership_constraint(expr, domain):
    return Contains(expr, domain)

membership_constraint(x, Interval(0, 1))
```

## Recipe F — propositional satisfiability wrapper

```python id="lqqmdz"
from sympy.logic.inference import satisfiable

def require_satisfiable(boolean_expr):
    model = satisfiable(boolean_expr)
    if model is False:
        raise ValueError(f"unsatisfiable: {boolean_expr}")
    return model
```

## Recipe G — condition-set preservation

```python id="ay8mxx"
def solve_or_preserve(eq, var, domain=S.Complexes):
    sol = sp.solveset(eq, var, domain=domain)

    return {
        "complete": not isinstance(sol, sp.ConditionSet),
        "solution_set": sol,
        "domain": domain,
    }
```

---

## 12.10 Anti-pattern inventory

| Anti-pattern                                    | Failure mode                                   | Correct pattern                                |
| ----------------------------------------------- | ---------------------------------------------- | ---------------------------------------------- |
| `x < y < z`                                     | Python chained comparison truth coercion       | `And(x < y, y < z)`                            |
| `(x < y) and (y < z)`                           | `TypeError: cannot determine truth value`      | `(x < y) & (y < z)` or `And(...)`              |
| `not (x > 0)`                                   | Python truth coercion                          | `Not(x > 0)` or `~(x > 0)`                     |
| missing parentheses around relationals with `&` | precedence bugs                                | `(x > 0) & (x < 1)`                            |
| `==` for equations                              | structural equality, not mathematical equation | `Eq(lhs, rhs)`                                 |
| `if expr.is_positive:`                          | collapses `None` into false branch             | `is True` / `is False` / unknown               |
| `list(solveset(...))`                           | infinite/conditional set failure               | inspect `Set` subtype                          |
| treating `ConditionSet` as empty                | lost solutions                                 | preserve/reject/numerically solve explicitly   |
| using Python `set` for symbolic sets            | no interval/domain operations                  | `FiniteSet`, `Interval`, `Union`               |
| `in` for symbolic membership                    | Python bool expected                           | `Contains(x, S.Reals)` or `.contains(x)`       |
| using `satisfiable` for arithmetic inequalities | propositional-only model semantics             | `reduce_inequalities`, `solveset`, numeric/SMT |
| assuming `Union` preserves interval fragments   | overlapping intervals merge                    | inspect normalized `Union.args`                |
| relying on ordering of `FiniteSet`              | set order non-semantic                         | sort explicitly for display/tests              |

---

## 12.11 Testing matrix

```python id="xqy9di"
def test_boolean_no_python_and():
    cond = And(x < y, y < z)
    assert cond == ((x < y) & (y < z))

def test_fuzzy_branching():
    q = sp.Symbol("u").is_positive
    assert q is None

def test_interval_relational_roundtrip():
    I = Interval(0, 1)
    cond = I.as_relational(x)
    assert cond == And(0 <= x, x <= 1)

def test_satisfiable_false():
    assert satisfiable(A & ~A) is False

def test_solveset_condition_handling():
    sol = sp.solveset(sp.sin(x) - x, x, domain=S.Reals)
    assert isinstance(sol, (sp.Set, sp.ConditionSet))

def test_contains_symbolic():
    c = Contains(x, S.Reals)
    assert isinstance(c, sp.Boolean)
```

Coverage categories:

```text id="gka80m"
Booleans:
  And/Or/Not/Xor/Implies/Equivalent
  simplify_logic
  to_cnf/to_dnf/to_nnf
  satisfiable one/all models

Relationals:
  Eq vs ==
  Lt/Le/Gt/Ge constructors
  canonical orientation
  chained inequality failure
  Python and/or/not rejection

Sets:
  Interval open/closed variants
  FiniteSet duplicate collapse
  Union interval merge
  Intersection/Complement
  ImageSet for periodic families
  ConditionSet preservation
  Contains symbolic membership

Solver domains:
  solveset real vs complex
  EmptySet/FiniteSet/ImageSet/ConditionSet branches
  reduce_inequalities relational output
```

---

## 12.12 Minimal sets/logic harness

```python id="kd62ba"
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Literal

import sympy as sp
from sympy import (
    S, Eq, Ne, Lt, Le, Gt, Ge,
    And, Or, Not, Xor, Implies, Equivalent,
    Interval, FiniteSet, Union, Intersection, Complement,
    ImageSet, Lambda, ConditionSet, Contains,
)
from sympy.core.relational import Relational
from sympy.logic.boolalg import (
    to_cnf, to_dnf, to_nnf, to_anf,
    simplify_logic,
)
from sympy.logic.inference import satisfiable


@dataclass(frozen=True)
class BooleanAudit:
    expr: sp.Basic
    symbolic_boolean_atoms: tuple[sp.Boolean, ...]
    relational_atoms: tuple[Relational, ...]
    cnf: sp.Boolean
    dnf: sp.Boolean
    nnf: sp.Boolean
    satisfiable_model: dict | bool


@dataclass(frozen=True)
class SetAudit:
    set_expr: sp.Set
    kind: str
    is_empty: bool | None
    is_iterable: bool | None
    boundary: sp.Set | None
    closure: sp.Set | None
    relational: sp.Boolean | None


def bool_and(*conds: Any) -> sp.Boolean:
    return And(*[sp.sympify(c) for c in conds])


def bool_or(*conds: Any) -> sp.Boolean:
    return Or(*[sp.sympify(c) for c in conds])


def bool_not(cond: Any) -> sp.Boolean:
    return Not(sp.sympify(cond))


def implication(a: Any, b: Any) -> sp.Boolean:
    return Implies(sp.sympify(a), sp.sympify(b))


def equivalence(*conds: Any) -> sp.Boolean:
    return Equivalent(*[sp.sympify(c) for c in conds])


def exact_equation(lhs: Any, rhs: Any, *, evaluate: bool = True) -> sp.Boolean:
    return Eq(sp.sympify(lhs), sp.sympify(rhs), evaluate=evaluate)


def inequality(lhs: Any, op: Literal["<", "<=", ">", ">="], rhs: Any) -> Relational:
    lhs = sp.sympify(lhs)
    rhs = sp.sympify(rhs)

    if op == "<":
        return Lt(lhs, rhs)
    if op == "<=":
        return Le(lhs, rhs)
    if op == ">":
        return Gt(lhs, rhs)
    if op == ">=":
        return Ge(lhs, rhs)

    raise ValueError(f"invalid operator: {op}")


def relational_to_zero(rel: Any) -> sp.Expr | Relational:
    rel = sp.sympify(rel)

    if isinstance(rel, sp.Equality):
        return sp.simplify(rel.lhs - rel.rhs)

    if isinstance(rel, Relational):
        return rel.func(sp.simplify(rel.lhs - rel.rhs), 0)

    return rel


def relational_bounds(boolean_expr: Any) -> tuple[tuple[Any, str, Any], ...]:
    expr = sp.sympify(boolean_expr)
    rels = [r.canonical for r in expr.atoms(Relational)]
    return tuple(sorted(((r.lhs, r.rel_op, r.rhs) for r in rels), key=str))


def audit_boolean(expr: Any) -> BooleanAudit:
    expr = sp.sympify(expr)

    bool_atoms = tuple(sorted(expr.atoms(sp.Boolean), key=str))
    rel_atoms = tuple(sorted((r.canonical for r in expr.atoms(Relational)), key=str))

    return BooleanAudit(
        expr=expr,
        symbolic_boolean_atoms=bool_atoms,
        relational_atoms=rel_atoms,
        cnf=to_cnf(expr),
        dnf=to_dnf(expr),
        nnf=to_nnf(expr),
        satisfiable_model=satisfiable(expr),
    )


def simplify_boolean(
    expr: Any,
    *,
    form: Literal["cnf", "dnf"] | None = None,
    dontcare: Any | None = None,
    force: bool = False,
) -> sp.Boolean:
    expr = sp.sympify(expr)
    kwargs = {"form": form, "force": force}
    if dontcare is not None:
        kwargs["dontcare"] = sp.sympify(dontcare)
    return simplify_logic(expr, **kwargs)


def interval_domain(
    lo: Any,
    hi: Any,
    *,
    left_open: bool = False,
    right_open: bool = False,
) -> sp.Interval:
    return Interval(sp.sympify(lo), sp.sympify(hi), left_open=left_open, right_open=right_open)


def finite_domain(*values: Any) -> sp.FiniteSet:
    return FiniteSet(*[sp.sympify(v) for v in values])


def union_domain(*sets: sp.Set) -> sp.Set:
    return Union(*sets)


def intersection_domain(*sets: sp.Set) -> sp.Set:
    return Intersection(*sets)


def complement_domain(base: sp.Set, removed: sp.Set) -> sp.Set:
    return Complement(base, removed)


def image_domain(var: sp.Symbol, expr: Any, base_set: sp.Set) -> sp.ImageSet:
    return sp.imageset(var, sp.sympify(expr), base_set)


def condition_domain(var: sp.Symbol, condition: Any, base_set: sp.Set = S.UniversalSet) -> sp.ConditionSet:
    return ConditionSet(var, sp.sympify(condition), base_set)


def contains_symbolic(value: Any, set_expr: sp.Set) -> sp.Boolean:
    return Contains(sp.sympify(value), set_expr)


def set_to_condition(set_expr: sp.Set, var: sp.Symbol) -> sp.Boolean:
    return set_expr.as_relational(var)


def audit_set(set_expr: sp.Set, *, var: sp.Symbol | None = None) -> SetAudit:
    if not isinstance(set_expr, sp.Set):
        raise TypeError(f"expected SymPy Set, got {type(set_expr).__name__}")

    relational = None
    if var is not None:
        try:
            relational = set_expr.as_relational(var)
        except Exception:
            relational = None

    boundary = None
    closure = None
    try:
        boundary = set_expr.boundary
    except Exception:
        pass
    try:
        closure = set_expr.closure
    except Exception:
        pass

    return SetAudit(
        set_expr=set_expr,
        kind=type(set_expr).__name__,
        is_empty=set_expr.is_empty,
        is_iterable=getattr(set_expr, "is_iterable", None),
        boundary=boundary,
        closure=closure,
        relational=relational,
    )


def solve_set(
    equation: Any,
    var: sp.Symbol,
    *,
    domain: sp.Set = S.Complexes,
    reject_condition_set: bool = False,
) -> sp.Set:
    eq = sp.sympify(equation)
    sol = sp.solveset(eq, var, domain=domain)

    if reject_condition_set and isinstance(sol, sp.ConditionSet):
        raise NotImplementedError(f"unresolved ConditionSet: {sol}")

    return sol


def classify_solution_set(sol: sp.Set) -> dict[str, Any]:
    if sol is S.EmptySet:
        return {"kind": "empty", "finite_values": ()}

    if isinstance(sol, sp.FiniteSet):
        return {"kind": "finite", "finite_values": tuple(sol)}

    if isinstance(sol, sp.ConditionSet):
        return {"kind": "conditional", "set": sol, "complete": False}

    if isinstance(sol, sp.ImageSet):
        return {"kind": "image", "set": sol, "complete": True}

    if isinstance(sol, sp.Interval):
        return {"kind": "interval", "set": sol, "complete": True}

    if isinstance(sol, sp.Union):
        return {"kind": "union", "args": sol.args, "complete": True}

    return {"kind": type(sol).__name__, "set": sol}


def reduce_inequality_system(inequalities: Iterable[Any], var: sp.Symbol) -> dict[str, Any]:
    reduced = sp.reduce_inequalities(list(inequalities), var)
    return {
        "reduced": reduced,
        "bounds": relational_bounds(reduced),
        "satisfiable_model": satisfiable(reduced),
    }


def fuzzy_bool_report(expr: Any, predicates: tuple[str, ...] = ("real", "positive", "zero", "integer")):
    expr = sp.sympify(expr)
    return {
        name: getattr(expr, f"is_{name}")
        for name in predicates
    }
```

This harness enforces the core boundary rules: symbolic Boolean construction, relational normalization, safe set construction, set-to-relational conversion, `solveset` domain output handling, `ConditionSet` preservation, inequality-bound extraction, propositional satisfiability, and fuzzy-boolean auditing.

[1]: https://docs.sympy.org/latest/guides/booleans.html?utm_source=chatgpt.com "Symbolic and fuzzy booleans - SymPy 1.14.0 documentation"
[2]: https://docs.sympy.org/latest/modules/logic.html "Logic - SymPy 1.14.0 documentation"
[3]: https://docs.sympy.org/latest/modules/core.html "Core - SymPy 1.14.0 documentation"
[4]: https://docs.sympy.org/latest/modules/sets.html "Sets - SymPy 1.14.0 documentation"
[5]: https://docs.sympy.org/latest/modules/solvers/solveset.html "Solveset - SymPy 1.14.0 documentation"
[6]: https://docs.sympy.org/latest/modules/solvers/solvers.html?utm_source=chatgpt.com "Solvers - SymPy 1.14.0 documentation"

# 13) Discrete math, combinatorics, number theory, and cryptography — agent-ready deep dive

Continuing the same advanced technical-doc pattern as the supplied reference artifact. 

## 13.0 Scope map

SymPy’s discrete-math surface spans two adjacent layers:

```text
symbolic combinatorial functions:
  factorial, binomial, partition, bell, catalan, stirling, fibonacci,
  totient, divisor functions, counting formulas

algorithmic combinatorics objects:
  Permutation, PermutationGroup, named groups, partitions,
  integer partitions, Prufer sequences, subsets, Gray codes, polyhedra

number theory:
  primes, factorization, modular arithmetic, residue arithmetic,
  primitive roots, continued fractions, Diophantine solvers

exact algebra / finite domains:
  ZZ, QQ, GF(p), AlgebraicField, Poly domains

educational cryptography:
  toy/teaching ciphers, RSA/Kid RSA/ElGamal helpers, LFSRs
```

SymPy’s combinatorics docs list partitions, permutations, permutation groups, polyhedra, Prufer sequences, subsets, Gray code, named groups, Galois groups, finitely presented groups, and polycyclic groups as separate combinatorics submodules. ([SymPy Documentation][1])

---

## 13.1 Combinatorial functions

## 13.1.1 Import surface

```python
import sympy as sp

from sympy import (
    factorial, factorial2, subfactorial,
    binomial, bell, bernoulli, catalan, euler, fibonacci, lucas,
    harmonic, partition, stirling,
)

from sympy.functions.combinatorial.factorials import ff, rf
from sympy.functions.combinatorial.numbers import nC, nP, nT
```

The combinatorial-functions module implements symbolic/numeric combinatorial functions such as Bell numbers/polynomials, binomial coefficients, factorials, partitions, divisor sums, totient functions, and Stirling numbers. ([SymPy Documentation][2])

---

## 13.1.2 Factorials, falling/rising factorials, derangements

```python
n, k, x = sp.symbols("n k x", integer=True)

factorial(0)          # 1
factorial(7)          # 5040
factorial(-2)         # zoo
factorial(n)          # factorial(n)

factorial2(5)         # 15
factorial2(-1)        # 1

subfactorial(5)       # 44

ff(x, 5)              # FallingFactorial(x, 5)
rf(x, 5)              # RisingFactorial(x, 5)
```

`factorial(n)` is implemented over nonnegative integers, has the gamma relation `n! = gamma(n + 1)` for nonnegative integers, returns complex infinity for negative integer input, uses a precomputed lookup table for small inputs, and uses the Prime-Swing algorithm for larger inputs. `subfactorial(n)` counts derangements and is recursively cached; `factorial2`, `ff`, and `rf` provide double, falling, and rising factorial forms. ([SymPy Documentation][2])

Rewrite / simplification surface:

```python
expr = ff(n, n - 2)

expr.rewrite(rf)
expr.rewrite(factorial)
expr.rewrite(binomial)
expr.rewrite(sp.gamma)

sp.combsimp(factorial(n) / factorial(n - 3))
```

Deployment rules:

```text
Use factorial/binomial/rf/ff symbolically:
  exact formulas
  summation/product manipulation
  hypergeometric transformations
  combinatorial identities

Use combsimp/gammasimp:
  simplify factorial/binomial/gamma ratios

Avoid:
  expanding huge factorials unless integer value is explicitly required
```

---

## 13.1.3 Binomial coefficients and counting shortcuts

```python
binomial(5, 2)                     # 10
binomial(sp.Rational(5, 4), 3)      # -5/128
binomial(n, 3)                      # binomial(n, 3)

binomial(n, 3).expand(func=True)
sp.expand_func(binomial(n, 3))

nC(5, 2)                            # combinations
nP(5, 2)                            # permutations
nT(5, 2)                            # partitions into k-sized groups
```

`binomial(n, k)` supports the factorial interpretation and falling-factorial interpretation; it works for symbolic and rational arguments. `expand_func(binomial(n, 3))` gives an explicit polynomial formula. `nC`, `nP`, and `nT` count combinations, permutations, and `k`-sized partitions of items, and accept integers, sequences converted to multisets, or multiset dictionaries depending on the function. ([SymPy Documentation][2])

Modulo-prime workflow:

```python
sp.Mod(binomial(156675, 4433, evaluate=False), 10**5 + 3)
```

Use `evaluate=False` when postponing binomial evaluation is required for modular computation; the docs mention fast computation modulo primes via Lucas’ theorem. ([SymPy Documentation][2])

---

## 13.1.4 Partition numbers, Bell/Catalan/Stirling numbers

```python
[partition(i) for i in range(9)]
# [1, 1, 2, 3, 5, 7, 11, 15, 22]

bell(4)
bell(4, x)
bell(6, 2, sp.symbols("x:6")[1:])

catalan(n)
stirling(n, k)
stirling(n, k, kind=1)
stirling(n, k, kind=2)
```

`partition(n)` returns the number of integer partitions of `n`, with negative integer input yielding `0`. `bell(n)` gives Bell numbers, `bell(n, x)` gives Bell polynomials, and `bell(n, k, symbols)` gives partial Bell polynomials. `stirling(n, k)` returns Stirling numbers, with first-kind values counting permutations with `k` cycles and second-kind values counting partitions of `n` distinct items into `k` parts. ([SymPy Documentation][2])

Deployment rules:

```text
Use partition/bell/stirling/catalan:
  exact integer sequences
  combinatorial identity derivation
  symbolic summation support
  generating-function experiments
  educational math tooling

For enumerating actual structures:
  use combinatorics classes / utilities, not only counting functions
```

---

## 13.2 Partitions and integer partitions

## 13.2.1 Set partitions

```python
from sympy.combinatorics import Partition

P = Partition([1, 2], [3], [4, 5])

P.members
P.RGS
P.partition
P.rank
P + 1
P.sort_key()

P2 = Partition.from_rgs([0, 1, 2, 0, 1], list("abcde"))
```

`Partition` represents an abstract set partition: disjoint sets whose union equals the underlying set. It exposes a restricted growth string (`RGS`), which encodes block membership, and `from_rgs()` reconstructs partitions from such encodings. ([SymPy Documentation][3])

## 13.2.2 Integer partitions

```python
from sympy.combinatorics.partitions import IntegerPartition

ip = IntegerPartition([3, 2, 1])
ip.partition
ip.integer
ip.rank
```

`IntegerPartition` represents a partition of a positive integer into positive summands, ignoring order; the docs distinguish integer partitions from compositions, where summand order matters. ([SymPy Documentation][3])

Deployment rules:

```text
Use Partition:
  set partition objects
  RGS encodings
  partition ranking/sorting
  block-structure algorithms

Use IntegerPartition:
  integer partition state
  exact enumeration/classification
  partition-rank workflows

Use partition(n):
  count only, not explicit partition objects
```

---

## 13.3 Permutations

## 13.3.1 Basic construction

```python
from sympy.combinatorics import Permutation

p = Permutation([2, 0, 1])
q = Permutation(0, 1, 2)          # cycle notation
r = Permutation([[0, 1], [2, 3]]) # disjoint cycles-style input
```

SymPy permutations are arrangements of indices `0..n-1`, not arrangements of arbitrary object labels. The docs emphasize that the first element is always index `0`, and permutation array entries refer to indices in the original ordering rather than the original objects themselves. ([SymPy Documentation][4])

## 13.3.2 Common operations

```python
p.size
p.array_form
p.cyclic_form
p.order()
p.signature()
p.inversions()
p.rank()
p**2
~p
p*q
p(0)
```

Deployment rules:

```text
Use Permutation:
  finite bijections on 0-based indices
  cycle/array form transformations
  group generators
  discrete state transitions
  puzzle/state-space math

Do not:
  treat arbitrary labels as permutation elements directly;
  map labels ↔ indices explicitly.
```

Label bridge:

```python
def permutation_from_reordering(original, reordered):
    pos = {value: i for i, value in enumerate(original)}
    return Permutation([pos[value] for value in reordered])
```

---

## 13.4 Permutation groups and named groups

## 13.4.1 `PermutationGroup`

```python
from sympy.combinatorics import Permutation, PermutationGroup

a = Permutation(0, 1, 2)
b = Permutation(0, 1)

G = PermutationGroup(a, b)

G.order()
G.generators
G.degree
G.is_abelian
G.is_transitive()
G.orbit(0)
G.stabilizer(0)
G.generate_schreier_sims()
```

`PermutationGroup(*generators)` defines the group generated by supplied permutations. The docs show it being used for motion groups such as a `2x2` Rubik’s cube example and computing group order. ([SymPy Documentation][5])

## 13.4.2 Named groups

```python
from sympy.combinatorics.named_groups import (
    SymmetricGroup,
    AlternatingGroup,
    CyclicGroup,
    DihedralGroup,
    AbelianGroup,
)

S5 = SymmetricGroup(5)
A5 = AlternatingGroup(5)
C7 = CyclicGroup(7)
D6 = DihedralGroup(6)
```

Named group constructors build standard permutation groups. For example, the docs describe `DihedralGroup(n)` as the group of symmetries of the regular `n`-gon generated by an `n`-cycle rotation and a reflection; `SymmetricGroup(n)` generates the full symmetric group on `n` elements. ([SymPy Documentation][6])

Deployment rules:

```text
Use named groups:
  standard examples
  test cases
  algebra education
  benchmark group algorithms
  model regular polygon / symmetric / alternating symmetries

Use explicit PermutationGroup:
  custom state spaces
  puzzles
  automorphism-like actions
  problem-specific generators
```

---

## 13.5 Polyhedra and symmetry groups

```python
from sympy.combinatorics import Polyhedron
from sympy.combinatorics.named_groups import DihedralGroup

corners = tuple(range(4))
faces = ((0, 1, 2), (0, 1, 3), (0, 2, 3), (1, 2, 3))
P = Polyhedron(corners, faces)
```

`Polyhedron(corners, faces=(), pgroup=())` represents a polyhedral symmetry group object. SymPy’s docs specifically frame it around Platonic-solid symmetry groups and mention tetrahedral, octahedral, and icosahedral groups of orders `12`, `24`, and `60`. ([SymPy Documentation][7])

Deployment rules:

```text
Use Polyhedron:
  decorated permutation action over vertices/faces
  educational symmetry computations
  Platonic-solid style examples
  puzzle/group-action visual reasoning

Do not:
  treat it as a general computational geometry engine.
```

---

## 13.6 Prufer sequences, subsets, and Gray code

## 13.6.1 Prufer sequences

```python
from sympy.combinatorics.prufer import Prufer

P = Prufer([0, 2, 2, 3])
P.prufer_repr
P.tree_repr

P.next()
P.prev()
P.rank
```

Use Prufer sequences for exact labeled-tree enumeration and tree ↔ sequence encoding. SymPy’s combinatorics index lists Prufer sequences as a first-class submodule. ([SymPy Documentation][1])

## 13.6.2 Subsets

```python
from sympy.combinatorics import Subset

S0 = Subset(["c", "d"], ["a", "b", "c", "d"])

S0.subset
S0.superset
S0.next_binary()
S0.prev_binary()
S0.next_lexicographic()
S0.prev_lexicographic()

Subset.bitlist_from_subset(["c", "d"], ["a", "b", "c", "d"])
Subset.subset_from_bitlist(["a", "b", "c", "d"], "0011")
```

`Subset(subset, superset)` represents a subset together with its universe and supports binary and lexicographic enumeration. The docs show `next_binary`, `prev_binary`, and `bitlist_from_subset`. ([SymPy Documentation][8])

## 13.6.3 Gray code

```python
from sympy.combinatorics import GrayCode

G = GrayCode(3)

list(G.generate_gray())
# ['000', '001', '011', '010', '110', '111', '101', '100']
```

A Gray code enumerates all subsets of `n` objects so adjacent subsets differ by adding or deleting a single object; the docs highlight this as useful for efficiently computing subset statistics. ([SymPy Documentation][9])

Deployment rules:

```text
Use Subset:
  deterministic subset enumeration
  binary/lexicographic traversal
  subset ↔ bitmask conversion

Use GrayCode:
  incremental subset updates
  dynamic programming over subsets
  statistics over subset families
  minimal-change enumeration

Use Prufer:
  labeled-tree enumeration and encoding
```

---

## 13.7 Number theory: primes, factorization, divisors

## 13.7.1 Prime testing and generation

```python
from sympy.ntheory import isprime, primerange, prime, primepi, nextprime, prevprime

isprime(13)            # True
isprime(15)            # False

list(primerange(10, 30))
prime(10)
primepi(100)
nextprime(100)
prevprime(100)
```

`isprime` is integer-only; floats are rejected because their limited precision can silently misrepresent integers. The docs describe the algorithm path: trivial-factor checks, sieve lookup when available, deterministic Miller–Rabin bases for small ranges, and a strong BPSW test for larger values; BPSW is probable-prime based but has no known counterexamples. ([SymPy Documentation][10])

Deployment rule:

```text
Use isprime for exact integer primality testing.
Reject floats before ntheory APIs.
Use primerange for generated prime lists.
Use prime/primepi for indexed prime and counting workflows.
Do not use primality functions for symbolic expressions.
```

## 13.7.2 Factorization

```python
from sympy.ntheory import factorint, divisors, divisor_count, proper_divisors

factorint(360)
# {2: 3, 3: 2, 5: 1}

factorint(360, multiple=True)
# [2, 2, 2, 3, 3, 5]

divisors(28)
proper_divisors(28)
divisor_count(360)
```

`factorint(n)` returns prime factors and multiplicities by default; with `multiple=True` it returns a list including multiplicities. Its documented algorithm switches between trial division, Pollard rho, and Pollard p−1, with boolean toggles `use_trial`, `use_rho`, and `use_pm1`; trial division quickly finds small factors and Pollard methods can find larger factors. ([SymPy Documentation][10])

Deployment rule:

```text
Use factorint:
  exact integer factorization
  divisor/totient/multiplicative-function preprocessing
  modular-arithmetic algorithms

Use multiple=True:
  multiset factor list

Guard:
  factoring large semiprimes may be expensive;
  factorint is not a cryptographic attack primitive for modern key sizes.
```

## 13.7.3 Multiplicative functions

```python
from sympy.functions.combinatorial.numbers import (
    totient, reduced_totient,
    divisor_sigma, udivisor_sigma,
    primenu, primeomega,
)

totient(45)
reduced_totient(45)
divisor_sigma(28)
divisor_sigma(28, 2)
primenu(30)
primeomega(20)
```

Some arithmetic functions historically exposed from `sympy.ntheory` have been relocated under `sympy.functions.combinatorial.numbers`; the number-theory page includes deprecation notes for aliases such as `reduced_totient`, `divisor_sigma`, and `udivisor_sigma` in `ntheory`, recommending the combinatorial-functions locations. ([SymPy Documentation][11])

---

## 13.8 Modular arithmetic and residues

## 13.8.1 Core APIs

```python
from sympy.ntheory import (
    n_order, primitive_root, is_primitive_root,
    discrete_log,
    quadratic_residues,
    is_quad_residue,
    sqrt_mod,
    sqrt_mod_iter,
)

sp.Mod(17, 5)
pow(3, 100, 101)

n_order(3, 10)
is_primitive_root(3, 10)
primitive_root(10)
quadratic_residues(11)
is_quad_residue(5, 11)
sqrt_mod(9, 11)
list(sqrt_mod_iter(9, 11))
```

`is_primitive_root(a, p)` checks whether `a` is a primitive root modulo `p`; the docs define primitive root by the condition that `phi(p)` is the smallest positive exponent giving congruence `1 mod p`. Primitive roots exist only for moduli `2`, `4`, `q**e`, and `2*q**e` for odd prime `q`; `primitive_root(p)` returns a primitive root or `None`. ([SymPy Documentation][10])

Deployment rules:

```text
Use n_order:
  multiplicative order modulo n

Use primitive_root / is_primitive_root:
  cyclic unit-group workflows over supported moduli

Use sqrt_mod / is_quad_residue:
  modular square root / residue workflows

Use discrete_log:
  educational/exact small-to-medium modular problems;
  not a production cryptanalysis oracle.
```

---

## 13.9 Continued fractions

```python
from sympy.ntheory.continued_fraction import (
    continued_fraction,
    continued_fraction_periodic,
    continued_fraction_iterator,
    continued_fraction_convergents,
    continued_fraction_reduce,
)

continued_fraction(sp.Rational(43, 19))
continued_fraction_periodic(0, 1, 2)          # sqrt(2)-style quadratic irrational data
it = continued_fraction_iterator(sp.pi)
[next(it) for _ in range(8)]
```

`continued_fraction_iterator(x)` returns an iterator over the continued-fraction expansion of `x`; the docs show examples using `Rational` and `pi`. ([SymPy Documentation][10])

Deployment rules:

```text
Use continued fractions:
  rational approximation
  convergents
  quadratic irrational periodic expansions
  Diophantine approximation
  educational number theory

Guard:
  irrational symbolic inputs may generate infinite iterators;
  consume bounded prefixes explicitly.
```

---

## 13.10 Diophantine solving

```python
from sympy.solvers.diophantine import diophantine

x, y, z = sp.symbols("x y z", integer=True)

diophantine(2*x + 3*y - 5)
diophantine(x**2 + y**2 - z**2)
```

A Diophantine equation is an integer-variable equation `f(x1, ..., xn) = 0`. SymPy’s Diophantine module supports selected classes, including linear Diophantine equations, binary quadratic equations, homogeneous ternary quadratic equations, extended Pythagorean equations, and sums of squares; `diophantine()` factors equations where possible and routes to specialized solvers. ([SymPy Documentation][12])

Deployment rules:

```text
Use diophantine:
  exact integer solution families
  Pythagorean/linear/quadratic integer equations
  symbolic integer-parameter outputs

Always:
  pass expression equal to zero
  use integer symbols for clarity
  expect parameter symbols t_0, t_1, ...
  handle empty set / unsupported class

Do not:
  expect arbitrary integer equations to be solved
```

---

## 13.11 Cryptography module

## 13.11.1 Scope and warning

```python
from sympy.crypto.crypto import (
    encipher_shift, decipher_shift,
    encipher_affine, decipher_affine,
    encipher_vigenere, decipher_vigenere,
    encipher_hill, decipher_hill,
    encipher_bifid5, decipher_bifid5,
    rsa_public_key, rsa_private_key, encipher_rsa, decipher_rsa,
)
```

SymPy’s cryptography module is **educational only**. The docs explicitly warn not to use it for real cryptographic applications and recommend using a production cryptography library for real data. The module includes shift, affine, substitution, Vigenère, Hill, Bifid, RSA, Kid RSA, linear-feedback shift registers, and ElGamal examples. ([SymPy Documentation][13])

## 13.11.2 Shift cipher example

```python
msg = "GONAVYBEATARMY"

ct = encipher_shift(msg, 1)
# 'HPOBWZCFBUBSNZ'

decipher_shift(ct, 1)
# 'GONAVYBEATARMY'
```

The docs show `encipher_shift(msg, 1)` shifting uppercase text and `decipher_shift(ct, 1)` reversing it. ([SymPy Documentation][13])

Deployment rules:

```text
Use sympy.crypto only for:
  classroom demos
  algebraic cipher explanations
  toy RSA/Kid RSA experiments
  number-theory demonstrations
  testing symbolic algorithms over small examples

Never use sympy.crypto for:
  real encryption
  key generation
  password storage
  secure communication
  production security
```

---

## 13.12 Finite fields and algebraic domains

```python
from sympy import Poly, GF, ZZ, QQ

Pz = Poly(x**2 + 1, x)
P2 = Poly(x**2 + 1, x, modulus=2)
P5 = Poly(x**2 + 1, x, domain=GF(5))

sp.factor(x**2 + 1, modulus=2)
sp.cancel((x**2 + 1)/(x + 1), domain=GF(2))
sp.gcd(x**2 + 1, x + 1, domain=GF(2))
```

`GF(p)` represents a finite field of prime order in the polynomial-domain system. A `Poly` over integer coefficients defaults to domain `ZZ`; passing `modulus=p` changes the domain to `GF(p)`. The docs explicitly warn that `GF(9)` can be created but is merely the ring of integers modulo `9`, not a true finite field of order `9`, and prime-power finite fields `GF(p**n)` are not implemented. ([SymPy Documentation][14])

Deployment rules:

```text
Use GF(p) with p prime:
  modular polynomial factorization
  modular GCD/cancel
  finite-field examples

Do not use GF(composite) when field inverses are required.
Do not assume GF(p**n) support.
Use polys domains for exact finite-field algebra, not Python % alone.
```

---

## 13.13 Use-case mapping

| Use case                                     | Preferred surface                                        | Notes                               |
| -------------------------------------------- | -------------------------------------------------------- | ----------------------------------- |
| exact combinatorial formula                  | `factorial`, `binomial`, `stirling`, `bell`, `partition` | symbolic, exact                     |
| count permutations/combinations of multisets | `nP`, `nC`, utilities                                    | handles multiset inputs             |
| enumerate subsets                            | `Subset`, `GrayCode`                                     | binary/lexicographic/minimal-change |
| group action / puzzle state                  | `Permutation`, `PermutationGroup`                        | 0-based index discipline            |
| named abstract examples                      | `SymmetricGroup`, `DihedralGroup`, `CyclicGroup`         | standard generators                 |
| exact integer factorization                  | `factorint`                                              | expensive for hard large inputs     |
| modular algebra                              | `Mod`, `n_order`, `sqrt_mod`, `GF(p)`                    | exact residue arithmetic            |
| integer equation families                    | `diophantine`                                            | supported Diophantine classes only  |
| continued fraction approximants              | `continued_fraction_*`                                   | bound infinite iterators            |
| educational ciphers                          | `sympy.crypto.crypto`                                    | never production security           |
| exact finite-field polynomials               | `Poly(..., modulus=p)`, `GF(p)`                          | prime `p` only for field semantics  |

---

## 13.14 Deployment recipes

## Recipe A — exact combinatorial-count wrapper

```python
def count_multiset_permutations(items, k=None, *, replacement=False):
    from sympy.functions.combinatorial.numbers import nP
    return nP(items, k, replacement=replacement)


def count_multiset_combinations(items, k=None, *, replacement=False):
    from sympy.functions.combinatorial.numbers import nC
    return nC(items, k, replacement=replacement)
```

## Recipe B — factorial-ratio simplification

```python
def simplify_factorial_ratio(expr):
    expr = sp.sympify(expr)
    return sp.combsimp(expr)
```

## Recipe C — safe integer factorization

```python
def factor_integer(n, *, limit=None, multiple=False):
    n = sp.Integer(n)

    if n < 0:
        sign = -1
        n = -n
    else:
        sign = 1

    f = sp.factorint(n, limit=limit, multiple=multiple)
    return (-1, f) if sign < 0 else f
```

## Recipe D — modular polynomial over prime field

```python
def poly_mod_prime(expr, var, p):
    if not sp.isprime(p):
        raise ValueError("p must be prime for GF(p) field semantics")
    return sp.Poly(expr, var, modulus=p)
```

## Recipe E — primitive-root wrapper

```python
def primitive_root_checked(p, *, smallest=True):
    p = int(p)
    root = sp.primitive_root(p, smallest=smallest)
    if root is None:
        raise ValueError(f"no primitive root exists modulo {p}")
    if not sp.is_primitive_root(root, p):
        raise AssertionError("primitive_root returned invalid result")
    return root
```

## Recipe F — bounded continued-fraction prefix

```python
def continued_fraction_prefix(value, length):
    from sympy.ntheory.continued_fraction import continued_fraction_iterator

    it = continued_fraction_iterator(value)
    return [next(it) for _ in range(length)]
```

## Recipe G — Diophantine solve with validation

```python
def solve_diophantine_checked(expr, variables):
    from sympy.solvers.diophantine import diophantine

    expr = sp.sympify(expr)
    sols = diophantine(expr)

    # validation is partial for parametric families; sample only if possible
    return sols
```

## Recipe H — Gray-code incremental subsets

```python
def gray_subsets(objects):
    from sympy.combinatorics import GrayCode

    n = len(objects)
    for bits in GrayCode(n).generate_gray():
        yield [obj for obj, bit in zip(objects, bits) if bit == "1"]
```

## Recipe I — educational crypto guard

```python
def educational_shift_cipher(msg, key):
    from sympy.crypto.crypto import encipher_shift, decipher_shift

    ct = encipher_shift(msg, key)
    pt = decipher_shift(ct, key)

    if pt != msg.upper():
        raise AssertionError("round-trip failed")

    return ct
```

---

## 13.15 Anti-pattern inventory

| Anti-pattern                                                   | Failure mode                        | Correct pattern                                                              |
| -------------------------------------------------------------- | ----------------------------------- | ---------------------------------------------------------------------------- |
| using `sympy.crypto` for real security                         | insecure / educational only         | use production `cryptography` library                                        |
| passing floats to `isprime`                                    | rejected / precision hazard         | exact integers only                                                          |
| using `GF(9)` as a true field                                  | zero divisors, no prime-power field | use `GF(p)` with prime `p` only                                              |
| enumerating huge permutations/subsets eagerly                  | combinatorial explosion             | use generators/iterators and bounds                                          |
| expanding huge factorials/binomials early                      | enormous integers/expressions       | keep symbolic; use `combsimp`                                                |
| treating `Permutation` values as labels                        | wrong mapping                       | map labels to 0-based indices                                                |
| assuming `diophantine` solves all integer equations            | unsupported classes                 | detect/handle unsupported or empty output                                    |
| using factorint on cryptographic-size semiprimes in production | infeasible runtime                  | avoid; factorint is not security tooling                                     |
| consuming infinite continued-fraction iterator unbounded       | infinite loop                       | bounded prefix                                                               |
| using `primitive_root` without checking existence              | `None` result                       | handle `None`                                                                |
| using deprecated `ntheory` aliases blindly                     | deprecation warnings / drift        | import relocated arithmetic functions from `functions.combinatorial.numbers` |

---

## 13.16 Testing matrix

```python
def test_factorial_binomial_exact():
    assert factorial(7) == 5040
    assert binomial(5, 2) == 10
    assert sp.combsimp(factorial(n) / factorial(n - 3)) == n*(n - 2)*(n - 1)

def test_partition_counts():
    assert [partition(i) for i in range(5)] == [1, 1, 2, 3, 5]

def test_permutation_roundtrip():
    p = Permutation([2, 0, 1])
    assert (~p) * p == Permutation(list(range(p.size)))

def test_gray_code_hamming_distance():
    from sympy.combinatorics import GrayCode
    codes = list(GrayCode(4).generate_gray())
    for a, b in zip(codes, codes[1:]):
        assert sum(aa != bb for aa, bb in zip(a, b)) == 1

def test_factorint_rebuild():
    N = 360
    factors = sp.factorint(N)
    rebuilt = sp.prod(p**e for p, e in factors.items())
    assert rebuilt == N

def test_gf_prime_validation():
    assert sp.isprime(5)
    P = sp.Poly(x**2 + 1, x, modulus=5)
    assert P.domain == GF(5)

def test_crypto_shift_roundtrip_educational():
    from sympy.crypto.crypto import encipher_shift, decipher_shift
    msg = "GONAVYBEATARMY"
    ct = encipher_shift(msg, 1)
    assert decipher_shift(ct, 1) == msg
```

Recommended coverage:

```text
Combinatorial functions:
  exact integer input
  symbolic input
  rewrite/gamma/binomial paths
  modular binomial with evaluate=False

Partitions:
  Partition RGS roundtrip
  IntegerPartition rank/order behavior

Permutations/groups:
  array/cycle construction
  inverse/order/signature
  group order/orbit/stabilizer
  named group sanity checks

Subsets/GrayCode:
  binary/lexicographic traversal
  bitlist conversion
  adjacent Hamming distance 1

Number theory:
  isprime exact integer checks
  factorint rebuild
  primitive_root existence/nonexistence
  sqrt_mod roundtrip
  continued fraction bounded consumption

Diophantine:
  linear examples
  Pythagorean examples
  unsupported-path handling

Crypto:
  educational roundtrips only
  explicit production-use rejection guard

Finite fields:
  GF(prime) arithmetic
  GF(composite) rejection by wrapper
  Poly modulus domain
```

---

## 13.17 Minimal discrete-math harness

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Sequence

import sympy as sp

from sympy import (
    factorial, factorial2, subfactorial, binomial,
    bell, catalan, partition, stirling,
    Poly, GF, ZZ, QQ,
)

from sympy.combinatorics import (
    Permutation,
    PermutationGroup,
    Partition,
    Subset,
    GrayCode,
)

from sympy.combinatorics.named_groups import (
    SymmetricGroup,
    AlternatingGroup,
    CyclicGroup,
    DihedralGroup,
)

from sympy.functions.combinatorial.factorials import ff, rf
from sympy.functions.combinatorial.numbers import nC, nP, nT


@dataclass(frozen=True)
class FactorizationAudit:
    n: int
    factor_dict: dict[int, int]
    rebuilt: int
    complete: bool


@dataclass(frozen=True)
class PermutationAudit:
    permutation: Permutation
    size: int
    array_form: list[int]
    cyclic_form: list
    order: int
    signature: int
    rank: int


@dataclass(frozen=True)
class GroupAudit:
    group: PermutationGroup
    degree: int
    order: int
    generator_count: int
    is_abelian: bool | None


def require_integer(n: Any) -> sp.Integer:
    n = sp.sympify(n)
    if not n.is_Integer:
        raise TypeError(f"expected exact integer, got {n!r}")
    return sp.Integer(n)


def exact_factorial_ratio(expr: Any) -> sp.Expr:
    return sp.combsimp(sp.sympify(expr))


def count_combinations(items: Any, k: int | None = None, *, replacement: bool = False) -> sp.Integer:
    return nC(items, k, replacement=replacement)


def count_permutations(items: Any, k: int | None = None, *, replacement: bool = False) -> sp.Integer:
    return nP(items, k, replacement=replacement)


def count_partitions(items: Any, k: int | None = None) -> sp.Integer:
    return nT(items, k)


def set_partition_from_blocks(*blocks) -> Partition:
    return Partition(*blocks)


def set_partition_from_rgs(rgs: Sequence[int], elements: Sequence[Any]) -> Partition:
    return Partition.from_rgs(list(rgs), list(elements))


def integer_partition_count(n: int) -> sp.Integer:
    return partition(require_integer(n))


def permutation_from_array(array: Sequence[int]) -> Permutation:
    return Permutation(list(array))


def permutation_audit(p: Permutation) -> PermutationAudit:
    return PermutationAudit(
        permutation=p,
        size=p.size,
        array_form=list(p.array_form),
        cyclic_form=p.cyclic_form,
        order=p.order(),
        signature=p.signature(),
        rank=p.rank(),
    )


def permutation_group(*generators: Permutation) -> PermutationGroup:
    return PermutationGroup(*generators)


def group_audit(G: PermutationGroup) -> GroupAudit:
    return GroupAudit(
        group=G,
        degree=G.degree,
        order=G.order(),
        generator_count=len(G.generators),
        is_abelian=G.is_abelian,
    )


def named_group(kind: str, n: int) -> PermutationGroup:
    if kind == "symmetric":
        return SymmetricGroup(n)
    if kind == "alternating":
        return AlternatingGroup(n)
    if kind == "cyclic":
        return CyclicGroup(n)
    if kind == "dihedral":
        return DihedralGroup(n)
    raise ValueError(f"unknown named group kind: {kind}")


def subset_binary_walk(subset: Sequence[Any], superset: Sequence[Any], steps: int):
    s = Subset(list(subset), list(superset))
    out = [s.subset]
    for _ in range(steps):
        s = s.next_binary()
        out.append(s.subset)
    return out


def subset_bitlist(subset: Sequence[Any], superset: Sequence[Any]) -> str:
    return Subset.bitlist_from_subset(list(subset), list(superset))


def gray_code_strings(n: int) -> list[str]:
    return list(GrayCode(n).generate_gray())


def gray_code_subsets(objects: Sequence[Any]) -> list[list[Any]]:
    out = []
    for bits in GrayCode(len(objects)).generate_gray():
        out.append([obj for obj, bit in zip(objects, bits) if bit == "1"])
    return out


def factor_integer(n: Any, *, limit: int | None = None, multiple: bool = False):
    n_int = require_integer(n)
    return sp.factorint(n_int, limit=limit, multiple=multiple)


def audit_factorization(n: Any) -> FactorizationAudit:
    n_int = int(require_integer(n))
    factor_dict = {int(p): int(e) for p, e in sp.factorint(n_int).items()}
    rebuilt = 1
    for p, e in factor_dict.items():
        rebuilt *= p**e
    return FactorizationAudit(
        n=n_int,
        factor_dict=factor_dict,
        rebuilt=rebuilt,
        complete=(rebuilt == n_int),
    )


def prime_report(n: Any) -> dict[str, Any]:
    n_int = int(require_integer(n))
    return {
        "n": n_int,
        "isprime": sp.isprime(n_int),
        "nextprime": sp.nextprime(n_int),
        "prevprime": sp.prevprime(n_int) if n_int > 2 else None,
        "primepi": sp.primepi(n_int),
    }


def primitive_root_report(p: Any, *, smallest: bool = True) -> dict[str, Any]:
    p_int = int(require_integer(p))
    root = sp.primitive_root(p_int, smallest=smallest)
    return {
        "p": p_int,
        "primitive_root": root,
        "exists": root is not None,
        "verified": bool(root is not None and sp.is_primitive_root(root, p_int)),
    }


def modular_sqrt_all(a: Any, m: Any) -> list[int]:
    return list(sp.sqrt_mod_iter(int(require_integer(a)), int(require_integer(m))))


def continued_fraction_prefix(value: Any, length: int) -> list[Any]:
    from sympy.ntheory.continued_fraction import continued_fraction_iterator
    it = continued_fraction_iterator(sp.sympify(value))
    return [next(it) for _ in range(length)]


def solve_diophantine(expr: Any):
    from sympy.solvers.diophantine import diophantine
    return diophantine(sp.sympify(expr))


def gf_prime_domain(p: int):
    if not sp.isprime(p):
        raise ValueError("p must be prime for GF(p) field semantics")
    return GF(p)


def poly_over_gf(expr: Any, var: sp.Symbol, p: int) -> Poly:
    return Poly(sp.sympify(expr), var, domain=gf_prime_domain(p))


def educational_shift_roundtrip(message: str, key: int) -> dict[str, str]:
    from sympy.crypto.crypto import encipher_shift, decipher_shift

    ct = encipher_shift(message, key)
    pt = decipher_shift(ct, key)

    return {
        "plaintext": message.upper(),
        "ciphertext": ct,
        "deciphered": pt,
        "educational_only": "do not use sympy.crypto for real cryptography",
    }
```

This harness enforces exact integer inputs, symbolic combinatorial simplification, set/integer partition operations, permutation/group auditing, subset/Gray-code enumeration, safe factorization/primality workflows, primitive-root validation, bounded continued-fraction iteration, Diophantine dispatch, prime-field validation for `GF(p)`, and an explicit educational-only crypto boundary.

[1]: https://docs.sympy.org/latest/modules/combinatorics/index.html?utm_source=chatgpt.com "Combinatorics - SymPy 1.14.0 documentation"
[2]: https://docs.sympy.org/latest/modules/functions/combinatorial.html "Combinatorial - SymPy 1.14.0 documentation"
[3]: https://docs.sympy.org/latest/modules/combinatorics/partitions.html "Partitions - SymPy 1.14.0 documentation"
[4]: https://docs.sympy.org/latest/modules/combinatorics/permutations.html "Permutations - SymPy 1.14.0 documentation"
[5]: https://docs.sympy.org/latest/modules/combinatorics/perm_groups.html "Permutation Groups - SymPy 1.14.0 documentation"
[6]: https://docs.sympy.org/latest/modules/combinatorics/named_groups.html?utm_source=chatgpt.com "Named Groups - SymPy 1.14.0 documentation"
[7]: https://docs.sympy.org/latest/modules/combinatorics/polyhedron.html "Polyhedron - SymPy 1.14.0 documentation"
[8]: https://docs.sympy.org/latest/modules/combinatorics/subsets.html "Subsets - SymPy 1.14.0 documentation"
[9]: https://docs.sympy.org/latest/modules/combinatorics/graycode.html "Gray Code - SymPy 1.14.0 documentation"
[10]: https://docs.sympy.org/latest/modules/ntheory.html "Number Theory - SymPy 1.14.0 documentation"
[11]: https://docs.sympy.org/latest/modules/ntheory.html?utm_source=chatgpt.com "Number Theory - SymPy 1.14.0 documentation"
[12]: https://docs.sympy.org/latest/modules/solvers/diophantine.html "Diophantine - SymPy 1.14.0 documentation"
[13]: https://docs.sympy.org/latest/modules/crypto.html "Cryptography - SymPy 1.14.0 documentation"
[14]: https://docs.sympy.org/latest/modules/polys/domainsref.html "Reference docs for the Poly Domains - SymPy 1.14.0 documentation"

# 14) Geometry, differential geometry, holonomic functions, and specialized topics — agent-ready deep dive

Continuing the same advanced technical-doc pattern as the supplied reference artifact. 

## 14.0 Scope map

This section covers five distinct SymPy layers:

```text id="30ctys"
sympy.geometry:
  exact 2D/3D Euclidean entities: Point, Line, Segment, Ray, Circle, Ellipse,
  Polygon, RegularPolygon, Triangle, Plane; intersections, distances, tangents,
  areas, projections.

sympy.diffgeom:
  manifolds, patches, coordinate systems, scalar/vector fields,
  differential forms, tensor/wedge products, Lie/covariant derivatives,
  Christoffel/Riemann/Ricci helpers, integral-curve series.

sympy.holonomic:
  holonomic functions as annihilator + initial conditions;
  closure operations: addition, multiplication, differentiation, integration,
  composition; conversions from expressions/hyper/meijerg.

sympy.liealgebras:
  Cartan types, root systems, Cartan matrices, simple/positive roots,
  Weyl-group style root-system data.

sympy.categories:
  abstract objects, morphisms, categories, diagrams; structural/category-theory IR,
  not a full theorem prover.
```

SymPy’s geometry module is explicitly centered on two-dimensional geometry entities but includes 3D entities such as `Point3D`, `Line3D`, and `Plane`; its main use case is numerical-valued geometric entities, although symbolic representations are possible. The module lists `Point`, `Line`/`Segment`/`Ray`, `Ellipse`/`Circle`, `Polygon`/`RegularPolygon`/`Triangle`, and global utilities such as `intersection`, `are_similar`, and `convex_hull`. ([SymPy Documentation][1])

---

## 14.1 Geometry: entities and construction

## 14.1.1 Imports

```python id="xeh5or"
import sympy as sp

from sympy import (
    Point, Point2D, Point3D,
    Line, Line2D, Line3D,
    Segment, Segment2D, Segment3D,
    Ray, Ray2D, Ray3D,
    Circle, Ellipse,
    Polygon, RegularPolygon, Triangle,
    Plane,
    intersection, are_similar, convex_hull,
)

x, y, z, t, u, v = sp.symbols("x y z t u v")
```

## 14.1.2 Points

```python id="rycc6v"
p0 = Point(0, 0)
p1 = Point(1, 2)
p2 = Point2D(3, 4)
p3 = Point3D(1, 2, 3)

p0.distance(p1)
p0.midpoint(p1)
p0.ambient_dimension
Point3D.are_coplanar(Point3D(1, 2, 2), Point3D(2, 7, 2), Point3D(0, 0, 2))
```

`Point.affine_rank(*points)` gives the dimension of the smallest affine space containing a point set; `Point3D.are_coplanar(*points)` checks whether points lie in a common plane, returning trivially `True` for fewer than three points or all 2D points, and raising on fewer than three unique points in the relevant nontrivial case. ([SymPy Documentation][2])

## 14.1.3 Lines, rays, and segments

```python id="vjch77"
L = Line(Point(0, 0), Point(1, 1))
S = Segment(Point(4, 3), Point(1, 1))
R = Ray(Point(0, 0), Point(1, 0))

L.slope
L.direction
L.angle_between(Line((0, 0), (1, 0)))
L.smallest_angle_between(Line((0, 0), (1, 0)))
S.length
S.midpoint
```

`LinearEntity` is the abstract base for `Line`, `Ray`, and `Segment`; it supports `ambient_dimension`, `direction`, `length`, endpoint/point access, and angle computations. `Segment` exposes `length` and `midpoint`; `Line3D` can be constructed from two points or a point plus a `direction_ratio`, and has direction ratio/cosine properties. ([SymPy Documentation][3])

## 14.1.4 Circles and ellipses

```python id="4qlsps"
c = Circle(Point(0, 0), 5)
e = Ellipse(Point(0, 0), 5, 7)

c.center
c.radius
c.area
c.circumference

e.center
e.hradius
e.vradius
e.foci
e.focus_distance
e.eccentricity
```

`Ellipse.intersection(o)` returns a list of geometry entities and supports intersections with `Point`, `Line`, `Segment`, `Ray`, `Circle`, and `Ellipse`. `Ellipse.tangent_lines(p)` returns tangent lines from/on a point where possible and may return one or two lines; if the point is inside the ellipse, no tangent line is possible. ([SymPy Documentation][4])

```python id="j5ycr5"
e = Ellipse(Point(0, 0), 5, 7)

e.intersection(Line(Point(0, 0), Point(0, 1)))
e.tangent_lines(Point(5, 0))
e.is_tangent(Line(Point(5, 0), Point(5, 1)))
```

## 14.1.5 Polygons, regular polygons, triangles

```python id="6sokmp"
poly = Polygon((0, 0), (1, 0), (5, 1), (0, 1))
tri = Triangle(Point(0, 0), Point(1, 0), Point(0, 1))
reg = RegularPolygon(Point(0, 0), 5, 6)

poly.area
poly.perimeter
poly.centroid
poly.sides
poly.angles
reg.vertices
reg.circumcircle
reg.incircle
```

`Polygon(*args, n=0)` constructs a 2D polygon from vertices, or constructs a `RegularPolygon` when `n > 0`; polygons are treated as closed paths, so signed area can depend on point orientation and self-crossing behavior. Consecutive identical points can be reduced, collinear intermediate points can be removed, and with three or fewer points the constructor may return a `Triangle`, `Segment`, or `Point`. ([SymPy Documentation][5])

## 14.1.6 Planes

```python id="6o8z6t"
P = Plane(Point3D(1, 1, 1), Point3D(2, 3, 4), Point3D(2, 2, 2))
Q = Plane(Point3D(1, 1, 1), normal_vector=(1, 4, 7))

P.p1
P.normal_vector
P.equation()
P.arbitrary_point(u, v)
P.distance(Point3D(1, 2, 3))
P.intersection(Q)
P.projection(Point3D(1, 1, 2))
```

A `Plane` can be constructed from three non-collinear points or from a point plus a normal vector. It supports distance to 3D points/lines/planes, equation extraction, plane/point/line intersections, coplanarity/parallel/perpendicular checks, arbitrary points, and projection of points/lines onto a plane. ([SymPy Documentation][6])

---

## 14.2 Geometry operations and robustness rules

## 14.2.1 Intersections

```python id="0ao3tl"
L1 = Line((0, 0), (1, 1))
L2 = Line((0, 1), (1, 0))

L1.intersection(L2)
intersection(L1, L2)

c = Circle(Point(0, 0), 5)
L = Line(Point(0, 0), Point(1, 0))
c.intersection(L)
```

Return contract:

```text id="fmwep9"
intersection output:
  list[GeometryEntity]
  []                 no intersection / unsupported detected no-hit
  [Point(...)]       point intersection
  [Line(...)]        coincident/self intersection
  [Segment(...)]     overlapping segment
  multiple points    algebraic intersections
```

The global `intersection()` utility requires at least two entities; an entity intersected with itself should return a list containing that entity. The docs warn that intersections can be missed if required quantities are not fully simplified internally and specifically recommend converting reals to rationals in such cases. ([SymPy Documentation][7])

```python id="ol0m28"
def exact_point(*coords):
    return Point(*[sp.Rational(c) if isinstance(c, int) else sp.sympify(c) for c in coords])
```

## 14.2.2 Distances, projections, tangents, areas

```python id="tr5cnx"
p = Point(0, 0)
q = Point(3, 4)

p.distance(q)
Line((0, 0), (1, 0)).distance(Point(0, 2))
Circle(Point(0, 0), 5).area
Polygon((0, 0), (1, 0), (1, 1), (0, 1)).area

plane = Plane((0, 0, 0), normal_vector=(0, 0, 1))
plane.projection(Point3D(1, 1, 2))
```

Deployment rules:

```text id="0iqjzd"
Use exact integer/Rational coordinates:
  stable equality/intersection.

Use .equals() / geometry predicates:
  mathematical equality rather than Python structural equality.

Normalize expressions:
  simplify/factor rational outputs before comparing.

Avoid floats:
  intersection/tangency/collinearity can fail due to exact-symbolic checks.

Always inspect list outputs:
  geometry intersections are lists, not nullable scalars.
```

---

## 14.3 Geometry maturity and production posture

```text id="tqv0ij"
Mature/useful:
  exact Euclidean geometry with Points, Lines, Segments, Rays, Circles,
  Ellipses, Polygons, Planes;
  distances, intersections, area/perimeter, tangent-line construction,
  projection, symbolic equations.

Best fit:
  educational geometry tooling,
  exact CAD-like small computations,
  symbolic problem generation,
  algebraic geometry preprocessing,
  exact analytic-geometry examples.

Caution:
  not a numeric computational-geometry engine;
  not optimized for large mesh/solid geometry;
  exact arithmetic preferred;
  intersections may depend on simplification;
  2D/3D entity compatibility must be handled explicitly.
```

SymPy’s geometry docs themselves describe the module as primarily intended for numerical-valued entities while allowing symbolic representations, and note exact/simplification issues in global intersection detection. ([SymPy Documentation][1])

---

## 14.4 Differential geometry module

## 14.4.1 Core imports and built-in coordinate systems

```python id="qguuhm"
from sympy.diffgeom import (
    Manifold, Patch, CoordSystem,
    BaseScalarField, BaseVectorField,
    Differential, TensorProduct, WedgeProduct,
    Commutator, LieDerivative,
    BaseCovarDerivativeOp, CovarDerivativeOp,
    metric_to_Christoffel_1st, metric_to_Christoffel_2nd,
    metric_to_Riemann_components, metric_to_Ricci_components,
    twoform_to_matrix,
    intcurve_diffequ, intcurve_series,
)

from sympy.diffgeom.rn import R2_r, R2_p
```

The diffgeom docs define a coordinate patch as a simply connected open set around a point in a manifold and explicitly state that `Patch` does not provide tools to study topological characteristics of the patch. The module includes base vector fields, commutators, differentials, tensor products, wedge products, Lie derivatives, and covariant derivative operators. ([SymPy Documentation][8])

## 14.4.2 Manifold/patch/coordinate-system skeleton

```python id="2k0lo0"
M = Manifold("M", 2)
P = Patch("P", M)
C = CoordSystem("C", P, [x, y])
```

Common built-in coordinate-system workflow:

```python id="z1pc28"
fx, fy = R2_r.base_scalars()
ex, ey = R2_r.base_vectors()
dx, dy = R2_r.base_oneforms()

rho, theta = R2_p.base_scalars()
erho, etheta = R2_p.base_vectors()
```

## 14.4.3 Scalar/vector fields and operators

```python id="jdmqtm"
s = fx**2 + fy**2
v = fx*ex + fy*ey

ex(s)                  # directional derivative in x direction
ey(s)                  # directional derivative in y direction
Commutator(ex, ey)
Differential(s)(ex)
```

A base vector field is an operator that takes a scalar field and returns a directional derivative; `Commutator(v1, v2)` represents `[v1, v2] = v1(v2(f)) - v2(v1(f))`. The docs also explicitly note that the current code cannot compute everything, showing a commutator that remains unevaluated even though applying it to a scalar and simplifying can produce a result. ([SymPy Documentation][8])

## 14.4.4 Forms, tensor products, wedge products

```python id="jg5k35"
TP = TensorProduct
WP = WedgeProduct

TP(dx, dy)(ex, ey)     # 1
TP(dx, dy)(ey, ex)     # 0

WP(dx, dy)(ex, ey)     # 1
WP(dx, dy)(ey, ex)     # -1
```

`TensorProduct` creates multilinear functionals from forms/vector fields but does not impose antisymmetry; `WedgeProduct` creates antisymmetric form products, which are the relevant objects in integration contexts. ([SymPy Documentation][8])

## 14.4.5 Metrics, Christoffel symbols, curvature

```python id="1nsloj"
metric = TP(dx, dx) + TP(dy, dy)

ch1 = metric_to_Christoffel_1st(metric)
ch2 = metric_to_Christoffel_2nd(metric)
riemann = metric_to_Riemann_components(metric)
ricci = metric_to_Ricci_components(metric)

cov_x = BaseCovarDerivativeOp(R2_r, 0, ch2)
cov = CovarDerivativeOp(ex + ey, ch2)
```

The diffgeom docs show `metric_to_Christoffel_2nd(TensorProduct(dx, dx) + TensorProduct(dy, dy))` returning zero Christoffel components for the Euclidean metric and using the result with `BaseCovarDerivativeOp`. ([SymPy Documentation][8])

## 14.4.6 Integral curves

```python id="5r4d8i"
start_point = R2_r.point([x, y])
vector_field = R2_r.e_x

series = intcurve_series(vector_field, t, start_point, n=3)
series_coeffs = intcurve_series(vector_field, t, start_point, n=3, coeffs=True)

equations, init_cond = intcurve_diffequ(vector_field, t, start_point)
```

`intcurve_series(vector_field, param, start_point, n=..., coord_sys=..., coeffs=...)` computes coordinate series for integral curves; with `coeffs=True`, it returns the expansion as a list of matrix coefficients. ([SymPy Documentation][8])

## 14.4.7 Diffgeom deployment posture

```text id="x5h85m"
Use diffgeom for:
  symbolic differential geometry experiments,
  educational manifold/coordinate-system examples,
  coordinate transformations,
  tensor-product/wedge-product calculations,
  Christoffel/Riemann/Ricci derivations for small symbolic metrics,
  integral-curve local series.

Caution:
  not a full differential-geometry theorem prover;
  not all commutators/objects simplify automatically;
  coordinate-system support is symbolic and exact;
  topology of patches is not studied by Patch;
  large metrics/curvature tensors can explode expression size.
```

---

## 14.5 Holonomic functions

## 14.5.1 Mental model

A holonomic function is represented by a linear homogeneous ordinary differential equation with polynomial coefficients, encoded as an **annihilator** `L` such that `L.f = 0`, plus optional initial conditions. SymPy’s holonomic docs state that holonomic functions are closed under addition, multiplication, integration, and differentiation, forming a ring. ([SymPy Documentation][9])

```python id="otq8wp"
from sympy.holonomic import DifferentialOperators, HolonomicFunction
from sympy.holonomic.holonomic import (
    expr_to_holonomic,
    from_hyper,
    from_meijerg,
)
```

## 14.5.2 Differential-operator construction

```python id="f7bdfq"
R, Dx = DifferentialOperators(sp.ZZ.old_poly_ring(x), "Dx")

# Example annihilator for sin(x): (D^2 + 1).f = 0
H_sin = HolonomicFunction(Dx**2 + 1, x, 0, [0, 1])
```

The representation docs show `DifferentialOperators(ZZ.old_poly_ring(x), 'D')` producing a differential-operator ring and `D` operator, with polynomial coefficients in `ZZ[x]`, and mention that the implementation currently uses older ring implementations for priority mechanics. ([SymPy Documentation][9])

## 14.5.3 Closure operations

```python id="4qscc2"
H1 = expr_to_holonomic(sp.sin(x), x)
H2 = expr_to_holonomic(sp.exp(x), x)

H_sum = H1 + H2
H_prod = H1 * H2
H_diff = H1.diff()
H_int = H1.integrate((x, 0, x))
```

The holonomic module is intended for operations such as addition, multiplication, composition, integration, and differentiation, plus conversion to/from other representations. ([SymPy Documentation][10])

## 14.5.4 Composition and initial conditions

```python id="79qnr9"
H = expr_to_holonomic(sp.sin(x), x)
H_comp = H.composition(x**2)
```

`HolonomicFunction.composition(expr, *args, **kwargs)` returns the composition with an algebraic function, but the docs state that it cannot compute initial conditions for the result by itself, so initial conditions can also be provided. ([SymPy Documentation][11])

## 14.5.5 Conversions

```python id="5m7xjw"
H_expr = expr_to_holonomic(sp.sin(x) + sp.exp(x), x)

H_hyper = from_hyper(sp.hyper([], [sp.S(3)/2], x**2/4))
H_meijer = from_meijerg(sp.meijerg(([], []), ([sp.S(1)/2], [0]), x**2/4))

expr_back = H_expr.to_expr()
seq = H_expr.to_sequence()
```

`from_hyper(func, x0=0, evalf=False)` converts a hypergeometric function to a holonomic function, `from_meijerg(func, x0=0, evalf=False, initcond=True, domain=QQ)` converts a Meijer G-function, and `expr_to_holonomic(func, x=None, x0=0, y0=None, lenics=None, domain=None, initcond=True)` converts expressions/functions with optional initial-condition controls. ([SymPy Documentation][12])

## 14.5.6 Integration workflow

```python id="7uoist"
integrand = expr_to_holonomic(sp.exp(-x**2), x)
integral_holo = integrand.integrate((x, 0, x))
candidate_expr = integral_holo.to_expr()
```

The holonomic “uses and limitations” docs describe integration as a three-step process: convert the integrand to a holonomic function, integrate the holonomic representation, and convert the integral back to expressions. ([SymPy Documentation][13])

## 14.5.7 Holonomic deployment posture

```text id="mmwzxu"
Use holonomic module for:
  special-function closure algebra,
  exact annihilator-based representation,
  algorithmic integration/recurrences,
  conversions between hyper/meijerg/expression/holonomic forms,
  advanced symbolic algorithms over D-finite functions.

Caution:
  specialized API;
  not all expressions are holonomic;
  initial conditions can be required or fail to compute automatically;
  composition/integration conversions may need manual domain/IC control;
  expect expression swell and unimplemented cases.
```

---

## 14.6 Lie algebra module

```python id="5vrxcc"
from sympy.liealgebras.cartan_type import CartanType

A3 = CartanType("A3")
B4 = CartanType("B4")
G2 = CartanType("G2")

A3.cartan_matrix()
A3.dimension()
A3.simple_root(1)
A3.positive_roots()
A3.roots()
A3.lie_algebra()
```

The Lie algebra docs expose Cartan-type classes for series such as `A`, `B`, `C`, `D`, exceptional types, and `G2`; methods include `cartan_matrix`, `dimension`, `lie_algebra`, `positive_roots`, `roots`, and `simple_root`. The docs define simple roots as roots that cannot be expressed as sums of other roots and note that every root can be expressed as a nonnegative linear combination of simple roots. ([SymPy Documentation][14])

Deployment posture:

```text id="y10zdr"
Use liealgebras for:
  root-system data,
  Cartan matrices,
  educational Lie algebra examples,
  symbolic root enumeration,
  classification/table workflows.

Caution:
  scope is root-system/Cartan-type data, not a full Lie algebra CAS;
  validate expected type/rank support;
  inspect returned lists/dicts/matrices directly;
  use Sage/GAP/LiE-style systems for heavy representation theory.
```

---

## 14.7 Category theory module

```python id="ox4k9j"
from sympy.categories import (
    Object, Morphism, NamedMorphism,
    IdentityMorphism, CompositeMorphism,
    Category, Diagram,
)

A = Object("A")
B = Object("B")
f = NamedMorphism(A, B, "f")
idA = IdentityMorphism(A)

C = Category("C")
```

The category-theory module implements basic notions: abstract objects, morphisms, categories, and diagrams. `Object(name, **assumptions)` is the recommended way to create abstract category objects, while `Morphism(domain, codomain)` represents arrows from a domain object to a codomain object. ([SymPy Documentation][15])

Deployment posture:

```text id="c71i6p"
Use categories module for:
  symbolic category-theory notation,
  diagrams,
  abstract-object/morphism IR,
  educational examples.

Caution:
  basic structural module;
  not a full categorical proof assistant;
  do not expect automated theorem proving, limits/colimits at production depth,
  or universal-property verification unless explicitly implemented/test-covered.
```

---

## 14.8 Production maturity matrix

| Module              | Best fit                                                                 | Production posture                                                               |
| ------------------- | ------------------------------------------------------------------------ | -------------------------------------------------------------------------------- |
| `sympy.geometry`    | exact 2D/3D analytic geometry, small symbolic/numeric tasks              | useful/mature for exact small problems; avoid float-heavy computational geometry |
| `sympy.diffgeom`    | symbolic differential-geometry experiments, forms, metrics, local curves | specialized; not exhaustive; expression swell likely                             |
| `sympy.holonomic`   | D-finite / special-function algorithms, annihilators, closure operations | advanced/specialized; requires domain/IC awareness                               |
| `sympy.liealgebras` | Cartan types, roots, Cartan matrices                                     | specialized classification/data module                                           |
| `sympy.categories`  | symbolic objects/morphisms/diagrams                                      | basic educational/IR layer                                                       |

---

## 14.9 Deployment recipes

## Recipe A — exact geometry wrapper

```python id="vwtsfo"
def exact_point(*coords):
    return Point(*[sp.Rational(c) if isinstance(c, int) else sp.sympify(c) for c in coords])


def safe_intersections(*entities):
    if len(entities) < 2:
        return []
    hits = intersection(*entities)
    return [sp.simplify(h) if isinstance(h, sp.Expr) else h for h in hits]


def distance_exact(a, b):
    return sp.simplify(a.distance(b))
```

## Recipe B — geometry intersection audit

```python id="x0stya"
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class GeometryIntersectionAudit:
    entities: tuple[Any, ...]
    hits: tuple[Any, ...]
    hit_count: int
    types: tuple[str, ...]


def audit_intersection(*entities) -> GeometryIntersectionAudit:
    hits = tuple(intersection(*entities)) if len(entities) >= 2 else ()
    return GeometryIntersectionAudit(
        entities=tuple(entities),
        hits=hits,
        hit_count=len(hits),
        types=tuple(type(h).__name__ for h in hits),
    )
```

## Recipe C — 3D plane projection pipeline

```python id="wemxim"
def project_point_to_plane(point, plane):
    point = Point3D(point)
    if not isinstance(plane, Plane):
        raise TypeError("expected Plane")
    projected = plane.projection(point)
    if projected not in plane:
        raise AssertionError("projection not on plane")
    return projected
```

## Recipe D — Christoffel/Ricci helper

```python id="67n2qr"
def diffgeom_metric_summary(metric):
    ch2 = metric_to_Christoffel_2nd(metric)
    riemann = metric_to_Riemann_components(metric)
    ricci = metric_to_Ricci_components(metric)
    return {
        "christoffel_2nd": ch2,
        "riemann": riemann,
        "ricci": ricci,
    }
```

## Recipe E — holonomic conversion with fallback

```python id="w5mw4e"
def try_holonomic(expr, var, *, x0=0, domain=None, initcond=True):
    try:
        return expr_to_holonomic(expr, var, x0=x0, domain=domain, initcond=initcond)
    except Exception as exc:
        return {"failed": True, "error": type(exc).__name__, "message": str(exc), "expr": expr}
```

## Recipe F — Cartan-type audit

```python id="9wz0xm"
@dataclass(frozen=True)
class CartanAudit:
    label: str
    cartan_matrix: sp.Matrix
    dimension: int
    roots: int
    simple_root_1: list
    positive_roots_count: int


def cartan_audit(label: str) -> CartanAudit:
    c = CartanType(label)
    pos = c.positive_roots()
    return CartanAudit(
        label=label,
        cartan_matrix=c.cartan_matrix(),
        dimension=c.dimension(),
        roots=c.roots(),
        simple_root_1=c.simple_root(1),
        positive_roots_count=len(pos),
    )
```

---

## 14.10 Anti-pattern inventory

| Anti-pattern                                               | Failure mode                          | Correct pattern                                   |
| ---------------------------------------------------------- | ------------------------------------- | ------------------------------------------------- |
| float coordinates in exact geometry                        | missed intersections / equality drift | use `Rational`/exact coordinates                  |
| assuming `intersection()` returns scalar                   | list handling bug                     | always handle `list[GeometryEntity]`              |
| comparing geometry with `==` only                          | structural mismatch                   | use `.equals()` / geometry predicates             |
| treating `Polygon` as always area object                   | signed/path behavior surprises        | account for orientation and self-crossing         |
| mixing 2D and 3D geometry without projection               | unsupported/incorrect operations      | convert/project explicitly                        |
| expecting `diffgeom` to simplify all commutators           | unevaluated objects                   | apply to scalars, simplify, or handle unevaluated |
| large symbolic curvature tensors                           | expression explosion                  | simplify componentwise, cache, restrict metrics   |
| holonomic composition without ICs                          | missing/incorrect initial data        | provide/validate initial conditions               |
| assuming every expression is holonomic                     | conversion failure                    | fallback to ordinary calculus/special functions   |
| using Lie algebra module as full representation-theory CAS | missing features                      | restrict to Cartan/root-system data               |
| using categories module as proof assistant                 | missing theorem automation            | use as symbolic IR/notation only                  |

---

## 14.11 Testing matrix

```python id="r9mov1"
def test_line_intersection():
    L1 = Line((0, 0), (1, 1))
    L2 = Line((0, 1), (1, 0))
    assert L1.intersection(L2) == [Point(sp.Rational(1, 2), sp.Rational(1, 2))]

def test_plane_projection():
    P = Plane((0, 0, 0), normal_vector=(0, 0, 1))
    q = P.projection(Point3D(1, 1, 2))
    assert q == Point3D(1, 1, 0)
    assert q in P

def test_polygon_area_orientation():
    sq = Polygon((0, 0), (1, 0), (1, 1), (0, 1))
    assert sq.area == 1

def test_diffgeom_flat_metric_christoffel():
    fx, fy = R2_r.base_scalars()
    dx, dy = R2_r.base_oneforms()
    metric = TensorProduct(dx, dx) + TensorProduct(dy, dy)
    assert metric_to_Christoffel_2nd(metric) == [[[0, 0], [0, 0]], [[0, 0], [0, 0]]]

def test_holonomic_sin_annihilator():
    R, Dx = DifferentialOperators(sp.ZZ.old_poly_ring(x), "Dx")
    H = HolonomicFunction(Dx**2 + 1, x, 0, [0, 1])
    assert H.x == x

def test_cartan_A3():
    c = CartanType("A3")
    assert c.dimension() == 4
    assert c.roots() == 12
```

Coverage categories:

```text id="ltwyhp"
Geometry:
  point distance, line intersection, circle-line intersection,
  ellipse tangent lines, polygon signed area, plane projection/intersection.

Diffgeom:
  base scalars/vectors, Differential, TensorProduct/WedgeProduct,
  commutator computed/unevaluated cases, Christoffel/Riemann/Ricci,
  intcurve_series.

Holonomic:
  manual annihilator construction, expr_to_holonomic,
  from_hyper/from_meijerg, add/product/diff/integrate,
  conversion failure fallback.

Lie algebra:
  Cartan matrix, dimension, simple roots, positive roots, total roots.

Categories:
  object/morphism construction, identity/composition/domain/codomain invariants.
```

---

## 14.12 Minimal specialized-topics harness

```python id="9ftl8e"
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import sympy as sp
from sympy import (
    Point, Point2D, Point3D,
    Line, Line2D, Line3D,
    Segment, Ray,
    Circle, Ellipse, Polygon, RegularPolygon, Triangle, Plane,
    intersection,
)
from sympy.diffgeom import (
    TensorProduct, WedgeProduct, Differential, Commutator,
    metric_to_Christoffel_2nd, metric_to_Riemann_components, metric_to_Ricci_components,
    intcurve_series,
)
from sympy.diffgeom.rn import R2_r, R2_p
from sympy.holonomic import DifferentialOperators, HolonomicFunction
from sympy.holonomic.holonomic import expr_to_holonomic, from_hyper, from_meijerg
from sympy.liealgebras.cartan_type import CartanType


@dataclass(frozen=True)
class GeometryAudit:
    entity: Any
    type_name: str
    ambient_dimension: int | None
    bounds: Any | None
    free_symbols: set[sp.Symbol]


def geometry_audit(entity: Any) -> GeometryAudit:
    return GeometryAudit(
        entity=entity,
        type_name=type(entity).__name__,
        ambient_dimension=getattr(entity, "ambient_dimension", None),
        bounds=getattr(entity, "bounds", None),
        free_symbols=getattr(entity, "free_symbols", set()),
    )


def exact_geometry_point(*coords) -> Point:
    return Point(*[sp.sympify(c) for c in coords])


def geometry_intersections(*entities) -> tuple[Any, ...]:
    if len(entities) < 2:
        return ()
    return tuple(intersection(*entities))


def geometry_distance(a: Any, b: Any) -> sp.Expr:
    return sp.simplify(a.distance(b))


def tangent_lines_to_ellipse(e: Ellipse, p: Point) -> tuple[Any, ...]:
    lines = e.tangent_lines(p)
    if lines is None:
        return ()
    return tuple(lines)


def plane_from_point_normal(point, normal_vector) -> Plane:
    return Plane(Point3D(point), normal_vector=tuple(map(sp.sympify, normal_vector)))


def project_to_plane(plane: Plane, point) -> Point3D:
    q = plane.projection(Point3D(point))
    if q not in plane:
        raise AssertionError("projection result is not contained in plane")
    return q


@dataclass(frozen=True)
class DiffGeomMetricAudit:
    metric: Any
    christoffel_2nd: Any
    riemann: Any
    ricci: Any


def diffgeom_flat_R2_metric():
    dx, dy = R2_r.base_oneforms()
    return TensorProduct(dx, dx) + TensorProduct(dy, dy)


def diffgeom_metric_audit(metric: Any) -> DiffGeomMetricAudit:
    return DiffGeomMetricAudit(
        metric=metric,
        christoffel_2nd=metric_to_Christoffel_2nd(metric),
        riemann=metric_to_Riemann_components(metric),
        ricci=metric_to_Ricci_components(metric),
    )


def integral_curve_series(vector_field: Any, parameter: sp.Symbol, start_point: Any, *, n: int = 3, coord_sys=None):
    kwargs = {"n": n}
    if coord_sys is not None:
        kwargs["coord_sys"] = coord_sys
    return intcurve_series(vector_field, parameter, start_point, **kwargs)


@dataclass(frozen=True)
class HolonomicAudit:
    holonomic: Any
    variable: sp.Symbol
    annihilator: Any
    x0: Any
    initial_conditions: Any


def holonomic_from_expr(expr: Any, var: sp.Symbol, *, x0=0, domain=None, initcond=True):
    return expr_to_holonomic(sp.sympify(expr), var, x0=x0, domain=domain, initcond=initcond)


def holonomic_audit(H: HolonomicFunction) -> HolonomicAudit:
    return HolonomicAudit(
        holonomic=H,
        variable=H.x,
        annihilator=H.annihilator,
        x0=H.x0,
        initial_conditions=H.y0,
    )


def holonomic_sin(var: sp.Symbol = x) -> HolonomicFunction:
    R, D = DifferentialOperators(sp.ZZ.old_poly_ring(var), "D")
    return HolonomicFunction(D**2 + 1, var, 0, [0, 1])


def try_expr_to_holonomic(expr: Any, var: sp.Symbol):
    try:
        return {"ok": True, "value": holonomic_from_expr(expr, var)}
    except Exception as exc:
        return {"ok": False, "error": type(exc).__name__, "message": str(exc)}


@dataclass(frozen=True)
class CartanData:
    label: str
    cartan_matrix: sp.Matrix
    dimension: int
    total_roots: int
    simple_roots: dict[int, list]
    positive_roots: dict[int, list]


def cartan_data(label: str) -> CartanData:
    c = CartanType(label)
    rank = len(c.cartan_matrix())
    simple = {}
    for i in range(1, rank + 1):
        try:
            simple[i] = c.simple_root(i)
        except Exception:
            pass

    return CartanData(
        label=label,
        cartan_matrix=c.cartan_matrix(),
        dimension=c.dimension(),
        total_roots=c.roots(),
        simple_roots=simple,
        positive_roots=c.positive_roots(),
    )


def category_objects_example():
    from sympy.categories import Object, NamedMorphism, IdentityMorphism, Category

    A = Object("A")
    B = Object("B")
    f = NamedMorphism(A, B, "f")
    idA = IdentityMorphism(A)
    C = Category("C")

    return {
        "A": A,
        "B": B,
        "f": f,
        "idA": idA,
        "category": C,
        "domain": f.domain,
        "codomain": f.codomain,
    }
```

This harness encodes robust geometry operations, exact point construction, intersection list handling, plane projection validation, differential-geometry metric/curvature summaries, integral-curve series, holonomic conversion and annihilator inspection, Cartan root-system auditing, and basic category-theory object/morphism construction.

[1]: https://docs.sympy.org/latest/modules/geometry/index.html "Geometry - SymPy 1.14.0 documentation"
[2]: https://docs.sympy.org/latest/modules/geometry/points.html "Points - SymPy 1.14.0 documentation"
[3]: https://docs.sympy.org/latest/modules/geometry/lines.html "Lines - SymPy 1.14.0 documentation"
[4]: https://docs.sympy.org/latest/modules/geometry/ellipses.html "Ellipses - SymPy 1.14.0 documentation"
[5]: https://docs.sympy.org/latest/modules/geometry/polygons.html "Polygons - SymPy 1.14.0 documentation"
[6]: https://docs.sympy.org/latest/modules/geometry/plane.html "Plane - SymPy 1.14.0 documentation"
[7]: https://docs.sympy.org/latest/modules/geometry/utils.html "Utils - SymPy 1.14.0 documentation"
[8]: https://docs.sympy.org/latest/modules/diffgeom.html "Differential Geometry - SymPy 1.14.0 documentation"
[9]: https://docs.sympy.org/latest/modules/holonomic/represent.html "Representation of holonomic functions in SymPy - SymPy 1.14.0 documentation"
[10]: https://docs.sympy.org/latest/modules/holonomic/index.html "Holonomic - SymPy 1.14.0 documentation"
[11]: https://docs.sympy.org/latest/modules/holonomic/operations.html "Operations on holonomic functions - SymPy 1.14.0 documentation"
[12]: https://docs.sympy.org/latest/modules/holonomic/convert.html "Converting other representations to holonomic - SymPy 1.14.0 documentation"
[13]: https://docs.sympy.org/latest/modules/holonomic/uses.html "Uses and Current limitations - SymPy 1.14.0 documentation"
[14]: https://docs.sympy.org/latest/modules/liealgebras/index.html "Lie Algebra - SymPy 1.14.0 documentation"
[15]: https://docs.sympy.org/latest/modules/categories.html "Category Theory - SymPy 1.14.0 documentation"

# 15) Physics modules — agent-ready deep dive

Continuing the same advanced technical-doc pattern as the supplied reference artifact. 

## 15.0 Physics-module boundary map

SymPy physics is not one uniform API. It is a collection of specialized symbolic physics subpackages:

```text
sympy.physics.vector
  reference frames, vectors, dyadics, kinematics, time derivatives

sympy.physics.mechanics
  multibody dynamics; particles, rigid bodies, loads, Kane/Lagrange methods,
  joints, System, actuators, linearization

sympy.physics.control
  transfer functions, state-space models, feedback/series/parallel interconnections,
  symbolic control analysis and plotting helpers

sympy.physics.units
  quantities, units, dimensions, prefixes, unit systems, conversion

sympy.physics.optics
  Gaussian optics, media, lenses/mirrors, Fresnel/refraction utilities,
  polarization/waves/ray transfer

sympy.physics.continuum_mechanics
  beams, trusses, cables, arches

sympy.physics.quantum
  operators, states, Hilbert spaces, commutators, tensor products,
  spin, qubits, gates, QFT, Grover, Shor, particle-in-box

sympy.physics.biomechanics
  musculotendon and activation dynamics, designed as an extension of mechanics

sympy.physics.hep
  high-energy physics helpers, primarily gamma-matrix tensor objects

specialized physics utilities
  hydrogen, harmonic oscillator, Wigner symbols, Pauli algebra, matrices
```

SymPy mechanics is scoped to multibody dynamics: formulating equations of motion for systems of particles and/or rigid bodies, such as pendulums, robots, bicycles, planets, and other rigid-body systems. Control, units, quantum, continuum mechanics, biomechanics, and HEP are separate physics submodules with their own object models and constraints. ([SymPy Documentation][1])

---

## 15.1 Vector physics: frames, vectors, dyadics, kinematics

## 15.1.1 Core imports

```python
import sympy as sp

from sympy.physics.vector import (
    ReferenceFrame,
    Point,
    Vector,
    Dyadic,
    dynamicsymbols,
    dot,
    cross,
    outer,
    express,
    time_derivative,
    init_vprinting,
)

t = dynamicsymbols._t
q1, q2 = dynamicsymbols("q1 q2")
u1, u2 = dynamicsymbols("u1 u2")
```

`ReferenceFrame` represents a classical-mechanics reference frame with basis unit vectors in the frame’s `x`, `y`, and `z` directions; vector functions include dot, cross, outer/dyadic products, expression in other frames, and time derivatives. ([SymPy Documentation][2])

## 15.1.2 Reference frames

```python
N = ReferenceFrame("N")
A = N.orientnew("A", "Axis", [q1, N.z])
B = A.orientnew("B", "Axis", [q2, A.x])

N.x, N.y, N.z
A.x, A.y, A.z
```

Frame orientation patterns:

```python
A = N.orientnew("A", "Axis", [q1, N.z])
B = N.orientnew("B", "Body", [q1, q2, q3], "XYZ")
C = N.orientnew("C", "Space", [q1, q2, q3], "XYZ")
```

## 15.1.3 Vectors, dyadics, dot/cross/outer

```python
v = u1*N.x + u2*A.y
w = q1*N.y

dot(v, w)
cross(N.x, N.y)          # N.z
outer(N.x, N.x)          # dyadic
express(A.x, N)          # rewrite A.x in N
```

`cross(vec1, vec2)` returns a vector; `outer(vec1, vec2)` returns a dyadic; `express(expr, frame)` rewrites vector/dyadic components in a chosen reference frame. ([SymPy Documentation][3])

## 15.1.4 Points and kinematics

```python
O = Point("O")
P = Point("P")

O.set_vel(N, 0)
P.set_pos(O, q1*N.x)
P.set_vel(N, P.pos_from(O).dt(N))

P.pos_from(O)
P.vel(N)
P.acc(N)
```

Time derivatives:

```python
time_derivative(v, N)
time_derivative(v, A)
time_derivative(outer(N.x, N.x), B)
```

`time_derivative(expr, frame, order=1)` calculates the derivative of vector/scalar/dyadic expressions in a specified frame; this is not identical to ordinary `diff` because rotating frames contribute basis-vector derivatives. ([SymPy Documentation][3])

### Deployment rules

```text
Use sympy.physics.vector for:
  rotating frames
  kinematics
  dyadics
  time derivatives in frames
  mechanics preprocessing

Do not use plain Matrix as a substitute for ReferenceFrame-aware vectors.
Use express(...) before extracting components for codegen.
Use dynamicsymbols for time-dependent generalized coordinates/speeds.
```

---

## 15.2 Mechanics: particles, rigid bodies, inertias, loads

## 15.2.1 Core imports

```python
from sympy.physics.mechanics import (
    Particle,
    RigidBody,
    ReferenceFrame,
    Point,
    dynamicsymbols,
    inertia,
    inertia_of_point_mass,
    Force,
    Torque,
    KanesMethod,
    LagrangesMethod,
    Lagrangian,
    System,
)
```

`RigidBody(name, masscenter=None, frame=None, mass=None, inertia=None)` is a container for a rigid body’s name, mass center, reference frame, mass, and inertia; `Particle` represents a point mass. The old `Body` class is deprecated since SymPy 1.13 in favor of `RigidBody` and `Particle`. ([SymPy Documentation][4])

## 15.2.2 Particle

```python
m = sp.symbols("m")
N = ReferenceFrame("N")
P = Point("P")

P.set_vel(N, u1*N.x)

pa = Particle("pa", P, m)

pa.mass
pa.point
pa.kinetic_energy(N)
```

## 15.2.3 Rigid body and inertia

```python
m, Ixx, Iyy, Izz = sp.symbols("m Ixx Iyy Izz")

N = ReferenceFrame("N")
C = Point("C")
C.set_vel(N, 0)

inertia_dyadic = inertia(N, Ixx, Iyy, Izz)

body = RigidBody(
    "body",
    masscenter=C,
    frame=N,
    mass=m,
    inertia=(inertia_dyadic, C),
)

body.kinetic_energy(N)
```

## 15.2.4 Loads

```python
F = sp.symbols("F")
force = (P, F*N.x)
torque = (N, F*N.z)
```

In Kane/Lagrange workflows, loads are usually iterable tuples of `(Point, Vector)` for forces or `(ReferenceFrame, Vector)` for torques; mechanics docs use this convention in method examples. ([SymPy Documentation][5])

---

## 15.3 Kane’s method

## 15.3.1 Minimal skeleton

```python
q = dynamicsymbols("q")
u = dynamicsymbols("u")
m, k, c = sp.symbols("m k c")

N = ReferenceFrame("N")
P = Point("P")
P.set_vel(N, u*N.x)

particle = Particle("particle", P, m)

kd = [q.diff(t) - u]
loads = [(P, (-k*q - c*u)*N.x)]

KM = KanesMethod(
    N,
    q_ind=[q],
    u_ind=[u],
    kd_eqs=kd,
)

fr, frstar = KM.kanes_equations(
    bodies=[particle],
    loads=loads,
)

mass_matrix = KM.mass_matrix
forcing = KM.forcing
eom_rhs = KM.rhs()
```

`KanesMethod` derives equations of motion using Kane’s method; its API accepts generalized coordinates, generalized speeds, kinematic differential equations, bodies, loads, constraints, auxiliary speeds, and solver choices. Its docs note that the kinematic differential equations and velocity constraints are solved as linear systems and that the default `'LU'` solver is compact but can produce zero-division issues, while `"CRAMER"` can be more robust but slower and larger. ([SymPy Documentation][6])

## 15.3.2 Solver selection

```python
KM = KanesMethod(
    N,
    q_ind=[q],
    u_ind=[u],
    kd_eqs=kd,
    kd_eqs_solver="LU",
)

KM_cramer = KanesMethod(
    N,
    q_ind=[q],
    u_ind=[u],
    kd_eqs=kd,
    kd_eqs_solver="CRAMER",
)
```

Deployment rules:

```text
Use Kane’s method when:
  generalized speeds are useful;
  constraints/noncontributing forces matter;
  multibody systems need efficient EOM derivation.

Use explicit q/u ordering:
  stable state-vector ordering for rhs(), linearization, codegen.

Solver guard:
  LU = fewer operations, possible zero-division singularities.
  CRAMER = slower/larger, fewer division-singularity surprises.
  callable solver = custom simplify/LU/linsolve strategy.
```

---

## 15.4 Lagrange’s method

```python
q = dynamicsymbols("q")
qd = q.diff(t)

N = ReferenceFrame("N")
P = Point("P")
P.set_vel(N, qd*N.x)

m, k = sp.symbols("m k")
particle = Particle("particle", P, m)

T = particle.kinetic_energy(N)
V = k*q**2/2
L = T - V

LM = LagrangesMethod(L, [q])
eom = LM.form_lagranges_equations()

mass_matrix = LM.mass_matrix
forcing = LM.forcing
rhs = LM.rhs()
```

`LagrangesMethod` derives equations of motion from a Lagrangian and generalized coordinates; mechanics docs use `LagrangesMethod`, `Lagrangian`, `ReferenceFrame`, `Particle`, `Point`, and `dynamicsymbols` in spring-mass examples. Both Kane and Lagrange method objects support forming a `Linearizer` through `.to_linearizer()`. ([SymPy Documentation][5])

Deployment rules:

```text
Use Lagrange’s method when:
  energy expressions are natural;
  forces are conservative or generalized forces are simple;
  coordinates alone are sufficient.

Use Kane’s method when:
  nonholonomic constraints, speeds, complex multibody kinematics dominate.
```

---

## 15.5 Joints, `System`, actuators, linearization

## 15.5.1 Joints and `System`

```python
from sympy.physics.mechanics import (
    RigidBody,
    PinJoint,
    PrismaticJoint,
    System,
)

# system = System.from_newtonian(wall_or_ground_body)
# system.add_bodies(body1, body2)
# system.add_joints(joint)
# system.add_loads(load)
# system.form_eoms()
```

The joints framework consists of joint classes that create connections between bodies and a `System` class that forms equations of motion; the docs describe both as bookkeeping layers for relationships between bodies. A joint subtracts degrees of freedom from a body and serves as a base class for specific joints, while `System` stores bodies, joints, loads, actuators, constraints, coordinates, speeds, and equation-of-motion method data. ([SymPy Documentation][7])

## 15.5.2 Linearization

```python
linearizer = KM.to_linearizer()
A, B = linearizer.linearize(A_and_B=True)
```

Mechanics linearization stores generalized coordinates, speeds, inputs, and constraints in a `Linearizer`; `KanesMethod` and `LagrangesMethod` both form this object via `.to_linearizer()`. Use linearization for small-signal state-space models, control design, and numerical simulation around operating points. ([SymPy Documentation][8])

Deployment rules:

```text
Use System + joints when:
  model structure matters;
  bodies/joints/loads should be mutable bookkeeping objects;
  later linearization/actuator workflows are needed.

Use raw Kane/Lagrange when:
  equations are compact and custom pipeline control is preferred.

Before linearization:
  define independent/dependent coordinates and speeds explicitly.
  substitute operating-point values.
  validate state/input ordering.
```

---

## 15.6 Control systems

## 15.6.1 Imports and transfer functions

```python
from sympy.physics.control import (
    TransferFunction,
    StateSpace,
    Series,
    Parallel,
    Feedback,
)

s = sp.symbols("s")

G = TransferFunction(3*s**2 + 7*s - 3, s**2 - 4*s + 2, s)
C = TransferFunction(5*s - 10, s + 7, s)

loop = Feedback(G, C)
closed = loop.doit(cancel=True, expand=True)
```

The control module supports transfer functions and state-space systems. `Series`, `Parallel`, and `Feedback` are symbolic interconnection objects that evaluate with `.doit()`. Interconnections require transfer functions to use the same Laplace variable; if a `StateSpace` object is part of an interconnection, `.doit()` can return a `StateSpace`, and `.rewrite(TransferFunction)` can convert compatible objects. ([SymPy Documentation][9])

## 15.6.2 Properness and expressions

```python
G.num
G.den
G.var
G.is_proper
G.is_strictly_proper
G.is_biproper
G.to_expr()
```

Control docs expose properness predicates: `is_proper`, `is_strictly_proper`, and `is_biproper`, based on numerator/denominator polynomial degrees. ([SymPy Documentation][9])

## 15.6.3 State-space

```python
A = sp.Matrix([[1, 2], [1, 0]])
B = sp.Matrix([1, 1])
Cmat = sp.Matrix([[0, 1]])
D = sp.Matrix([0])

ss = StateSpace(A, B, Cmat, D)

ss.num_states
ss.state_matrix
ss.input_matrix
ss.output_matrix
ss.feedforward_matrix
ss.observability_matrix()
ss.controllability_matrix()
```

`StateSpace` models support controllability, observability, and transformations between state-space and transfer-function representations; MIMO state-space systems are supported. Symbolic control outputs are exact symbolic expressions rather than numerical approximations. ([SymPy Documentation][10])

## 15.6.4 Plotting cautions

Control plotting helpers can raise if the system is not SISO LTI, if time-delay terms are present, if more than one free symbol exists, or if frequency/phase units are invalid. ([SymPy Documentation][11])

Deployment rules:

```text
Use control module for:
  symbolic transfer functions;
  exact pole/zero/properness analysis;
  symbolic feedback/series/parallel derivations;
  state-space controllability/observability;
  educational control-system derivations.

Use python-control/SciPy for:
  numeric robust control, simulation-heavy workflows, industrial design loops.

Before plotting:
  ensure SISO LTI,
  exactly one Laplace variable,
  no unsupported time-delay terms,
  numeric parameter substitutions when required.
```

---

## 15.7 Units, dimensions, quantities, unit systems

## 15.7.1 Imports

```python
from sympy.physics.units import (
    meter, second, kilogram, newton, joule, watt,
    speed_of_light, gravitational_constant,
    Quantity, Dimension,
)
from sympy.physics.units import convert_to
from sympy.physics.units.systems import SI
```

The units module integrates unit systems into SymPy, allowing users to choose unit systems, display units, and convert units. Units and constants are represented as `Quantity` objects; a `Quantity` has a dimension and a scale factor to another quantity of the same dimension, usually mediated through `UnitSystem` objects. ([SymPy Documentation][12])

## 15.7.2 Dimensions

```python
length = Dimension("length")
time = Dimension("time")
velocity = length / time
acceleration = length / time**2
```

Dimensions compose by multiplication, division, and exponentiation; addition/subtraction is defined only for identical dimensions. ([SymPy Documentation][13])

## 15.7.3 Quantities and conversion

```python
expr = 3*meter + 40*sp.physics.units.centimeter
convert_to(expr, meter)

force = kilogram * meter / second**2
convert_to(force, newton)
```

`convert_to(expr, target_units, unit_system='SI')` rewrites an expression involving quantities into target units when dimensions are compatible. ([SymPy Documentation][14])

## 15.7.4 Prefixes and custom systems

```python
from sympy.physics.units.prefixes import kilo, milli, Prefix
from sympy.physics.units.unitsystem import UnitSystem
```

`Prefix` objects define name, symbol, exponent, base, and factor, and prefixes are used to create derived units. `UnitSystem(base_units, units=(), name='', descr='', dimension_system=None, derived_units={})` represents a coherent unit system and can be extended. ([SymPy Documentation][15])

Deployment rules:

```text
Use units for:
  dimensional consistency checks;
  symbolic unit conversion;
  exact display/derivation with physical quantities.

Do not:
  expect units to make numerical simulations dimension-safe automatically;
  lambdify expressions with Quantity objects without converting/removing units first.

Before numeric deployment:
  convert_to(..., target_units)
  strip unit factors deliberately
  validate dimensions
```

---

## 15.8 Optics

## 15.8.1 Utility surface

```python
from sympy.physics.optics import (
    refraction_angle,
    fresnel_coefficients,
    deviation,
    brewster_angle,
    critical_angle,
    lens_makers_formula,
    mirror_formula,
    lens_formula,
    hyperfocal_distance,
    transverse_magnification,
)
```

The optics utilities include refraction, Fresnel coefficients, deviation, Brewster angle, critical angle, lens maker’s formula, mirror/lens formulas, hyperfocal distance, and transverse magnification. `brewster_angle` and `critical_angle` accept `Medium` objects or sympifiable refractive indices and return angles in radians; Fresnel coefficients return reflection/transmission coefficients for `p` and `s` polarizations, with complex coefficients under total internal reflection. ([SymPy Documentation][16])

```python
brewster_angle(1, 1.33)
critical_angle(1.33, 1)
lens_formula(u, v, f)
mirror_formula(u, v, f)
```

Deployment rules:

```text
Use optics utilities for:
  paraxial/elementary optics formulas;
  symbolic refractive-index relationships;
  exact/symbolic optical derivations;
  educational wave/polarization/refraction examples.

Guard:
  angles are radians.
  functions may return numeric Float if inputs are floats.
  use exact Rational/symbolic inputs for exact formulas.
  verify sign conventions for lens/mirror formulas.
```

---

## 15.9 Continuum mechanics

## 15.9.1 Beam

```python
from sympy.physics.continuum_mechanics.beam import Beam

E, I = sp.symbols("E I")
R1, R2 = sp.symbols("R1 R2")

b = Beam(10, E, I)
b.apply_load(-10, 5, -1)   # point load
b.apply_support(0, "pin")
b.apply_support(10, "roller")

b.load
b.shear_force()
b.bending_moment()
b.slope()
b.deflection()
```

A `Beam` models a structural element resisting bending, parameterized by length, elastic modulus, and second moment of area; docs explicitly require a consistent sign convention, where positive shear and moment conventions must be respected. ([SymPy Documentation][17])

## 15.9.2 Truss, cable, arch

```python
from sympy.physics.continuum_mechanics.truss import Truss
# from sympy.physics.continuum_mechanics.cable import Cable
# from sympy.physics.continuum_mechanics.arch import Arch
```

Continuum mechanics includes beam, truss, cable, and arch modules. `Truss` solves 2D truss problems; docs define a truss as an assembly of two-force members connected by nodes and note engineering applications such as bridges. ([SymPy Documentation][18])

Deployment rules:

```text
Use continuum_mechanics for:
  educational structural mechanics;
  exact symbolic reaction/shear/moment/deflection expressions;
  small deterministic structural problems.

Guard:
  sign conventions are user responsibility.
  geometry/load units should be consistent.
  for large finite-element analysis, use dedicated FEA tools.
```

---

## 15.10 Quantum mechanics

## 15.10.1 Core objects

```python
from sympy.physics.quantum import (
    Operator,
    HermitianOperator,
    Commutator,
    AntiCommutator,
    Dagger,
    TensorProduct,
    qapply,
    represent,
)
```

The quantum module includes quantum functions, operators/states/Hilbert spaces, tensor products, representation logic, spin, qubits, gates, Grover, QFT, Shor, and analytic particle-in-box tools. ([SymPy Documentation][19])

## 15.10.2 Operators and commutators

```python
A = Operator("A")
B = Operator("B")

comm = Commutator(A, B)
comm.doit()          # A*B - B*A

Dagger(A*B)
```

`Operator` is the base for noncommuting quantum operators. `Commutator(A, B)` represents `[A, B] = A*B - B*A` unevaluated; `.doit()` evaluates it, canonical ordering is applied, and commutative constants are factored out. ([SymPy Documentation][20])

## 15.10.3 States, Hilbert spaces, representation

```python
# representative imports vary by basis:
# from sympy.physics.quantum.state import Ket, Bra
# from sympy.physics.quantum.spin import JzKet, JzBra, JzOp
```

`represent(expr, **options)` handles matrix/vector representations of quantum operators/states in specified bases; the docs note TODOs around continuous Hilbert spaces and default-basis documentation, so agents should not assume complete continuous-basis coverage. ([SymPy Documentation][21])

## 15.10.4 Spin

```python
from sympy.physics.quantum.spin import (
    JzKet,
    JzBra,
    JzOp,
    JplusOp,
    JminusOp,
)

ket = JzKet(sp.S(1)/2, sp.S(1)/2)
```

Spin states such as `JzKet(j, m)` represent eigenkets of spin operators; uncoupled multi-spin states are represented as tensor products of separate spin states. ([SymPy Documentation][22])

## 15.10.5 Qubits, gates, QFT, Grover, Shor

```python
from sympy.physics.quantum.qubit import Qubit
# from sympy.physics.quantum.gate import XGate, HGate, CNOT
# from sympy.physics.quantum.qft import QFT
```

The quantum module includes quantum computation submodules for circuit plotting, gates, Grover’s algorithm, QFT, qubits, and Shor’s algorithm. Treat these as symbolic/educational quantum-computation tools, not high-performance quantum simulators. ([SymPy Documentation][19])

## 15.10.6 Deployment rules

```text
Use quantum module for:
  symbolic noncommutative operator algebra;
  exact commutators/anticommutators;
  symbolic spin states;
  small exact qubit/gate derivations;
  educational quantum algorithms.

Guard:
  not a production quantum simulator.
  representation support can be basis-specific.
  continuous Hilbert-space support has documented TODOs.
  simplify/qapply/represent should be explicit phase boundaries.
```

---

## 15.11 Biomechanics

```python
from sympy.physics.biomechanics import (
    # activation and musculotendon classes vary by model;
)
```

`physics.biomechanics` extends `physics.mechanics` for biomechanical modeling. It provides musculotendon models for the muscular system and activation dynamics for the neurological system, is designed to be used together with mechanics, and mimics mechanics interfaces where possible. Musculotendon models produce force based on activation, length, and extension velocity, governed by force-length and force-velocity characteristic curves. ([SymPy Documentation][23])

Curve examples and published constants:

```python
from sympy.physics.biomechanics.curve import TendonForceLengthDeGroote2016

l_T_tilde = sp.symbols("l_T_tilde")
curve = TendonForceLengthDeGroote2016.with_defaults(l_T_tilde)
```

Biomechanics curve docs provide De Groote 2016 characteristic functions such as tendon force-length and inverse tendon force-length functions; `.with_defaults(...)` constructors use published constants and are recommended when those model constants should not be changed. ([SymPy Documentation][24])

Deployment rules:

```text
Use biomechanics for:
  symbolic musculotendon/activation model derivation;
  integration with mechanics multibody models;
  educational/research model equations.

Guard:
  not intended as standalone; use with mechanics.
  published constants have model-specific meanings.
  validate physiological domain/ranges externally.
  numeric simulation should be generated/handed off after symbolic derivation.
```

---

## 15.12 High-energy physics, Pauli algebra, hydrogen, oscillator, Wigner

## 15.12.1 HEP gamma matrices

```python
from sympy.physics.hep.gamma_matrices import GammaMatrix, LorentzIndex
from sympy.tensor.tensor import tensor_indices

i = tensor_indices("i", LorentzIndex)
GammaMatrix(i)
```

The HEP module contains gamma-matrix routines expressed as tensor objects. Treat it as a specialized tensor/gamma algebra helper, not a complete particle-physics CAS. ([SymPy Documentation][25])

## 15.12.2 Pauli algebra

```python
from sympy.physics.paulialgebra import Pauli, evaluate_pauli_product

sx = Pauli(1)
sy = Pauli(2)
sz = Pauli(3)

evaluate_pauli_product(sx*sy)
```

The Pauli algebra module implements Pauli algebra by subclassing `Symbol`; it uses algebraic properties of Pauli matrices, not explicit `Matrix` objects. ([SymPy Documentation][26])

## 15.12.3 Physics matrices

```python
from sympy.physics.matrices import mgamma, msigma

gamma0 = mgamma(0)
gamma_mu_lower = mgamma(0, lower=True)
sigma1 = msigma(1)
```

`mgamma(mu, lower=False)` returns Dirac gamma matrices in the standard representation; `lower=True` returns lower-index gamma matrices. The `mdft` function is deprecated in favor of `DFT(...).as_explicit()`. ([SymPy Documentation][27])

## 15.12.4 Hydrogen wavefunctions

```python
from sympy.physics.hydrogen import R_nl, Psi_nlm, E_nl, E_nl_dirac

r, phi, theta = sp.symbols("r phi theta", positive=True)

R_nl(1, 0, r)
Psi_nlm(1, 0, 0, r, phi, theta)
E_nl(1)
E_nl_dirac(3, 1)
```

Hydrogen docs provide functions such as `Psi_nlm(n, l, m, r, phi, theta, Z=1)`, which returns the product of radial wavefunction `R_nl` and spherical harmonic `Y_l^m`, plus nonrelativistic and Dirac energy expressions. ([SymPy Documentation][28])

## 15.12.5 Quantum harmonic oscillator and Wigner symbols

```python
# representative modules:
# sympy.physics.qho_1d
# sympy.physics.sho
# sympy.physics.wigner
```

SymPy physics includes pages for quantum harmonic oscillator in 1D and 3D and Wigner symbols; Wigner and oscillator helpers are specialized symbolic physics utilities. ([SymPy Documentation][29])

Deployment rules:

```text
Use these modules for:
  exact symbolic textbook physics formulas;
  representation of gamma/Pauli algebra;
  hydrogen/oscillator/Wigner coefficient derivation;
  educational and analytic symbolic workflows.

Guard:
  not full numerical physics simulation libraries.
  some APIs are specialized and less general than core SymPy.
  prefer explicit Matrix objects when actual numeric matrix multiplication is required.
```

---

## 15.13 Production maturity matrix

| Module                                             | Best fit                                                        | Production posture                                                         |
| -------------------------------------------------- | --------------------------------------------------------------- | -------------------------------------------------------------------------- |
| `physics.vector`                                   | kinematics, frames, dyadics                                     | mature symbolic mechanics foundation                                       |
| `physics.mechanics`                                | multibody EOM derivation                                        | strong symbolic derivation; simulation requires generated/numeric handoff  |
| `physics.control`                                  | exact transfer/state-space algebra                              | useful symbolic analysis; not a replacement for numeric control toolchains |
| `physics.units`                                    | dimensional analysis and unit conversion                        | useful symbolic layer; strip/convert before numeric kernels                |
| `physics.optics`                                   | paraxial/formula optics and Fresnel utilities                   | educational/analytic optics; verify conventions                            |
| `continuum_mechanics`                              | beams/trusses/cables/arches                                     | exact small structural problems; not full FEA                              |
| `physics.quantum`                                  | symbolic quantum algebra and small quantum-computation examples | educational/symbolic; not high-performance quantum simulation              |
| `biomechanics`                                     | musculotendon/activation models with mechanics                  | specialized research/education; validate model/domain                      |
| `hep`, `paulialgebra`, `hydrogen`, `qho`, `wigner` | specialized textbook physics formulas                           | specialized symbolic utilities                                             |

---

## 15.14 Deployment recipes

## Recipe A — mechanics derive → numeric RHS

```python
def mechanics_rhs_callable(KM, states, parameters, *, modules="numpy"):
    rhs = KM.rhs()
    args = list(states) + list(parameters)
    return sp.lambdify(args, rhs, modules=modules)
```

Use after equations of motion are derived and all unresolved symbolic mechanics objects have been expressed as scalar/matrix expressions.

## Recipe B — linearized mechanics model

```python
def linearize_mechanics(method, *, op_point=None):
    lin = method.to_linearizer()
    A, B = lin.linearize(A_and_B=True, op_point=op_point)
    return sp.simplify(A), sp.simplify(B)
```

Use `op_point` to substitute equilibrium values and reduce expression swell.

## Recipe C — unit-safe numeric conversion

```python
from sympy.physics.units import convert_to, meter, second

def strip_units(expr, target_units):
    converted = convert_to(expr, target_units)
    return sp.simplify(converted / sp.prod(target_units if isinstance(target_units, (list, tuple)) else [target_units]))
```

Use only when `target_units` forms a dimension-compatible basis.

## Recipe D — control feedback exact simplification

```python
def closed_loop_tf(plant, controller, *, cancel=True, expand=False):
    return Feedback(plant, controller).doit(cancel=cancel, expand=expand)
```

## Recipe E — symbolic quantum commutator

```python
def commutator_expanded(A, B):
    return Commutator(A, B).doit()
```

## Recipe F — continuum beam workflow

```python
def beam_solve_basic(length, E, I, loads, supports):
    from sympy.physics.continuum_mechanics.beam import Beam

    b = Beam(length, E, I)
    for load in loads:
        b.apply_load(*load)
    for support in supports:
        b.apply_support(*support)
    return {
        "load": b.load,
        "shear": b.shear_force(),
        "moment": b.bending_moment(),
        "slope": b.slope(),
        "deflection": b.deflection(),
    }
```

---

## 15.15 Anti-pattern inventory

| Anti-pattern                                                           | Failure mode                                    | Correct pattern                               |
| ---------------------------------------------------------------------- | ----------------------------------------------- | --------------------------------------------- |
| using plain `diff` for rotating vector derivative                      | missing frame effects                           | `time_derivative(expr, frame)`                |
| building mechanics with plain symbols for time states                  | no time dependence                              | `dynamicsymbols`                              |
| using `A.inv()*b` inside mechanics/control loops                       | expression swell                                | solve/decomposition methods                   |
| ignoring Kane solver singularities                                     | `nan` / zero division                           | use `"CRAMER"` or callable solver when needed |
| treating `System` as black box                                         | unstable state/order assumptions                | inspect coordinates/speeds/bodies/joints      |
| plotting control system with extra free symbols                        | `ValueError`                                    | substitute parameters; one Laplace variable   |
| lambdifying unit expressions directly                                  | backend errors / unit objects in numeric kernel | `convert_to`, strip units                     |
| using continuum mechanics as FEA                                       | not scalable/general enough                     | export equations or use dedicated FEA         |
| using `sympy.physics.quantum` as simulator                             | performance/features mismatch                   | use quantum simulators for numerics           |
| using biomechanics standalone                                          | missing skeletal mechanics context              | combine with `physics.mechanics`              |
| using `sympy.crypto`-like physics analogs for real security/simulation | toy/educational modules                         | use domain-specific production tools          |

---

## 15.16 Testing matrix

```python
def test_vector_frame_derivative():
    N = ReferenceFrame("N")
    q = dynamicsymbols("q")
    A = N.orientnew("A", "Axis", [q, N.z])
    assert time_derivative(A.x, N) != 0

def test_control_closed_loop_var():
    s = sp.symbols("s")
    G = TransferFunction(1, s + 1, s)
    C = TransferFunction(1, s + 2, s)
    F = Feedback(G, C).doit()
    assert F.var == s

def test_units_conversion():
    from sympy.physics.units import meter, centimeter, convert_to
    assert convert_to(100*centimeter, meter) == meter

def test_quantum_commutator():
    A = Operator("A")
    B = Operator("B")
    assert Commutator(A, B).doit() == A*B - B*A

def test_pauli_product():
    from sympy.physics.paulialgebra import Pauli, evaluate_pauli_product
    assert evaluate_pauli_product(Pauli(1)*Pauli(1)) == 1
```

Coverage targets:

```text
vector:
  frame orientation, express, dot/cross/outer, time_derivative

mechanics:
  particle kinetic energy, rigid-body inertia, Kane equations, Lagrange equations,
  rhs shape, linearizer shape, solver variants

control:
  transfer function properness, feedback/series/parallel doit,
  state-space controllability/observability, rewrite TransferFunction

units:
  dimension compatibility, convert_to, prefixes, custom unit system

optics:
  Brewster/critical angles, refraction/Fresnel coefficients, lens formulas

continuum:
  beam reaction/shear/moment/deflection, truss solve

quantum:
  commutators, Dagger, tensor products, qapply, represent, spin states, qubit gates

biomechanics:
  curve constructors with defaults, activation/musculotendon force expressions

special:
  hydrogen functions, Pauli algebra, Wigner symbols, gamma matrices
```

---

## 15.17 Minimal physics harness

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import sympy as sp

from sympy.physics.vector import (
    ReferenceFrame,
    Point,
    dynamicsymbols,
    express,
    time_derivative,
    dot,
    cross,
    outer,
)

from sympy.physics.mechanics import (
    Particle,
    RigidBody,
    KanesMethod,
    LagrangesMethod,
    Lagrangian,
    inertia,
)

from sympy.physics.control import (
    TransferFunction,
    StateSpace,
    Series,
    Parallel,
    Feedback,
)

from sympy.physics.units import convert_to

from sympy.physics.quantum import (
    Operator,
    Commutator,
    Dagger,
    TensorProduct,
)

t = dynamicsymbols._t


@dataclass(frozen=True)
class VectorAudit:
    expr: Any
    frame: ReferenceFrame
    expressed: Any
    time_derivative: Any


def audit_vector(expr: Any, frame: ReferenceFrame) -> VectorAudit:
    return VectorAudit(
        expr=expr,
        frame=frame,
        expressed=express(expr, frame),
        time_derivative=time_derivative(expr, frame),
    )


@dataclass(frozen=True)
class MechanicsAudit:
    mass_matrix: sp.Matrix
    forcing: sp.Matrix
    rhs: sp.Matrix
    coordinates: tuple[Any, ...]
    speeds: tuple[Any, ...]


def audit_kane_method(method: KanesMethod) -> MechanicsAudit:
    return MechanicsAudit(
        mass_matrix=method.mass_matrix,
        forcing=method.forcing,
        rhs=method.rhs(),
        coordinates=tuple(method.q),
        speeds=tuple(method.u),
    )


def kane_spring_mass_damper():
    q = dynamicsymbols("q")
    u = dynamicsymbols("u")
    m, k, c = sp.symbols("m k c")

    N = ReferenceFrame("N")
    P = Point("P")
    P.set_vel(N, u*N.x)

    particle = Particle("particle", P, m)
    kd = [q.diff(t) - u]
    loads = [(P, (-k*q - c*u)*N.x)]

    KM = KanesMethod(N, q_ind=[q], u_ind=[u], kd_eqs=kd)
    KM.kanes_equations(bodies=[particle], loads=loads)

    return KM


def mechanics_rhs_lambdify(method: KanesMethod, args: Sequence[Any], *, modules="numpy"):
    return sp.lambdify(list(args), method.rhs(), modules=modules)


@dataclass(frozen=True)
class TransferFunctionAudit:
    tf: TransferFunction
    expr: sp.Expr
    var: sp.Symbol
    is_proper: bool
    is_strictly_proper: bool
    is_biproper: bool


def audit_transfer_function(tf: TransferFunction) -> TransferFunctionAudit:
    return TransferFunctionAudit(
        tf=tf,
        expr=tf.to_expr(),
        var=tf.var,
        is_proper=tf.is_proper,
        is_strictly_proper=tf.is_strictly_proper,
        is_biproper=tf.is_biproper,
    )


def feedback_transfer_function(plant: TransferFunction, controller: TransferFunction, *, cancel=True, expand=False):
    if plant.var != controller.var:
        raise ValueError("plant and controller must use same Laplace variable")
    return Feedback(plant, controller).doit(cancel=cancel, expand=expand)


def state_space_from_matrices(A, B, C, D) -> StateSpace:
    return StateSpace(sp.Matrix(A), sp.Matrix(B), sp.Matrix(C), sp.Matrix(D))


def state_space_audit(ss: StateSpace) -> dict[str, Any]:
    return {
        "num_states": ss.num_states,
        "shape": ss.shape,
        "A": ss.state_matrix,
        "B": ss.input_matrix,
        "C": ss.output_matrix,
        "D": ss.feedforward_matrix,
        "observability_matrix": ss.observability_matrix(),
        "controllability_matrix": ss.controllability_matrix(),
    }


def unit_convert(expr: Any, target_units: Any, *, unit_system="SI"):
    return convert_to(expr, target_units, unit_system=unit_system)


def quantum_commutator(A_name="A", B_name="B"):
    A = Operator(A_name)
    B = Operator(B_name)
    C = Commutator(A, B)
    return {
        "unevaluated": C,
        "expanded": C.doit(),
        "dagger": Dagger(C),
    }


def pauli_product(i: int, j: int):
    from sympy.physics.paulialgebra import Pauli, evaluate_pauli_product
    return evaluate_pauli_product(Pauli(i) * Pauli(j))


def hydrogen_state(n, l, m, r, phi, theta, Z=1):
    from sympy.physics.hydrogen import R_nl, Psi_nlm, E_nl
    return {
        "R_nl": R_nl(n, l, r, Z=Z),
        "Psi_nlm": Psi_nlm(n, l, m, r, phi, theta, Z=Z),
        "E_nl": E_nl(n, Z=Z),
    }


def beam_basic(length, E, I, loads=(), supports=()):
    from sympy.physics.continuum_mechanics.beam import Beam

    b = Beam(length, E, I)

    for load in loads:
        b.apply_load(*load)

    for support in supports:
        b.apply_support(*support)

    return {
        "beam": b,
        "load": b.load,
        "shear_force": b.shear_force(),
        "bending_moment": b.bending_moment(),
        "slope": b.slope(),
        "deflection": b.deflection(),
    }


def optics_angles(n1, n2):
    from sympy.physics.optics import brewster_angle, critical_angle
    return {
        "brewster_angle": brewster_angle(n1, n2),
        "critical_angle": critical_angle(n1, n2),
    }


def biomechanics_tendon_curve(l_T_tilde):
    from sympy.physics.biomechanics.curve import TendonForceLengthDeGroote2016
    return TendonForceLengthDeGroote2016.with_defaults(l_T_tilde)
```

This harness encodes module-boundary discipline: frame-aware vector differentiation, Kane-method equation extraction, mechanics-to-numeric RHS conversion, symbolic transfer-function feedback, state-space analysis, unit conversion, quantum commutator expansion, Pauli algebra, hydrogen formulas, beam structural expressions, optics angles, and biomechanics curve construction.

[1]: https://docs.sympy.org/latest/modules/physics/mechanics/api/index.html?utm_source=chatgpt.com "Mechanics API Reference - SymPy 1.14.0 documentation"
[2]: https://docs.sympy.org/latest/modules/physics/vector/api/classes.html?utm_source=chatgpt.com "Essential Classes - SymPy 1.14.0 documentation"
[3]: https://docs.sympy.org/latest/modules/physics/vector/api/functions.html?utm_source=chatgpt.com "Essential Functions (Docstrings)"
[4]: https://docs.sympy.org/latest/modules/physics/mechanics/api/part_bod.html?utm_source=chatgpt.com "Bodies, Inertias, Loads & Other Functions (Docstrings)"
[5]: https://docs.sympy.org/latest/modules/physics/mechanics/api/kane_lagrange.html?utm_source=chatgpt.com "Kane's Method & Lagrange's Method (Docstrings)"
[6]: https://docs.sympy.org/latest/explanation/modules/physics/mechanics/kane.html?utm_source=chatgpt.com "Kane's Method in Physics/Mechanics"
[7]: https://docs.sympy.org/latest/explanation/modules/physics/mechanics/joints.html?utm_source=chatgpt.com "Joints Framework in Physics/Mechanics"
[8]: https://docs.sympy.org/latest/explanation/modules/physics/mechanics/linearize.html?utm_source=chatgpt.com "Linearization in Physics/Mechanics"
[9]: https://docs.sympy.org/latest/modules/physics/control/lti.html "Control API - SymPy 1.14.0 documentation"
[10]: https://docs.sympy.org/latest/modules/physics/control/control.html "Control - SymPy 1.14.0 documentation"
[11]: https://docs.sympy.org/latest/modules/physics/control/control_plots.html?utm_source=chatgpt.com "Control System Plots - SymPy 1.14.0 documentation"
[12]: https://docs.sympy.org/latest/modules/physics/units/index.html "Unit Systems - SymPy 1.14.0 documentation"
[13]: https://docs.sympy.org/latest/modules/physics/units/dimensions.html?utm_source=chatgpt.com "Dimensions and dimension systems"
[14]: https://docs.sympy.org/latest/modules/physics/units/quantities.html?utm_source=chatgpt.com "Physical quantities - SymPy 1.14.0 documentation"
[15]: https://docs.sympy.org/latest/modules/physics/units/prefixes.html?utm_source=chatgpt.com "Unit prefixes - SymPy 1.14.0 documentation"
[16]: https://docs.sympy.org/latest/modules/physics/optics/utils.html?utm_source=chatgpt.com "Utilities - SymPy 1.14.0 documentation"
[17]: https://docs.sympy.org/latest/modules/physics/continuum_mechanics/beam.html?utm_source=chatgpt.com "Beam (Docstrings) - SymPy 1.14.0 documentation"
[18]: https://docs.sympy.org/latest/modules/physics/continuum_mechanics/index.html?utm_source=chatgpt.com "Continuum Mechanics - SymPy 1.14.0 documentation"
[19]: https://docs.sympy.org/latest/modules/physics/quantum/index.html "Quantum Mechanics - SymPy 1.14.0 documentation"
[20]: https://docs.sympy.org/latest/modules/physics/quantum/operator.html?utm_source=chatgpt.com "Operator - SymPy 1.14.0 documentation"
[21]: https://docs.sympy.org/latest/modules/physics/quantum/represent.html?utm_source=chatgpt.com "Represent - SymPy 1.14.0 documentation"
[22]: https://docs.sympy.org/latest/modules/physics/quantum/spin.html?utm_source=chatgpt.com "Spin - SymPy 1.14.0 documentation"
[23]: https://docs.sympy.org/latest/modules/physics/biomechanics/api/index.html?utm_source=chatgpt.com "Biomechanics API Reference - SymPy 1.14.0 documentation"
[24]: https://docs.sympy.org/latest/modules/physics/biomechanics/api/curve.html?utm_source=chatgpt.com "Curve (Docstrings) - SymPy 1.14.0 documentation"
[25]: https://docs.sympy.org/latest/modules/physics/hep/index.html "High Energy Physics - SymPy 1.14.0 documentation"
[26]: https://docs.sympy.org/latest/modules/physics/paulialgebra.html?utm_source=chatgpt.com "Pauli Algebra - SymPy 1.14.0 documentation"
[27]: https://docs.sympy.org/latest/modules/physics/matrices.html?utm_source=chatgpt.com "Matrices - SymPy 1.14.0 documentation"
[28]: https://docs.sympy.org/latest/modules/physics/hydrogen.html?utm_source=chatgpt.com "Hydrogen Wavefunctions - SymPy 1.14.0 documentation"
[29]: https://docs.sympy.org/latest/modules/physics/wigner.html?utm_source=chatgpt.com "Wigner Symbols - SymPy 1.14.0 documentation"

# 16) Statistics, probability, random variables, and symbolic distributions — agent-ready deep dive

Continuing the same advanced technical-doc pattern as the supplied reference artifact. 

## 16.0 Mental model: `sympy.stats` is symbolic probability IR

`sympy.stats` models probability spaces through **random-variable constructor functions** such as `Die`, `Coin`, `FiniteRV`, `Normal`, `Exponential`, and distribution-specific constructors. These constructors return `RandomSymbol` objects; probability spaces combine naturally through symbolic expressions and are queried through interface functions such as `P`, `E`, `density`, `given`, `where`, `variance`, `covariance`, and sampling helpers. The docs explicitly state that users normally interact through variable-creation functions rather than internal probability-space classes. ([SymPy Documentation][1])

```python id="f6dbnr"
import sympy as sp

from sympy.stats import (
    Die, Coin, FiniteRV,
    Bernoulli, Binomial, Poisson, Geometric, Exponential, Normal,
    density, cdf, quantile, P, E, variance, covariance, correlation,
    std, median, entropy, moment, skewness, kurtosis,
    given, where, sample, sample_iter,
    Probability, Expectation, Variance, Covariance,
)

x, y, z = sp.symbols("x y z")
mu = sp.Symbol("mu", real=True)
sigma = sp.Symbol("sigma", positive=True)
lamda = sp.Symbol("lambda", positive=True, real=True)
p = sp.Symbol("p", positive=True)
```

Core contract:

```text id="wvp5nq"
SymPy stats:
  exact symbolic probability
  distributions as RandomSymbol objects
  density/cdf/probability/expectation as symbolic expressions
  conditional spaces via given/P/E(..., condition)
  sampling as optional external-library-backed approximation

SciPy stats:
  numerical distributions, fitting, tests, sampling, array statistics
  fast numeric workflows over data arrays
```

SciPy’s `scipy.stats` module is the numeric/scientific-statistics counterpart: it contains many probability distributions, summary/frequency statistics, correlation functions, statistical tests, kernel density estimation, quasi-Monte Carlo tools, and more; its probability-distribution tutorial states it has general classes for continuous and discrete random variables and implements over 100 continuous and 20 discrete distributions. ([SciPy Documentation][2])

---

## 16.1 Random variable construction

## 16.1.1 Finite random variables

```python id="av95r4"
D = Die("D", 6)
C = Coin("C")                      # fair coin
B = Bernoulli("B", p, 1, 0)
X = FiniteRV("X", {0: sp.Rational(1, 10),
                   1: sp.Rational(2, 10),
                   2: sp.Rational(3, 10),
                   3: sp.Rational(4, 10)})
```

`Die(name, sides=6)` creates a finite fair die random variable and returns a `RandomSymbol`; the docs show `density(Die('D6', 6)).dict` producing the exact uniform mass map `{1: 1/6, ..., 6: 1/6}`. `FiniteRV(name, density, check=False)` creates a finite random variable from a density dictionary; `check=True` verifies the density sums to one, while the default is `False`. ([SymPy Documentation][3])

```python id="ywbs88"
density(D).dict
# {1: 1/6, ..., 6: 1/6}

density(X).dict
# {0: 1/10, 1: 1/5, 2: 3/10, 3: 2/5}
```

Deployment rules:

```text id="mm9dy6"
Use exact Rational probabilities.
Use FiniteRV(check=True) when ingesting external PMFs.
Use density(rv).dict for finite PMF extraction.
Avoid Python floats unless data are intentionally approximate.
```

---

## 16.1.2 Discrete infinite random variables

```python id="m03xrh"
G = Geometric("G", sp.Rational(1, 5))
Z = Poisson("Z", lamda)
```

`Geometric(name, p)` creates a discrete random variable with density `p*(1-p)**(k-1)`; the docs show `density(G)(z)`, `E(G)`, and `variance(G)` evaluating to `(4/5)**(z - 1)/5`, `5`, and `20` for `p=1/5`. `Poisson(name, lamda)` creates a Poisson random variable with density `lamda**k*exp(-lamda)/k!` and requires a positive rate parameter. ([SymPy Documentation][3])

```python id="ks5wv2"
density(G)(z)
E(G)
variance(G)

density(Z)(z)
E(Z)
variance(Z)
```

Deployment rules:

```text id="sr27qp"
Use positive assumptions for rate/probability parameters.
Expect Sum/infinite support expressions internally.
Use evaluate=False / symbolic classes for delayed probability algebra.
```

---

## 16.1.3 Continuous random variables

```python id="bxfpq2"
N = Normal("N", mu, sigma)
Evar = Exponential("Evar", lamda)
```

Continuous variables produce density functions as `Lambda`-like callable objects from `density(...)`, whereas discrete variables produce dictionary-style mass objects. The docs state this directly: discrete variables produce `Dict`s and continuous variables produce `Lambda`s; examples show `density(Die(...)).dict` and `density(Normal(...))(x)`. ([SymPy Documentation][3])

```python id="6e0ln6"
density(N)(x)
# sqrt(2)*exp(-(x - mu)**2/(2*sigma**2))/(2*sqrt(pi)*sigma)

density(Evar)(x)
```

Deployment rules:

```text id="dj0du4"
Continuous RV:
  density(X)(symbol) -> expression
  cdf(X)(symbol) -> expression/function when available
  P(X > a) -> integral/simplified expression

Discrete finite RV:
  density(X).dict -> PMF map
  P(condition) -> exact sum

Discrete infinite RV:
  density(X)(k) -> symbolic mass function
  E/P may create Sum or closed forms
```

---

## 16.1.4 Binomial and Bernoulli

```python id="48xj5m"
B = Bernoulli("B", p, 1, 0)
K = Binomial("K", 10, p)
```

`Bernoulli(name, p, succ=1, fail=0)` represents a Bernoulli process; `Binomial(name, n, p, succ=1, fail=0)` represents a finite binomial random variable with `n` positive integer trials and `p` rational probability between 0 and 1. ([SymPy Documentation][3])

```python id="m36m1p"
density(B).dict
E(B)
variance(B).simplify()

density(K)
E(K)
variance(K)
```

---

## 16.2 Interface functions: probability, expectation, density

## 16.2.1 `P(condition, given_condition=None, numsamples=None, evaluate=True, **kwargs)`

```python id="xcb50l"
X, Y = Die("X", 6), Die("Y", 6)

P(X > 3)
# 1/2

P(sp.Eq(X, 5), X > 2)
# 1/4

P(X > Y)
# 5/12
```

`P` computes the probability that a condition is true, optionally conditioned on another condition. It accepts combinations of relationals containing `RandomSymbol`s; `numsamples` switches to sampling approximation; `evaluate=False` can return unevaluated objects/integrals for continuous systems. ([SymPy Documentation][3])

Deployment rules:

```text id="gv8ojw"
Use P(condition):
  exact symbolic probability when feasible.

Use P(condition, condition2):
  conditional probability.

Use Probability(condition):
  symbolic object; rewrite/evaluate later.

Use numsamples only:
  sampling approximation; not exact proof.
```

---

## 16.2.2 `Probability`

```python id="qrug1j"
X = Normal("X", 0, 1)

prob = Probability(X > 1)
prob.rewrite(sp.Integral)
prob.evaluate_integral()
prob.doit()
```

`Probability` is the symbolic expression class for probability. It can rewrite to an `Integral` and evaluate that integral; the docs show `Probability(X > 1).rewrite(Integral)` producing the Gaussian tail integral and `evaluate_integral()` evaluating it to an error-function expression. ([SymPy Documentation][3])

Use cases:

```text id="l0g5x1"
delay probability evaluation
emit integral forms
control simplification manually
serialize symbolic probability queries
teach/trace probability derivations
```

---

## 16.2.3 `E(expr, condition=None, numsamples=None, evaluate=True, **kwargs)`

```python id="0mp7qr"
D = Die("D", 6)

E(D)
# 7/2

E(2*D + 1)
# 8

E(D, D > 3)
# 5
```

`E` returns the expected value of a random expression; it accepts a condition for conditional expectation, `numsamples` for sampling approximation, `evalf` behavior for sampling, and `evaluate=False` to return unevaluated forms/integrals in continuous systems. ([SymPy Documentation][3])

---

## 16.2.4 `Expectation`

```python id="wzj8fj"
X = Normal("X", mu, sigma)
Y = Normal("Y", 1, 2)

expr = Expectation(X + Y)
expr.expand()
expr.doit()
expr.doit(deep=False)

Expectation(X).rewrite(sp.Integral)
Expectation(Z).rewrite(sp.Sum)
```

`Expectation` is a symbolic expectation object. It can rewrite to `Integral` for continuous variables and to `Sum` for discrete variables; `.expand()` applies expectation linearity without necessarily evaluating the result, and `.doit(deep=False)` prevents evaluating nested expectations. ([SymPy Documentation][3])

Deployment rules:

```text id="rvu2xr"
Use E:
  immediate exact expectation.

Use Expectation:
  lazy symbolic probability algebra.

Use .rewrite(Integral/Sum):
  inspect measure-level representation.

Use .expand():
  linearity/product algebra before evaluation.

Use .doit(deep=False):
  preserve nested symbolic expectation structure.
```

---

## 16.2.5 `density(expr, condition=None, evaluate=True, numsamples=None, **kwargs)`

```python id="a6t9y9"
D = Die("D", 6)
X = Normal("X", 0, 1)

density(D).dict
density(2*D).dict
density(X)(x)
```

`density` computes the probability density or mass of a random expression, optionally conditioned. Its output shape depends on the probability space: finite/discrete variables can return dictionary-like densities, while continuous variables return callable density functions. The docs explicitly show `density(D).dict`, `density(2*D).dict`, and `density(X)(x)` for a normal variable. ([SymPy Documentation][3])

Output-shape guard:

```python id="tu02q8"
def density_kind(rv):
    d = density(rv)
    if hasattr(d, "dict"):
        return "finite_or_discrete", d.dict
    return "callable_density", d
```

---

## 16.3 CDF, quantile, median, entropy

## 16.3.1 `cdf`, `quantile`, `median`

```python id="ogj2pv"
F = cdf(N)
F(x)

Q = quantile(Evar)
Q(p)

median(N)
median(Die("D"))
```

`quantile(expr)` returns a callable quantile expression. The docs define the quantile as `inf{x : p <= F(x)}` and show `quantile(Exponential("x", lambda))(p)` returning `-log(1-p)/lambda`; for a die, quantile returns a `Piecewise` object with `nan` outside `[0,1]`. `median(X)` returns a `FiniteSet` or `Interval` containing median values; examples show `median(Normal('N', 3, 1)) -> {3}` and `median(Die('D')) -> {3, 4}`. ([SymPy Documentation][3])

## 16.3.2 `entropy`

```python id="2tmhxl"
entropy(Normal("N", 0, 1))
entropy(Die("D", 4))
```

`entropy(expr, condition=None, b=E)` calculates distribution entropy; the docs show the standard normal entropy expression and `entropy(Die('D', 4)) -> log(4)`. ([SymPy Documentation][3])

Deployment rules:

```text id="mtmshm"
median:
  expect FiniteSet or Interval, not scalar.

quantile:
  expect callable / Piecewise; validate p-domain [0,1].

entropy:
  symbolic exact expression; base parameter controls logarithm base.
```

---

## 16.4 Variance, covariance, correlation, moments

## 16.4.1 `variance`, `Variance`

```python id="9r1z6o"
X = Die("X", 6)
B = Bernoulli("B", p, 1, 0)

variance(2*X)
# 35/3

sp.simplify(variance(B))
# p*(1 - p)

Variance(X).rewrite(Expectation)
Variance(X).rewrite(sp.Integral)
Variance(a*X).expand()
```

`variance(X)` is defined as `E((X - E(X))**2)`; examples show `variance(2*Die('X', 6)) -> 35/3` and Bernoulli variance simplifying to `p*(1-p)`. `Variance` is the symbolic class and can rewrite to expectations, integrals, and expand scalar multiplication / sums. ([SymPy Documentation][3])

## 16.4.2 `covariance`, `Covariance`

```python id="qv71pv"
rate = sp.Symbol("lambda", positive=True, real=True)
X = Exponential("X", rate)
Y = Exponential("Y", rate)

covariance(X, X)
# lambda**(-2)

covariance(X, Y)
# 0

covariance(X, Y + rate*X)
# 1/lambda

Covariance(X, Y).rewrite(Expectation)
Covariance(a*X + b*Y, c*Z + d*W).expand()
```

`covariance(X, Y)` is defined as `E((X-E(X))*(Y-E(Y)))`; the docs show independent exponentials have zero covariance, covariance with `X` itself equals `lambda**(-2)`, and symbolic `Covariance` expands bilinearly and rewrites to expectation form. ([SymPy Documentation][3])

## 16.4.3 `correlation`, `std`, `moment`, `skewness`, `kurtosis`

```python id="lqr46o"
std(B)
correlation(X, X)
moment(Die("D", 6), 2)
skewness(Normal("N", 0, 1))
kurtosis(Exponential("Y", rate))
```

`std(X)` is the square root of variance; `correlation(X, Y)` is the normalized covariance-like expression `E((X-E(X))(Y-E(Y))/(sigma_x sigma_y))`; `moment(X, n, c=0)` returns the nth moment about `c`; `skewness` and `kurtosis` compute standardized higher moments. The docs show normal skewness `0`, exponential skewness `2`, and correlation examples for independent and dependent expressions. ([SymPy Documentation][3])

---

## 16.5 Conditional probability and domains

## 16.5.1 `given`

```python id="h3f4b5"
X = Die("X", 6)

Y = given(X, X > 3)
density(Y).dict
# {4: 1/3, 5: 1/3, 6: 1/3}
```

`given(expr, condition)` creates a conditional random expression by constructing a new probability space from the condition and returning the same expression in that conditional space. The docs show `given(Die('X',6), X > 3)` producing a die restricted to `{4,5,6}` with density `1/3` each. ([SymPy Documentation][3])

## 16.5.2 `where`

```python id="gme9hr"
X = Normal("X", 0, 1)

domain = where(X**2 < 1)
domain
domain.set
# Interval.open(-1, 1)
```

`where(condition, given_condition=None)` returns the domain where a random condition is true. Examples show `where(X**2 < 1)` returning a domain whose `.set` is `Interval.open(-1, 1)`, and finite-die conditions producing a disjunction of equalities. ([SymPy Documentation][3])

Deployment rules:

```text id="gz789z"
Use given:
  construct conditional random variables.

Use P(expr, condition):
  compute conditional probability directly.

Use where:
  inspect support/domain induced by a condition.

Keep domains:
  important for truncation, conditional distributions, validation, sampling.
```

---

## 16.6 Symbolic probability classes and delayed evaluation

```python id="9suo8v"
Probability(X > 1)
Expectation(X)
Variance(X)
Covariance(X, Y)
```

Delayed symbolic classes allow algebra before evaluation:

```python id="z7wyb2"
Expectation(X + Y).expand()
Variance(X + Y).expand()
Covariance(a*X + b*Y, c*Z + d*W).expand()

Expectation(X).rewrite(sp.Integral)
Expectation(Z).rewrite(sp.Sum)
Variance(X).rewrite(Expectation)
Covariance(X, Y).rewrite(Expectation)
```

Deployment rules:

```text id="lgdzg7"
Immediate functions:
  P, E, variance, covariance, density
  compute now

Symbolic classes:
  Probability, Expectation, Variance, Covariance
  manipulate algebraically, rewrite to Integral/Sum, evaluate later

Use classes when:
  generating explanations,
  preserving derivation steps,
  avoiding expensive integrals too early,
  building symbolic-statistics IR.
```

---

## 16.7 Sampling vs exact symbolic statistics

## 16.7.1 `sample`

```python id="pb6mtu"
N = Normal("N", 3, 4)

sample(N)
sample(N, N > 0)
sample(N, size=4)
sample(N, size=(2, 3), library="scipy", seed=123)
```

`sample(expr, condition=None, size=(), library='scipy', numsamples=1, seed=None)` produces realizations of a random expression. Supported sampling libraries are `scipy`, `numpy`, and `pymc`; the default is `scipy`. `numsamples` is deprecated since SymPy 1.9 and retained for compatibility; use a list comprehension or an added dimension in `size` instead. The `seed` argument is passed to the external library without modifying the environment’s global seed. Return shapes include scalar values for `sample(X)` and NumPy arrays for `sample(X, size=...)`. ([SymPy Documentation][3])

```python id="0ofeuz"
s1 = sample(N, seed=123)
sarr = sample(N, size=(1000,), seed=123)
```

## 16.7.2 `sample_iter`

```python id="1vso8x"
it = sample_iter(N, size=(), library="scipy", seed=123)
next(it)
```

`sample_iter(expr, condition=None, size=(), library='scipy', numsamples=oo, seed=None)` returns an iterator of realizations. Use it when streaming samples is desired. ([SymPy Documentation][3])

## 16.7.3 Sampling approximations for `P`, `E`, `density`

```python id="vcw8b6"
P(X > 3, numsamples=10_000)
E(N, numsamples=10_000)

from sympy.stats.rv import sampling_P, sampling_E, sampling_density

sampling_P(N > 0, numsamples=10_000, seed=123)
sampling_E(N, numsamples=10_000, seed=123)
```

SymPy exposes sampling versions of `density`, `P`, and `E`; the docs list `sampling_density`, `sampling_P`, and `sampling_E` as sampling variants with default `library='scipy'`. ([SymPy Documentation][3])

Deployment rules:

```text id="fs84tf"
Exact symbolic mode:
  P/E/density/variance/covariance without numsamples.

Sampling mode:
  sample/sample_iter or numsamples/sampling_* APIs.
  approximate, seed-controlled, external-library-dependent.

Never treat sampled estimates as symbolic proofs.
Prefer SciPy/NumPy directly for large Monte Carlo workflows.
```

---

## 16.8 Continuous, discrete, finite, multivariate, matrix distributions

## 16.8.1 Finite/discrete/continuous output distinction

```text id="ybr3le"
finite:
  density(X).dict

discrete infinite:
  density(X)(k) -> mass formula

continuous:
  density(X)(x) -> PDF formula

joint/multivariate:
  density(X)(x1, x2, ...)
  X[i] component random symbol access
  marginal_distribution(...)
```

The docs state the density output differs by probability-space type: discrete variables produce dictionaries and continuous variables produce `Lambda`s/callables. ([SymPy Documentation][3])

## 16.8.2 Multivariate normal

```python id="6ahy79"
from sympy.stats import MultivariateNormal, marginal_distribution

MV = MultivariateNormal("MV", [3, 4], [[2, 1], [1, 2]])

density(MV)(x, y)
density(MV)(1, 2)

marginal_distribution(MV, MV[0])(x)
marginal_distribution(MV, MV[1])(y)
```

`MultivariateNormal(name, mu, sigma)` creates a continuous multivariate-normal random variable with a mean vector and positive semidefinite covariance matrix; if `sigma` is noninvertible, only sampling is currently supported. The docs show density evaluation, marginal distributions, component indexing, and a symbolic-parameter example using `MatrixSymbol`s for `mu`, covariance matrix `Sg`, and observation vector. ([SymPy Documentation][3])

Deployment rule:

```text id="huo8ua"
Use MultivariateNormal for exact symbolic density/marginal derivation.
Use sampling only when covariance is noninvertible.
Use SciPy for large numeric multivariate random generation/density evaluation.
```

## 16.8.3 Other multivariate and matrix distributions

```python id="eub3he"
from sympy.stats import (
    Multinomial, MultivariateBeta, MultivariateT,
    NegativeMultinomial, MatrixNormal, Wishart, MatrixGamma,
)

Mnom = Multinomial("M", 10, sp.Rational(1, 3), sp.Rational(2, 3))
Dir = MultivariateBeta("Dir", sp.Symbol("a1", positive=True), sp.Symbol("a2", positive=True))
Tmv = MultivariateT("T", [1, 1], [[1, 0], [0, 1]], 2)
```

The stats docs list multivariate distributions including `Multinomial`, `MultivariateBeta`/Dirichlet, `MultivariateT`, `NegativeMultinomial`, and matrix distributions such as `MatrixGamma`, `Wishart`, and `MatrixNormal`; each returns a `RandomSymbol` and provides density formulas where implemented. ([SymPy Documentation][3])

---

## 16.9 Independence and product spaces

```python id="yx5kie"
X = Normal("X", 0, 1)
Y = Normal("Y", 0, 1)

E(X + Y)
covariance(X, Y)
P(X > Y)
```

By default, separately constructed random variables such as `X = Normal("X", ...)` and `Y = Normal("Y", ...)` inhabit product spaces and are treated as independent unless dependence is explicitly modeled via joint distributions or conditional constructions. The docs demonstrate independent exponentials with `covariance(X, Y) -> 0` and covariance with dependent expressions such as `covariance(X, Y + rate*X) -> 1/lambda`. ([SymPy Documentation][3])

Deployment rules:

```text id="a4m9mv"
Separate constructors:
  independent RVs by default.

Dependent expressions:
  Y + rate*X depends on X.

Joint RV:
  use multivariate/joint constructors when components are dependent.

Do not assume same distribution name implies same variable.
Use object identity and symbols deliberately.
```

---

## 16.10 SymPy stats vs SciPy stats

## 16.10.1 Use SymPy stats when

```text id="uvfspm"
Need exact symbolic probability.
Need formulas in parameters: mu, sigma, lambda, p.
Need exact E/P/variance/covariance.
Need derivation to Integral/Sum/Probability/Expectation.
Need symbolic conditional distributions.
Need density/cdf/quantile expressions.
Need educational/proof-like statistics.
Need algebraic manipulation before numeric deployment.
```

Examples:

```python id="n9j77i"
X = Normal("X", mu, sigma)
Expectation(X).rewrite(sp.Integral)
E(X)
variance(X)
P(X > mu)
```

## 16.10.2 Use SciPy stats when

```text id="b2c6la"
Need fast numeric PDF/CDF/PPF/SF/ISF over arrays.
Need random variate generation at scale.
Need distribution fitting / maximum likelihood.
Need statistical tests, confidence intervals, empirical data workflows.
Need kernel density estimation, QMC, summary/frequency statistics.
Need robust numeric production pipelines over data.
```

SciPy’s stats module explicitly targets numeric statistics with distributions, tests, summaries, KDE, quasi-Monte Carlo, and more; `scipy.stats.fit` estimates distribution parameters from data using MLE by default or MSE-like spacing methods with optimizer control. ([SciPy Documentation][2])

Bridge pattern:

```python id="dzqd4c"
# symbolic derivation
X = Normal("X", mu, sigma)
pdf_expr = density(X)(x)

# numeric backend
pdf_np = sp.lambdify((x, mu, sigma), pdf_expr, modules="numpy")
```

---

## 16.11 Deployment recipes

## Recipe A — exact finite PMF audit

```python id="k6kkm7"
def finite_pmf(rv):
    d = density(rv)
    if not hasattr(d, "dict"):
        raise TypeError("expected finite/discrete density with .dict")
    return d.dict


def validate_pmf_dict(pmf):
    total = sp.Add(*pmf.values())
    if sp.simplify(total - 1) != 0:
        raise ValueError(f"PMF does not sum to 1: {total}")
    if any(v.is_negative is True for v in pmf.values()):
        raise ValueError(f"negative probabilities: {pmf}")
    return pmf
```

## Recipe B — symbolic normal summary

```python id="v4u8ik"
def normal_symbolic_summary(mu, sigma):
    X = Normal("X", mu, sigma)
    return {
        "rv": X,
        "pdf": density(X)(x),
        "mean": E(X),
        "variance": variance(X),
        "std": std(X),
        "tail_gt_mean": P(X > mu),
        "expectation_integral": Expectation(X).rewrite(sp.Integral),
    }
```

## Recipe C — conditional distribution

```python id="xk780j"
def conditional_density(rv, condition):
    Y = given(rv, condition)
    return density(Y)
```

## Recipe D — robust `P/E` with exact-first, sample fallback

```python id="jh8n2k"
def probability_exact_or_sample(condition, *, samples=None, seed=None):
    if samples is None:
        return P(condition)
    return P(condition, numsamples=samples, seed=seed)


def expectation_exact_or_sample(expr, *, samples=None, seed=None):
    if samples is None:
        return E(expr)
    return E(expr, numsamples=samples, seed=seed)
```

## Recipe E — density to numeric callable

```python id="t4p781"
def density_callable(rv, variable, parameters=(), *, backend="numpy"):
    pdf = density(rv)(variable)
    return sp.lambdify((variable, *parameters), pdf, modules=backend)
```

## Recipe F — multivariate density wrapper

```python id="ohactn"
def multivariate_density_callable(rv, variables, parameters=(), *, backend="numpy"):
    pdf = density(rv)(*variables)
    return sp.lambdify(tuple(variables) + tuple(parameters), pdf, modules=backend)
```

## Recipe G — sample with seed and no deprecated `numsamples`

```python id="wr5xcb"
def draw_samples(rv, *, size, library="scipy", seed=123):
    return sample(rv, size=size, library=library, seed=seed)
```

Use `size` instead of deprecated `numsamples`. ([SymPy Documentation][3])

---

## 16.12 Anti-pattern inventory

| Anti-pattern                                                 | Failure mode                            | Correct pattern                               |
| ------------------------------------------------------------ | --------------------------------------- | --------------------------------------------- |
| float probabilities in symbolic PMF                          | approximate output                      | use `Rational`                                |
| assuming `density(X)` always callable                        | finite distributions expose `.dict`     | branch on `.dict` vs callable                 |
| treating `sample` output as proof                            | Monte Carlo estimate only               | use exact `P/E` for proof                     |
| using deprecated `numsamples` in `sample`                    | deprecated API                          | use `size` or list comprehension              |
| large Monte Carlo via `sympy.stats.sample`                   | overhead / external library indirection | use SciPy/NumPy directly                      |
| no positive assumptions on rate/scale                        | unevaluated/conditional results         | `Symbol(..., positive=True)`                  |
| expecting scalar median                                      | `FiniteSet` or `Interval`               | handle set output                             |
| assuming separate same-parameter RVs are dependent           | covariance zero by independence         | use joint/dependent expression                |
| ignoring `ConditionSet`/Piecewise from quantile/CDF          | invalid domain handling                 | preserve/branch on conditions                 |
| lambdifying random variables directly                        | backend cannot evaluate RV object       | lambdify density/expectation expression       |
| using SymPy stats for data fitting                           | not its purpose                         | SciPy `stats.fit` / numeric stats             |
| relying on exact symbolic integrations for all distributions | slow/unsupported integrals              | delayed `Expectation`/sampling/SciPy fallback |

---

## 16.13 Testing matrix

```python id="rbmz8o"
def test_die_pmf():
    D = Die("D", 6)
    pmf = density(D).dict
    assert sp.simplify(sum(pmf.values()) - 1) == 0
    assert pmf[1] == sp.Rational(1, 6)

def test_normal_mean_variance():
    X = Normal("X", mu, sigma)
    assert E(X) == mu
    assert variance(X).simplify() == sigma**2

def test_bernoulli_variance():
    B = Bernoulli("B", p, 1, 0)
    assert sp.simplify(variance(B) - p*(1 - p)) == 0

def test_conditional_die_density():
    X = Die("X", 6)
    Y = given(X, X > 3)
    assert density(Y).dict == {
        4: sp.Rational(1, 3),
        5: sp.Rational(1, 3),
        6: sp.Rational(1, 3),
    }

def test_covariance_independence():
    X = Exponential("X", lamda)
    Y = Exponential("Y", lamda)
    assert covariance(X, Y) == 0

def test_sample_shape():
    X = Normal("X", 0, 1)
    arr = sample(X, size=(2, 3), seed=123)
    assert arr.shape == (2, 3)
```

Coverage targets:

```text id="ef8u50"
Finite:
  Die, Coin, Bernoulli, Binomial, FiniteRV(check=True)

Discrete infinite:
  Geometric, Poisson, expectation/variance/density formula

Continuous:
  Normal, Exponential, PDF/CDF/quantile/tail probability

Conditional:
  given, P(condition, given_condition), where

Symbolic classes:
  Probability/Expectation/Variance/Covariance rewrite + doit + expand

Multivariate:
  MultivariateNormal density/marginal_distribution/component access

Sampling:
  sample scalar, sample size int/tuple, sample_iter, seed reproducibility

SciPy bridge:
  lambdify density to numpy; compare numeric values against scipy.stats where appropriate
```

---

## 16.14 Minimal statistics harness

```python id="tk2cmz"
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Literal

import sympy as sp

from sympy.stats import (
    Die, Coin, FiniteRV, Bernoulli, Binomial, Poisson, Geometric,
    Exponential, Normal,
    density, cdf, quantile, P, E, variance, covariance, correlation,
    std, median, entropy, moment, skewness, kurtosis,
    given, where, sample, sample_iter,
    Probability, Expectation, Variance, Covariance,
)

x = sp.Symbol("x")


@dataclass(frozen=True)
class RVSummary:
    rv: Any
    density_object: Any
    expectation: Any
    variance: Any
    std: Any
    median: Any | None
    entropy: Any | None


@dataclass(frozen=True)
class ProbabilityAudit:
    expr: Any
    exact_probability: Any
    integral_form: Any | None
    evaluated_integral: Any | None


def exact_rational_probability(p: Any) -> sp.Rational | sp.Expr:
    p = sp.sympify(p)
    if isinstance(p, float):
        raise TypeError("use Rational/string for exact symbolic probability, not float")
    return p


def finite_random_variable(name: str, pmf: dict[Any, Any], *, check: bool = True):
    pmf_exact = {sp.sympify(k): exact_rational_probability(v) for k, v in pmf.items()}
    return FiniteRV(name, pmf_exact, check=check)


def finite_density_dict(rv: Any) -> dict:
    d = density(rv)
    if not hasattr(d, "dict"):
        raise TypeError(f"expected density object with .dict, got {type(d).__name__}")
    return dict(d.dict)


def continuous_density_expr(rv: Any, variable: sp.Symbol = x) -> sp.Expr:
    d = density(rv)
    if hasattr(d, "dict"):
        raise TypeError("expected continuous density callable, got discrete density")
    return sp.sympify(d(variable))


def rv_summary(rv: Any, *, include_median: bool = True, include_entropy: bool = True) -> RVSummary:
    med = None
    ent = None

    if include_median:
        try:
            med = median(rv)
        except Exception:
            med = None

    if include_entropy:
        try:
            ent = entropy(rv)
        except Exception:
            ent = None

    return RVSummary(
        rv=rv,
        density_object=density(rv),
        expectation=E(rv),
        variance=variance(rv),
        std=std(rv),
        median=med,
        entropy=ent,
    )


def probability_audit(condition: Any) -> ProbabilityAudit:
    prob_obj = Probability(condition)

    integral_form = None
    evaluated = None

    try:
        integral_form = prob_obj.rewrite(sp.Integral)
    except Exception:
        pass

    try:
        evaluated = prob_obj.evaluate_integral()
    except Exception:
        pass

    return ProbabilityAudit(
        expr=condition,
        exact_probability=P(condition),
        integral_form=integral_form,
        evaluated_integral=evaluated,
    )


def expectation_symbolic(expr: Any, *, condition: Any | None = None, expand: bool = False, evaluate: bool = False):
    obj = Expectation(expr, condition=condition)
    if expand:
        obj = obj.expand()
    if evaluate:
        obj = obj.doit()
    return obj


def variance_symbolic(expr: Any, *, condition: Any | None = None, expand: bool = False, evaluate: bool = False):
    obj = Variance(expr, condition=condition)
    if expand:
        obj = obj.expand()
    if evaluate:
        obj = obj.doit()
    return obj


def covariance_symbolic(a: Any, b: Any, *, condition: Any | None = None, expand: bool = False, evaluate: bool = False):
    obj = Covariance(a, b, condition=condition)
    if expand:
        obj = obj.expand()
    if evaluate:
        try:
            return obj.evaluate_integral()
        except Exception:
            return obj.doit()
    return obj


def conditional_rv(rv: Any, condition: Any):
    return given(rv, condition)


def conditional_density(rv: Any, condition: Any):
    return density(given(rv, condition))


def support_where(condition: Any):
    return where(condition)


def sample_values(
    expr: Any,
    *,
    condition: Any | None = None,
    size: int | tuple[int, ...] = (),
    library: Literal["scipy", "numpy", "pymc"] = "scipy",
    seed: Any | None = None,
):
    return sample(expr, condition=condition, size=size, library=library, seed=seed)


def sample_stream(
    expr: Any,
    *,
    condition: Any | None = None,
    size: int | tuple[int, ...] = (),
    library: Literal["scipy", "numpy", "pymc"] = "scipy",
    seed: Any | None = None,
):
    return sample_iter(expr, condition=condition, size=size, library=library, seed=seed)


def density_lambdify(
    rv: Any,
    variable: sp.Symbol,
    parameters: Iterable[sp.Symbol] = (),
    *,
    backend: str = "numpy",
):
    expr = continuous_density_expr(rv, variable)
    return sp.lambdify((variable, *tuple(parameters)), expr, modules=backend)


def multivariate_density_expr(rv: Any, variables: tuple[sp.Symbol, ...]) -> sp.Expr:
    return sp.sympify(density(rv)(*variables))


def exact_or_sampling_probability(condition: Any, *, samples: int | None = None, seed: Any | None = None):
    if samples is None:
        return P(condition)
    return P(condition, numsamples=samples, seed=seed)


def exact_or_sampling_expectation(expr: Any, *, samples: int | None = None, seed: Any | None = None):
    if samples is None:
        return E(expr)
    return E(expr, numsamples=samples, seed=seed)


def normal_model(name: str, mu: Any, sigma: Any):
    sigma = sp.sympify(sigma)
    if sigma.is_positive is False:
        raise ValueError("Normal standard deviation must be positive")
    return Normal(name, sp.sympify(mu), sigma)


def poisson_model(name: str, rate: Any):
    rate = sp.sympify(rate)
    if rate.is_positive is False:
        raise ValueError("Poisson rate must be positive")
    return Poisson(name, rate)


def bernoulli_model(name: str, prob: Any, succ: Any = 1, fail: Any = 0):
    prob = exact_rational_probability(prob)
    return Bernoulli(name, prob, succ, fail)


def binomial_model(name: str, trials: int, prob: Any, succ: Any = 1, fail: Any = 0):
    if int(trials) <= 0:
        raise ValueError("trials must be positive")
    prob = exact_rational_probability(prob)
    return Binomial(name, int(trials), prob, succ, fail)


def scipy_handoff_note() -> str:
    return (
        "Use SymPy stats for exact symbolic probability derivation; "
        "use scipy.stats for numeric distributions, fitting, tests, "
        "large sampling, and data-analysis workflows."
    )
```

This harness enforces exact probability inputs, finite-vs-continuous density branching, symbolic probability/expectation/variance/covariance control, conditional random variables, support-domain extraction, seed-controlled sampling through supported libraries, density-to-numeric-callable conversion, distribution parameter validation, and explicit SciPy handoff boundaries.

[1]: https://docs.sympy.org/latest/_sources/modules/stats.rst.txt "docs.sympy.org"
[2]: https://docs.scipy.org/doc/scipy/reference/stats.html?utm_source=chatgpt.com "Statistical functions (scipy.stats) — SciPy v1.17.0 Manual"
[3]: https://docs.sympy.org/latest/modules/stats.html "Stats - SymPy 1.14.0 documentation"

# 17) Plotting, visualization, and interactive workflows — agent-ready deep dive

Continuing the same advanced technical-doc pattern as the supplied reference artifact. 

## 17.0 Visualization model: symbolic expression → numeric sampling → backend render

SymPy plotting is a convenience layer that converts exact symbolic expressions into numerical data series and sends those series to a plotting backend. The official plotting docs state that SymPy supports 2D and 3D plots, currently renders plots with matplotlib as the main backend, and can also plot 2D line plots with a `TextBackend` if matplotlib is unavailable. The core convenience functions are `plot`, `plot_parametric`, `plot_implicit`, `plot3d`, `plot3d_parametric_line`, and `plot3d_parametric_surface`; all are convenience wrappers around `Plot` plus data-series classes. ([SymPy Documentation][1])

```python id="9ymtla"
import sympy as sp

from sympy import sin, cos, exp, Eq, And, pi
from sympy.plotting import (
    plot,
    plot_parametric,
    plot_implicit,
    plot3d,
    plot3d_parametric_line,
    plot3d_parametric_surface,
    PlotGrid,
)

x, y, u, v = sp.symbols("x y u v")
```

Core execution path:

```text id="mmrmf4"
symbolic Expr / Eq / Boolean region
  → plotting function
  → BaseSeries object(s)
  → numeric sampling / mesh generation
  → Plot backend object
  → show() / save(path) / backend-specific figure access
```

---

## 17.1 Basic 2D symbolic plotting: `plot`

## 17.1.1 Syntax

```python id="pyl9x2"
plot(expr, (x, xmin, xmax))
plot(expr)
plot(expr1, expr2, expr3, (x, xmin, xmax))
plot((expr1, (x, a1, b1)), (expr2, (x, a2, b2)))
plot(expr, (x, xmin, xmax), show=False)
```

`plot(*args, show=True, **kwargs)` plots functions of one variable as 2D curves. Typical call shapes: `plot(expr, range)`, `plot(expr)` with default range, `plot(expr1, expr2, ..., range)`, and `plot((expr1, range1), (expr2, range2), ...)`. The docs explicitly recommend specifying ranges because the default range may change if future range-detection logic changes. ([SymPy Documentation][1])

```python id="ocn8pm"
p = plot(sp.sin(x), (x, -sp.pi, sp.pi), show=False)
p.show()

p = plot(x, x**2, x**3, (x, -5, 5), legend=True, show=False)
```

## 17.1.2 Main kwargs

```python id="0oz2zz"
plot(
    sp.sin(x),
    (x, -sp.pi, sp.pi),
    title="sin(x)",
    xlabel=x,
    ylabel="y",
    xlim=(-4, 4),
    ylim=(-2, 2),
    xscale="linear",
    yscale="linear",
    axis_center="auto",
    legend=False,
    line_color="blue",
    adaptive=False,
    n=400,
    show=False,
    backend="matplotlib",
    size=(6, 4),
)
```

Relevant options include axis labels, title, line color, axis scales, axis center, limits, legend, backend, and figure size. `show=False` prevents immediate rendering and returns a `Plot` object that can later be displayed with `.show()` or saved with `.save(path)`. ([SymPy Documentation][1])

## 17.1.3 Sampling controls

```python id="y7v1mg"
plot(sp.sin(x), (x, -10, 10), adaptive=False, n=1000)
plot(sp.sin(1/x), (x, -1, 1), adaptive=True, depth=5)
```

For `plot`, adaptive sampling is not the default in current docs; uniform sampling uses `n`, while adaptive sampling uses recursive sampling and `depth`. The plotting docs state that adaptive sampling uses a random point near a midpoint, so repeated plots may appear slightly different; use `adaptive=False, n=...` for deterministic uniform sampling. ([SymPy Documentation][1])

Deployment rule:

```text id="erafqs"
Use adaptive=False,n=N:
  deterministic output
  tests/snapshots
  smooth non-singular functions
  reproducible docs

Use adaptive=True,depth=D:
  sharp features
  singularities
  oscillations
  exploratory plotting

Always:
  specify range explicitly
```

---

## 17.2 2D parametric plotting: `plot_parametric`

## 17.2.1 Syntax

```python id="rfmm13"
plot_parametric((expr_x, expr_y), (u, umin, umax))
plot_parametric((expr_x, expr_y), ..., (u, umin, umax))
plot_parametric((expr_x1, expr_y1, (u, a1, b1)),
                (expr_x2, expr_y2, (u, a2, b2)))
```

`plot_parametric(*args, show=True, **kwargs)` plots 2D parametric curves. Common call forms include a single `(expr_x, expr_y)` pair plus a range, multiple curves sharing one range, or per-curve tuples `(expr_x, expr_y, range)`. If no range is specified, default range is `(-10, 10)`, but explicit ranges are safer. ([SymPy Documentation][1])

```python id="3d26ke"
p = plot_parametric((sp.cos(u), sp.sin(u)), (u, 0, 2*sp.pi), show=False)
```

## 17.2.2 Sampling and color

```python id="8pz9j1"
plot_parametric(
    (sp.cos(u), sp.sin(u)),
    (u, 0, 2*sp.pi),
    adaptive=False,
    n=500,
    line_color=lambda uu: sp.cos(uu),
    show=False,
)
```

Parametric plots support `adaptive`, `depth`, `n`, `line_color`, and `label`. The docs state that parametric adaptive sampling defaults to `True`; set `adaptive=False` and specify `n` for uniform sampling. ([SymPy Documentation][1])

---

## 17.3 3D plotting: surfaces, parametric lines, parametric surfaces

## 17.3.1 Cartesian 3D surfaces: `plot3d`

```python id="zctau5"
plot3d(expr, (x, xmin, xmax), (y, ymin, ymax))
plot3d(expr1, expr2, (x, xmin, xmax), (y, ymin, ymax))
plot3d((expr1, (x, a1, b1), (y, c1, d1)),
       (expr2, (x, a2, b2), (y, c2, d2)))
```

`plot3d` plots functions in two variables. Single-plot form is `plot3d(expr, range_x, range_y)`, multiple plots can share ranges, and multiple plots with distinct ranges must specify ranges for each expression. If ranges are omitted, the default is `(-10, 10)`. ([SymPy Documentation][1])

```python id="6z005j"
p = plot3d(x*y, (x, -5, 5), (y, -5, 5), show=False)
```

## 17.3.2 3D parametric line

```python id="3az6va"
plot3d_parametric_line(expr_x, expr_y, expr_z, (u, umin, umax))
plot3d_parametric_line((expr_x1, expr_y1, expr_z1, range1),
                       (expr_x2, expr_y2, expr_z2, range2))
```

```python id="pojsje"
plot3d_parametric_line(
    sp.cos(u),
    sp.sin(u),
    u,
    (u, -5, 5),
    show=False,
)
```

The docs show `plot3d_parametric_line(cos(u), sin(u), u, (u, -5, 5))` returning a 3D parametric line series. ([SymPy Documentation][1])

## 17.3.3 3D parametric surface

```python id="2v6jgx"
plot3d_parametric_surface(
    expr_x,
    expr_y,
    expr_z,
    (u, umin, umax),
    (v, vmin, vmax),
)

plot3d_parametric_surface(
    (expr_x1, expr_y1, expr_z1, range_u1, range_v1),
    (expr_x2, expr_y2, expr_z2, range_u2, range_v2),
)
```

```python id="g86dvo"
plot3d_parametric_surface(
    sp.cos(u + v),
    sp.sin(u - v),
    u - v,
    (u, -5, 5),
    (v, -5, 5),
    n1=80,
    n2=80,
    show=False,
)
```

`plot3d_parametric_surface` uses `n1` and `n2` to set uniform sample counts along the `u` and `v` ranges; these replace deprecated `nb_of_points_u` and `nb_of_points_v`. ([SymPy Documentation][1])

Deployment rule:

```text id="ex0z1z"
3D surfaces:
  choose n/n1/n2 deliberately.
  expect numeric sampling cost.
  avoid huge symbolic expressions without lambdify/caching.
  explicit ranges mandatory for reproducible visualization.
```

---

## 17.4 Implicit, contour-like, and region plotting: `plot_implicit`

## 17.4.1 Syntax

```python id="rgnw67"
plot_implicit(expr)
plot_implicit(Eq(expr, 0), (x, xmin, xmax), (y, ymin, ymax))
plot_implicit(inequality, (x, xmin, xmax), (y, ymin, ymax))
plot_implicit(And(cond1, cond2), (x, xmin, xmax), (y, ymin, ymax))
plot_implicit(expr, x_var=x, y_var=y)
```

`plot_implicit(expr, x_var=None, y_var=None, adaptive=True, depth=0, n=300, line_color='blue', show=True, **kwargs)` plots implicit equations and inequalities. `expr` may be an equation, inequality, or Boolean region expression; if variables are omitted, the free symbols are assigned in sorted order. The docs show plotting `Eq(x**2 + y**2, 5)`, inequalities such as `y > x**2`, and Boolean conjunctions such as `And(y > x, y > -x)`. ([SymPy Documentation][1])

```python id="xk2voh"
p_circle = plot_implicit(
    Eq(x**2 + y**2, 4),
    (x, -3, 3),
    (y, -3, 3),
    show=False,
)

p_region = plot_implicit(
    And(y > x**2, y < 2),
    (x, -2, 2),
    (y, -1, 3),
    show=False,
)
```

## 17.4.2 Adaptive vs mesh-grid mode

```python id="myu7dj"
plot_implicit(Eq(x**2 + y**2, 5), (x, -5, 5), (y, -2, 2), adaptive=False, n=400)
plot_implicit(Eq(x**2 + y**2, 5), (x, -4, 4), (y, -4, 4), depth=2)
```

`plot_implicit` uses interval arithmetic by default; if interval arithmetic cannot plot the expression, it falls back to generating a contour with a mesh grid. Setting `adaptive=False` forces the mesh-grid path, and `n` controls mesh resolution; the series data for non-adaptive implicit plotting are NumPy arrays intended for Matplotlib `contour` or `contourf`. ([SymPy Documentation][1])

Deployment rule:

```text id="ce3fb8"
Use adaptive=True:
  implicit curves/regions where interval arithmetic works well.

Use adaptive=False,n=N:
  contour-like mesh-grid control.
  reproducible grid output.
  cases where adaptive interval plot misses thin features.

For single-variable implicit expressions:
  pass x_var=... or y_var=... explicitly.
```

---

## 17.5 `Plot` object lifecycle

## 17.5.1 `show=False`, `.show()`, `.save()`, `.close()`

```python id="b0d29n"
p = plot(sp.sin(x), (x, -sp.pi, sp.pi), show=False)

p.show()
p.save("sin_plot.png")
p.close()
```

`show=False` returns a `Plot` object without displaying it; `.show()` displays, `.save(path)` writes to a file, and `.close()` closes backend resources. The docs describe `Plot` as a backend container that stores data series plus figure-wide attributes, and a backend must implement `show`, `save`, and `close`. ([SymPy Documentation][1])

## 17.5.2 Append/extend

```python id="2hjjmw"
p1 = plot(x**2, (x, -5, 5), show=False)
p2 = plot(x, -x, (x, -5, 5), show=False)

p1.extend(p2)
p1.show()
```

`Plot.extend()` adds all series from another plot; the docs show `p1.extend(p2)` producing a single plot containing all series from both plots. ([SymPy Documentation][1])

## 17.5.3 Series indexing for per-series customization

```python id="5e2c73"
p = plot(x, x**2, (x, -5, 5), legend=True, show=False)

p[0].line_color = "red"
p[1].line_color = "blue"
p.show()
```

The docs note that when multiple plots are created, shared series arguments apply to all series, and per-series options should be set by indexing the returned `Plot` object. ([SymPy Documentation][1])

---

## 17.6 Backends and matplotlib integration

## 17.6.1 Backend choices

```python id="o5h6oy"
plot(sp.sin(x), backend="default")
plot(sp.sin(x), backend="matplotlib")
plot(sp.sin(x), backend="text")
```

The `Plot` constructor accepts `backend='default'`, `'matplotlib'`, `'text'`, or a subclass of `BaseBackend`. SymPy’s current plotting docs identify matplotlib as the primary backend and a text backend for 2D line plots without matplotlib. ([SymPy Documentation][1])

## 17.6.2 Access matplotlib figure/axes

```python id="8a9v2l"
p = plot(sp.cos(x), (x, -5, 5), backend="matplotlib", show=False)

fig = p._backend.fig
ax = p._backend.ax

ax.plot([0, 1, 2], [0, 1, -1], "*")
fig.savefig("augmented_plot.png")
```

The plotting docs explicitly recommend retrieving the matplotlib figure/axis from the backend for custom numerical data or full matplotlib customization rather than adding more SymPy plotting keyword arguments; the example accesses `p._backend.fig` and `p._backend.ax` and then calls `ax.plot(...)`. ([SymPy Documentation][1])

Deployment rule:

```text id="krma5r"
Use SymPy plot API:
  symbolic expression sampling
  quick interactive visual checks
  exact expression labels

Use Matplotlib directly:
  publication styling
  multiple custom axes
  annotations beyond SymPy options
  mixed symbolic and empirical/numeric data
  deterministic figure styling
```

## 17.6.3 Custom backend caution

A backend must know how to process SymPy series objects. The plotting docs state that current `Series` classes are “matplotlib-centric” and that custom backends are responsible for adapting numerical data and checking compatibility across SymPy releases. ([SymPy Documentation][1])

---

## 17.7 PlotGrid and layout

```python id="66aaqm"
p1 = plot(x, x**2, x**3, (x, -5, 5), show=False)
p2 = plot((x**2, (x, -6, 6)), (x, (x, -5, 5)), show=False)
p3 = plot3d(x*y, (x, -5, 5), (y, -5, 5), show=False)

grid = PlotGrid(1, 3, p1, p2, p3, show=False)
grid.show()
```

`PlotGrid(nrows, ncolumns, *args, show=True, size=None, **kwargs)` combines existing SymPy `Plot` objects into subplot layouts. The docs show vertical, horizontal, and grid arrangements using plots already created by `plot` and `plot3d`. ([SymPy Documentation][1])

Deployment rule:

```text id="7zp7t8"
Use PlotGrid:
  quick multi-panel symbolic visualization
  teaching notebooks
  side-by-side expression comparisons

Use matplotlib subplots directly:
  detailed layout, shared axes, custom colorbars, publication figures
```

---

## 17.8 ASCII/text plotting

```python id="4pu3vx"
from sympy.plotting import textplot

textplot(sp.sin(x)*x, 0, 15)
plot(sp.sin(x), (x, -5, 5), backend="text")
```

SymPy supports a `TextBackend` for 2D line plots and a `textplot(expr, a, b, W=55, H=21)` utility that prints a crude ASCII plot of a single-symbol expression over an interval. ([SymPy Documentation][1])

Use cases:

```text id="8r4h1f"
SSH/headless debugging
plain-text notebooks/logs
CI smoke checks
minimal environments without matplotlib
```

---

## 17.9 Plotting expressions vs numerical functions

## 17.9.1 Symbolic expression path

```python id="01fy1z"
expr = sp.sin(x) / x
plot(expr, (x, -20, 20), adaptive=True)
```

Use SymPy plotting when the input is a symbolic expression, equation, inequality, or Boolean region. SymPy creates series objects that numerically sample the expression and pass data to a backend. ([SymPy Documentation][1])

## 17.9.2 Numeric callable path

```python id="2o8z7z"
import numpy as np
import matplotlib.pyplot as plt

expr = sp.sin(x) / x
f = sp.lambdify(x, expr, modules="numpy")

xs = np.linspace(-20, 20, 2000)
ys = f(xs)

fig, ax = plt.subplots()
ax.plot(xs, ys)
```

Use direct NumPy/matplotlib when plotting large arrays, empirical data, simulation results, or production figures. SymPy’s plot layer is optimized for convenience and expression-to-plot workflows, not for large plotting pipelines or full matplotlib feature coverage. The official plotting docs themselves recommend accessing the matplotlib figure/axis for customization rather than extending SymPy plotting keywords. ([SymPy Documentation][1])

Deployment decision:

```text id="8zt17n"
SymPy plot:
  fast symbolic preview
  exact labels
  automatic sampling
  notebook exploration
  simple docs examples

NumPy + Matplotlib:
  large data
  reproducibility-critical grids
  custom styling
  publication figures
  animations
  integration with external numeric simulations
```

---

## 17.10 Interactive printing and notebooks

## 17.10.1 Printers overview

SymPy’s tutorial lists common printers: `str`, `srepr`, ASCII pretty printer, Unicode pretty printer, LaTeX, MathML, and Dot; code printers such as C, Fortran, JavaScript, Theano, and Python exist separately. ([SymPy Documentation][2])

```python id="ye6lci"
sp.sstr(expr)
sp.srepr(expr)
sp.pretty(expr)
sp.latex(expr)
sp.print_latex(expr)
sp.pprint(expr)
```

## 17.10.2 `init_printing`

```python id="3aqex5"
from sympy import init_printing

init_printing()
init_printing(use_unicode=True)
init_printing(use_latex="mathjax")
init_printing(use_latex=False)
init_printing(order="lex")
init_printing(num_columns=120)
```

`init_printing()` automatically enables the best printer available for the current environment. In IPython notebooks, it uses MathJax to render LaTeX; in IPython/regular consoles, it uses Unicode pretty printing when supported; in terminals without Unicode, it falls back to ASCII. The docs also state `use_latex=False` disables LaTeX rendering and `use_unicode=False` disables Unicode. ([SymPy Documentation][2])

`init_printing` supports options such as `pretty_print`, `order`, `use_unicode`, `use_latex`, `wrap_line`, `num_columns`, `latex_mode`, custom string/pretty/LaTeX printers, and `scale` for PNG/SVG LaTeX output. `use_latex` may be `True`, `False`, `None`, `'png'`, `'matplotlib'`, `'mathjax'`, or `'svg'`. ([SymPy Documentation][3])

## 17.10.3 `init_session`

```python id="21p9lg"
from sympy import init_session

init_session()
init_session(pretty_print=False)
init_session(use_unicode=True)
init_session(order="grevlex")
```

`init_session()` imports SymPy, creates common symbols, sets up plotting, and runs `init_printing()`. The tutorial positions it for interactive calculator-style sessions, not production modules. ([SymPy Documentation][2])

Deployment rule:

```text id="e1561r"
Use init_printing:
  notebooks, REPL, teaching, reports.

Use init_session:
  interactive sessions only.

Do not use init_session in libraries:
  wildcard imports, global symbols, environment mutation.

For generated docs:
  use latex(expr), pretty(expr), srepr(expr) explicitly.
```

---

## 17.11 Visualization best practices for exact symbolic expressions

## 17.11.1 Exact-to-numeric boundary

```python id="tiacnb"
expr = sp.simplify(sp.sin(x) / x)

# Keep exact symbolic form for algebra.
exact_label = sp.latex(expr)

# Numeric sampling boundary.
f = sp.lambdify(x, expr, modules="numpy")
```

Best-practice rule:

```text id="rfisiz"
Symbolic phase:
  exact expressions
  simplify/normalize
  assumptions/domains
  LaTeX labels

Numeric plot phase:
  explicit ranges
  explicit sample counts
  lambdified functions if using matplotlib directly
  handle singularities/discontinuities
```

## 17.11.2 Singularities and discontinuities

```python id="pgf429"
expr = 1 / (x - 1)

plot(expr, (x, -5, 5), adaptive=True, ylim=(-10, 10))
```

Guardrails:

```text id="oapiv0"
Before plotting:
  inspect singularities when possible.
  split intervals at singular points.
  set ylim/xlim.
  avoid connecting across poles if using direct matplotlib arrays.
```

Example split:

```python id="2esfvp"
plot(
    (1/(x - 1), (x, -5, 0.95)),
    (1/(x - 1), (x, 1.05, 5)),
    ylim=(-20, 20),
    show=False,
)
```

## 17.11.3 Piecewise / relational regions

```python id="v12na8"
pw = sp.Piecewise((x**2, x < 0), (sp.sin(x), True))
plot(pw, (x, -3, 3), adaptive=False, n=500)

plot_implicit(And(y > x**2, y < 2), (x, -2, 2), (y, -1, 3))
```

Use `plot_implicit` for inequalities and Boolean regions; the docs show region plotting and conjunction plotting with `And`. ([SymPy Documentation][1])

## 17.11.4 Reproducibility

```text id="aqy1re"
For reproducible figures:
  show=False
  backend="matplotlib"
  adaptive=False
  explicit n/n1/n2
  explicit ranges
  fixed xlim/ylim/zlim if relevant
  save(path)
  version-pin SymPy + Matplotlib
  avoid adaptive random midpoint sampling for snapshot tests
```

---

## 17.12 Deployment recipes

## Recipe A — deterministic 2D symbolic plot

```python id="eqi8qz"
def deterministic_plot_2d(expr, var, a, b, *, n=1000, path=None):
    p = plot(
        sp.sympify(expr),
        (var, a, b),
        adaptive=False,
        n=n,
        backend="matplotlib",
        show=False,
    )
    if path is not None:
        p.save(path)
    return p
```

## Recipe B — implicit region plot

```python id="j775bp"
def implicit_region_plot(condition, x_range, y_range, *, n=400, path=None):
    p = plot_implicit(
        condition,
        x_range,
        y_range,
        adaptive=False,
        n=n,
        backend="matplotlib",
        show=False,
    )
    if path:
        p.save(path)
    return p
```

## Recipe C — symbolic expression to matplotlib data

```python id="64uvgu"
def expression_samples(expr, var, a, b, *, n=1000, modules="numpy"):
    import numpy as np

    expr = sp.sympify(expr)
    f = sp.lambdify(var, expr, modules=modules)
    xs = np.linspace(float(a), float(b), n)
    ys = f(xs)
    return xs, ys
```

## Recipe D — split singularity-safe plot

```python id="sdhj1u"
def split_plot(expr, var, intervals, *, n=500, ylim=None):
    series = [
        (sp.sympify(expr), (var, a, b))
        for a, b in intervals
    ]
    kwargs = {
        "adaptive": False,
        "n": n,
        "show": False,
        "backend": "matplotlib",
    }
    if ylim is not None:
        kwargs["ylim"] = ylim
    return plot(*series, **kwargs)
```

## Recipe E — notebook setup

```python id="y3jg71"
def notebook_symbolic_display():
    sp.init_printing(use_latex="mathjax", use_unicode=True)
```

## Recipe F — custom matplotlib augmentation

```python id="cc87e6"
def augment_sympy_plot_with_points(expr, var, a, b, points, *, path=None):
    p = plot(expr, (var, a, b), backend="matplotlib", show=False)
    fig, ax = p._backend.fig, p._backend.ax

    xs, ys = zip(*points)
    ax.plot(xs, ys, "*")

    if path:
        fig.savefig(path)

    return p, fig, ax
```

---

## 17.13 Anti-pattern inventory

| Anti-pattern                                                 | Failure mode                                | Correct pattern                                         |
| ------------------------------------------------------------ | ------------------------------------------- | ------------------------------------------------------- |
| relying on default plot range                                | future/default drift, misleading view       | always pass `(x, a, b)`                                 |
| adaptive sampling in snapshot tests                          | slight plot differences                     | `adaptive=False, n=N`                                   |
| plotting exact expression with huge symbolic form directly   | slow lambdify/sampling                      | simplify/cse/lambdify manually                          |
| plotting across poles as one curve                           | misleading vertical lines                   | split intervals                                         |
| expecting SymPy plots to handle publication styling          | limited wrapper options                     | access matplotlib `fig, ax`                             |
| passing multivariate expression to `plot`                    | variable ambiguity                          | use `plot3d`, `plot_implicit`, or substitute            |
| using `init_session()` in libraries                          | global imports/symbols/environment mutation | `import sympy as sp`                                    |
| depending on `p._backend` in public library API              | private attribute stability risk            | use direct matplotlib for library-grade plotting        |
| using `plot_implicit` without variable ranges                | symbol-order/default-range ambiguity        | pass `(x,a,b),(y,c,d)`                                  |
| expecting `plot_implicit` to be true symbolic contour engine | numeric mesh/interval approximations        | verify with algebra/numeric sampling                    |
| using floats as exact labels                                 | approximate artifacts                       | keep exact expression for labels, numeric only for data |
| assuming text backend supports all plot types                | only limited 2D line plotting               | matplotlib for full plot support                        |

---

## 17.14 Testing matrix

```python id="9ksd4e"
def test_plot_object_returned():
    p = plot(x**2, (x, -1, 1), show=False)
    assert hasattr(p, "show")
    assert len(p._series) == 1

def test_deterministic_plot_series_count():
    p = plot(x, x**2, (x, -1, 1), adaptive=False, n=50, show=False)
    assert len(p._series) == 2

def test_implicit_plot_object():
    p = plot_implicit(Eq(x**2 + y**2, 1), (x, -2, 2), (y, -2, 2), show=False)
    assert hasattr(p, "show")

def test_parametric_plot_object():
    p = plot_parametric((cos(u), sin(u)), (u, 0, 2*pi), show=False)
    assert len(p._series) == 1

def test_latex_label():
    expr = sin(x)/x
    assert r"\sin" in sp.latex(expr)

def test_samples_shape():
    xs, ys = expression_samples(sin(x), x, 0, 1, n=10)
    assert len(xs) == 10
    assert len(ys) == 10
```

Coverage targets:

```text id="o8bcwk"
2D:
  single expression
  multiple expressions shared range
  multiple expressions distinct ranges
  adaptive=False deterministic sampling

Parametric:
  shared range
  per-series range
  line_color function

3D:
  cartesian surface
  parametric line
  parametric surface
  n/n1/n2 controls

Implicit:
  Eq
  inequality
  And/Or region
  adaptive=True
  adaptive=False,n=N
  single-variable x_var/y_var

Backends:
  matplotlib save
  text backend smoke test
  fig/ax augmentation

Printing:
  init_printing options
  latex(expr)
  pretty(expr)
  srepr(expr)
```

---

## 17.15 Minimal plotting/interactive harness

```python id="r6vvc4"
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Sequence

import sympy as sp

from sympy.plotting import (
    plot,
    plot_parametric,
    plot_implicit,
    plot3d,
    plot3d_parametric_line,
    plot3d_parametric_surface,
    PlotGrid,
)


@dataclass(frozen=True)
class PlotAudit:
    plot: Any
    series_count: int
    backend: str
    title: Any
    xlabel: Any
    ylabel: Any
    zlabel: Any | None


def audit_plot(p: Any) -> PlotAudit:
    return PlotAudit(
        plot=p,
        series_count=len(getattr(p, "_series", [])),
        backend=type(getattr(p, "_backend", None)).__name__ if getattr(p, "_backend", None) else "uninitialized",
        title=getattr(p, "title", None),
        xlabel=getattr(p, "xlabel", None),
        ylabel=getattr(p, "ylabel", None),
        zlabel=getattr(p, "zlabel", None),
    )


def symbolic_plot_2d(
    exprs: Any | Sequence[Any],
    var: sp.Symbol,
    a: Any,
    b: Any,
    *,
    adaptive: bool = False,
    n: int = 1000,
    show: bool = False,
    backend: str = "matplotlib",
    **kwargs,
):
    if not isinstance(exprs, (list, tuple)):
        exprs = [exprs]

    args = [sp.sympify(e) for e in exprs] + [(var, a, b)]

    return plot(
        *args,
        adaptive=adaptive,
        n=n,
        show=show,
        backend=backend,
        **kwargs,
    )


def symbolic_plot_parametric_2d(
    expr_x: Any,
    expr_y: Any,
    param: sp.Symbol,
    a: Any,
    b: Any,
    *,
    adaptive: bool = False,
    n: int = 1000,
    show: bool = False,
    backend: str = "matplotlib",
    **kwargs,
):
    return plot_parametric(
        (sp.sympify(expr_x), sp.sympify(expr_y)),
        (param, a, b),
        adaptive=adaptive,
        n=n,
        show=show,
        backend=backend,
        **kwargs,
    )


def symbolic_plot_surface_3d(
    expr: Any,
    xvar: sp.Symbol,
    xa: Any,
    xb: Any,
    yvar: sp.Symbol,
    ya: Any,
    yb: Any,
    *,
    show: bool = False,
    backend: str = "matplotlib",
    **kwargs,
):
    return plot3d(
        sp.sympify(expr),
        (xvar, xa, xb),
        (yvar, ya, yb),
        show=show,
        backend=backend,
        **kwargs,
    )


def symbolic_plot_parametric_line_3d(
    expr_x: Any,
    expr_y: Any,
    expr_z: Any,
    param: sp.Symbol,
    a: Any,
    b: Any,
    *,
    show: bool = False,
    backend: str = "matplotlib",
    **kwargs,
):
    return plot3d_parametric_line(
        sp.sympify(expr_x),
        sp.sympify(expr_y),
        sp.sympify(expr_z),
        (param, a, b),
        show=show,
        backend=backend,
        **kwargs,
    )


def symbolic_plot_parametric_surface_3d(
    expr_x: Any,
    expr_y: Any,
    expr_z: Any,
    u: sp.Symbol,
    ua: Any,
    ub: Any,
    v: sp.Symbol,
    va: Any,
    vb: Any,
    *,
    n1: int = 100,
    n2: int = 100,
    show: bool = False,
    backend: str = "matplotlib",
    **kwargs,
):
    return plot3d_parametric_surface(
        sp.sympify(expr_x),
        sp.sympify(expr_y),
        sp.sympify(expr_z),
        (u, ua, ub),
        (v, va, vb),
        n1=n1,
        n2=n2,
        show=show,
        backend=backend,
        **kwargs,
    )


def symbolic_plot_implicit(
    condition: Any,
    xrange: tuple[sp.Symbol, Any, Any],
    yrange: tuple[sp.Symbol, Any, Any],
    *,
    adaptive: bool = False,
    n: int = 400,
    show: bool = False,
    backend: str = "matplotlib",
    **kwargs,
):
    return plot_implicit(
        condition,
        xrange,
        yrange,
        adaptive=adaptive,
        n=n,
        show=show,
        backend=backend,
        **kwargs,
    )


def save_plot(p: Any, path: str):
    p.save(path)
    return path


def matplotlib_axes_from_plot(p: Any):
    if getattr(p, "_backend", None) is None:
        p.show()
    backend = p._backend
    return backend.fig, backend.ax


def augment_with_points(p: Any, points: Iterable[tuple[float, float]], *, marker: str = "*"):
    fig, ax = matplotlib_axes_from_plot(p)
    xs, ys = zip(*points)
    ax.plot(xs, ys, marker)
    return fig, ax


def expression_samples(
    expr: Any,
    var: sp.Symbol,
    a: Any,
    b: Any,
    *,
    n: int = 1000,
    modules: str = "numpy",
):
    import numpy as np

    expr = sp.sympify(expr)
    f = sp.lambdify(var, expr, modules=modules)

    xs = np.linspace(float(a), float(b), n)
    ys = f(xs)

    return xs, ys


def split_intervals_around_points(a: float, b: float, excluded: Sequence[float], *, eps: float = 1e-6):
    points = [p for p in sorted(excluded) if a < p < b]
    intervals = []
    left = a
    for p in points:
        intervals.append((left, p - eps))
        left = p + eps
    intervals.append((left, b))
    return intervals


def plot_split_expression(
    expr: Any,
    var: sp.Symbol,
    intervals: Sequence[tuple[Any, Any]],
    *,
    adaptive: bool = False,
    n: int = 500,
    show: bool = False,
    backend: str = "matplotlib",
    **kwargs,
):
    series = [(sp.sympify(expr), (var, a, b)) for a, b in intervals]
    return plot(
        *series,
        adaptive=adaptive,
        n=n,
        show=show,
        backend=backend,
        **kwargs,
    )


def plot_grid(nrows: int, ncols: int, *plots: Any, show: bool = False, **kwargs):
    return PlotGrid(nrows, ncols, *plots, show=show, **kwargs)


def setup_notebook_printing(
    *,
    use_latex: str | bool | None = "mathjax",
    use_unicode: bool | None = True,
    order: str | None = "lex",
    num_columns: int | None = None,
):
    sp.init_printing(
        use_latex=use_latex,
        use_unicode=use_unicode,
        order=order,
        num_columns=num_columns,
    )


def expression_renderings(expr: Any) -> dict[str, str]:
    expr = sp.sympify(expr)
    return {
        "str": str(expr),
        "srepr": sp.srepr(expr),
        "pretty": sp.pretty(expr),
        "latex": sp.latex(expr),
    }


def visualization_policy() -> dict[str, str]:
    return {
        "symbolic_preview": "use SymPy plot with explicit ranges and show=False",
        "reproducible_docs": "use adaptive=False, fixed n, backend='matplotlib', save(path)",
        "publication": "lambdify + NumPy + Matplotlib directly or retrieve fig/ax",
        "implicit_regions": "use plot_implicit with explicit ranges; adaptive=False for mesh control",
        "interactive_notebook": "init_printing(use_latex='mathjax') and exact symbolic labels",
        "headless": "use backend='matplotlib' with noninteractive Matplotlib backend, or textplot for 2D smoke checks",
    }
```

This harness encodes plotting-phase discipline: explicit ranges, deterministic sampling, `show=False` object workflows, backend choice, matplotlib augmentation, implicit region plotting, parametric/3D wrappers, split-interval plotting near singularities, sample extraction for direct matplotlib use, PlotGrid layout, notebook printing setup, and stable expression renderings.

[1]: https://docs.sympy.org/latest/modules/plotting.html "Plotting - SymPy 1.14.0 documentation"
[2]: https://docs.sympy.org/latest/tutorials/intro-tutorial/printing.html "Printing - SymPy 1.14.0 documentation"
[3]: https://docs.sympy.org/latest/modules/interactive.html "Interactive - SymPy 1.14.0 documentation"


# 18) Printing, parsing, and external representation — agent-ready deep dive

Continuing the same advanced technical-doc pattern as the supplied reference artifact. 

## 18.0 External-representation taxonomy

SymPy expressions are immutable symbolic object graphs. External representations are **views**, **serialization artifacts**, or **target-language projections**, not the expression itself. Use the representation that matches the consumer: human-readable display, structural debugging, LaTeX document output, parser input, cache key, API payload, generated code, solver input, or notebook rendering. SymPy’s printing docs define the printing system as a dispatcher that passes an expression to a printer, which either lets the object print itself, selects the best printer method, or falls back to an empty/default printer. ([SymPy Documentation][1])

```python id="s8nhgq"
import sympy as sp

x, y, z = sp.symbols("x y z")
expr = sp.Integral(sp.sqrt(1/x), x)
```

Representation map:

```text id="c84giq"
human display:
  str(expr), pprint(expr), pretty(expr), latex(expr)

structural debug:
  srepr(expr), dotprint(expr)

document / notebook:
  latex(expr), init_printing(use_latex="mathjax"), MathML

target-language code:
  ccode, fcode, pycode, octave_code, jscode, rust_code, etc.

runtime numeric callable:
  lambdify, autowrap, ufuncify

string input:
  parse_expr with explicit dictionaries and transformations

internal canonical object:
  SymPy Expr / Matrix / Set / Boolean / Poly object itself

cache / API payload:
  explicit metadata + structural string or controlled custom schema
```

---

## 18.1 String and structural representations

## 18.1.1 `str(expr)`

```python id="kebhsz"
s = str(expr)
print(expr)
```

`str(expr)` returns a readable string form that usually resembles valid Python/SymPy input; `print(expr)` uses this form. It is useful for logs and lightweight human diagnostics, but not ideal as a stable machine serialization format. The printing tutorial states that the `str()` form is designed to be readable and copy/pasteable in Python-like syntax. ([SymPy Documentation][2])

```python id="wtv4g6"
str(sp.Integral(sp.sqrt(1/x), x))
# 'Integral(sqrt(1/x), x)'
```

Deployment rule:

```text id="cytmsx"
Use str:
  logs
  error messages
  simple CLI output
  human-facing plain text

Avoid str:
  cache keys needing structural exactness
  round-trip persistence
  expression equality
  security-sensitive parsing
```

---

## 18.1.2 `repr(expr)`

```python id="08p7y0"
repr(expr)
```

SymPy’s ordinary Python `repr()` is not its main structural representation. The tutorial explicitly notes SymPy does not use Python’s builtin `repr()` as the main repr-style printer because `repr()` is implicitly used by Python containers and full structural output would be too verbose in contexts such as lists returned by `solve()`. ([SymPy Documentation][2])

Deployment rule:

```text id="wgg2a8"
Use repr:
  Python debugging only.

Use srepr:
  structural SymPy expression-tree debug.
```

---

## 18.1.3 `srepr(expr)`

```python id="utcrpz"
sp.srepr(expr)
```

`srepr(expr)` shows the exact internal constructor-tree structure of a SymPy expression. The tutorial describes it as useful for understanding how an expression is built internally. ([SymPy Documentation][2])

```python id="krca74"
sp.srepr(sp.Integral(sp.sqrt(1/x), x))
# "Integral(Pow(Pow(Symbol('x'), Integer(-1)), Rational(1, 2)), Tuple(Symbol('x')))"
```

Use cases:

```text id="w71y72"
debug structural mismatch
detect Float vs Rational
detect Symbol assumptions/name mismatch indirectly
inspect Add/Mul/Pow canonicalization
snapshot internal expression tree for regression tests
build explainability traces for LLM agents
```

Guardrails:

```text id="hwn9ti"
srepr is verbose.
srepr is SymPy-specific.
srepr is not a security sandbox.
srepr should be version-pinned if persisted long-term.
```

---

## 18.2 Pretty printing: `pprint`, `pretty`

## 18.2.1 `pprint(expr, use_unicode=...)`

```python id="im4zcg"
sp.pprint(expr)
sp.pprint(expr, use_unicode=False)
sp.pprint(expr, use_unicode=True)
```

`pprint()` prints a two-dimensional pretty representation directly to the output stream. ASCII and Unicode pretty printers are both exposed through `pprint`; Unicode is used automatically when supported, and `use_unicode=True/False` can force behavior. ([SymPy Documentation][2])

```python id="m7clj6"
sp.pprint(sp.Integral(sp.sqrt(1/x), x), use_unicode=False)
sp.pprint(sp.Integral(sp.sqrt(1/x), x), use_unicode=True)
```

## 18.2.2 `pretty(expr, use_unicode=...)`

```python id="fvxvgk"
text = sp.pretty(expr)
text_ascii = sp.pretty(expr, use_unicode=False)
```

`pretty()` returns the pretty-printed string instead of printing it. The tutorial explicitly distinguishes `pprint()` as screen output and `pretty()` as string-returning output. ([SymPy Documentation][2])

Deployment rule:

```text id="x439cr"
Use pprint:
  REPL output
  console demos

Use pretty:
  logs, API response strings, text artifacts, test snapshots

Use use_unicode=False:
  ASCII-only logs, legacy terminals, deterministic plain-text artifacts
```

---

## 18.3 LaTeX, MathML, Dot, notebook rendering

## 18.3.1 `latex(expr)`

```python id="r3sg3v"
tex = sp.latex(expr)
print(tex)
```

`latex(expr)` returns a LaTeX string. The printing tutorial shows `latex(Integral(sqrt(1/x), x))` producing `\int \sqrt{\frac{1}{x}}\, dx`; it also notes `latex()` has many formatting options. ([SymPy Documentation][2])

```python id="zys59c"
sp.latex(sp.Integral(sp.sqrt(1/x), x))
# '\\int \\sqrt{\\frac{1}{x}}\\, dx'
```

Common options:

```python id="hdm9te"
sp.latex(expr, mode="plain")
sp.latex(expr, mode="inline")
sp.latex(expr, mode="equation")
sp.latex(expr, mode="equation*", fold_short_frac=True)
sp.latex(expr, symbol_names={x: r"x_{\mathrm{state}}"})
```

Deployment rule:

```text id="2q819d"
Use latex:
  reports
  notebooks
  generated docs
  explanation artifacts
  human-facing math output

Do not use latex:
  expression storage
  parser round-trip source
  computational IR
```

---

## 18.3.2 MathML

```python id="7ko91w"
from sympy.printing.mathml import mathml, print_mathml

xml = mathml(expr)
print_mathml(expr)
```

The tutorial documents `print_mathml()` as the printer that prints MathML and `mathml()` as the string-returning equivalent. ([SymPy Documentation][2])

Use cases:

```text id="vwxfri"
web math rendering
XML-based interchange
accessibility pipelines
math-document systems
```

---

## 18.3.3 Dot / Graphviz

```python id="t7bjmt"
from sympy.printing.dot import dotprint

dot = dotprint(x + 2)
```

`dotprint()` emits Graphviz Dot output for expression trees; the tutorial shows a graph representation where an `Add` node points to `Integer(2)` and `Symbol('x')`. ([SymPy Documentation][2])

Use cases:

```text id="4w4bsq"
visualize expression trees
debug nested Add/Mul/Pow structure
teach expression-tree semantics
inspect generated formula complexity
```

---

## 18.3.4 `init_printing`

```python id="n46kp4"
from sympy import init_printing

init_printing()
init_printing(use_unicode=True)
init_printing(use_latex="mathjax")
init_printing(use_latex=False)
```

`init_printing()` enables the best available interactive printer. In Jupyter/IPython notebooks it uses MathJax for LaTeX rendering; in IPython/regular consoles it uses Unicode pretty printing when possible; in terminals without Unicode it falls back to ASCII. `use_latex=False` disables LaTeX rendering, and `use_unicode=False` disables Unicode. ([SymPy Documentation][2])

Deployment rule:

```text id="aghywm"
Use init_printing:
  notebooks
  REPL
  teaching
  exploratory sessions

Avoid init_printing side effects:
  library modules
  CLI tools where output must be controlled
  batch jobs
```

---

## 18.4 Printer internals and custom printing

## 18.4.1 Printer method resolution

Printer dispatch order:

```text id="7rrwpy"
1. object-specific print method, e.g. _latex, _sympystr
2. best matching printer method, e.g. _print_Add
3. empty/default printer fallback
```

The printing guide states that a printer’s `.doprint(expr)` looks for an object-specific method named by the printer’s `printmethod` attribute; for example, `StrPrinter` calls `_sympystr` and `LatexPrinter` calls `_latex`. ([SymPy Documentation][1])

## 18.4.2 Custom LaTeX hook

```python id="6rtvbv"
class MyFunction(sp.Function):
    def _latex(self, printer):
        x, = self.args
        return r"\operatorname{MyFunction}\left(%s\right)" % printer._print(x)
```

Agent rules:

```text id="niy8ip"
Inside custom printer hooks:
  use printer._print(arg)
  do not use str(arg)
  do not instantiate a new printer recursively
  keep output backend-specific
```

Use object methods for a few custom classes; use custom printer subclasses for larger libraries with many custom output rules.

---

## 18.5 Code printers: target-language projection

## 18.5.1 Code-generation abstraction stack

SymPy’s code-generation docs define four levels: expression → code printers → code generators → autowrap. Code printers translate SymPy objects into language code, code generators produce routines/files, and `autowrap` can compile/import a numerical function into the current Python session. The docs also state that code printers do **not** optimize code automatically; e.g. C printing may emit `pow(x, 2)` instead of `x*x`, and CSE is not automatically applied anywhere in the chain. ([SymPy Documentation][3])

```text id="9fe8bc"
Expr
  → ccode/fcode/pycode/jscode/octave_code/rust_code/...
  → codegen
  → autowrap / ufuncify
```

Deployment rule:

```text id="6ebfqi"
Before code printing:
  simplify target form
  cancel/together rational expressions
  trigsimp/powsimp where valid
  apply cse if repeated subexpressions matter
  ensure Piecewise has default (expr, True)
  ensure unsupported functions are mapped
```

---

## 18.5.2 C code: `ccode`

```python id="rly0we"
from sympy import ccode
from sympy.codegen.ast import Assignment

ccode(sp.sin(x))
ccode(sp.sin(x), assign_to="s")
ccode(Assignment(x, y + 1))
ccode(expr, standard="C99")
```

`ccode(expr, assign_to=None, standard='c99', **settings)` converts a SymPy expression to C code. `assign_to` may be a string, `Symbol`, `MatrixSymbol`, or `Indexed`; `user_functions` maps SymPy functions to custom C functions; `human=False` returns `(symbols_to_declare, not_supported_functions, code_text)`; and `contract=True` lets `Indexed` expressions generate loops. ([SymPy Documentation][1])

```python id="ich38e"
expr = (sp.Rational(-1, 2) * z * x**2 / y)

ccode(expr)
ccode(expr, assign_to="out")
```

Custom function mapping:

```python id="hkl4jy"
func = sp.Function("func")
custom_functions = {
    "Abs": [
        (lambda arg: not arg.is_integer, "fabs"),
        (lambda arg: arg.is_integer, "ABS"),
    ],
    "func": "f",
}

ccode(func(sp.Abs(x)), user_functions=custom_functions)
```

Piecewise rule:

```python id="dihgr3"
pw = sp.Piecewise((x + 1, x > 0), (x, True))
print(ccode(pw, assign_to="tau"))
```

`Piecewise` is converted into conditionals; if no default `(expr, True)` branch exists, the printer raises to prevent generating code that may not evaluate. ([SymPy Documentation][3])

---

## 18.5.3 Fortran: `fcode`

```python id="xhs6k1"
from sympy import fcode

fcode(sp.sin(x))
fcode(sp.sin(x), assign_to="s")
fcode(1 - sp.gamma(x)**2, strict=False)
fcode(1 - sp.gamma(x)**2, allow_unknown_functions=True)
fcode(expr, human=False)
```

Fortran printing supports strict handling of unsupported functions. Without `user_functions`, unsupported functions can raise; `strict=False` emits comments about unsupported functions, `allow_unknown_functions=True` emits the unknown function call, and `human=False` returns a tuple with declarations, unsupported functions, and code text. ([SymPy Documentation][1])

Deployment rule:

```text id="f1prx6"
Use strict=True/default:
  fail fast on unsupported Fortran output.

Use strict=False:
  human-inspection artifact with unsupported-function comments.

Use allow_unknown_functions=True:
  external library supplies those functions.

Use human=False:
  downstream source-code generator needs structured metadata.
```

---

## 18.5.4 Python, mpmath, NumPy/SciPy printers

```python id="cxqsr5"
from sympy import pycode

pycode(sp.tan(x) + 1)
pycode(sp.tan(x) + 1, fully_qualified_modules=True)
```

`pycode(expr)` converts an expression to Python code, with `fully_qualified_modules=True` controlling whether functions appear as `math.sin`/`math.tan` versus unqualified names. The printing docs identify Python code printers for plain Python as well as NumPy/SciPy-enabled code and mpmath precision-oriented code. ([SymPy Documentation][1])

Deployment rule:

```text id="f0par3"
Use pycode:
  textual Python source emission.

Use lambdify:
  executable Python callable generation.

Use NumPy/SciPy code paths:
  array numeric backends; usually via lambdify, not manual string eval.
```

---

## 18.5.5 JavaScript: `jscode`

```python id="4p5423"
from sympy import jscode

jscode(sp.sin(x))
jscode(sp.sin(x), assign_to="s")
jscode(sp.Piecewise((x + 1, x > 0), (x, True)), assign_to="tau")
```

`jscode(expr, assign_to=None, **settings)` converts expressions to JavaScript code. Known functions map to `Math.*`; `user_functions`, `human=False`, and `contract=True/False` are supported; `Piecewise` converts to conditionals, and missing default branches raise. The docs show `jscode((2*tau)**Rational(7, 2)) -> '8*Math.sqrt(2)*Math.pow(tau, 7/2)'` and loop-generation support for `Indexed`. ([SymPy Documentation][1])

Deployment rule:

```text id="eu3qvv"
Use jscode for:
  browser/server JS formula emission
  educational web tools
  simple numeric kernels

Guard:
  unsupported special functions need user_functions
  JavaScript number model is double precision
  Matrix assignment has specific output conventions
```

---

## 18.5.6 Octave/Matlab: `octave_code`

```python id="v0kv2p"
from sympy import octave_code

octave_code(sp.sin(x).series(x).removeO())
octave_code(sp.sin(sp.pi*x*y), assign_to="s")
```

`octave_code` emits Octave/Matlab-style code. The docs state elementwise operations are used by default between scalar symbols because vectorized code is common in Octave; `MatrixSymbol` is used when matrix products/powers are intended. Matrices and `Piecewise` are supported; `Piecewise` defaults to logical masks unless `inline=False` requests conditionals, and unsupported/missing default branches can raise. ([SymPy Documentation][1])

```python id="7x54d2"
A = sp.MatrixSymbol("A", 3, 3)
octave_code(3*sp.pi*A**3)
```

Deployment rule:

```text id="dyw7ng"
Use MatrixSymbol to force matrix algebra.
Expect Symbol multiplication to become elementwise `.*`.
Use HadamardProduct for explicit componentwise matrix multiplication.
```

---

## 18.5.7 Rust: `rust_code`

```python id="ezyq7g"
from sympy import rust_code

rust_code(sp.sin(x), assign_to="s")
rust_code(sp.Piecewise((x + 1, x > 0), (x, True)), assign_to="tau")
```

`rust_code` emits Rust expressions/statements. The docs show `sin(x)` printing as `x.sin()`, `Piecewise` printing as `if` expressions when assigned, loop support for `Indexed`, and matrix assignment support when a same-shaped `MatrixSymbol` is supplied. ([SymPy Documentation][1])

Deployment rule:

```text id="dg88n7"
Use rust_code for:
  scalar kernels
  Rust numeric source emission
  educational formula exports

Guard:
  map custom functions with user_functions
  inspect numeric literal suffixes and powi/powf output
  verify generated code under rustc/clippy/tests
```

---

## 18.5.8 SMT-LIB printer

```python id="22pwac"
from sympy.printing.smtlib import smtlib_code

smtlib_code(x > 0)
smtlib_code([x > 0, y < 2], auto_assert=True)
```

`smtlib_code(expr, auto_assert=True, auto_declare=True, ...)` emits SMT-LIB S-expressions/declarations/assertions and accepts symbol/function/type mapping dictionaries. The docs define known function/type mappings and options such as `symbol_table`, `known_types`, `known_functions`, and `precision`. ([SymPy Documentation][1])

Deployment rule:

```text id="nu447c"
Use SMT-LIB output for:
  solver constraints
  real/integer/boolean formula export

Guard:
  pass symbol_table for stable types
  inspect unsupported functions
  decide auto_assert/auto_declare explicitly
```

---

## 18.5.9 Codegen rewrites and optimizations

```python id="54qz1s"
from sympy.codegen.rewriting import optimize, optims_c99

optimized = optimize(3*sp.exp(2*x) - 3, optims_c99)
# 3*expm1(2*x)
```

The codegen rewriting module provides optimizations such as `expm1`, `log1p`, `exp2`, and `log2` rewrites for target languages that support numerically superior functions. The docs note such rewrites can improve precision, e.g. using `expm1(x)` instead of `exp(x)-1` to avoid catastrophic cancellation near zero. ([SymPy Documentation][3])

Deployment rule:

```text id="06pff3"
Before target code output:
  apply symbolic simplification
  apply cse
  apply target-specific rewrites
  then print

Do not expect code printers to optimize.
```

---

## 18.6 Parsing strings

## 18.6.1 `sympify`

```python id="3xqa3n"
sp.sympify(2)
sp.sympify(2.0)
sp.sympify("x**2 + 1")
sp.sympify("0.1", rational=True)
sp.sympify("x^y", convert_xor=True)
sp.sympify("2**2 / 3 + 5", evaluate=False)
sp.sympify(obj, strict=True)
```

`sympify()` converts Python objects into SymPy objects: ints to `Integer`, floats to `Float`, strings to parsed expressions, containers recursively, and objects with `_sympy_` conversion hooks. It uses `eval` for string parsing and should not be used on unsanitized input. `strict=True` only allows explicitly defined conversions and disables deprecated fallback-to-string behavior. `rational` and `convert_xor` apply only for string input. ([SymPy Documentation][4])

Important behaviors:

```python id="ip3q2l"
sp.sympify("2x+1")
# SympifyError; use parse_expr with transformations

sp.sympify("0.1", rational=False)
# 0.1

sp.sympify("0.1", rational=True)
# 1/10

sp.sympify("2**2 / 3 + 5", evaluate=False)
# 2**2/3 + 5
```

Deployment rule:

```text id="ht2efk"
Use sympify:
  API boundary coercion of trusted Python objects
  int/float/Decimal/list/tuple conversion
  objects implementing _sympy_

Do not use sympify on untrusted strings.
Do not use S("x")/sympify("x") just to create symbols.
```

The best-practices docs explicitly warn against using strings as inputs to ordinary SymPy functions and against `S()`/string parsing merely to create symbols, because automatic parsing can hide typos, lose assumptions, and silently create different symbols. ([SymPy Documentation][5])

---

## 18.6.2 `parse_expr`

```python id="noofvn"
from sympy.parsing.sympy_parser import parse_expr

parse_expr("1/2")
parse_expr("2*x + 1", local_dict={"x": x})
parse_expr("2**3", evaluate=False)
```

`parse_expr(s, local_dict=None, transformations=..., global_dict=None, evaluate=True)` converts a string into a SymPy expression. It also uses `eval` and should not be used on unsanitized input. `local_dict` supplies known symbols/functions; `global_dict` defaults to `from sympy import *`; `transformations` modifies token streams before evaluation; and `evaluate=False` suppresses some automatic simplification and preserves argument order. ([SymPy Documentation][6])

```python id="vydgoc"
a = parse_expr("1 + x", local_dict={"x": x}, evaluate=False)
b = parse_expr("x + 1", local_dict={"x": x}, evaluate=False)

a == b       # False
a.args       # (1, x)
b.args       # (x, 1)
```

Security rule:

```text id="4gex5s"
parse_expr is not a sandbox.
sympify is not a sandbox.
Both use eval for strings.
Never parse untrusted user strings without a separate sandbox/security layer.
```

Both `parse_expr` and `sympify` docs carry explicit warnings that they use `eval` and should not be used on unsanitized input. ([SymPy Documentation][6])

---

## 18.6.3 Transformations

```python id="9p0la6"
from sympy.parsing.sympy_parser import (
    parse_expr,
    standard_transformations,
    implicit_multiplication_application,
    implicit_multiplication,
    implicit_application,
    convert_xor,
    rationalize,
    T,
)

transformations = standard_transformations + (implicit_multiplication_application,)
parse_expr("2x", transformations=transformations)

parse_expr(".3x", transformations=T[:])
parse_expr(".3x", transformations="all")
parse_expr("2x", transformations="implicit")
```

The parsing docs list transformations: `lambda_notation`, `auto_symbol`, `repeated_decimals`, `auto_number`, `factorial_notation`, `implicit_multiplication_application`, `convert_xor`, `implicit_application`, `implicit_multiplication`, `convert_equals_signs`, `function_exponentiation`, and `rationalize`. `T` lets callers select transformations by index/slice; strings `"implicit"` and `"all"` are convenience selectors. ([SymPy Documentation][6])

Examples:

```python id="wz7cc5"
parse_expr("2x", transformations=T[:5])
# SyntaxError

parse_expr("2x", transformations=T[:6])
# 2*x

parse_expr(".3", transformations=T[3, 11])
# 3/10

parse_expr(".3x", transformations="all")
# 3*x/10
```

Deployment rule:

```text id="7fvqhj"
For strict Python-like input:
  standard_transformations

For math-like user input:
  standard_transformations + implicit_multiplication_application

For formula-recovery / decimal exactness:
  include rationalize

For source-faithful AST:
  evaluate=False

Always:
  pass local_dict for intended symbols with assumptions.
  avoid global from-sympy wildcard exposure when possible.
```

---

## 18.6.4 Symbol-assumption preservation when parsing

Bad:

```python id="l5940i"
z = sp.Symbol("z", positive=True)
sp.diff("z**2", z)
# can silently use a distinct parsed Symbol('z') with different assumptions/name identity
```

Good:

```python id="63z84f"
z = sp.Symbol("z", positive=True)
expr = parse_expr("z**2", local_dict={"z": z})
sp.diff(expr, z)
```

SymPy’s best-practices docs highlight this exact class of bug: parsing strings creates symbols without the caller’s assumptions unless the correct symbol is passed into the parser’s dictionary, and this can silently yield wrong results rather than errors. ([SymPy Documentation][5])

---

## 18.7 Avoiding string manipulation of expressions

Do not use regex/string replacement as symbolic algebra. SymPy’s best-practices docs say to create expressions explicitly using symbols and SymPy functions, parse strings early only when unavoidable, then manipulate symbolic objects from that point onward; support for accidental string inputs in general functions may go away in a future version. ([SymPy Documentation][5])

Bad:

```python id="dojvpz"
expr_s = "sin(x + y)"
expr_s = expr_s.replace("sin", "cos")
```

Good:

```python id="g89cgx"
expr = sp.sin(x + y)
expr = expr.xreplace({sp.sin(x + y): sp.cos(x + y)})
expr = expr.replace(sp.sin, sp.cos)
```

Bad:

```python id="0w4rzo"
sp.expand("(x**2 + x)/x")
```

Good:

```python id="7e7joq"
expr = (x**2 + x)/x
sp.expand(expr)
```

---

## 18.8 Serialization strategies

## 18.8.1 Strategy matrix

| Consumer                       | Representation                          | Notes                                  |
| ------------------------------ | --------------------------------------- | -------------------------------------- |
| human log                      | `str(expr)`                             | readable, not structural               |
| text report                    | `pretty(expr)`, `latex(expr)`           | display only                           |
| notebook                       | `init_printing`, `latex`                | environment-dependent rendering        |
| structural debugging           | `srepr(expr)`                           | verbose, SymPy-specific                |
| expression graph visualization | `dotprint(expr)`                        | Graphviz Dot                           |
| generated source               | `ccode`, `fcode`, `jscode`, etc.        | target-language, not round-trip SymPy  |
| numeric runtime                | `lambdify`, `autowrap`, `ufuncify`      | callable, not textual IR               |
| API/cache artifact             | custom schema + metadata                | version, assumptions, symbols, domains |
| persisted exact object         | pickle/joblib with version pin          | Python/SymPy-version coupling          |
| parsed user input              | `parse_expr` with explicit dictionaries | trusted/sandboxed only                 |

## 18.8.2 Structural metadata payload

```python id="20hvzm"
def expression_payload(expr: sp.Basic) -> dict[str, object]:
    expr = sp.sympify(expr)
    return {
        "sympy_version": sp.__version__,
        "type": type(expr).__name__,
        "srepr": sp.srepr(expr),
        "str": str(expr),
        "latex": sp.latex(expr),
        "free_symbols": sorted(str(s) for s in expr.free_symbols),
        "assumptions": {
            str(s): getattr(s, "assumptions0", {})
            for s in expr.free_symbols
            if isinstance(s, sp.Symbol)
        },
    }
```

Deployment rule:

```text id="snl32k"
Persist:
  sympy_version
  srepr or controlled schema
  free symbol names
  assumptions
  domain assumptions
  generator ordering for Poly
  target backend for code

Do not persist:
  bare str(expr) as only source of truth
  LaTeX as computational IR
  code-printer output as source SymPy expression
```

## 18.8.3 API payload with symbol registry

```python id="ncfky3"
def make_symbol_registry(symbols: list[sp.Symbol]) -> dict[str, dict[str, object]]:
    return {
        str(s): {
            "name": s.name,
            "assumptions0": dict(s.assumptions0),
        }
        for s in symbols
    }
```

Round-trip parsing pattern for trusted strings:

```python id="7a7193"
def parse_with_registry(expr_text: str, registry: dict[str, sp.Symbol]) -> sp.Expr:
    return parse_expr(
        expr_text,
        local_dict=registry,
        global_dict={"Symbol": sp.Symbol},
        transformations=standard_transformations,
        evaluate=True,
    )
```

Guardrail:

```text id="82fv1s"
For public APIs:
  treat string formulas as untrusted.
  parse in a sandbox or reject.
  prefer structured JSON over arbitrary expression strings.
```

---

## 18.9 Custom object conversion into SymPy

## 18.9.1 `_sympy_` hook

```python id="6jvuxn"
class MyScalar:
    def __init__(self, value):
        self.value = value

    def _sympy_(self):
        return sp.Rational(self.value)

sp.sympify(MyScalar(3))
```

`sympify()` supports conversion of custom objects by defining a `_sympy_` method; if you do not control the class, a converter can be registered in `sympy.core.sympify.converter`, but docs recommend `_sympy_` when you control the class. ([SymPy Documentation][4])

Deployment rule:

```text id="hutvrs"
Use _sympy_:
  local, explicit conversion contract
  custom domain objects
  API input normalization

Avoid global converter registry:
  unless wrapping external classes you do not control
```

---

## 18.10 Assignment, `Piecewise`, `Indexed`, matrices in code printers

## 18.10.1 Assignment

```python id="6iuwsz"
from sympy.codegen.ast import Assignment
from sympy import ccode

ccode(Assignment(x, y + 1))
# x = y + 1;
```

Code printers can print expressions and assignments; the codegen docs show `Assignment` as a building block for C and other printers. ([SymPy Documentation][3])

## 18.10.2 `Piecewise`

```python id="ltcwxq"
pw = sp.Piecewise((x + 1, x > 0), (x, True))

sp.ccode(pw, assign_to="out")
sp.jscode(pw, assign_to="out")
sp.rust_code(pw, assign_to="out")
```

Code printers convert `Piecewise` to conditionals or ternaries/masks depending on target language and assignment mode. Missing default `(expr, True)` branches raise to avoid code that might not evaluate. ([SymPy Documentation][3])

## 18.10.3 Indexed contraction loops

```python id="duqtum"
i = sp.Idx("i", 5)
A = sp.IndexedBase("A", shape=(5,))
B = sp.IndexedBase("B", shape=(5,))
C = sp.IndexedBase("C", shape=(5,))

expr = sp.Eq(C[i], A[i] + B[i])

sp.ccode(expr.rhs, assign_to=expr.lhs, contract=True)
sp.ccode(expr.rhs, assign_to=expr.lhs, contract=False)
```

Many code printers support `Indexed` objects. With `contract=True`, repeated/indexed expressions can generate loops; with `contract=False`, the printer emits only the assignment expression and the caller must supply loops. ([SymPy Documentation][3])

---

## 18.11 Agent deployment recipes

## Recipe A — stable display bundle

```python id="z8a23t"
def display_bundle(expr: sp.Basic) -> dict[str, str]:
    expr = sp.sympify(expr)
    return {
        "str": str(expr),
        "pretty_ascii": sp.pretty(expr, use_unicode=False),
        "pretty_unicode": sp.pretty(expr, use_unicode=True),
        "latex": sp.latex(expr),
        "srepr": sp.srepr(expr),
    }
```

## Recipe B — exact parser with assumptions

```python id="lfdifu"
from sympy.parsing.sympy_parser import parse_expr, standard_transformations

def parse_trusted_expr(expr_text: str, symbols: dict[str, sp.Symbol]) -> sp.Expr:
    return parse_expr(
        expr_text,
        local_dict=symbols,
        transformations=standard_transformations,
        evaluate=True,
    )
```

## Recipe C — math-like parser with implicit multiplication

```python id="yoc2ah"
from sympy.parsing.sympy_parser import implicit_multiplication_application

def parse_trusted_math_expr(expr_text: str, symbols: dict[str, sp.Symbol]) -> sp.Expr:
    return parse_expr(
        expr_text,
        local_dict=symbols,
        transformations=standard_transformations + (implicit_multiplication_application,),
        evaluate=True,
    )
```

## Recipe D — source-faithful parser

```python id="9p6l9u"
def parse_source_faithful(expr_text: str, symbols: dict[str, sp.Symbol]) -> sp.Expr:
    return parse_expr(
        expr_text,
        local_dict=symbols,
        transformations=standard_transformations,
        evaluate=False,
    )
```

## Recipe E — safe-ish API coercion for non-string objects

```python id="6miyuo"
def coerce_sympy_object(obj) -> sp.Basic:
    if isinstance(obj, str):
        raise TypeError("string formulas must be parsed through explicit parser pipeline")
    return sp.sympify(obj, strict=True)
```

## Recipe F — C kernel print with validation

```python id="fdhdbr"
def c_scalar_kernel(expr, assign_to="out"):
    expr = sp.sympify(expr)

    if expr.has(sp.Integral, sp.Derivative, sp.Limit):
        raise ValueError("unevaluated calculus node remains")

    expr = sp.cse(expr)[1][0] if False else expr  # choose explicit cse pipeline separately

    return sp.ccode(expr, assign_to=assign_to, standard="C99")
```

## Recipe G — codegen-ready `Piecewise`

```python id="pi356p"
def ensure_piecewise_default(expr: sp.Expr) -> sp.Expr:
    expr = sp.sympify(expr)
    for pw in expr.atoms(sp.Piecewise):
        if pw.args[-1][1] != True:
            raise ValueError(f"Piecewise lacks default True branch: {pw}")
    return expr
```

## Recipe H — target-code export bundle

```python id="zo75ru"
def code_bundle(expr, assign_to="out") -> dict[str, str]:
    expr = ensure_piecewise_default(sp.sympify(expr))
    return {
        "c": sp.ccode(expr, assign_to=assign_to, standard="C99"),
        "fortran": sp.fcode(expr, assign_to=assign_to, source_format="free"),
        "javascript": sp.jscode(expr, assign_to=assign_to),
        "rust": sp.rust_code(expr, assign_to=assign_to),
        "octave": sp.octave_code(expr, assign_to=assign_to),
        "python": sp.pycode(expr),
    }
```

---

## 18.12 Anti-pattern inventory

| Anti-pattern                                        | Failure mode                                | Correct pattern                                 |
| --------------------------------------------------- | ------------------------------------------- | ----------------------------------------------- |
| `expand("(x**2+x)/x")`                              | accidental string parsing / future drift    | build expression with symbols                   |
| `S("x")` just to create symbol                      | hidden parse path / assumptions loss        | `Symbol("x")`                                   |
| parsing with no `local_dict`                        | wrong assumptions, typo-created symbols     | pass explicit symbols/functions                 |
| parsing untrusted input                             | code execution risk                         | reject or sandbox outside SymPy                 |
| using LaTeX as computational storage                | not stable/complete IR                      | store structured metadata / `srepr`             |
| using `str(expr)` as cache key                      | ambiguous/version-dependent                 | use object hash in-memory, or `srepr` + version |
| using code-printer output as optimized code         | suboptimal `pow`, no CSE                    | optimize/cse before printing                    |
| `Piecewise` without default in codegen              | printer error or incomplete code            | add `(expr, True)` branch                       |
| unsupported custom function in code printer         | output failure/unknown calls                | `user_functions` or rewrite                     |
| relying on printer private formatting for tests     | formatting drift                            | test structural expression separately           |
| `parse_expr(..., transformations="all")` blindly    | permissive grammar accepts unintended input | choose minimal transformations                  |
| `sympify(obj)` on arbitrary class                   | fallback/deprecation surprises              | `strict=True` or `_sympy_`                      |
| overriding SymPy names `S`, `I`, `E`, `N`, `O`, `Q` | namespace corruption                        | avoid reserved names                            |
| expecting `repr()` to be structural                 | not SymPy structural print                  | `srepr()`                                       |

SymPy gotchas explicitly recommend avoiding variable names such as `I`, `E`, `S`, `N`, `O`, and `Q` because they are used by core SymPy objects/functions such as the imaginary unit, Euler’s number, `sympify`, numeric evaluation, Big-O, and assumptions predicates. ([SymPy Documentation][7])

---

## 18.13 Testing matrix

```python id="0e1xap"
def test_srepr_contains_exact_nodes():
    expr = sp.Rational(1, 2)*x
    assert "Rational(1, 2)" in sp.srepr(expr)

def test_pretty_returns_string():
    assert isinstance(sp.pretty(sp.Integral(sp.sqrt(1/x), x)), str)

def test_latex_contains_integral():
    assert r"\int" in sp.latex(sp.Integral(sp.sqrt(1/x), x))

def test_parse_with_assumptions():
    z = sp.Symbol("z", positive=True)
    expr = parse_expr("z**2", local_dict={"z": z})
    assert list(expr.free_symbols)[0].is_positive is True

def test_evaluate_false_preserves_order():
    a = parse_expr("1 + x", local_dict={"x": x}, evaluate=False)
    b = parse_expr("x + 1", local_dict={"x": x}, evaluate=False)
    assert a != b

def test_ccode_piecewise_default():
    pw = sp.Piecewise((x + 1, x > 0), (x, True))
    assert "if" in sp.ccode(pw, assign_to="out")

def test_jscode_math_mapping():
    assert "Math.sin" in sp.jscode(sp.sin(x))

def test_octave_elementwise():
    assert ".*" in sp.octave_code(sp.sin(sp.pi*x*y), assign_to="s")

def test_sympify_reject_string_boundary():
    try:
        coerce_sympy_object("x+1")
    except TypeError:
        pass
    else:
        raise AssertionError("string should be rejected")
```

Coverage targets:

```text id="ru5xif"
Printing:
  str, pretty ASCII, pretty Unicode, latex, srepr, mathml, dotprint

Interactive:
  init_printing options, notebook-safe rendering, no library side effects

Code printers:
  ccode/fcode/pycode/jscode/octave_code/rust_code
  assign_to
  Piecewise with/without default
  user_functions
  Indexed contract True/False
  Matrix/MatrixSymbol assignment
  human=False structured metadata

Parsing:
  sympify strict=True
  parse_expr local_dict/global_dict
  transformations minimal/implicit/all
  evaluate=False structure preservation
  rationalize decimal exactness
  assumption preservation
  unsanitized input rejection policy

Serialization:
  metadata payload includes SymPy version
  free symbol assumptions captured
  target backend captured
```

---

## 18.14 Minimal printing/parsing/external-representation harness

```python id="jpsm11"
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Literal

import sympy as sp

from sympy.parsing.sympy_parser import (
    parse_expr,
    standard_transformations,
    implicit_multiplication_application,
    T,
)

from sympy.codegen.ast import Assignment


@dataclass(frozen=True)
class ExpressionRenderBundle:
    expr: sp.Basic
    str_text: str
    repr_text: str
    srepr_text: str
    pretty_ascii: str
    pretty_unicode: str
    latex_text: str
    free_symbols: tuple[str, ...]
    sympy_version: str


@dataclass(frozen=True)
class CodeRenderBundle:
    expr: sp.Basic
    c_code: str
    fortran_code: str
    python_code: str
    javascript_code: str
    octave_code: str
    rust_code: str


@dataclass(frozen=True)
class ParsePolicy:
    allow_strings: bool
    implicit_multiplication: bool
    evaluate: bool
    rationalize_all_decimals: bool
    trusted_input_only: bool


def render_bundle(expr: Any) -> ExpressionRenderBundle:
    expr = sp.sympify(expr)
    return ExpressionRenderBundle(
        expr=expr,
        str_text=str(expr),
        repr_text=repr(expr),
        srepr_text=sp.srepr(expr),
        pretty_ascii=sp.pretty(expr, use_unicode=False),
        pretty_unicode=sp.pretty(expr, use_unicode=True),
        latex_text=sp.latex(expr),
        free_symbols=tuple(sorted(str(s) for s in expr.free_symbols)),
        sympy_version=sp.__version__,
    )


def dot_source(expr: Any) -> str:
    from sympy.printing.dot import dotprint
    return dotprint(sp.sympify(expr))


def mathml_source(expr: Any) -> str:
    from sympy.printing.mathml import mathml
    return mathml(sp.sympify(expr))


def reject_string_input(obj: Any) -> Any:
    if isinstance(obj, str):
        raise TypeError("string input rejected; use explicit parse pipeline")
    return obj


def sympify_trusted_object(obj: Any, *, strict: bool = True) -> sp.Basic:
    reject_string_input(obj)
    return sp.sympify(obj, strict=strict)


def parse_trusted_python_expr(
    expr_text: str,
    symbols: Mapping[str, Any],
    *,
    evaluate: bool = True,
) -> sp.Expr:
    return parse_expr(
        expr_text,
        local_dict=dict(symbols),
        transformations=standard_transformations,
        evaluate=evaluate,
    )


def parse_trusted_math_expr(
    expr_text: str,
    symbols: Mapping[str, Any],
    *,
    evaluate: bool = True,
) -> sp.Expr:
    return parse_expr(
        expr_text,
        local_dict=dict(symbols),
        transformations=standard_transformations + (implicit_multiplication_application,),
        evaluate=evaluate,
    )


def parse_trusted_all_transformations(
    expr_text: str,
    symbols: Mapping[str, Any],
    *,
    evaluate: bool = True,
) -> sp.Expr:
    return parse_expr(
        expr_text,
        local_dict=dict(symbols),
        transformations="all",
        evaluate=evaluate,
    )


def parse_source_faithful(expr_text: str, symbols: Mapping[str, Any]) -> sp.Expr:
    return parse_expr(
        expr_text,
        local_dict=dict(symbols),
        transformations=standard_transformations,
        evaluate=False,
    )


def make_symbol_registry(symbols: Iterable[sp.Symbol]) -> dict[str, sp.Symbol]:
    registry = {}
    for s in symbols:
        if not isinstance(s, sp.Symbol):
            raise TypeError(f"expected Symbol, got {type(s).__name__}")
        registry[s.name] = s
    return registry


def ensure_no_unevaluated_nodes_for_code(expr: sp.Basic) -> sp.Basic:
    expr = sp.sympify(expr)
    bad_nodes = (sp.Integral, sp.Derivative, sp.Limit, sp.Sum, sp.Product)
    if any(expr.has(node) for node in bad_nodes):
        raise ValueError(f"unevaluated symbolic node remains: {expr}")
    return expr


def ensure_piecewise_default(expr: sp.Basic) -> sp.Basic:
    expr = sp.sympify(expr)
    for pw in expr.atoms(sp.Piecewise):
        if not pw.args or pw.args[-1][1] != True:
            raise ValueError(f"Piecewise lacks default True branch: {pw}")
    return expr


def prepare_for_code(expr: Any) -> sp.Basic:
    expr = sp.sympify(expr)
    expr = ensure_no_unevaluated_nodes_for_code(expr)
    expr = ensure_piecewise_default(expr)
    return expr


def c_code(expr: Any, *, assign_to: str | sp.Symbol | None = None, standard: str = "C99", cse: bool = False) -> str:
    expr = prepare_for_code(expr)

    if cse:
        reps, reduced = sp.cse(expr)
        lines = [sp.ccode(Assignment(sym, val), standard=standard) for sym, val in reps]
        lines.append(sp.ccode(reduced[0], assign_to=assign_to, standard=standard))
        return "\n".join(lines)

    return sp.ccode(expr, assign_to=assign_to, standard=standard)


def code_bundle(expr: Any, *, assign_to: str = "out") -> CodeRenderBundle:
    expr = prepare_for_code(expr)

    return CodeRenderBundle(
        expr=expr,
        c_code=sp.ccode(expr, assign_to=assign_to, standard="C99"),
        fortran_code=sp.fcode(expr, assign_to=assign_to, source_format="free"),
        python_code=sp.pycode(expr),
        javascript_code=sp.jscode(expr, assign_to=assign_to),
        octave_code=sp.octave_code(expr, assign_to=assign_to),
        rust_code=sp.rust_code(expr, assign_to=assign_to),
    )


def code_with_custom_functions(
    expr: Any,
    *,
    target: Literal["c", "js", "octave", "rust"],
    user_functions: dict,
    assign_to: str | None = None,
) -> str:
    expr = prepare_for_code(expr)

    if target == "c":
        return sp.ccode(expr, assign_to=assign_to, user_functions=user_functions)
    if target == "js":
        return sp.jscode(expr, assign_to=assign_to, user_functions=user_functions)
    if target == "octave":
        return sp.octave_code(expr, assign_to=assign_to, user_functions=user_functions)
    if target == "rust":
        return sp.rust_code(expr, assign_to=assign_to, user_functions=user_functions)

    raise ValueError(f"unknown target: {target}")


def indexed_assignment_code(
    rhs: Any,
    lhs: Any,
    *,
    target: Literal["c", "js", "rust", "octave"] = "c",
    contract: bool = True,
) -> str:
    rhs = sp.sympify(rhs)

    if target == "c":
        return sp.ccode(rhs, assign_to=lhs, contract=contract)
    if target == "js":
        return sp.jscode(rhs, assign_to=lhs, contract=contract)
    if target == "rust":
        return sp.rust_code(rhs, assign_to=lhs, contract=contract)
    if target == "octave":
        return sp.octave_code(rhs, assign_to=lhs, contract=contract)

    raise ValueError(f"unknown target: {target}")


def external_payload(expr: Any) -> dict[str, Any]:
    expr = sp.sympify(expr)
    return {
        "format": "sympy-expression-payload-v1",
        "sympy_version": sp.__version__,
        "class": type(expr).__name__,
        "srepr": sp.srepr(expr),
        "str": str(expr),
        "latex": sp.latex(expr),
        "free_symbols": [
            {
                "name": s.name,
                "assumptions0": dict(s.assumptions0),
            }
            for s in sorted(expr.free_symbols, key=str)
            if isinstance(s, sp.Symbol)
        ],
    }


def setup_interactive_printing(
    *,
    use_latex: str | bool | None = "mathjax",
    use_unicode: bool | None = True,
    order: str | None = "lex",
    num_columns: int | None = None,
) -> None:
    sp.init_printing(
        use_latex=use_latex,
        use_unicode=use_unicode,
        order=order,
        num_columns=num_columns,
    )


def parse_policy_summary() -> dict[str, str]:
    return {
        "trusted_python_syntax": "parse_expr(..., transformations=standard_transformations)",
        "trusted_math_like_syntax": "parse_expr(..., transformations=standard_transformations + (implicit_multiplication_application,))",
        "trusted_source_faithful": "parse_expr(..., evaluate=False)",
        "object_coercion": "sympify(obj, strict=True), reject strings",
        "untrusted_string": "do not use sympify/parse_expr; sandbox or reject",
        "symbols_with_assumptions": "construct Symbol objects first and pass local_dict",
        "serialization": "store version + srepr + symbol assumptions + domain metadata",
    }
```

This harness enforces representation boundaries: display bundles, structural diagnostics, safe object coercion, trusted parsing with explicit symbol registries, source-faithful parsing, codegen preflight checks, `Piecewise` default validation, language-specific code-printer bundles, custom function mappings, `Indexed` loop control, external payload metadata, and notebook printing setup.

[1]: https://docs.sympy.org/latest/modules/printing.html "Printing - SymPy 1.14.0 documentation"
[2]: https://docs.sympy.org/latest/tutorials/intro-tutorial/printing.html "Printing - SymPy 1.14.0 documentation"
[3]: https://docs.sympy.org/latest/modules/codegen.html "Code Generation - SymPy 1.14.0 documentation"
[4]: https://docs.sympy.org/latest/modules/core.html "Core - SymPy 1.14.0 documentation"
[5]: https://docs.sympy.org/latest/explanation/best-practices.html "Best Practices - SymPy 1.14.0 documentation"
[6]: https://docs.sympy.org/latest/modules/parsing.html "Parsing - SymPy 1.14.0 documentation"
[7]: https://docs.sympy.org/latest/explanation/gotchas.html "Gotchas and Pitfalls - SymPy 1.14.0 documentation"

# 19) Numeric computation bridge: `subs`, `evalf`, `lambdify`, `ufuncify`, and `autowrap` — agent-ready deep dive

Continuing the same advanced technical-doc pattern as the supplied reference artifact. 

## 19.0 Numeric-bridge mental model

SymPy’s high-value workflow is **symbolic derivation first, numeric execution second**. Build exact expressions with SymPy objects, transform/simplify them symbolically, then ship the final expression to a numeric backend. SymPy’s numeric-computation docs explicitly state that symbolic systems often have poor performance on numerical data and that SymPy provides hooks into numeric systems such as `math`, NumPy, C, and Fortran. The same docs classify options from slow/simple `subs/evalf` through `lambdify`, NumPy-backed `lambdify`, `ufuncify`, CuPy, and JAX. ([SymPy Documentation][1])

```python id="fc8aua"
import sympy as sp

x, y, z = sp.symbols("x y z")
expr = sp.sin(x) / x
```

Bridge stack:

```text id="kir4ya"
exact symbolic IR:
  Expr / Matrix / Piecewise / Indexed / Function

simple scalar numeric check:
  expr.evalf(subs={x: value})
  expr.subs(...).evalf(...)

Python scalar callable:
  lambdify(args, expr, modules="math")
  lambdify(args, expr, modules="mpmath")

vectorized CPU arrays:
  lambdify(args, expr, modules="numpy")
  lambdify(args, expr, modules="scipy")
  lambdify(args, expr, modules="numexpr")

accelerators:
  lambdify(args, expr, modules="cupy")
  lambdify(args, expr, modules="jax")
  lambdify(args, expr, modules="tensorflow")

compiled extension:
  autowrap(expr, backend="f2py"|"cython")
  ufuncify(args, expr, backend="f2py"|"cython")

source-code generation:
  ccode/fcode/codegen + external build system
```

---

## 19.1 Path-selection matrix

| Requirement                          |           Preferred bridge | Runtime target          | Notes                                |
| ------------------------------------ | -------------------------: | ----------------------- | ------------------------------------ |
| one-off scalar value                 |     `expr.evalf(subs=...)` | SymPy/mpmath            | simplest, slowest                    |
| repeated scalar machine-float calls  |    `lambdify(..., "math")` | Python `math`           | low dependency                       |
| arbitrary precision scalar calls     |  `lambdify(..., "mpmath")` | mpmath                  | precision-oriented                   |
| vectorized CPU arrays                |   `lambdify(..., "numpy")` | NumPy ufuncs            | standard array path                  |
| SciPy special functions              |   `lambdify(..., "scipy")` | SciPy/NumPy             | richer numeric namespace             |
| large array expression speedup       | `lambdify(..., "numexpr")` | numexpr VM              | limited function set                 |
| GPU array execution                  |    `lambdify(..., "cupy")` | CuPy arrays             | GPU if CuPy configured               |
| CPU/GPU/TPU array execution          |     `lambdify(..., "jax")` | JAX arrays/XLA          | accelerator/JIT ecosystem            |
| fused compiled NumPy ufunc           |                 `ufuncify` | C/Fortran + NumPy ufunc | compiled elementwise array kernel    |
| compiled scalar/function wrapper     |                 `autowrap` | f2py/Cython callable    | compiled Python-callable function    |
| generated files for external project |         `codegen`/printers | C/F95/Octave/etc.       | source artifact, not Python callable |

SymPy’s current numeric-computation comparison lists approximate qualitative speeds and dependencies: `subs/evalf` as simple/no-dependency but slow, `lambdify` as scalar `math`-backed, NumPy `lambdify` as vector-function oriented, `ufuncify` for complex vector expressions with `f2py`/Cython, CuPy for GPU vector functions, and JAX for CPU/GPU/TPU vector functions. ([SymPy Documentation][1])

---

## 19.2 Simple numeric evaluation: `.subs()`, `.evalf()`, `N()`

## 19.2.1 Direct substitution and evaluation

```python id="ya14xe"
expr = sp.sin(x) / x

expr.subs(x, sp.Rational(1, 3))
expr.subs(x, 3.14).evalf()
expr.evalf(subs={x: 3.14})
sp.N(expr.subs(x, sp.pi/3), 50)
```

`subs/evalf` runs inside SymPy and is the slowest but simplest path. SymPy’s docs show `expr.evalf(subs={x: 3.14})` for `sin(x)/x`, state that `.subs(...).evalf()` runs at SymPy speeds, and explicitly advise using it in production only when performance is not an issue. ([SymPy Documentation][2])

## 19.2.2 `.evalf(subs=...)` vs `.subs(...).evalf()`

```python id="xwfy8m"
expr = x + y - z
values = {x: 1e16, y: 1, z: 1e16}

expr.subs(values)
# may collapse through ordinary inexact substitution

expr.evalf(30, subs=values)
# numerical substitution/evaluation inside evalf machinery
```

Deployment rule:

```text id="kmx0jw"
Use expr.evalf(n, subs=values):
  one-off scalar evaluation
  cancellation-sensitive inexact values
  high-precision diagnostics
  symbolic expression still mostly exact

Use expr.subs(exact_values):
  exact specialization
  formula transformation
  symbolic simplification before numeric boundary

Avoid:
  .subs(...).evalf() in hot loops
  .evalf() for vectorized arrays
```

## 19.2.3 Precision control

```python id="a12xj2"
expr.evalf()
expr.evalf(50)
sp.N(expr, 80)
expr.evalf(100, subs={x: sp.Rational(1, 7)})
```

`evalf`/`N` are scalar symbolic numerical-evaluation tools. They are appropriate for diagnostics, high-precision checks, and exact-to-approximate scalar transitions; repeated numeric evaluation should use `lambdify` or compiled paths.

---

## 19.3 `lambdify`: namespace translation to numeric callables

## 19.3.1 API surface

```python id="3ickgg"
from sympy import lambdify

f = lambdify(x, expr)
f = lambdify(x, expr, modules="math")
f = lambdify(x, expr, modules="mpmath")
f = lambdify(x, expr, modules="numpy")
f = lambdify((x, y), sp.sin(x*y)**2, modules="numpy")

f = lambdify(
    args=(x, y),
    expr=expr,
    modules="numpy",
    dummify=False,
    cse=False,
    docstring_limit=1000,
)
```

`lambdify` converts a SymPy expression into a Python function for fast numerical evaluation. Its docs warn that it uses `exec`, so it must not be used on unsanitized input. It also deprecates unordered `set` arguments because call-argument order must be deterministic. ([SymPy Documentation][3])

Core contract:

```text id="x6yemg"
lambdify(args, expr, modules=...):
  creates Python callable
  maps SymPy functions to backend namespace functions
  returns ordinary Python function
  output type determined by backend and expression shape
  not a symbolic object
```

## 19.3.2 Basic examples

```python id="xmf0he"
expr = sp.sin(x) + sp.cos(x)

f_math = sp.lambdify(x, expr, "math")
f_math(1.0)

f_np = sp.lambdify(x, expr, "numpy")
```

```python id="wjs1qq"
import numpy as np

a = np.array([1.0, 2.0])
f_np(a)
# vectorized NumPy output
```

The docs describe `lambdify` as the bridge from SymPy expressions to numerical libraries including NumPy, SciPy, NumExpr, mpmath, and TensorFlow. They emphasize the correct workflow: first create a SymPy expression using SymPy symbols/functions, then convert it with `lambdify`, then call the generated function on backend-compatible numeric inputs. ([SymPy Documentation][3])

---

## 19.4 Backend semantics: `math`, `mpmath`, `numpy`, `scipy`, `numexpr`, `tensorflow`, `jax`, `cupy`

## 19.4.1 Backend decision rules

```text id="x4fq8o"
modules="math":
  scalar Python floats
  no arrays
  lowest dependency

modules="mpmath":
  arbitrary precision scalar / complex numerics
  good verification oracle

modules="numpy":
  vectorized arrays
  ufunc-backed elementwise operations
  common production array path

modules="scipy":
  SciPy special functions + NumPy
  useful for special functions not in NumPy

modules="numexpr":
  large array expressions
  limited supported functions
  can reduce temporary arrays / improve speed

modules="tensorflow":
  tensors / eager tensors
  result may be EagerTensor; use .numpy() when needed

modules="jax":
  JAX arrays / JIT / autodiff ecosystem
  CPU/GPU/TPU path when expression maps cleanly

modules="cupy":
  CuPy arrays
  GPU vectorized path when CuPy/CUDA stack is configured
```

SymPy’s lambdify docs state that `numexpr` can significantly speed large array calculations but has a more limited function set than NumPy; TensorFlow lambdified functions may return `EagerTensor` values whose `.numpy()` method extracts a NumPy value; and some NumPy-backed lambdified functions rely on NumPy-array inputs, especially with `Piecewise`, where scalar inputs can fail but arrays work. ([SymPy Documentation][3])

## 19.4.2 Backend-specific examples

```python id="fju0dk"
expr = sp.Piecewise((x, x <= 1), (1/x, x > 1))

f_numpy = sp.lambdify(x, expr, "numpy")
f_math = sp.lambdify(x, expr, "math")
```

```python id="segzwg"
import numpy as np

f_numpy(np.array([-1.0, 0.0, 1.0, 2.0]))
# array-safe Piecewise path

f_math(0.0)
# scalar branch semantics, if expressible by math backend
```

## 19.4.3 Custom namespace mapping

```python id="sp2sjy"
def my_sin(u):
    return 1000

f = sp.lambdify(
    x,
    sp.sin(x) + x,
    modules=[{"sin": my_sin}, "numpy"],
)
```

`modules` can be a string, module, dictionary, or ordered list combining dictionaries and modules. Custom dictionaries are high priority when placed first. Use this for unsupported functions, target-specific approximations, instrumentation, or backend-specific kernels.

---

## 19.5 Namespace boundary: do not mix SymPy and numeric backends

## 19.5.1 Failure mode

```python id="6srn6d"
f = sp.lambdify(x, x + sp.sin(x), "numpy")

# Correct:
# f(np.array([1, 2]))

# Wrong:
# f(x + 1)
```

SymPy’s lambdify docs give this exact conceptual warning: a NumPy-backed lambdified function calls NumPy functions, and NumPy functions do not know how to operate on SymPy expressions; likewise, SymPy functions do not directly operate on NumPy arrays. This is why `lambdify` exists as a bridge, and mixing sides can fail or work only accidentally. ([SymPy Documentation][3])

Deployment rule:

```text id="y3vxxz"
Symbolic phase:
  SymPy expressions only.

Numeric phase:
  backend-native scalars/arrays/tensors only.

Forbidden:
  NumPy ufuncs on SymPy Expr.
  SymPy functions on NumPy arrays.
  NumPy-lambdified function called with SymPy Expr.
```

## 19.5.2 Boundary validator

```python id="u1phpq"
def reject_sympy_inputs(*values):
    if any(isinstance(v, sp.Basic) for v in values):
        raise TypeError("numeric backend received SymPy object")
```

---

## 19.6 Argument structures, matrices, and return shapes

## 19.6.1 Scalar and tuple arguments

```python id="46n8ew"
f = sp.lambdify((x, y, z), [z, y, x])
f(1, 2, 3)

g = sp.lambdify((x, (y, z)), x + y)
g(1, (2, 4))
```

`lambdify` supports nested tuple arguments; the generated function must be called with the same argument structure. The docs also show using `flatten` to flatten nested argument structures into a flat call signature. ([SymPy Documentation][3])

```python id="5y1oq1"
from sympy.utilities.iterables import flatten

args = (x, (y, z))
flat_args = flatten(args)

f = sp.lambdify(flat_args, x + y + z)
f(1, 2, 3)
```

## 19.6.2 Matrix/list outputs

```python id="mrzbjb"
Mexpr = sp.Matrix([x, x + y])

f_sympy = sp.lambdify((x, y), Mexpr.T, modules="sympy")
f_numpy = sp.lambdify((x, y), Mexpr, modules="numpy")
```

Output shape depends on expression type and backend. Matrix expressions may return SymPy `Matrix` under `modules="sympy"` or nested lists/arrays under numeric backends, depending on printer/backend behavior. Test return shape explicitly before exposing the callable.

---

## 19.7 `_imp_`, `implemented_function`, and custom functions

## 19.7.1 Quick implementation attachment

```python id="0ywg7q"
from sympy.utilities.lambdify import implemented_function

f_undef = sp.Function("f")
f_impl = implemented_function(f_undef, lambda u: u + 1)

fn = sp.lambdify(x, f_impl(x))
fn(4)
# 5
```

`lambdify` can use numerical implementations attached to functions through `_imp_`; `implemented_function` creates such an implementation for an undefined function. The docs state that `lambdify` prefers `_imp_` implementations unless `use_imps=False`. ([SymPy Documentation][3])

## 19.7.2 Deployment choice

```text id="h1pf47"
Use implemented_function:
  quick numeric function for lambdify
  no full symbolic behavior required

Use custom Function subclass:
  symbolic assumptions
  differentiation
  rewrites
  printing
  evalf behavior

Use modules dict:
  target-backend-specific mapping
```

---

## 19.8 Large expression lambdification: `cse` and `docstring_limit`

```python id="vb0v99"
f = sp.lambdify(
    (x, y),
    large_expr,
    modules="numpy",
    cse=True,
    docstring_limit=0,
)
```

For large expressions, a significant part of `lambdify` construction time can be spent rendering the generated function’s docstring. The docs describe `docstring_limit`: `None` renders the full expression, `0` or negative values render an ellipsis, and positive values render the full expression only below a node-count threshold. The default is `1000`. ([SymPy Documentation][3])

Deployment rules:

```text id="soz10x"
Large expression lambdify:
  cse=True
  docstring_limit=0
  fixed modules backend
  pre-simplify expression
  benchmark construction time separately from call time
```

---

## 19.9 NumPy vectorization path

## 19.9.1 Basic vectorized callable

```python id="70ellq"
import numpy as np

expr = sp.sin(x) / x
f = sp.lambdify(x, expr, modules="numpy")

data = np.linspace(1.0, 10.0, 10_000)
out = f(data)
```

SymPy’s numeric-computation docs show `lambdify(x, expr, "numpy")` applied to `numpy.linspace(...)` for `sin(x)/x`; they describe NumPy as providing compiled ufunc-backed vectorized operations and note array evaluation can be on the order of nanoseconds per element, while incurring startup overhead. ([SymPy Documentation][2])

## 19.9.2 Multi-argument broadcasting

```python id="bqzgo7"
expr = sp.sin(x*y) + x**2

f = sp.lambdify((x, y), expr, "numpy")

xs = np.linspace(0, 1, 1000)
ys = np.linspace(0, 10, 1000)

out = f(xs, ys)
```

Backend rules:

```text id="z96as2"
NumPy lambdified function:
  obeys NumPy broadcasting
  returns NumPy arrays for array inputs
  returns NumPy scalar/Python scalar for scalar inputs
  may fail on SymPy inputs
  may require array input for Piecewise semantics
```

## 19.9.3 Matrix/vector returns

```python id="sap7dt"
exprs = [sp.sin(x), sp.cos(x), x**2]
f = sp.lambdify(x, exprs, "numpy")

out = f(np.linspace(0, 1, 5))
```

For production APIs, normalize return shapes:

```python id="h012m5"
def as_array_output(f, *args):
    import numpy as np
    return np.asarray(f(*args))
```

---

## 19.10 GPU/accelerator paths: CuPy, JAX, TensorFlow

## 19.10.1 CuPy

```python id="2fkfvs"
f_cupy = sp.lambdify(x, sp.sin(x)/x, modules="cupy")

# import cupy as cp
# data_gpu = cp.linspace(1, 10, 1_000_000)
# out_gpu = f_cupy(data_gpu)
```

CuPy is appropriate when the expression maps to CuPy-supported functions and data already live on the GPU. The numeric-computation docs list `lambdify-cupy` as a vector-function GPU path with `cupy` dependency. ([SymPy Documentation][1])

## 19.10.2 JAX

```python id="aaxfx0"
f_jax = sp.lambdify(x, sp.sin(x)/x, modules="jax")

# import jax
# import jax.numpy as jnp
# f_jit = jax.jit(f_jax)
# out = f_jit(jnp.linspace(1, 10, 1_000_000))
```

JAX is appropriate for CPU/GPU/TPU array execution, JIT, autodiff, and accelerator pipelines when the generated expression maps cleanly to JAX operations. SymPy’s numeric-computation docs list `lambdify-jax` as a vector-function path on CPUs, GPUs, and TPUs with the `jax` dependency. ([SymPy Documentation][1])

## 19.10.3 TensorFlow

```python id="ep4pla"
f_tf = sp.lambdify(x, sp.Max(x, sp.sin(x)), modules="tensorflow")

# import tensorflow as tf
# result = f_tf(tf.constant(1.0))
# result.numpy()
```

SymPy’s lambdify docs show TensorFlow usage where results may be `EagerTensor` objects and `.numpy()` extracts a NumPy value when eager execution is enabled. ([SymPy Documentation][3])

Deployment rules:

```text id="kn5zu6"
CuPy:
  best when arrays are already on GPU.
  avoid host-device copy bottlenecks.

JAX:
  best for JIT/autodiff/accelerator workflows.
  validate generated function under jit.

TensorFlow:
  expect Tensor/EagerTensor outputs.
  extract .numpy() only at boundary.

All accelerators:
  verify function coverage.
  verify dtype/shape.
  benchmark including transfer/JIT compile cost.
```

---

## 19.11 `ufuncify`: compiled NumPy ufunc generation

## 19.11.1 API surface

```python id="y6l03j"
from sympy.utilities.autowrap import ufuncify

f = ufuncify([x], sp.sin(x)/x)
f = ufuncify([x, y], sp.sin(x*y) + x**2, backend="f2py")
f = ufuncify([x], expr, backend="cython")
```

`ufuncify` creates a NumPy-aware universal function from a SymPy expression, using autowrap infrastructure. It accepts arrays and operates element-by-element according to NumPy broadcasting rules. SymPy’s codegen docs state that `ufuncify` generally performs at least as well as `lambdify`, and for complicated expressions can significantly outperform NumPy-backed `lambdify` because it can fuse chained elementwise operations into a single low-level loop. ([SymPy Documentation][4])

## 19.11.2 Why `ufuncify` can beat NumPy `lambdify`

NumPy evaluates chained ufuncs as separate loops, possibly allocating temporary arrays; SymPy-generated C/Fortran can fuse operations into one loop, avoiding extra memory passes and temporaries. SymPy’s codegen docs illustrate this with `sin(x)/x`, where NumPy calls `sin` and division as separate tight loops, while generated code can fuse the operation. ([SymPy Documentation][4])

Deployment rules:

```text id="d9t0pt"
Use ufuncify when:
  vectorized NumPy expression is called many times;
  expression is complex enough to benefit from loop fusion;
  f2py/Cython toolchain is available;
  inputs/outputs are NumPy arrays/scalars compatible with ufunc semantics.

Avoid ufuncify when:
  deployment cannot compile native extensions;
  expression is simple and NumPy overhead is already negligible;
  startup/build cost dominates;
  backend toolchain availability is uncertain.
```

---

## 19.12 `autowrap`: compiled Python-callable generation

## 19.12.1 API surface

```python id="7bvimo"
from sympy.utilities.autowrap import autowrap

f = autowrap(expr)
f = autowrap(expr, backend="f2py")
f = autowrap(expr, backend="cython")
f = autowrap(expr, language="C", backend="cython")
f = autowrap(expr, args=[x, y, z], tempdir="/tmp/sympy-autowrap", verbose=True)
```

`autowrap` automatically generates code, writes it to disk, compiles it, and imports the compiled function into the current session. It is not in the top-level SymPy namespace and must be imported from `sympy.utilities.autowrap`; the callable it returns is a binary Python function, not a SymPy object. Its main functions include `autowrap`, `binary_function`, and `ufuncify`. ([SymPy Documentation][4])

## 19.12.2 Indexed output / loop generation

```python id="qzbdqg"
from sympy import Eq, IndexedBase, Idx

m = sp.symbols("m", integer=True, positive=True)
i = sp.Idx("i", m)

x_arr = sp.IndexedBase("x")
y_arr = sp.IndexedBase("y")

expr = sp.Eq(y_arr[i], sp.sin(x_arr[i]) / x_arr[i])

# f = autowrap(expr, backend="f2py", tempdir="/tmp", args=[y_arr, x_arr, m])
```

Autowrap automatically converts expressions containing `Indexed` objects into summations/loops. The docs show `autowrap(Eq(y_[i], ...), tempdir='/tmp')` generating Fortran code with an explicit loop over `i`, and `args=[...]` controls argument ordering. ([SymPy Documentation][4])

## 19.12.3 Helpers and debugging

```python id="k2j11g"
# autowrap(expr, helpers=[("helper_name", helper_expr, (x, y))], ...)
```

`tempdir` preserves generated source files for inspection; `verbose=True` exposes backend command output; `language` and `backend` switch defaults from Fortran/f2py to C/Cython; helper routines require explicit argument sequences. ([SymPy Documentation][4])

Deployment rules:

```text id="h55rru"
Use autowrap when:
  scalar or array compiled function is needed in Python;
  native toolchain is allowed;
  generated source inspection is useful;
  argument order must be controlled;
  Indexed loop expressions are present.

Avoid autowrap when:
  runtime environment lacks compilers;
  deployment must be pure Python;
  native extension build latency is unacceptable;
  packaging compiled artifacts is out of scope.
```

---

## 19.13 `binary_function`: compiled function wrapped as SymPy function

```python id="j4y6hc"
from sympy.utilities.autowrap import binary_function

# f = binary_function("f", expr)
# f(x).evalf(subs={x: 1.0})
```

`binary_function` returns a SymPy function object backed by compiled code, letting the compiled function participate in SymPy expressions while evaluating quickly. The docs show `binary_function('f', psi_nl)` producing a function whose applied form can be evaluated with `.evalf(..., subs=...)`. ([SymPy Documentation][4])

Use when:

```text id="ja32nq"
Need compiled speed but still want a SymPy Function wrapper.
Need generated function to appear in larger symbolic formulas.
Need evalf-compatible compiled special-function substitute.
```

---

## 19.14 Codegen vs autowrap vs printers

```text id="d4jz8p"
printers:
  ccode/fcode/jscode/rust_code
  code snippets only

codegen:
  compilable source/header files
  no automatic compile/import

autowrap:
  generate code
  compile
  import callable

ufuncify:
  generate compiled NumPy-style elementwise ufunc
```

`codegen` creates compilable source and header files but does not compile them; `autowrap` generates code, compiles it, and imports a function; `ufuncify` is autowrap-level and creates NumPy-style elementwise functions. ([SymPy Documentation][4])

---

## 19.15 Pre-deployment symbolic preparation

## 19.15.1 Normalize expression before numeric export

```python id="rtuqmk"
def prepare_numeric_expr(expr: sp.Expr) -> sp.Expr:
    expr = sp.sympify(expr)

    # Reject symbolic calculus objects.
    if expr.has(sp.Integral, sp.Derivative, sp.Limit, sp.Sum, sp.Product):
        raise ValueError(f"unevaluated symbolic node remains: {expr}")

    # Rational and trig cleanup.
    expr = sp.cancel(sp.together(expr))
    expr = sp.trigsimp(expr)
    expr = sp.powsimp(expr, combine="exp", deep=True, force=False)

    return expr
```

## 19.15.2 Handle `Piecewise`

```python id="vwmcnu"
def ensure_piecewise_default(expr: sp.Expr) -> sp.Expr:
    expr = sp.sympify(expr)

    for pw in expr.atoms(sp.Piecewise):
        if pw.args[-1][1] != True:
            raise ValueError(f"Piecewise lacks default True branch: {pw}")

    return expr
```

Why: code printers and numeric backends may require a complete branch structure; scalar NumPy-backed `Piecewise` can also behave differently from array-backed input.

## 19.15.3 CSE and optimized rewrites

```python id="67c2cz"
from sympy.codegen.rewriting import optimize, optims_c99

optimized = optimize(3*sp.exp(2*x) - 3, optims_c99)
# 3*expm1(2*x)
```

SymPy’s codegen rewriting docs show target-specific rewrites such as `exp(x)-1 → expm1(x)` and `log(1+x) → log1p(x)` for improved precision/performance in languages with those library functions. ([SymPy Documentation][4])

---

## 19.16 Deployment profiles

## Profile A — one-off scalar diagnostic

```python id="wuhrgk"
value = prepare_numeric_expr(expr).evalf(50, subs={x: sp.Rational(1, 7)})
```

Use:

```text id="6izdgk"
debugging
validation
high-precision scalar check
unit tests for exact formulas
```

## Profile B — Python scalar function

```python id="ygbke8"
f = sp.lambdify(x, prepare_numeric_expr(expr), modules="math")
```

Use:

```text id="36xhvo"
low dependency
ordinary Python floats
simple scalar loops
CLI calculators
```

## Profile C — high-precision scalar function

```python id="ot6fzf"
f = sp.lambdify(x, prepare_numeric_expr(expr), modules="mpmath")
```

Use:

```text id="k1jf6w"
arbitrary precision
complex scalar verification
test oracle for compiled/double-precision kernels
```

## Profile D — NumPy vectorized function

```python id="3w80k8"
f = sp.lambdify(x, prepare_numeric_expr(expr), modules="numpy")
```

Use:

```text id="nxa8y4"
arrays
plots
Monte Carlo / grid evaluation
standard scientific Python
```

## Profile E — SciPy-backed special functions

```python id="7egmsc"
f = sp.lambdify(x, prepare_numeric_expr(sp.erf(x) + sp.gamma(x)), modules="scipy")
```

Use:

```text id="ke1hnu"
special functions
SciPy namespace coverage
NumPy arrays plus SciPy functions
```

## Profile F — numexpr large-array expression

```python id="t07dav"
f = sp.lambdify(x, prepare_numeric_expr(expr), modules="numexpr")
```

Use:

```text id="be3u7i"
large arrays
supported elementary functions only
expression evaluation with reduced temporaries
```

## Profile G — accelerator JAX

```python id="dqx4ro"
f = sp.lambdify((x, y), prepare_numeric_expr(expr), modules="jax")
# f_jit = jax.jit(f)
```

Use:

```text id="62p3es"
JIT
autodiff ecosystem
CPU/GPU/TPU arrays
stateless pure numeric functions
```

## Profile H — GPU CuPy

```python id="0v3hnb"
f = sp.lambdify(x, prepare_numeric_expr(expr), modules="cupy")
```

Use:

```text id="9bbzxt"
GPU-resident arrays
NumPy-like GPU array workflows
large vectorized data
```

## Profile I — compiled NumPy ufunc

```python id="gixx8d"
from sympy.utilities.autowrap import ufuncify

uf = ufuncify([x], prepare_numeric_expr(expr), backend="f2py")
```

Use:

```text id="hf4wqh"
complex elementwise array kernels
loop fusion
repeated high-volume evaluation
native toolchain allowed
```

## Profile J — compiled scalar callable

```python id="we3ab9"
from sympy.utilities.autowrap import autowrap

compiled = autowrap(prepare_numeric_expr(expr), args=[x], backend="cython")
```

Use:

```text id="l4yp4x"
compiled scalar kernels
native extension workflows
performance-critical repeated calls
```

---

## 19.17 Anti-pattern inventory

| Anti-pattern                                         | Failure mode                        | Correct pattern                       |
| ---------------------------------------------------- | ----------------------------------- | ------------------------------------- |
| `.subs(...).evalf()` in hot loop                     | SymPy-speed bottleneck              | `lambdify` or compiled path           |
| NumPy ufunc on SymPy expression                      | type error / object arrays          | SymPy first, then `lambdify`          |
| SymPy function on NumPy array                        | symbolic/object behavior or error   | backend-native function               |
| NumPy-lambdified function called with SymPy Expr     | accidental success or ufunc failure | backend-native inputs only            |
| `lambdify` on unsanitized user expression            | `exec` risk                         | parse/sanitize/reject before lambdify |
| unordered args set to `lambdify`                     | nondeterministic call order         | list/tuple ordered args               |
| no `docstring_limit` for huge expressions            | slow function construction          | `docstring_limit=0`                   |
| no `cse` for repeated large expressions              | redundant runtime work              | `cse=True` or manual CSE              |
| GPU backend with host-device transfers per call      | slower than CPU                     | keep data resident on device          |
| JAX function not tested under `jit`                  | tracing incompatibilities           | test eager and `jax.jit`              |
| `ufuncify` in compilerless environment               | build failure                       | fallback to NumPy lambdify            |
| autowrap without fixed `args`                        | argument-order surprises            | pass `args=[...]`                     |
| unsupported special function in backend              | NameError / wrong mapping           | custom modules dict or rewrite        |
| unresolved `Derivative`/`Integral` in numeric export | backend cannot evaluate             | `.doit()` / discretize / reject       |
| `Piecewise` without default                          | codegen/backend branch failure      | include `(expr, True)`                |

---

## 19.18 Testing and benchmarking matrix

```python id="jm29px"
def assert_backend_close(expr, args, values, *, atol=1e-12):
    e = prepare_numeric_expr(expr)

    ref = sp.N(e.subs(dict(zip(args, values))), 50)

    f_np = sp.lambdify(args, e, "numpy")
    got = f_np(*values)

    assert abs(float(ref) - float(got)) <= atol
```

Coverage targets:

```text id="oskk10"
subs/evalf:
  exact substitution
  Float substitution
  cancellation-sensitive evalf(subs=...)

lambdify:
  math scalar
  mpmath scalar
  numpy array
  scipy special functions
  numexpr supported/unsupported functions
  custom modules dict
  implemented_function/_imp_
  Piecewise scalar vs array
  nested tuple arguments
  matrix/list output shape
  docstring_limit large expression
  cse=True behavior

accelerators:
  jax eager
  jax.jit
  cupy arrays if GPU stack present
  tensorflow EagerTensor and .numpy()

compiled:
  ufuncify f2py/cython
  autowrap f2py/cython
  args ordering
  tempdir source inspection
  Indexed loop expressions

fallbacks:
  compiler unavailable
  backend missing
  unsupported function mapping
```

Benchmark skeleton:

```python id="be3pug"
def benchmark_callable(f, args, *, number=10000):
    import timeit
    return timeit.timeit(lambda: f(*args), number=number)
```

---

## 19.19 Minimal numeric-bridge harness

```python id="g2bvh0"
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Literal, Sequence

import sympy as sp


Backend = Literal[
    "math",
    "mpmath",
    "numpy",
    "scipy",
    "numexpr",
    "tensorflow",
    "jax",
    "cupy",
    "sympy",
]


@dataclass(frozen=True)
class NumericBridgeAudit:
    expr: sp.Expr
    free_symbols: tuple[sp.Symbol, ...]
    operation_count: int
    has_piecewise: bool
    has_unevaluated_calculus: bool
    has_unsupported_float: bool
    backend: str | None = None


def numeric_audit(expr: Any, *, backend: str | None = None) -> NumericBridgeAudit:
    expr = sp.sympify(expr)

    return NumericBridgeAudit(
        expr=expr,
        free_symbols=tuple(sorted(expr.free_symbols, key=str)),
        operation_count=int(sp.count_ops(expr)),
        has_piecewise=bool(expr.atoms(sp.Piecewise)),
        has_unevaluated_calculus=any(
            expr.has(node)
            for node in (sp.Integral, sp.Derivative, sp.Limit, sp.Sum, sp.Product)
        ),
        has_unsupported_float=bool(expr.atoms(sp.Float)),
        backend=backend,
    )


def ensure_numeric_exportable(expr: Any) -> sp.Expr:
    expr = sp.sympify(expr)

    if any(expr.has(node) for node in (sp.Integral, sp.Derivative, sp.Limit, sp.Sum, sp.Product)):
        raise ValueError(f"unevaluated symbolic object remains: {expr}")

    for pw in expr.atoms(sp.Piecewise):
        if not pw.args or pw.args[-1][1] != True:
            raise ValueError(f"Piecewise lacks default True branch: {pw}")

    return expr


def prepare_numeric_expr(expr: Any, *, cse_safe: bool = False) -> sp.Expr:
    expr = ensure_numeric_exportable(expr)

    expr = sp.cancel(sp.together(expr))
    expr = sp.trigsimp(expr)
    expr = sp.powsimp(expr, combine="exp", deep=True, force=False)

    return expr


def evalf_once(
    expr: Any,
    *,
    subs: dict[sp.Symbol, Any] | None = None,
    digits: int = 50,
) -> sp.Expr:
    expr = sp.sympify(expr)
    return expr.evalf(digits, subs=subs)


def lambdify_numeric(
    args: Sequence[Any] | Any,
    expr: Any,
    *,
    backend: Backend | list | dict = "numpy",
    cse: bool = True,
    docstring_limit: int | None = 0,
    dummify: bool = False,
    use_imps: bool = True,
    custom_modules: dict[str, Callable] | None = None,
):
    expr = prepare_numeric_expr(expr)

    modules: Any
    if custom_modules is not None:
        modules = [custom_modules, backend]
    else:
        modules = backend

    return sp.lambdify(
        args,
        expr,
        modules=modules,
        cse=cse,
        docstring_limit=docstring_limit,
        dummify=dummify,
        use_imps=use_imps,
    )


def lambdify_numpy(args: Sequence[Any] | Any, expr: Any, **kwargs):
    return lambdify_numeric(args, expr, backend="numpy", **kwargs)


def lambdify_mpmath(args: Sequence[Any] | Any, expr: Any, **kwargs):
    return lambdify_numeric(args, expr, backend="mpmath", **kwargs)


def lambdify_jax(args: Sequence[Any] | Any, expr: Any, **kwargs):
    return lambdify_numeric(args, expr, backend="jax", **kwargs)


def lambdify_cupy(args: Sequence[Any] | Any, expr: Any, **kwargs):
    return lambdify_numeric(args, expr, backend="cupy", **kwargs)


def reject_sympy_numeric_inputs(*values):
    if any(isinstance(v, sp.Basic) for v in values):
        raise TypeError("numeric backend received a SymPy object")


def call_numeric(f: Callable, *values):
    reject_sympy_numeric_inputs(*values)
    return f(*values)


def vector_samples(
    f: Callable,
    start: float,
    stop: float,
    *,
    n: int = 1000,
    module: Literal["numpy", "cupy", "jax"] = "numpy",
):
    if module == "numpy":
        import numpy as np
        xs = np.linspace(start, stop, n)
        return xs, f(xs)

    if module == "cupy":
        import cupy as cp
        xs = cp.linspace(start, stop, n)
        return xs, f(xs)

    if module == "jax":
        import jax.numpy as jnp
        xs = jnp.linspace(start, stop, n)
        return xs, f(xs)

    raise ValueError(module)


def implemented_numeric_function(name: str, implementation: Callable):
    from sympy.utilities.lambdify import implemented_function
    return implemented_function(sp.Function(name), implementation)


def ufuncify_numeric(
    args: Sequence[sp.Symbol],
    expr: Any,
    *,
    backend: Literal["f2py", "cython"] = "f2py",
    tempdir: str | None = None,
    **kwargs,
):
    from sympy.utilities.autowrap import ufuncify

    expr = prepare_numeric_expr(expr)

    if tempdir is not None:
        kwargs["tempdir"] = tempdir

    return ufuncify(list(args), expr, backend=backend, **kwargs)


def autowrap_numeric(
    expr: Any,
    *,
    args: Sequence[sp.Symbol] | None = None,
    backend: Literal["f2py", "cython"] = "f2py",
    language: Literal["F95", "C"] | None = None,
    tempdir: str | None = None,
    verbose: bool = False,
    helpers: Sequence[tuple[str, Any, Sequence[sp.Symbol]]] = (),
    **kwargs,
):
    from sympy.utilities.autowrap import autowrap

    expr = prepare_numeric_expr(expr)

    if args is not None:
        kwargs["args"] = list(args)
    if language is not None:
        kwargs["language"] = language
    if tempdir is not None:
        kwargs["tempdir"] = tempdir
    if helpers:
        kwargs["helpers"] = list(helpers)

    kwargs["verbose"] = verbose

    return autowrap(expr, backend=backend, **kwargs)


def binary_function_numeric(
    name: str,
    expr: Any,
    *,
    backend: Literal["f2py", "cython"] = "f2py",
    **kwargs,
):
    from sympy.utilities.autowrap import binary_function

    expr = prepare_numeric_expr(expr)
    return binary_function(name, expr, backend=backend, **kwargs)


def compare_backends(
    expr: Any,
    args: Sequence[sp.Symbol],
    values: Sequence[Any],
    *,
    backends: Sequence[Backend] = ("math", "numpy", "mpmath"),
    digits: int = 50,
):
    expr = prepare_numeric_expr(expr)
    ref = expr.evalf(digits, subs=dict(zip(args, values)))

    results = {}
    for backend in backends:
        f = lambdify_numeric(args, expr, backend=backend, cse=True, docstring_limit=0)
        try:
            results[backend] = f(*values)
        except Exception as exc:
            results[backend] = {"error": type(exc).__name__, "message": str(exc)}

    return {
        "reference_evalf": ref,
        "results": results,
    }


def benchmark_function(f: Callable, *args, number: int = 10000) -> float:
    import timeit
    return timeit.timeit(lambda: f(*args), number=number)


def numeric_path_recommendation(*, scalar: bool, repeated: bool, array: bool, gpu: bool, compiler: bool, high_precision: bool):
    if high_precision and scalar:
        return "lambdify(..., 'mpmath') or evalf for one-off diagnostics"
    if not repeated and scalar:
        return "expr.evalf(subs=...)"
    if gpu and array:
        return "lambdify(..., 'cupy') or lambdify(..., 'jax') depending stack"
    if compiler and array:
        return "ufuncify"
    if array:
        return "lambdify(..., 'numpy') or 'scipy'"
    if repeated:
        return "lambdify(..., 'math')"
    return "expr.evalf(subs=...)"
```

This harness encodes the numeric-bridge discipline: exact symbolic preparation, `evalf` for scalar diagnostics, backend-specific `lambdify`, custom numeric implementations, SymPy-object rejection at numeric-call boundaries, NumPy/CuPy/JAX vector sampling, compiled `ufuncify`/`autowrap` wrappers, `binary_function`, backend comparison, benchmarking, and deterministic path recommendation.

[1]: https://docs.sympy.org/latest/modules/numeric-computation.html "Numeric Computation - SymPy 1.14.0 documentation"
[2]: https://docs.sympy.org/latest/modules/numeric-computation.html?utm_source=chatgpt.com "Numeric Computation - SymPy 1.14.0 documentation"
[3]: https://docs.sympy.org/latest/modules/utilities/lambdify.html "Lambdify - SymPy 1.14.0 documentation"
[4]: https://docs.sympy.org/latest/modules/codegen.html "Code Generation - SymPy 1.14.0 documentation"

# 20) Code generation and deployment of symbolic results — agent-ready deep dive

Continuing the same advanced technical-doc pattern as the supplied reference artifact. 

## 20.0 Code-generation mental model

```text
symbolic model
  → assumptions/domain validation
  → targeted simplification / rewriting / approximation
  → CSE / codegen AST normalization
  → printer or codegen routine generation
  → compile/wrap/package/embed
  → symbolic + numeric regression tests
```

SymPy treats code generation as a first-class pipeline: the lower-level printing system emits target-language strings, `codegen` emits compilable source/header artifacts, and `autowrap`/`ufuncify` can compile and import callable binaries into Python. The official codegen docs describe `codegen` as generating directly compilable code, with a `Routine` abstraction that decides arguments, outputs, and return values. ([SymPy Documentation][1])

Core rule:

```text
Do not generate code from raw derivation expressions.
Generate code from a validated, normalized, backend-targeted expression.
```

---

## 20.1 Codegen stack map

| Layer                     |                                                               API | Output                              | Use case                                    |
| ------------------------- | ----------------------------------------------------------------: | ----------------------------------- | ------------------------------------------- |
| code string printer       |  `ccode`, `fcode`, `pycode`, `jscode`, `octave_code`, `rust_code` | string                              | snippets, assignments, embedded kernels     |
| code AST                  | `Assignment`, `CodeBlock`, `Variable`, `FunctionDefinition`, etc. | SymPy codegen AST                   | structured code blocks, CSE assignments     |
| routine generator         |                                         `codegen`, `make_routine` | source/header file strings or files | compilable functions                        |
| Python binary wrapper     |                                                        `autowrap` | Python callable                     | compile/import scalar or array routine      |
| NumPy ufunc wrapper       |                                                        `ufuncify` | NumPy ufunc / ufunc-like callable   | vectorized compiled elementwise kernel      |
| callable from expressions |                                                        `lambdify` | Python function                     | fast pure Python/numeric backend            |
| low-level full control    |                               subclass printers / code generators | custom source                       | embedded systems, DSLs, restricted runtimes |

---

## 20.2 Pre-codegen expression preparation

## 20.2.1 Reject unresolved symbolic nodes

```python
import sympy as sp

x, y, z = sp.symbols("x y z")

def reject_unresolved_for_codegen(expr: sp.Basic) -> sp.Basic:
    expr = sp.sympify(expr)
    bad = (sp.Integral, sp.Derivative, sp.Limit, sp.Sum, sp.Product)
    hits = [cls.__name__ for cls in bad if expr.has(cls)]
    if hits:
        raise ValueError(f"unresolved symbolic nodes for codegen: {hits}: {expr}")
    return expr
```

Reject or explicitly lower:

```text
Derivative → symbolic differentiation, finite difference, or external callback
Integral   → closed form, quadrature kernel, or external callback
Sum        → closed form, generated loop, or explicit summation
Piecewise  → complete branch structure
RootOf     → numeric approximation, callback, or target runtime support
UndefinedFunction → user_functions mapping / rewrite / callback
```

## 20.2.2 Ensure `Piecewise` totality

```python
def ensure_piecewise_default(expr: sp.Basic) -> sp.Basic:
    expr = sp.sympify(expr)
    for pw in expr.atoms(sp.Piecewise):
        if not pw.args or pw.args[-1][1] != True:
            raise ValueError(f"Piecewise lacks default True branch: {pw}")
    return expr
```

Several printers generate conditionals or masks for `Piecewise`; docs for code printers note that missing default branches raise because generated code may otherwise fail to produce a value. ([SymPy Documentation][2])

## 20.2.3 Normalize for numeric code

```python
def prepare_expr_for_codegen(expr: sp.Basic, *, force: bool = False) -> sp.Basic:
    expr = reject_unresolved_for_codegen(expr)
    expr = ensure_piecewise_default(expr)

    expr = sp.cancel(sp.together(expr))
    expr = sp.trigsimp(expr)
    expr = sp.powsimp(expr, combine="exp", deep=True, force=force)

    return expr
```

Production policy:

```text
rational form:
  cancel(together(expr))

trig/hyperbolic cleanup:
  trigsimp(expr)

power/log cleanup:
  powsimp(..., force=False)
  powdenest/logcombine only with domain guarantees

large repeated subexpressions:
  cse(expr)

target-specific numerics:
  optimize(expr, optims_c99), e.g. exp(x)-1 → expm1(x)
```

---

## 20.3 Common subexpression elimination: `cse`

## 20.3.1 Basic API

```python
replacements, reduced = sp.cse(expr)

replacements
# [(x0, ...), (x1, ...)]

reduced
# [reduced_expr]
```

Full surface:

```python
sp.cse(
    exprs,
    symbols=None,
    optimizations=None,
    postprocess=None,
    order="canonical",
    ignore=(),
    list=True,
)
```

`cse` performs common-subexpression elimination over one expression or a list of expressions; the `symbols` argument must be an infinite iterator of symbols used for generated temporaries, and `order='canonical'` gives deterministic ordering at the cost of speed. ([SymPy Documentation][3])

## 20.3.2 CSE code-emission pattern

```python
from sympy.codegen.ast import Assignment

def cse_assignments(expr, *, prefix="x"):
    temps = sp.numbered_symbols(prefix)
    replacements, reduced = sp.cse(expr, symbols=temps)

    assignments = [Assignment(sym, val) for sym, val in replacements]
    result = reduced[0] if len(reduced) == 1 else reduced
    return assignments, result
```

## 20.3.3 Multi-output CSE

```python
exprs = [
    sp.sin(x + y)**2 + sp.cos(x + y),
    sp.exp(x + y) + sp.sin(x + y),
]

repls, reduced = sp.cse(exprs)
```

Use multi-output CSE when generating a vector, RHS system, residual block, Jacobian block, or multiple kernel outputs. Separate per-output CSE misses cross-output reuse.

## 20.3.4 CodeBlock CSE

```python
from sympy.codegen.ast import CodeBlock, Assignment

block = CodeBlock(
    Assignment(sp.Symbol("a"), sp.sin(x) + 1),
    Assignment(sp.Symbol("b"), sp.sin(x) - 1),
)

optimized_block = block.cse()
```

`CodeBlock.cse()` returns a new code block with common subexpressions extracted as assignments, and `CodeBlock.topological_sort()` sorts assignments so variables are assigned before use. ([SymPy Documentation][4])

Deployment rules:

```text
Use CSE:
  generated code kernels
  vector/matrix outputs
  repeated trig/exp/polynomial terms
  code emitted with compiler optimization disabled or weak

Avoid blind CSE:
  very small expressions
  expressions where compiler optimizes better
  highly branchy Piecewise code without inspection

Tune:
  order="canonical" for deterministic generated code
  order="none" for speed on huge expressions
```

---

## 20.4 Code printers

## 20.4.1 C printer: `ccode`

```python
from sympy import ccode
from sympy.codegen.ast import Assignment

expr = sp.sin(x) + sp.cos(y)**2

ccode(expr)
ccode(expr, assign_to="out")
ccode(Assignment(sp.Symbol("out"), expr))
ccode(expr, standard="C99")
```

C printers map known functions to standard C functions; C99 has broader known-function coverage including `erf`, `erfc`, `expm1`, `log1p`, `tgamma`, `lgamma`, `fma`, `hypot`, and more. The C printer supports `assign_to`, custom `user_functions`, and target standards. ([SymPy Documentation][2])

### C custom function mapping

```python
f = sp.Function("f")

custom = {
    "f": "f_impl",
    "Abs": [
        (lambda arg: arg.is_integer, "abs"),
        (lambda arg: not arg.is_integer, "fabs"),
    ],
}

ccode(f(sp.Abs(x)), user_functions=custom)
```

### C `Piecewise`

```python
pw = sp.Piecewise((x + 1, x > 0), (x, True))
print(ccode(pw, assign_to="out"))
```

---

## 20.4.2 Fortran printer: `fcode`

```python
from sympy import fcode

fcode(expr)
fcode(expr, assign_to="out", source_format="free")
fcode(expr, standard=2003)
fcode(expr, strict=False)
fcode(expr, allow_unknown_functions=True)
```

Fortran printers are useful for scientific kernels, f2py workflows, Fortran modules/subroutines, and high-performance numerical environments. Use `strict=True` behavior to fail early on unsupported constructs; use `allow_unknown_functions=True` only when the target environment supplies the function.

---

## 20.4.3 Python printer: `pycode`

```python
from sympy import pycode

pycode(sp.sin(x) + 1)
pycode(sp.tan(x), fully_qualified_modules=True)
```

Use `pycode` for textual Python emission. Use `lambdify` for executable Python-callable generation.

```text
pycode:
  source text

lambdify:
  callable with backend namespace
```

---

## 20.4.4 JavaScript printer: `jscode`

```python
from sympy import jscode

jscode(sp.sin(x))
# Math.sin(x)

jscode(sp.sin(x), assign_to="s")
```

`jscode(expr, assign_to=None, **settings)` converts expressions to JavaScript, maps functions to `Math.*` where known, supports `user_functions`, emits conditionals for `Piecewise`, and supports `Indexed` loops with `contract=True/False`. ([SymPy Documentation][2])

```python
jscode(sp.Piecewise((x + 1, x > 0), (x, True)), assign_to="tau")
```

Deployment warning:

```text
JavaScript number model:
  IEEE double only

Unsupported special functions:
  map through user_functions or rewrite

Browser deployment:
  validate NaN/Infinity branch behavior
```

---

## 20.4.5 Octave/Matlab printer: `octave_code`

```python
from sympy import octave_code

octave_code(sp.sin(x).series(x).removeO())
octave_code(sp.sin(sp.pi*x*y), assign_to="s")
```

Octave/Matlab printing uses elementwise operations between scalar symbols by default because vectorized code is common in Octave; matrix products and matrix powers require `MatrixSymbol`. Matrix outputs, `Piecewise`, custom functions, and indexed loops are supported. ([SymPy Documentation][2])

```python
n = sp.Symbol("n", integer=True, positive=True)
A = sp.MatrixSymbol("A", n, n)

octave_code(3*sp.pi*A**3)
# matrix product/power form
```

Deployment rules:

```text
Symbol * Symbol:
  elementwise .*

MatrixSymbol * MatrixSymbol:
  matrix *

HadamardProduct:
  explicit componentwise matrix product

Piecewise:
  logical masks by default; inline=False for if/else
```

---

## 20.4.6 Rust printer: `rust_code`

```python
from sympy import rust_code

rust_code(sp.sin(x), assign_to="s")
rust_code(sp.Piecewise((x + 1, x > 0), (x, True)), assign_to="tau")
```

`rust_code` emits Rust-style expressions such as `x.sin()`, supports `user_functions`, prints `Piecewise` as `if` expressions when assigned, and supports `Indexed` loop-style assignment behavior. ([SymPy Documentation][2])

Deployment rules:

```text
Validate:
  powi vs powf output
  f64 literal formatting
  crate/runtime dependencies for custom math
  generated code under rustc tests
```

---

## 20.5 `codegen`: compilable source/header generation

## 20.5.1 Import and basic API

```python
from sympy.utilities.codegen import codegen

[(c_name, c_code), (h_name, c_header)] = codegen(
    ("f", x + y*z),
    language="C99",
    prefix="kernel",
    header=True,
    empty=True,
)
```

`codegen` is not imported into the top-level SymPy namespace automatically; it must be imported from `sympy.utilities.codegen`. It generates source code for expressions in target languages; the utility currently covers C, C++, Fortran 77/90, Julia, Rust, and Octave/Matlab routines, with codegen internals built around language-agnostic `Routine` objects. ([SymPy Documentation][1])

## 20.5.2 Signature

```python
codegen(
    name_expr,
    language=None,
    prefix=None,
    project="project",
    to_files=False,
    header=True,
    empty=True,
    argument_sequence=None,
    global_vars=None,
    standard=None,
    code_gen=None,
    printer=None,
)
```

Key options:

```text
name_expr:
  ("function_name", expr) or list of such pairs

language:
  "C", "C89", "C99", "F95", "Rust", "Octave", etc.

prefix:
  generated filename prefix

to_files:
  False → return (filename, code) tuples
  True  → write files

header:
  generate header/interface when supported

argument_sequence:
  explicit argument ordering
  required for stable ABI/API

global_vars:
  variables used by expression but excluded from function signature

printer:
  custom printer instance
```

The docs specify that `argument_sequence` orders routine arguments and raises an error if required arguments are missing; redundant arguments are used without warning. `global_vars` removes listed variables from the generated function signature. ([SymPy Documentation][1])

## 20.5.3 Multiple outputs and `Eq`

```python
f_sym, g_sym = sp.symbols("f g")

outputs = [
    ("scalar_kernel", x + y),
    ("multi_out", [sp.Eq(f_sym, 2*x), sp.Eq(g_sym, y + 1)]),
]

files = codegen(outputs, "C99", header=False, empty=False)
```

For `Eq(lhs, rhs)` outputs, routine construction typically treats the left-hand side as an output argument or in-out argument; otherwise expressions often become return values. The docs show `make_routine` identifying `Eq(f, ...)` and `Eq(g, ...)` as output variables, and matrix output as an output argument. ([SymPy Documentation][1])

## 20.5.4 `make_routine`

```python
from sympy.utilities.codegen import make_routine

r = make_routine(
    "kernel",
    [sp.Eq(f_sym, 2*x), sp.Eq(g_sym, x + y)],
    argument_sequence=[x, y, f_sym, g_sym],
)
```

Use `make_routine` when you need to inspect routine arguments, outputs, result variables, local variables, and language-independent routine structure before dumping code.

---

## 20.6 `autowrap`: compile and import callable binaries

## 20.6.1 API

```python
from sympy.utilities.autowrap import autowrap

binary_func = autowrap(expr)
binary_func = autowrap(expr, backend="f2py")
binary_func = autowrap(expr, backend="cython")
binary_func = autowrap(expr, language="C", backend="cython")
binary_func = autowrap(expr, args=[x, y], tempdir="build/autowrap", verbose=True)
```

`autowrap(expr, language=None, backend='f2py', tempdir=None, args=None, flags=None, verbose=False, helpers=None, code_gen=None, **kwargs)` generates Python-callable binaries from a SymPy expression. The backend is `f2py` by default or `cython`; `tempdir` preserves generated source/wrapper files for inspection; and `args` controls argument order. ([SymPy Documentation][5])

## 20.6.2 Helpers

```python
helper = ("helper_func", 4*x, [x])

f = autowrap(
    3*x + sp.Function("helper_func")(y),
    args=[x, y],
    helpers=[helper],
    backend="cython",
)
```

Helpers define auxiliary compiled routines used inside the main expression. The docs show helper functions with both `f2py` and Cython backends. ([SymPy Documentation][5])

## 20.6.3 When *not* to use `autowrap`

The autowrap docs explicitly state it is not the best approach when deep speed/memory optimization is required—manual wrapper/toolchain work can do better—or when NumPy handles the array computation easily and binaries are not needed for another project. ([SymPy Documentation][5])

Deployment rules:

```text
Use autowrap:
  prototype compiled code quickly
  test generated binaries from Python
  package compiled kernels later
  inspect generated source via tempdir

Avoid autowrap:
  compilerless deployment
  pure Python wheels only
  full manual memory control required
  simple vectorized NumPy expressions
```

---

## 20.7 `ufuncify`: compiled NumPy-style elementwise kernels

## 20.7.1 API

```python
from sympy.utilities.autowrap import ufuncify

uf = ufuncify([x], sp.sin(x)/x)
uf = ufuncify([x, y], sp.sin(x*y) + x**2, backend="f2py")
uf = ufuncify([x], expr, backend="cython", tempdir="build/ufunc")
```

`ufuncify(args, expr, language=None, backend='numpy', tempdir=None, flags=None, verbose=False, helpers=None, **kwargs)` generates a binary function that supports broadcasting on NumPy arrays. With the default `numpy` backend it creates an actual `numpy.ufunc`; other backends produce “ufunc-like” functions requiring equal-length one-dimensional arrays and no implicit type conversion. ([SymPy Documentation][5])

Deployment rules:

```text
Use ufuncify:
  repeated array evaluation
  elementwise kernels
  loop fusion
  generated NumPy ufunc deployment

Prefer lambdify:
  small expressions
  compilerless environments
  fast iteration

Prefer autowrap:
  scalar / non-ufunc compiled callable
  custom loop/output behavior
```

---

## 20.8 `binary_function`: compiled code behind a SymPy function

```python
from sympy.utilities.autowrap import binary_function

f_bin = binary_function("f_bin", ((x - y)**25).expand())
expr2 = 2*f_bin(x, y)

expr2.evalf(30, subs={x: 1, y: 2})
```

`binary_function` returns a SymPy undefined-function object backed by compiled code, automating autowrap plus `implemented_function` attachment; the docs show the resulting object staying symbolic in expressions and evaluating numerically via `.evalf(..., subs=...)`. ([SymPy Documentation][5])

Use when:

```text
Need:
  symbolic function node in larger formulas
  compiled numeric implementation
  evalf-compatible custom kernel
```

---

## 20.9 Matrix code generation

## 20.9.1 Explicit `Matrix` output with printers

```python
M = sp.Matrix([[x**2, sp.sin(x), sp.ceiling(x)]])

sp.octave_code(M, assign_to="A")
```

Octave/Matlab and Julia code printers support matrix outputs using inline notation; when `assign_to` is a `MatrixSymbol`, dimensions must align. Matrix content can include any normally printable expression, including `Piecewise`. ([SymPy Documentation][2])

## 20.9.2 `MatrixSymbol` vs scalar symbols in matrix code

```python
n = sp.Symbol("n", integer=True, positive=True)
A = sp.MatrixSymbol("A", n, n)

sp.octave_code(3*sp.pi*A**3)
```

Octave/Matlab printing uses elementwise operations between ordinary symbols by default and matrix operations for `MatrixSymbol`; use `HadamardProduct` to explicitly request componentwise multiplication between matrix symbols. ([SymPy Documentation][2])

## 20.9.3 Matrix outputs in `make_routine` / `codegen`

```python
from sympy.utilities.codegen import make_routine

f_sym, g_sym = sp.symbols("f g")

routine = make_routine(
    "fcn",
    [
        x*y,
        sp.Eq(f_sym, 1),
        sp.Eq(g_sym, x + g_sym),
        sp.Matrix([[x, 2]]),
    ],
)
```

`make_routine` classifies plain expressions as results, `Eq` left-hand sides as output or in-out arguments, and matrices as output arguments where needed; the docs show a mixed scalar/matrix-output routine with input, output, in-out, and auto-named matrix output variables. ([SymPy Documentation][1])

## 20.9.4 Matrix solve nodes and printers

`MatrixSolve` appears in code-printer precedence tables, so matrix-solve expression nodes are recognized by the printing system, but agents should not assume every target language has a native linear-solve primitive or that printers emit optimal linear algebra calls. For deployment, either lower matrix solves explicitly to scalar assignments, call target-library routines manually, or generate a dedicated numerical linear-algebra wrapper. ([SymPy Documentation][2])

Deployment rules:

```text
Small fixed-size symbolic matrix:
  expand to scalar expressions, CSE, print assignments.

Large matrix algebra:
  do not emit expanded symbolic inverse.
  call BLAS/LAPACK/Eigen/NumPy/SciPy target routine manually.
  use MatrixSymbol for symbolic derivation only.

Matrix solve:
  avoid A.inv()*b in generated code.
  generate residual/Jacobian scalar kernels or external solver calls.
```

---

## 20.10 Indexed expressions and generated loops

```python
i = sp.Idx("i", 5)
A = sp.IndexedBase("A", shape=(5,))
B = sp.IndexedBase("B", shape=(5,))
C = sp.IndexedBase("C", shape=(5,))

rhs = A[i] + B[i]

sp.ccode(rhs, assign_to=C[i], contract=True)
sp.ccode(rhs, assign_to=C[i], contract=False)
```

Code printers can use `Indexed` objects to emit loops when `contract=True`; with `contract=False`, they print only the indexed assignment expression that should be placed in an external loop. JavaScript, Rust, Julia, and Octave docs show the same `Indexed` loop-control pattern. ([SymPy Documentation][2])

Deployment rules:

```text
contract=True:
  printer emits loops when supported.

contract=False:
  caller owns loop structure.

Use contract=False when:
  embedding into custom kernels
  controlling memory layout
  vectorization/openmp/cuda/manual loops
```

---

## 20.11 Approximation and rewriting for efficient generated code

## 20.11.1 Numerically stable rewrites

```python
from sympy.codegen.rewriting import optimize, optims_c99

optimized = optimize(3*sp.exp(2*x) - 3, optims_c99)
# 3*expm1(2*x)
```

Use target-specific rewrites before code printing:

```text
exp(x) - 1      → expm1(x)
log(1 + x)      → log1p(x)
2**x            → exp2(x)
log(x)/log(2)   → log2(x)
fused patterns   → fma where available
```

C99 printer known functions include `expm1`, `log1p`, `exp2`, `log2`, `fma`, and others, so optimized rewrites can map to target math-library functions. ([SymPy Documentation][2])

## 20.11.2 Polynomial and rational rewrites

```python
def numeric_codegen_rewrite(expr):
    expr = sp.sympify(expr)

    expr = sp.cancel(sp.together(expr))
    expr = sp.horner(expr, x) if expr.is_polynomial(x) else expr
    expr = sp.trigsimp(expr)
    expr = sp.powsimp(expr, combine="exp", deep=True, force=False)

    return expr
```

Use `horner` for polynomial evaluation when operation count and numerical stability improve.

## 20.11.3 Approximation boundary

```python
series_expr = sp.series(sp.sin(x)/x, x, 0, 8).removeO()
```

Use approximations deliberately:

```text
Taylor/series:
  fixed local approximation; track center/order/domain

nfloat:
  approximate constants; not exact formula

evalf:
  replace symbolic constants with Float; use only after exact derivation

RootOf/nroots:
  approximate algebraic roots for target language support
```

Deployment rule:

```text
Every approximation must carry:
  approximation type
  domain/range
  error/order/tolerance
  exact source expression
```

---

## 20.12 Generated-code testing

## 20.12.1 Symbolic equivalence tests

```python
def assert_symbolically_equivalent(a, b):
    delta = sp.cancel(sp.together(sp.sympify(a) - sp.sympify(b)))
    if delta == 0:
        return
    q = sp.sympify(a).equals(sp.sympify(b))
    if q is True:
        return
    raise AssertionError(f"not proved equivalent: {delta}")
```

Use when comparing pre-codegen and optimized expression variants.

## 20.12.2 Numeric regression tests

```python
def assert_numeric_close(expr, generated_fn, args, samples, *, tol=1e-12, backend="math"):
    ref_fn = sp.lambdify(args, expr, modules="mpmath")

    for values in samples:
        ref = ref_fn(*values)
        got = generated_fn(*values)
        if abs(float(ref) - float(got)) > tol:
            raise AssertionError((values, ref, got))
```

## 20.12.3 Property grid

```text
Test points:
  ordinary values
  zeros
  small magnitudes
  large magnitudes
  branch boundaries
  Piecewise boundaries
  singularity-adjacent values
  domain edges
  random samples
```

## 20.12.4 Compiled code smoke tests

```python
def smoke_autowrap(expr, args, samples):
    from sympy.utilities.autowrap import autowrap

    fn = autowrap(expr, args=args)
    for values in samples:
        fn(*values)
```

Deployment rule:

```text
Always test:
  exact formula equivalence where possible
  numeric generated output
  target compiler/runtime
  boundary conditions
  backend-specific branch behavior
  matrix shape/order/ABI
```

---

## 20.13 Deployment targets

## 20.13.1 Python package

```text
Recommended:
  lambdify for pure-Python/numpy functions
  autowrap/ufuncify if package build supports extensions
  generated source files committed only if build reproducibility requires it
  version-pin SymPy for regenerated kernels
```

## 20.13.2 C extension / native module

```text
Recommended:
  codegen → C99/F95 source
  autowrap for prototype
  manual build system for production
  explicit C ABI
  tests against Python reference
```

## 20.13.3 Simulation kernels

```text
Recommended:
  symbolic derivation of RHS/Jacobian/residuals
  CSE across vector outputs
  emit C/Fortran/Rust
  external integrator/solver calls generated kernels
  avoid symbolic matrix inverses
```

## 20.13.4 Embedded systems

```text
Recommended:
  restricted math-function set
  no dynamic allocation
  fixed precision
  Horner polynomial form
  no unsupported special functions
  pre-expanded scalar assignments
  no Python runtime dependency
```

## 20.13.5 Notebooks and reports

```text
Recommended:
  latex(expr)
  ccode/fcode snippets
  lambdify for validation plots
  autowrap for demonstration only if compiler available
```

---

## 20.14 Anti-pattern inventory

| Anti-pattern                                      | Failure mode                            | Correct pattern                                |
| ------------------------------------------------- | --------------------------------------- | ---------------------------------------------- |
| generating code from unsimplified raw derivation  | huge slow code                          | targeted simplification + CSE                  |
| `A.inv()*b` in generated code                     | expression explosion                    | external linear solve / scalar residual kernel |
| assuming printers optimize code                   | suboptimal `pow`, no CSE                | apply `cse`, `optimize`, `horner` first        |
| missing `Piecewise` default branch                | printer error / undefined runtime value | include `(expr, True)`                         |
| unsupported custom function                       | unknown call / error                    | `user_functions`, rewrite, or callback         |
| no explicit argument ordering                     | unstable ABI                            | `argument_sequence`, `args=[...]`              |
| using `autowrap` in compilerless deployment       | build failure                           | `lambdify` or prebuilt extension               |
| using `ufuncify` for tiny one-off expression      | compile overhead dominates              | `lambdify(..., "numpy")`                       |
| not preserving generated files while debugging    | opaque compiler failure                 | `tempdir=...`, `verbose=True`                  |
| treating JS/Rust/C code as exact SymPy expression | one-way projection                      | keep source expression metadata                |
| using floats before codegen                       | precision artifacts                     | exact symbolic constants until final lowering  |
| generating code without tests                     | silent numerical drift                  | symbolic + numeric regression                  |
| no backend-specific branch tests                  | `Piecewise`, NaN, Inf mismatch          | sample boundary cases                          |
| no version metadata                               | non-reproducible regeneration           | store SymPy version + options                  |

---

## 20.15 Testing matrix

```python
def test_cse_rebuild():
    expr = (x + y)**2 + sp.sin(x + y)
    repls, reduced = sp.cse(expr)
    rebuilt = reduced[0].xreplace(dict(reversed(repls))) if False else None
```

Recommended matrix:

```text
Expression classes:
  polynomial
  rational
  trig/exponential
  Piecewise
  Matrix output
  Indexed loop
  custom Function
  special Function
  RootOf/numeric approximation
  derivative/integral rejection

Targets:
  C99 printer
  Fortran free form
  Python printer
  JavaScript printer
  Octave/Matlab printer
  Rust printer
  codegen C/F95
  autowrap f2py/cython
  ufuncify numpy/f2py/cython

Validation:
  symbolic equivalence
  numeric random regression
  boundary-value regression
  generated source compiles
  function signature stable
  matrix shape stable
  no unresolved nodes
  no unsupported functions
```

---

## 20.16 Minimal code-generation harness

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Literal, Sequence

import sympy as sp

from sympy.codegen.ast import Assignment, CodeBlock
from sympy.utilities.codegen import codegen, make_routine


CodeTarget = Literal["c", "fortran", "python", "javascript", "octave", "rust"]
CompiledBackend = Literal["f2py", "cython"]
UfuncBackend = Literal["numpy", "f2py", "cython"]


@dataclass(frozen=True)
class CodegenAudit:
    expr: sp.Basic
    free_symbols: tuple[sp.Symbol, ...]
    operation_count: int
    has_piecewise: bool
    has_unresolved_calculus: bool
    has_undefined_functions: bool
    cse_temporaries: int


@dataclass(frozen=True)
class GeneratedCodeBundle:
    expr: sp.Basic
    c: str
    fortran: str
    python: str
    javascript: str
    octave: str
    rust: str


def codegen_audit(expr: Any) -> CodegenAudit:
    from sympy.core.function import AppliedUndef

    expr = sp.sympify(expr)
    repls, _ = sp.cse(expr)

    return CodegenAudit(
        expr=expr,
        free_symbols=tuple(sorted(expr.free_symbols, key=str)),
        operation_count=int(sp.count_ops(expr)),
        has_piecewise=bool(expr.atoms(sp.Piecewise)),
        has_unresolved_calculus=any(
            expr.has(node)
            for node in (sp.Integral, sp.Derivative, sp.Limit, sp.Sum, sp.Product)
        ),
        has_undefined_functions=bool(expr.atoms(AppliedUndef)),
        cse_temporaries=len(repls),
    )


def reject_unresolved(expr: Any) -> sp.Basic:
    expr = sp.sympify(expr)
    bad_nodes = (sp.Integral, sp.Derivative, sp.Limit, sp.Sum, sp.Product)

    hits = [node.__name__ for node in bad_nodes if expr.has(node)]
    if hits:
        raise ValueError(f"unresolved symbolic nodes for code generation: {hits}")

    return expr


def ensure_piecewise_total(expr: Any) -> sp.Basic:
    expr = sp.sympify(expr)
    for pw in expr.atoms(sp.Piecewise):
        if not pw.args or pw.args[-1][1] != True:
            raise ValueError(f"Piecewise missing default True branch: {pw}")
    return expr


def prepare_codegen_expr(
    expr: Any,
    *,
    trig: bool = True,
    rational: bool = True,
    powers: bool = True,
    force_power_simplification: bool = False,
) -> sp.Basic:
    expr = reject_unresolved(expr)
    expr = ensure_piecewise_total(expr)

    if rational:
        expr = sp.cancel(sp.together(expr))

    if trig:
        expr = sp.trigsimp(expr)

    if powers:
        expr = sp.powsimp(
            expr,
            combine="exp",
            deep=True,
            force=force_power_simplification,
        )

    return expr


def apply_codegen_optimizations(expr: Any, *, c99: bool = True) -> sp.Basic:
    expr = prepare_codegen_expr(expr)

    if c99:
        from sympy.codegen.rewriting import optimize, optims_c99
        expr = optimize(expr, optims_c99)

    return expr


def cse_codeblock(expr: Any, *, result_symbol: str | sp.Symbol = "out", temp_prefix: str = "x") -> CodeBlock:
    expr = prepare_codegen_expr(expr)

    temps = sp.numbered_symbols(temp_prefix)
    repls, reduced = sp.cse(expr, symbols=temps)

    assignments = [Assignment(sym, val) for sym, val in repls]
    assignments.append(Assignment(sp.Symbol(str(result_symbol)), reduced[0]))

    return CodeBlock(*assignments)


def render_codeblock(block: CodeBlock, target: CodeTarget = "c") -> str:
    if target == "c":
        return sp.ccode(block)
    if target == "fortran":
        return sp.fcode(block, source_format="free")
    if target == "python":
        return sp.pycode(block)
    if target == "javascript":
        return sp.jscode(block)
    if target == "octave":
        return sp.octave_code(block)
    if target == "rust":
        return sp.rust_code(block)
    raise ValueError(f"unknown target: {target}")


def code_string(
    expr: Any,
    *,
    target: CodeTarget,
    assign_to: str | sp.Symbol | sp.MatrixSymbol | None = None,
    user_functions: dict | None = None,
) -> str:
    expr = prepare_codegen_expr(expr)

    kwargs = {}
    if user_functions is not None:
        kwargs["user_functions"] = user_functions

    if target == "c":
        return sp.ccode(expr, assign_to=assign_to, standard="C99", **kwargs)
    if target == "fortran":
        return sp.fcode(expr, assign_to=assign_to, source_format="free", **kwargs)
    if target == "python":
        if assign_to is not None:
            return sp.pycode(Assignment(sp.Symbol(str(assign_to)), expr))
        return sp.pycode(expr)
    if target == "javascript":
        return sp.jscode(expr, assign_to=assign_to, **kwargs)
    if target == "octave":
        return sp.octave_code(expr, assign_to=assign_to, **kwargs)
    if target == "rust":
        return sp.rust_code(expr, assign_to=assign_to, **kwargs)

    raise ValueError(f"unknown target: {target}")


def code_bundle(expr: Any, *, assign_to: str = "out") -> GeneratedCodeBundle:
    expr = apply_codegen_optimizations(expr)

    return GeneratedCodeBundle(
        expr=expr,
        c=sp.ccode(expr, assign_to=assign_to, standard="C99"),
        fortran=sp.fcode(expr, assign_to=assign_to, source_format="free"),
        python=sp.pycode(expr),
        javascript=sp.jscode(expr, assign_to=assign_to),
        octave=sp.octave_code(expr, assign_to=assign_to),
        rust=sp.rust_code(expr, assign_to=assign_to),
    )


def generate_source_files(
    name: str,
    expr: Any,
    *,
    language: str = "C99",
    prefix: str | None = None,
    to_files: bool = False,
    header: bool = True,
    argument_sequence: Sequence[sp.Symbol] | None = None,
    global_vars: Sequence[sp.Symbol] | None = None,
):
    expr = prepare_codegen_expr(expr)

    return codegen(
        (name, expr),
        language=language,
        prefix=prefix,
        to_files=to_files,
        header=header,
        argument_sequence=argument_sequence,
        global_vars=global_vars,
    )


def routine_for_expression(
    name: str,
    expr: Any,
    *,
    argument_sequence: Sequence[sp.Symbol] | None = None,
    global_vars: Sequence[sp.Symbol] | None = None,
    language: str = "F95",
):
    expr = prepare_codegen_expr(expr)

    return make_routine(
        name,
        expr,
        argument_sequence=argument_sequence,
        global_vars=global_vars,
        language=language,
    )


def compiled_callable(
    expr: Any,
    *,
    args: Sequence[sp.Symbol] | None = None,
    backend: CompiledBackend = "f2py",
    language: Literal["C", "F95"] | None = None,
    tempdir: str | None = None,
    verbose: bool = False,
    helpers: Sequence[tuple[str, Any, Sequence[sp.Symbol]]] = (),
):
    from sympy.utilities.autowrap import autowrap

    expr = prepare_codegen_expr(expr)

    kwargs: dict[str, Any] = {
        "backend": backend,
        "verbose": verbose,
    }

    if args is not None:
        kwargs["args"] = list(args)
    if language is not None:
        kwargs["language"] = language
    if tempdir is not None:
        kwargs["tempdir"] = tempdir
    if helpers:
        kwargs["helpers"] = list(helpers)

    return autowrap(expr, **kwargs)


def compiled_ufunc(
    args: Sequence[sp.Symbol],
    expr: Any,
    *,
    backend: UfuncBackend = "numpy",
    language: Literal["C", "F95"] | None = None,
    tempdir: str | None = None,
    verbose: bool = False,
):
    from sympy.utilities.autowrap import ufuncify

    expr = prepare_codegen_expr(expr)

    kwargs: dict[str, Any] = {
        "backend": backend,
        "verbose": verbose,
    }

    if language is not None:
        kwargs["language"] = language
    if tempdir is not None:
        kwargs["tempdir"] = tempdir

    return ufuncify(list(args), expr, **kwargs)


def binary_sympy_function(
    name: str,
    expr: Any,
    *,
    backend: CompiledBackend = "f2py",
    args: Sequence[sp.Symbol] | None = None,
):
    from sympy.utilities.autowrap import binary_function

    expr = prepare_codegen_expr(expr)

    kwargs = {"backend": backend}
    if args is not None:
        kwargs["args"] = list(args)

    return binary_function(name, expr, **kwargs)


def indexed_assignment_code(
    rhs: Any,
    lhs: Any,
    *,
    target: CodeTarget = "c",
    contract: bool = True,
) -> str:
    rhs = prepare_codegen_expr(rhs)

    if target == "c":
        return sp.ccode(rhs, assign_to=lhs, contract=contract)
    if target == "fortran":
        return sp.fcode(rhs, assign_to=lhs, source_format="free", contract=contract)
    if target == "javascript":
        return sp.jscode(rhs, assign_to=lhs, contract=contract)
    if target == "octave":
        return sp.octave_code(rhs, assign_to=lhs, contract=contract)
    if target == "rust":
        return sp.rust_code(rhs, assign_to=lhs, contract=contract)

    raise ValueError(f"unsupported indexed target: {target}")


def symbolic_equivalence_check(original: Any, transformed: Any) -> None:
    original = sp.sympify(original)
    transformed = sp.sympify(transformed)

    delta = sp.cancel(sp.together(original - transformed))
    if delta == 0:
        return

    q = original.equals(transformed)
    if q is True:
        return

    raise AssertionError(f"expressions not proved equivalent: {delta}")


def numeric_regression_check(
    expr: Any,
    fn: Callable,
    args: Sequence[sp.Symbol],
    samples: Sequence[Sequence[float]],
    *,
    tol: float = 1e-12,
) -> None:
    ref = sp.lambdify(args, prepare_codegen_expr(expr), modules="mpmath")

    for values in samples:
        expected = ref(*values)
        actual = fn(*values)
        if abs(float(expected) - float(actual)) > tol:
            raise AssertionError({
                "values": values,
                "expected": expected,
                "actual": actual,
                "tol": tol,
            })


def deployment_recommendation(
    *,
    target: Literal["notebook", "python", "numpy", "compiled_python", "c_project", "embedded", "simulation"],
    vectorized: bool = False,
    compiler_available: bool = False,
) -> str:
    if target == "notebook":
        return "Use latex/ccode snippets + lambdify for validation plots."
    if target == "python":
        return "Use lambdify unless native speed is required."
    if target == "numpy":
        return "Use lambdify(..., 'numpy'); consider ufuncify for heavy repeated elementwise kernels."
    if target == "compiled_python":
        return "Use autowrap for scalar compiled callable or ufuncify for array ufunc."
    if target == "c_project":
        return "Use codegen/ccode with explicit argument_sequence and external build system."
    if target == "embedded":
        return "Use scalar assignments, restricted math functions, C99/Rust printer, CSE, Horner, no dynamic allocation."
    if target == "simulation":
        return "Generate RHS/residual/Jacobian kernels; avoid symbolic inverse; CSE across vector outputs."
    return "Unknown target."
```

This harness encodes production codegen discipline: unresolved-node rejection, `Piecewise` totality checks, target-specific expression preparation, CSE code blocks, multi-language code-printer output, `codegen` source generation, routine introspection, compiled `autowrap`, `ufuncify`, `binary_function`, indexed loop assignment, symbolic equivalence checks, numeric regression testing, and deployment-target recommendations.

[1]: https://docs.sympy.org/latest/modules/utilities/codegen.html "Codegen - SymPy 1.14.0 documentation"
[2]: https://docs.sympy.org/latest/modules/printing.html "Printing - SymPy 1.14.0 documentation"
[3]: https://docs.sympy.org/latest/modules/rewriting.html "Term Rewriting - SymPy 1.14.0 documentation"
[4]: https://docs.sympy.org/latest/modules/codegen.html "Code Generation - SymPy 1.14.0 documentation"
[5]: https://docs.sympy.org/latest/modules/utilities/autowrap.html "Autowrap Module - SymPy 1.14.0 documentation"


# 21) Performance engineering and scalability — agent-ready deep dive

Continuing the same advanced technical-doc pattern as the supplied reference artifact. 

## 21.0 Performance mental model

SymPy performance is dominated by **expression-tree size**, **algorithm class**, **domain choice**, **simplification strategy**, and **numeric-boundary placement**. SymPy is symbolic-first: its own glossary frames SymPy as focused on symbolic functions while numerical libraries such as NumPy/SciPy are numeric-first, with bridges such as `lambdify()` and code generation for numerical execution. ([docs.sympy.org](https://docs.sympy.org/latest/explanation/glossary.html))

```python id="4mk2u3"
import sympy as sp

x, y, z = sp.symbols("x y z")
```

Core scalability policy:

```text id="s2w1o5"
derive once symbolically
  → simplify intentionally
  → choose data model deliberately: Expr / Poly / Matrix / DomainMatrix
  → CSE / targeted rewrites
  → lambdify / ufuncify / codegen
  → execute numerically many times
```

---

## 21.1 Expression swell

## 21.1.1 Definition

```text id="r8do5c"
expression swell =
  rapid growth in expression-tree size caused by expansion, substitution,
  differentiation, integration, solving, matrix operations, simplification,
  Groebner bases, exact algebra, or repeated rewrite passes.
```

High-risk operations:

```text id="fcp7bw"
expand((large sum)**n)
diff(large_product, x, high_order)
integrate(symbolic_expression_with_parameters)
simplify(large_expr)
trigsimp(..., method="fu"|"groebner")
groebner(large_system, order="lex")
Matrix.inv() on symbolic matrix
A.inv()*b instead of solve
.subs(...) repeated into growing expression
recursive .replace(...) with broad pattern
```

Detection:

```python id="t64u6c"
def expr_size(expr: sp.Basic) -> dict[str, int]:
    expr = sp.sympify(expr)
    return {
        "ops": int(sp.count_ops(expr)),
        "string_len": len(str(expr)),
        "node_count": sum(1 for _ in sp.preorder_traversal(expr)),
        "atoms": len(expr.atoms()),
        "free_symbols": len(expr.free_symbols),
    }
```

Use `count_ops` as the primary cheap complexity proxy; string length can be expensive for large expressions and is not semantically meaningful.

---

## 21.2 `count_ops`: cost proxy and rewrite gate

## 21.2.1 API

```python id="nfwl0z"
sp.count_ops(expr)
sp.count_ops(expr, visual=True)
expr.count_ops()
expr.count_ops(visual=True)
```

`count_ops(expr, visual=False)` returns an operation count; `visual=True` returns a symbolic expression showing operation classes such as `ADD`, `MUL`, `POW`, and function calls. SymPy’s simplification docs use `count_ops` as the default complexity measure for `simplify`, and the `simplify()` API accepts custom `measure` functions. ([docs.sympy.org](https://docs.sympy.org/latest/modules/simplify/simplify.html))

```python id="36l9c8"
expr = sp.sin(x)*x + sp.sin(x)**2

sp.count_ops(expr)
# 5

sp.count_ops(expr, visual=True)
# ADD + MUL + POW + 2*SIN
```

## 21.2.2 Cost guard

```python id="190ein"
def accept_if_cheaper(
    before: sp.Expr,
    after: sp.Expr,
    *,
    ratio: float = 1.25,
    measure=sp.count_ops,
) -> sp.Expr:
    before = sp.sympify(before)
    after = sp.sympify(after)

    b = measure(before)
    a = measure(after)

    if b == 0:
        return after

    return after if a <= ratio*b else before
```

## 21.2.3 Weighted cost for codegen

```python id="ukf6zk"
def weighted_codegen_ops(expr: sp.Expr) -> int:
    POW = sp.Symbol("POW")
    SIN = sp.Symbol("SIN")
    COS = sp.Symbol("COS")
    EXP = sp.Symbol("EXP")
    LOG = sp.Symbol("LOG")

    cost = sp.count_ops(expr, visual=True)
    cost = cost.subs({
        POW: 8,
        EXP: 6,
        LOG: 6,
        SIN: 4,
        COS: 4,
    })
    cost = cost.replace(sp.Symbol, type(sp.S.One))
    return int(cost)
```

Use weighted measures when target runtime cost differs from default symbolic operation count: embedded C may prefer multiplication over `pow`, GPU kernels may penalize branch-heavy `Piecewise`, and microcontrollers may penalize transcendental functions.

---

## 21.3 `simplify()` cost and targeted simplification

## 21.3.1 Why broad `simplify()` is risky

SymPy’s best-practices docs explicitly say to avoid `simplify()` in programmatic code when a specific transformation is known, because `simplify()` is heuristic, can be slow, and offers no stable output-form guarantee. The simplification tutorial similarly distinguishes the broad `simplify()` function from targeted simplification functions such as `factor`, `cancel`, and `trigsimp`, which have clearer contracts. ([docs.sympy.org](https://docs.sympy.org/latest/explanation/best-practices.html))

Bad production pattern:

```python id="g0uac9"
for expr in exprs:
    expr = sp.simplify(expr)   # broad, repeated, shape-unstable
```

Better:

```python id="u70ovw"
def normalize_rational_trig(expr: sp.Expr) -> sp.Expr:
    expr = sp.sympify(expr)
    expr = sp.cancel(sp.together(expr))
    expr = sp.trigsimp(expr)
    return expr
```

## 21.3.2 Targeted transform selection

```text id="m0yuru"
rational equality:
  cancel(together(expr))

polynomial coefficient extraction:
  expand(expr), collect(expr, x), Poly(expr, x)

human-readable polynomial:
  factor(expr), factor_terms(expr)

trig identities:
  trigsimp(expr), expand_trig(expr)

power/exponent normalization:
  powsimp(expr), powdenest(expr) with domain care

log compression:
  logcombine(expr) only with positivity/real-domain guarantees

radicals:
  radsimp(expr, symbolic=False) for safer denominator rationalization

combinatorics:
  combsimp(expr), gammasimp(expr)

codegen:
  cancel/together → trigsimp → powsimp → CSE → target-specific optimize
```

---

## 21.4 Avoid repeated simplification in loops

## 21.4.1 Anti-pattern

```python id="j8o0qk"
expr = 0
for term in terms:
    expr = sp.simplify(expr + term)
```

Failure mode:

```text id="4ytirs"
O(N) terms can cause repeated full-tree traversal,
progressive expression swell,
quadratic/cubic construction time,
unstable intermediate forms.
```

## 21.4.2 Accumulate first, simplify once

```python id="gd7g7i"
expr = sp.Add(*terms)
expr = sp.cancel(sp.together(expr))
```

## 21.4.3 Use unevaluated construction when needed

```python id="wex9m8"
expr = sp.Add(*terms, evaluate=False)
expr = sp.factor_terms(expr)
```

## 21.4.4 Batch CSE across all outputs

```python id="rc409h"
outputs = [rhs1, rhs2, jac11, jac12, jac21, jac22]
repls, reduced = sp.cse(outputs)
```

Multi-output CSE is often better than per-output CSE because common terms can be shared across residuals, RHS components, Jacobian entries, and generated kernels.

---

## 21.5 CSE and rewrite optimization

## 21.5.1 `cse`

```python id="35r97n"
replacements, reduced = sp.cse(expr)
replacements, reduced = sp.cse([expr1, expr2, expr3], order="canonical")
replacements, reduced = sp.cse(exprs, order="none")
```

`cse` performs common-subexpression elimination. Its docs include parameters such as `exprs`, `symbols`, `optimizations`, `postprocess`, `order`, `ignore`, and `list`; for large expressions where speed matters, the docs note that `order='none'` can be used instead of canonical ordering. ([docs.sympy.org](https://docs.sympy.org/latest/modules/simplify/simplify.html))

Tradeoff:

```text id="4rtn0m"
order="canonical":
  deterministic replacement ordering
  stable generated code
  slower for huge expressions

order="none":
  faster
  less deterministic
  useful for very large kernels
```

## 21.5.2 CSE plus codegen assignment emission

```python id="gkg7b9"
from sympy.codegen.ast import Assignment, CodeBlock

def cse_codeblock(outputs, *, temp_prefix="x", result_prefix="out"):
    temps = sp.numbered_symbols(temp_prefix)
    repls, reduced = sp.cse(outputs, symbols=temps, order="canonical")

    assignments = [Assignment(sym, val) for sym, val in repls]
    result_syms = [sp.Symbol(f"{result_prefix}{i}") for i in range(len(reduced))]
    assignments.extend(Assignment(s, e) for s, e in zip(result_syms, reduced))

    return CodeBlock(*assignments)
```

## 21.5.3 Target-specific rewrites

```python id="ucpmh6"
from sympy.codegen.rewriting import optimize, optims_c99

expr = 3*sp.exp(2*x) - 3
optimized = optimize(expr, optims_c99)
# 3*expm1(2*x)
```

SymPy’s codegen docs highlight target-specific rewrites such as `expm1` to avoid cancellation in `exp(x) - 1` near zero. Use these rewrites after symbolic simplification and before code printing. ([docs.sympy.org](https://docs.sympy.org/latest/modules/codegen.html))

---

## 21.6 Caching and memoization

## 21.6.1 Expression cache keys

SymPy expressions are immutable, and the core expression model satisfies `expr == expr.func(*expr.args)` for well-formed objects; immutable expression trees are hashable and suitable as dictionary keys in memory. ([docs.sympy.org](https://docs.sympy.org/latest/modules/core.html))

```python id="2h7ds9"
_cache: dict[sp.Basic, sp.Basic] = {}

def normalized_cached(expr: sp.Basic) -> sp.Basic:
    expr = sp.sympify(expr)
    if expr not in _cache:
        _cache[expr] = sp.cancel(sp.together(expr))
    return _cache[expr]
```

## 21.6.2 `functools.lru_cache`

```python id="4hq1qj"
from functools import lru_cache

@lru_cache(maxsize=2048)
def derivative_kernel(expr: sp.Expr, var: sp.Symbol) -> sp.Expr:
    return sp.factor(sp.diff(expr, var))
```

## 21.6.3 External persistent cache payload

```python id="tsnbsm"
def persistent_key(expr: sp.Basic) -> tuple[str, str]:
    expr = sp.sympify(expr)
    return (sp.__version__, sp.srepr(expr))
```

Deployment rules:

```text id="q04co1"
In-memory:
  use SymPy objects as keys.

Persistent cache:
  include SymPy version.
  include representation strategy.
  include assumptions/domain/generator order.
  include transform options.

Do not:
  use str(expr) alone for persistent cache.
  cache unbounded huge expressions without eviction.
```

## 21.6.4 Cache invalidation hazards

```text id="52gyk3"
same printed symbol, different assumptions:
  Symbol("x") != Symbol("x", positive=True)

same formula, different generator order:
  Poly(expr, x, y) != Poly(expr, y, x)

same expression, different domain:
  Poly(expr, x, domain=ZZ) vs domain=QQ

same transform, different force flag:
  powsimp(force=False) vs powsimp(force=True)
```

---

## 21.7 Choosing `Expr` vs `Poly` vs `Matrix` vs `DomainMatrix`

## 21.7.1 `Expr`

Use `Expr` for:

```text id="hvx8tm"
general symbolic formulas
calculus
transcendental functions
sets/booleans mixed into formulas
one-off algebra
lambdify/codegen source
```

Avoid `Expr` for repeated polynomial coefficient/exact-domain operations.

## 21.7.2 `Poly`

Use `Poly` for:

```text id="qe874u"
polynomial coefficient extraction
degree/leading-term queries
exact division / gcd / resultants / discriminants
factorization over domains
Groebner bases
polynomial systems
repeated polynomial manipulation
```

SymPy’s domain docs explain that the polys module uses explicit domains such as `ZZ`, `QQ`, polynomial rings, rational-function fields, algebraic fields, and finite fields, and that these domains are used internally by `Poly`. ([docs.sympy.org](https://docs.sympy.org/latest/modules/polys/domainsintro.html))

```python id="f00f6r"
P = sp.Poly(x**4 + 2*x**2 + 1, x, domain=sp.QQ)

P.degree()
P.coeff_monomial(x**2)
P.factor_list()
```

## 21.7.3 Explicit `Matrix`

Use `Matrix` for:

```text id="zuvuqh"
small/medium exact matrices
symbolic linear algebra
equation derivation
nullspaces/eigenvalues/ranks
mechanics/control symbolic matrices
```

Avoid:

```text id="krc15x"
large numeric linear algebra
large symbolic inverse
A.inv()*b for solving
```

Use:

```python id="n040m7"
A.solve(b)
A.LUsolve(b)
sp.linsolve((A, b), *vars)
```

## 21.7.4 `DomainMatrix`

Use `DomainMatrix` for:

```text id="56r84o"
exact-domain matrix algorithms
polynomial/rational/integer coefficient matrices
lower-level solver internals
performance-critical exact linear algebra
```

SymPy’s domain introduction notes that domain objects and polynomial-domain machinery are more relevant for development and internal algorithms, but they also expose the exact coefficient domains used by polys. `DomainMatrix` is the matrix analogue: use it when the matrix has a known exact domain and performance matters. ([docs.sympy.org](https://docs.sympy.org/latest/modules/polys/domainsintro.html))

---

## 21.8 Assumptions reduce ambiguity and output size

## 21.8.1 Symbol construction

```python id="9pz3qd"
x = sp.Symbol("x")
xp = sp.Symbol("x", positive=True)
xr = sp.Symbol("x", real=True)
n = sp.Symbol("n", integer=True, nonnegative=True)
```

SymPy’s best-practices docs recommend using assumptions when known because many simplifications depend on them; they also warn to avoid recreating symbols with the same name but different assumptions. ([docs.sympy.org](https://docs.sympy.org/latest/explanation/best-practices.html))

## 21.8.2 Examples

```python id="6qm5cl"
sp.sqrt(x**2)
# sqrt(x**2)

sp.sqrt(xp**2)
# x

a = sp.Symbol("a")
ap = sp.Symbol("a", positive=True)

integrand = sp.exp(-a*x)
integrand_pos = sp.exp(-ap*x)
```

Assumptions can eliminate `Piecewise`, `Abs`, unevaluated integrals, branch conditions, and excessive conservative forms.

Performance rule:

```text id="jpau6w"
Declare assumptions early:
  positive, real, integer, nonzero, finite

Benefit:
  smaller expressions
  simpler integrals/limits
  fewer Piecewise branches
  safer powsimp/logcombine/powdenest
  cleaner generated code
```

---

## 21.9 Numeric acceleration: `lambdify`, `ufuncify`, JAX/CuPy

## 21.9.1 Numeric bridge selection

SymPy’s best-practices page says to separate symbolic and numeric code and avoid mixing SymPy expressions with NumPy arrays; it specifically warns against storing SymPy expressions in NumPy arrays and recommends `lambdify()` as the bridge from symbolic expressions to numerical array evaluation. ([docs.sympy.org](https://docs.sympy.org/latest/explanation/best-practices.html))

```python id="4rm0vg"
expr = sp.sin(x) / x

f_np = sp.lambdify(x, expr, modules="numpy")
f_mp = sp.lambdify(x, expr, modules="mpmath")
```

## 21.9.2 Speed path matrix

```text id="wr2g9u"
one-off scalar:
  expr.evalf(subs=...)

repeated scalar:
  lambdify(..., "math")
  lambdify(..., "mpmath") for high precision

vectorized CPU:
  lambdify(..., "numpy")
  lambdify(..., "scipy") for special functions

large arrays / limited function set:
  lambdify(..., "numexpr")

compiled elementwise:
  ufuncify

GPU:
  lambdify(..., "cupy") with CuPy arrays

accelerator/JIT/autodiff:
  lambdify(..., "jax") + jax.jit
```

SymPy’s numeric-computation docs explicitly compare `subs/evalf`, `lambdify`, NumPy-backed `lambdify`, `ufuncify`, CuPy, and JAX paths by speed/dependencies and describe `ufuncify` as generating binary functions that support broadcasting and can be faster than `subs/evalf` and `lambdify` for suitable array workloads. ([docs.sympy.org](https://docs.sympy.org/latest/modules/numeric-computation.html))

## 21.9.3 Compiled vector path

```python id="j9c53l"
from sympy.utilities.autowrap import ufuncify

uf = ufuncify([x], sp.sin(x)/x)
```

Use compiled paths only when build/runtime environment supports compilers and compile latency is amortized.

---

## 21.10 Benchmarking symbolic workflows

## 21.10.1 Time measurement

```python id="02qwjj"
import time
from dataclasses import dataclass

@dataclass(frozen=True)
class TimedResult:
    result: object
    seconds: float

def timed(fn, *args, **kwargs) -> TimedResult:
    start = time.perf_counter()
    result = fn(*args, **kwargs)
    end = time.perf_counter()
    return TimedResult(result=result, seconds=end - start)
```

## 21.10.2 Benchmark stages separately

```python id="rewh1m"
def benchmark_pipeline(expr, var):
    stages = {}

    stages["differentiate"] = timed(sp.diff, expr, var)
    d = stages["differentiate"].result

    stages["simplify"] = timed(lambda e: sp.cancel(sp.together(e)), d)
    s = stages["simplify"].result

    stages["cse"] = timed(sp.cse, s)
    stages["lambdify"] = timed(sp.lambdify, var, s, "numpy")

    return stages
```

Measure separately:

```text id="yk0xrb"
construction
differentiation
integration / solving
simplification
CSE
lambdify construction
compiled code generation
compiled build
numeric call latency
numeric throughput
memory footprint
```

## 21.10.3 Timeit for call latency

```python id="69lgw8"
import timeit

def bench_callable(f, args, *, number=10000):
    return timeit.timeit(lambda: f(*args), number=number)
```

## 21.10.4 Operation-count tracking

```python id="c61cz6"
def stage_metrics(name, expr):
    expr = sp.sympify(expr)
    return {
        "stage": name,
        "ops": sp.count_ops(expr),
        "nodes": sum(1 for _ in sp.preorder_traversal(expr)),
        "atoms": len(expr.atoms()),
        "string_len": len(str(expr)),
    }
```

---

## 21.11 Memory risks for large expression trees

## 21.11.1 Risk sources

```text id="dqx9jy"
Add/Mul/Pow expansion:
  combinatorial term growth

Matrix inverse/determinant:
  huge rational expressions

Groebner bases:
  basis explosion

Full simplification:
  multiple candidate expressions simultaneously

String printing:
  massive temporary strings

LaTeX/srepr:
  massive serialization overhead

CSE:
  replacements + reduced expressions exist simultaneously

lambdify:
  source-string/docstring generation can dominate
```

## 21.11.2 Memory-aware rules

```text id="fvw9l7"
Avoid:
  full expand unless coefficient extraction requires it
  full Matrix.inv for symbolic matrices
  repeated simplify
  huge str/latex/srepr in loops
  unbounded caches
  storing giant expressions in NumPy object arrays

Prefer:
  targeted local transforms
  Poly for polynomial structure
  DomainMatrix for exact-domain matrices
  CSE before codegen
  docstring_limit=0 in lambdify
  generator/streaming outputs where possible
```

`lambdify` docs state that for large expressions, rendering the generated function’s docstring can dominate construction time, and `docstring_limit=0` or negative values can render an ellipsis instead of the full expression. ([docs.sympy.org](https://docs.sympy.org/latest/modules/utilities/lambdify.html))

```python id="j7nbio"
f = sp.lambdify(
    (x, y),
    large_expr,
    modules="numpy",
    cse=True,
    docstring_limit=0,
)
```

---

## 21.12 Pipeline architecture: derive once, execute many

## 21.12.1 Recommended production pipeline

```text id="qwyvnl"
1. define symbols with assumptions
2. derive exact symbolic expression once
3. validate expression structure
4. choose normalization profile
5. CSE across all outputs
6. generate numeric callable/code once
7. execute numeric callable many times
8. cache artifacts with SymPy version + transform options
9. regression-test symbolic and numeric equivalence
```

## 21.12.2 Example

```python id="5lo8xv"
def build_symbolic_kernel():
    x = sp.Symbol("x", real=True)
    a = sp.Symbol("a", positive=True)

    expr = sp.diff(sp.exp(-a*x)*sp.sin(x), x)
    expr = sp.cancel(sp.together(expr))
    expr = sp.trigsimp(expr)

    return (x, a), expr


def compile_kernel():
    args, expr = build_symbolic_kernel()
    f = sp.lambdify(args, expr, modules="numpy", cse=True, docstring_limit=0)
    return args, expr, f
```

## 21.12.3 Bad request-loop architecture

```python id="skmm8e"
def request_handler_bad(x_value, a_value):
    x, a = sp.symbols("x a")
    expr = sp.diff(sp.exp(-a*x)*sp.sin(x), x)
    expr = sp.simplify(expr)
    return expr.subs({x: x_value, a: a_value}).evalf()
```

## 21.12.4 Good request-loop architecture

```python id="cpnrqv"
ARGS, EXPR, NUMERIC = compile_kernel()

def request_handler_good(x_value, a_value):
    return NUMERIC(x_value, a_value)
```

---

## 21.13 Optimization patterns

## Pattern A — rational canonicalization for equality/testing

```python id="4m5pjk"
def rational_normal(expr):
    return sp.cancel(sp.together(sp.sympify(expr)))
```

## Pattern B — cost-guarded factorization

```python id="xepdg4"
def factor_if_cheaper(expr):
    expr = sp.sympify(expr)
    candidate = sp.factor(expr)
    return accept_if_cheaper(expr, candidate, ratio=1.1)
```

## Pattern C — polynomial mode

```python id="y7dou7"
def poly_mode(expr, gens, *, domain=sp.QQ):
    expr = sp.sympify(expr)
    if expr.atoms(sp.Float):
        raise ValueError("Float atoms not allowed in exact Poly mode")
    return sp.Poly(expr, *gens, domain=domain)
```

## Pattern D — matrix solve instead of inverse

```python id="3p1xs3"
def solve_linear_symbolically(A, b):
    A = sp.Matrix(A)
    b = sp.Matrix(b)
    return A.solve(b)
```

## Pattern E — CSE across vector output

```python id="u9kgq8"
def cse_vector_output(outputs):
    return sp.cse(list(outputs), order="canonical")
```

## Pattern F — numeric callable cache

```python id="7f00f4"
from functools import lru_cache

@lru_cache(maxsize=128)
def compiled_callable_for_srepr(srepr_text, args_names):
    # production implementation should parse from controlled schema, not eval raw text
    raise NotImplementedError
```

Better: cache at object construction site, not by reparsing text.

---

## 21.14 Anti-pattern inventory

| Anti-pattern                                       | Failure mode                            | Correct pattern                                  |
| -------------------------------------------------- | --------------------------------------- | ------------------------------------------------ |
| `simplify()` in hot loop                           | repeated expensive heuristics           | targeted simplify once                           |
| repeated `.subs(...).evalf()`                      | SymPy-speed numeric bottleneck          | `lambdify`/`ufuncify`                            |
| `expand()` before every step                       | expression swell                        | expand only for coefficient extraction           |
| `A.inv()*b`                                        | huge symbolic inverse                   | `A.solve(b)` / `linsolve`                        |
| using `Expr` for polynomial-heavy loop             | repeated domain/generator inference     | `Poly` with explicit domain                      |
| symbolic matrices for large numeric linear algebra | very slow                               | NumPy/SciPy/mpmath                               |
| missing assumptions                                | `Abs`, `Piecewise`, unevaluated results | declare `positive`, `real`, `integer`, `nonzero` |
| broad `Wild` replacement                           | expression explosion                    | constrained `Wild`, exact patterns               |
| lambdify huge expr with default docstring          | slow construction                       | `docstring_limit=0`                              |
| CSE after per-component codegen                    | missed cross-output reuse               | CSE across full output vector                    |
| unbounded expression cache                         | memory leak                             | LRU/maxsize/weakrefs                             |
| persistent cache without SymPy version             | stale/incompatible artifacts            | include `sp.__version__`                         |
| NumPy array of SymPy expressions                   | object-array slowdown                   | use SymPy Matrix/Array or lambdify               |
| JAX/CuPy path without backend tests                | unsupported function/runtime errors     | test eager/JIT/device arrays                     |
| using string length as main measure                | slow and misleading                     | `count_ops` / weighted measure                   |

---

## 21.15 Testing and regression matrix

```python id="erd45m"
def assert_no_expression_swell(before, after, *, max_ratio=2.0):
    b = sp.count_ops(before)
    a = sp.count_ops(after)
    if b and a > max_ratio*b:
        raise AssertionError(f"expression swell: {b} -> {a}")

def assert_symbolic_equivalent(a, b):
    delta = sp.cancel(sp.together(sp.sympify(a) - sp.sympify(b)))
    if delta == 0:
        return
    if sp.sympify(a).equals(sp.sympify(b)) is True:
        return
    raise AssertionError(f"not equivalent: {delta}")

def assert_numeric_equivalent(expr, fn, args, samples, *, tol=1e-12):
    ref = sp.lambdify(args, expr, modules="mpmath")
    for values in samples:
        expected = ref(*values)
        got = fn(*values)
        if abs(float(expected) - float(got)) > tol:
            raise AssertionError((values, expected, got))
```

Coverage targets:

```text id="72z174"
Symbolic:
  operation counts before/after
  expression-tree node counts
  exact equivalence
  no Float contamination
  no unresolved Derivative/Integral/Limit before numeric export

Performance:
  derivation time
  simplification time
  CSE time
  lambdify construction time
  numeric call latency
  vector throughput
  compiled build time

Scalability:
  increasing polynomial degree
  increasing matrix dimension
  increasing number of output equations
  increasing number of parameters
  memory growth
```

---

## 21.16 Minimal performance/scalability harness

```python id="13ps8w"
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from time import perf_counter
from typing import Any, Callable, Iterable, Literal, Sequence

import sympy as sp


@dataclass(frozen=True)
class ExprMetrics:
    expr: sp.Basic
    ops: int
    nodes: int
    atoms: int
    free_symbols: int
    string_len: int
    has_float: bool


@dataclass(frozen=True)
class StageResult:
    name: str
    result: Any
    seconds: float
    metrics: ExprMetrics | None


@dataclass(frozen=True)
class PipelineReport:
    stages: tuple[StageResult, ...]
    final_expr: sp.Basic
    final_metrics: ExprMetrics


def metrics(expr: Any) -> ExprMetrics:
    expr = sp.sympify(expr)
    return ExprMetrics(
        expr=expr,
        ops=int(sp.count_ops(expr)),
        nodes=sum(1 for _ in sp.preorder_traversal(expr)),
        atoms=len(expr.atoms()),
        free_symbols=len(expr.free_symbols),
        string_len=len(str(expr)),
        has_float=bool(expr.atoms(sp.Float)),
    )


def timed_stage(name: str, fn: Callable, *args, collect_metrics: bool = True, **kwargs) -> StageResult:
    start = perf_counter()
    result = fn(*args, **kwargs)
    seconds = perf_counter() - start

    m = None
    if collect_metrics:
        try:
            m = metrics(result)
        except Exception:
            m = None

    return StageResult(name=name, result=result, seconds=seconds, metrics=m)


def rational_normal(expr: Any) -> sp.Expr:
    return sp.cancel(sp.together(sp.sympify(expr)))


def targeted_normal(expr: Any) -> sp.Expr:
    expr = sp.sympify(expr)
    expr = sp.cancel(sp.together(expr))
    expr = sp.trigsimp(expr)
    expr = sp.powsimp(expr, combine="exp", deep=True, force=False)
    return expr


def weighted_codegen_measure(expr: sp.Expr) -> int:
    POW = sp.Symbol("POW")
    EXP = sp.Symbol("EXP")
    LOG = sp.Symbol("LOG")
    SIN = sp.Symbol("SIN")
    COS = sp.Symbol("COS")

    cost = sp.count_ops(expr, visual=True)
    cost = cost.subs({
        POW: 8,
        EXP: 6,
        LOG: 6,
        SIN: 4,
        COS: 4,
    })
    cost = cost.replace(sp.Symbol, type(sp.S.One))
    return int(cost)


def accept_if_cheaper(
    before: Any,
    candidate: Any,
    *,
    ratio: float = 1.25,
    measure: Callable[[sp.Expr], int | float] = sp.count_ops,
) -> sp.Expr:
    before = sp.sympify(before)
    candidate = sp.sympify(candidate)

    b = measure(before)
    c = measure(candidate)

    if b == 0:
        return candidate

    return candidate if c <= ratio*b else before


def factor_if_cheaper(expr: Any, *, ratio: float = 1.1) -> sp.Expr:
    expr = sp.sympify(expr)
    return accept_if_cheaper(expr, sp.factor(expr), ratio=ratio)


def cse_all(
    exprs: Sequence[Any],
    *,
    temp_prefix: str = "x",
    order: Literal["canonical", "none"] = "canonical",
):
    temps = sp.numbered_symbols(temp_prefix)
    return sp.cse([sp.sympify(e) for e in exprs], symbols=temps, order=order)


def require_exact(expr: Any) -> sp.Basic:
    expr = sp.sympify(expr)
    floats = expr.atoms(sp.Float)
    if floats:
        raise ValueError(f"Float contamination: {floats}")
    return expr


def choose_poly(expr: Any, gens: Sequence[sp.Symbol], *, domain=sp.QQ) -> sp.Poly:
    expr = require_exact(expr)
    return sp.Poly(expr, *gens, domain=domain)


def choose_matrix_solve(A: Any, b: Any) -> sp.Matrix:
    return sp.Matrix(A).solve(sp.Matrix(b))


def reject_numeric_backend_sympy_inputs(*values):
    if any(isinstance(v, sp.Basic) for v in values):
        raise TypeError("numeric backend received SymPy object")


def prepare_numeric_export(expr: Any) -> sp.Expr:
    expr = targeted_normal(expr)
    bad = (sp.Integral, sp.Derivative, sp.Limit, sp.Sum, sp.Product)
    if any(expr.has(node) for node in bad):
        raise ValueError(f"unresolved symbolic node remains: {expr}")

    for pw in expr.atoms(sp.Piecewise):
        if not pw.args or pw.args[-1][1] != True:
            raise ValueError(f"Piecewise lacks default True branch: {pw}")

    return expr


def compile_numpy_callable(args: Sequence[sp.Symbol] | sp.Symbol, expr: Any):
    expr = prepare_numeric_export(expr)
    return sp.lambdify(args, expr, modules="numpy", cse=True, docstring_limit=0)


def compile_mpmath_callable(args: Sequence[sp.Symbol] | sp.Symbol, expr: Any):
    expr = prepare_numeric_export(expr)
    return sp.lambdify(args, expr, modules="mpmath", cse=True, docstring_limit=0)


def compile_jax_callable(args: Sequence[sp.Symbol] | sp.Symbol, expr: Any, *, jit: bool = False):
    expr = prepare_numeric_export(expr)
    f = sp.lambdify(args, expr, modules="jax", cse=True, docstring_limit=0)
    if jit:
        import jax
        return jax.jit(f)
    return f


def compile_cupy_callable(args: Sequence[sp.Symbol] | sp.Symbol, expr: Any):
    expr = prepare_numeric_export(expr)
    return sp.lambdify(args, expr, modules="cupy", cse=True, docstring_limit=0)


def compile_ufunc(args: Sequence[sp.Symbol], expr: Any, *, backend: Literal["f2py", "cython"] = "f2py"):
    from sympy.utilities.autowrap import ufuncify
    expr = prepare_numeric_export(expr)
    return ufuncify(list(args), expr, backend=backend)


def benchmark_callable(fn: Callable, args: Sequence[Any], *, number: int = 10_000) -> float:
    import timeit
    return timeit.timeit(lambda: fn(*args), number=number)


def derive_once_pipeline(expr: Any, var: sp.Symbol) -> PipelineReport:
    stages = []

    s1 = timed_stage("differentiate", sp.diff, sp.sympify(expr), var)
    stages.append(s1)

    s2 = timed_stage("targeted_normal", targeted_normal, s1.result)
    stages.append(s2)

    s3 = timed_stage("factor_if_cheaper", factor_if_cheaper, s2.result)
    stages.append(s3)

    s4 = timed_stage("cse", sp.cse, s3.result, collect_metrics=False)
    stages.append(s4)

    final = s3.result
    return PipelineReport(
        stages=tuple(stages),
        final_expr=final,
        final_metrics=metrics(final),
    )


@lru_cache(maxsize=2048)
def cached_diff_normal(expr: sp.Expr, var: sp.Symbol) -> sp.Expr:
    return targeted_normal(sp.diff(expr, var))


def persistent_cache_key(expr: Any, *, namespace: str = "default") -> tuple[str, str, str]:
    expr = sp.sympify(expr)
    return (namespace, sp.__version__, sp.srepr(expr))


def assert_no_swell(before: Any, after: Any, *, max_ratio: float = 2.0) -> None:
    b = metrics(before).ops
    a = metrics(after).ops
    if b and a > max_ratio*b:
        raise AssertionError(f"operation-count swell: {b} -> {a}")


def assert_equivalent(a: Any, b: Any) -> None:
    a = sp.sympify(a)
    b = sp.sympify(b)

    delta = rational_normal(a - b)
    if delta == 0:
        return

    if a.equals(b) is True:
        return

    raise AssertionError(f"not symbolically equivalent: {delta}")


def performance_strategy(
    *,
    polynomial: bool = False,
    matrix: bool = False,
    numeric_many_times: bool = False,
    vectorized: bool = False,
    gpu: bool = False,
    compiler: bool = False,
) -> str:
    if polynomial:
        return "Use Poly with explicit gens/domain; avoid repeated Expr coefficient inference."
    if matrix and numeric_many_times:
        return "Derive symbolic matrices once; hand off numeric evaluation/linear algebra to NumPy/SciPy."
    if matrix:
        return "Use Matrix.solve/linsolve; avoid Matrix.inv()*b."
    if numeric_many_times and gpu:
        return "Use lambdify(..., 'jax' or 'cupy') and keep arrays on device."
    if numeric_many_times and compiler and vectorized:
        return "Use ufuncify for compiled elementwise vector kernels."
    if numeric_many_times and vectorized:
        return "Use lambdify(..., 'numpy') with cse=True, docstring_limit=0."
    if numeric_many_times:
        return "Use lambdify(..., 'math'/'mpmath') for scalar repeated calls."
    return "Use exact symbolic operations and evalf(subs=...) only for one-off diagnostics."
```

This harness encodes scalable symbolic discipline: expression metrics, timed stages, targeted normalization, cost-guarded rewrites, multi-output CSE, exactness validation, `Expr`→`Poly` routing, matrix solve routing, numeric export validation, backend-specific compilation, benchmarking, derive-once pipeline reporting, memoization, persistent cache keys, expression-swell assertions, symbolic equivalence checks, and strategy selection.


# 22) Best practices and common pitfalls — agent-ready deep dive

## 22.0 Operating contract

SymPy code should be written as **explicit symbolic object construction → targeted transformation → validated numeric/codegen boundary**. Avoid implicit symbol creation, accidental string parsing, float leakage, Python boolean coercion, and broad heuristic simplification in reusable code. SymPy’s own best-practices page emphasizes explicit `Symbol`/`symbols` usage, avoiding `var()` outside interactive work, avoiding string inputs, using exact numbers, separating symbolic and numeric code, and preferring targeted simplification over `simplify()` in programmatic code. ([SymPy Documentation][1])

```python
import sympy as sp

x, y = sp.symbols("x y", real=True)
n = sp.Symbol("n", integer=True, nonnegative=True)
a = sp.Symbol("a", positive=True)
```

---

## 22.1 Define symbols explicitly

### Correct constructors

```python
x = sp.Symbol("x")
x_pos = sp.Symbol("x", positive=True)
x, y, z = sp.symbols("x y z")
i, j, k = sp.symbols("i j k", integer=True)
f, g = sp.symbols("f g", cls=sp.Function)
xs = sp.symbols("x:10")
```

### Avoid

```python
sp.var("x")       # interactive convenience only
sp.S("x")         # parser, not symbol constructor
sp.sympify("x")   # parser, not symbol constructor
```

`var()` injects names into the caller namespace and is intended for interactive convenience, not programmatic code. `S()`/`sympify()` parse entire expressions and should not be used merely to create symbols; a string that is valid as a `Symbol` name may not be valid Python expression syntax. ([SymPy Documentation][1])

### Agent rule

```text
Library/module code:
  import sympy as sp
  x = sp.Symbol("x", assumptions...)
  x, y = sp.symbols("x y", assumptions...)

Interactive-only:
  var(...)
  from sympy import *
  sympy.abc
```

---

## 22.2 Centralize assumptions and symbol identity

Symbols with the same printed name but different assumptions are distinct SymPy symbols. This can produce visually confusing expressions like `z + z` where the two `z` objects are not equal. Declare assumptions early, keep one registry per mathematical model, and reuse caller-provided symbols rather than recreating same-named symbols inside helpers. ([SymPy Documentation][1])

```python
z_plain = sp.Symbol("z")
z_pos = sp.Symbol("z", positive=True)

assert z_plain != z_pos
```

### Preferred registry

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Symbols:
    x: sp.Symbol
    y: sp.Symbol
    n: sp.Symbol
    a: sp.Symbol

def make_symbols() -> Symbols:
    return Symbols(
        x=sp.Symbol("x", real=True),
        y=sp.Symbol("y", real=True),
        n=sp.Symbol("n", integer=True, nonnegative=True),
        a=sp.Symbol("a", positive=True),
    )
```

### Avoid hardcoded symbol names

```python
# Bad
def theta_operator(expr):
    z = sp.Symbol("z")
    return z * sp.diff(expr, z)

# Good
def theta_operator(expr: sp.Expr, z: sp.Symbol) -> sp.Expr:
    return z * sp.diff(expr, z)
```

Hardcoding symbol names makes helpers fail silently when callers use a different variable or a same-named symbol with different assumptions; SymPy’s docs show this exact pattern causing a derivative to be treated as zero. ([SymPy Documentation][1])

---

## 22.3 Use exact numbers by default

### Correct exact literals

```python
sp.Integer(2)
sp.Rational(1, 2)
sp.S(1) / 2
sp.pi
sp.E
sp.I
```

### Avoid early floats

```python
x + 0.5          # Float enters expression
x + 2/7          # Python computes float before SymPy sees it
sp.sin(math.pi)  # approximate pi
```

### Preferred

```python
x + sp.Rational(1, 2)
x + sp.Rational(2, 7)
x + sp.S(2) / 7
sp.sin(sp.pi)
```

SymPy’s docs recommend exact values when the value is known exactly. Floats can block exact algorithms, introduce cancellation artifacts, and make expressions fail to simplify; for example, `factor(x**2.0 - 1)` does not factor like `factor(x**2 - 1)`. They also show `sin(math.pi)` producing a tiny nonzero approximation while `sin(sympy.pi)` gives exact `0`. ([SymPy Documentation][1])

### Float audit

```python
def require_exact(expr: sp.Basic) -> sp.Basic:
    expr = sp.sympify(expr)
    floats = expr.atoms(sp.Float)
    if floats:
        raise ValueError(f"Float contamination: {floats}")
    return expr
```

---

## 22.4 Avoid `math` for symbolic work

```python
# Bad
import math
expr = sp.sin(math.pi * x)

# Good
expr = sp.sin(sp.pi * x)
```

The standard `math` module operates on finite-precision Python floats and cannot handle symbolic expressions. SymPy docs say using `math` alongside SymPy is virtually never necessary; SymPy has symbolic functions/constants and `evalf()` for arbitrary-precision numeric evaluation. ([SymPy Documentation][1])

### Boundary rule

```text
Symbolic layer:
  sp.sin, sp.cos, sp.exp, sp.log, sp.sqrt, sp.pi, sp.E

Numeric scalar layer:
  lambdify(..., "math") or float(expr.evalf(...))

Numeric array layer:
  lambdify(..., "numpy"|"scipy"|"jax"|"cupy")
```

---

## 22.5 Separate symbolic and numeric code

```python
# Symbolic derivation
x = sp.Symbol("x", real=True)
expr = sp.diff(sp.sin(x) * sp.exp(x**2), x)

# Numeric execution
f = sp.lambdify(x, expr, modules="numpy")
```

Do not pass SymPy expressions into NumPy/SciPy functions, and do not pass SymPy expressions into lambdified numeric functions. SymPy docs explicitly state that SymPy and NumPy operate under different paradigms, that SymPy is not designed to work with NumPy arrays directly, and that `lambdify()` is the intended bridge. ([SymPy Documentation][1])

### Bad

```python
import numpy as np

np.sin(x)       # NumPy does not understand SymPy Symbol
sp.sin(np.array([0.0, 1.0, 2.0]))  # SymPy function on NumPy array
```

### Good

```python
f = sp.lambdify(x, sp.sin(x), "numpy")
f(np.array([0.0, 1.0, 2.0]))
```

---

## 22.6 Handle `is_*` as three-valued logic

Assumption queries such as `expr.is_positive`, `expr.is_real`, and `expr.is_zero` return **Python** `True`, `False`, or `None`. `None` means unknown/maybe, not failure and not false. The assumptions docs explicitly say code using assumptions must handle all three cases. ([SymPy Documentation][2])

```python
def classify_positive(expr: sp.Expr) -> str:
    q = expr.is_positive
    if q is True:
        return "definitely positive"
    if q is False:
        return "definitely not positive"
    return "unknown"
```

### Avoid

```python
if expr.is_positive:
    ...
else:
    ...  # incorrectly combines False and None
```

### Correct strict validator

```python
def require_positive(expr: sp.Expr) -> sp.Expr:
    q = expr.is_positive
    if q is True:
        return expr
    if q is False:
        raise ValueError(f"definitely not positive: {expr}")
    raise ValueError(f"positivity unknown: {expr}")
```

### Correct permissive validator

```python
def reject_definitely_nonpositive(expr: sp.Expr) -> sp.Expr:
    if expr.is_positive is False:
        raise ValueError(f"not positive: {expr}")
    return expr  # allow True or None
```

---

## 22.7 Distinguish fuzzy booleans from symbolic booleans

```python
x = sp.Symbol("x")

x.is_positive   # None, fuzzy bool
x > 0           # symbolic relational: x > 0
```

Fuzzy booleans are Python-level `True`/`False`/`None`. Symbolic booleans are SymPy objects such as `x > 0`, `Eq(x, y)`, `And(...)`, `Or(...)`, and `Piecewise` conditions. `Piecewise((1, x > 0), (2, True))` is valid because `x > 0` is symbolic; `Piecewise((1, x.is_positive), ...)` fails for unknown `x` because `None` is not a symbolic Boolean. ([SymPy Documentation][3])

```python
expr = sp.Piecewise((1, x > 0), (0, True))
```

---

## 22.8 Avoid Python boolean operators on symbolic booleans

### Bad

```python
if x > 0:
    ...

cond = (x > 0) and (x < 1)
cond = not (x > 0)
cond = x < y < z
```

### Good

```python
cond = sp.And(x > 0, x < 1)
cond = (x > 0) & (x < 1)
cond = sp.Not(x > 0)
cond = sp.And(x < y, y < z)
```

A symbolic inequality like `x > 0` cannot be coerced to Python `bool`; SymPy docs show `bool(x > 0)` raising `TypeError: cannot determine truth value of Relational`. Use symbolic logic constructors or return `Piecewise` when symbolic branching is required. ([SymPy Documentation][1])

### Guardrail

```python
def symbolic_indicator(expr: sp.Expr, condition: sp.Boolean) -> sp.Expr:
    return sp.Piecewise((expr, condition), (0, True))
```

---

## 22.9 Equality: `=`, `==`, `Eq`, `.equals()`

### Four different concepts

```text
=             Python assignment
==            structural equality test
Eq(a, b)      symbolic equation object
a.equals(b)   mathematical-equivalence attempt
```

SymPy’s gotchas docs state that `=` is assignment, not mathematical equality; `==` tests exact structural equality, not symbolic mathematical equality; and symbolic equations should use `Eq(lhs, rhs)`. For mathematical equivalence tests, subtract and simplify/expand/trigsimp toward zero, or use `.equals()` as a heuristic/equivalence attempt. ([SymPy Documentation][4])

```python
lhs = (x + 1)**2
rhs = x**2 + 2*x + 1

lhs == rhs
# False

sp.Eq(lhs, rhs)
# Eq((x + 1)**2, x**2 + 2*x + 1)

sp.expand(lhs - rhs) == 0
# True

lhs.equals(rhs)
# True
```

### Robust equality helper

```python
def mathematically_equal(a: sp.Expr, b: sp.Expr) -> bool | None:
    a = sp.sympify(a)
    b = sp.sympify(b)

    if a == b:
        return True

    delta = sp.cancel(sp.together(a - b))
    if delta == 0:
        return True

    q = a.equals(b)
    if q is True:
        return True
    if q is False:
        return False

    return None
```

---

## 22.10 Avoid string-driven workflows

### Bad

```python
sp.expand("(x**2 + x)/x")
expr = sp.parse_expr("+".join(f"{i}*x_{i}" for i in range(10)))
expr_str = str(expr).replace("sin", "cos")
```

### Good

```python
expr = (x**2 + x) / x
sp.expand(expr)

terms = [i * sp.Symbol(f"x_{i}") for i in range(10)]
expr = sp.Add(*terms)

expr = expr.replace(sp.sin, sp.cos)
```

SymPy docs warn that support for string inputs in general SymPy functions is mostly accidental through `sympify`, that typos in strings can silently create undefined symbols/functions, and that string inputs always create symbols without caller-defined assumptions unless explicitly parsed with a dictionary. They also explicitly warn against manipulating expressions as strings because strings have no symbolic structure. ([SymPy Documentation][1])

### String assumption-loss bug

```python
z = sp.Symbol("z", positive=True)
sp.diff("z**2", z)
# 0  because parsed "z" is Symbol("z") without assumptions, not z
```

### Controlled parsing

```python
from sympy.parsing.sympy_parser import parse_expr, standard_transformations

z = sp.Symbol("z", positive=True)

expr = parse_expr(
    "z**2",
    local_dict={"z": z},
    transformations=standard_transformations,
)
```

---

## 22.11 Treat parsing as a security boundary

Both `sympify()` and `parse_expr()` use `eval` for string parsing and should not be used on unsanitized input. `parse_expr` accepts `local_dict`, `global_dict`, transformations, and `evaluate=False`; use the smallest grammar that fits, pass explicit symbols/functions, and reject or sandbox public user input outside SymPy. ([SymPy Documentation][5])

### Safer API boundary

```python
def coerce_sympy_object(obj) -> sp.Basic:
    if isinstance(obj, str):
        raise TypeError("string formulas must use explicit parse pipeline")
    return sp.sympify(obj, strict=True)
```

### Trusted parser only

```python
def parse_trusted_expr(text: str, symbols: dict[str, sp.Symbol]) -> sp.Expr:
    from sympy.parsing.sympy_parser import parse_expr, standard_transformations
    return parse_expr(
        text,
        local_dict=symbols,
        transformations=standard_transformations,
        evaluate=True,
    )
```

---

## 22.12 Prefer targeted transformations over broad heuristics

### Avoid default production simplification

```python
expr = sp.simplify(expr)  # broad heuristic; output shape unstable
```

### Use output-shape-driven transforms

```python
def rational_normal(expr: sp.Expr) -> sp.Expr:
    return sp.cancel(sp.together(sp.sympify(expr)))

def polynomial_expanded(expr: sp.Expr) -> sp.Expr:
    return sp.expand(sp.sympify(expr))

def polynomial_factored(expr: sp.Expr) -> sp.Expr:
    return sp.factor(sp.sympify(expr))

def trig_normal(expr: sp.Expr) -> sp.Expr:
    return sp.trigsimp(sp.sympify(expr))
```

SymPy docs describe `simplify()` as a general-purpose heuristic that tries many algorithms and chooses what seems simplest by a metric. They recommend targeted functions in programmatic usage because targeted functions have clearer behavior and output guarantees; examples include `factor()` for irreducible polynomial factorization and `cancel()` for reduced rational-function form. ([SymPy Documentation][1])

### Selection table

| Target                       | Function                    |
| ---------------------------- | --------------------------- |
| common denominator           | `together`                  |
| reduced rational form        | `cancel(together(expr))`    |
| polynomial factor form       | `factor`                    |
| polynomial terms             | `expand`, `collect`, `Poly` |
| trig identity reduction      | `trigsimp`                  |
| trig expansion               | `expand_trig`               |
| power simplification         | `powsimp`, `powdenest`      |
| log combination              | `logcombine`                |
| radical cleanup              | `radsimp`, `sqrtdenest`     |
| combinatorial simplification | `combsimp`, `gammasimp`     |
| generated-code size          | `cse`, targeted rewrites    |

---

## 22.13 Avoid unsafe `force=True` transformations

Power, logarithm, and radical identities are not valid over all complex values. SymPy’s simplification docs explain why identities like `sqrt(x)*sqrt(y) = sqrt(x*y)` and `(x**a)**b = x**(a*b)` are not generally valid without assumptions; `force=True` bypasses some assumption checks and should be reserved for externally guaranteed domains. ([SymPy Documentation][6])

```python
# Conservative
sp.powsimp(expr, force=False)

# Only with external proof: e.g. x, y nonnegative and exponent real
sp.powsimp(expr, force=True)
```

### Deployment rule

```text
force=True requires:
  documented domain precondition
  tests over boundary values
  no complex/negative-domain ambiguity
  codegen contract stating assumptions
```

---

## 22.14 Avoid symbolic sorting/comparison unless ordering is defined

```python
sorted([x, 0])  # can raise TypeError
```

Unknown symbolic inequalities cannot be reduced to Python truth values. If ordering is needed for display, use a structural key; if mathematical ordering is required, require numeric inputs or explicit assumptions. SymPy docs show `sorted([x, 0])` failing because sorting internally uses comparison. ([SymPy Documentation][1])

```python
sorted_exprs = sorted(exprs, key=sp.default_sort_key)
```

---

## 22.15 Recommended reusable API patterns

### Pattern A — accept symbols as parameters

```python
def derivative_operator(expr: sp.Expr, var: sp.Symbol) -> sp.Expr:
    expr = sp.sympify(expr)
    return sp.diff(expr, var)
```

### Pattern B — sympify non-string inputs only

```python
def normalize_input(expr) -> sp.Expr:
    if isinstance(expr, str):
        raise TypeError("string input rejected")
    return sp.sympify(expr, strict=False)
```

### Pattern C — exact numeric boundary

```python
def exact_rational(p: int, q: int) -> sp.Rational:
    return sp.Rational(p, q)
```

### Pattern D — symbolic/numeric separation

```python
def build_formula():
    x = sp.Symbol("x", real=True)
    expr = sp.diff(sp.sin(x) * sp.exp(x**2), x)
    expr = sp.factor(expr)
    return x, expr

x, expr = build_formula()
numeric = sp.lambdify(x, expr, "numpy")
```

### Pattern E — three-valued predicate handling

```python
def require_known_real(expr: sp.Expr) -> sp.Expr:
    q = expr.is_real
    if q is True:
        return expr
    if q is False:
        raise TypeError("definitely non-real")
    raise TypeError("realness unknown")
```

### Pattern F — symbolic branching

```python
def heaviside_like(x: sp.Expr) -> sp.Expr:
    return sp.Piecewise((1, x > 0), (0, True))
```

---

## 22.16 Pitfall matrix

| Pitfall                               | Symptom                              | Corrective action                               |
| ------------------------------------- | ------------------------------------ | ----------------------------------------------- |
| `var("x")` in library                 | namespace mutation                   | `Symbol("x")` / `symbols("x")`                  |
| `S("x")` to create symbol             | parser failure / assumption loss     | `Symbol("x")`                                   |
| same name, different assumptions      | visually identical distinct symbols  | central registry                                |
| hardcoded `Symbol("z")` inside helper | silent wrong derivative/substitution | pass symbol parameter                           |
| `x + 2/7`                             | float leakage                        | `x + Rational(2, 7)`                            |
| `math.pi`                             | approximate artifact                 | `sp.pi`                                         |
| `np.sin(x)`                           | NumPy cannot handle Symbol           | `sp.sin(x)` then `lambdify`                     |
| `sp.sin(np_array)`                    | SymPy not NumPy backend              | lambdified NumPy function                       |
| `if x > 0`                            | `TypeError`                          | `Piecewise`, assumptions, or numeric validation |
| `if expr.is_positive:`                | `None` mishandled                    | explicit `is True` / `is False` / unknown       |
| `x < y < z`                           | Python chained comparison            | `And(x < y, y < z)`                             |
| `==` as equation                      | structural equality only             | `Eq(lhs, rhs)`                                  |
| string formulas in functions          | typo-created symbols/functions       | explicit object construction                    |
| `parse_expr` on user input            | `eval` security risk                 | reject/sandbox/controlled parser                |
| `simplify()` in hot path              | slow/unstable shape                  | targeted transforms                             |

---

## 22.17 LLM-agent guardrail checklist

```text
Before emitting SymPy code:
  [ ] import sympy as sp
  [ ] define symbols explicitly
  [ ] include assumptions when known
  [ ] avoid var() except interactive snippets
  [ ] no math module in symbolic layer
  [ ] exact rationals for exact values
  [ ] no string parsing unless explicitly requested
  [ ] if parsing, pass local_dict and trusted-input warning
  [ ] no Python and/or/not on relationals
  [ ] handle is_* None
  [ ] use Eq for equations
  [ ] use targeted simplification
  [ ] separate symbolic derivation from numeric execution
  [ ] lambdify before NumPy/SciPy/JAX/CuPy arrays
  [ ] preserve domain assumptions for force=True transforms
```

---

## 22.18 Minimal best-practices harness

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

import sympy as sp
from sympy.parsing.sympy_parser import parse_expr, standard_transformations


@dataclass(frozen=True)
class SymPyLintReport:
    expr: sp.Basic
    free_symbols: tuple[sp.Symbol, ...]
    float_atoms: tuple[sp.Float, ...]
    has_string_origin: bool
    has_unresolved_calculus: bool
    has_piecewise_without_default: bool
    operation_count: int


def make_symbol(name: str, **assumptions) -> sp.Symbol:
    return sp.Symbol(name, **assumptions)


def make_symbols(names: str, **assumptions):
    return sp.symbols(names, **assumptions)


def reject_string(obj: Any) -> Any:
    if isinstance(obj, str):
        raise TypeError(
            "String input rejected. Use explicit Symbol construction or a trusted parse pipeline."
        )
    return obj


def sympify_nonstring(obj: Any, *, strict: bool = False) -> sp.Basic:
    reject_string(obj)
    return sp.sympify(obj, strict=strict)


def parse_trusted(
    text: str,
    *,
    local_dict: dict[str, Any],
    evaluate: bool = True,
) -> sp.Expr:
    return parse_expr(
        text,
        local_dict=local_dict,
        transformations=standard_transformations,
        evaluate=evaluate,
    )


def require_exact(expr: Any) -> sp.Basic:
    expr = sp.sympify(expr)
    floats = expr.atoms(sp.Float)
    if floats:
        raise ValueError(f"Float contamination detected: {floats}")
    return expr


def rational(p: int, q: int) -> sp.Rational:
    return sp.Rational(p, q)


def exact_pi() -> sp.Expr:
    return sp.pi


def symbolic_bool_and(*conditions) -> sp.Boolean:
    return sp.And(*conditions)


def symbolic_bool_or(*conditions) -> sp.Boolean:
    return sp.Or(*conditions)


def symbolic_bool_not(condition) -> sp.Boolean:
    return sp.Not(condition)


def piecewise_if(condition: sp.Boolean, then_expr: Any, else_expr: Any) -> sp.Piecewise:
    return sp.Piecewise((sp.sympify(then_expr), condition), (sp.sympify(else_expr), True))


def require_predicate(expr: sp.Expr, predicate: str) -> sp.Expr:
    q = getattr(expr, f"is_{predicate}")
    if q is True:
        return expr
    if q is False:
        raise TypeError(f"{expr} is definitely not {predicate}")
    raise TypeError(f"{expr}: {predicate} unknown")


def reject_if_predicate_false(expr: sp.Expr, predicate: str) -> sp.Expr:
    q = getattr(expr, f"is_{predicate}")
    if q is False:
        raise TypeError(f"{expr} is definitely not {predicate}")
    return expr


def equation(lhs: Any, rhs: Any, *, evaluate: bool = True) -> sp.Equality:
    return sp.Eq(sp.sympify(lhs), sp.sympify(rhs), evaluate=evaluate)


def mathematically_equal(a: Any, b: Any) -> bool | None:
    a = sp.sympify(a)
    b = sp.sympify(b)

    if a == b:
        return True

    delta = sp.cancel(sp.together(a - b))
    if delta == 0:
        return True

    q = a.equals(b)
    if q is True:
        return True
    if q is False:
        return False

    return None


def targeted_normal(expr: Any) -> sp.Expr:
    expr = sp.sympify(expr)
    expr = sp.cancel(sp.together(expr))
    expr = sp.trigsimp(expr)
    expr = sp.powsimp(expr, combine="exp", deep=True, force=False)
    return expr


def rational_normal(expr: Any) -> sp.Expr:
    return sp.cancel(sp.together(sp.sympify(expr)))


def polynomial_normal(expr: Any, *gens: sp.Symbol) -> sp.Expr:
    expr = sp.expand(sp.sympify(expr))
    if gens and not expr.is_polynomial(*gens):
        raise ValueError("expression is not polynomial in requested generators")
    return expr


def numeric_callable(args, expr: Any, *, backend: str = "numpy") -> Callable:
    expr = targeted_normal(expr)
    return sp.lambdify(args, expr, modules=backend, cse=True, docstring_limit=0)


def lint_expr(expr: Any, *, string_origin: bool = False) -> SymPyLintReport:
    expr = sp.sympify(expr)

    has_bad_piecewise = False
    for pw in expr.atoms(sp.Piecewise):
        if not pw.args or pw.args[-1][1] != True:
            has_bad_piecewise = True
            break

    return SymPyLintReport(
        expr=expr,
        free_symbols=tuple(sorted(expr.free_symbols, key=str)),
        float_atoms=tuple(sorted(expr.atoms(sp.Float), key=str)),
        has_string_origin=string_origin,
        has_unresolved_calculus=any(
            expr.has(node)
            for node in (sp.Integral, sp.Derivative, sp.Limit, sp.Sum, sp.Product)
        ),
        has_piecewise_without_default=has_bad_piecewise,
        operation_count=int(sp.count_ops(expr)),
    )


def assert_best_practice_ready(expr: Any) -> sp.Basic:
    report = lint_expr(expr)

    if report.float_atoms:
        raise ValueError(f"Float atoms present: {report.float_atoms}")

    if report.has_unresolved_calculus:
        raise ValueError("Unresolved calculus node remains")

    if report.has_piecewise_without_default:
        raise ValueError("Piecewise without default True branch")

    return report.expr
```

This harness encodes the central discipline: explicit symbols, no accidental string inputs, exact numbers, three-valued predicate handling, symbolic Boolean construction, equation/equality separation, targeted normalization, numeric backend separation, and linting for float leakage, unresolved symbolic nodes, and incomplete `Piecewise` branches.

[1]: https://docs.sympy.org/latest/explanation/best-practices.html "Best Practices - SymPy 1.14.0 documentation"
[2]: https://docs.sympy.org/latest/guides/assumptions.html "Assumptions - SymPy 1.14.0 documentation"
[3]: https://docs.sympy.org/latest/guides/booleans.html "Symbolic and fuzzy booleans - SymPy 1.14.0 documentation"
[4]: https://docs.sympy.org/latest/explanation/gotchas.html "Gotchas and Pitfalls - SymPy 1.14.0 documentation"
[5]: https://docs.sympy.org/latest/modules/parsing.html "Parsing - SymPy 1.14.0 documentation"
[6]: https://docs.sympy.org/latest/tutorials/intro-tutorial/simplification.html "Simplification - SymPy 1.14.0 documentation"

# 23) Testing, validation, and QA for SymPy-based systems — agent-ready deep dive

## 23.0 QA mental model

SymPy-based systems need layered validation:

```text
symbolic correctness
  → structural equality, mathematical equivalence, domain/assumption invariants

numeric correctness
  → lambdified reference evaluation, randomized samples, tolerance policies

generated-code correctness
  → generated target callable vs symbolic reference

domain correctness
  → branch cuts, singularities, assumptions, excluded values, Piecewise boundaries

artifact correctness
  → LaTeX/codegen snapshots, API payload schemas, version metadata

performance correctness
  → expression-size, simplification time, lambdify/codegen time, runtime throughput

reproducibility
  → SymPy version, Python version, optional dependencies, backend versions, seeds
```

SymPy’s own docs distinguish examples/doctests from dedicated tests: doctests should demonstrate API behavior for users, while pure testing logic belongs in `test_*.py` files. SymPy’s testing docs also document `XFAIL`, `@slow`, optional-dependency handling, and randomized numerical utilities, so agent-generated QA should separate normal tests, expected-failure tests, slow/performance tests, optional-backend tests, and randomized tests. ([SymPy Documentation][1])

---

## 23.1 Core test categories

| Category                      |                               Target | Primary assertion                                  |
| ----------------------------- | -----------------------------------: | -------------------------------------------------- |
| structural equality           |                exact expression tree | `actual == expected`                               |
| algebraic equivalence         |                 mathematical formula | `simplify/cancel/together(actual - expected) == 0` |
| symbolic predicate invariants |                   assumptions/domain | `expr.is_* is True/False/None` explicitly          |
| solver validation             |                   returned solutions | substitute into original equations                 |
| numeric regression            |                      function values | `abs(actual - expected) <= tol`                    |
| randomized symbolic/numeric   |                   broad sample space | seeded samples, skip singularities                 |
| generated-code validation     |      C/Fortran/Python/NumPy/JAX/etc. | generated callable vs symbolic reference           |
| branch/domain testing         | discontinuities, singularities, cuts | boundary grids and side-specific checks            |
| snapshot testing              |         LaTeX/codegen/display output | normalized text compare, version-pinned            |
| performance regression        |        time, memory, expression size | thresholded metrics                                |
| reproducibility               |            version/backend stability | metadata checks and pinned environments            |

---

## 23.2 Structural equality tests

## 23.2.1 Contract

Use structural equality when exact internal form is the API contract.

```python
import sympy as sp

x, y = sp.symbols("x y")

actual = sp.factor(x**2 - 1)
expected = (x - 1)*(x + 1)

assert actual == expected
```

Structural equality means the two expression trees match exactly; it is appropriate after canonicalizing to a known normal form, after targeted transformations with known output, for tree-rewrite tests, and for object-model invariants. It is not a proof of mathematical equivalence in arbitrary form.

## 23.2.2 Good structural targets

```text
Good structural tests:
  Symbol construction
  assumptions metadata
  exact Rational/Integer atoms
  targeted factor/cancel/collect output
  srepr-level rewrite tests
  printer output when output is intentionally frozen
  custom Function special values
  Piecewise branch tuples
  Poly coefficient dictionaries
```

## 23.2.3 Bad structural targets

```text
Bad structural tests:
  arbitrary simplify() output
  solver output order without normalization
  Add/Mul argument order without canonical handling
  mathematically equivalent but differently arranged expressions
  expressions involving dummy-bound symbols unless dummy_eq is used
```

## 23.2.4 Helpers

```python
def assert_structural_equal(actual, expected):
    assert actual == expected, (
        "structural mismatch\n"
        f"actual:   {actual!r}\n"
        f"expected: {expected!r}\n"
        f"actual srepr:   {sp.srepr(actual)}\n"
        f"expected srepr: {sp.srepr(expected)}"
    )


def assert_no_float_atoms(expr):
    expr = sp.sympify(expr)
    floats = expr.atoms(sp.Float)
    assert not floats, f"unexpected Float atoms: {floats}"
```

---

## 23.3 Mathematical equivalence tests

## 23.3.1 Zero-difference pattern

```python
def assert_expr_equal(actual, expected):
    actual = sp.sympify(actual)
    expected = sp.sympify(expected)

    delta = sp.cancel(sp.together(actual - expected))
    if delta == 0:
        return

    delta2 = sp.trigsimp(delta)
    if delta2 == 0:
        return

    q = actual.equals(expected)
    if q is True:
        return

    raise AssertionError(
        "mathematical equivalence not proven\n"
        f"actual: {actual}\n"
        f"expected: {expected}\n"
        f"delta: {delta}\n"
        f"trigsimp(delta): {delta2}\n"
        f"equals(): {q}"
    )
```

Use targeted equivalence strategies instead of blind `simplify()` whenever the expression class is known. SymPy’s simplification docs show that `simplify()` is heuristic, has a `ratio` cutoff, and uses a complexity measure such as `count_ops`; the same result can often be achieved by targeted functions like `trigsimp` followed by `cancel`. ([SymPy Documentation][2])

## 23.3.2 Equivalence by expression class

```text
Rational expressions:
  cancel(together(a - b)) == 0

Trigonometric identities:
  trigsimp(a - b) == 0

Polynomial expressions:
  Poly(expand(a - b), *gens).is_zero

Matrix expressions:
  simplify elementwise, or check A - B == zeros with normalized entries

Piecewise:
  compare branch conditions and expressions separately, or test by domain partition

Set outputs:
  compare Set objects structurally or use subset/intersection logic when supported

Equations:
  compare lhs-rhs normalized forms, not Eq object strings
```

## 23.3.3 Polynomial equality

```python
def assert_poly_equal(actual, expected, *gens, domain=sp.QQ):
    P = sp.Poly(sp.expand(actual - expected), *gens, domain=domain)
    assert P.is_zero, f"polynomial difference not zero: {P}"
```

## 23.3.4 Matrix equality

```python
def assert_matrix_equal(A, B):
    A = sp.Matrix(A)
    B = sp.Matrix(B)
    assert A.shape == B.shape

    D = A - B
    for entry in D:
        assert_expr_equal(entry, 0)
```

---

## 23.4 Assumption and fuzzy-boolean tests

SymPy’s core assumptions system returns fuzzy booleans: `True`, `False`, or `None`. `None` is expected and means “unknown,” so tests must assert all three cases deliberately rather than relying on Python truthiness. The assumptions docs also state that the core/old assumptions system is the widely used one in SymPy. ([SymPy Documentation][3])

```python
def assert_fuzzy(expr, attr, expected):
    q = getattr(expr, attr)
    assert q is expected, f"{expr}.{attr}: expected {expected}, got {q}"


x = sp.Symbol("x")
xp = sp.Symbol("xp", positive=True)
xr = sp.Symbol("xr", real=True)

assert_fuzzy(x.is_positive, "__class__", type(None))  # not recommended style
assert x.is_positive is None
assert xp.is_positive is True
assert xr.is_complex is True
```

Better table-driven tests:

```python
def test_assumption_table():
    cases = [
        (sp.Symbol("x"), "is_positive", None),
        (sp.Symbol("x", positive=True), "is_positive", True),
        (sp.Symbol("x", negative=True), "is_positive", False),
        (sp.Integer(0), "is_zero", True),
        (sp.I, "is_real", False),
    ]

    for expr, attr, expected in cases:
        assert getattr(expr, attr) is expected
```

Assumption-driven simplification tests:

```python
def test_sqrt_square_assumptions():
    x = sp.Symbol("x")
    xp = sp.Symbol("xp", positive=True)

    assert sp.sqrt(x**2) == sp.sqrt(x**2)
    assert sp.sqrt(xp**2) == xp
```

---

## 23.5 Solver-output validation

## 23.5.1 Substitute solutions into original equations

```python
def equation_to_zero(eq):
    eq = sp.sympify(eq)
    if isinstance(eq, sp.Equality):
        return sp.simplify(eq.lhs - eq.rhs)
    return eq


def assert_solution_satisfies(eqs, solution):
    if not isinstance(eqs, (list, tuple)):
        eqs = [eqs]

    for eq in eqs:
        residual = equation_to_zero(eq).subs(solution)
        assert_expr_equal(residual, 0)
```

## 23.5.2 Validate `solve(..., dict=True)` output

```python
def assert_solve_dicts(eqs, symbols, solutions):
    for sol in solutions:
        assert set(sol).issubset(set(symbols))
        assert_solution_satisfies(eqs, sol)
```

## 23.5.3 Validate `linsolve` / `nonlinsolve` tuple sets

```python
def assert_tuple_solution_set(eqs, symbols, solset):
    if solset is sp.S.EmptySet:
        return

    assert isinstance(solset, sp.FiniteSet)

    for item in solset:
        tup = item if isinstance(item, tuple) else (item,)
        sol = dict(zip(symbols, tup))
        assert_solution_satisfies(eqs, sol)
```

## 23.5.4 Validate ODE solutions

```python
def assert_ode_solution(ode, sol):
    ok, residual = sp.checkodesol(ode, sol)
    assert ok is True, residual
```

## 23.5.5 Validate inequalities by sampling and relation extraction

```python
def assert_inequality_solution_contains_samples(solution_condition, var, good_samples, bad_samples):
    for value in good_samples:
        assert bool(solution_condition.subs(var, value)) is True

    for value in bad_samples:
        assert bool(solution_condition.subs(var, value)) is False
```

---

## 23.6 Numeric regression tests

## 23.6.1 Lambdified function regression

```python
def assert_lambdified_close(expr, args, samples, *, backend="numpy", tol=1e-12):
    expr = sp.sympify(expr)

    f_test = sp.lambdify(args, expr, modules=backend)
    f_ref = sp.lambdify(args, expr, modules="mpmath")

    for values in samples:
        got = f_test(*values)
        expected = f_ref(*values)
        assert abs(float(got) - float(expected)) <= tol, {
            "values": values,
            "got": got,
            "expected": expected,
            "tol": tol,
        }
```

`lambdify` is SymPy’s bridge from symbolic expressions to fast numerical functions, and the docs state that it can target numerical libraries including `math`, `mpmath`, NumPy, SciPy, TensorFlow, JAX, and other backends. ([SymPy Documentation][4])

## 23.6.2 Reference-backend policy

```text
Reference backend:
  mpmath for scalar high-precision comparisons
  exact SymPy evalf for one-off scalar references
  NumPy for array-shape regression
  SciPy for special-function numeric compatibility
  generated compiled code compared against mpmath/SymPy reference
```

SymPy depends on `mpmath` for arbitrary-precision arithmetic and uses it under the hood when evaluating floating-point values with `evalf`, making it a natural high-precision scalar reference backend. ([SymPy Documentation][5])

## 23.6.3 Absolute/relative tolerance

```python
def assert_close(got, expected, *, atol=1e-12, rtol=1e-12):
    got = complex(got)
    expected = complex(expected)

    err = abs(got - expected)
    scale = max(1.0, abs(expected))

    assert err <= atol + rtol*scale, {
        "got": got,
        "expected": expected,
        "abs_error": err,
        "atol": atol,
        "rtol": rtol,
    }
```

Tolerance selection:

```text
Use exact equality:
  rational/integer symbolic output
  structural target forms
  algebraic normal forms

Use tight tolerance:
  high-precision scalar generated code checks
  deterministic closed-form numeric values

Use looser tolerance:
  branch-boundary values
  cancellation-prone expressions
  special functions
  GPU/JAX/CuPy float32 paths
```

---

## 23.7 Randomized numerical testing

SymPy exposes randomized numerical utilities in `sympy.core.random`, including `random_complex_number`, `verify_numerically`, and `test_derivative_numerically`. The older `sympy.testing.randtest` location is deprecated since SymPy 1.10; the current random-testing docs point to `sympy.core.random`. ([SymPy Documentation][6])

```python
from sympy.core.random import (
    seed,
    random_complex_number,
    verify_numerically,
    test_derivative_numerically,
)

def test_identity_randomized():
    seed(123)
    assert verify_numerically(sp.sin(x)**2 + sp.cos(x)**2, 1, x)
```

`verify_numerically(f, g, z, tol=..., a=..., b=..., c=..., d=...)` checks that two expressions agree at random complex values; the docs warn that it does not account for Floats with precision higher than 15 digits, so high-precision Float atoms can lead to misleading results. ([SymPy Documentation][7])

## 23.7.1 Safer randomized sampling with domain filters

```python
def random_rational_samples(var, *, count=20, low=-5, high=5, exclude=()):
    vals = []
    for i in range(count * 5):
        v = sp.Rational(low + i % (high - low + 1), 1)
        if all(sp.simplify(v - e) != 0 for e in exclude):
            vals.append(v)
        if len(vals) == count:
            break
    return vals


def assert_equal_on_samples(a, b, var, samples, *, digits=80, tol=1e-40):
    for s in samples:
        av = sp.N(a.subs(var, s), digits)
        bv = sp.N(b.subs(var, s), digits)
        assert abs(av - bv) <= tol, (s, av, bv)
```

## 23.7.2 Randomized derivative test

```python
def assert_derivative_numerically(expr, var):
    from sympy.core.random import test_derivative_numerically
    assert test_derivative_numerically(expr, var)
```

## 23.7.3 Sampling guardrails

```text
Randomized tests must:
  seed randomness
  avoid singularities
  avoid branch cuts unless intentionally tested
  test real and complex samples separately
  include exact deterministic edge cases
  not replace symbolic proof tests
```

---

## 23.8 Property-based testing with assumptions

## 23.8.1 Symbol-domain parametrization

```python
def symbol_cases(name="x"):
    return {
        "generic": sp.Symbol(name),
        "real": sp.Symbol(name, real=True),
        "positive": sp.Symbol(name, positive=True),
        "negative": sp.Symbol(name, negative=True),
        "integer": sp.Symbol(name, integer=True),
        "nonzero": sp.Symbol(name, nonzero=True),
    }
```

## 23.8.2 Assumption-sensitive property tests

```python
def test_sqrt_square_property_by_domain():
    xs = symbol_cases("x")

    assert sp.sqrt(xs["generic"]**2) == sp.sqrt(xs["generic"]**2)
    assert sp.sqrt(xs["positive"]**2) == xs["positive"]
    assert sp.sqrt(xs["real"]**2) == sp.Abs(xs["real"])
```

## 23.8.3 Property invariant templates

```text
Algebraic property:
  f(a + b) obeys known identity under assumptions

Derivative property:
  diff(integrate(f, x), x) equals f on domain

Solver property:
  every returned solution satisfies original equation

Series property:
  residual is O((x-x0)**n)

Matrix property:
  A * A.inv() == I for nonsingular sample/assumption set

Codegen property:
  generated function agrees with symbolic reference on valid domain

Simplification property:
  transformed expression is mathematically equivalent and not larger than threshold
```

## 23.8.4 Hypothesis-style input strategy skeleton

```python
# Optional external dependency pattern.
# Do not require Hypothesis unless the test suite declares it as optional.

def exact_small_rationals():
    for p in range(-5, 6):
        for q in range(1, 6):
            yield sp.Rational(p, q)
```

SymPy’s test-writing docs say optional-dependency tests should skip cleanly if the dependency is missing, using `sympy.external.import_module()` and skip markers rather than failing the test suite. ([SymPy Documentation][8])

---

## 23.9 Generated-code validation

## 23.9.1 Printer snapshot plus executable comparison

```python
def ccode_snapshot(expr, assign_to="out"):
    expr = sp.sympify(expr)
    return sp.ccode(expr, assign_to=assign_to, standard="C99")


def assert_generated_callable_matches(expr, fn, args, samples, *, tol=1e-12):
    ref = sp.lambdify(args, expr, "mpmath")

    for values in samples:
        expected = ref(*values)
        got = fn(*values)
        assert_close(got, expected, atol=tol, rtol=tol)
```

SymPy’s `codegen` module generates directly compilable code from expressions, and its `Routine` abstraction determines arguments, outputs, and return values; target-code QA should therefore validate both source text/signature shape and runtime numerical behavior. ([SymPy Documentation][9])

## 23.9.2 Autowrap / ufuncify smoke tests

```python
def assert_autowrap_matches(expr, args, samples, *, backend="cython", tol=1e-12):
    from sympy.utilities.autowrap import autowrap

    fn = autowrap(expr, args=args, backend=backend)
    assert_generated_callable_matches(expr, fn, args, samples, tol=tol)


def assert_ufunc_matches(expr, args, array_values, *, backend="f2py", tol=1e-12):
    from sympy.utilities.autowrap import ufuncify
    import numpy as np

    uf = ufuncify(args, expr, backend=backend)
    ref = sp.lambdify(args, expr, "numpy")

    got = uf(*array_values)
    expected = ref(*array_values)

    assert np.allclose(got, expected, atol=tol, rtol=tol)
```

SymPy’s codegen documentation describes `autowrap` and `ufuncify` as ways to generate compiled/imported numerical functions from SymPy expressions; compiled QA should include compiler availability, runtime execution, and numeric agreement. ([SymPy Documentation][10])

## 23.9.3 Matrix/vector generated-code validation

```python
def assert_matrix_numeric_close(expr_matrix, fn, args, samples, *, tol=1e-12):
    ref = sp.lambdify(args, expr_matrix, "numpy")

    for values in samples:
        expected = ref(*values)
        got = fn(*values)

        import numpy as np
        assert np.allclose(got, expected, atol=tol, rtol=tol)
```

## 23.9.4 Generated-code preflight

```python
def assert_codegen_ready(expr):
    expr = sp.sympify(expr)

    unresolved = (sp.Integral, sp.Derivative, sp.Limit, sp.Sum, sp.Product)
    assert not any(expr.has(node) for node in unresolved), expr

    for pw in expr.atoms(sp.Piecewise):
        assert pw.args and pw.args[-1][1] is True, f"Piecewise missing default: {pw}"

    from sympy.core.function import AppliedUndef
    assert not expr.atoms(AppliedUndef), f"undefined functions remain: {expr.atoms(AppliedUndef)}"
```

---

## 23.10 Branch cuts, singularities, assumptions, domains

## 23.10.1 Domain partitioning

```python
def test_points_around(points, *, eps=sp.Rational(1, 1000)):
    vals = []
    for p in points:
        vals.extend([p - eps, p, p + eps])
    return vals
```

Test categories:

```text
Singularities:
  denominator zeros
  poles of tan/log/gamma/zeta/special functions
  matrix determinant zeros
  solver excluded roots

Branch cuts:
  log negative real axis
  sqrt/rational powers
  inverse trig/hyperbolic
  Abs/sign/arg

Piecewise:
  every condition boundary
  default branch
  overlapping branches
  impossible branches

Assumptions:
  generic
  real
  positive
  negative
  integer
  nonzero
  finite/infinite

Domains:
  real vs complex
  open/closed intervals
  discrete integer domains
  finite fields/modular domains
```

SymPy’s gotchas docs warn that exact rationals can avoid float artifacts in numerical checks and show that simplification can be a stronger validation than approximate evaluation for identities. ([SymPy Documentation][11])

## 23.10.2 Singularity-aware rational samples

```python
def denominator_roots(expr, var):
    num, den = sp.together(expr).as_numer_denom()
    try:
        return set(sp.solve(sp.Eq(den, 0), var))
    except Exception:
        return set()


def safe_samples_for_expr(expr, var, candidates):
    excluded = denominator_roots(expr, var)
    return [v for v in candidates if all(sp.simplify(v - e) != 0 for e in excluded)]
```

## 23.10.3 Side-specific limit checks

```python
def assert_two_sided_or_side_limits(expr, var, point, *, expected_plus=None, expected_minus=None):
    if expected_plus is not None:
        assert sp.limit(expr, var, point, dir="+") == expected_plus
    if expected_minus is not None:
        assert sp.limit(expr, var, point, dir="-") == expected_minus
```

## 23.10.4 Branch-cut sample grid

```python
def complex_branch_samples():
    return [
        -2 + sp.I*sp.Rational(1, 1000),
        -2 - sp.I*sp.Rational(1, 1000),
        -1,
        0,
        1,
        2,
        sp.I,
        -sp.I,
    ]
```

---

## 23.11 Snapshot tests for LaTeX, codegen, and external artifacts

## 23.11.1 Snapshot scope

```text
Good snapshot targets:
  LaTeX output for public docs
  generated C/Fortran/JS/Rust code snippets
  API payload schemas
  srepr for internal rewrite trees
  codegen routine signatures

Bad snapshot targets:
  arbitrary simplify output
  unordered sets/dicts without normalization
  backend-dependent floating output
  full giant expressions without normalization
```

## 23.11.2 Normalize text before snapshot

```python
def normalize_text_snapshot(s: str) -> str:
    lines = [line.rstrip() for line in s.strip().splitlines()]
    return "\n".join(lines) + "\n"


def assert_snapshot_text(actual: str, expected: str):
    assert normalize_text_snapshot(actual) == normalize_text_snapshot(expected)
```

## 23.11.3 LaTeX snapshot

```python
def assert_latex_snapshot(expr, expected):
    actual = sp.latex(expr)
    assert_snapshot_text(actual, expected)
```

## 23.11.4 Codegen snapshot

```python
def assert_c_snapshot(expr, expected, *, assign_to="out"):
    actual = sp.ccode(expr, assign_to=assign_to, standard="C99")
    assert_snapshot_text(actual, expected)
```

Snapshot tests are useful but should be version-aware because printer outputs can legitimately change across SymPy versions; store `sp.__version__` alongside blessed artifacts.

---

## 23.12 Performance regression tests

## 23.12.1 Expression-size regression

```python
def assert_ops_below(expr, max_ops):
    ops = sp.count_ops(expr)
    assert ops <= max_ops, f"operation count {ops} > {max_ops}"


def assert_nodes_below(expr, max_nodes):
    nodes = sum(1 for _ in sp.preorder_traversal(expr))
    assert nodes <= max_nodes, f"node count {nodes} > {max_nodes}"
```

`simplify()` exposes a `measure` parameter and uses `count_ops` by default; the docs caution that string-length measures can be too slow for very large expressions and recommend `count_ops` when no better metric is known. ([SymPy Documentation][2])

## 23.12.2 Time regression

```python
import time

def assert_runtime_below(fn, *args, seconds, **kwargs):
    start = time.perf_counter()
    result = fn(*args, **kwargs)
    elapsed = time.perf_counter() - start
    assert elapsed <= seconds, f"{fn.__name__} took {elapsed:.6f}s > {seconds:.6f}s"
    return result
```

## 23.12.3 Slow-test classification

```python
from sympy.testing.pytest import slow

@slow
def test_large_codegen_performance():
    ...
```

SymPy’s test-writing docs say tests taking more than a minute should be marked with `@slow`; slow tests are skipped by default and run separately, while hanging tests should be skipped rather than marked slow. ([SymPy Documentation][8])

## 23.12.4 Benchmark dimensions

```text
Benchmark axes:
  expression degree
  number of symbols
  number of outputs
  matrix dimension
  polynomial domain
  simplification profile
  CSE on/off
  lambdify backend
  generated-code backend
  optional dependency installed/missing
```

---

## 23.13 Reproducibility across SymPy versions

## 23.13.1 Metadata capture

```python
import platform

def sympy_test_metadata():
    return {
        "sympy_version": sp.__version__,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
    }
```

## 23.13.2 Artifact metadata

```python
def expression_artifact(expr):
    expr = sp.sympify(expr)
    return {
        "sympy_version": sp.__version__,
        "srepr": sp.srepr(expr),
        "str": str(expr),
        "latex": sp.latex(expr),
        "free_symbols": sorted(str(s) for s in expr.free_symbols),
    }
```

## 23.13.3 Version-sensitive test policy

```text
Stable tests:
  mathematical equivalence
  substitution residuals
  solver solution validation
  numeric regression within tolerance
  operation-count upper bounds with margin

Version-sensitive tests:
  exact LaTeX/code printer snapshots
  srepr snapshots
  simplify output form
  generated temporary variable names
  ordering of unordered sets/dicts
```

## 23.13.4 Optional dependencies

SymPy has one hard dependency, `mpmath`, and many optional dependencies enable additional functionality such as plotting, autowrapping, and optional test coverage. Optional-dependency tests should skip cleanly when packages are not installed. ([SymPy Documentation][5])

```python
def optional_module(name):
    from sympy.external import import_module
    return import_module(name)


def test_numpy_backend_if_available():
    np = optional_module("numpy")
    if np is None:
        from sympy.testing.pytest import skip
        skip("NumPy not installed")

    f = sp.lambdify(x, sp.sin(x), "numpy")
    assert np.allclose(f(np.array([0.0])), np.array([0.0]))
```

---

## 23.14 CI layout for SymPy-based projects

```text
tests/
  test_symbolic_core.py
  test_assumptions.py
  test_solvers.py
  test_numeric_regression.py
  test_codegen.py
  test_branch_domains.py
  test_snapshots.py
  test_performance.py
  test_optional_backends.py
```

Recommended markers:

```text
unit:
  fast symbolic tests

numeric:
  lambdify/generated-code numeric checks

slow:
  expensive simplification/codegen/large matrix tests

optional:
  NumPy/SciPy/JAX/CuPy/autowrap/compiler-dependent tests

snapshot:
  printer/codegen text output

xfail:
  known SymPy limitation or future expected improvement
```

SymPy’s contributor docs describe `XFAIL` tests for known expected failures and warn that an XFAIL test should be written so that it will XPASS when the functionality starts working; they also document separate slow-test handling and optional-dependency skips. ([SymPy Documentation][8])

---

## 23.15 Anti-pattern inventory

| Anti-pattern                                       | Failure mode                  | Correct pattern                                   |
| -------------------------------------------------- | ----------------------------- | ------------------------------------------------- |
| `assert simplify(a-b) == 0` everywhere             | slow, branch/domain blind     | targeted equivalence by expression class          |
| `assert actual == expected` for arbitrary formulas | false negatives               | canonicalize or use equivalence helper            |
| numeric-only proof of identity                     | missed branch/domain failures | symbolic proof plus numeric regression            |
| unseeded randomized tests                          | flaky CI                      | fixed seed and deterministic samples              |
| random samples include singularities               | false failures / `zoo`        | filter denominator roots and branch boundaries    |
| no real/complex split                              | branch-cut bugs missed        | explicit real and complex sample grids            |
| testing only generic symbols                       | assumptions bugs missed       | test real/positive/integer/nonzero variants       |
| code snapshot without runtime test                 | compilable-looking wrong code | compile/call and compare reference                |
| runtime test without source snapshot               | signature drift missed        | snapshot source/signature plus numeric regression |
| absolute tolerance only                            | scale-sensitive failures      | `atol + rtol*scale`                               |
| snapshots of unordered output                      | nondeterministic diffs        | sort/normalize first                              |
| performance tests in normal unit suite             | slow/flaky CI                 | mark slow or benchmark separately                 |
| no SymPy version metadata                          | irreproducible artifacts      | capture `sp.__version__`                          |
| optional backend missing causes failure            | CI environment-dependent      | import/skip cleanly                               |

---

## 23.16 Minimal QA harness

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Sequence
import math
import platform
import time

import sympy as sp


@dataclass(frozen=True)
class ExprQAReport:
    expr: sp.Basic
    sympy_version: str
    python_version: str
    free_symbols: tuple[sp.Symbol, ...]
    float_atoms: tuple[sp.Float, ...]
    operation_count: int
    node_count: int
    has_piecewise: bool
    has_unresolved_calculus: bool
    has_undefined_functions: bool


@dataclass(frozen=True)
class NumericFailure:
    values: tuple[Any, ...]
    expected: Any
    actual: Any
    abs_error: Any
    tolerance: Any


def qa_report(expr: Any) -> ExprQAReport:
    from sympy.core.function import AppliedUndef

    expr = sp.sympify(expr)

    return ExprQAReport(
        expr=expr,
        sympy_version=sp.__version__,
        python_version=platform.python_version(),
        free_symbols=tuple(sorted(expr.free_symbols, key=str)),
        float_atoms=tuple(sorted(expr.atoms(sp.Float), key=str)),
        operation_count=int(sp.count_ops(expr)),
        node_count=sum(1 for _ in sp.preorder_traversal(expr)),
        has_piecewise=bool(expr.atoms(sp.Piecewise)),
        has_unresolved_calculus=any(
            expr.has(node)
            for node in (sp.Integral, sp.Derivative, sp.Limit, sp.Sum, sp.Product)
        ),
        has_undefined_functions=bool(expr.atoms(AppliedUndef)),
    )


def assert_structural_equal(actual: Any, expected: Any) -> None:
    actual = sp.sympify(actual)
    expected = sp.sympify(expected)

    assert actual == expected, (
        "structural mismatch\n"
        f"actual: {actual}\n"
        f"expected: {expected}\n"
        f"actual srepr: {sp.srepr(actual)}\n"
        f"expected srepr: {sp.srepr(expected)}"
    )


def rational_delta(a: Any, b: Any) -> sp.Expr:
    return sp.cancel(sp.together(sp.sympify(a) - sp.sympify(b)))


def assert_symbolically_equal(a: Any, b: Any) -> None:
    a = sp.sympify(a)
    b = sp.sympify(b)

    if a == b:
        return

    delta = rational_delta(a, b)
    if delta == 0:
        return

    delta_trig = sp.trigsimp(delta)
    if delta_trig == 0:
        return

    q = a.equals(b)
    if q is True:
        return

    raise AssertionError(
        "symbolic equality not established\n"
        f"a: {a}\n"
        f"b: {b}\n"
        f"delta: {delta}\n"
        f"trigsimp(delta): {delta_trig}\n"
        f"equals: {q}"
    )


def assert_polynomial_equal(a: Any, b: Any, gens: Sequence[sp.Symbol], *, domain=sp.QQ) -> None:
    P = sp.Poly(sp.expand(sp.sympify(a) - sp.sympify(b)), *gens, domain=domain)
    assert P.is_zero, f"polynomial difference not zero: {P}"


def assert_matrix_equal(A: Any, B: Any) -> None:
    A = sp.Matrix(A)
    B = sp.Matrix(B)

    assert A.shape == B.shape, f"shape mismatch: {A.shape} vs {B.shape}"

    for i in range(A.rows):
        for j in range(A.cols):
            assert_symbolically_equal(A[i, j], B[i, j])


def assert_fuzzy(expr: Any, predicate: str, expected: bool | None) -> None:
    expr = sp.sympify(expr)
    actual = getattr(expr, f"is_{predicate}")
    assert actual is expected, f"{expr}.is_{predicate}: expected {expected}, got {actual}"


def equation_to_zero(eq: Any) -> sp.Expr:
    eq = sp.sympify(eq)
    if isinstance(eq, sp.Equality):
        return sp.simplify(eq.lhs - eq.rhs)
    return eq


def assert_solution_satisfies(eqs: Any, solution: dict[sp.Symbol, Any]) -> None:
    if not isinstance(eqs, (list, tuple)):
        eqs = [eqs]

    for eq in eqs:
        residual = equation_to_zero(eq).subs(solution)
        assert_symbolically_equal(residual, 0)


def assert_solution_set_satisfies(eqs: Any, symbols: Sequence[sp.Symbol], solset: Any) -> None:
    if solset is sp.S.EmptySet:
        return

    assert isinstance(solset, sp.FiniteSet), f"expected FiniteSet, got {type(solset).__name__}"

    for item in solset:
        tup = item if isinstance(item, tuple) else (item,)
        sol = dict(zip(symbols, tup))
        assert_solution_satisfies(eqs, sol)


def assert_ode_solution(ode: Any, sol: Any) -> None:
    ok, residual = sp.checkodesol(ode, sol)
    assert ok is True, residual


def assert_close(actual: Any, expected: Any, *, atol=1e-12, rtol=1e-12) -> None:
    actual_c = complex(actual)
    expected_c = complex(expected)

    err = abs(actual_c - expected_c)
    scale = max(1.0, abs(expected_c))
    tol = atol + rtol*scale

    assert err <= tol, NumericFailure(
        values=(),
        expected=expected,
        actual=actual,
        abs_error=err,
        tolerance=tol,
    )


def assert_lambdified_matches_reference(
    expr: Any,
    args: Sequence[sp.Symbol],
    samples: Sequence[Sequence[Any]],
    *,
    backend: str = "numpy",
    atol=1e-12,
    rtol=1e-12,
) -> None:
    expr = sp.sympify(expr)

    f_test = sp.lambdify(args, expr, modules=backend)
    f_ref = sp.lambdify(args, expr, modules="mpmath")

    for values in samples:
        actual = f_test(*values)
        expected = f_ref(*values)
        assert_close(actual, expected, atol=atol, rtol=rtol)


def assert_generated_callable_matches(
    expr: Any,
    fn: Callable,
    args: Sequence[sp.Symbol],
    samples: Sequence[Sequence[Any]],
    *,
    atol=1e-12,
    rtol=1e-12,
) -> None:
    expr = sp.sympify(expr)
    f_ref = sp.lambdify(args, expr, modules="mpmath")

    for values in samples:
        expected = f_ref(*values)
        actual = fn(*values)
        assert_close(actual, expected, atol=atol, rtol=rtol)


def assert_codegen_ready(expr: Any) -> None:
    from sympy.core.function import AppliedUndef

    expr = sp.sympify(expr)

    unresolved = (sp.Integral, sp.Derivative, sp.Limit, sp.Sum, sp.Product)
    hits = [node.__name__ for node in unresolved if expr.has(node)]
    assert not hits, f"unresolved nodes for codegen: {hits}"

    undef = expr.atoms(AppliedUndef)
    assert not undef, f"undefined functions remain: {undef}"

    for pw in expr.atoms(sp.Piecewise):
        assert pw.args and pw.args[-1][1] is True, f"Piecewise missing default branch: {pw}"


def normalize_snapshot_text(s: str) -> str:
    return "\n".join(line.rstrip() for line in s.strip().splitlines()) + "\n"


def assert_text_snapshot(actual: str, expected: str) -> None:
    assert normalize_snapshot_text(actual) == normalize_snapshot_text(expected)


def assert_latex_snapshot(expr: Any, expected: str) -> None:
    assert_text_snapshot(sp.latex(sp.sympify(expr)), expected)


def assert_c_snapshot(expr: Any, expected: str, *, assign_to: str = "out") -> None:
    assert_codegen_ready(expr)
    code = sp.ccode(sp.sympify(expr), assign_to=assign_to, standard="C99")
    assert_text_snapshot(code, expected)


def assert_ops_below(expr: Any, max_ops: int) -> None:
    ops = int(sp.count_ops(sp.sympify(expr)))
    assert ops <= max_ops, f"operation count {ops} > {max_ops}"


def assert_node_count_below(expr: Any, max_nodes: int) -> None:
    nodes = sum(1 for _ in sp.preorder_traversal(sp.sympify(expr)))
    assert nodes <= max_nodes, f"node count {nodes} > {max_nodes}"


def timed_call(fn: Callable, *args, **kwargs):
    start = time.perf_counter()
    result = fn(*args, **kwargs)
    elapsed = time.perf_counter() - start
    return result, elapsed


def assert_runtime_below(fn: Callable, *args, seconds: float, **kwargs):
    result, elapsed = timed_call(fn, *args, **kwargs)
    assert elapsed <= seconds, f"{fn.__name__} took {elapsed:.6f}s > {seconds:.6f}s"
    return result


def denominator_exclusions(expr: Any, var: sp.Symbol) -> set:
    expr = sp.sympify(expr)
    _, den = sp.together(expr).as_numer_denom()

    try:
        return set(sp.solve(sp.Eq(den, 0), var))
    except Exception:
        return set()


def safe_samples(expr: Any, var: sp.Symbol, candidates: Iterable[Any]) -> list[Any]:
    exclusions = denominator_exclusions(expr, var)
    out = []

    for value in candidates:
        if all(sp.simplify(sp.sympify(value) - e) != 0 for e in exclusions):
            out.append(value)

    return out


def assert_equal_on_samples(
    a: Any,
    b: Any,
    var: sp.Symbol,
    samples: Sequence[Any],
    *,
    digits: int = 80,
    tol=sp.S("1e-40"),
) -> None:
    a = sp.sympify(a)
    b = sp.sympify(b)

    for value in samples:
        av = sp.N(a.subs(var, value), digits)
        bv = sp.N(b.subs(var, value), digits)
        assert abs(av - bv) <= tol, (value, av, bv)


def assert_side_limits(
    expr: Any,
    var: sp.Symbol,
    point: Any,
    *,
    plus: Any | None = None,
    minus: Any | None = None,
) -> None:
    expr = sp.sympify(expr)

    if plus is not None:
        assert sp.limit(expr, var, point, dir="+") == plus

    if minus is not None:
        assert sp.limit(expr, var, point, dir="-") == minus


def artifact_metadata(expr: Any) -> dict[str, Any]:
    expr = sp.sympify(expr)
    return {
        "sympy_version": sp.__version__,
        "python_version": platform.python_version(),
        "srepr": sp.srepr(expr),
        "str": str(expr),
        "latex": sp.latex(expr),
        "free_symbols": [str(s) for s in sorted(expr.free_symbols, key=str)],
        "operation_count": int(sp.count_ops(expr)),
    }


def optional_import_or_skip(module_name: str):
    from sympy.external import import_module
    mod = import_module(module_name)

    if mod is None:
        from sympy.testing.pytest import skip
        skip(f"{module_name} is not installed")

    return mod
```

This harness encodes the QA discipline: structural equality, mathematical equivalence, polynomial/matrix equivalence, fuzzy-boolean assertions, solver residual validation, ODE validation, lambdified numeric regression, generated-code validation, codegen readiness, snapshot normalization, expression-size limits, runtime checks, singularity-safe sampling, side-limit checks, reproducibility metadata, and optional-dependency skipping.

[1]: https://docs.sympy.org/latest/contributing/docstring.html "Docstrings Style Guide - SymPy 1.14.0 documentation"
[2]: https://docs.sympy.org/latest/modules/simplify/simplify.html "Simplify - SymPy 1.14.0 documentation"
[3]: https://docs.sympy.org/latest/guides/assumptions.html "Assumptions - SymPy 1.14.0 documentation"
[4]: https://docs.sympy.org/latest/modules/utilities/lambdify.html "Lambdify - SymPy 1.14.0 documentation"
[5]: https://docs.sympy.org/latest/contributing/dependencies.html "Dependencies - SymPy 1.14.0 documentation"
[6]: https://docs.sympy.org/latest/modules/testing/randtest.html "Randomised Testing - SymPy 1.14.0 documentation"
[7]: https://docs.sympy.org/latest/modules/core.html "Core - SymPy 1.14.0 documentation"
[8]: https://docs.sympy.org/latest/contributing/new-contributors-guide/writing-tests.html "Writing Tests - SymPy 1.14.0 documentation"
[9]: https://docs.sympy.org/latest/modules/utilities/codegen.html "Codegen - SymPy 1.14.0 documentation"
[10]: https://docs.sympy.org/latest/modules/codegen.html "Code Generation - SymPy 1.14.0 documentation"
[11]: https://docs.sympy.org/latest/explanation/gotchas.html "Gotchas and Pitfalls - SymPy 1.14.0 documentation"


# 24) Interoperability with the Python scientific stack — agent-ready deep dive

## 24.0 Domain rule

```text
SymPy layer:
  exact symbolic objects, assumptions, algebra, calculus, solving, codegen IR

Numeric stack layer:
  NumPy/SciPy/mpmath/JAX/CuPy arrays/scalars/callables

Interop boundary:
  SymPy Expr → lambdify/codegen/autowrap/ufuncify → numeric callable
  numeric results → optional nsimplify/Rational/Float → SymPy object
```

SymPy’s own best-practices docs explicitly recommend modeling symbolically in SymPy, then converting to numerical functions with `lambdify()` for NumPy evaluation; they also warn that SymPy expressions and NumPy arrays/functions do not directly interoperate cleanly. ([SymPy Documentation][1])

```python
import sympy as sp

x, y, t = sp.symbols("x y t", real=True)
expr = sp.sin(x) / x

# Boundary: symbolic expression → numeric callable
f_np = sp.lambdify(x, expr, modules="numpy")
```

---

## 24.1 NumPy interoperability

## 24.1.1 Correct boundary: `lambdify(..., "numpy")`

```python
import numpy as np
import sympy as sp

x = sp.Symbol("x", real=True)
expr = sp.sin(x) / x

f = sp.lambdify(x, expr, modules="numpy")

xs = np.linspace(1.0, 10.0, 10_000)
ys = f(xs)
```

SymPy’s numeric-computation docs show this exact style: build `expr = sin(x)/x`, then `lambdify(x, expr, "numpy")`, then call the generated function on NumPy arrays; the generated function uses NumPy’s vectorized ufuncs backed by compiled code. ([SymPy Documentation][2])

### Wrong direction

```python
# Bad: NumPy ufunc called on SymPy Symbol
np.sin(x)

# Bad: SymPy function called on NumPy array
sp.sin(np.array([1.0, 2.0]))

# Bad: NumPy-lambdified function called with SymPy expression
f_np = sp.lambdify(x, sp.sin(x), "numpy")
f_np(x + 1)
```

### Correct direction

```python
# Symbolic
expr = sp.sin(x) + sp.cos(x)**2

# Numeric
f = sp.lambdify(x, expr, "numpy")
values = f(np.asarray([0.0, 1.0, 2.0]))
```

## 24.1.2 NumPy dtype boundary

NumPy arrays are homogeneous and each element is interpreted by a `dtype`; a dtype can describe numeric types, Python objects, structured fields, byte order, and storage size. Storing SymPy expressions in a NumPy array usually produces `dtype=object`, which keeps Python object references rather than fast native numeric storage. ([NumPy][3])

```python
arr_bad = np.array([x, x + 1])
arr_bad.dtype
# dtype('O')
```

### Rule

```text
Use SymPy Matrix/Array/List:
  symbolic containers

Use NumPy ndarray:
  numeric arrays

Avoid:
  NumPy object arrays of SymPy expressions unless explicitly building symbolic object containers.
```

### Symbolic container alternative

```python
M = sp.Matrix([x, x + 1, sp.sin(x)])
A = sp.Array([x, x + 1, sp.sin(x)])
```

### Numeric container alternative

```python
f = sp.lambdify(x, [x, x + 1, sp.sin(x)], modules="numpy")
numeric = np.asarray(f(np.linspace(0.0, 1.0, 5)))
```

## 24.1.3 Broadcasting and vectorization

```python
x, y = sp.symbols("x y")
expr = sp.sin(x*y) + x**2

f = sp.lambdify((x, y), expr, "numpy")

xs = np.linspace(0, 1, 1000)
ys = np.linspace(1, 2, 1000)

out = f(xs, ys)      # NumPy broadcasting rules
```

### Deployment rules

```text
Use NumPy backend when:
  repeated array evaluation
  plotting grids
  Monte Carlo evaluation
  vectorized scalar formulas
  standard CPU scientific stack

Do not:
  pass SymPy objects into NumPy backend
  store large symbolic expressions in object arrays
  expect NumPy to preserve exact Rational/pi/E semantics
```

---

## 24.2 SciPy interoperability

## 24.2.1 SciPy integration

```python
import scipy.integrate as integrate

x = sp.Symbol("x", real=True)
expr = sp.exp(-x**2)

f = sp.lambdify(x, expr, modules="numpy")

val, err = integrate.quad(f, 0.0, np.inf)
```

`scipy.integrate.quad` computes definite integrals over finite or infinite intervals using QUADPACK, and `solve_ivp` numerically integrates systems of ODEs from initial values. SymPy should derive exact integrands/RHS expressions; SciPy should execute numeric quadrature or ODE solving. ([SciPy Documentation][4])

### ODE bridge

```python
t = sp.Symbol("t")
y0, k = sp.symbols("y0 k", positive=True)

# symbolic RHS
y = sp.Symbol("y")
rhs_expr = -k*y

# numeric RHS function for solve_ivp
rhs = sp.lambdify((t, y, k), rhs_expr, modules="numpy")

def scipy_rhs(t_value, y_vec, k_value):
    return [rhs(t_value, y_vec[0], k_value)]

# scipy.integrate.solve_ivp(scipy_rhs, (0.0, 10.0), [1.0], args=(0.2,))
```

## 24.2.2 SciPy optimization and root finding

```python
import scipy.optimize as optimize

x, y = sp.symbols("x y", real=True)
objective = (x - 1)**2 + (y + 2)**2

f = sp.lambdify((x, y), objective, "numpy")
grad_expr = [sp.diff(objective, x), sp.diff(objective, y)]
grad = sp.lambdify((x, y), grad_expr, "numpy")

def fun(v):
    return float(f(v[0], v[1]))

def jac(v):
    return np.asarray(grad(v[0], v[1]), dtype=float)

res = optimize.minimize(fun, x0=np.array([0.0, 0.0]), jac=jac)
```

`scipy.optimize` provides numerical minimization/maximization, nonlinear equation solvers, constrained optimization, least squares, root finding, curve fitting, and linear programming. Derive objective functions, gradients, Jacobians, Hessians, or residuals symbolically in SymPy, then hand numeric callables to SciPy. ([SciPy Documentation][5])

## 24.2.3 SciPy sparse solvers

```python
import scipy.sparse as sparse
import scipy.sparse.linalg as spla

# symbolic derivation of entries
a = sp.Symbol("a")
entry_expr = 2*a + 1
entry_fn = sp.lambdify(a, entry_expr, "numpy")

# numeric sparse assembly
A = sparse.csr_array([[entry_fn(1.0), 0.0], [0.0, entry_fn(2.0)]])
b = np.array([1.0, 2.0])

x_sol = spla.spsolve(A, b)
```

SciPy sparse arrays have specific sparse formats such as CSR, CSC, COO, DOK, LIL, BSR, and DIA; SciPy warns against using NumPy functions directly on sparse arrays because NumPy may treat them as generic Python objects rather than sparse arrays. Use SciPy sparse functions/solvers or convert deliberately. ([SciPy Documentation][6])

## 24.2.4 SciPy special functions

```python
expr = sp.erf(x) + sp.gamma(x)

f = sp.lambdify(x, expr, modules="scipy")
```

`scipy.special` implements many special functions as NumPy universal functions; almost all accept NumPy arrays and follow broadcasting/automatic array-looping rules. Use `modules="scipy"` when SymPy expressions contain special functions not covered by NumPy. ([SciPy Documentation][7])

### SciPy boundary rules

```text
Use SciPy for:
  numerical quadrature
  ODE/IVP solving
  nonlinear optimization
  root finding
  least squares
  sparse linear algebra
  special-function arrays
  signal/control/data workflows

Use SymPy for:
  exact derivatives/Jacobians/Hessians
  closed forms
  symbolic simplification
  algebraic preprocessing
  codegen/source of formulas
```

---

## 24.3 mpmath interoperability

## 24.3.1 `evalf` and `lambdify(..., "mpmath")`

```python
import mpmath as mp

x = sp.Symbol("x")
expr = sp.sin(x) / x

# SymPy scalar precision path
expr.evalf(80, subs={x: sp.Rational(1, 7)})

# mpmath callable path
f_mp = sp.lambdify(x, expr, "mpmath")

mp.mp.dps = 80
value = f_mp(mp.mpf("0.142857142857142857"))
```

mpmath is a Python library for arbitrary-precision real and complex floating-point arithmetic, can substitute for Python `float`/`complex` and `math`/`cmath`, and supports calculations at high precision such as 10 or 1000 digits. ([mpmath][8])

## 24.3.2 Precision context

mpmath uses a global working precision context `mp`, and operations round to the current working precision. Set `mp.mp.dps` or use context managers before calling mpmath-backed lambdified functions. ([mpmath][9])

```python
old_dps = mp.mp.dps
try:
    mp.mp.dps = 100
    value = f_mp(mp.mpf("0.1"))
finally:
    mp.mp.dps = old_dps
```

### mpmath rules

```text
Use mpmath when:
  arbitrary precision scalar values
  complex scalar high-precision checks
  verification oracle for generated code
  special-function high-precision diagnostics

Avoid mpmath when:
  large vectorized arrays
  GPU/accelerator execution
  SciPy-style fitting/optimization over large data
```

---

## 24.4 pandas interoperability

## 24.4.1 Recommended pattern: derive symbolic, apply numeric callable to columns

```python
import pandas as pd

x = sp.Symbol("x")
expr = sp.log(1 + x**2)

f = sp.lambdify(x, expr, "numpy")

df = pd.DataFrame({"x": np.linspace(0.0, 10.0, 1000)})
df["y"] = f(df["x"].to_numpy())
```

pandas is built for tabular data analysis on top of NumPy-style dtypes; columns with mixed types are stored as `object` dtype, and pandas offers conversion helpers such as `infer_objects`, `astype`, and `convert_dtypes` to avoid or convert object dtype. ([Pandas][10])

## 24.4.2 Avoid symbolic object columns unless intentional

```python
# Usually bad for numeric analytics:
df = pd.DataFrame({"expr": [x, x + 1, sp.sin(x)]})
df.dtypes
# object
```

pandas text-data docs warn that object dtype can accidentally store mixed Python objects and makes dtype-specific operations less clear; for symbolic formulas, use object dtype only as an explicit metadata/formula column, not for numeric analytics. ([Pandas][11])

### Safer pattern

```python
formula_metadata = {
    "sympy_srepr": sp.srepr(expr),
    "latex": sp.latex(expr),
    "variables": [str(s) for s in expr.free_symbols],
}

df["numeric_y"] = f(df["x"].to_numpy())
```

### pandas rules

```text
Use pandas for:
  numeric tabular results
  parameter sweeps
  simulation output tables
  formula metadata columns if intentionally object dtype

Avoid:
  vectorized symbolic algebra inside DataFrame columns
  large object-dtype columns of SymPy expressions
  row-wise .apply with SymPy operations in hot paths

Preferred:
  lambdify → NumPy arrays → assign numeric columns
```

---

## 24.5 xarray interoperability

## 24.5.1 Apply lambdified NumPy functions to labeled arrays

```python
import xarray as xr

x = sp.Symbol("x")
expr = sp.sin(x) + x**2
f = sp.lambdify(x, expr, "numpy")

da = xr.DataArray(
    np.linspace(0.0, 1.0, 100),
    dims=("time",),
    coords={"time": np.arange(100)},
)

out = xr.apply_ufunc(f, da)
```

`xarray.apply_ufunc` applies vectorized functions to xarray objects using xarray’s labeled-computation rules, including alignment, broadcasting, looping over grouped/dataset variables, and coordinate handling. ([xarray][12])

## 24.5.2 Dask-backed xarray

```python
out = xr.apply_ufunc(
    f,
    da,
    dask="parallelized",
    output_dtypes=[float],
)
```

xarray’s Dask guidance recommends `apply_ufunc()` for functions that consume and return NumPy arrays, `map_blocks()` for functions that need full xarray objects per block, or direct Dask-array extraction for lower-level control. ([xarray][13])

### xarray rules

```text
Use xarray for:
  labeled multi-dimensional numeric results
  climate/physics grids
  parameter-coordinate arrays
  Dask-backed chunked evaluation

Use SymPy for:
  formula derivation

Bridge:
  expr → lambdify(..., "numpy") → xr.apply_ufunc

Avoid:
  storing SymPy Expr in DataArray values unless symbolic metadata is the objective
```

---

## 24.6 JAX interoperability

## 24.6.1 Lambdify to JAX

```python
x, y = sp.symbols("x y")
expr = sp.sin(x*y) + x**2

f_jax = sp.lambdify((x, y), expr, modules="jax")

# import jax
# import jax.numpy as jnp
# f_jit = jax.jit(f_jax)
# out = f_jit(jnp.linspace(0, 1, 1000), 2.0)
```

JAX provides a NumPy-like interface for computations on CPU, GPU, or TPU and supports transformations such as JIT compilation, automatic differentiation, batching, and parallelization. ([JAX Docs][14])

### JAX deployment rules

```text
Use JAX path when:
  generated formula must run in JAX ecosystem
  JIT compilation is desired
  autodiff/grad/vmap/pmap pipeline is desired
  CPU/GPU/TPU portability matters

Guard:
  test eager call
  test jax.jit call
  avoid Python side effects
  avoid unsupported SymPy functions
  avoid object arrays
  validate dtype behavior: float32 vs float64 config
```

### Symbolic derivative vs JAX autodiff

```text
SymPy derivative:
  exact closed-form derivative
  can simplify/codegen independently
  may be large

JAX grad:
  numeric program transformation
  backend-compatible
  useful when formula is already numeric/JAX-native

Hybrid:
  SymPy derive expression/Jacobian
  lambdify to JAX
  optionally JIT the result
```

---

## 24.7 CuPy interoperability

## 24.7.1 Lambdify to CuPy

```python
x = sp.Symbol("x")
expr = sp.sin(x) / x

f_cupy = sp.lambdify(x, expr, modules="cupy")

# import cupy as cp
# xs_gpu = cp.linspace(1, 10, 1_000_000)
# ys_gpu = f_cupy(xs_gpu)
```

CuPy is a NumPy/SciPy-compatible GPU array library and can often act as a drop-in replacement for NumPy/SciPy by replacing `numpy`/`scipy` with `cupy`/`cupyx.scipy`; it provides GPU-backed `ndarray`, sparse matrices, and related routines. ([CuPy][15])

### CuPy deployment rules

```text
Use CuPy path when:
  data already lives on GPU
  expression maps to CuPy-supported ufuncs
  array sizes amortize transfer overhead
  CUDA/ROCm stack is available and tested

Avoid:
  per-call CPU↔GPU transfers
  unsupported special functions without custom mapping
  small arrays where transfer/JIT overhead dominates
```

---

## 24.8 matplotlib interoperability

## 24.8.1 Direct Matplotlib with lambdified function

```python
import matplotlib.pyplot as plt

x = sp.Symbol("x")
expr = sp.sin(x) / x
f = sp.lambdify(x, expr, "numpy")

xs = np.linspace(0.1, 20.0, 2000)
ys = f(xs)

fig, ax = plt.subplots()
ax.plot(xs, ys)
ax.set_xlabel("x")
ax.set_ylabel(r"$\sin(x)/x$")
ax.set_title(sp.latex(expr))
```

Matplotlib provides a full plotting API with figures, axes, subplots, output backends, labels, scales, legends, and styling. `pyplot` is a state-based MATLAB-like interface mainly intended for interactive plots and simple programmatic generation; the explicit Figure/Axes interface is preferred for controlled application/library plotting. ([Matplotlib][16])

## 24.8.2 SymPy plotting vs Matplotlib

```text
SymPy plotting:
  quick symbolic previews
  plot(expr, range)
  plot_implicit(Eq(...))
  labels from symbolic expressions

Matplotlib directly:
  publication figures
  custom styling
  mixed empirical + symbolic data
  reusable figure API
  deterministic sampling grids
```

### Recommended bridge

```python
def plot_expr(expr, var, a, b, *, n=1000):
    f = sp.lambdify(var, expr, "numpy")
    xs = np.linspace(float(a), float(b), n)
    ys = f(xs)

    fig, ax = plt.subplots()
    ax.plot(xs, ys)
    ax.set_title(f"${sp.latex(expr)}$")
    return fig, ax
```

---

## 24.9 C/Fortran tooling: `codegen`, `autowrap`, `ufuncify`, F2PY, Cython

## 24.9.1 SymPy compiled paths

```python
from sympy.utilities.autowrap import autowrap, ufuncify
from sympy.utilities.codegen import codegen

expr = sp.sin(x) / x

# Python-callable compiled scalar/function
compiled = autowrap(expr, args=[x], backend="cython")

# NumPy-style elementwise compiled function
uf = ufuncify([x], expr, backend="f2py")

# Source generation
files = codegen(("kernel", expr), language="C99", header=True)
```

SymPy’s numeric-computation docs list `ufuncify` as a compiled vector-function path that depends on `f2py` and Cython, and its numeric guidance places `autowrap`/`ufuncify` below the symbolic-to-numeric bridge layer. ([SymPy Documentation][2])

## 24.9.2 F2PY

F2PY is NumPy’s Fortran-to-Python interface generator; its purpose is to connect Python and Fortran and it is distributed as `numpy.f2py`, also available as a standalone command-line tool after NumPy installation. ([NumPy][17])

```text
Use F2PY when:
  Fortran kernel exists
  SymPy generates Fortran source
  NumPy-compatible Python wrapper is needed
  scientific legacy code integration matters
```

## 24.9.3 Cython

Cython allows use of C data types in Python-like syntax and supports compiling Python/Cython code into extension modules; its docs recommend Cython 3 for newer pure-Python syntax improvements. ([Cython][18])

```text
Use Cython when:
  generated C code needs Python extension wrapper
  custom memory layout / typed loops are needed
  autowrap backend='cython' is acceptable
  packaging compiled Python extensions is allowed
```

### Native toolchain rules

```text
Use autowrap/ufuncify:
  quick compiled functions
  prototypes
  internal kernels

Use codegen + build system:
  production native package
  embedded systems
  explicit ABI
  CI/compiler control

Always:
  preserve generated source during debugging
  test compiled output vs symbolic reference
  pin SymPy/compiler/backend versions
```

---

## 24.10 End-to-end scientific-stack patterns

## Pattern A — symbolic derivative → SciPy optimizer

```python
x, y = sp.symbols("x y")
objective = (x - 2)**4 + (y + 1)**2

grad_expr = [sp.diff(objective, x), sp.diff(objective, y)]
hess_expr = sp.hessian(objective, (x, y))

f = sp.lambdify((x, y), objective, "numpy")
g = sp.lambdify((x, y), grad_expr, "numpy")
H = sp.lambdify((x, y), hess_expr, "numpy")

def fun(v):
    return float(f(v[0], v[1]))

def jac(v):
    return np.asarray(g(v[0], v[1]), dtype=float)

def hess(v):
    return np.asarray(H(v[0], v[1]), dtype=float)
```

## Pattern B — symbolic RHS/Jacobian → SciPy IVP solver

```python
t = sp.Symbol("t")
y0, y1, k = sp.symbols("y0 y1 k")

rhs_expr = sp.Matrix([y1, -k*y0])
jac_expr = rhs_expr.jacobian([y0, y1])

rhs_fn = sp.lambdify((t, y0, y1, k), rhs_expr, "numpy")
jac_fn = sp.lambdify((t, y0, y1, k), jac_expr, "numpy")

def rhs_scipy(tval, yvec, kval):
    return np.asarray(rhs_fn(tval, yvec[0], yvec[1], kval), dtype=float).reshape(-1)

def jac_scipy(tval, yvec, kval):
    return np.asarray(jac_fn(tval, yvec[0], yvec[1], kval), dtype=float)
```

## Pattern C — SymPy formula → pandas parameter sweep

```python
a, x = sp.symbols("a x")
expr = sp.exp(-a*x) * sp.sin(x)

f = sp.lambdify((a, x), expr, "numpy")

df = pd.DataFrame({
    "a": np.linspace(0.1, 2.0, 1000),
    "x": np.linspace(0.0, 10.0, 1000),
})
df["value"] = f(df["a"].to_numpy(), df["x"].to_numpy())
```

## Pattern D — SymPy formula → xarray labeled grid

```python
a, x = sp.symbols("a x")
expr = sp.exp(-a*x) * sp.sin(x)
f = sp.lambdify((a, x), expr, "numpy")

a_da = xr.DataArray(np.linspace(0.1, 2.0, 50), dims="a", coords={"a": np.linspace(0.1, 2.0, 50)})
x_da = xr.DataArray(np.linspace(0.0, 10.0, 100), dims="x", coords={"x": np.linspace(0.0, 10.0, 100)})

out = xr.apply_ufunc(f, a_da, x_da)
```

## Pattern E — SymPy formula → JAX JIT

```python
x = sp.Symbol("x")
expr = sp.sin(x) / x

f_jax = sp.lambdify(x, expr, "jax")

# import jax
# f_jit = jax.jit(f_jax)
```

## Pattern F — SymPy formula → CuPy GPU array

```python
x = sp.Symbol("x")
expr = sp.sin(x) / x

f_cupy = sp.lambdify(x, expr, "cupy")

# import cupy as cp
# xs = cp.linspace(1, 100, 10_000_000)
# ys = f_cupy(xs)
```

## Pattern G — SymPy formula → compiled ufunc

```python
from sympy.utilities.autowrap import ufuncify

x = sp.Symbol("x")
expr = sp.sin(x) / x

uf = ufuncify([x], expr, backend="f2py")
```

---

## 24.11 Interop anti-pattern inventory

| Anti-pattern                                       | Failure mode                          | Correct pattern                       |
| -------------------------------------------------- | ------------------------------------- | ------------------------------------- |
| `np.sin(Symbol("x"))`                              | NumPy cannot handle symbolic object   | `sp.sin(x)` then `lambdify`           |
| `sp.sin(np.ndarray)`                               | SymPy object/slow/failure             | `lambdify(..., "numpy")`              |
| NumPy object array of SymPy Expr                   | slow Python object operations         | SymPy Matrix/Array or numeric ndarray |
| pandas column of SymPy Expr for analytics          | object dtype, slow, unclear semantics | formula metadata + numeric columns    |
| xarray DataArray of symbolic objects               | object arrays, no Dask/vector speed   | lambdify + `apply_ufunc`              |
| SciPy optimizer calls SymPy `.subs` each step      | very slow                             | lambdified objective/gradient         |
| SciPy ODE RHS returns SymPy Matrix                 | dtype/object errors                   | NumPy array of floats                 |
| sparse SciPy matrix passed to NumPy functions      | incorrect object treatment            | SciPy sparse APIs                     |
| JAX lambdified function with unsupported op        | tracing/JIT failure                   | rewrite or custom mapping             |
| CuPy backend with CPU arrays                       | wrong backend / transfers             | pass CuPy arrays                      |
| copying GPU data per call                          | transfer dominates                    | keep arrays on device                 |
| autowrap in compilerless deployment                | build failure                         | lambdify fallback                     |
| generated code without numeric tests               | silent mismatch                       | compare to mpmath/SymPy reference     |
| using exact SymPy for large numeric linear algebra | slow                                  | SciPy/NumPy sparse/dense solvers      |

---

## 24.12 Deployment decision matrix

| Need                              | Use                                                     |
| --------------------------------- | ------------------------------------------------------- |
| exact derivation                  | SymPy                                                   |
| one-off high-precision scalar     | `expr.evalf` / `lambdify(..., "mpmath")`                |
| CPU vectorized arrays             | `lambdify(..., "numpy")`                                |
| SciPy special functions           | `lambdify(..., "scipy")`                                |
| numerical quadrature              | SymPy derive integrand → `scipy.integrate.quad`         |
| numerical ODE solve               | SymPy derive RHS/Jacobian → `scipy.integrate.solve_ivp` |
| nonlinear optimization            | SymPy derive objective/grad/Hessian → `scipy.optimize`  |
| sparse linear solve               | SymPy derive entries → SciPy sparse matrix/solver       |
| high-precision verification       | mpmath                                                  |
| DataFrame workflow                | lambdify → NumPy arrays → pandas columns                |
| labeled multidim arrays           | lambdify → xarray `apply_ufunc`                         |
| GPU NumPy-like arrays             | `lambdify(..., "cupy")`                                 |
| JIT/autodiff accelerator          | `lambdify(..., "jax")`                                  |
| compiled elementwise NumPy kernel | `ufuncify`                                              |
| compiled scalar/function          | `autowrap`                                              |
| production C/Fortran source       | `codegen` / printers + external build                   |

---

## 24.13 Testing matrix

```python
def assert_numeric_bridge(expr, args, values, *, backend="numpy", tol=1e-12):
    ref = sp.lambdify(args, expr, "mpmath")
    test = sp.lambdify(args, expr, backend)

    expected = ref(*values)
    actual = test(*values)

    assert abs(float(expected) - float(actual)) <= tol
```

Coverage targets:

```text
NumPy:
  scalar input
  vector input
  broadcasting
  Piecewise
  matrix/list outputs

SciPy:
  quad integral
  solve_ivp RHS shape
  optimize objective/grad
  sparse solver shape/dtype
  special function backend

mpmath:
  precision context
  complex values
  high-precision reference checks

pandas:
  no accidental object dtype for numeric columns
  formula metadata stored separately

xarray:
  apply_ufunc dims/coords preserved
  dask="parallelized" path if Dask present

JAX:
  eager call
  jax.jit call
  dtype/shape
  unsupported function detection

CuPy:
  cupy array input
  no host-transfer assumption
  fallback when GPU unavailable

C/Fortran:
  autowrap smoke test
  ufuncify array test
  generated code snapshot
```

---

## 24.14 Minimal interoperability harness

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Literal, Sequence

import sympy as sp


NumericBackend = Literal[
    "math",
    "mpmath",
    "numpy",
    "scipy",
    "numexpr",
    "jax",
    "cupy",
    "tensorflow",
]


@dataclass(frozen=True)
class InteropAudit:
    expr: sp.Basic
    free_symbols: tuple[sp.Symbol, ...]
    backend: str
    has_float_atoms: bool
    has_piecewise: bool
    has_unresolved_symbolic_nodes: bool
    operation_count: int


def interop_audit(expr: Any, *, backend: str = "numpy") -> InteropAudit:
    expr = sp.sympify(expr)

    return InteropAudit(
        expr=expr,
        free_symbols=tuple(sorted(expr.free_symbols, key=str)),
        backend=backend,
        has_float_atoms=bool(expr.atoms(sp.Float)),
        has_piecewise=bool(expr.atoms(sp.Piecewise)),
        has_unresolved_symbolic_nodes=any(
            expr.has(node)
            for node in (sp.Integral, sp.Derivative, sp.Limit, sp.Sum, sp.Product)
        ),
        operation_count=int(sp.count_ops(expr)),
    )


def prepare_for_numeric_stack(expr: Any) -> sp.Expr:
    expr = sp.sympify(expr)

    if any(expr.has(node) for node in (sp.Integral, sp.Derivative, sp.Limit, sp.Sum, sp.Product)):
        raise ValueError(f"unresolved symbolic node remains: {expr}")

    for pw in expr.atoms(sp.Piecewise):
        if not pw.args or pw.args[-1][1] != True:
            raise ValueError(f"Piecewise lacks default True branch: {pw}")

    expr = sp.cancel(sp.together(expr))
    expr = sp.trigsimp(expr)
    expr = sp.powsimp(expr, combine="exp", deep=True, force=False)

    return expr


def lambdify_backend(
    args: Sequence[sp.Symbol] | sp.Symbol,
    expr: Any,
    *,
    backend: NumericBackend = "numpy",
    cse: bool = True,
    docstring_limit: int = 0,
    custom: dict[str, Callable] | None = None,
):
    expr = prepare_for_numeric_stack(expr)

    modules: Any = [custom, backend] if custom else backend

    return sp.lambdify(
        args,
        expr,
        modules=modules,
        cse=cse,
        docstring_limit=docstring_limit,
    )


def reject_sympy_numeric_inputs(*values):
    if any(isinstance(v, sp.Basic) for v in values):
        raise TypeError("numeric backend received SymPy object")


def numpy_function(args, expr):
    return lambdify_backend(args, expr, backend="numpy")


def scipy_function(args, expr):
    return lambdify_backend(args, expr, backend="scipy")


def mpmath_function(args, expr):
    return lambdify_backend(args, expr, backend="mpmath")


def jax_function(args, expr, *, jit: bool = False):
    f = lambdify_backend(args, expr, backend="jax")
    if jit:
        import jax
        return jax.jit(f)
    return f


def cupy_function(args, expr):
    return lambdify_backend(args, expr, backend="cupy")


def numpy_samples(
    expr: Any,
    var: sp.Symbol,
    start: float,
    stop: float,
    *,
    n: int = 1000,
):
    import numpy as np

    f = numpy_function(var, expr)
    xs = np.linspace(start, stop, n)
    return xs, f(xs)


def scipy_quad(expr: Any, var: sp.Symbol, a: float, b: float, **kwargs):
    import scipy.integrate as integrate

    f = scipy_function(var, expr)
    return integrate.quad(f, a, b, **kwargs)


def scipy_minimize_from_sympy(
    objective: Any,
    vars: Sequence[sp.Symbol],
    x0,
    *,
    use_grad: bool = True,
    method: str | None = None,
):
    import numpy as np
    import scipy.optimize as optimize

    objective = prepare_for_numeric_stack(objective)
    f = sp.lambdify(vars, objective, "numpy")

    def fun(v):
        return float(f(*v))

    kwargs = {}

    if use_grad:
        grad_expr = [sp.diff(objective, v) for v in vars]
        grad = sp.lambdify(vars, grad_expr, "numpy")

        def jac(v):
            return np.asarray(grad(*v), dtype=float)

        kwargs["jac"] = jac

    if method is not None:
        kwargs["method"] = method

    return optimize.minimize(fun, x0=x0, **kwargs)


def scipy_solve_ivp_from_sympy(
    rhs_exprs: Sequence[Any],
    state_vars: Sequence[sp.Symbol],
    params: Sequence[sp.Symbol],
    *,
    t_symbol: sp.Symbol,
    t_span,
    y0,
    param_values: Sequence[Any],
    jacobian: bool = False,
    **kwargs,
):
    import numpy as np
    import scipy.integrate as integrate

    rhs_vec = sp.Matrix([prepare_for_numeric_stack(e) for e in rhs_exprs])
    rhs_fn = sp.lambdify((t_symbol, *state_vars, *params), rhs_vec, "numpy")

    def rhs(t_value, y_vec):
        out = rhs_fn(t_value, *y_vec, *param_values)
        return np.asarray(out, dtype=float).reshape(-1)

    if jacobian:
        J = rhs_vec.jacobian(state_vars)
        J_fn = sp.lambdify((t_symbol, *state_vars, *params), J, "numpy")

        def jac(t_value, y_vec):
            return np.asarray(J_fn(t_value, *y_vec, *param_values), dtype=float)

        kwargs["jac"] = jac

    return integrate.solve_ivp(rhs, t_span=t_span, y0=y0, **kwargs)


def pandas_apply_formula(df, expr: Any, input_columns: Sequence[str], output_column: str):
    import numpy as np

    symbols = [sp.Symbol(c) for c in input_columns]
    f = numpy_function(symbols, expr)

    arrays = [df[c].to_numpy() for c in input_columns]
    df[output_column] = f(*arrays)
    return df


def xarray_apply_formula(data_arrays: Sequence[Any], expr: Any, symbols: Sequence[sp.Symbol], **kwargs):
    import xarray as xr

    f = numpy_function(symbols, expr)
    return xr.apply_ufunc(f, *data_arrays, **kwargs)


def matplotlib_plot_expr(expr: Any, var: sp.Symbol, start: float, stop: float, *, n: int = 1000):
    import matplotlib.pyplot as plt

    xs, ys = numpy_samples(expr, var, start, stop, n=n)

    fig, ax = plt.subplots()
    ax.plot(xs, ys)
    ax.set_xlabel(str(var))
    ax.set_title(f"${sp.latex(sp.sympify(expr))}$")
    return fig, ax


def compiled_ufunc(args: Sequence[sp.Symbol], expr: Any, *, backend: Literal["f2py", "cython"] = "f2py"):
    from sympy.utilities.autowrap import ufuncify

    expr = prepare_for_numeric_stack(expr)
    return ufuncify(list(args), expr, backend=backend)


def compiled_autowrap(
    expr: Any,
    args: Sequence[sp.Symbol],
    *,
    backend: Literal["f2py", "cython"] = "cython",
    tempdir: str | None = None,
    verbose: bool = False,
):
    from sympy.utilities.autowrap import autowrap

    expr = prepare_for_numeric_stack(expr)

    kwargs = {
        "args": list(args),
        "backend": backend,
        "verbose": verbose,
    }
    if tempdir is not None:
        kwargs["tempdir"] = tempdir

    return autowrap(expr, **kwargs)


def assert_backend_matches_reference(
    expr: Any,
    args: Sequence[sp.Symbol],
    values: Sequence[Any],
    *,
    backend: NumericBackend = "numpy",
    atol: float = 1e-12,
    rtol: float = 1e-12,
):
    expr = prepare_for_numeric_stack(expr)

    ref = sp.lambdify(args, expr, "mpmath")
    test = lambdify_backend(args, expr, backend=backend)

    expected = complex(ref(*values))
    actual = complex(test(*values))

    err = abs(actual - expected)
    scale = max(1.0, abs(expected))
    tol = atol + rtol*scale

    if err > tol:
        raise AssertionError({
            "backend": backend,
            "values": values,
            "actual": actual,
            "expected": expected,
            "abs_error": err,
            "tolerance": tol,
        })


def choose_interop_path(
    *,
    exact_symbolic: bool = False,
    scalar_high_precision: bool = False,
    numpy_arrays: bool = False,
    scipy_solver: bool = False,
    pandas_table: bool = False,
    xarray_grid: bool = False,
    gpu: bool = False,
    jax_autodiff_or_jit: bool = False,
    compiled: bool = False,
):
    if exact_symbolic:
        return "Stay in SymPy."
    if scalar_high_precision:
        return "Use evalf or lambdify(..., 'mpmath')."
    if scipy_solver:
        return "Derive expressions/Jacobians in SymPy; lambdify to NumPy/SciPy callables; call SciPy."
    if pandas_table:
        return "lambdify(..., 'numpy'), evaluate arrays, assign numeric columns."
    if xarray_grid:
        return "lambdify(..., 'numpy'), apply with xarray.apply_ufunc."
    if jax_autodiff_or_jit:
        return "lambdify(..., 'jax'), test eager and jit."
    if gpu:
        return "lambdify(..., 'cupy') for CuPy GPU arrays."
    if compiled:
        return "Use ufuncify/autowrap or codegen plus external build."
    if numpy_arrays:
        return "Use lambdify(..., 'numpy')."
    return "Use lambdify(..., 'math') or evalf for one-off scalar evaluation."
```

This harness enforces the domain rule: SymPy for exact symbolic derivation; `lambdify` for numeric-stack callables; SciPy for numeric solvers/integration/sparse/special workflows; mpmath for high-precision scalar references; pandas/xarray for numeric data structures after conversion; JAX/CuPy for accelerator arrays; matplotlib for explicit figure generation; and F2PY/Cython-backed `ufuncify`/`autowrap` for compiled deployment.

[1]: https://docs.sympy.org/latest/explanation/best-practices.html?utm_source=chatgpt.com "Best Practices - SymPy 1.14.0 documentation"
[2]: https://docs.sympy.org/latest/modules/numeric-computation.html?utm_source=chatgpt.com "Numeric Computation - SymPy 1.14.0 documentation"
[3]: https://numpy.org/doc/stable/reference/arrays.dtypes.html?utm_source=chatgpt.com "Data type objects (dtype)"
[4]: https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.quad.html?utm_source=chatgpt.com "quad — SciPy v1.17.0 Manual"
[5]: https://docs.scipy.org/doc/scipy/reference/optimize.html?utm_source=chatgpt.com "Optimization and root finding - Numpy and Scipy Documentation"
[6]: https://docs.scipy.org/doc/scipy/reference/sparse.html?utm_source=chatgpt.com "Sparse arrays (scipy.sparse) — SciPy v1.17.0 Manual"
[7]: https://docs.scipy.org/doc/scipy/reference/special.html?utm_source=chatgpt.com "Special functions (scipy.special) — SciPy v1.17.0 Manual"
[8]: https://mpmath.org/?utm_source=chatgpt.com "mpmath - Python library for arbitrary-precision floating-point ..."
[9]: https://mpmath.org/doc/current/basics.html?utm_source=chatgpt.com "Basic usage — mpmath 1.3.0 documentation"
[10]: https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.dtypes.html?utm_source=chatgpt.com "pandas.DataFrame.dtypes — pandas 3.0.2 documentation"
[11]: https://pandas.pydata.org/docs/user_guide/text.html?utm_source=chatgpt.com "Working with text data — pandas 3.0.2 documentation"
[12]: https://docs.xarray.dev/en/stable/generated/xarray.apply_ufunc.html?utm_source=chatgpt.com "xarray.apply_ufunc"
[13]: https://docs.xarray.dev/en/stable/user-guide/dask.html?utm_source=chatgpt.com "Parallel Computing with Dask"
[14]: https://docs.jax.dev/en/latest/quickstart.html?utm_source=chatgpt.com "Quickstart: How to think in JAX"
[15]: https://cupy.dev/?utm_source=chatgpt.com "CuPy: NumPy & SciPy for GPU"
[16]: https://matplotlib.org/stable/users/index.html?utm_source=chatgpt.com "Using Matplotlib — Matplotlib 3.10.9 documentation"
[17]: https://numpy.org/doc/stable/f2py/?utm_source=chatgpt.com "F2PY user guide and reference manual"
[18]: https://cython.readthedocs.io/en/latest/src/userguide/numpy_tutorial.html?utm_source=chatgpt.com "Cython for NumPy users"


# 25) Extending SymPy — agent-ready deep dive

## 25.0 Extension-surface map

```text
Extension surfaces:
  undefined symbolic functions
  custom Function subclasses
  custom Basic / Expr subclasses
  custom assumptions handlers
  custom printing hooks / printer subclasses
  custom rewrite / expansion / evaluation hooks
  custom numeric evaluation hooks
  custom polynomial domains
  upstream contributions: tests, docs, deprecations
```

SymPy is explicitly designed to be extended with custom classes, typically by subclassing `Basic`, `Expr`, or `Function`; the same object-model rules apply to user classes and internal SymPy classes. `Function` subclasses are intended for complex-valued mathematical functions, while functions accepting/returning non-complex objects should usually subclass a different base such as `Boolean`, `MatrixExpr`, `Expr`, or `Basic`. ([SymPy Documentation][1])

---

## 25.1 Extension decision matrix

| Need                                                                           | Use                                                                        |
| ------------------------------------------------------------------------------ | -------------------------------------------------------------------------- |
| symbolic placeholder function, no custom behavior                              | `Function("f")`                                                            |
| shorthand that always expands to existing expression                           | ordinary Python function returning SymPy expression                        |
| symbolic function with special values, derivative, evalf, assumptions, rewrite | subclass `Function`                                                        |
| symbolic object not naturally a scalar function                                | subclass `Expr` or `Basic`                                                 |
| object participates in `+`, `*`, powers, calculus                              | subclass `Expr`                                                            |
| object is structural metadata / non-algebraic symbolic node                    | subclass `Basic`                                                           |
| matrix-shaped symbolic object                                                  | subclass/use `MatrixExpr`                                                  |
| boolean-valued symbolic object                                                 | subclass/use Boolean classes                                               |
| exact polynomial coefficient system                                            | use existing `Domain` first; custom domains only for advanced/internal use |
| custom rendering only                                                          | object `_latex`/`_sympystr` method or custom printer subclass              |
| numerical-only callable                                                        | `lambdify`, `implemented_function`, backend module mapping                 |
| upstream SymPy feature                                                         | tests + docs + deprecation policy compliance                               |

---

## 25.2 Undefined symbolic functions

```python
import sympy as sp

x, y = sp.symbols("x y")

f = sp.Function("f")
expr = f(x)

expr.diff(x)
# Derivative(f(x), x)
```

Use `Function("f")` when the function should remain fully symbolic and no custom simplification, derivative, numeric evaluation, assumptions logic, or printer is needed. Undefined functions can carry assumptions such as `real=True`, but those assumptions describe the output/range of the function, not argument-dependent domain logic. For argument-dependent behavior, define a custom `Function` subclass. ([SymPy Documentation][2])

```python
g = sp.Function("g", real=True)
assert g(x).is_real is True
```

---

## 25.3 Python helper vs symbolic `Function`

### Python helper: use when expression should always expand

```python
def versin_expr(x):
    return 1 - sp.cos(x)

versin_expr(x)
# 1 - cos(x)
```

### Custom `Function`: use when unevaluated identity matters

```python
class versin(sp.Function):
    pass

versin(x)
# versin(x)
```

Do not make `eval()` merely return the mathematical definition for all inputs; the custom-function guide states that `eval()` is not the mathematical definition, but the automatic-evaluation policy. If a function always returns an existing expression and never remains as its own node, a plain Python helper or `Piecewise` is usually simpler. ([SymPy Documentation][2])

---

## 25.4 Custom `Function` subclass

## 25.4.1 Minimal skeleton

```python
class MyFunc(sp.Function):
    pass

obj = MyFunc(x)
assert isinstance(obj, MyFunc)
```

If no hooks are implemented, SymPy leaves most behavior unevaluated. For example, absent differentiation support, `diff()` returns an unevaluated `Derivative`. ([SymPy Documentation][2])

---

## 25.4.2 `eval(cls, *args)`: automatic evaluation

```python
class versin(sp.Function):
    @classmethod
    def eval(cls, x):
        n = x / sp.pi
        if isinstance(n, sp.Integer):
            return 1 - (-1)**n
        # implicit None => remain unevaluated
```

Contract:

```text
eval:
  @classmethod
  receives raw function arguments
  returns SymPy object or None
  returning None keeps function unevaluated
  also defines accepted call signature
  should be cheap
  should evaluate explicit special values only
```

The custom-function guide recommends minimizing automatic evaluation, avoiding slow work in `eval()`, and usually avoiding assumption-driven evaluation inside `eval()`; advanced simplifications belong in `doit()`, rewrites, expansion hooks, or simplification-specific methods. ([SymPy Documentation][2])

Anti-pattern:

```python
class bad_versin(sp.Function):
    @classmethod
    def eval(cls, x):
        return 1 - sp.cos(x)  # bad if symbolic identity node is desired
```

---

## 25.4.3 Input-domain validation in `eval`

Bad:

```python
class divides_bad(sp.Function):
    @classmethod
    def eval(cls, m, n):
        if not m.is_integer or not n.is_integer:
            raise TypeError("m and n must be integers")
```

Good:

```python
class divides(sp.Function):
    @classmethod
    def eval(cls, m, n):
        if isinstance(m, sp.Integer) and isinstance(n, sp.Integer):
            if m == 0:
                raise ZeroDivisionError("division by zero")
            return sp.Integer(int(n % m == 0))

        if m.is_integer is False or n.is_integer is False:
            raise TypeError("m and n must be integers")

        # None means unknown; allow symbolic construction
```

When restricting input domains, allow `None` from assumptions queries. SymPy’s custom-function guide explicitly warns that assumptions may return `None` even when a property is mathematically true but not proven, so rejection logic should reject only `is_* is False`. ([SymPy Documentation][2])

---

## 25.4.4 `fdiff(self, argindex=1)`: derivatives for `Function`

```python
from sympy.core.function import ArgumentIndexError

class FMA(sp.Function):
    """
    FMA(x, y, z) = x*y + z
    """

    def fdiff(self, argindex):
        x, y, z = self.args
        if argindex == 1:
            return y
        if argindex == 2:
            return x
        if argindex == 3:
            return sp.Integer(1)
        raise ArgumentIndexError(self, argindex)
```

`Function` subclasses should define differentiation with `fdiff(self, argindex)`, returning the derivative with respect to the selected argument **without** chain rule; `diff()` applies the chain rule automatically. The guide says user code should call `diff()`, not `fdiff()` directly, and non-`Function` `Expr` subclasses use `_eval_derivative()` instead. ([SymPy Documentation][2])

```python
FMA(x**2, x + 1, y).diff(x)
# x**2 + 2*x*(x + 1)
```

---

## 25.4.5 `_eval_evalf(self, prec)`: numerical evaluation

```python
class versin(sp.Function):
    def _eval_evalf(self, prec):
        x, = self.args
        return (2*sp.sin(x/2)**2)._eval_evalf(prec)
```

`_eval_evalf(self, prec)` defines floating-point numerical evaluation. The `prec` argument is binary precision in bits, not decimal digits; recursive implementations should call `subexpr._eval_evalf(prec)`, not `subexpr.evalf(prec)`, because `evalf()` interprets its first argument as decimal precision. Once `_eval_evalf` is defined, floating-point inputs can automatically evaluate. ([SymPy Documentation][2])

---

## 25.4.6 `_eval_rewrite(self, rule, args, **hints)`

```python
class versin(sp.Function):
    def _eval_rewrite(self, rule, args, **hints):
        x, = args
        if rule == sp.cos:
            return 1 - sp.cos(x)
        if rule == sp.sin:
            return 2*sp.sin(x/2)**2
        return None
```

`_eval_rewrite` should return a rewritten expression or `None`. Use the supplied `args`, not `self.args`, because recursive rewrites are already reflected in `args` when `rewrite(deep=True)` is used. Unknown hints should be ignored or passed through. ([SymPy Documentation][2])

---

## 25.4.7 `doit(self, **hints)`: explicit evaluation

```python
class FMA(sp.Function):
    @classmethod
    def eval(cls, x, y, z):
        if all(isinstance(a, sp.Number) for a in (x, y, z)):
            return x*y + z

    def doit(self, **hints):
        x, y, z = self.args
        return x*y + z
```

Use `doit()` for advanced or potentially expensive evaluation that should not occur automatically at construction. The custom-function guide recommends this pattern when automatic `eval()` would be too eager but explicit evaluation is useful. ([SymPy Documentation][2])

---

## 25.4.8 `_eval_expand_<hint>`

```python
class versin(sp.Function):
    def _eval_expand_trig(self, **hints):
        x, = self.args
        return sp.expand_trig(1 - sp.cos(x))
```

Custom functions can implement expansion-specific behavior via methods named `_eval_expand_<hint>`, such as `_eval_expand_trig`. This integrates with `expand(trig=True)` and keeps expansion explicit rather than automatic. ([SymPy Documentation][2])

---

## 25.4.9 `as_real_imag(self, deep=True, **hints)`

```python
class versin(sp.Function):
    def as_real_imag(self, deep=True, **hints):
        x, = self.args
        return (1 - sp.cos(x)).as_real_imag(deep=deep, **hints)
```

`as_real_imag()` should return `(real_part, imaginary_part)` and enables complex expansion behavior such as `expand(complex=True)`. The custom-function guide states that `as_real_imag` should honor `deep` and ignore/pass unknown hints. ([SymPy Documentation][2])

---

## 25.4.10 `inverse(self, argindex=1)`

```python
class aversin(sp.Function):
    def inverse(self, argindex=1):
        return versin
```

`inverse()` is used by `solve()` and `solveset()` and should return a function, not an expression. Define it only for one-to-one functions; defining an inverse for a non-injective function can cause solvers to miss branches. ([SymPy Documentation][2])

---

## 25.5 Assumptions handlers for custom functions

## 25.5.1 `_eval_is_*` methods

```python
from sympy.core.logic import fuzzy_and, fuzzy_not

class versin(sp.Function):
    def _eval_is_nonnegative(self):
        x, = self.args
        if x.is_real is True:
            return True

    def _eval_is_positive(self):
        x, = self.args
        coeff, pi_part = x.as_independent(sp.pi, as_Add=False)

        if pi_part == sp.pi:
            return fuzzy_and([x.is_real, fuzzy_not(coeff.is_even)])
        if x.is_real is False:
            return False
```

Assumptions handlers must return `True`, `False`, or `None`. The guide recommends structural decomposition such as `as_independent()` inside assumptions handlers and warns not to create new expressions there, because expression construction can be slow and can recursively trigger assumptions queries. ([SymPy Documentation][2])

## 25.5.2 Assumption class variables

```python
class NonnegativeRealFunc(sp.Function):
    is_nonnegative = True
```

Fixed assumptions can be class variables. Dynamic assumptions depending on `.args` should be `_eval_is_*` methods. Never define `is_<assumption>` as a `@property`; the custom-function guide says doing so breaks automatic deduction of other assumptions. ([SymPy Documentation][2])

## 25.5.3 Fuzzy logic contract

```text
Assumption handler rules:
  return True only when definitely true
  return False only when definitely false
  return None or fall through when unknown
  use fuzzy_and / fuzzy_or / fuzzy_not
  avoid creating new expressions
  do not query the same assumption on self inside its own handler
```

The guide explicitly points to careful three-valued logic handling in assumptions handlers because subqueries such as `x.is_real` or `coeff.is_even` may be `None`. ([SymPy Documentation][2])

---

## 25.6 Custom `Basic` / `Expr` subclasses

## 25.6.1 Basic invariants

Custom SymPy objects must satisfy two core invariants: every element of `.args` must be a `Basic`, and `expr.func(*expr.args) == expr`. SymPy’s best-practices docs state these invariants are assumed throughout SymPy and are essential for functions that manipulate expressions. ([SymPy Documentation][1])

```text
Invariant 1:
  all(isinstance(arg, Basic) for arg in expr.args)

Invariant 2:
  expr.func(*expr.args) == expr
```

## 25.6.2 Minimal `Expr` subclass

```python
class WeightedSymbol(sp.Expr):
    is_commutative = True

    def __new__(cls, symbol, weight):
        symbol = sp.sympify(symbol)
        weight = sp.sympify(weight)

        if not isinstance(symbol, sp.Symbol):
            raise TypeError("symbol must be a Symbol")

        obj = sp.Expr.__new__(cls, symbol, weight)
        return obj

    @property
    def symbol(self):
        return self.args[0]

    @property
    def weight(self):
        return self.args[1]

    def _eval_derivative(self, s):
        if s == self.symbol:
            return self.weight
        return sp.Integer(0)

    def _eval_evalf(self, prec):
        return (self.weight * self.symbol)._eval_evalf(prec)

    def _eval_is_real(self):
        return sp.fuzzy_and([self.symbol.is_real, self.weight.is_real])

    def _latex(self, printer):
        return r"%s\,%s" % (
            printer._print(self.weight),
            printer._print(self.symbol),
        )
```

Use `__new__`, not `__init__`, because SymPy objects are immutable. Sympify all args, validate input types early, store state exclusively in `.args`, and expose named properties for readability.

## 25.6.3 `Basic` subclass for non-algebraic symbolic objects

```python
class TaggedObject(sp.Basic):
    def __new__(cls, expr, tag):
        expr = sp.sympify(expr)
        tag = sp.Symbol(str(tag)) if not isinstance(tag, sp.Basic) else tag
        return sp.Basic.__new__(cls, expr, tag)

    @property
    def expr(self):
        return self.args[0]

    @property
    def tag(self):
        return self.args[1]
```

Use `Basic` when the object should participate in SymPy tree traversal, substitution, hashing, and printing, but should **not** behave as an algebraic scalar expression under `+`, `*`, `Pow`, calculus, or numeric evaluation.

## 25.6.4 `Expr` vs `Function` vs `Basic`

```text
Function subclass:
  f(x)-style applied function
  supports fdiff, _eval_evalf, _eval_rewrite, _eval_is_*
  default complex-valued scalar function model

Expr subclass:
  algebraic scalar object
  can appear in Add/Mul/Pow
  derivative support via _eval_derivative
  must define algebraic semantics carefully

Basic subclass:
  symbolic tree node
  not necessarily algebraic
  safest for metadata-like symbolic nodes
```

---

## 25.7 Canonicalization, immutability, and hash stability

## 25.7.1 Canonicalization in `__new__`

```python
class SortedPair(sp.Basic):
    def __new__(cls, a, b):
        a = sp.sympify(a)
        b = sp.sympify(b)

        a, b = sorted([a, b], key=sp.default_sort_key)
        return sp.Basic.__new__(cls, a, b)
```

Use canonicalization when mathematically equivalent inputs should produce structurally equal objects.

## 25.7.2 Do not mutate instances

```python
# Bad
obj.cache = something

# Better
_external_cache[obj] = something
```

SymPy objects should be immutable. Store only `.args`-derived state in the object. Use external caches, `@property`, or cached computations only if they do not change semantic equality or hash behavior.

## 25.7.3 Hash-stability checklist

```text
Hash-stable custom object:
  all semantic state appears in args
  args are Basic instances
  no mutable lists/dicts in args
  func(*args) reconstructs equivalent object
  __eq__ not redefined for mathematical equality
  no post-construction mutation
```

---

## 25.8 Custom printers

## 25.8.1 Object-local printer hook

```python
class divides(sp.Function):
    def _latex(self, printer):
        m, n = self.args
        return r"\left[%s \middle| %s\right]" % (
            printer._print(m),
            printer._print(n),
        )
```

SymPy’s printer dispatch first lets an object print itself through a printer-specific method, then falls back to printer methods, then to the printer’s empty/default printer. For LaTeX, the object method is `_latex(self, printer)`, and the custom-function guide explicitly says to use `printer._print()` recursively on arguments. ([SymPy Documentation][3])

## 25.8.2 Printer methods by target

```text
StrPrinter:
  _sympystr(self, printer)

LatexPrinter:
  _latex(self, printer)

PrettyPrinter:
  printer-specific pretty hooks

Code printers:
  usually better through custom printer subclass or user_functions mapping
```

## 25.8.3 Custom printer subclass

```python
from sympy.printing.latex import LatexPrinter

class MyLatexPrinter(LatexPrinter):
    def _print_WeightedSymbol(self, expr):
        return r"%s\,%s" % (
            self._print(expr.weight),
            self._print(expr.symbol),
        )

def my_latex(expr):
    return MyLatexPrinter().doprint(expr)
```

Use object-local hooks for a small library of custom objects. Use printer subclasses when many classes or target-wide style rules must be controlled.

---

## 25.9 Custom simplification and rewrite methods

## 25.9.1 Preferred hooks

```text
Function subclass:
  eval
  doit
  fdiff
  _eval_evalf
  _eval_rewrite
  _eval_expand_<hint>
  as_real_imag
  inverse
  _eval_is_*

Expr subclass:
  _eval_derivative
  _eval_evalf
  _eval_rewrite
  _eval_expand_<hint>
  as_real_imag
  _eval_is_*
  class-level flags: is_commutative, is_real, etc.
```

## 25.9.2 Avoid global `simplify` dependence

```python
class MyExpr(sp.Expr):
    def _eval_rewrite(self, rule, args, **hints):
        ...
```

Do not rely on `simplify()` discovering every identity. Put identity-specific behavior in explicit rewrite, expansion, `doit`, or targeted helper methods, then test those methods directly.

## 25.9.3 Pattern

```python
class SafeLog1p(sp.Function):
    @classmethod
    def eval(cls, x):
        if x == 0:
            return sp.Integer(0)

    def fdiff(self, argindex=1):
        if argindex == 1:
            x, = self.args
            return 1/(1 + x)
        raise sp.core.function.ArgumentIndexError(self, argindex)

    def _eval_rewrite(self, rule, args, **hints):
        x, = args
        if rule == sp.log:
            return sp.log(1 + x)

    def _eval_evalf(self, prec):
        x, = self.args
        return sp.log(1 + x)._eval_evalf(prec)

    def _latex(self, printer):
        return r"\operatorname{log1p}\left(%s\right)" % printer._print(self.args[0])
```

---

## 25.10 Adding support for calculus and numeric evaluation

## 25.10.1 Derivatives

```python
class CustomScalar(sp.Expr):
    def _eval_derivative(self, sym):
        ...
```

```python
class CustomFunction(sp.Function):
    def fdiff(self, argindex=1):
        ...
```

For `Function` subclasses, use `fdiff()`. For non-`Function` `Expr` subclasses, define `_eval_derivative()`. ([SymPy Documentation][2])

## 25.10.2 Numeric evaluation

```python
def _eval_evalf(self, prec):
    ...
```

Use `_eval_evalf(self, prec)` for numerical evaluation. Remember `prec` is binary precision, not decimal digits. ([SymPy Documentation][2])

## 25.10.3 Series and integrals

Recommended order:

```text
1. Provide rewrites to existing SymPy functions.
2. Provide derivatives via fdiff / _eval_derivative.
3. Provide evalf via _eval_evalf.
4. Add expansion hooks where targeted expansion is meaningful.
5. Implement lower-level series/integration hooks only after checking analogous SymPy source patterns and adding extensive tests.
```

Practical examples:

```python
class MyFunc(sp.Function):
    def _eval_rewrite(self, rule, args, **hints):
        x, = args
        if rule == sp.exp:
            return ...  # expression using built-ins with known series/integrals
```

For many custom functions, rewriting to built-ins is the most robust way to inherit existing integration, series, simplification, and codegen behavior.

---

## 25.11 Custom domains and polynomial extensions

## 25.11.1 Prefer existing domains

```python
from sympy import ZZ, QQ, GF, Poly

P = Poly(x**2 + 1, x, domain=QQ)
Q = Poly(x**2 + 1, x, modulus=5)
```

SymPy’s polys domain system has abstract, concrete, and implementation domains; `Poly` coefficients are elements of a `Domain`, and common domains include `ZZ` and `QQ`. The docs also note that implementation domains can vary depending on available libraries, so code should use domain APIs rather than relying on concrete Python element classes. ([SymPy Documentation][4])

## 25.11.2 Custom domain caution

```text
Custom Domain subclass requires:
  dtype element type
  conversion methods
  arithmetic operations
  exact quotient / division semantics
  coercion / unification rules
  zero/one handling
  polynomial algorithm compatibility
  extensive tests
```

Use custom domains only for advanced algebraic infrastructure. For most extension projects, prefer `ZZ`, `QQ`, algebraic fields, rational-function fields, `GF(p)`, or custom `Expr` coefficients inside existing polynomial rings.

---

## 25.12 Contribution workflow, tests, docs, deprecations

## 25.12.1 Tests

SymPy’s contribution docs state that correctness is the top concern, all new functionality must be tested, PRs must pass CI, and bug fixes should include regression tests. Tests live in neighboring `tests/` directories and in `test_<thing>.py` files. ([SymPy Documentation][5])

Minimum test categories:

```text
custom class:
  construction
  args invariant
  rebuild invariant
  equality/hash
  substitution/xreplace
  assumptions
  printing
  differentiation
  evalf
  rewrite
  expand
  doit
  pickling if relevant

custom function:
  explicit special values
  generic unevaluated behavior
  invalid domain rejection
  None assumptions allowed
  fdiff/chain rule
  evalf precision
  rewrite/expand/as_real_imag
  LaTeX/code printing
  solving/inverse if implemented

custom domain:
  arithmetic laws
  conversion/coercion
  exact quotient
  zero/one behavior
  Poly integration
  failure cases
```

## 25.12.2 Docs

Docs should explain mathematical definition, domain/codomain, assumptions, examples, return shapes, exceptions, and rewrite/evaluation behavior. SymPy’s contributing guide points new contributors through docs, tests, dependencies, debugging, and deprecation policy sections, and documentation is part of the expected contribution workflow. ([SymPy Documentation][6])

## 25.12.3 Deprecations

Backwards-incompatible API changes should be avoided when possible. SymPy’s deprecation policy defines deprecation as continuing to work while warning users and giving an alternative; the policy explicitly says breaking changes should not be made lightly because users depend on stable APIs. ([SymPy Documentation][7])

Deprecation checklist:

```text
If changing public behavior:
  avoid if compatible path exists
  add deprecation warning
  document replacement
  add/update active deprecation entry if upstream
  test warning behavior
  preserve behavior through deprecation window
```

---

## 25.13 Anti-pattern inventory

| Anti-pattern                                    | Failure mode                              | Correct pattern                         |
| ----------------------------------------------- | ----------------------------------------- | --------------------------------------- |
| custom object args contain Python `list`/`dict` | non-Basic args, hashing/traversal failure | sympify/tuple/Basic args                |
| storing semantic state outside `.args`          | rebuild/equality/hash drift               | all semantic state in `.args`           |
| redefining `__eq__` for math equality           | breaks structural equality assumptions    | use `.equals()` or normal forms         |
| mutating SymPy instance after construction      | hash/cache corruption                     | immutable design                        |
| `eval()` always returns definition              | function node never exists                | Python helper or `doit`/rewrite         |
| expensive work in `eval()`                      | slow expression construction              | explicit `doit`/rewrite/simplify method |
| rejecting `None` assumptions                    | valid symbolic inputs fail                | reject only `is_* is False`             |
| creating expressions in `_eval_is_*`            | recursion/performance bugs                | structural decomposition                |
| defining `is_positive` as property              | assumptions deduction breakage            | class var or `_eval_is_positive`        |
| redefining `_eval_derivative` on `Function`     | bypasses `fdiff` convention               | implement `fdiff`                       |
| custom `_eval_evalf` uses `evalf(prec)`         | precision mismatch                        | use `_eval_evalf(prec)`                 |
| custom printer uses `str(arg)`                  | broken nested output                      | `printer._print(arg)`                   |
| custom domain without coercion tests            | Poly algorithm failures                   | use existing domains or fully test      |
| upstream feature without regression tests       | PR rejection / correctness risk           | add tests beside modified module        |
| breaking API without deprecation                | user breakage                             | follow deprecation policy               |

---

## 25.14 Extension QA checklist

```text
Object invariants:
  [ ] all args are Basic
  [ ] expr.func(*expr.args) == expr
  [ ] immutable
  [ ] hash stable
  [ ] no hidden mutable semantic state

Construction:
  [ ] sympifies args
  [ ] validates domains without rejecting unknown assumptions incorrectly
  [ ] canonicalizes equivalent inputs if appropriate
  [ ] cheap construction

Assumptions:
  [ ] returns True/False/None correctly
  [ ] uses fuzzy logic helpers
  [ ] no expression construction in handlers
  [ ] no is_* properties

Behavior:
  [ ] derivative support
  [ ] evalf support
  [ ] rewrite support
  [ ] expansion support
  [ ] real/imag support if complex values matter
  [ ] inverse only if injective
  [ ] doit for explicit evaluation

Printing:
  [ ] latex/string/pretty/code behavior tested
  [ ] printer._print used recursively

Testing:
  [ ] construction tests
  [ ] invalid input tests
  [ ] regression tests
  [ ] edge cases
  [ ] symbolic equivalence
  [ ] numeric checks
  [ ] docs examples
```

---

## 25.15 Minimal extension harness

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import sympy as sp
from sympy.core.logic import fuzzy_and, fuzzy_not
from sympy.core.function import ArgumentIndexError


@dataclass(frozen=True)
class ExtensionAudit:
    obj: sp.Basic
    type_name: str
    args_are_basic: bool
    rebuilds: bool
    hashable: bool
    free_symbols: set[sp.Symbol]
    assumptions: dict[str, bool | None]
    srepr: str
    latex: str


def audit_custom_object(obj: sp.Basic) -> ExtensionAudit:
    obj = sp.sympify(obj)

    try:
        hash(obj)
        hashable = True
    except TypeError:
        hashable = False

    try:
        rebuilds = obj.func(*obj.args) == obj
    except Exception:
        rebuilds = False

    return ExtensionAudit(
        obj=obj,
        type_name=type(obj).__name__,
        args_are_basic=all(isinstance(a, sp.Basic) for a in obj.args),
        rebuilds=rebuilds,
        hashable=hashable,
        free_symbols=set(obj.free_symbols),
        assumptions={
            "real": obj.is_real,
            "positive": obj.is_positive,
            "zero": obj.is_zero,
            "finite": obj.is_finite,
        },
        srepr=sp.srepr(obj),
        latex=sp.latex(obj),
    )


def assert_basic_invariants(obj: sp.Basic) -> None:
    obj = sp.sympify(obj)

    assert all(isinstance(a, sp.Basic) for a in obj.args), (
        "all .args must be Basic instances",
        obj.args,
    )

    assert obj.func(*obj.args) == obj, (
        "object must rebuild from func(*args)",
        sp.srepr(obj),
    )

    hash(obj)


class Versin(sp.Function):
    r"""
    Versin(x) = 1 - cos(x) = 2*sin(x/2)**2.
    """

    @classmethod
    def eval(cls, x):
        n = x / sp.pi
        if isinstance(n, sp.Integer):
            return 1 - (-1)**n

    def fdiff(self, argindex=1):
        if argindex == 1:
            return sp.sin(self.args[0])
        raise ArgumentIndexError(self, argindex)

    def _eval_is_nonnegative(self):
        x, = self.args
        if x.is_real is True:
            return True

    def _eval_is_positive(self):
        x, = self.args
        coeff, pi_part = x.as_independent(sp.pi, as_Add=False)

        if pi_part == sp.pi:
            return fuzzy_and([x.is_real, fuzzy_not(coeff.is_even)])
        if x.is_real is False:
            return False

    def _eval_evalf(self, prec):
        x, = self.args
        return (2*sp.sin(x/2)**2)._eval_evalf(prec)

    def _eval_rewrite(self, rule, args, **hints):
        x, = args
        if rule == sp.cos:
            return 1 - sp.cos(x)
        if rule == sp.sin:
            return 2*sp.sin(x/2)**2

    def _eval_expand_trig(self, **hints):
        x, = self.args
        return sp.expand_trig(1 - sp.cos(x))

    def as_real_imag(self, deep=True, **hints):
        x, = self.args
        return (1 - sp.cos(x)).as_real_imag(deep=deep, **hints)

    def _latex(self, printer):
        return r"\operatorname{versin}{\left(%s\right)}" % printer._print(self.args[0])


class Divides(sp.Function):
    r"""
    Divides(m, n) = 1 if integer m divides integer n, else 0.
    """

    @classmethod
    def eval(cls, m, n):
        if isinstance(m, sp.Integer) and isinstance(n, sp.Integer):
            if m == 0:
                raise ZeroDivisionError("divisibility by zero is undefined")
            return sp.Integer(int(n % m == 0))

        if m.is_integer is False or n.is_integer is False:
            raise TypeError("m and n must be integers")

    is_integer = True
    is_nonnegative = True

    def _eval_is_zero(self):
        m, n = self.args
        if isinstance(m, sp.Integer) and isinstance(n, sp.Integer) and m != 0:
            return n % m != 0

    def _latex(self, printer):
        m, n = self.args
        return r"\left[%s \middle| %s\right]" % (
            printer._print(m),
            printer._print(n),
        )


class WeightedSymbol(sp.Expr):
    is_commutative = True

    def __new__(cls, symbol, weight):
        symbol = sp.sympify(symbol)
        weight = sp.sympify(weight)

        if not isinstance(symbol, sp.Symbol):
            raise TypeError("symbol must be a Symbol")

        return sp.Expr.__new__(cls, symbol, weight)

    @property
    def symbol(self):
        return self.args[0]

    @property
    def weight(self):
        return self.args[1]

    def _eval_derivative(self, sym):
        if sym == self.symbol:
            return self.weight
        return sp.Integer(0)

    def _eval_evalf(self, prec):
        return (self.weight * self.symbol)._eval_evalf(prec)

    def _eval_is_real(self):
        return fuzzy_and([self.symbol.is_real, self.weight.is_real])

    def _eval_rewrite(self, rule, args, **hints):
        symbol, weight = args
        if rule == sp.Mul:
            return weight * symbol

    def doit(self, **hints):
        return self.weight * self.symbol

    def _latex(self, printer):
        return r"%s\,%s" % (
            printer._print(self.weight),
            printer._print(self.symbol),
        )


class TaggedObject(sp.Basic):
    def __new__(cls, expr, tag):
        expr = sp.sympify(expr)
        tag = sp.Symbol(str(tag)) if not isinstance(tag, sp.Basic) else tag
        return sp.Basic.__new__(cls, expr, tag)

    @property
    def expr(self):
        return self.args[0]

    @property
    def tag(self):
        return self.args[1]


def assert_function_contract(fn_cls: type[sp.Function], sample: sp.Expr) -> None:
    obj = fn_cls(sample)

    assert_basic_invariants(obj)

    # Generic construction should not over-evaluate unless explicitly intended.
    assert isinstance(obj, fn_cls)

    # Printing should not fail.
    str(obj)
    sp.latex(obj)
    sp.srepr(obj)

    # Differentiation may evaluate or remain Derivative, but should not crash.
    sp.diff(obj, sample) if sample.is_Symbol else None

    # Numeric eval should either evaluate or leave symbolic numeric parts.
    obj.evalf()


def assert_expr_subclass_contract(obj: sp.Expr, var: sp.Symbol) -> None:
    assert isinstance(obj, sp.Expr)
    assert_basic_invariants(obj)

    # Expr must cooperate with Add/Mul.
    obj + 1
    2 * obj

    # Derivative should not crash.
    sp.diff(obj, var)

    # Rebuild and substitution should work.
    obj.xreplace({var: var})
    obj.subs(var, var)


def assert_assumption_handler_contract(obj: sp.Basic) -> None:
    for attr in ("is_real", "is_positive", "is_zero", "is_finite"):
        q = getattr(obj, attr)
        assert q in (True, False, None), (attr, q)


def symbolic_equivalence(a: sp.Expr, b: sp.Expr) -> bool:
    delta = sp.cancel(sp.together(sp.sympify(a) - sp.sympify(b)))
    if delta == 0:
        return True
    return sp.sympify(a).equals(sp.sympify(b)) is True


def test_extension_smoke():
    x = sp.Symbol("x", real=True)

    objs = [
        Versin(x),
        Divides(sp.Symbol("m", integer=True), sp.Symbol("n", integer=True)),
        WeightedSymbol(x, sp.Integer(3)),
        TaggedObject(x + 1, "source"),
    ]

    for obj in objs:
        assert_basic_invariants(obj)
        assert_assumption_handler_contract(obj)

    assert Versin(sp.pi) == 2
    assert Versin(2*sp.pi) == 0
    assert Versin(x).diff(x) == sp.sin(x)
    assert symbolic_equivalence(Versin(x).rewrite(sp.cos), 1 - sp.cos(x))

    w = WeightedSymbol(x, 3)
    assert w.doit() == 3*x
    assert sp.diff(w, x) == 3
```

This harness enforces the extension contract: `.args` invariants, rebuildability, immutability/hashability, safe `Function` hooks, assumption-handler discipline, custom printing, `Expr` subclass behavior, `Basic` subclass behavior, derivative/evalf smoke tests, and symbolic-equivalence checks.

## SMARTREF Implementation Note - 2026-05-14

SMARTREF's solver-math pre-analysis now uses SymPy as the source-neutral symbolic substrate for polynomial signatures, Jacobian/Hessian sparsity, inequality reduction, conservative linear elimination, local series summaries, asymptotic diagnostics, model-wide CSE, and targeted codegen stability rewrites. These are recorded as typed derived facts with budgets and diagnostics rather than mutating canonical problem identity.

[1]: https://docs.sympy.org/latest/explanation/best-practices.html "Best Practices - SymPy 1.14.0 documentation"
[2]: https://docs.sympy.org/latest/guides/custom-functions.html "Writing Custom Functions - SymPy 1.14.0 documentation"
[3]: https://docs.sympy.org/latest/modules/printing.html "Printing - SymPy 1.14.0 documentation"
[4]: https://docs.sympy.org/latest/modules/polys/domainsref.html "Reference docs for the Poly Domains - SymPy 1.14.0 documentation"
[5]: https://docs.sympy.org/latest/contributing/new-contributors-guide/writing-tests.html "Writing Tests - SymPy 1.14.0 documentation"
[6]: https://docs.sympy.org/latest/contributing/index.html "Contributing - SymPy 1.14.0 documentation"
[7]: https://docs.sympy.org/latest/contributing/deprecations.html "Deprecation Policy - SymPy 1.14.0 documentation"
