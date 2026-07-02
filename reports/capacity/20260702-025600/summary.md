# Capacity Report: 20260702-025600

Status: passed, release evidence for production-smoke WebSocket/realtime and P2 operations smoke gate.

Scope:

- Production smoke compose: `deploy/docker-compose.production-smoke.yml`
- Executed against the local production-smoke stack.
- `web` was rebuilt and recreated from the current workspace image before the final backup/restore dry-run and runtime integrations smoke evidence.
- `DB_CONN_MAX_AGE=0` remained in effect.
- This report does not replace target-environment public HTTPS/WebSocket, SMTP, object storage, multi-node, backup, upgrade, or destructive rollback exercise evidence.

WebSocket/realtime:

Command:

```powershell
docker compose -f deploy/docker-compose.production-smoke.yml exec -T web python manage.py load_test_websocket --base-url http://127.0.0.1:8000 --connections 20 --discussion-id 13124 --p95-threshold-ms 1000 --broadcast-p95-threshold-ms 1000 --fail-on-threshold --format json
```

| Metric | Value |
| --- | ---: |
| Connections | 20 / 20 |
| Connect P95 | 3.019ms |
| Subscribe P95 | 20.345ms |
| Broadcasts received | 20 / 20 |
| Broadcast P95 | 2.604ms |
| Threshold | 1000ms |
| Result | passed |

Operations smoke:

| Check | Result | Key evidence |
| --- | --- | --- |
| Strict health | passed | `status=ok`, `strict_failed=false` |
| HTTP P95 smoke | passed | 5 targets, 0 failed |
| Queue worker smoke | passed | 1 worker online, probe task ok |
| `install_forum` dry-run JSON | passed | `summary.ok=true`, 8 install steps, 0 errors, 0 warnings |
| `upgrade_forum` dry-run JSON | passed | `summary.ok=true`, 10 upgrade steps, `dry_run=true`, `executed=false`, 0 errors, 0 warnings |
| `backup_forum` JSON | passed | 4 backup artifacts created, 0 missing, 0 errors, 0 warnings |
| `verify_forum_backup` JSON | passed | 4 checks, 0 errors; site config parsed, PostgreSQL dump listed, directory backups scanned |
| `upgrade_forum` executed JSON | passed | `summary.ok=true`, 10 executed steps, `dry_run=false`, `executed=true`, 0 errors, 0 warnings |
| Post-upgrade strict health | passed | `status=ok`, `strict_failed=false` |
| Post-upgrade HTTP P95 smoke | passed | 5 targets, 0 failed |
| Post-upgrade queue worker smoke | passed | `summary.ok=true`, 0 errors |
| `plan_forum_rollback` JSON | passed | required backup artifacts present, 6 restore steps, 4 verification steps, `executes_restore=false` |
| `rehearse_forum_restore` JSON | passed | restored PostgreSQL dump into isolated temp database, verified 31 public tables, copied media/static backups into temp directories, dropped temp database; `executes_live_restore=false`, 0 errors, 1 PostgreSQL client/server compatibility warning |
| `restore_forum_backup` dry-run JSON | passed | planned 4 destructive live restore steps, `dry_run=true`, `executes_live_restore=false`, 0 errors, 0 warnings |
| `smoke_runtime_integrations` JSON | passed | local storage write/delete probe passed with no leftover probe file; email config dry-run passed; SMTP connection was not attempted |
| `plan_target_environment_evidence` JSON | passed as planning artifact | 25 target-environment evidence commands planned, 3 safe unattended, 3 safe manifest entries, 22 excluded-from-safe entries, 8 dependency-blocked commands, 5 command groups, 5 execution-sequence steps, 3 dependency execution waves, execution_queue_counts: 3 safe_unattended, 20 requires_substitution, 0 target_value_required, 8 dependency_blocked, 1 maintenance_approval, 1 destructive_approval, 1 final_validation; 20 substitution-required, 0 target-value-required, 2 manual approval, 1 final validation, 1 destructive, PowerShell and POSIX shell safe-only scripts exclude substitution-required/approval/final/dependency-blocked steps; POSIX shell redirects quote output/stderr paths; `executes_commands=false` |
| `inspect_target_topology` JSON | failed as expected for local production-smoke | local topology has 1 web, 1 worker, 1 scheduler; rejects local image/shared service/HTTP LB values; `require_multi_node=true`, `multi_node=false`, 5 errors |
| Target-environment evidence validation | failed as expected for local production-smoke | 21 checks, 16 failed, 16 remediation actions with planned command metadata, command-group summary: 1 safe_unattended, 17 requires_substitution, 1 destructive_approval, 1 final_validation; execution_queue_counts: 1 safe_unattended, 18 requires_substitution, 0 target_value_required, 7 dependency_blocked, 0 maintenance_approval, 1 destructive_approval, 1 final_validation; remediation dependency execution waves: 4 |

Evidence:

