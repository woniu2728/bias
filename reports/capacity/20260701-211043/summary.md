# Formal Capacity Run 20260701-211043

Status: failed, not release evidence.

Seed target was confirmed at users 1000, discussions 10000, posts 100000, tags 200, notifications 50000.

Artifacts:

- `health-strict.json`: strict health before formal run.
- `seed-load-test-data.json`: initial target-scale seed.
- `seed-load-test-data-after-db-conn-fix.json`: idempotent seed confirmation after rebuild.
- `load-http-forum-main-300s.json`: first 300s run, failed with PostgreSQL connection exhaustion.
- `load-http-forum-main-300s-after-db-conn-fix.json`: second 300s run, connection residue reduced but hot search still failed.
- `load-http-forum-main-300s-after-search-fix.json`: third 300s run, no HTTP errors but P95 thresholds still failed.

Latest `forum-main` result:

| Target | P95 ms | Threshold ms | Error rate | Result |
| --- | ---: | ---: | ---: | --- |
| GET /api/forum | 882.276 | 300 | 0.0% | failed |
| GET /api/discussions/?limit=20 | 1201.599 | 300 | 0.0% | failed |
| GET /api/search?q=loadtest-discussion-00000001 | 1123.727 | 800 | 0.0% | failed |
| GET /api/tags | 1207.394 | 300 | 0.0% | failed |

Findings:

- `DB_CONN_MAX_AGE=0` and `DB_CONN_HEALTH_CHECKS=True` are active in the production smoke web container.
- PostgreSQL full-text indexes are healthy.
- The original `loadtest` search target was a hot-term stress case because it matches almost all seeded posts and discussions; `forum-main` now uses the selective seed term `loadtest-discussion-00000001`.
- Search query changes removed the 10s timeout/500/503 failure mode, but the anonymous read profile still misses P95 thresholds.
- After the latest run, PostgreSQL connection state returned to a low idle count and web logs showed no exception stack.

Next development gate:

Optimize anonymous read paths before running the rest of the formal suite:

- `/api/forum`
- `/api/discussions/?limit=20`
- `/api/tags`
- `/api/search?q=loadtest-discussion-00000001`

The next report must include query counts, SQL explain evidence, and a passing 300s `forum-main` run before continuing with auth/write/upload/moderation/WebSocket formal capacity evidence.
