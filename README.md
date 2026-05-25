# ATRI-HRMS — Python 后端

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat&logo=fastapi&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-D71F00?style=flat&logo=sqlalchemy&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-0.3-1C3C3C?style=flat&logo=langchain&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-4169E1?style=flat&logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-7-DC382D?style=flat&logo=redis&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat&logo=docker&logoColor=white)

基于 **FastAPI + SQLAlchemy + LangChain + LangGraph** 的企业级人力资源管理系统后端，内置 AI 聊天助手「亚托莉（Atri）」。

## 技术栈

| 层级 | 技术 |
|------|------|
| Web 框架 | FastAPI 0.115+ (异步) |
| ORM | SQLAlchemy 2.0 (async) |
| 数据库 | PostgreSQL 16 + pgvector（业务数据 + 向量存储 + Trace 统一单库） |
| AI 框架 | LangChain 0.3 + LangGraph 0.2 |
| LLM | 阿里云 DashScope (qwen-plus) / Ollama 本地 (qwen3:4b) |
| Embedding | text-embedding-v3 (1536 维) |
| 认证 | JWT (python-jose + bcrypt) |
| 可观测性 | Langfuse (可选) + 本地 trace 持久化 |
| 知识图谱 | NetworkX + Neo4j (可选) |
| 多模态 | Whisper (large-v3) + Edge TTS |
| 部署 | Docker + uvicorn |

## 功能模块

### HR 业务

- 员工管理：CRUD + 分部门 / 状态筛选 + 分页
- 部门管理：树形结构 + CRUD
- 职位管理：CRUD + 关联部门
- 考勤管理：打卡记录 + 自动状态计算（正常 / 迟到 / 早退 / 缺勤）
- 请假管理：多级审批工作流 + 审批链自动匹配
- 薪资管理：配置 + 记录 + 审批流程（草稿 → 已提交 → 已审批 → 已发放）

### 权限体系

四层权限模型，从粗到细逐级控制：

| 层级 | 维度 | 说明 |
|------|------|------|
| 第一层 | 角色权限（RBAC） | 菜单 + 按钮级别权限控制 |
| 第二层 | 身份标签 | 员工 / HR / 财务 / 管理员 |
| 第三层 | 模块数据范围 | 公司级 / 部门级 / 个人级 |
| 第四层 | 审批规则引擎 | 基于天数条件的动态审批链 |

### AI 聊天助手「亚托莉」

不是简单的 LLM 套壳。系统构建了完整的 **消息分类 → 知识注入 → 多层 Prompt → 流式输出 → 对话记忆** 管线。

**两阶段消息分类器**

先走零延迟关键词匹配（59 个关键词覆盖 4 大类别），匹配失败再走 LLM 辅助分类。优先级经过精心设计：情绪安抚 > 数据查询 > 流程解释 > 未知。

**三层 Prompt 架构**

- Layer 1 — 角色人设：亚托莉的性格、语气、行为规则
- Layer 2 — 分类指令：根据消息类别选择回答策略（先共情 / 先说结论 / 分步解释）
- Layer 3 — 事实注入：今日日期 + 12+ 业务域实时数据，明确标注「只读真实数据」抑制幻觉

**12+ 业务域数据注入**

AI 直接查询数据库获取真实数据注入上下文，覆盖：系统概览、用户档案、考勤、请假、薪资、部门、职位、角色、权限、天气（高德 API）、AI 自身元数据等。

**SSE 流式输出 + 对话记忆**

- LangChain LCEL 链式调用，逐 chunk 推送 SSE 事件
- 自定义 DatabaseChatMemory，异步 MySQL 持久化，滑动窗口 10 轮对话
- 主备模型自动切换：DashScope → Ollama → 模板降级回复

### Agent 代理执行

使用 LangGraph 构建 6 节点有状态工作流，实现「自然语言 → 意图识别 → 执行计划 → 人工审批 → 自动执行」闭环。

```
intent_recognition → plan_generation → human_approval → execution → result_reporting
                         ↓                  ↓                ↓
                   error_reporting    拒绝则终止      error_reporting
```

核心设计：`human_approval` 是虚拟暂停点，用户确认后直接调用执行节点，不重新跑整个图。支持请假申请、考勤补录、权限修改三种操作，按风险分级需要不同确认级别。

