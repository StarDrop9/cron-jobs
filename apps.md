# App Audit Registry

Tracked by daily Lighthouse audit (8am UTC). Threshold: 95 on all categories.
Tasks auto-created in Taskmaster when scores drop below threshold.

---

## Apps

| App | URL | Status |
|---|---|---|
| Taskmaster | https://todo-scribe-master.vercel.app | ✅ Active |
| ASIPro | https://asipro.vercel.app | ✅ Active |
| DentalBookingApp | https://dental-booking-app-iota.vercel.app | ✅ Active |
| GlobalMonitor | https://aworldmonitor.vercel.app | ✅ Active |
| HealthWellnes | https://health-wellness-theta.vercel.app | ✅ Active |
| kpssite | https://kpsdev.org | ✅ Active |
| HITL-v2 | https://hitl-v2.vercel.app | ✅ Active |
| VideoAnalyst | https://videoanalyst-nine.vercel.app | ✅ Active |
| WisdomAlign | https://wisdom-align.vercel.app | ✅ Active |

## Pending / Not Yet Deployed
| App | Notes |
|---|---|
| IgniteScotus | Not deployed yet |
| WisdomAlign | VPS deploy pending |
| IgniteVideoCast | Local only |
| AppDesignerWithPredTest | VPS deploy pending |

---

## Last Known Scores (2026-04-01 21:04 UTC)

| App | Performance | Accessibility | Best Practices | SEO |
|---|---|---|---|---|
| Taskmaster | 98 ✓ | 95 ✓ | 100 ✓ | 96 ✓ |
| ASIPro | 100 ✓ | 100 ✓ | 100 ✓ | 83 ❌ |
| DentalBookingApp | 95 ✓ | 91 ❌ | 96 ✓ | 100 ✓ |
| GlobalMonitor | 25 ❌ | 95 ✓ | 96 ✓ | 90 ❌ |
| HealthWellnes | 96 ✓ | 93 ❌ | 96 ✓ | 100 ✓ |
| kpssite | 87 ❌ | 100 ✓ | 100 ✓ | 100 ✓ |
| HITL-v2 | 98 ✓ | 90 ❌ | 100 ✓ | 100 ✓ |
| VideoAnalyst | 98 ✓ | 86 ❌ | 100 ✓ | 100 ✓ |
| WisdomAlign | 82 ❌ | 95 ✓ | 100 ✓ | 100 ✓ |

---

## Notes
- Scores updated daily by GitHub Actions → StarDrop9/cron-jobs
- Tasks created in Taskmaster with priority 60 (score 80-94) or 80 (score <80)
- Dedup: same failing task won't be created twice while still open
