# Target Environment Remediation Checklist

- report_dir: `D:\files\project\tmp\bias\reports\capacity\20260702-025600`
- p0_report_dir: `D:\files\project\tmp\bias\reports\capacity\20260702-011925`
- p1_report_dir: `D:\files\project\tmp\bias\reports\capacity\20260702-020409`
- plan_file: `D:\files\project\tmp\bias\reports\capacity\20260702-025600\target-environment-evidence-plan.json`
- ok: `false`
- failed_count: `16`
- missing_count: `1`

## Guardrails

- Do not treat this checklist as P2 approval; `summary.ok` must be true in the final validation JSON.
- Replace every `<...>` token and fix every target value error before running a command.
- Run `destructive_approval` commands only in an approved maintenance window with a current durable backup.
- Run `final_validation` only after all required evidence files have been archived.
- This checklist is rendered from remediation metadata only; it does not execute commands.

## Execution Sequence

### Step 1: safe_unattended

- policy: run safe unattended archive commands
- command_count: `1`
- safe_to_run_unattended: `true`
- safe_archive_ready: `true`
- manual_approval_required: `false`
- destructive: `false`
- requires_substitution: `false`
- target_value_required: `false`
- dependency_blocked: `false`
- action_keys: `runtime_integrations`
- command_keys: `runtime_integrations`

### Step 2: requires_substitution

- policy: replace substitution tokens before running
- command_count: `17`
- safe_to_run_unattended: `false`
- safe_archive_ready: `false`
- manual_approval_required: `false`
- destructive: `false`
- requires_substitution: `true`
- target_value_required: `false`
- dependency_blocked: `true`
- requires_completed_commands: `upgrade_executed, backup_verification, restore_rehearsal, p1_forum_write, p1_forum_write_mixed`
- action_keys: `https_http_smoke, external_websocket, queue_worker, backup, backup_verification, post_upgrade_http_smoke, post_upgrade_queue_worker, rollback_plan, restore_rehearsal, restore_dry_run, multi_node_topology, p0_capacity_suite, p1_capacity_suite`
- command_keys: `https_http_smoke, external_websocket, queue_worker, backup, backup_verification, post_upgrade_http_smoke, post_upgrade_queue_worker, rollback_plan, restore_rehearsal, restore_dry_run, multi_node_topology, p0_forum_main, p1_forum_main_auth, p1_forum_write, p1_forum_write_mixed, p1_forum_upload, p1_forum_moderation`

### Step 3: destructive_approval

- policy: run only after approval, durable backup, and rollback staffing are confirmed
- command_count: `1`
- safe_to_run_unattended: `false`
- safe_archive_ready: `false`
- manual_approval_required: `true`
- destructive: `true`
- requires_substitution: `true`
- target_value_required: `false`
- dependency_blocked: `true`
- requires_completed_commands: `backup_verification, restore_dry_run`
- action_keys: `live_restore`
- command_keys: `live_restore`

### Step 4: final_validation

- policy: run only after all evidence-producing commands have been archived
- command_count: `1`
- safe_to_run_unattended: `false`
- safe_archive_ready: `false`
- manual_approval_required: `false`
- destructive: `false`
- requires_substitution: `false`
- target_value_required: `false`
- dependency_blocked: `false`
- action_keys: `target_evidence_plan`
- command_keys: `validate_target_environment_evidence`

## Execution Queues

### safe_unattended

- policy: eligible for unattended archive execution after target values are reviewed
- command_count: `1`
- action_keys: `runtime_integrations`
- command_keys: `runtime_integrations`

### requires_substitution

- policy: replace substitution tokens before running
- command_count: `18`
- action_keys: `https_http_smoke, external_websocket, queue_worker, backup, backup_verification, post_upgrade_http_smoke, post_upgrade_queue_worker, rollback_plan, restore_rehearsal, restore_dry_run, live_restore, multi_node_topology, p0_capacity_suite, p1_capacity_suite`
- command_keys: `https_http_smoke, external_websocket, queue_worker, backup, backup_verification, post_upgrade_http_smoke, post_upgrade_queue_worker, rollback_plan, restore_rehearsal, restore_dry_run, live_restore, multi_node_topology, p0_forum_main, p1_forum_main_auth, p1_forum_write, p1_forum_write_mixed, p1_forum_upload, p1_forum_moderation`

### target_value_required

- policy: fix target value errors before running
- command_count: `0`

### dependency_blocked

- policy: run only after requires_completed_commands have been archived
- command_count: `7`
- action_keys: `post_upgrade_http_smoke, post_upgrade_queue_worker, restore_rehearsal, restore_dry_run, live_restore, p1_capacity_suite`
- command_keys: `post_upgrade_http_smoke, post_upgrade_queue_worker, restore_rehearsal, restore_dry_run, live_restore, p1_forum_write_mixed, p1_forum_moderation`

### maintenance_approval

- policy: run only in an approved maintenance window
- command_count: `0`

### destructive_approval

- policy: run only after destructive approval and durable backup confirmation
- command_count: `1`
- action_keys: `live_restore`
- command_keys: `live_restore`

### final_validation

