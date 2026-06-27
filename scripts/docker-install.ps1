param(
    [string]$SiteDomains = "localhost",
    [string]$SiteScheme = "http",
    [string]$AdminUsername = "admin",
    [string]$AdminEmail = "admin@example.com",
    [string]$AdminPassword = "",
    [switch]$Overwrite,
    [switch]$SkipBuild
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

function Test-FrontendDist {
    if (-not (Test-Path "frontend\dist\index.html") -or -not (Test-Path "frontend\dist\admin.html")) {
        throw "前端构建产物缺失，请检查 frontend 容器日志：docker compose logs frontend"
    }
}

if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "已从 .env.example 创建 .env，请确认 DB_NAME/DB_USER/DB_PASSWORD 后重新执行。"
        exit 1
    }
    throw "缺少 .env 文件。"
}

if (-not $AdminPassword) {
    $securePassword = Read-Host "管理员密码" -AsSecureString
    $passwordPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
    try {
        $AdminPassword = [Runtime.InteropServices.Marshal]::PtrToStringAuto($passwordPtr)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPtr)
    }
}

if (-not $SkipBuild) {
    Run-Step "构建并启动 Docker 服务" @("docker", "compose", "up", "-d", "--build")
} else {
    Run-Step "启动 Docker 服务" @("docker", "compose", "up", "-d")
}

$installArgs = @(
    "compose", "exec", "web", "python", "manage.py", "install_forum",
    "--database", "postgres",
    "--site-domains", $SiteDomains,
    "--site-scheme", $SiteScheme,
    "--admin-username", $AdminUsername,
    "--admin-email", $AdminEmail,
    "--admin-password", $AdminPassword,
    "--non-interactive"
)
if ($Overwrite) {
    $installArgs += "--overwrite"
}

Run-Step "安装 Bias" @("docker", $installArgs)
Run-Step "重启应用进程" @("docker", "compose", "restart", "web", "celery")
Run-Step "构建前端资源" @("docker", "compose", "restart", "frontend")
Run-Step "等待前端构建完成" @("docker", "compose", "up", "-d", "--wait", "frontend")
Run-Step "检查前端构建产物" @("Test-FrontendDist")
Run-Step "重启 Nginx" @("docker", "compose", "restart", "nginx")
Run-Step "运行部署检查" @("docker", "compose", "exec", "web", "python", "manage.py", "doctor")

Write-Host ""
Write-Host "Bias 安装完成：http://localhost:8080"
