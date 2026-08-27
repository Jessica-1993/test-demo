# TestHub Demo

TestHub Demo 是一套基于 Django REST Framework 与 Vue 3 的测试资产治理项目。当前系统围绕“项目知识和需求来源 → 人工确认的正式需求 → 版本发布 → 用例生成 → 缺陷反馈 → 用例增强”建立可追溯闭环。

## 当前能力

- Django 默认用户 + SimpleJWT 登录。
- 项目与正式模块的候选修订、人工确认和历史保留。
- 全局大模型、用途/协议/供应商约束和系统角色配置。
- 七牛文档资产、Docling 结构化解析、文本/表格/图片内容块。
- 项目知识与证据、候选需求整合、冲突/开放问题处理、不可变正式需求修订。
- 需求版本发布、Celery 用例生成与模型评审、用例库。
- 缺陷导入/确认、历史证据检索、用例增强建议与人工应用。
- OpenSearch BM25/向量混合检索和可重建索引任务。
- 统一错误码、`trace_id`、脱敏诊断与异步任务错误。

API/UI/APP 自动化、统一测试执行、报告和数据工厂仍是规划模块，详见完整说明书中的[后续开发指南](docs/TestHub-Demo-完整项目说明书.md#chapter-future)。

## 技术栈

- 后端：Python 3.12、Django 4.2、DRF、SimpleJWT、Celery、Channels。
- 前端：Vue 3、Vite、Element Plus、Pinia、Vue Router、Axios。
- 存储：MySQL 8（权威数据）、七牛（文档/图片）、OpenSearch 3（检索副本）、Redis（队列/消息）。
- AI：OpenAI Compatible、OpenAI Responses、Gemini 协议；Embedding 索引固定 768 维。

## 项目结构

```text
test-hub-demo/
├── apps/
│   ├── core/                 # 错误协议、追踪编号和脱敏日志
│   ├── users/                # JWT 登录与当前用户
│   ├── configuration/        # 项目、模型与系统角色
│   ├── project_knowledge/    # 正式模块、项目知识和证据
│   ├── requirements/         # 文档、需求、版本、用例与增强
│   ├── defects/              # 缺陷知识库
│   └── search/               # OpenSearch 网关与索引任务
├── backend/                  # Django settings、URL、Celery、ASGI/WSGI
├── frontend/src/             # Vue 页面、路由、状态、API 和组件
├── docs/                     # 完整项目说明书
├── docker/                   # OpenSearch 本地镜像
├── docker-compose.opensearch.yml
├── requirements.txt
└── manage.py
```

## 完整说明书

新人请从这份单文件说明书开始：[TestHub Demo：从零读懂项目](docs/TestHub-Demo-完整项目说明书.md)。前七部分按学习顺序讲业务、数据关系、后端设计和真实源码链路；接口、排障与后续开发统一放在附录中查阅。

## 快速开始

### 1. 后端

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py check
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 8000
```

默认数据库为 `127.0.0.1:3306/test_hub_demo`，字符集使用 `utf8mb4`。配置项参见 `.env.example`。

### 2. Redis、Celery 与 OpenSearch

启动本地 Redis 后执行：

```bash
.venv/bin/celery -A backend worker -l info
docker compose -f docker-compose.opensearch.yml up -d --build
```

OpenSearch 本地配置关闭安全插件且只绑定 `127.0.0.1`，不能直接作为生产配置。

### 3. 前端

```bash
npm --prefix frontend install
npm --prefix frontend run dev -- --host 0.0.0.0
```

- 前端登录：`http://127.0.0.1:3000/login`
- API 文档：`http://127.0.0.1:8000/api/docs/`
- OpenAPI schema：`http://127.0.0.1:8000/api/schema/`

项目没有 `/api/health/`；OpenSearch 健康检查为登录后的 `/api/search/index-jobs/health/`。

## 开发和验证

开发顺序固定为数据库模型 → 后端 API/Service/Task → 前端 → 端到端验证。架构、模型、路由、依赖或模块边界变化时，必须同步 README 和说明书。

```bash
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/python manage.py migrate --check
.venv/bin/python manage.py test
npm --prefix frontend run build
git diff --check
```

真实 API Key、鉴权头、数据库密码和供应商原始响应不得进入 Git、文档或日志。