- policy: run only after all evidence-producing commands have been archived
- command_count: `1`
- action_keys: `target_evidence_plan`
- command_keys: `validate_target_environment_evidence`

## Dependency Execution Waves

### Wave 1

- dependency_depth: `0`
- command_count: `2`
- command_keys: `post_upgrade_http_smoke, post_upgrade_queue_worker`
- requires_completed_commands: `upgrade_executed`

### Wave 2

- dependency_depth: `1`
- command_count: `2`
- command_keys: `restore_rehearsal, p1_forum_write_mixed`
- requires_completed_commands: `backup_verification, p1_forum_write`

### Wave 3

- dependency_depth: `2`
- command_count: `2`
- command_keys: `restore_dry_run, p1_forum_moderation`
- requires_completed_commands: `backup_verification, restore_rehearsal, p1_forum_write_mixed`

### Wave 4

- dependency_depth: `3`
- command_count: `1`
- command_keys: `live_restore`
- requires_completed_commands: `backup_verification, restore_dry_run`

## Command Groups

### destructive_approval

- command_count: `1`
- safe_to_run_unattended: `false`
- safe_archive_ready: `false`
- manual_approval_required: `true`
- destructive: `true`
- requires_substitution: `true`
- target_value_required: `false`
- dependency_blocked: `true`
- requires_completed_commands: `backup_verification, restore_dry_run`
- execution_policy: maintenance approval required; confirm durable backup and post-restore verification before running

- [ ] `python manage.py restore_forum_backup --config instance/site.json --backup-dir <durable-backup-uri> --i-understand-this-overwrites-live-data --confirm-phrase "restore live forum data" --format json > D:\files\project\tmp\bias\reports\capacity\20260702-025600\restore-forum-backup-live.json 2> D:\files\project\tmp\bias\reports\capacity\20260702-025600\restore-forum-backup-live.stderr.txt`

### final_validation

- command_count: `1`
- safe_to_run_unattended: `false`
- safe_archive_ready: `false`
- manual_approval_required: `false`
- destructive: `false`
- requires_substitution: `false`
- target_value_required: `false`
- dependency_blocked: `false`
- execution_policy: run only after all evidence-producing commands are archived

- [ ] `python manage.py validate_target_environment_evidence --report-dir D:\files\project\tmp\bias\reports\capacity\20260702-025600 --p0-report-dir D:\files\project\tmp\bias\reports\capacity\20260702-011925 --p1-report-dir D:\files\project\tmp\bias\reports\capacity\20260702-020409 --plan-file D:\files\project\tmp\bias\reports\capacity\20260702-025600\target-environment-evidence-plan.json --write-remediation-checklist D:\files\project\tmp\bias\reports\capacity\20260702-025600\target-environment-remediation-checklist.md --require-multi-node --format json > D:\files\project\tmp\bias\reports\capacity\20260702-025600\target-environment-evidence-validation.json 2> D:\files\project\tmp\bias\reports\capacity\20260702-025600\target-environment-evidence-validation.stderr.txt`

### requires_substitution

- command_count: `17`
- safe_to_run_unattended: `false`
- safe_archive_ready: `false`
- manual_approval_required: `false`
- destructive: `false`
- requires_substitution: `true`
- target_value_required: `false`
- dependency_blocked: `true`
- requires_completed_commands: `upgrade_executed, backup_verification, restore_rehearsal, p1_forum_write, p1_forum_write_mixed`
- execution_policy: replace substitution tokens with real target values before running

