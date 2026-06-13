param(
    [switch]$SkipPull,
    [switch]$SkipBuild,
    [switch]$SkipDoctor
)

$ErrorActionPreference = "Stop"

function Run-Step {
    param(
        [string]$Label,
        [string[]]$Command
    )
    Write-Host ""
    Write-Host "==> $Label"
    $args = @()
    if ($Command.Length -gt 1) {
        $args = $Command[1..($Command.Length - 1)]
    }
    & $Command[0] @args
}

if (-not (Test-Path ".env")) {
    throw "缺少 .env 文件，请先复制 .env.example 并填写数据库配置。"
}

if (-not $SkipPull) {
    Run-Step "拉取最新代码" @("git", "pull", "--ff-only")
}

if (-not $SkipBuild) {
    Run-Step "构建后端镜像" @("docker", "compose", "build", "web", "celery")
}

Run-Step "启动基础服务" @("docker", "compose", "up", "-d", "db", "redis", "web", "celery", "nginx")
Run-Step "执行 Bias 升级" @("docker", "compose", "exec", "web", "python", "manage.py", "upgrade_forum", "--non-interactive")
Run-Step "重新构建前端资源" @("docker", "compose", "restart", "frontend")
Run-Step "等待前端构建完成" @("docker", "compose", "up", "-d", "--wait", "frontend")
Run-Step "重启应用进程" @("docker", "compose", "restart", "web", "celery", "nginx")

if (-not $SkipDoctor) {
    Run-Step "运行部署检查" @("docker", "compose", "exec", "web", "python", "manage.py", "doctor")
}

Write-Host ""
Write-Host "Bias 升级完成：http://localhost:8080"
