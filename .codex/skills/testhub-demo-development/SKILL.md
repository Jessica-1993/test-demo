---
name: testhub-demo-development
description: 当开发本仓库 /Users/xkj/local/project/Codex/test-hub-demo，或用户要求在 TestHub Demo 骨架中新增前后端业务模块时使用此 skill。它约束当前 Django 4.2 + DRF + MySQL 8.0 + Vue 3/Vite 架构、模块边界、开发顺序和验证流程。
---

# TestHub Demo 开发实践

## 用途

本 skill 用于后续开发当前仓库。这个项目是参考 TestHub 工程分层初始化出来的架构骨架，不是完整 TestHub 产品。开发时保持当前结构：后端业务模块放在 `apps/`，Django 全局配置放在 `backend/`，前端模块放在 `frontend/src/`。

## 开发前先做

每次改代码前：

1. 查看当前目录和 `git status --short`。
2. 先读 `README.md`、`backend/settings.py`、`backend/urls.py`，再读本次相关的 `apps/<module>/` 或 `frontend/src/` 文件。
3. 不要把生成物和本地环境提交进 Git：`.venv/`、`.idea/`、`frontend/node_modules/`、`frontend/dist/`、`__pycache__/`。
4. 不要直接复制原 TestHub 的业务代码，除非用户明确要求。默认只复用它的架构思路和分层方式。

## 开发顺序

新增任何业务能力时，按这个顺序做：

1. **先设计数据库模型**：在 `apps/<module>/models.py` 定义业务实体和关系。
2. **再实现后端 API**：新增 `serializers.py`、`views.py`、`urls.py`；在 `backend/settings.py` 注册 app；在 `backend/urls.py` 挂载 `/api/<module>/`。
3. **API 稳定后再做前端**：新增 `frontend/src/api/<module>.js`、`frontend/src/views/<module>/`，再补路由和菜单。
4. **架构变化后同步文档**：如果新增/调整 app、路由、目录、配置、依赖、数据库模型或前后端模块边界，必须同步更新 `README.md` 的目录说明和架构说明。
5. **最后做端到端验证**：运行后端检查/迁移、前端构建，并验证一个真实 API 或页面路径。

不要在后端模型和 API 未定义前先堆 Vue 页面。

## 后端模块规范

业务模块使用下面的目录结构：

```text
apps/<module>/
├── __init__.py
├── apps.py
├── models.py
├── serializers.py
├── views.py
├── urls.py
├── services.py      # 业务逻辑复杂时再加
└── tasks.py         # 需要 Celery / 后台任务时再加
```

后端接口规则：

- CRUD 资源默认使用 DRF `ModelViewSet`。
- 资源上的命令操作用 `@action`，例如执行、导入、启用、禁用、状态查询。
- 复杂业务放进 `services.py` 或 executor 类，ViewSet 只负责请求校验、权限、编排和响应。
- 返回关联数据时考虑 `select_related` / `prefetch_related`。
- 后续如果增加 AI 能力，模型配置、API Key、Prompt 等业务配置应使用数据库配置表；不要硬编码密钥，也不要把密钥返回给前端。

数据库规则：

- 默认使用本地 MySQL 8.0，通过 `PyMySQL` 连接。
- 默认数据库：`test_hub_demo`；用户：`root`；密码为空；主机：`127.0.0.1`；端口：`3306`。
- 字符集使用 `utf8mb4`，SQL 模式使用 `STRICT_TRANS_TABLES`。
- 新增模型后必须创建迁移，并在 MySQL 上执行迁移验证。

## 前端模块规范

每个前端业务模块使用下面的结构：

```text
frontend/src/api/<module>.js              # Axios API 函数
frontend/src/views/<module>/<Page>.vue    # 页面
frontend/src/router/index.js              # 路由注册
frontend/src/layout/index.vue             # 菜单入口
frontend/src/stores/<module>.js           # 仅在需要跨页面共享状态时新增
```

前端开发规则：

- 所有 HTTP 请求都通过 `frontend/src/utils/api.js`，不要在页面里直接新建 Axios 实例。
- 保持 `baseURL: /api`，通过 Vite 代理访问 Django。
- 页面调用 `frontend/src/api/<module>.js` 中的函数，不要在页面里散落接口 URL 字符串。
- UI 使用当前后台壳子的 Element Plus 风格。
- 如果开发异步执行类模块，要围绕任务记录、状态字段、日志、轮询或 WebSocket 设计，不要假设一次请求立即完成。

## 推荐模块顺序

除非用户明确指定其它顺序，否则按下面顺序推进：

1. `projects`：`Project`、`ProjectMember`、`ProjectEnvironment`，先跑通 Model -> API -> Vue 表格/表单。
2. `testcases`：手工测试用例 CRUD 和步骤。
3. `executions`：测试计划、测试执行、执行用例、结果历史。
4. `reports`：报告摘要和报告记录。
5. 自动化或 AI 模块：等核心项目/用例/执行链路稳定后再做。

## 验证清单

后端改动后运行：

```bash
source .venv/bin/activate
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
```

前端改动后运行：

```bash
cd frontend
npm run build
```

端到端验证入口：

- 后端健康检查：`http://127.0.0.1:8000/api/health/`
- API 文档：`http://127.0.0.1:8000/api/docs/`
- 前端入口：`http://127.0.0.1:3000/`
- 确认前端页面通过 Vite 代理调用目标 `/api/<module>/` 接口。

## 提交规范

提交前：

1. 查看 `git status --short`。
2. 确认没有暂存缓存、构建产物、密钥或 IDE 文件。
3. 如果本次涉及项目架构变动，确认 `README.md` 已同步更新。
4. 使用简洁提交信息，例如 `feat: 添加项目管理模块` 或 `chore: 初始化模块骨架`。
