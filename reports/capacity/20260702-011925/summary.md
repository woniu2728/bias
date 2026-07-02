# Capacity Report: 20260702-011925

Status: passed, release evidence for P0 anonymous read gate.

Command:

```powershell
docker compose -f deploy/docker-compose.production-smoke.yml exec -T web python manage.py load_test_http --base-url http://127.0.0.1:8000 --profile forum-main --concurrency 20 --duration 300 --fail-on-threshold --format json
```

Environment:

- Production smoke compose: `deploy/docker-compose.production-smoke.yml`
- Executed inside the `web` container.
- Seed scale: users 1000, discussions 10000, posts 100000, tags 200, notifications 50000.
- Strict health before run: ok.

Summary:

| Metric | Value |
| --- | ---: |
| Duration | 300.354s |
| Concurrency | 20 |
| Requests | 27378 |
| Error count | 0 |
| Error rate | 0.0 |
| Requests/sec | 91.153 |
| Failed threshold count | 0 |
| Overall result | passed |

Targets:

| Endpoint | Requests | Errors | P50 | P95 | P99 | Threshold | Result |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `GET /api/forum` | 6844 | 0 | 130.935ms | 227.741ms | 263.995ms | 300ms | passed |
| `GET /api/discussions/?limit=20` | 6844 | 0 | 194.354ms | 286.790ms | 334.483ms | 300ms | passed |
| `GET /api/search?q=loadtest-discussion-00000001` | 6848 | 0 | 384.823ms | 477.282ms | 522.742ms | 800ms | passed |
| `GET /api/tags` | 6842 | 0 | 141.017ms | 218.777ms | 256.337ms | 300ms | passed |

Evidence:

- Raw JSON: [forum-main-300s.json](forum-main-300s.json)

Conclusion:

The P0 anonymous read path capacity gate passed for the current target seed scale. This report is release evidence for the anonymous read gate only; auth, write, upload, moderation, and realtime capacity suites remain separate P1/P2 gates.
