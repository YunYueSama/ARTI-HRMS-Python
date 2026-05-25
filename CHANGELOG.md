# 变更日志

本文件记录项目的所有重要变更，格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/)。

## [2.0.0] - 2025-01-20

### 新增

#### 核心架构
- 从 Java Spring Boot 完整重构为 Python FastAPI 异步架构
- 基于 SQLAlchemy 2.0 的异步 ORM 层，映射现有 MySQL 表结构
- Pydantic 2.x 数据校验和序列化层，自动生成 OpenAPI 文档
- 基于 pydantic-settings 的环境变量配置管理
- 全局异常处理器，统一 JSON 错误响应格式
- 应用生命周期管理（Lifespan），优雅启动和关闭

#### 认证与权限
- JWT Token 认证，兼容原 Java 版本的 BCrypt 密码哈希
- 四层权限模型：操作权限 → 数据范围 → 字段权限 → 审批规则
- FastAPI 依赖注入实现透明的权限校验

#### HR 业务模块
- 员工管理：CRUD、搜索、分页、统计
- 部门管理：树形结构、层级查询
- 职位管理：岗位定义与分配
- 考勤管理：打卡记录、月度统计、异常检测
- 请假管理：申请、多级审批流程
- 薪资管理：配置模板、自动计算、批量发放
- 报表统计：多维度数据分析

#### AI 聊天助手
- 基于 LangChain 的智能聊天服务（角色：亚托莉）
- 对话历史管理（Memory），支持多轮上下文
- 意图分类器：闲聊/HR查询/操作指令自动路由
- SSE 流式输出，实时显示生成内容
- 主备 LLM 双提供商（DashScope + Ollama），自动故障转移

#### Agent 任务引擎
- 基于 LangGraph 的有状态工作流引擎
- 自然语言指令 → 意图识别 → 计划生成 → 执行
- 人工审批节点：高风险操作需用户确认
- 业务工具集：员工查询、请假申请、考勤统计等
- 任务状态持久化，支持断点续执行

#### RAG 文档知识库
- 文档上传与解析（PDF/Word/TXT）
- 智能分块策略（512 Token/块，50 Token 重叠）
- 向量嵌入与存储（pgvector）
- 语义检索（余弦相似度 Top-K）
- 检索结果融入聊天上下文

#### GraphRAG 知识图谱
- 基于 NetworkX 的内存图计算
- Neo4j 持久化存储（可选）
- 实体关系抽取与多跳查询
- 与 RAG 向量检索互补

#### 多模态交互
- OpenAI Whisper 语音转文字（STT）
- Edge-TTS 文字转语音（TTS）
- 语音输入 → AI 处理 → 语音输出完整链路

#### LLM 可观测性
- Langfuse 全链路追踪（Trace → Span → Generation）
- Token 用量统计与费用估算
- 慢响应检测与告警
- 调用成功率监控

#### Token 管理
- 上下文窗口使用率监控
- Token 预算分配策略
- 自动截断过长对话历史

#### 部署与运维
- Docker Compose 一键部署（后端 + MySQL + PostgreSQL + Redis + Ollama）
- GitHub Actions CI/CD 流水线（测试 → 构建 → 部署）
- Harness CI 配置
- 健康检查端点（/health）
- 开发/生产环境配置分离

### 变更

- 后端语言从 Java 17 迁移到 Python 3.11+
- Web 框架从 Spring Boot 迁移到 FastAPI
- ORM 从 MyBatis-Plus 迁移到 SQLAlchemy 2.0（异步）
- AI 框架从自定义 RestClient 调用迁移到 LangChain/LangGraph
- 认证从 Spring Security 迁移到 python-jose + passlib
- 构建工具从 Maven 迁移到 pyproject.toml (PEP 621)
- 部署方式从 JAR 包迁移到 Docker 容器
- API 文档从手动维护迁移到 FastAPI 自动生成（Swagger UI）