- Raw JSON: [load-websocket-external-20.json](load-websocket-external-20.json)
- Raw JSON: [health-strict.json](health-strict.json)
- Raw JSON: [smoke-http-p95.json](smoke-http-p95.json)
- Raw JSON: [smoke-queue-worker.json](smoke-queue-worker.json)
- Raw JSON: [install-forum-dry-run.json](install-forum-dry-run.json)
- Raw JSON: [upgrade-forum-dry-run.json](upgrade-forum-dry-run.json)
- Raw JSON: [upgrade-forum-executed.json](upgrade-forum-executed.json)
- Raw JSON: [post-upgrade-health-strict.json](post-upgrade-health-strict.json)
- Raw JSON: [post-upgrade-smoke-http-p95.json](post-upgrade-smoke-http-p95.json)
- Raw JSON: [post-upgrade-smoke-queue-worker.json](post-upgrade-smoke-queue-worker.json)
- Raw JSON: [plan-forum-rollback.json](plan-forum-rollback.json)
- Raw JSON: [backup-forum.json](backup-forum.json)
- Raw JSON: [verify-forum-backup.json](verify-forum-backup.json)
- Raw JSON: [plan-forum-rollback-with-backups.json](plan-forum-rollback-with-backups.json)
- Raw JSON: [rehearse-forum-restore.json](rehearse-forum-restore.json)
- Raw JSON: [restore-forum-backup-dry-run.json](restore-forum-backup-dry-run.json)
- Raw JSON: [smoke-runtime-integrations.json](smoke-runtime-integrations.json)
- Raw JSON: [target-environment-evidence-plan.json](target-environment-evidence-plan.json)
- Safe script: [target-environment-safe-archive.ps1](target-environment-safe-archive.ps1)
- Safe shell script: [target-environment-safe-archive.sh](target-environment-safe-archive.sh)
- Raw JSON: [multi-node-topology.json](multi-node-topology.json)
- Stderr: [multi-node-topology.stderr.txt](multi-node-topology.stderr.txt)
- Raw JSON: [target-environment-evidence-validation.json](target-environment-evidence-validation.json)
- Checklist: [target-environment-remediation-checklist.md](target-environment-remediation-checklist.md)
- Stderr: [target-environment-evidence-validation.stderr.txt](target-environment-evidence-validation.stderr.txt)

Conclusion:

The production-smoke WebSocket/realtime path and the P2 operations smoke checks passed for the current local production-like stack. Machine-readable backup creation, backup verification, upgrade execution, post-upgrade smoke, rollback planning, isolated restore rehearsal, protected live restore dry-run, local runtime integration smoke, and a target-environment evidence run plan are available. The restore rehearsal did not overwrite the live database, media, static assets, or site config; it restored the PostgreSQL dump into `bias_smoke_restore_smoke_20260702_p2_smoke`, verified the restored schema, copied directory backups into temp directories, and dropped the temp database afterward. The rehearsal recorded one tolerated PostgreSQL client/server compatibility warning for `transaction_timeout`. The live restore command was exercised only with `--dry-run`: it planned database, media, static frontend, and site config overwrite steps, but `executes_live_restore=false`. Runtime integration smoke verified local storage write/delete and email configuration dry-run; it did not connect to a real SMTP server or object storage provider. The backup path used here is inside the production-smoke container lifecycle; target environments must write backups to a durable location.

The target-environment evidence plan is a planning artifact only (`executes_commands=false`) and does not prove target readiness; it can be written directly with `--write-plan-file` so the report directory is created by the command instead of relying on shell redirection. It includes `archive_command`, `safe_to_run_unattended`, `safe_archive_ready`, `requires_completed_commands`, `requires_substitution`, `substitution_tokens`, `target_value_errors`, and `execution_group` fields, plus top-level `safe_archive_commands`, `safe_archive_manifest`, `excluded_from_safe_archive`, `command_groups`, `execution_sequence`, `execution_queues`, `dependency_execution_waves`, `substitution_required_commands`, `target_value_required_commands`, `dependency_blocked_commands`, `manual_approval_commands`, and `final_validation_commands` lists for deployment systems to consume. `summary.dependency_execution_wave_count=3` and the plan waves are: wave 1 `post_upgrade_strict_health`, `post_upgrade_http_smoke`, `post_upgrade_queue_worker`, `restore_rehearsal`, `p1_forum_write_mixed`; wave 2 `restore_dry_run`, `p1_forum_moderation`; wave 3 `live_restore`. `safe_to_run_unattended=true` means the command itself has no approval/substitution/target-value blocker; `safe_archive_ready=true` is stricter and is required for inclusion in the generated safe-only scripts. Commands with `requires_completed_commands` are dependency-blocked and remain excluded from the safe-only scripts until their prerequisite evidence is archived. `command_groups` summarizes commands by execution group before any evidence is run, including command keys, raw commands, output/stderr paths, archive commands, approval/destructive flags, substitution/target-value flags, and dependency-blocked state. `execution_sequence` records the recommended order from safe unattended work through substitution, maintenance approval, destructive approval, and final validation. `execution_queues` separately exposes safe unattended, substitution-required, target-value-required, dependency-blocked, maintenance approval, destructive approval, and final validation command queues with complete command/output/stderr/archive metadata; in the local template plan, live restore remains destructive and also appears in the substitution and dependency-blocked queues because `<durable-backup-uri>` is unresolved and restore prerequisites are not complete. Safe-only PowerShell and POSIX shell scripts were generated from `safe_archive_commands`; they create safe output directories before command redirection and intentionally exclude commands with `<...>` substitution tokens, target values that would fail target evidence gates, dependency-blocked commands, actual upgrade execution, live restore, and final validation. The excluded command manifest records why each command was not ready for safe archive execution. Actual upgrade execution is `maintenance_approval`; live restore is `destructive_approval`; final evidence validation is `final_validation`, automatically includes the same target run's `--plan-file` and same report directory's `--write-remediation-checklist`, and should run only after approval, substitution-required, target-value-required, and dependency-blocked commands have been archived. Real target-environment verification is intentionally skipped in this local development report and must be completed later in the target environment.

