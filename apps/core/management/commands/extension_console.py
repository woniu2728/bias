from __future__ import annotations

import json

from django.core.management import BaseCommand, CommandError
from django.core.management.base import CommandParser

from apps.core.extensions.system_runtime import (
    list_runtime_console_commands,
    list_runtime_console_schedules,
    run_runtime_console_command,
)


class Command(BaseCommand):
    help = "列出或执行扩展注册的控制台命令。"
    requires_system_checks = []

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("name", nargs="?", help="要执行的扩展命令名称。")
        parser.add_argument("--list", action="store_true", help="列出扩展命令。")
        parser.add_argument("--scheduled", action="store_true", help="列出扩展计划任务。")
        parser.add_argument("--payload", default="{}", help="传给扩展命令的 JSON 参数。")
        parser.add_argument("--format", choices=("text", "json"), default="text")

    def handle(self, *args, **options):
        if options.get("scheduled"):
            schedules = [
                {
                    "name": str(schedule.get("name") or ""),
                    "description": str(schedule.get("description") or ""),
                    "schedule": str(schedule.get("schedule") or ""),
                    "args": schedule.get("args") or {},
                }
                for schedule in list_runtime_console_schedules()
            ]
            if options.get("format") == "json":
                self.stdout.write(json.dumps({"schedules": schedules}, ensure_ascii=False, indent=2))
                return
            for schedule in schedules:
                description = f" - {schedule['description']}" if schedule["description"] else ""
                self.stdout.write(f"{schedule['name']} @ {schedule['schedule']}{description}")
            return

        if options.get("list") or not options.get("name"):
            commands = [
                {
                    "name": str(command.get("name") or ""),
                    "description": str(command.get("description") or ""),
                }
                for command in list_runtime_console_commands()
            ]
            if options.get("format") == "json":
                self.stdout.write(json.dumps({"commands": commands}, ensure_ascii=False, indent=2))
                return
            for command in commands:
                description = f" - {command['description']}" if command["description"] else ""
                self.stdout.write(f"{command['name']}{description}")
            return

        try:
            payload = json.loads(str(options.get("payload") or "{}"))
        except json.JSONDecodeError as exc:
            raise CommandError("--payload 必须是合法 JSON") from exc
        if not isinstance(payload, dict):
            raise CommandError("--payload 必须是 JSON 对象")

        result = run_runtime_console_command(str(options.get("name") or ""), options=payload)
        if result is None:
            raise CommandError(f"扩展命令不存在: {options.get('name')}")

        if options.get("format") == "json":
            self.stdout.write(json.dumps({"result": result}, ensure_ascii=False, indent=2, default=str))
            return
        if result is not True:
            self.stdout.write(str(result))
