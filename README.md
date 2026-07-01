# bias

Bias 站点宿主工程。核心后端 SDK 在 `bias_core`，官方扩展位于同级 `bias-ext-*` 包，本仓库只保留站点配置、前端宿主和部署入口。

## 开发落地文档

- [用户可用版本开发落地文档](docs/user-ready-development-plan.md)：总入口，说明与 Flarum 的差距、耦合度判断、下一步开发顺序和用户开放 gate。
- [匿名读路径性能开发文档](docs/anonymous-read-performance-development.md)：当前 P0 阻塞项，跟踪 `forum-main` 300 秒正式容量 gate。

## 本地前端构建

官方扩展已经拆成独立包，但 Vite 仍需要在站点工程内看到扩展前端源码。构建前执行：

```bash
cd frontend
npm run sync:extension-sources
npm run build
```

`sync:extension-sources` 会从同级 `bias-ext-*` 仓库同步 `extension.json` 和 `frontend/` 到 `extensions/<id>`。这些目录是生成的构建输入，不应作为站点源码提交；本地 fixture 扩展 `extensions/fixture_theme` 例外。

## 工作区验证

```powershell
.\scripts\validate-workspace.ps1 -BuildFrontend
```

该脚本会编译 Python 包、检查拆包 import 边界，并验证/构建站点前端。

## 部署前静态资源

发布镜像不包含 Node。前端 dist 应在镜像构建前由宿主机或 CI 生成，再由 Dockerfile 复制进 `/app`：

```bash
cd frontend
npm install
npm run build
```

运行时容器只执行 Django 迁移和 `collectstatic`。