`inspect_target_topology --require-multi-node --format json` was run with the local production-smoke topology and failed as expected because it has only one web node, uses `local-production-smoke`, points database/Redis at container-local hosts, and records an HTTP load balancer. `validate_target_environment_evidence --report-dir reports/capacity/20260702-025600 --p0-report-dir reports/capacity/20260702-011925 --p1-report-dir reports/capacity/20260702-020409 --plan-file reports/capacity/20260702-025600/target-environment-evidence-plan.json --write-remediation-checklist reports/capacity/20260702-025600/target-environment-remediation-checklist.md --require-multi-node --format json` was then run against this local report and failed as expected: initial and post-upgrade HTTP smoke used `http://127.0.0.1:8000`, WebSocket used `ws://127.0.0.1:8000`, queue worker smoke used local/container-only `redis://redis:6379/...`, backups, rollback plan artifacts, restore rehearsal sources, and restore dry-run sources were under container-local `/app/backups/...` rather than a durable target-environment backup location, `restore-forum-backup-live.json` with site_config/database/media/static_frontend post-restore verification is intentionally absent, runtime integrations were not run with SMTP connect, object storage, or fail-on-warning, local topology is not multi-node and records local image/PostgreSQL/Redis/HTTP LB values, the P0/P1 capacity reports were local `http://127.0.0.1:8000` evidence rather than target-environment HTTPS evidence, and the template target evidence plan still contained substitution tokens. Plan consistency validation now also rejects stale or tampered dependency waves, mismatched `summary.dependency_execution_wave_count`, unknown dependency references, self-dependencies, and dependency cycles. The validation JSON includes a machine-readable `remediation` block with failed keys, missing files, and 16 target-environment actions for follow-up execution; when a `--plan-file` is supplied, each matching action also includes `planned_commands` with `command`, `output_file`, `stderr_file`, `archive_command`, `execution_group`, `safe_to_run_unattended`, `safe_archive_ready`, `requires_completed_commands`, `manual_approval_required`, `destructive`, and substitution/target-value status. `remediation.command_groups` summarizes those planned commands for execution routing in this local template run: 1 `safe_unattended`, 17 `requires_substitution`, 1 `destructive_approval`, and 1 `final_validation`; `remediation.execution_sequence` records the same groups in recommended execution order and keeps `final_validation` last. `remediation.execution_queues` also derives machine-readable queues for automation: 1 `safe_unattended`, 18 `requires_substitution`, 0 `target_value_required`, 7 `dependency_blocked`, 0 `maintenance_approval`, 1 `destructive_approval`, and 1 `final_validation`; live restore remains destructive and also appears in the substitution and dependency-blocked queues because the template still contains `<durable-backup-uri>` and restore prerequisites are not complete. `remediation.dependency_execution_waves` contains 4 waves for the still-failing local evidence run: wave 1 `post_upgrade_http_smoke`, `post_upgrade_queue_worker`; wave 2 `restore_rehearsal`, `p1_forum_write_mixed`; wave 3 `restore_dry_run`, `p1_forum_moderation`; wave 4 `live_restore`. The Markdown remediation checklist renders the same follow-up queue and dependency execution waves for humans; it does not execute any command, includes guardrails, records the execution sequence, execution queues, and each group `execution_policy`, and surfaces per-command command/output/stderr paths, substitution tokens, target value errors, and required completed commands so template commands are not copied directly into target execution. This is release evidence for the production-smoke realtime and operations smoke gate only. Full P2 remains incomplete until destructive rollback/restore with post-restore verification, multi-node topology, target HTTPS capacity, durable backup storage, final plan consistency, and target-environment production integrations are exercised against the intended target environment.
