# RM-153 expected-red evidence

Baseline production SHA: `1c227c323c0e9912f9a8f44dc859703e2d3fcd36`  
Audit commit: `92986ab56452f31c4b1092346b40f96691f2d976`  
Characterization commit: `c33bd916c73ea9833b08b97c4b944bc9b4b21ef2`

Before production implementation, the RM-153 theme-epoch tests were run with:

```text
python -m pytest -q --basetemp .rm153-test-tmp tests/test_rm153_theme_epoch.py
```

Result: **2 failed in 10.55s**, intentionally.

1. `test_reapplying_current_theme_is_idempotent` failed because the current shell called the root
   `setStyleSheet` once when asked to apply its already-current theme. The same pre-change method
   also invokes every page adapter and persists the unchanged setting.
2. `test_theme_change_updates_only_active_page_then_updates_stale_page_on_route` failed because a
   Dashboard theme change called the hidden workflow adapter once. The pre-change shell has no
   page-theme epoch or route-time stale-page update.

The failures are the missing behavior required by `RM-153_PERFORMANCE_CONTRACT.md`; they are not
environment, fixture, import or unrelated regression failures. Production implementation may begin
only after this evidence commit.