- [ ] `python manage.py smoke_http_p95 --base-url https://<your-domain> --fail-on-threshold --format json > D:\files\project\tmp\bias\reports\capacity\20260702-025600\smoke-http-p95.json 2> D:\files\project\tmp\bias\reports\capacity\20260702-025600\smoke-http-p95.stderr.txt`
- [ ] `python manage.py load_test_websocket --base-url https://<your-domain> --connections 20 --discussion-id <discussion-id> --p95-threshold-ms 1000 --broadcast-p95-threshold-ms 1000 --fail-on-threshold --format json > D:\files\project\tmp\bias\reports\capacity\20260702-025600\load-websocket-external-20.json 2> D:\files\project\tmp\bias\reports\capacity\20260702-025600\load-websocket-external-20.stderr.txt`
- [ ] `python manage.py smoke_queue_worker --broker-url <redis-broker-url> --result-backend <redis-result-backend> --timeout 45 --format json > D:\files\project\tmp\bias\reports\capacity\20260702-025600\smoke-queue-worker.json 2> D:\files\project\tmp\bias\reports\capacity\20260702-025600\smoke-queue-worker.stderr.txt`
- [ ] `python manage.py backup_forum --config instance/site.json --backup-dir <durable-backup-uri> --format json > D:\files\project\tmp\bias\reports\capacity\20260702-025600\backup-forum.json 2> D:\files\project\tmp\bias\reports\capacity\20260702-025600\backup-forum.stderr.txt`
- [ ] `python manage.py verify_forum_backup --config instance/site.json --backup-dir <durable-backup-uri> --format json > D:\files\project\tmp\bias\reports\capacity\20260702-025600\verify-forum-backup.json 2> D:\files\project\tmp\bias\reports\capacity\20260702-025600\verify-forum-backup.stderr.txt`
- [ ] `python manage.py smoke_http_p95 --base-url https://<your-domain> --fail-on-threshold --format json > D:\files\project\tmp\bias\reports\capacity\20260702-025600\post-upgrade-smoke-http-p95.json 2> D:\files\project\tmp\bias\reports\capacity\20260702-025600\post-upgrade-smoke-http-p95.stderr.txt`
- [ ] `python manage.py smoke_queue_worker --broker-url <redis-broker-url> --result-backend <redis-result-backend> --timeout 45 --format json > D:\files\project\tmp\bias\reports\capacity\20260702-025600\post-upgrade-smoke-queue-worker.json 2> D:\files\project\tmp\bias\reports\capacity\20260702-025600\post-upgrade-smoke-queue-worker.stderr.txt`
- [ ] `python manage.py plan_forum_rollback --config instance/site.json --backup-dir <durable-backup-uri> --require-existing-backups --format json > D:\files\project\tmp\bias\reports\capacity\20260702-025600\plan-forum-rollback-with-backups.json 2> D:\files\project\tmp\bias\reports\capacity\20260702-025600\plan-forum-rollback-with-backups.stderr.txt`
- [ ] `python manage.py rehearse_forum_restore --config instance/site.json --backup-dir <durable-backup-uri> --format json > D:\files\project\tmp\bias\reports\capacity\20260702-025600\rehearse-forum-restore.json 2> D:\files\project\tmp\bias\reports\capacity\20260702-025600\rehearse-forum-restore.stderr.txt`
- [ ] `python manage.py restore_forum_backup --config instance/site.json --backup-dir <durable-backup-uri> --dry-run --format json > D:\files\project\tmp\bias\reports\capacity\20260702-025600\restore-forum-backup-dry-run.json 2> D:\files\project\tmp\bias\reports\capacity\20260702-025600\restore-forum-backup-dry-run.stderr.txt`
- [ ] `python manage.py inspect_target_topology --web-nodes <web-count> --worker-nodes <worker-count> --scheduler-nodes <scheduler-count> --image <image-or-release> --app-version <version> --database <db-endpoint> --redis <redis-endpoint> --load-balancer https://<your-domain> --require-multi-node --format json > D:\files\project\tmp\bias\reports\capacity\20260702-025600\multi-node-topology.json 2> D:\files\project\tmp\bias\reports\capacity\20260702-025600\multi-node-topology.stderr.txt`
- [ ] `python manage.py load_test_http --base-url https://<your-domain> --profile forum-main --concurrency 20 --duration 300 --fail-on-threshold --format json > D:\files\project\tmp\bias\reports\capacity\20260702-011925\forum-main-300s.json 2> D:\files\project\tmp\bias\reports\capacity\20260702-011925\forum-main-300s.stderr.txt`
- [ ] `python manage.py load_test_http --base-url https://<your-domain> --profile forum-main-auth --login-username <load-user> --login-password <load-password> --concurrency 20 --duration 300 --fail-on-threshold --format json > D:\files\project\tmp\bias\reports\capacity\20260702-020409\forum-main-auth-300s.json 2> D:\files\project\tmp\bias\reports\capacity\20260702-020409\forum-main-auth-300s.stderr.txt`
- [ ] `python manage.py load_test_http --base-url https://<your-domain> --profile forum-write --login-username <load-user> --login-password <load-password> --discussion-id <discussion-id> --concurrency 5 --duration 120 --fail-on-threshold --format json > D:\files\project\tmp\bias\reports\capacity\20260702-020409\forum-write-120s.json 2> D:\files\project\tmp\bias\reports\capacity\20260702-020409\forum-write-120s.stderr.txt`
- [ ] `python manage.py load_test_http --base-url https://<your-domain> --profile forum-write-mixed --login-username <load-user> --login-password <load-password> --prepare-isolated-targets --cleanup-isolated-targets --concurrency 5 --duration 120 --fail-on-threshold --format json > D:\files\project\tmp\bias\reports\capacity\20260702-020409\forum-write-mixed-120s.json 2> D:\files\project\tmp\bias\reports\capacity\20260702-020409\forum-write-mixed-120s.stderr.txt`
- [ ] `python manage.py load_test_http --base-url https://<your-domain> --profile forum-upload --login-username <load-user> --login-password <load-password> --concurrency 5 --duration 120 --fail-on-threshold --format json > D:\files\project\tmp\bias\reports\capacity\20260702-020409\forum-upload-120s.json 2> D:\files\project\tmp\bias\reports\capacity\20260702-020409\forum-upload-120s.stderr.txt`
- [ ] `python manage.py load_test_http --base-url https://<your-domain> --profile forum-write-moderation --login-username <moderator-user> --login-password <moderator-password> --prepare-isolated-targets --cleanup-isolated-targets --concurrency 2 --duration 60 --fail-on-threshold --format json > D:\files\project\tmp\bias\reports\capacity\20260702-020409\forum-write-moderation-60s.json 2> D:\files\project\tmp\bias\reports\capacity\20260702-020409\forum-write-moderation-60s.stderr.txt`

### safe_unattended

