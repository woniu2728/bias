# Production Smoke Capacity Report

Date: 2026-07-01

Environment: `deploy/docker-compose.production-smoke.yml` on `http://127.0.0.1:8000`.

Scope: short smoke-capacity run after rebuilding the production-smoke image. This is not the final 300-second benchmark.

| Artifact | OK | Count | Error Rate / Broadcast P95 ms | Max Target P95 / Connect P95 ms | Failed / Expected |
| --- | --- | ---: | ---: | ---: | ---: |
| health-strict.json | ok |  |  |  |  |
| load-http-forum-main-auth.json | False | 8 | 0.5 | 651.312 | 4 |
| load-http-forum-main.json | False | 10 | 0.2 | 734.213 | 4 |
| load-http-forum-upload.json | False | 1 | 1.0 | 541.226 | 1 |
| load-http-forum-write-mixed.json | False | 7 | 1.0 | 554.814 | 7 |
| load-http-forum-write-moderation.json | False | 1 | 1.0 | 23.894 | 9 |
| load-http-forum-write.json | False | 1 | 1.0 | 544.481 | 1 |
| load-websocket-external-broadcast.json | True | 2 | 0.822 | 11.505 | 2 |
| load-websocket-external-subscribe.json | True | 2 | 0.000 | 53.889 | 2 |
| seed-load-test-data.json | True | 270 |  |  |  |
| smoke-http-p95.json | True |  |  |  |  |
| smoke-queue-worker.json | True |  |  |  |  |

Findings:

- Strict health, seed data, HTTP smoke, queue worker smoke, and external WebSocket subscribe/broadcast passed.
- External WebSocket broadcast passed after fixing WebSocket route extender merge semantics; broadcast P95 is recorded in `load-websocket-external-broadcast.json`.
- Anonymous read profile still includes `/api/notifications`, which returns 401 in production smoke and should be moved out of `forum-main` or marked auth-required.
- Auth/write/upload profiles used a placeholder token and no CSRF session cookie, so they correctly failed with 401/403. Next work should add a load-test login/session bootstrap or token fixture for production smoke.
- Several read target P95 values are above current strict thresholds in this short cold run; rerun after warmup and with the final 300-second benchmark before making capacity claims.

Artifacts are stored next to this summary as JSON files.
