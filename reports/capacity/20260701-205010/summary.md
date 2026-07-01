# Production Smoke Capacity Report

Date: 2026-07-01

Environment: `deploy/docker-compose.production-smoke.yml` on `http://127.0.0.1:8000`.

Scope: short smoke-capacity run after rebuilding the production-smoke image. This validates command coverage, authenticated CSRF/JWT bootstrap, write-path correctness, Redis queue smoke, and production-like PostgreSQL behavior. This is not the final 300-second benchmark.

| Artifact | OK | Count | Error Rate | Max Target P95 ms | Failed |
| --- | --- | ---: | ---: | ---: | ---: |
| health-strict.json | True |  |  |  |  |
| load-http-forum-main-auth.json | True | 8 | 0.0000 | 128.33 | 0 |
| load-http-forum-main.json | True | 8 | 0.0000 | 113.04 | 0 |
| load-http-forum-upload.json | True | 1 | 0.0000 | 25.86 | 0 |
| load-http-forum-write-mixed.json | True | 7 | 0.0000 | 327.53 | 0 |
| load-http-forum-write-moderation.json | True | 9 | 0.0000 | 102.25 | 0 |
| load-http-forum-write.json | True | 1 | 0.0000 | 427.04 | 0 |
| seed-load-test-data-after-final-rebuild.json | True | 0 |  |  |  |
| seed-load-test-data-after-rebuild.json | True | 0 |  |  |  |
| seed-load-test-data.json | True | 350 |  |  |  |
| smoke-http-p95.json | True | 4 |  | 105.05 | 0 |
| smoke-queue-worker.json | True |  |  |  | 0 |

Findings:

- Strict health, deterministic seed, HTTP P95 smoke, Redis queue worker smoke, public read, authenticated read, reply write, mixed write, upload, and moderation write profiles all passed in the production-smoke compose environment.
- `load_test_http` now supports real `/api/csrf` + `/api/users/login` bootstrap via `--login-username/--login-password`; placeholder bearer tokens are no longer needed for auth/write/upload smoke evidence.
- `forum-main` now covers only anonymous public read paths; `/api/notifications` remains in `forum-main-auth`.
- Production PostgreSQL exposed a real `select_for_update` issue on nullable `user` joins in post moderation/delete paths; content runtime now locks only the Post row with `of=("self",)`.
- Write profiles use isolated targets where destructive or stateful actions would otherwise conflict, and cleanup evidence is included in profile JSON.
- This run is intentionally short. The remaining capacity gate is a final warm 300-second benchmark on target-sized data and concurrency.

Artifacts are stored next to this summary as JSON files.