- command_count: `1`
- safe_to_run_unattended: `true`
- safe_archive_ready: `true`
- manual_approval_required: `false`
- destructive: `false`
- requires_substitution: `false`
- target_value_required: `false`
- dependency_blocked: `false`
- execution_policy: eligible for unattended execution after reviewing target values

- [ ] `python manage.py smoke_runtime_integrations --smtp-connect --storage-write --require-smtp-connect --require-storage-write --require-object-storage --fail-on-warning --format json > D:\files\project\tmp\bias\reports\capacity\20260702-025600\smoke-runtime-integrations.json 2> D:\files\project\tmp\bias\reports\capacity\20260702-025600\smoke-runtime-integrations.stderr.txt`

## Actions

### target_evidence_plan

- file: `target-environment-evidence-plan.json`
- missing: `false`
- error_count: `1`
- hint: Regenerate the target run plan with real target values and --write-plan-file, then validate that exact plan file.

Planned commands:

- [ ] `validate_target_environment_evidence` (final_validation, safe=false, archive_ready=false, manual=false, destructive=false)
  - command: `python manage.py validate_target_environment_evidence --report-dir D:\files\project\tmp\bias\reports\capacity\20260702-025600 --p0-report-dir D:\files\project\tmp\bias\reports\capacity\20260702-011925 --p1-report-dir D:\files\project\tmp\bias\reports\capacity\20260702-020409 --plan-file D:\files\project\tmp\bias\reports\capacity\20260702-025600\target-environment-evidence-plan.json --write-remediation-checklist D:\files\project\tmp\bias\reports\capacity\20260702-025600\target-environment-remediation-checklist.md --require-multi-node --format json`
  - output_file: `D:\files\project\tmp\bias\reports\capacity\20260702-025600\target-environment-evidence-validation.json`
  - stderr_file: `D:\files\project\tmp\bias\reports\capacity\20260702-025600\target-environment-evidence-validation.stderr.txt`
  - archive: `python manage.py validate_target_environment_evidence --report-dir D:\files\project\tmp\bias\reports\capacity\20260702-025600 --p0-report-dir D:\files\project\tmp\bias\reports\capacity\20260702-011925 --p1-report-dir D:\files\project\tmp\bias\reports\capacity\20260702-020409 --plan-file D:\files\project\tmp\bias\reports\capacity\20260702-025600\target-environment-evidence-plan.json --write-remediation-checklist D:\files\project\tmp\bias\reports\capacity\20260702-025600\target-environment-remediation-checklist.md --require-multi-node --format json > D:\files\project\tmp\bias\reports\capacity\20260702-025600\target-environment-evidence-validation.json 2> D:\files\project\tmp\bias\reports\capacity\20260702-025600\target-environment-evidence-validation.stderr.txt`

### https_http_smoke

- file: `smoke-http-p95.json`
- missing: `false`
- error_count: `1`
- hint: Run target HTTPS HTTP P95 smoke and archive smoke-http-p95.json.

Planned commands:

- [ ] `https_http_smoke` (requires_substitution, safe=false, archive_ready=false, manual=false, destructive=false)
  - substitution_tokens: `<your-domain>`
  - command: `python manage.py smoke_http_p95 --base-url https://<your-domain> --fail-on-threshold --format json`
  - output_file: `D:\files\project\tmp\bias\reports\capacity\20260702-025600\smoke-http-p95.json`
  - stderr_file: `D:\files\project\tmp\bias\reports\capacity\20260702-025600\smoke-http-p95.stderr.txt`
  - archive: `python manage.py smoke_http_p95 --base-url https://<your-domain> --fail-on-threshold --format json > D:\files\project\tmp\bias\reports\capacity\20260702-025600\smoke-http-p95.json 2> D:\files\project\tmp\bias\reports\capacity\20260702-025600\smoke-http-p95.stderr.txt`

### external_websocket

- file: `load-websocket-external-20.json`
- missing: `false`
- error_count: `1`
- hint: Run external WSS WebSocket load smoke with a real discussion id.

Planned commands:

- [ ] `external_websocket` (requires_substitution, safe=false, archive_ready=false, manual=false, destructive=false)
  - substitution_tokens: `<discussion-id>, <your-domain>`
  - command: `python manage.py load_test_websocket --base-url https://<your-domain> --connections 20 --discussion-id <discussion-id> --p95-threshold-ms 1000 --broadcast-p95-threshold-ms 1000 --fail-on-threshold --format json`
  - output_file: `D:\files\project\tmp\bias\reports\capacity\20260702-025600\load-websocket-external-20.json`
  - stderr_file: `D:\files\project\tmp\bias\reports\capacity\20260702-025600\load-websocket-external-20.stderr.txt`
  - archive: `python manage.py load_test_websocket --base-url https://<your-domain> --connections 20 --discussion-id <discussion-id> --p95-threshold-ms 1000 --broadcast-p95-threshold-ms 1000 --fail-on-threshold --format json > D:\files\project\tmp\bias\reports\capacity\20260702-025600\load-websocket-external-20.json 2> D:\files\project\tmp\bias\reports\capacity\20260702-025600\load-websocket-external-20.stderr.txt`

### queue_worker

