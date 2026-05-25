"""
通用响应模型（schemas/common.py）

说明：定义标准化的 API 响应格式，保持与现有 Java 后端的 ApiResponse 格式一致。
     所有 API 端点都使用这些模型包装返回数据，确保前端解析逻辑无需修改。

Java 对应关系：
    ApiResponse<T>  → ApiResponse[T]（泛型响应信封）
    PageResponse<T> → PageResponse[T]（分页响应）

用法：
    from app.schemas.common import ApiResponse, PageResponse

    @router.get("/employees")
    async def list_employees() -> ApiResponse[list[EmployeeVO]]:
        return ApiResponse.success(data=employees, message="查询成功")
"""

from pydantic import BaseModel, Field
from typing import Generic, TypeVar, Optional, List

# 泛型类型变量，用于响应数据的类型参数化
T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """
    标准 API 响应信封模型

    说明：所有 API 返回值都包装在此模型中，提供统一的响应格式。
         前端通过 success 字段判断请求是否成功，通过 message 获取提示信息。

    字段：
        success: 请求是否成功（True/False）
        message: 提示信息（成功时为 "ok"，失败时为错误描述）
        data: 响应数据（泛型，可以是任意类型）

    对应 Java 的 ApiResponse<T>：
        - success 对应 Java 的 success 字段
        - message 对应 Java 的 message 字段
        - data 对应 Java 的 data 字段
    """
    success: bool = Field(description="请求是否成功")
    message: str = Field(default="ok", description="提示信息")
    data: Optional[T] = Field(default=None, description="响应数据")


def ok(data=None, message: str = "ok") -> ApiResponse:
    """
    创建成功响应（工厂函数）

    参数：
        data: 响应数据
        message: 成功提示信息，默认 "ok"

    示例：
        from app.schemas.common import ok
        return ok(data=employee, message="创建成功")
    """
    return ApiResponse(success=True, message=message, data=data)


def fail(message: str, data=None) -> ApiResponse:
    """
    创建错误响应（工厂函数）

    参数：
        message: 错误描述信息
        data: 可选的错误详情数据

    示例：
        from app.schemas.common import fail
        return fail(message="用户不存在")
    """
    return ApiResponse(success=False, message=message, data=data)


class PageResponse(BaseModel, Generic[T]):
    """
    分页响应模型

    说明：用于列表查询的分页返回，包含数据列表和分页元信息。
         前端根据 total 和 size 计算总页数，实现分页导航。

    字段：
        items: 当前页数据列表
        total: 总记录数
        page: 当前页码（从 1 开始）
        size: 每页大小

    对应 Java 的 PageResponse<T>：
        - items 对应 Java 的 content 字段
        - total 对应 Java 的 total 字段
    """
    items: List[T] = Field(description="当前页数据列表")
    total: int = Field(description="总记录数")
    page: int = Field(ge=1, description="当前页码（从 1 开始）")
    size: int = Field(ge=1, description="每页大小")

    @property
    def total_pages(self) -> int:
        """计算总页数"""
        return (self.total + self.size - 1) // self.size if self.size > 0 else 0
