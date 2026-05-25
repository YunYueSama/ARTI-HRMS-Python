-- ============================================================
-- HRMS PostgreSQL 一站式初始化脚本
--
-- 用途：用一份 PG 实例承载全部数据，包含：
--   1. HR 业务库（员工、部门、岗位、考勤、请假、薪资、权限、Agent 任务等）
--   2. AI 聊天历史（ai_chat_message）
--   3. RAG 知识库（rag_document、rag_chunk + pgvector）
--   4. LLM 追踪持久化（llm_trace，原本是内存存储，重启丢数据）
--
-- 用法（Navicat）：
--   1. 新建数据库 hrms_db，编码 UTF-8
--   2. 双击进入 hrms_db
--   3. 顶部"查询" → 新建查询 → 粘贴本文件全部内容 → 运行
--
-- 前置：PostgreSQL 镜像必须自带 pgvector 扩展
--      （pgvector/pgvector:pg16 或更高版本）
-- ============================================================

-- 启用 pgvector 扩展
CREATE EXTENSION IF NOT EXISTS vector;

-- ------------------------------------------------------------
-- 通用 update_time 自动维护触发器函数
-- 说明：MySQL 的 ON UPDATE CURRENT_TIMESTAMP 在 PG 中需要触发器实现
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION trigger_set_update_time()
RETURNS TRIGGER AS $$
BEGIN
    NEW.update_time = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-- ============================================================
-- 1. 基础数据表
-- ============================================================