- file: `smoke-queue-worker.json`
- missing: `false`
- error_count: `2`
- hint: Run queue worker smoke against shared target Redis broker/result backend.

Planned commands:

- [ ] `queue_worker` (requires_substitution, safe=false, archive_ready=false, manual=false, destructive=false)
  - substitution_tokens: `<redis-broker-url>, <redis-result-backend>`
  - command: `python manage.py smoke_queue_worker --broker-url <redis-broker-url> --result-backend <redis-result-backend> --timeout 45 --format json`
  - output_file: `D:\files\project\tmp\bias\reports\capacity\20260702-025600\smoke-queue-worker.json`
  - stderr_file: `D:\files\project\tmp\bias\reports\capacity\20260702-025600\smoke-queue-worker.stderr.txt`
  - archive: `python manage.py smoke_queue_worker --broker-url <redis-broker-url> --result-backend <redis-result-backend> --timeout 45 --format json > D:\files\project\tmp\bias\reports\capacity\20260702-025600\smoke-queue-worker.json 2> D:\files\project\tmp\bias\reports\capacity\20260702-025600\smoke-queue-worker.stderr.txt`

### backup

- file: `backup-forum.json`
- missing: `false`
- error_count: `5`
- hint: Create a target backup in durable storage and archive backup-forum.json.

Planned commands:

- [ ] `backup` (requires_substitution, safe=false, archive_ready=false, manual=false, destructive=false)
  - substitution_tokens: `<durable-backup-uri>`
  - command: `python manage.py backup_forum --config instance/site.json --backup-dir <durable-backup-uri> --format json`
  - output_file: `D:\files\project\tmp\bias\reports\capacity\20260702-025600\backup-forum.json`
  - stderr_file: `D:\files\project\tmp\bias\reports\capacity\20260702-025600\backup-forum.stderr.txt`
  - archive: `python manage.py backup_forum --config instance/site.json --backup-dir <durable-backup-uri> --format json > D:\files\project\tmp\bias\reports\capacity\20260702-025600\backup-forum.json 2> D:\files\project\tmp\bias\reports\capacity\20260702-025600\backup-forum.stderr.txt`

### backup_verification

- file: `verify-forum-backup.json`
- missing: `false`
- error_count: `5`
- hint: Verify the durable target backup and archive verify-forum-backup.json.

Planned commands:

- [ ] `backup_verification` (requires_substitution, safe=false, archive_ready=false, manual=false, destructive=false)
  - substitution_tokens: `<durable-backup-uri>`
  - command: `python manage.py verify_forum_backup --config instance/site.json --backup-dir <durable-backup-uri> --format json`
  - output_file: `D:\files\project\tmp\bias\reports\capacity\20260702-025600\verify-forum-backup.json`
  - stderr_file: `D:\files\project\tmp\bias\reports\capacity\20260702-025600\verify-forum-backup.stderr.txt`
  - archive: `python manage.py verify_forum_backup --config instance/site.json --backup-dir <durable-backup-uri> --format json > D:\files\project\tmp\bias\reports\capacity\20260702-025600\verify-forum-backup.json 2> D:\files\project\tmp\bias\reports\capacity\20260702-025600\verify-forum-backup.stderr.txt`

### post_upgrade_http_smoke

- file: `post-upgrade-smoke-http-p95.json`
- missing: `false`
- error_count: `1`
- hint: Run target HTTPS HTTP P95 smoke after upgrade.

Planned commands:

- [ ] `post_upgrade_http_smoke` (requires_substitution, safe=false, archive_ready=false, manual=false, destructive=false)
  - substitution_tokens: `<your-domain>`
  - requires_completed_commands: `upgrade_executed`
  - command: `python manage.py smoke_http_p95 --base-url https://<your-domain> --fail-on-threshold --format json`
  - output_file: `D:\files\project\tmp\bias\reports\capacity\20260702-025600\post-upgrade-smoke-http-p95.json`
  - stderr_file: `D:\files\project\tmp\bias\reports\capacity\20260702-025600\post-upgrade-smoke-http-p95.stderr.txt`
  - archive: `python manage.py smoke_http_p95 --base-url https://<your-domain> --fail-on-threshold --format json > D:\files\project\tmp\bias\reports\capacity\20260702-025600\post-upgrade-smoke-http-p95.json 2> D:\files\project\tmp\bias\reports\capacity\20260702-025600\post-upgrade-smoke-http-p95.stderr.txt`

### post_upgrade_queue_worker

- file: `post-upgrade-smoke-queue-worker.json`
- missing: `false`
- error_count: `2`
- hint: Run target queue worker smoke after upgrade.

Planned commands:

