@echo off
REM Bias 快速启动脚本 (Windows)

echo ================================
echo Bias 快速启动
echo ================================
echo.

REM 检查Docker是否安装
docker --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker未安装，请先安装Docker Desktop
    pause
    exit /b 1
)

docker-compose --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker Compose未安装，请先安装Docker Compose
    pause
    exit /b 1
)

echo ✅ Docker环境检查通过
echo.

REM 启动后端服务
echo 🚀 启动后端服务...
docker-compose up -d --build

echo.
echo ⏳ 等待服务启动...
timeout /t 10 /nobreak >nul

REM 运行数据库迁移
echo 📦 运行数据库迁移...
docker-compose exec -T web python manage.py migrate

echo.
echo 👤 创建超级用户（可选，按Ctrl+C跳过）
docker-compose exec web python manage.py createsuperuser

echo.
echo ================================
echo ✅ 后端服务启动成功！
echo ================================
echo.
echo 📍 访问地址：
echo    - 后端API: http://localhost:8000/api
echo    - API文档: http://localhost:8000/api/docs
echo    - 管理后台: http://localhost:8000/admin
echo.
echo 🔧 启动前端开发服务器：
echo    cd frontend
echo    npm install
echo    npm run dev
echo.
echo 📍 前端访问地址：
echo    - 前端应用: http://localhost:3000
echo.
echo 🛑 停止服务：
echo    docker-compose down
echo.
pause
