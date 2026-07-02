# Capacity Report: 20260702-020409

Status: passed, release evidence for P1 authenticated read/write/upload/moderation gate.

Environment:

- Production smoke compose: `deploy/docker-compose.production-smoke.yml`
- Executed inside the `web` container.
- `web` and `worker` were rebuilt from the same current workspace image before the final write-mixed and moderation runs.
- Load actors were prepared with `prepare_load_test_actors`.
- `DB_CONN_MAX_AGE=0` remained in effect.
- Seed scale inherited from the P0 production smoke dataset: users 1000, discussions 10000, posts 100000, tags 200, notifications 50000.
- Strict health before final runs: ok.

Profiles:

| Profile | Duration | Concurrency | Requests | Errors | Error rate | Requests/sec | Failed thresholds | Result |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `forum-main-auth` | 300.050s | 20 | 33256 | 0 | 0.0 | 110.835 | 0 | passed |
| `forum-write` | 120.216s | 5 | 2036 | 0 | 0.0 | 16.936 | 0 | passed |
| `forum-write-mixed` | 120.052s | 5 | 8085 | 0 | 0.0 | 67.346 | 0 | passed |
| `forum-upload` | 120.030s | 5 | 4265 | 0 | 0.0 | 35.533 | 0 | passed |
| `forum-write-moderation` | 60.046s | 2 | 2782 | 0 | 0.0 | 46.331 | 0 | passed |

Targets:

| Profile | Endpoint | Requests | Errors | P50 | P95 | P99 | Threshold | Result |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `forum-main-auth` | `GET /api/users/me` | 8312 | 0 | 155.790ms | 234.935ms | 274.700ms | 300ms | passed |
| `forum-main-auth` | `GET /api/discussions/?filter=my&limit=20` | 8316 | 0 | 192.118ms | 270.954ms | 298.573ms | 300ms | passed |
| `forum-main-auth` | `GET /api/discussions/?filter=unread&limit=20` | 8315 | 0 | 205.226ms | 284.129ms | 319.701ms | 300ms | passed |
| `forum-main-auth` | `GET /api/notifications` | 8313 | 0 | 159.580ms | 238.042ms | 273.028ms | 300ms | passed |
| `forum-write` | `POST /api/discussions/10842/posts` | 2036 | 0 | 296.689ms | 384.437ms | 420.345ms | 500ms | passed |
| `forum-write-mixed` | `POST /api/discussions/` | 1154 | 0 | 112.167ms | 138.962ms | 186.689ms | 500ms | passed |
| `forum-write-mixed` | `PATCH /api/discussions/11970` | 1155 | 0 | 88.393ms | 112.471ms | 150.343ms | 500ms | passed |
| `forum-write-mixed` | `POST /api/discussions/11970/read` | 1156 | 0 | 49.189ms | 66.192ms | 106.042ms | 300ms | passed |
| `forum-write-mixed` | `POST /api/posts/149824/like` | 1156 | 0 | 86.159ms | 134.853ms | 160.541ms | 500ms | passed |
| `forum-write-mixed` | `DELETE /api/posts/149825/like` | 1157 | 0 | 75.714ms | 107.723ms | 142.515ms | 500ms | passed |
| `forum-write-mixed` | `POST /api/discussions/11970/subscribe` | 1154 | 0 | 46.477ms | 64.173ms | 114.117ms | 300ms | passed |
| `forum-write-mixed` | `DELETE /api/discussions/11970/subscribe` | 1153 | 0 | 47.463ms | 67.624ms | 106.093ms | 300ms | passed |
| `forum-upload` | `POST /api/uploads` | 4265 | 0 | 138.402ms | 202.891ms | 233.450ms | 800ms | passed |
| `forum-write-moderation` | `PATCH /api/posts/156234` | 309 | 0 | 52.180ms | 55.822ms | 57.501ms | 500ms | passed |
| `forum-write-moderation` | `POST /api/posts/156235/report` | 310 | 0 | 46.448ms | 48.748ms | 50.352ms | 300ms | passed |
| `forum-write-moderation` | `POST /api/notifications/57913/read` | 310 | 0 | 20.262ms | 22.607ms | 23.892ms | 300ms | passed |
| `forum-write-moderation` | `POST /api/posts/156236/hide` | 310 | 0 | 76.754ms | 82.947ms | 88.865ms | 300ms | passed |
| `forum-write-moderation` | `POST /api/posts/156237/hide` | 310 | 0 | 65.560ms | 70.254ms | 79.473ms | 300ms | passed |
| `forum-write-moderation` | `POST /api/notifications/read-filtered?type=postReply&discussion_id=13125` | 309 | 0 | 19.250ms | 21.314ms | 23.179ms | 300ms | passed |
| `forum-write-moderation` | `DELETE /api/notifications/read/clear-filtered?type=postReply&discussion_id=13125` | 308 | 0 | 18.860ms | 20.755ms | 21.577ms | 300ms | passed |
| `forum-write-moderation` | `DELETE /api/notifications/read/clear` | 308 | 0 | 20.479ms | 22.434ms | 23.527ms | 300ms | passed |
| `forum-write-moderation` | `DELETE /api/posts/156238` | 308 | 0 | 66.198ms | 77.162ms | 83.068ms | 500ms | passed |

Evidence:

- Raw JSON: [forum-main-auth-300s.json](forum-main-auth-300s.json)
- Raw JSON: [forum-write-120s.json](forum-write-120s.json)
- Raw JSON: [forum-write-mixed-120s.json](forum-write-mixed-120s.json)
- Raw JSON: [forum-upload-120s.json](forum-upload-120s.json)
- Raw JSON: [forum-write-moderation-60s.json](forum-write-moderation-60s.json)

Conclusion:

The P1 authenticated read, write, upload, mixed write, and moderation capacity gate passed for the current production smoke seed scale. This report is release evidence for P1 only; WebSocket/realtime capacity, deployment/upgrade/rollback evidence, and target-environment operations gates remain separate follow-up gates.
