// SPDX-License-Identifier: BSD-3-Clause
// Copyright (c) 2026 Paul Heyse.
// Part of a fork of the IDAES Integrated Platform (IDAES IP);
// see LICENSE.md and COPYRIGHT.md at the repository root.

//! Kernels backing `idaes.core.surrogate.pysmo.sampling`.

/// Returns the leading prime numbers, ascending, while the count is below `n`.
///
/// Mirrors `SamplingMethods.prime_number_generator` in
/// `idaes/core/surrogate/pysmo/sampling.py`, whose loop condition is
/// `while len(prime_list) < n`.
///
/// `n` is `f64`, not an integer, and that is load-bearing. The Python function
/// is untyped and its own test suite calls it with a float
/// (`test_prime_number_generator_05` passes `2.9` and expects `[2, 3, 5]`,
/// because `3 < 2.9` is false). Comparing `primes.len() as f64 < n` reproduces
/// Python's comparison exactly, including for fractional and negative `n`, which
/// both terminate immediately rather than erroring.
///
/// The Python implementation uses naive trial division against every smaller
/// integer. This uses trial division against previously found primes up to
/// `sqrt(candidate)`, which is materially faster and provably yields the same
/// sequence -- "the first k primes" admits exactly one answer.
///
/// # Examples
///
/// ```
/// use idaes_accel_core::sampling::prime_number_generator;
/// assert_eq!(prime_number_generator(3.0), vec![2, 3, 5]);
/// assert_eq!(prime_number_generator(2.9), vec![2, 3, 5]);
/// assert_eq!(prime_number_generator(0.5), vec![2]);
/// assert!(prime_number_generator(0.0).is_empty());
/// ```
#[must_use]
pub fn prime_number_generator(n: f64) -> Vec<u64> {
    // NaN compares false against everything, so Python's loop never runs for it
    // either. Spelling that out beats `!(n > 0.0)`, which reads as a typo.
    if n.is_nan() || n <= 0.0 {
        return Vec::new();
    }
    // Not pre-sized: converting `n` to a capacity needs a lossy float cast, and
    // trial division dominates the cost of a few reallocations anyway.
    let mut primes: Vec<u64> = Vec::new();
    let mut candidate: u64 = 2;
    loop {
        // Exact for any length that could be reached here: f64 represents every
        // integer below 2^53, and this loop is super-linear in `n`.
        #[allow(clippy::cast_precision_loss)]
        let reached = primes.len() as f64 >= n;
        if reached {
            break;
        }
        if is_prime_given(&primes, candidate) {
            primes.push(candidate);
        }
        candidate += 1;
    }
    primes
}

/// Tests `candidate` for primality by trial division against `primes`, which
/// must contain every prime below `candidate` in ascending order.
fn is_prime_given(primes: &[u64], candidate: u64) -> bool {
    for &p in primes {
        if p.saturating_mul(p) > candidate {
            break;
        }
        if candidate.is_multiple_of(p) {
            return false;
        }
    }
    true
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The exact example in the Python docstring.
    #[test]
    fn matches_python_docstring_example() {
        assert_eq!(prime_number_generator(3.0), vec![2, 3, 5]);
    }

    /// Regression: `test_prime_number_generator_05` in the IDAES suite calls the
    /// Python function with 2.9 and expects three primes, because the loop stops
    /// when `len(prime_list) < n` goes false. An integer signature rejected this.
    #[test]
    fn fractional_n_matches_python_comparison() {
        assert_eq!(prime_number_generator(2.9), vec![2, 3, 5]);
        assert_eq!(prime_number_generator(0.5), vec![2]);
        assert_eq!(prime_number_generator(1.000_001), vec![2, 3]);
        assert!(prime_number_generator(-0.5).is_empty());
    }

    #[test]
    fn non_positive_n_yields_empty() {
        // `while len(prime_list) < n` is immediately false for n <= 0.
        assert!(prime_number_generator(0.0).is_empty());
        assert!(prime_number_generator(-1.0).is_empty());
        assert!(prime_number_generator(f64::NEG_INFINITY).is_empty());
        // NaN: every comparison is false, in Rust and in Python alike.
        assert!(prime_number_generator(f64::NAN).is_empty());
    }

    #[test]
    fn first_twenty_five_primes() {
        assert_eq!(
            prime_number_generator(25.0),
            vec![
                2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79,
                83, 89, 97
            ]
        );
    }

    /// Cross-check against the naive algorithm the Python actually uses, so the
    /// faster trial division cannot drift from it.
    #[test]
    fn agrees_with_naive_trial_division() {
        let naive: Vec<u64> = {
            let mut out = Vec::new();
            let mut c: u64 = 2;
            while out.len() < 200 {
                if (2..c).all(|i| !c.is_multiple_of(i)) {
                    out.push(c);
                }
                c += 1;
            }
            out
        };
        assert_eq!(prime_number_generator(200.0), naive);
    }

    #[test]
    fn length_is_exactly_n() {
        for n in 0..64_u32 {
            assert_eq!(
                prime_number_generator(f64::from(n)).len(),
                usize::try_from(n).unwrap()
            );
        }
    }
}
