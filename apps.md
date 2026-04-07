# App Audit Registry

Tracked by daily Lighthouse audit (8am UTC). Threshold: 95 on all categories.
Tasks auto-created in Taskmaster when scores drop below threshold.

---

## Apps

<!-- Repo column: verify these match your actual GitHub repo names under StarDrop9/ -->
| App | URL | Repo | Status |
|---|---|---|---|
| Taskmaster | https://todo-scribe-master.vercel.app | StarDrop9/todo-scribe-master | ✅ Active |
| ASIPro | https://asipro.vercel.app | StarDrop9/asipro | ✅ Active |
| DentalBookingApp | https://dental-booking-app-iota.vercel.app | StarDrop9/DentalBookingApp | ✅ Active |
| GlobalMonitor | https://aworldmonitor.vercel.app | StarDrop9/GlobalMonitor | ⛔ Removed — 3D WebGL app, inherently <90 perf |
| HealthWellnes | https://health-wellness-theta.vercel.app | StarDrop9/HealthWellness | ✅ Active |
| kpssite | https://kpsdev.org | StarDrop9/kpssite | ✅ Active |
| HITL-v2 | https://hitl-v2.vercel.app | StarDrop9/hitl-v2 | ✅ Active |
| VideoAnalyst | https://videoanalyst-nine.vercel.app | StarDrop9/VideoAnalyzer | ✅ Active |
| WisdomAlign | https://wisdom-align.vercel.app | StarDrop9/WisdomAlign | ✅ Active |

## Pending / Not Yet Deployed
| App | Notes |
|---|---|
| IgniteScotus | Not deployed yet |
| WisdomAlign | VPS deploy pending |
| IgniteVideoCast | Local only |
| AppDesignerWithPredTest | VPS deploy pending |

---

## Last Known Scores (2026-04-07 17:32 UTC)

| App | Date/Time | Performance | Accessibility | Best Practices | SEO |
|---|---|---|---|---|---|
| Taskmaster | 2026-04-07 17:32 UTC | 96 | 95 | 100 | 96 |
| ASIPro | 2026-04-07 17:32 UTC | 74 ❌ | 100 | 78 ❌ | 100 |
| DentalBookingApp | 2026-04-07 17:32 UTC | 94 ❌ | 91 ❌ | 96 | 100 |
| GlobalMonitor | 2026-04-07 17:32 UTC | 25 ❌ | 95 | 96 | 90 ❌ |
| HealthWellnes | 2026-04-07 17:32 UTC | 96 | 93 ❌ | 96 | 100 |
| kpssite | 2026-04-07 17:32 UTC | 80 ❌ | 100 | 100 | 100 |
| HITL-v2 | 2026-04-07 17:32 UTC | 99 | 96 | 100 | 100 |
| VideoAnalyst | 2026-04-07 17:32 UTC | 98 | 94 ❌ | 100 | 100 |
| WisdomAlign | 2026-04-07 17:32 UTC | 89 ❌ | 100 | 100 | 100 |

---

## Notes
- Scores updated daily by GitHub Actions → StarDrop9/cron-jobs
- Tasks created in Taskmaster with priority 60 (score 80-94) or 80 (score <80)
- Dedup: same failing task won't be created twice while still open
