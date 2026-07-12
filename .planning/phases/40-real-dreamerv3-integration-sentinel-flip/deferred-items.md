# Deferred Items (out-of-scope discoveries)

| Category | Item | Discovered At | Status |
|----------|------|---------------|--------|
| Env | torch + libomp fatal abort on Python 3.14 at import time (libomp.dylib __kmp_register_library_startup). Surfaces when tests/dreamer/test_dreamerv3_subprocess_e2e.py module-level _gpu_available() does import torch. Reproduces on commit 936aa88 (before 40-01 GREEN edits) — pre-existing, NOT caused by this plan. Non-torch dreamer/subprocess suite (30 tests) passes. | 40-01 Task 2 | Acknowledged (env/Python 3.14 + torch compat; out of v0.6.0 scope) |