### RAG 知识库

支持 PDF / Word / Markdown / 纯文本上传，完整管线：

```
上传 → 文本提取 → 清洗（去页眉页脚、过滤短行）→ 递归字符分块 (512 字符/块, 50 重叠)
    → text-embedding-v3 向量化 (每批 20 条) → pgvector 存储 → 余弦相似度检索 (top-5)
```

检索结果自动格式化为带来源标注的上下文注入 LLM：`[来源: filename, 分块 #N, 相关度: 0.XX]`。

### 知识图谱（GraphRAG）

HR 领域实体关系建模为有向图，支持多跳关系遍历与向量检索融合：

- **4 类节点**：Employee、Department、Position、Role
- **5 种关系**：belongs_to、holds、has_role、parent_of、in_department
- **BFS 多跳查询**：最大 4 跳，模糊名称匹配
- **融合检索**：向量检索 + 图谱查询结果合并注入 LLM
- **可视化**：导出 ECharts 力导向图格式

### LLM 可观测性

每次调用自动记录：provider、model、Token 用量（tiktoken 计数）、费用估算、延迟、状态。支持按日 / 周聚合统计。可选集成 Langfuse 做可视化 Trace 面板。

模型定价表（元 / 千 Token）：

| 模型 | 输入 | 输出 |
|------|------|------|
| qwen-plus | 0.004 | 0.012 |
| qwen-turbo | 0.001 | 0.002 |
| qwen3:4b (Ollama) | 免费 | 免费 |

## 快速开始

### 1. 环境要求

- Python 3.11+
- PostgreSQL 16+（推荐 Docker: `pgvector/pgvector:pg16-trixie`，统一存储业务数据 + 向量 + Trace）
- Redis（可选，缓存）

### 2. 安装依赖

```bash
cd backend
pip install -e .
# 或
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入数据库连接信息和 LLM API Key
```

### 4. 初始化数据库

```bash
# PostgreSQL 中创建 hrms_db 数据库，然后执行：
psql -U postgres -d hrms_db -f scripts/init_postgres.sql
# 或在 Navicat 中：打开 hrms_db → 新建查询 → 粘贴内容 → 运行
```

### 5. 启动服务

```bash
python run.py              # 开发模式（热重载）
python run.py --prod       # 生产模式
```

Windows 用户也可以直接双击 `start.bat` 启动。

> `run.py` 会自动切换到脚本所在目录，从任意位置运行均可。

访问 http://localhost:8000/docs 查看 API 文档。

### 6. 默认账号

| 用户名 | 密码 | 角色 |
|--------|------|------|
| yunyue | yunyue | 系统管理员 |
| gm | 123456 | 总经理 |
| hr_lina | 123456 | HR 专员 |
| finance_liu | 123456 | 财务经理 |

## 项目结构

```
backend/
├── app/
│   ├── ai/
│   │   ├── chat/            # 聊天核心：服务、分类器、Prompt、记忆、LLM 提供商
│   │   ├── agent/           # Agent 工作流：LangGraph 状态机、节点、状态
│   │   ├── knowledge/       # 业务知识注入：12+ 域只读数据查询
│   │   ├── rag/             # RAG 管线：文档处理、分块、向量化、检索
│   │   ├── graph_rag/       # 知识图谱：NetworkX 图、融合检索
│   │   ├── multimodal/      # 多模态：Whisper 语音、TTS、视觉
│   │   └── observability/   # 可观测性：Token 计数、费用、Langfuse
│   ├── core/                # 核心：配置、认证、权限、数据库连接
│   ├── models/              # SQLAlchemy ORM 模型
│   ├── routers/             # FastAPI 路由（API 端点）
│   ├── schemas/             # Pydantic 请求/响应模型
│   └── services/            # 业务逻辑层
├── scripts/
│   └── init_postgres.sql    # 数据库初始化（表结构 + 种子数据）
├── tests/                   # 测试用例
├── run.py                   # 一键启动脚本
├── start.bat                # Windows 双击启动
├── .env.example             # 环境变量模板（不含真实密钥）
├── Dockerfile               # Docker 构建文件
└── pyproject.toml           # 项目元数据和依赖
```

## 相关文档

- 项目根 README — 项目总览

- `scripts/init_postgres.sql` — 完整数据库 DDL + 种子数据

## License

MIT