- [ ] `post_upgrade_queue_worker` (requires_substitution, safe=false, archive_ready=false, manual=false, destructive=false)
  - substitution_tokens: `<redis-broker-url>, <redis-result-backend>`
  - requires_completed_commands: `upgrade_executed`
  - command: `python manage.py smoke_queue_worker --broker-url <redis-broker-url> --result-backend <redis-result-backend> --timeout 45 --format json`
  - output_file: `D:\files\project\tmp\bias\reports\capacity\20260702-025600\post-upgrade-smoke-queue-worker.json`
  - stderr_file: `D:\files\project\tmp\bias\reports\capacity\20260702-025600\post-upgrade-smoke-queue-worker.stderr.txt`
  - archive: `python manage.py smoke_queue_worker --broker-url <redis-broker-url> --result-backend <redis-result-backend> --timeout 45 --format json > D:\files\project\tmp\bias\reports\capacity\20260702-025600\post-upgrade-smoke-queue-worker.json 2> D:\files\project\tmp\bias\reports\capacity\20260702-025600\post-upgrade-smoke-queue-worker.stderr.txt`

### rollback_plan

- file: `plan-forum-rollback-with-backups.json`
- missing: `false`
- error_count: `5`
- hint: Generate rollback plan using durable target backups.

Planned commands:

- [ ] `rollback_plan` (requires_substitution, safe=false, archive_ready=false, manual=false, destructive=false)
  - substitution_tokens: `<durable-backup-uri>`
  - command: `python manage.py plan_forum_rollback --config instance/site.json --backup-dir <durable-backup-uri> --require-existing-backups --format json`
  - output_file: `D:\files\project\tmp\bias\reports\capacity\20260702-025600\plan-forum-rollback-with-backups.json`
  - stderr_file: `D:\files\project\tmp\bias\reports\capacity\20260702-025600\plan-forum-rollback-with-backups.stderr.txt`
  - archive: `python manage.py plan_forum_rollback --config instance/site.json --backup-dir <durable-backup-uri> --require-existing-backups --format json > D:\files\project\tmp\bias\reports\capacity\20260702-025600\plan-forum-rollback-with-backups.json 2> D:\files\project\tmp\bias\reports\capacity\20260702-025600\plan-forum-rollback-with-backups.stderr.txt`

### restore_rehearsal

- file: `rehearse-forum-restore.json`
- missing: `false`
- error_count: `8`
- hint: Run isolated restore rehearsal from durable target backups.

Planned commands:

- [ ] `restore_rehearsal` (requires_substitution, safe=false, archive_ready=false, manual=false, destructive=false)
  - substitution_tokens: `<durable-backup-uri>`
  - requires_completed_commands: `backup_verification`
  - command: `python manage.py rehearse_forum_restore --config instance/site.json --backup-dir <durable-backup-uri> --format json`
  - output_file: `D:\files\project\tmp\bias\reports\capacity\20260702-025600\rehearse-forum-restore.json`
  - stderr_file: `D:\files\project\tmp\bias\reports\capacity\20260702-025600\rehearse-forum-restore.stderr.txt`
  - archive: `python manage.py rehearse_forum_restore --config instance/site.json --backup-dir <durable-backup-uri> --format json > D:\files\project\tmp\bias\reports\capacity\20260702-025600\rehearse-forum-restore.json 2> D:\files\project\tmp\bias\reports\capacity\20260702-025600\rehearse-forum-restore.stderr.txt`

### restore_dry_run

- file: `restore-forum-backup-dry-run.json`
- missing: `false`
- error_count: `9`
- hint: Run protected live restore dry-run from durable target backups.

Planned commands:

- [ ] `restore_dry_run` (requires_substitution, safe=false, archive_ready=false, manual=false, destructive=false)
  - substitution_tokens: `<durable-backup-uri>`
  - requires_completed_commands: `backup_verification, restore_rehearsal`
  - command: `python manage.py restore_forum_backup --config instance/site.json --backup-dir <durable-backup-uri> --dry-run --format json`
  - output_file: `D:\files\project\tmp\bias\reports\capacity\20260702-025600\restore-forum-backup-dry-run.json`
  - stderr_file: `D:\files\project\tmp\bias\reports\capacity\20260702-025600\restore-forum-backup-dry-run.stderr.txt`
  - archive: `python manage.py restore_forum_backup --config instance/site.json --backup-dir <durable-backup-uri> --dry-run --format json > D:\files\project\tmp\bias\reports\capacity\20260702-025600\restore-forum-backup-dry-run.json 2> D:\files\project\tmp\bias\reports\capacity\20260702-025600\restore-forum-backup-dry-run.stderr.txt`

### live_restore

- file: `restore-forum-backup-live.json`
- missing: `true`
- error_count: `1`
- hint: Archive approved destructive live restore with post-restore verification.

Planned commands:

- [ ] `live_restore` (destructive_approval, safe=false, archive_ready=false, manual=true, destructive=true)
  - substitution_tokens: `<durable-backup-uri>`
  - requires_completed_commands: `backup_verification, restore_dry_run`
  - command: `python manage.py restore_forum_backup --config instance/site.json --backup-dir <durable-backup-uri> --i-understand-this-overwrites-live-data --confirm-phrase "restore live forum data" --format json`
  - output_file: `D:\files\project\tmp\bias\reports\capacity\20260702-025600\restore-forum-backup-live.json`
  - stderr_file: `D:\files\project\tmp\bias\reports\capacity\20260702-025600\restore-forum-backup-live.stderr.txt`
  - archive: `python manage.py restore_forum_backup --config instance/site.json --backup-dir <durable-backup-uri> --i-understand-this-overwrites-live-data --confirm-phrase "restore live forum data" --format json > D:\files\project\tmp\bias\reports\capacity\20260702-025600\restore-forum-backup-live.json 2> D:\files\project\tmp\bias\reports\capacity\20260702-025600\restore-forum-backup-live.stderr.txt`

