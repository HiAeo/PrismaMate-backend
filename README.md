# PrismaMate Backend - FastAPI 后端服务

## 环境要求

- Python 3.11+
- PostgreSQL 15+
- Redis 7+

## 安装依赖

```bash
pip install -r requirements.txt
```

## 数据库迁移

```bash
# 初始化 Alembic
alembic init alembic

# 生成迁移脚本
alembic revision --autogenerate -m "init"

# 执行迁移
alembic upgrade head
```

## 运行服务

```bash
# 开发模式
uvicorn app.main:app --reload --port 8000

# 生产模式
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```

## 项目结构

```
app/
├── api/           # API 路由
│   └── v1/       # V1 版本 API
├── core/          # 核心配置
│   ├── config.py  # 配置管理
│   ├── security.py # 安全相关
│   └── database.py # 数据库连接
├── models/        # SQLAlchemy 模型
├── schemas/       # Pydantic 模型
├── services/      # 业务逻辑
├── tasks/         # Celery 任务
└── adapters/      # 平台适配器
```

## 配置

配置通过 `config/` 目录下的 YAML 文件管理，详见各配置文件注释。

## API 文档

启动服务后访问：http://localhost:8000/docs
