<div align="center">

<img src="https://github.com/user-attachments/assets/47258057-8df9-4bf0-9bfb-dc4a234e3f38" width="120" alt="ATRI Logo" />

# ATRI-HRMS — Python 后端

**基于 FastAPI + LangChain + LangGraph 的企业级 HRMS 后端服务**

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat&logo=fastapi&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-D71F00?style=flat&logo=sqlalchemy&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-0.3-1C3C3C?style=flat&logo=langchain&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-4169E1?style=flat&logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-7-DC382D?style=flat&logo=redis&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat&logo=docker&logoColor=white)

内置 AI 聊天助手「亚托莉（Atri）」，配合 [前端项目](https://github.com/YunYueSama/ARTI-HRMS-WEB) 使用。

</div>

---

## 技术栈

| 层级 | 技术 |
|------|------|
| Web 框架 | FastAPI 0.115+ (异步) |
| ORM | SQLAlchemy 2.0 (async) |
| 数据库 | PostgreSQL 16 + pgvector（业务数据 + 向量存储 + Trace 统一单库） |
| AI 框架 | LangChain 0.3 + LangGraph 0.2 |
| LLM | 阿里云 DashScope (qwen-plus) / Ollama 本地 (qwen3:4b) |
| Embedding | text-embedding-v2 (1536 维，DashScope OpenAI 兼容接口) |
| 认证 | JWT (python-jose + bcrypt) |
| 可观测性 | Langfuse (可选) + 本地 trace 持久化 |
| 知识图谱 | NetworkX + Neo4j (可选) |
| 多模态 | Whisper (large-v3) + Edge TTS |
| 部署 | Docker + uvicorn |

## 功能模块

### HR 业务

| 模块 | 功能 |
|------|------|
| **员工管理** | CRUD + 分部门 / 状态筛选 + 分页 |
| **部门管理** | 树形结构 + CRUD |
| **职位管理** | CRUD + 关联部门 |
| **考勤管理** | 打卡记录 + 自动状态计算（正常 / 迟到 / 早退 / 缺勤） |
| **请假管理** | 多级审批工作流 + 审批链自动匹配 |
| **薪酬管理** | 配置 + 记录 + 审批流程（草稿 → 已发放） |

### 权限体系

四层权限模型，从粗到细逐级控制：

| 层级 | 维度 | 说明 |
|------|------|------|
| 第一层 | 角色权限（RBAC） | 菜单 + 按钮级别权限控制 |
| 第二层 | 身份标签 | 员工 / HR / 财务 / 管理员 |
| 第三层 | 模块数据范围 | 公司级 / 部门级 / 个人级 |
| 第四层 | 审批规则引擎 | 基于天数条件的动态审批链 |

AI 聊天同样遵循权限体系 — 用户只能查询自己权限范围内的数据，管理员角色自动获得全部权限。

### AI 聊天助手「亚托莉」

不是简单的 LLM 套壳。系统构建了完整的 **消息分类 → 混合检索 → 知识注入 → 多层 Prompt → 流式输出 → 对话记忆** 管线。

**两阶段消息分类器**

先走零延迟关键词匹配（59 个关键词覆盖 4 大类别），匹配失败再走 LLM 辅助分类。优先级：情绪安抚 > 数据查询 > 流程解释 > 未知。

**三层 Prompt 架构**

- Layer 1 — 角色人设：亚托莉的性格、语气、行为规则（支持数据库动态配置）
- Layer 1.5 — 输出格式约束：防编造规则 + 逐字引用原则 + 禁止装饰性 emoji
- Layer 2 — 分类指令：根据消息类别选择回答策略
- Layer 3 — 事实注入：今日日期 + 混合检索结果，明确标注「只读真实数据」抑制幻觉

**混合检索 + RRF 融合**

当用户查询业务数据时，系统并行发起三路检索，最后用 RRF（Reciprocal Rank Fusion）算法融合排名：

```
用户查询
  ├── 关键词查询（query_knowledge）→ MySQL 直查，12+ 业务域
  ├── 增强向量检索（enhanced_vector_search）→ pgvector 余弦相似度 + 查询增强
  └── 知识图谱查询（graph_rag）→ 实体匹配 → NetworkX 多跳遍历
          │
          ▼
   RRF 融合（k=60）→ 统一排名 → 注入 LLM 上下文
```

**查询增强引擎**

短查询自动检测，使用 qwen-turbo 并行执行三种增强：

- **查询改写（Rewrite）**：口语化 → 正式表述
- **查询扩展（Expand）**：生成 3 个相关搜索关键词
- **HyDE**：生成假设性文档片段用于嵌入检索

**可配置人设**

人设通过 `persona_config` 表存储，支持前端在线编辑和切换激活，无需改代码。

**防编造机制**

1. Prompt 层：逐字引用原则，禁止改写扩充
2. Few-Shot 层：正反示例对比
3. 数据层：无数据时不注入上下文

**SSE 流式输出 + 对话记忆**

- LangChain LCEL 链式调用，逐 chunk 推送 SSE 事件
- `<think>` 思考标签自动过滤
- DatabaseChatMemory：异步 PostgreSQL 持久化，滑动窗口 10 轮
- 主备模型自动切换：DashScope → Ollama → 模板降级
- 用户反馈闭环：👍/👎 关联 Langfuse Trace

### Agent 代理执行

LangGraph 构建 6 节点有状态工作流：

```
intent_recognition → plan_generation → human_approval → execution → result_reporting
                         ↓                  ↓                ↓
                   error_reporting    拒绝则终止      error_reporting
```

支持请假申请、考勤补录、权限修改三种操作，按风险分级需要不同确认级别。

### RAG 知识库

```
上传 → 文本提取 → 清洗 → 递归字符分块 (512 字符/块, 50 重叠)
    → text-embedding-v2 向量化 → pgvector 存储 → 余弦相似度检索 (top-5)
```

### 知识图谱（GraphRAG）

- **4 类节点**：Employee、Department、Position、Role
- **5 种关系**：belongs_to、holds、has_role、parent_of、in_department
- **BFS 多跳查询**：最大 4 跳，模糊名称匹配
- **融合检索**：向量检索 + 图谱查询通过 RRF 合并

### LLM 可观测性

每次调用自动记录：provider、model、Token 用量、费用估算、延迟、状态。

| 模型 | 输入（元/千Token） | 输出（元/千Token） |
|------|------|------|
| qwen-plus | 0.004 | 0.012 |
| qwen-turbo | 0.001 | 0.002 |
| qwen3:4b (Ollama) | 免费 | 免费 |

## 快速开始

### 环境要求

- Python 3.11+
- PostgreSQL 16+（推荐 Docker: `pgvector/pgvector:pg16-trixie`）
- Redis（可选，缓存）

### 安装与运行

```bash
# 安装依赖
cd backend
pip install -e .

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入数据库连接信息和 LLM API Key

# 初始化数据库
psql -U postgres -d hrms_db -f scripts/init_postgres.sql

# 启动服务
python run.py              # 开发模式（热重载）
python run.py --prod       # 生产模式
```

Windows 用户也可以直接双击 `start.bat` 启动。

访问 http://localhost:8000/docs 查看 API 文档。

### 默认账号

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
│   │   ├── agent/           # Agent 工作流：LangGraph 状态机
│   │   ├── knowledge/       # 业务知识注入：12+ 域数据查询
│   │   ├── rag/             # RAG 管线：文档处理、分块、向量化、检索
│   │   ├── graph_rag/       # 知识图谱：NetworkX 图、RRF 融合
│   │   ├── multimodal/      # 多模态：Whisper 语音、TTS
│   │   └── observability/   # 可观测性：Token 计数、Langfuse
│   ├── core/                # 核心：配置、认证、权限、数据库
│   ├── models/              # SQLAlchemy ORM 模型
│   ├── routers/             # FastAPI 路由
│   ├── schemas/             # Pydantic 请求/响应模型
│   └── services/            # 业务逻辑层
├── scripts/
│   ├── init_postgres.sql    # 数据库初始化
│   └── migrate_*.sql        # 增量迁移脚本
├── run.py                   # 一键启动脚本
├── start.bat                # Windows 双击启动
├── .env.example             # 环境变量模板
├── Dockerfile               # Docker 构建文件
└── pyproject.toml           # 项目元数据和依赖
```

## 设计特点

**混合检索 + RRF 融合** — 关键词查询、向量检索、知识图谱三路并行，RRF 算法统一排名。

**四层权限体系** — RBAC → 身份标签 → 数据范围 → 审批规则，AI 聊天同样受权限约束。

**查询增强引擎** — 短查询自动改写 / 扩展 / HyDE，提升向量检索召回率。

**可配置人设** — 数据库持久化，前端在线编辑，无需改代码即可切换 AI 人格。

**防编造机制** — Prompt 约束 + Few-Shot + 数据层防护，确保 AI 只引用真实数据。

## 相关项目

- [ARTI-HRMS-WEB](https://github.com/YunYueSama/ARTI-HRMS-WEB) — Vue 3 前端

## License

MIT