### runtime_integrations

- file: `smoke-runtime-integrations.json`
- missing: `false`
- error_count: `7`
- hint: Run runtime integrations with SMTP connect, object storage write/delete, and fail-on-warning.

Planned commands:

- [ ] `runtime_integrations` (safe_unattended, safe=true, archive_ready=true, manual=false, destructive=false)
  - command: `python manage.py smoke_runtime_integrations --smtp-connect --storage-write --require-smtp-connect --require-storage-write --require-object-storage --fail-on-warning --format json`
  - output_file: `D:\files\project\tmp\bias\reports\capacity\20260702-025600\smoke-runtime-integrations.json`
  - stderr_file: `D:\files\project\tmp\bias\reports\capacity\20260702-025600\smoke-runtime-integrations.stderr.txt`
  - archive: `python manage.py smoke_runtime_integrations --smtp-connect --storage-write --require-smtp-connect --require-storage-write --require-object-storage --fail-on-warning --format json > D:\files\project\tmp\bias\reports\capacity\20260702-025600\smoke-runtime-integrations.json 2> D:\files\project\tmp\bias\reports\capacity\20260702-025600\smoke-runtime-integrations.stderr.txt`

### multi_node_topology

- file: `multi-node-topology.json`
- missing: `false`
- error_count: `7`
- hint: Archive target multi-node topology with shared services and HTTPS load balancer.

Planned commands:

- [ ] `multi_node_topology` (requires_substitution, safe=false, archive_ready=false, manual=false, destructive=false)
  - substitution_tokens: `<db-endpoint>, <image-or-release>, <redis-endpoint>, <scheduler-count>, <version>, <web-count>, <worker-count>, <your-domain>`
  - command: `python manage.py inspect_target_topology --web-nodes <web-count> --worker-nodes <worker-count> --scheduler-nodes <scheduler-count> --image <image-or-release> --app-version <version> --database <db-endpoint> --redis <redis-endpoint> --load-balancer https://<your-domain> --require-multi-node --format json`
  - output_file: `D:\files\project\tmp\bias\reports\capacity\20260702-025600\multi-node-topology.json`
  - stderr_file: `D:\files\project\tmp\bias\reports\capacity\20260702-025600\multi-node-topology.stderr.txt`
  - archive: `python manage.py inspect_target_topology --web-nodes <web-count> --worker-nodes <worker-count> --scheduler-nodes <scheduler-count> --image <image-or-release> --app-version <version> --database <db-endpoint> --redis <redis-endpoint> --load-balancer https://<your-domain> --require-multi-node --format json > D:\files\project\tmp\bias\reports\capacity\20260702-025600\multi-node-topology.json 2> D:\files\project\tmp\bias\reports\capacity\20260702-025600\multi-node-topology.stderr.txt`

### p0_capacity_suite

- file: `forum-main-300s.json`
- missing: `false`
- error_count: `1`
- hint: Run target HTTPS P0 forum-main capacity suite.

Planned commands:

- [ ] `p0_forum_main` (requires_substitution, safe=false, archive_ready=false, manual=false, destructive=false)
  - substitution_tokens: `<your-domain>`
  - command: `python manage.py load_test_http --base-url https://<your-domain> --profile forum-main --concurrency 20 --duration 300 --fail-on-threshold --format json`
  - output_file: `D:\files\project\tmp\bias\reports\capacity\20260702-011925\forum-main-300s.json`
  - stderr_file: `D:\files\project\tmp\bias\reports\capacity\20260702-011925\forum-main-300s.stderr.txt`
  - archive: `python manage.py load_test_http --base-url https://<your-domain> --profile forum-main --concurrency 20 --duration 300 --fail-on-threshold --format json > D:\files\project\tmp\bias\reports\capacity\20260702-011925\forum-main-300s.json 2> D:\files\project\tmp\bias\reports\capacity\20260702-011925\forum-main-300s.stderr.txt`

### p1_capacity_suite

- file: `20260702-020409`
- missing: `false`
- error_count: `5`
- hint: Run all target HTTPS P1 auth/write/upload/moderation capacity suites.

Planned commands:

- [ ] `p1_forum_main_auth` (requires_substitution, safe=false, archive_ready=false, manual=false, destructive=false)
  - substitution_tokens: `<load-password>, <load-user>, <your-domain>`
  - command: `python manage.py load_test_http --base-url https://<your-domain> --profile forum-main-auth --login-username <load-user> --login-password <load-password> --concurrency 20 --duration 300 --fail-on-threshold --format json`
  - output_file: `D:\files\project\tmp\bias\reports\capacity\20260702-020409\forum-main-auth-300s.json`
  - stderr_file: `D:\files\project\tmp\bias\reports\capacity\20260702-020409\forum-main-auth-300s.stderr.txt`
  - archive: `python manage.py load_test_http --base-url https://<your-domain> --profile forum-main-auth --login-username <load-user> --login-password <load-password> --concurrency 20 --duration 300 --fail-on-threshold --format json > D:\files\project\tmp\bias\reports\capacity\20260702-020409\forum-main-auth-300s.json 2> D:\files\project\tmp\bias\reports\capacity\20260702-020409\forum-main-auth-300s.stderr.txt`
