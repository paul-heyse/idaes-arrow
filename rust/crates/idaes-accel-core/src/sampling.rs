// SPDX-License-Identifier: BSD-3-Clause
// Copyright (c) 2026 Paul Heyse.
// Part of a fork of the IDAES Integrated Platform (IDAES IP);
// see LICENSE.md and COPYRIGHT.md at the repository root.

//! Kernels backing `idaes.core.surrogate.pysmo.sampling`.

/// Returns the first `n` prime numbers, ascending.
///
/// Mirrors `SamplingMethods.prime_number_generator` in
/// `idaes/core/surrogate/pysmo/sampling.py`. The Python version loops
/// `while len(prime_list) < n`, so a non-positive `n` yields an empty list;
/// that behaviour is reproduced rather than treated as an error.
///
/// The Python implementation uses naive trial division against every smaller
/// integer. This uses trial division against previously found primes up to
/// `sqrt(candidate)`, which is materially faster and provably yields the same
/// sequence -- "the first `n` primes" admits exactly one answer.
///
/// # Examples
///
/// ```
/// use idaes_accel_core::sampling::prime_number_generator;
/// assert_eq!(prime_number_generator(3), vec![2, 3, 5]);
/// assert!(prime_number_generator(0).is_empty());
/// ```
#[must_use]
pub fn prime_number_generator(n: i64) -> Vec<u64> {
    if n <= 0 {
        return Vec::new();
    }
    let wanted = usize::try_from(n).unwrap_or(usize::MAX);
    let mut primes: Vec<u64> = Vec::with_capacity(wanted);
    let mut candidate: u64 = 2;
    while primes.len() < wanted {
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
        assert_eq!(prime_number_generator(3), vec![2, 3, 5]);
    }

    #[test]
    fn non_positive_n_yields_empty() {
        // `while len(prime_list) < n` is immediately false for n <= 0.
        assert!(prime_number_generator(0).is_empty());
        assert!(prime_number_generator(-1).is_empty());
        assert!(prime_number_generator(i64::MIN).is_empty());
    }

    #[test]
    fn first_twenty_five_primes() {
        assert_eq!(
            prime_number_generator(25),
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
        assert_eq!(prime_number_generator(200), naive);
    }

    #[test]
    fn length_is_exactly_n() {
        for n in 0..64 {
            assert_eq!(prime_number_generator(n).len(), usize::try_from(n).unwrap());
        }
    }
}