-- 部门表
DROP TABLE IF EXISTS department CASCADE;
CREATE TABLE department (
    dept_id     SERIAL PRIMARY KEY,
    dept_name   VARCHAR(100) NOT NULL UNIQUE,
    dept_desc   TEXT,
    parent_id   INTEGER REFERENCES department(dept_id),
    create_time TIMESTAMP NOT NULL DEFAULT NOW(),
    update_time TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_department_parent_id ON department(parent_id);
CREATE TRIGGER trg_department_update BEFORE UPDATE ON department
    FOR EACH ROW EXECUTE FUNCTION trigger_set_update_time();

-- 身份标签表
DROP TABLE IF EXISTS identity_tag CASCADE;
CREATE TABLE identity_tag (
    tag_code    VARCHAR(50) PRIMARY KEY,
    tag_name    VARCHAR(50) NOT NULL,
    tag_desc    VARCHAR(255),
    create_time TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 职位表
DROP TABLE IF EXISTS job_position CASCADE;
CREATE TABLE job_position (
    position_id   SERIAL PRIMARY KEY,
    position_name VARCHAR(100) NOT NULL,
    position_desc TEXT,
    dept_id       INTEGER NOT NULL REFERENCES department(dept_id),
    create_time   TIMESTAMP NOT NULL DEFAULT NOW(),
    update_time   TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_job_position_dept_id ON job_position(dept_id);
CREATE TRIGGER trg_job_position_update BEFORE UPDATE ON job_position
    FOR EACH ROW EXECUTE FUNCTION trigger_set_update_time();

-- 员工表
DROP TABLE IF EXISTS employee CASCADE;
CREATE TABLE employee (
    emp_id            SERIAL PRIMARY KEY,
    emp_name          VARCHAR(50) NOT NULL,
    gender            VARCHAR(10) NOT NULL CHECK (gender IN ('男','女')),
    phone             VARCHAR(20) NOT NULL UNIQUE,
    email             VARCHAR(100) UNIQUE,
    id_card           VARCHAR(18) UNIQUE,
    birthday          DATE,
    address           VARCHAR(255),
    hire_date         DATE NOT NULL,
    leave_date        DATE,
    dept_id           INTEGER NOT NULL REFERENCES department(dept_id),
    position_id       INTEGER NOT NULL REFERENCES job_position(position_id),
    identity_tag_code VARCHAR(50) REFERENCES identity_tag(tag_code),
    status            VARCHAR(20) NOT NULL DEFAULT '在职',
    create_time       TIMESTAMP NOT NULL DEFAULT NOW(),
    update_time       TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_employee_dept_id ON employee(dept_id);
CREATE INDEX idx_employee_position_id ON employee(position_id);
CREATE INDEX idx_employee_hire_date ON employee(hire_date);
CREATE INDEX idx_employee_identity_tag_code ON employee(identity_tag_code);
CREATE TRIGGER trg_employee_update BEFORE UPDATE ON employee
    FOR EACH ROW EXECUTE FUNCTION trigger_set_update_time();

-- 角色表
DROP TABLE IF EXISTS role CASCADE;
CREATE TABLE role (
    role_id     SERIAL PRIMARY KEY,
    role_name   VARCHAR(50) NOT NULL UNIQUE,
    role_code   VARCHAR(50) NOT NULL UNIQUE,
    role_desc   VARCHAR(255),
    create_time TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 系统用户
DROP TABLE IF EXISTS sys_user CASCADE;
CREATE TABLE sys_user (
    user_id     SERIAL PRIMARY KEY,
    emp_id      INTEGER NOT NULL UNIQUE REFERENCES employee(emp_id),
    username    VARCHAR(50) NOT NULL UNIQUE,
    password    VARCHAR(255) NOT NULL,
    role_id     INTEGER NOT NULL REFERENCES role(role_id),
    status      VARCHAR(20) NOT NULL DEFAULT '启用',
    last_login  TIMESTAMP,
    create_time TIMESTAMP NOT NULL DEFAULT NOW(),
    update_time TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_sys_user_role_id ON sys_user(role_id);
CREATE TRIGGER trg_sys_user_update BEFORE UPDATE ON sys_user
    FOR EACH ROW EXECUTE FUNCTION trigger_set_update_time();

-- 权限表
DROP TABLE IF EXISTS permission CASCADE;
CREATE TABLE permission (
    perm_id     SERIAL PRIMARY KEY,
    perm_name   VARCHAR(100) NOT NULL,
    perm_code   VARCHAR(100) NOT NULL UNIQUE,
    perm_type   VARCHAR(20) NOT NULL DEFAULT 'BUTTON',
    parent_id   INTEGER REFERENCES permission(perm_id),
    path        VARCHAR(255),
    icon        VARCHAR(50),
    sort_order  INTEGER NOT NULL DEFAULT 0,
    create_time TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_permission_parent_id ON permission(parent_id);

-- 角色权限关联
DROP TABLE IF EXISTS role_permission CASCADE;
CREATE TABLE role_permission (
    id      SERIAL PRIMARY KEY,
    role_id INTEGER NOT NULL REFERENCES role(role_id),
    perm_id INTEGER NOT NULL REFERENCES permission(perm_id),
    UNIQUE (role_id, perm_id)
);
CREATE INDEX idx_role_permission_perm_id ON role_permission(perm_id);

-- 模块范围规则
DROP TABLE IF EXISTS module_scope_rule CASCADE;
CREATE TABLE module_scope_rule (
    module_code   VARCHAR(50) PRIMARY KEY,
    module_name   VARCHAR(100) NOT NULL,
    default_scope VARCHAR(20) NOT NULL DEFAULT 'dept',
    create_time   TIMESTAMP NOT NULL DEFAULT NOW(),
    update_time   TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE TRIGGER trg_module_scope_rule_update BEFORE UPDATE ON module_scope_rule
    FOR EACH ROW EXECUTE FUNCTION trigger_set_update_time();

-- 模块范围细则
DROP TABLE IF EXISTS module_scope_detail CASCADE;
CREATE TABLE module_scope_detail (
    id          SERIAL PRIMARY KEY,
    module_code VARCHAR(50) NOT NULL REFERENCES module_scope_rule(module_code),
    tag_code    VARCHAR(50) NOT NULL REFERENCES identity_tag(tag_code),
    scope       VARCHAR(20) NOT NULL,
    create_time TIMESTAMP NOT NULL DEFAULT NOW(),
    update_time TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (module_code, tag_code)
);
CREATE INDEX idx_module_scope_detail_tag_code ON module_scope_detail(tag_code);
CREATE TRIGGER trg_module_scope_detail_update BEFORE UPDATE ON module_scope_detail
    FOR EACH ROW EXECUTE FUNCTION trigger_set_update_time();

-- 部门权限模板
DROP TABLE IF EXISTS dept_permission_template CASCADE;
CREATE TABLE dept_permission_template (
    id          SERIAL PRIMARY KEY,
    dept_id     INTEGER NOT NULL REFERENCES department(dept_id),
    module_code VARCHAR(50) NOT NULL REFERENCES module_scope_rule(module_code),
    create_time TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (dept_id, module_code)
);
CREATE INDEX idx_dept_permission_template_module_code ON dept_permission_template(module_code);

-- 审批规则类型
DROP TABLE IF EXISTS approval_rule_type CASCADE;
CREATE TABLE approval_rule_type (
    type_code   VARCHAR(50) PRIMARY KEY,
    type_name   VARCHAR(100) NOT NULL,
    type_desc   VARCHAR(255),
    status      VARCHAR(20) NOT NULL DEFAULT '启用',
    create_time TIMESTAMP NOT NULL DEFAULT NOW(),
    update_time TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE TRIGGER trg_approval_rule_type_update BEFORE UPDATE ON approval_rule_type
    FOR EACH ROW EXECUTE FUNCTION trigger_set_update_time();

-- 审批规则
DROP TABLE IF EXISTS approval_rule CASCADE;
CREATE TABLE approval_rule (
    rule_id               SERIAL PRIMARY KEY,
    type_code             VARCHAR(50) NOT NULL REFERENCES approval_rule_type(type_code),
    applicant_tag         VARCHAR(50) NOT NULL,
    days_op               VARCHAR(10) NOT NULL,
    days_value            NUMERIC(6, 2) NOT NULL DEFAULT 0,
    first_approver_tag    VARCHAR(50) NOT NULL,
    second_approver_tag   VARCHAR(50),
    second_approver_scope VARCHAR(20),
    sort_order            INTEGER NOT NULL DEFAULT 0,
    create_time           TIMESTAMP NOT NULL DEFAULT NOW(),
    update_time           TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_approval_rule_type_code ON approval_rule(type_code);
CREATE INDEX idx_approval_rule_applicant_tag ON approval_rule(applicant_tag);
CREATE TRIGGER trg_approval_rule_update BEFORE UPDATE ON approval_rule
    FOR EACH ROW EXECUTE FUNCTION trigger_set_update_time();


-- ============================================================
-- 2. 业务数据表（考勤、请假、薪资）
-- ============================================================

-- 考勤
DROP TABLE IF EXISTS attendance CASCADE;
CREATE TABLE attendance (
    attendance_id   SERIAL PRIMARY KEY,
    emp_id          INTEGER NOT NULL REFERENCES employee(emp_id),
    attendance_date DATE NOT NULL,
    clock_in        TIME,
    clock_out       TIME,
    status          VARCHAR(20) NOT NULL,
    remark          VARCHAR(255),
    create_time     TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (emp_id, attendance_date)
);
CREATE INDEX idx_attendance_date_status ON attendance(attendance_date, status);

-- 请假
DROP TABLE IF EXISTS leave_request CASCADE;
CREATE TABLE leave_request (
    leave_id              SERIAL PRIMARY KEY,
    emp_id                INTEGER NOT NULL REFERENCES employee(emp_id),
    leave_type            VARCHAR(20) NOT NULL,
    start_date            DATE NOT NULL,
    end_date              DATE NOT NULL,
    days                  NUMERIC(6, 2) NOT NULL,
    reason                TEXT NOT NULL,
    status                VARCHAR(20) NOT NULL,
    approver_id           INTEGER REFERENCES sys_user(user_id),
    pending_approver_tag  VARCHAR(50),
    pending_approver_scope VARCHAR(20),
    next_approver_tag     VARCHAR(50),
    next_approver_scope   VARCHAR(20),
    apply_time            TIMESTAMP NOT NULL DEFAULT NOW(),
    approve_time          TIMESTAMP,
    approve_remark        VARCHAR(255)
);
CREATE INDEX idx_leave_request_emp_id ON leave_request(emp_id);
CREATE INDEX idx_leave_request_apply_time ON leave_request(apply_time);
CREATE INDEX idx_leave_request_status ON leave_request(status);
CREATE INDEX idx_leave_request_approver_id ON leave_request(approver_id);

-- 薪资配置
DROP TABLE IF EXISTS salary_config CASCADE;
CREATE TABLE salary_config (
    config_id      SERIAL PRIMARY KEY,
    config_name    VARCHAR(100) NOT NULL,
    config_key     VARCHAR(100) NOT NULL,
    config_value   VARCHAR(255) NOT NULL,
    config_desc    VARCHAR(255),
    effective_date DATE,
    status         VARCHAR(20) NOT NULL DEFAULT '草稿',
    submit_date    DATE,
    approve_date   DATE,
    create_time    TIMESTAMP NOT NULL DEFAULT NOW(),
    update_time    TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (config_key, effective_date)
);
CREATE TRIGGER trg_salary_config_update BEFORE UPDATE ON salary_config
    FOR EACH ROW EXECUTE FUNCTION trigger_set_update_time();

-- 薪资记录
DROP TABLE IF EXISTS salary_record CASCADE;
CREATE TABLE salary_record (
    salary_id             SERIAL PRIMARY KEY,
    emp_id                INTEGER NOT NULL REFERENCES employee(emp_id),
    salary_month          DATE NOT NULL,
    base_salary           NUMERIC(10, 2) NOT NULL DEFAULT 0,
    position_salary       NUMERIC(10, 2) NOT NULL DEFAULT 0,
    bonus                 NUMERIC(10, 2) NOT NULL DEFAULT 0,
    overtime_pay          NUMERIC(10, 2) NOT NULL DEFAULT 0,
    gross_salary          NUMERIC(10, 2) NOT NULL DEFAULT 0,
    social_insurance      NUMERIC(10, 2) NOT NULL DEFAULT 0,
    housing_fund          NUMERIC(10, 2) NOT NULL DEFAULT 0,
    attendance_deduct     NUMERIC(10, 2) NOT NULL DEFAULT 0,
    tax                   NUMERIC(10, 2) NOT NULL DEFAULT 0,
    other_deduct          NUMERIC(10, 2) NOT NULL DEFAULT 0,
    net_salary            NUMERIC(10, 2) NOT NULL DEFAULT 0,
    status                VARCHAR(20) NOT NULL DEFAULT '待发放',
    pending_approver_role VARCHAR(50),
    next_approver_role    VARCHAR(50),
    next_approver_scope   VARCHAR(20),
    submit_date           DATE,
    approve_date          DATE,
    pay_date              DATE,
    create_time           TIMESTAMP NOT NULL DEFAULT NOW(),
    update_time           TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (emp_id, salary_month)
);
CREATE INDEX idx_salary_record_month ON salary_record(salary_month);
CREATE INDEX idx_salary_record_status ON salary_record(status);
CREATE TRIGGER trg_salary_record_update BEFORE UPDATE ON salary_record
    FOR EACH ROW EXECUTE FUNCTION trigger_set_update_time();

-- 操作日志
DROP TABLE IF EXISTS operation_log CASCADE;
CREATE TABLE operation_log (
    log_id           BIGSERIAL PRIMARY KEY,
    user_id          INTEGER REFERENCES sys_user(user_id),
    operation_time   TIMESTAMP NOT NULL DEFAULT NOW(),
    operation_type   VARCHAR(50) NOT NULL,
    operation_module VARCHAR(100) NOT NULL,
    operation_desc   TEXT NOT NULL
);
CREATE INDEX idx_operation_log_user_id ON operation_log(user_id);
CREATE INDEX idx_operation_log_time ON operation_log(operation_time);


-- ============================================================
-- 3. AI 相关表
-- ============================================================

-- Agent 任务
DROP TABLE IF EXISTS agent_task CASCADE;
CREATE TABLE agent_task (
    task_id           SERIAL PRIMARY KEY,
    user_id           INTEGER NOT NULL REFERENCES sys_user(user_id),
    command_text      TEXT NOT NULL,
    intent            VARCHAR(100) NOT NULL,
    risk_level        VARCHAR(20) NOT NULL,
    status            VARCHAR(20) NOT NULL,
    provider_name     VARCHAR(100),
    requires_approval BOOLEAN NOT NULL DEFAULT TRUE,
    executable        BOOLEAN NOT NULL DEFAULT FALSE,
    plan_json         TEXT NOT NULL,
    result_summary    VARCHAR(255),
    create_time       TIMESTAMP NOT NULL DEFAULT NOW(),
    update_time       TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_agent_task_user_id ON agent_task(user_id);
CREATE INDEX idx_agent_task_status ON agent_task(status);
CREATE INDEX idx_agent_task_create_time ON agent_task(create_time);
CREATE TRIGGER trg_agent_task_update BEFORE UPDATE ON agent_task
    FOR EACH ROW EXECUTE FUNCTION trigger_set_update_time();

-- Agent 执行日志
DROP TABLE IF EXISTS agent_execution_log CASCADE;
CREATE TABLE agent_execution_log (
    log_id      SERIAL PRIMARY KEY,
    task_id     INTEGER NOT NULL REFERENCES agent_task(task_id),
    step_no     INTEGER NOT NULL DEFAULT 0,
    log_level   VARCHAR(20) NOT NULL,
    message     TEXT,
    create_time TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_agent_execution_task_id ON agent_execution_log(task_id);
CREATE INDEX idx_agent_execution_step_no ON agent_execution_log(step_no);

-- Agent 审批记录
DROP TABLE IF EXISTS agent_approval_record CASCADE;
CREATE TABLE agent_approval_record (
    approval_id      SERIAL PRIMARY KEY,
    task_id          INTEGER NOT NULL REFERENCES agent_task(task_id),
    approver_user_id INTEGER NOT NULL REFERENCES sys_user(user_id),
    action           VARCHAR(20) NOT NULL,
    remark           VARCHAR(255),
    create_time      TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_agent_approval_task_id ON agent_approval_record(task_id);
CREATE INDEX idx_agent_approval_user_id ON agent_approval_record(approver_user_id);

-- AI 聊天消息
DROP TABLE IF EXISTS ai_chat_message CASCADE;
CREATE TABLE ai_chat_message (
    id               BIGSERIAL PRIMARY KEY,
    user_id          BIGINT NOT NULL,
    role             VARCHAR(20) NOT NULL,
    content          TEXT NOT NULL,
    provider_name    VARCHAR(100),
    model_name       VARCHAR(100),
    used_system_data BOOLEAN DEFAULT FALSE,
    create_time      TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_ai_chat_user_id ON ai_chat_message(user_id);
CREATE INDEX idx_ai_chat_create_time ON ai_chat_message(create_time);

-- LLM 追踪记录（新增，用于持久化 LLM 调用监控数据）
DROP TABLE IF EXISTS llm_trace CASCADE;
CREATE TABLE llm_trace (
    trace_id       VARCHAR(64) PRIMARY KEY,
    user_id        INTEGER,
    operation_type VARCHAR(20) NOT NULL,
    model_name     VARCHAR(100),
    input_tokens   INTEGER NOT NULL DEFAULT 0,
    output_tokens  INTEGER NOT NULL DEFAULT 0,
    total_tokens   INTEGER NOT NULL DEFAULT 0,
    latency_ms     NUMERIC(12, 2) NOT NULL DEFAULT 0,
    cost_estimate  NUMERIC(12, 6) NOT NULL DEFAULT 0,
    status         VARCHAR(20) NOT NULL DEFAULT 'success',
    tags           JSONB DEFAULT '[]'::JSONB,
    feedback       INTEGER,
    input_preview  TEXT,
    output_preview TEXT,
    create_time    TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_llm_trace_user_id ON llm_trace(user_id);
CREATE INDEX idx_llm_trace_operation_type ON llm_trace(operation_type);
CREATE INDEX idx_llm_trace_status ON llm_trace(status);
CREATE INDEX idx_llm_trace_create_time ON llm_trace(create_time DESC);

COMMENT ON TABLE  llm_trace IS 'LLM 调用追踪持久化表（替代旧版内存 TraceStore）';
COMMENT ON COLUMN llm_trace.tags IS '标签数组（JSONB），如 ["chat","weather"]';
COMMENT ON COLUMN llm_trace.input_preview IS '输入文本前 500 字符（用于详情查看）';

-- RAG 文档元数据
DROP TABLE IF EXISTS rag_chunk CASCADE;
DROP TABLE IF EXISTS rag_document CASCADE;
CREATE TABLE rag_document (
    doc_id         SERIAL PRIMARY KEY,
    filename       VARCHAR(500) NOT NULL,
    file_type      VARCHAR(20) NOT NULL,
    file_size      INTEGER NOT NULL DEFAULT 0,
    chunk_count    INTEGER NOT NULL DEFAULT 0,
    status         VARCHAR(20) NOT NULL DEFAULT 'uploading',
    upload_time    TIMESTAMP NOT NULL DEFAULT NOW(),
    processed_time TIMESTAMP
);
CREATE INDEX idx_rag_document_status ON rag_document(status);

-- RAG 文档分块（含 1536 维向量）
CREATE TABLE rag_chunk (
    chunk_id    SERIAL PRIMARY KEY,
    doc_id      INTEGER NOT NULL REFERENCES rag_document(doc_id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL DEFAULT 0,
    content     TEXT NOT NULL,
    embedding   vector(1536),
    token_count INTEGER NOT NULL DEFAULT 0,
    create_time TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_rag_chunk_doc_id ON rag_chunk(doc_id);
CREATE INDEX idx_rag_chunk_embedding
    ON rag_chunk USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);


-- ============================================================
-- 4. 种子数据
-- ============================================================

-- 部门
INSERT INTO department (dept_id, dept_name, dept_desc, parent_id, create_time, update_time) VALUES
(1, '总经办', '公司最高管理层', NULL, '2024-01-01 09:00:00', '2024-01-01 09:00:00'),
(2, '人力资源部', '负责人力资源管理', 1, '2024-01-01 09:00:00', '2024-01-01 09:00:00'),
(3, '财务部', '负责财务管理', 1, '2024-01-01 09:00:00', '2024-01-01 09:00:00'),
(4, '技术部', '负责技术研发', 1, '2024-01-01 09:00:00', '2024-01-01 09:00:00'),
(5, '市场部', '负责市场运营', 1, '2024-01-01 09:00:00', '2024-01-01 09:00:00'),
(6, '行政部', '负责行政事务', 1, '2024-01-01 09:00:00', '2024-01-01 09:00:00'),
(7, '综合部', '负责后勤与综合事务', 1, '2024-01-01 09:00:00', '2024-01-01 09:00:00');
SELECT setval('department_dept_id_seq', 8);

-- 身份标签
INSERT INTO identity_tag (tag_code, tag_name, tag_desc) VALUES
('ADMIN', '管理员', '系统管理员身份标签'),
('EMPLOYEE', '普通员工', '普通员工身份标签'),
('FINANCE_MANAGER', '财务经理', '财务经理身份标签'),
('FINANCE_SPECIALIST', '财务专员', '财务专员身份标签'),
('GENERAL_MANAGER', '总经理', '总经理身份标签'),
('HR_MANAGER', 'HR经理', '人力资源经理身份标签'),
('HR_SPECIALIST', 'HR专员', '人力资源专员身份标签'),
('MANAGER', '部门经理', '普通业务部门经理身份标签');

-- 职位
INSERT INTO job_position (position_id, position_name, position_desc, dept_id) VALUES
(1, '总经理', '公司总负责人', 1),
(2, 'HR经理', '人力资源部负责人', 2),
(3, 'HR专员', '人力资源专员', 2),
(4, '财务经理', '财务部负责人', 3),
(5, '财务专员', '财务日常处理', 3),
(6, '技术总监', '技术部负责人', 4),
(7, '高级工程师', '技术骨干岗位', 4),
(8, '软件工程师', '技术研发岗位', 4),
(9, '市场经理', '市场部负责人', 5),
(10, '市场专员', '市场运营岗位', 5),
(11, '行政经理', '行政部负责人', 6),
(12, '行政专员', '行政事务岗位', 6),
(13, '综合部经理', '综合部负责人', 7),
(14, '后勤专员', '后勤与宿舍管理', 7),
(15, '管理员', '负责公司系统管理', 1);
SELECT setval('job_position_position_id_seq', 16);

-- 员工
INSERT INTO employee (emp_id, emp_name, gender, phone, email, id_card, birthday, address, hire_date, dept_id, position_id, identity_tag_code, status, create_time, update_time) VALUES
(1, '张伟', '男', '13800000001', 'zhangwei@company.com', '110101199001010011', '1990-01-01', '北京市海淀区', '2020-01-15', 1, 1, 'GENERAL_MANAGER', '在职', '2024-01-01 09:00:00', '2024-01-01 09:00:00'),
(2, '李娜', '女', '13800000002', 'lina@company.com', '110101199203120022', '1992-03-12', '北京市朝阳区', '2020-03-01', 2, 3, 'HR_SPECIALIST', '在职', '2024-01-01 09:00:00', '2024-01-01 09:00:00'),
(3, '王芳', '女', '13800000003', 'wangfang@company.com', '110101199508080033', '1995-08-08', '北京市丰台区', '2021-06-15', 2, 3, 'HR_SPECIALIST', '在职', '2024-01-01 09:00:00', '2024-01-01 09:00:00'),
(4, '刘强', '男', '13800000004', 'liuqiang@company.com', '110101198909210044', '1989-09-21', '北京市西城区', '2020-05-20', 3, 4, 'FINANCE_MANAGER', '在职', '2024-01-01 09:00:00', '2024-01-01 09:00:00'),
(5, '陈静', '女', '13800000005', 'chenjing@company.com', '110101199704150055', '1997-04-15', '北京市通州区', '2022-01-10', 3, 5, 'FINANCE_SPECIALIST', '在职', '2024-01-01 09:00:00', '2024-01-01 09:00:00'),
(6, '赵明', '男', '13800000006', 'zhaoming@company.com', '110101198811180066', '1988-11-18', '北京市昌平区', '2019-08-01', 4, 6, 'MANAGER', '在职', '2024-01-01 09:00:00', '2024-01-01 09:00:00'),
(7, '孙磊', '男', '13800000007', 'sunlei@company.com', '110101199402140077', '1994-02-14', '北京市顺义区', '2021-03-15', 4, 7, 'EMPLOYEE', '在职', '2024-01-01 09:00:00', '2024-01-01 09:00:00'),
(8, '周洋', '男', '13800000008', 'zhouyang@company.com', '110101199909090088', '1999-09-09', '北京市大兴区', '2022-07-01', 4, 8, 'EMPLOYEE', '试用', '2024-01-01 09:00:00', '2024-01-01 09:00:00'),
(9, '吴敏', '女', '13800000009', 'wumin@company.com', '110101199105260099', '1991-05-26', '北京市石景山区', '2020-11-01', 5, 9, 'MANAGER', '在职', '2024-01-01 09:00:00', '2024-01-01 09:00:00'),
(10, '郑涛', '男', '13800000010', 'zhengtao@company.com', '110101199612300010', '1996-12-30', '北京市房山区', '2023-02-15', 5, 10, 'EMPLOYEE', '在职', '2024-01-01 09:00:00', '2024-01-01 09:00:00'),
(11, '黄丽', '女', '13800000011', 'huangli@company.com', '110101199303030011', '1993-03-03', '北京市门头沟区', '2021-09-01', 6, 11, 'MANAGER', '在职', '2024-01-01 09:00:00', '2024-01-01 09:00:00'),
(12, '林峰', '男', '13800000012', 'linfeng@company.com', '110101199807170012', '1998-07-17', '北京市延庆区', '2023-05-01', 6, 12, 'EMPLOYEE', '在职', '2024-01-01 09:00:00', '2024-01-01 09:00:00'),
(13, '何军', '男', '13800000013', 'hejun@company.com', '110101199211110013', '1992-11-11', '北京市密云区', '2021-11-01', 7, 13, 'MANAGER', '在职', '2024-01-01 09:00:00', '2024-01-01 09:00:00'),
(14, '许洁', '女', '13800000014', 'xujie@company.com', '110101199606060014', '1996-06-06', '北京市怀柔区', '2022-10-18', 7, 14, 'EMPLOYEE', '在职', '2024-01-01 09:00:00', '2024-01-01 09:00:00'),
(15, '郭婷', '女', '13800000015', 'guoting@company.com', '110101199410100015', '1994-10-10', '北京市东城区', '2019-12-20', 2, 2, 'HR_MANAGER', '在职', '2024-01-01 09:00:00', '2024-01-01 09:00:00'),
(16, '云月', '男', '13800000000', 'yunyue@company.com', NULL, NULL, NULL, '2020-01-01', 1, 15, 'ADMIN', '在职', '2026-03-14 00:20:43', '2026-03-14 00:25:46');
SELECT setval('employee_emp_id_seq', 17);

-- 角色
INSERT INTO role (role_id, role_name, role_code, role_desc, create_time) VALUES
(1, '系统管理员', 'ADMIN', '拥有系统全部权限', '2024-01-01 09:00:00'),
(2, 'HR专员', 'HR', '负责人事基础信息与请假处理', '2024-01-01 09:00:00'),
(3, '部门经理', 'MANAGER', '管理本部门员工与审批', '2024-01-01 09:00:00'),
(4, '普通员工', 'EMPLOYEE', '普通员工自助权限', '2024-01-01 09:00:00'),
(5, '财务经理', 'FINANCE_MANAGER', '负责薪资审批与发放', '2024-01-01 09:00:00'),
(6, '财务专员', 'FINANCE', '负责薪资制单与配置提交', '2024-01-01 09:00:00'),
(7, 'HR经理', 'HR_MANAGER', '负责人事审批与管理', '2024-01-01 09:00:00'),
(8, '总经理', 'GENERAL_MANAGER', '公司负责人', '2026-03-14 00:14:01');
SELECT setval('role_role_id_seq', 9);

-- 用户（密码全部为 123456，云月密码为 yunyue）
INSERT INTO sys_user (user_id, emp_id, username, password, role_id, status, create_time, update_time) VALUES
(1, 1, 'gm', '123456', 8, '启用', '2024-01-01 09:00:00', '2026-03-14 00:21:56'),
(2, 2, 'hr_lina', '123456', 2, '启用', '2024-01-01 09:00:00', '2026-04-10 19:18:40'),
(3, 6, 'manager_zhao', '123456', 3, '启用', '2024-01-01 09:00:00', '2024-01-01 09:00:00'),
(4, 8, 'emp_zhou', '123456', 4, '启用', '2024-01-01 09:00:00', '2024-01-01 09:00:00'),
(5, 4, 'finance_liu', '123456', 5, '启用', '2024-01-01 09:00:00', '2024-01-01 09:00:00'),
(6, 5, 'finance_chen', '123456', 6, '启用', '2024-01-01 09:00:00', '2026-04-10 19:59:56'),
(7, 15, 'hr_manager', '123456', 7, '启用', '2024-01-01 09:00:00', '2024-01-01 09:00:00'),
(8, 9, 'emp_wu', '123456', 4, '启用', '2024-01-01 09:00:00', '2026-04-10 19:16:30'),
(9, 16, 'yunyue', 'yunyue', 1, '启用', '2026-03-14 00:22:55', '2026-05-18 15:00:08');
SELECT setval('sys_user_user_id_seq', 10);

-- 权限
INSERT INTO permission (perm_id, perm_name, perm_code, perm_type, parent_id, path, icon, sort_order) VALUES
(1, '仪表盘', 'dashboard', 'MENU', NULL, '/dashboard', 'DataLine', 1),
(2, '仪表盘查看', 'dashboard:view', 'BUTTON', 1, NULL, NULL, 1),
(3, '基础信息', 'base', 'MENU', NULL, '/base', 'Menu', 2),
(4, '员工管理', 'base:employee', 'MENU', 3, '/base/employee', 'User', 1),
(5, '部门管理', 'base:department', 'MENU', 3, '/base/department', 'OfficeBuilding', 2),
(6, '职位管理', 'base:position', 'MENU', 3, '/base/position', 'Suitcase', 3),
(7, '员工查看', 'base:employee:view', 'BUTTON', 4, NULL, NULL, 1),
(8, '部门查看', 'base:department:view', 'BUTTON', 5, NULL, NULL, 1),
(9, '职位查看', 'base:position:view', 'BUTTON', 6, NULL, NULL, 1),
(10, '员工新增', 'base:employee:add', 'BUTTON', 4, NULL, NULL, 2),
(11, '员工编辑', 'base:employee:edit', 'BUTTON', 4, NULL, NULL, 3),
(12, '员工删除', 'base:employee:delete', 'BUTTON', 4, NULL, NULL, 4),
(13, '部门新增', 'base:department:add', 'BUTTON', 5, NULL, NULL, 2),
(14, '部门编辑', 'base:department:edit', 'BUTTON', 5, NULL, NULL, 3),
(15, '部门删除', 'base:department:delete', 'BUTTON', 5, NULL, NULL, 4),
(16, '职位新增', 'base:position:add', 'BUTTON', 6, NULL, NULL, 2),
(17, '职位编辑', 'base:position:edit', 'BUTTON', 6, NULL, NULL, 3),
(18, '职位删除', 'base:position:delete', 'BUTTON', 6, NULL, NULL, 4),
(19, '考勤管理', 'attendance', 'MENU', NULL, '/attendance', 'Calendar', 3),
(20, '考勤记录', 'attendance:record', 'MENU', 19, '/attendance/record', 'Calendar', 1),
(21, '请假管理', 'attendance:leave', 'MENU', 19, '/attendance/leave', 'Document', 2),
(22, '考勤查看', 'attendance:record:view', 'BUTTON', 20, NULL, NULL, 1),
(23, '请假查看', 'attendance:leave:view', 'BUTTON', 21, NULL, NULL, 1),
(24, '考勤新增', 'attendance:record:add', 'BUTTON', 20, NULL, NULL, 2),
(25, '考勤编辑', 'attendance:record:edit', 'BUTTON', 20, NULL, NULL, 3),
(26, '请假申请', 'attendance:leave:add', 'BUTTON', 21, NULL, NULL, 2),
(27, '请假审批', 'attendance:leave:approve', 'BUTTON', 21, NULL, NULL, 3),
(28, '请假撤销', 'attendance:leave:cancel', 'BUTTON', 21, NULL, NULL, 4),
(29, '薪资管理', 'salary', 'MENU', NULL, '/salary', 'Money', 4),
(30, '薪资记录', 'salary:record', 'MENU', 29, '/salary/record', 'List', 1),
(31, '薪资配置', 'salary:config', 'MENU', 29, '/salary/config', 'Tools', 2),
(32, '薪资记录查看', 'salary:record:view', 'BUTTON', 30, NULL, NULL, 1),
(33, '薪资配置查看', 'salary:config:view', 'BUTTON', 31, NULL, NULL, 1),
(34, '薪资记录新增', 'salary:record:add', 'BUTTON', 30, NULL, NULL, 2),
(35, '薪资记录编辑', 'salary:record:edit', 'BUTTON', 30, NULL, NULL, 3),
(36, '薪资记录提交', 'salary:record:submit', 'BUTTON', 30, NULL, NULL, 4),
(37, '薪资记录审批', 'salary:record:approve', 'BUTTON', 30, NULL, NULL, 5),
(38, '薪资记录发放', 'salary:record:pay', 'BUTTON', 30, NULL, NULL, 6),
(39, '薪资配置新增', 'salary:config:add', 'BUTTON', 31, NULL, NULL, 2),
(40, '薪资配置编辑', 'salary:config:edit', 'BUTTON', 31, NULL, NULL, 3),
(41, '薪资配置提交', 'salary:config:submit', 'BUTTON', 31, NULL, NULL, 4),
(42, '薪资配置审批', 'salary:config:approve', 'BUTTON', 31, NULL, NULL, 5),
(43, '权限管理', 'permission', 'MENU', NULL, '/permission', 'Lock', 5),
(44, '用户管理', 'permission:user', 'MENU', 43, '/permission/user', 'UserFilled', 1),
(45, '角色管理', 'permission:role', 'MENU', 43, '/permission/role', 'Avatar', 2),
(46, '用户查看', 'permission:user:view', 'BUTTON', 44, NULL, NULL, 1),
(47, '角色查看', 'permission:role:view', 'BUTTON', 45, NULL, NULL, 1),
(48, '部门模板查看', 'permission:dept-template:view', 'BUTTON', 43, NULL, NULL, 3),
(49, '身份标签查看', 'permission:identity:view', 'BUTTON', 43, NULL, NULL, 4),
(50, '模块范围查看', 'permission:module-scope:view', 'BUTTON', 43, NULL, NULL, 5),
(51, '审批规则查看', 'permission:approval-rule:view', 'BUTTON', 43, NULL, NULL, 6),
(52, '用户新增', 'permission:user:add', 'BUTTON', 44, NULL, NULL, 2),
(53, '用户编辑', 'permission:user:edit', 'BUTTON', 44, NULL, NULL, 3),
(54, '用户删除', 'permission:user:delete', 'BUTTON', 44, NULL, NULL, 4),
(55, '角色新增', 'permission:role:add', 'BUTTON', 45, NULL, NULL, 2),
(56, '角色编辑', 'permission:role:edit', 'BUTTON', 45, NULL, NULL, 3),
(57, '角色删除', 'permission:role:delete', 'BUTTON', 45, NULL, NULL, 4),
(58, '角色授权', 'permission:role:perm', 'BUTTON', 45, NULL, NULL, 5),
(59, '报表中心', 'report', 'MENU', NULL, '/report', 'PieChart', 6),
(60, '报表查看', 'report:view', 'BUTTON', 59, NULL, NULL, 1),
(61, '亚托莉', 'dashboard:ai', 'MENU', 1, '/ai-assistant', 'ChatDotRound', 2),
(62, '亚托莉查看', 'dashboard:ai:view', 'BUTTON', 61, NULL, NULL, 1);
SELECT setval('permission_perm_id_seq', 65);

-- 模块范围规则
INSERT INTO module_scope_rule (module_code, module_name, default_scope) VALUES
('attendance:leave', '请假管理', 'dept'),
('attendance:record', '考勤记录', 'dept'),
('base:department', '部门管理', 'dept'),
('base:employee', '员工管理', 'dept'),
('base:position', '职位管理', 'dept'),
('report', '报表中心', 'dept'),
('salary:config', '薪资配置', 'company'),
('salary:record', '薪资记录', 'dept');

-- 模块范围细则
INSERT INTO module_scope_detail (id, module_code, tag_code, scope) VALUES
(1, 'base:employee', 'ADMIN', 'company'),
(2, 'base:employee', 'HR_SPECIALIST', 'company'),
(3, 'base:employee', 'HR_MANAGER', 'company'),
(4, 'base:employee', 'FINANCE_SPECIALIST', 'dept'),
(5, 'base:employee', 'FINANCE_MANAGER', 'dept'),
(6, 'base:employee', 'MANAGER', 'dept'),
(7, 'base:employee', 'EMPLOYEE', 'self'),
(8, 'base:department', 'ADMIN', 'company'),
(9, 'base:department', 'HR_SPECIALIST', 'company'),
(10, 'base:department', 'HR_MANAGER', 'company'),
(11, 'base:department', 'FINANCE_SPECIALIST', 'dept'),
(12, 'base:department', 'FINANCE_MANAGER', 'dept'),
(13, 'base:department', 'MANAGER', 'dept'),
(14, 'base:department', 'EMPLOYEE', 'dept'),
(15, 'base:position', 'ADMIN', 'company'),
(16, 'base:position', 'HR_SPECIALIST', 'company'),
(17, 'base:position', 'HR_MANAGER', 'company'),
(18, 'base:position', 'FINANCE_SPECIALIST', 'dept'),
(19, 'base:position', 'FINANCE_MANAGER', 'dept'),
(20, 'base:position', 'MANAGER', 'dept'),
(21, 'base:position', 'EMPLOYEE', 'dept'),
(22, 'attendance:record', 'ADMIN', 'company'),
(23, 'attendance:record', 'HR_SPECIALIST', 'company'),
(24, 'attendance:record', 'HR_MANAGER', 'company'),
(25, 'attendance:record', 'MANAGER', 'dept'),
(26, 'attendance:record', 'EMPLOYEE', 'self'),
(27, 'attendance:leave', 'ADMIN', 'company'),
(28, 'attendance:leave', 'HR_SPECIALIST', 'company'),
(29, 'attendance:leave', 'HR_MANAGER', 'company'),
(30, 'attendance:leave', 'MANAGER', 'dept'),
(31, 'attendance:leave', 'EMPLOYEE', 'self'),
(32, 'salary:record', 'ADMIN', 'company'),
(33, 'salary:record', 'FINANCE_SPECIALIST', 'company'),
(34, 'salary:record', 'FINANCE_MANAGER', 'company'),
(35, 'salary:config', 'ADMIN', 'company'),
(36, 'salary:config', 'FINANCE_SPECIALIST', 'company'),
(37, 'salary:config', 'FINANCE_MANAGER', 'company'),
(38, 'report', 'ADMIN', 'company'),
(39, 'report', 'HR_SPECIALIST', 'company'),
(40, 'report', 'HR_MANAGER', 'company'),
(41, 'report', 'FINANCE_SPECIALIST', 'company'),
(42, 'report', 'FINANCE_MANAGER', 'company'),
(43, 'report', 'MANAGER', 'dept'),
(44, 'report', 'EMPLOYEE', 'self');
SELECT setval('module_scope_detail_id_seq', 45);

-- 部门权限模板
INSERT INTO dept_permission_template (id, dept_id, module_code) VALUES
(1, 2, 'base:employee'), (2, 2, 'base:department'), (3, 2, 'base:position'),
(4, 2, 'attendance:record'), (5, 2, 'attendance:leave'), (6, 2, 'report'),
(7, 3, 'salary:record'), (8, 3, 'salary:config'), (9, 3, 'report'),
(10, 4, 'attendance:record'), (11, 4, 'base:employee'),
(12, 1, 'attendance:leave'), (13, 1, 'salary:config'), (14, 1, 'base:employee'),
(15, 1, 'salary:record'), (16, 1, 'base:position'), (17, 1, 'attendance:record'),
(18, 1, 'base:department'), (19, 1, 'report');
SELECT setval('dept_permission_template_id_seq', 20);

-- 审批规则类型
INSERT INTO approval_rule_type (type_code, type_name, type_desc, status) VALUES
('leave', '请假审批规则', '请假申请的审批流转规则', '启用'),
('salary_config', '薪资配置审批规则', '薪资配置提交与审批流程', '启用'),
('salary_record', '薪资记录审批规则', '薪资记录提交与审批流程', '启用');

-- 审批规则
INSERT INTO approval_rule (rule_id, type_code, applicant_tag, days_op, days_value, first_approver_tag, second_approver_tag, second_approver_scope, sort_order) VALUES
(1, 'leave', 'ADMIN', 'any', 0, 'GENERAL_MANAGER', NULL, NULL, 0),
(2, 'leave', 'FINANCE_SPECIALIST', '<=', 3, 'HR_SPECIALIST', NULL, NULL, 1),
(3, 'leave', 'FINANCE_SPECIALIST', '>', 3, 'HR_SPECIALIST', 'HR_MANAGER', 'company', 2),
(4, 'leave', 'HR_SPECIALIST', 'any', 0, 'HR_MANAGER', NULL, NULL, 3),
(5, 'leave', 'EMPLOYEE', '<=', 3, 'HR_SPECIALIST', NULL, NULL, 4),
(6, 'leave', 'EMPLOYEE', '>', 3, 'HR_SPECIALIST', 'HR_MANAGER', 'company', 5),
(7, 'leave', 'MANAGER', 'any', 0, 'HR_MANAGER', 'GENERAL_MANAGER', 'company', 6),
(8, 'leave', 'FINANCE_MANAGER', 'any', 0, 'HR_MANAGER', 'GENERAL_MANAGER', 'company', 7),
(9, 'leave', 'HR_MANAGER', 'any', 0, 'GENERAL_MANAGER', NULL, NULL, 8),
(10, 'leave', 'GENERAL_MANAGER', 'any', 0, 'HR_MANAGER', NULL, NULL, 9),
(11, 'salary_record', 'FINANCE_SPECIALIST', 'any', 0, 'FINANCE_MANAGER', NULL, 'company', 1),
(12, 'salary_config', 'FINANCE_SPECIALIST', 'any', 0, 'FINANCE_MANAGER', NULL, 'company', 1);
SELECT setval('approval_rule_rule_id_seq', 13);

-- 角色权限关联（管理员拥有全部权限）
INSERT INTO role_permission (role_id, perm_id)
SELECT 1, perm_id FROM permission;
INSERT INTO role_permission (role_id, perm_id) VALUES
-- HR专员
(2, 1), (2, 2), (2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9),
(2, 10), (2, 11), (2, 12), (2, 13), (2, 14), (2, 15), (2, 16), (2, 17), (2, 18),
(2, 19), (2, 20), (2, 21), (2, 22), (2, 23), (2, 24), (2, 25), (2, 26), (2, 27), (2, 28),
(2, 29), (2, 30), (2, 32), (2, 59), (2, 60), (2, 61), (2, 62),
-- 部门经理
(3, 1), (3, 2), (3, 3), (3, 4), (3, 7), (3, 11),
(3, 19), (3, 20), (3, 21), (3, 22), (3, 23), (3, 27), (3, 28),
(3, 29), (3, 30), (3, 32), (3, 59), (3, 60), (3, 61), (3, 62),
-- 普通员工
(4, 1), (4, 2),
(4, 19), (4, 20), (4, 21), (4, 22), (4, 23), (4, 26), (4, 28),
(4, 29), (4, 30), (4, 32), (4, 61), (4, 62),
-- 财务经理
(5, 1), (5, 2),
(5, 29), (5, 30), (5, 31), (5, 32), (5, 33), (5, 37), (5, 38), (5, 42),
(5, 61), (5, 62),
-- 财务专员
(6, 1), (6, 2),
(6, 29), (6, 30), (6, 31), (6, 32), (6, 33), (6, 34), (6, 35), (6, 36),
(6, 39), (6, 40), (6, 41), (6, 61), (6, 62),
-- HR经理
(7, 1), (7, 2), (7, 3), (7, 4), (7, 5), (7, 6), (7, 7), (7, 8), (7, 9),
(7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (7, 15), (7, 16), (7, 17), (7, 18),
(7, 19), (7, 20), (7, 21), (7, 22), (7, 23), (7, 24), (7, 25), (7, 26), (7, 27), (7, 28),
(7, 29), (7, 30), (7, 32), (7, 59), (7, 60), (7, 61), (7, 62);
SELECT setval('role_permission_id_seq', (SELECT MAX(id)+1 FROM role_permission));

-- 考勤
INSERT INTO attendance (attendance_id, emp_id, attendance_date, clock_in, clock_out, status, remark, create_time) VALUES
(1, 1, '2024-01-15', '08:55:00', '18:05:00', '正常', NULL, '2024-01-15 18:05:00'),
(2, 2, '2024-01-15', '09:10:00', '18:00:00', '迟到', '早会迟到10分钟', '2024-01-15 18:00:00'),
(3, 3, '2024-01-15', '08:50:00', '17:30:00', '早退', '身体不适提前离岗', '2024-01-15 17:30:00'),
(4, 4, '2024-01-15', '08:45:00', '18:10:00', '正常', NULL, '2024-01-15 18:10:00'),
(5, 5, '2024-01-15', NULL, NULL, '请假', '年假中', '2024-01-15 09:00:00'),
(6, 6, '2024-01-15', '08:30:00', '20:00:00', '加班', '项目上线支持', '2024-01-15 20:00:00'),
(7, 7, '2024-01-15', '08:58:00', '18:02:00', '正常', NULL, '2024-01-15 18:02:00'),
(8, 8, '2024-01-15', NULL, NULL, '缺勤', '未打卡且无请假记录', '2024-01-15 18:00:00');
SELECT setval('attendance_attendance_id_seq', 10);

-- 请假
INSERT INTO leave_request (leave_id, emp_id, leave_type, start_date, end_date, days, reason, status, approver_id, apply_time, approve_time, approve_remark) VALUES
(1, 5, '年假', '2024-01-15', '2024-01-17', 3, '回老家探亲', '已通过', 2, '2024-01-10 09:30:00', '2024-01-11 14:00:00', '资料齐全，同意请假'),
(2, 3, '病假', '2024-01-20', '2024-01-21', 2, '感冒发烧需要休息', '待审批', NULL, '2024-01-18 14:20:00', NULL, NULL),
(3, 8, '事假', '2024-01-22', '2024-01-22', 1, '处理个人事务', '已通过', 3, '2024-01-19 10:00:00', '2024-01-19 16:10:00', '先由HR继续处理'),
(4, 10, '婚假', '2024-02-01', '2024-02-10', 10, '办理婚礼', '待审批', NULL, '2024-01-20 16:00:00', NULL, NULL),
(5, 7, '年假', '2024-01-25', '2024-01-26', 2, '个人休假', '已拒绝', 3, '2024-01-15 11:30:00', '2024-01-16 09:30:00', '项目关键期暂不批准'),
(6, 1, '年假', '2024-03-01', '2024-03-03', 3, '总经理请假测试', '待审批', NULL, '2024-02-28 10:00:00', NULL, NULL),
(7, 15, '事假', '2024-03-05', '2024-03-05', 1, 'HR经理请假测试', '待审批', NULL, '2024-03-04 14:00:00', NULL, NULL);
SELECT setval('leave_request_leave_id_seq', 8);

-- 薪资配置
INSERT INTO salary_config (config_id, config_name, config_key, config_value, config_desc, effective_date, status, submit_date, approve_date, create_time, update_time) VALUES
(1, '社保比例', 'social_insurance_rate', '0.105', '员工个人社保扣缴比例', '2024-01-01', '已审批', '2023-12-25', '2023-12-28', '2023-12-25 09:00:00', '2023-12-28 10:00:00'),
(2, '公积金比例', 'housing_fund_rate', '0.08', '员工公积金扣缴比例', '2024-01-01', '已审批', '2023-12-25', '2023-12-28', '2023-12-25 09:00:00', '2023-12-28 10:00:00'),
(3, '个税起征点', 'tax_threshold', '5000', '工资薪金个税起征点', '2024-01-01', '已审批', '2023-12-25', '2023-12-28', '2023-12-25 09:00:00', '2023-12-28 10:00:00'),
(4, '迟到扣款', 'late_deduct', '50', '每次迟到扣款金额', '2024-01-01', '已审批', '2023-12-25', '2023-12-28', '2023-12-25 09:00:00', '2023-12-28 10:00:00');
SELECT setval('salary_config_config_id_seq', 5);

-- 薪资记录
INSERT INTO salary_record (salary_id, emp_id, salary_month, base_salary, position_salary, bonus, overtime_pay, gross_salary, social_insurance, housing_fund, attendance_deduct, tax, other_deduct, net_salary, status, submit_date, approve_date, pay_date, create_time, update_time) VALUES
(1, 1, '2024-01-01', 25000.00, 5000.00, 3000.00, 0.00, 33000.00, 2475.00, 2400.00, 0.00, 2590.00, 0.00, 25535.00, '已发放', '2024-01-20', '2024-01-25', '2024-01-31', '2024-01-20 09:00:00', '2024-01-31 12:00:00'),
(2, 2, '2024-01-01', 15000.00, 3000.00, 1500.00, 0.00, 19500.00, 1575.00, 1440.00, 50.00, 1045.00, 0.00, 15390.00, '已发放', '2024-01-20', '2024-01-25', '2024-01-31', '2024-01-20 09:00:00', '2024-01-31 12:00:00'),
(3, 3, '2024-01-01', 10000.00, 2000.00, 800.00, 0.00, 12800.00, 1050.00, 960.00, 50.00, 434.00, 0.00, 10306.00, '已发放', '2024-01-20', '2024-01-25', '2024-01-31', '2024-01-20 09:00:00', '2024-01-31 12:00:00'),
(4, 6, '2024-01-01', 20000.00, 5000.00, 2000.00, 1500.00, 28500.00, 2100.00, 1920.00, 0.00, 2095.00, 0.00, 22385.00, '已发放', '2024-01-20', '2024-01-25', '2024-01-31', '2024-01-20 09:00:00', '2024-01-31 12:00:00'),
(5, 8, '2024-01-01', 8000.00, 1500.00, 500.00, 0.00, 10000.00, 840.00, 720.00, 200.00, 144.00, 0.00, 8096.00, '待发放', '2024-01-20', NULL, NULL, '2024-01-20 09:00:00', '2024-01-20 09:00:00');
SELECT setval('salary_record_salary_id_seq', 6);

-- 操作日志
INSERT INTO operation_log (log_id, user_id, operation_time, operation_type, operation_module, operation_desc) VALUES
(1, 1, '2024-01-01 09:30:00', '登录', '认证中心', '系统管理员首次登录系统'),
(2, 2, '2024-01-10 09:35:00', '审批', '请假管理', 'HR专员审批了陈静的请假申请'),
(3, 5, '2024-01-25 10:00:00', '审批', '薪资管理', '财务经理审批了2024年1月薪资记录');
SELECT setval('operation_log_log_id_seq', 4);


-- ============================================================
-- 5. 完成提示
-- ============================================================
DO $$
BEGIN
    RAISE NOTICE '====================================';
    RAISE NOTICE 'HRMS PostgreSQL 初始化完成！';
    RAISE NOTICE '业务表 + AI 聊天 + RAG 向量 + LLM 追踪 全部就绪';
    RAISE NOTICE '====================================';
END $$;

SELECT 'HRMS PostgreSQL 初始化完成' AS result,
       (SELECT COUNT(*) FROM employee) AS employees,
       (SELECT COUNT(*) FROM department) AS departments,
       (SELECT COUNT(*) FROM permission) AS permissions,
       (SELECT extversion FROM pg_extension WHERE extname = 'vector') AS pgvector_version;