- [ ] `p1_forum_write` (requires_substitution, safe=false, archive_ready=false, manual=false, destructive=false)
  - substitution_tokens: `<discussion-id>, <load-password>, <load-user>, <your-domain>`
  - command: `python manage.py load_test_http --base-url https://<your-domain> --profile forum-write --login-username <load-user> --login-password <load-password> --discussion-id <discussion-id> --concurrency 5 --duration 120 --fail-on-threshold --format json`
  - output_file: `D:\files\project\tmp\bias\reports\capacity\20260702-020409\forum-write-120s.json`
  - stderr_file: `D:\files\project\tmp\bias\reports\capacity\20260702-020409\forum-write-120s.stderr.txt`
  - archive: `python manage.py load_test_http --base-url https://<your-domain> --profile forum-write --login-username <load-user> --login-password <load-password> --discussion-id <discussion-id> --concurrency 5 --duration 120 --fail-on-threshold --format json > D:\files\project\tmp\bias\reports\capacity\20260702-020409\forum-write-120s.json 2> D:\files\project\tmp\bias\reports\capacity\20260702-020409\forum-write-120s.stderr.txt`
- [ ] `p1_forum_write_mixed` (requires_substitution, safe=false, archive_ready=false, manual=false, destructive=false)
  - substitution_tokens: `<load-password>, <load-user>, <your-domain>`
  - requires_completed_commands: `p1_forum_write`
  - command: `python manage.py load_test_http --base-url https://<your-domain> --profile forum-write-mixed --login-username <load-user> --login-password <load-password> --prepare-isolated-targets --cleanup-isolated-targets --concurrency 5 --duration 120 --fail-on-threshold --format json`
  - output_file: `D:\files\project\tmp\bias\reports\capacity\20260702-020409\forum-write-mixed-120s.json`
  - stderr_file: `D:\files\project\tmp\bias\reports\capacity\20260702-020409\forum-write-mixed-120s.stderr.txt`
  - archive: `python manage.py load_test_http --base-url https://<your-domain> --profile forum-write-mixed --login-username <load-user> --login-password <load-password> --prepare-isolated-targets --cleanup-isolated-targets --concurrency 5 --duration 120 --fail-on-threshold --format json > D:\files\project\tmp\bias\reports\capacity\20260702-020409\forum-write-mixed-120s.json 2> D:\files\project\tmp\bias\reports\capacity\20260702-020409\forum-write-mixed-120s.stderr.txt`
- [ ] `p1_forum_upload` (requires_substitution, safe=false, archive_ready=false, manual=false, destructive=false)
  - substitution_tokens: `<load-password>, <load-user>, <your-domain>`
  - command: `python manage.py load_test_http --base-url https://<your-domain> --profile forum-upload --login-username <load-user> --login-password <load-password> --concurrency 5 --duration 120 --fail-on-threshold --format json`
  - output_file: `D:\files\project\tmp\bias\reports\capacity\20260702-020409\forum-upload-120s.json`
  - stderr_file: `D:\files\project\tmp\bias\reports\capacity\20260702-020409\forum-upload-120s.stderr.txt`
  - archive: `python manage.py load_test_http --base-url https://<your-domain> --profile forum-upload --login-username <load-user> --login-password <load-password> --concurrency 5 --duration 120 --fail-on-threshold --format json > D:\files\project\tmp\bias\reports\capacity\20260702-020409\forum-upload-120s.json 2> D:\files\project\tmp\bias\reports\capacity\20260702-020409\forum-upload-120s.stderr.txt`
- [ ] `p1_forum_moderation` (requires_substitution, safe=false, archive_ready=false, manual=false, destructive=false)
  - substitution_tokens: `<moderator-password>, <moderator-user>, <your-domain>`
  - requires_completed_commands: `p1_forum_write_mixed`
  - command: `python manage.py load_test_http --base-url https://<your-domain> --profile forum-write-moderation --login-username <moderator-user> --login-password <moderator-password> --prepare-isolated-targets --cleanup-isolated-targets --concurrency 2 --duration 60 --fail-on-threshold --format json`
  - output_file: `D:\files\project\tmp\bias\reports\capacity\20260702-020409\forum-write-moderation-60s.json`
  - stderr_file: `D:\files\project\tmp\bias\reports\capacity\20260702-020409\forum-write-moderation-60s.stderr.txt`
  - archive: `python manage.py load_test_http --base-url https://<your-domain> --profile forum-write-moderation --login-username <moderator-user> --login-password <moderator-password> --prepare-isolated-targets --cleanup-isolated-targets --concurrency 2 --duration 60 --fail-on-threshold --format json > D:\files\project\tmp\bias\reports\capacity\20260702-020409\forum-write-moderation-60s.json 2> D:\files\project\tmp\bias\reports\capacity\20260702-020409\forum-write-moderation-60s.stderr.txt`
