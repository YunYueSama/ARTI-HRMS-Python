"""
Pydantic Schema 层（schemas/__init__.py）

说明：统一导出所有 Schema 模型，方便其他模块按需导入。

用法：
    from app.schemas import LoginRequest, LoginResponse, UserProfile
    from app.schemas import EmployeeCreate, EmployeeResponse, EmployeeQuery
    from app.schemas import ApiResponse, ok, fail, PageResponse
"""

# 通用响应模型
# Agent 相关
from app.schemas.agent import (
    AgentPlan,
    AgentPlanEntity,
    AgentPlanStep,
    AgentTaskView,
    ApproveRequest,
    DraftPlan,
    IntentType,
    MessageCategory,
    PlanRequest,
    RiskLevel,
)

# AI 聊天相关
from app.schemas.ai_chat import (
    ChatHistoryQuery,
    ChatMessageResponse,
    ChatRequest,
)

# 考勤相关
from app.schemas.attendance import (
    AttendanceCreate,
    AttendanceQuery,
    AttendanceResponse,
    AttendanceUpdate,
)

# 认证相关
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    PasswordCheckRequest,
    PasswordStrengthResponse,
    ResetPasswordRequest,
    UserProfile,
    UserView,
)
from app.schemas.common import ApiResponse, PageResponse, fail, ok

# 部门相关
from app.schemas.department import (
    DepartmentCreate,
    DepartmentResponse,
    DepartmentUpdate,
)

# 员工相关
from app.schemas.employee import (
    EmployeeCreate,
    EmployeeQuery,
    EmployeeResponse,
    EmployeeUpdate,
)

# 请假相关
from app.schemas.leave_request import (
    LeaveApprovalAction,
    LeaveRequestCreate,
    LeaveRequestQuery,
    LeaveRequestResponse,
)

# NLP 相关
from app.schemas.nlp import (
    EntityItem,
    KeywordExtractRequest,
    KeywordExtractResponse,
    KeywordItem,
    SentimentAnalyzeRequest,
    SentimentAnalyzeResponse,
    SentimentResult,
    TextAnalyzeRequest,
    TextAnalyzeResponse,
)

# 权限与角色相关
from app.schemas.permission import (
    DepartmentStat,
    PermissionResponse,
    ReportSummary,
    RoleCreate,
    RolePermissionUpdateRequest,
    RoleResponse,
    RoleUpdate,
)

# 薪资相关
from app.schemas.salary import (
    SalaryConfigCreate,
    SalaryConfigResponse,
    SalaryConfigUpdate,
    SalaryRecordCreate,
    SalaryRecordQuery,
    SalaryRecordResponse,
    SalaryRecordUpdate,
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
