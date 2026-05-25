"""
Pydantic Schema 层（schemas/__init__.py）

说明：统一导出所有 Schema 模型，方便其他模块按需导入。

用法：
    from app.schemas import LoginRequest, LoginResponse, UserProfile
    from app.schemas import EmployeeCreate, EmployeeResponse, EmployeeQuery
    from app.schemas import ApiResponse, ok, fail, PageResponse
"""

# 通用响应模型
from app.schemas.common import ApiResponse, PageResponse, ok, fail

# 认证相关
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    UserProfile,
    ChangePasswordRequest,
    ResetPasswordRequest,
    PasswordCheckRequest,
    PasswordStrengthResponse,
    UserView,
)

# 员工相关
from app.schemas.employee import (
    EmployeeCreate,
    EmployeeUpdate,
    EmployeeResponse,
    EmployeeQuery,
)

# 部门相关
from app.schemas.department import (
    DepartmentCreate,
    DepartmentUpdate,
    DepartmentResponse,
)

# 考勤相关
from app.schemas.attendance import (
    AttendanceCreate,
    AttendanceUpdate,
    AttendanceResponse,
    AttendanceQuery,
)

# 请假相关
from app.schemas.leave_request import (
    LeaveRequestCreate,
    LeaveApprovalAction,
    LeaveRequestResponse,
    LeaveRequestQuery,
)

# 薪资相关
from app.schemas.salary import (
    SalaryConfigCreate,
    SalaryConfigUpdate,
    SalaryConfigResponse,
    SalaryRecordCreate,
    SalaryRecordUpdate,
    SalaryRecordResponse,
    SalaryRecordQuery,
)

# 权限与角色相关
from app.schemas.permission import (
    RoleCreate,
    RoleUpdate,
    RoleResponse,
    PermissionResponse,
    RolePermissionUpdateRequest,
    DepartmentStat,
    ReportSummary,
)

# AI 聊天相关
from app.schemas.ai_chat import (
    ChatRequest,
    ChatMessageResponse,
    ChatHistoryQuery,
)

# Agent 相关
from app.schemas.agent import (
    IntentType,
    RiskLevel,
    MessageCategory,
    PlanRequest,
    ApproveRequest,
    DraftPlan,
    AgentPlanStep,
    AgentPlanEntity,
    AgentPlan,
    AgentTaskView,
)

# NLP 相关
from app.schemas.nlp import (
    TextAnalyzeRequest,
    TextAnalyzeResponse,
    EntityItem,
    SentimentResult,
    KeywordItem,
    KeywordExtractRequest,
    KeywordExtractResponse,
    SentimentAnalyzeRequest,
    SentimentAnalyzeResponse,
)

__all__ = [
    # 通用
    "ApiResponse",
    "PageResponse",
    "ok",
    "fail",
    # 认证
    "LoginRequest",
    "LoginResponse",
    "UserProfile",
    "ChangePasswordRequest",
    "ResetPasswordRequest",
    "PasswordCheckRequest",
    "PasswordStrengthResponse",
    "UserView",
    # 员工
    "EmployeeCreate",
    "EmployeeUpdate",
    "EmployeeResponse",
    "EmployeeQuery",
    # 部门
    "DepartmentCreate",
    "DepartmentUpdate",
    "DepartmentResponse",
    # 考勤
    "AttendanceCreate",
    "AttendanceUpdate",
    "AttendanceResponse",
    "AttendanceQuery",
    # 请假
    "LeaveRequestCreate",
    "LeaveApprovalAction",
    "LeaveRequestResponse",
    "LeaveRequestQuery",
    # 薪资
    "SalaryConfigCreate",
    "SalaryConfigUpdate",
    "SalaryConfigResponse",
    "SalaryRecordCreate",
    "SalaryRecordUpdate",
    "SalaryRecordResponse",
    "SalaryRecordQuery",
    # 权限与角色
    "RoleCreate",
    "RoleUpdate",
    "RoleResponse",
    "PermissionResponse",
    "RolePermissionUpdateRequest",
    "DepartmentStat",
    "ReportSummary",
    # AI 聊天
    "ChatRequest",
    "ChatMessageResponse",
    "ChatHistoryQuery",
    # Agent
    "IntentType",
    "RiskLevel",
    "MessageCategory",
    "PlanRequest",
    "ApproveRequest",
    "DraftPlan",
    "AgentPlanStep",
    "AgentPlanEntity",
    "AgentPlan",
    "AgentTaskView",
    # NLP
    "TextAnalyzeRequest",
    "TextAnalyzeResponse",
    "EntityItem",
    "SentimentResult",
    "KeywordItem",
    "KeywordExtractRequest",
    "KeywordExtractResponse",
    "SentimentAnalyzeRequest",
    "SentimentAnalyzeResponse",
]
