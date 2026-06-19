"""Demos package — RL training/evaluation/benchmark scripts for Surg-RL.

This package contains user-facing demo scripts (e.g. ``suturing_demo``,
``train_demo``, ``eval_demo``, ``benchmark``) plus private helper modules
(``_omp_compat``, ``_platform_guard``, ``_common``) that the demos share.

Public demos import private helpers via:

    from demos._common import print_banner, ...

The ``__init__`` is intentionally minimal so the demos directory remains
easy to invoke via ``python demos/suturing_demo.py`` (no implicit
package side-effects on import).
"""