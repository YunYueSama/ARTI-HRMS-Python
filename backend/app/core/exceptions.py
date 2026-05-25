"""
自定义异常和全局异常处理器（core/exceptions.py）

说明：定义业务异常类和全局异常处理器，确保所有错误都返回统一的 JSON 格式。
     类似 Spring 的 @ControllerAdvice + @ExceptionHandler 机制。

异常映射关系：
    NotFoundException       → HTTP 404（资源不存在）
    PermissionDeniedException → HTTP 403（权限不足）
    BusinessException       → HTTP 400（业务逻辑错误）
    ValidationError         → HTTP 422（请求参数校验失败）
    Exception（未处理）     → HTTP 500（服务器内部错误）

用法：
    from app.core.exceptions import NotFoundException, BusinessException

    # 在 Service 层抛出业务异常
    if not employee:
        raise NotFoundException(message="员工不存在", detail=f"emp_id={emp_id}")

    # 全局异常处理器会自动捕获并返回标准化 JSON 响应
"""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

logger = logging.getLogger(__name__)


# ============================================================
# 自定义异常类
# ============================================================


class NotFoundException(Exception):
    """
    资源不存在异常（HTTP 404）

    说明：当请求的资源（员工、部门、任务等）在数据库中不存在时抛出。
         对应 Java 的 NotFoundException。

    示例：
        raise NotFoundException(message="员工不存在")
    """

    def __init__(self, message: str = "资源不存在", detail: str | None = None):
        self.message = message
        self.detail = detail  # 可选的详细信息（如 ID 值）
        super().__init__(self.message)


class PermissionDeniedException(Exception):
    """
    权限不足异常（HTTP 403）

    说明：当用户尝试访问无权限的资源或执行无权限的操作时抛出。
         对应 Spring Security 的 AccessDeniedException。

    示例：
        raise PermissionDeniedException(message="无权修改该部门数据")
    """

    def __init__(self, message: str = "权限不足", detail: str | None = None):
        self.message = message
        self.detail = detail
        super().__init__(self.message)


class BusinessException(Exception):
    """
    业务逻辑异常（HTTP 400）

    说明：当业务规则校验失败时抛出（如重复提交、状态流转不合法等）。
         这是一个通用的业务错误，不属于 404 或 403 的情况。

    示例：
        raise BusinessException(message="请假天数不能超过年假余额")
        raise BusinessException(message="薪资记录已审批，不可修改")
    """

    def __init__(self, message: str = "业务处理失败", detail: str | None = None):
        self.message = message
        self.detail = detail
        super().__init__(self.message)


class UnauthorizedException(Exception):
    """
    未认证异常（HTTP 401）

    说明：当用户未提供有效的认证凭据（JWT Token 缺失、过期或无效）时抛出。

    示例：
        raise UnauthorizedException(message="Token 已过期，请重新登录")
    """

    def __init__(self, message: str = "未认证，请先登录", detail: str | None = None):
        self.message = message
        self.detail = detail
        super().__init__(self.message)


# ============================================================
# 全局异常处理器注册函数
#
# 说明：将所有异常处理器注册到 FastAPI 应用实例。
#      类似 Spring 的 @ControllerAdvice，统一处理所有未捕获的异常。
#      确保任何情况下都返回标准化的 JSON 响应，前端可统一解析。
# ============================================================


def register_exception_handlers(app: FastAPI) -> None:
    """
    注册全局异常处理器到 FastAPI 应用

    参数：
        app: FastAPI 应用实例

    说明：
        每种异常类型对应一个处理器，返回对应的 HTTP 状态码和标准化 JSON 响应。
        处理器按照异常类型的具体程度排列（具体异常优先匹配）。
    """

    @app.exception_handler(NotFoundException)
    async def not_found_handler(request: Request, exc: NotFoundException) -> JSONResponse:
        """处理资源不存在异常 → 404"""
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "message": exc.message,
                "data": exc.detail,
            },
        )

    @app.exception_handler(UnauthorizedException)
    async def unauthorized_handler(request: Request, exc: UnauthorizedException) -> JSONResponse:
        """处理未认证异常 → 401"""
        return JSONResponse(
            status_code=401,
            content={
                "success": False,
                "message": exc.message,
                "data": exc.detail,
            },
        )

    @app.exception_handler(PermissionDeniedException)
    async def permission_denied_handler(request: Request, exc: PermissionDeniedException) -> JSONResponse:
        """处理权限不足异常 → 403"""
        return JSONResponse(
            status_code=403,
            content={
                "success": False,
                "message": exc.message,
                "data": exc.detail,
            },
        )

    @app.exception_handler(BusinessException)
    async def business_exception_handler(request: Request, exc: BusinessException) -> JSONResponse:
        """处理业务逻辑异常 → 400"""
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": exc.message,
                "data": exc.detail,
            },
        )

    @app.exception_handler(ValidationError)
    async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
        """
        处理 Pydantic 校验错误 → 422

        说明：当请求体不符合 Pydantic Schema 定义的约束时触发。
             返回详细的字段校验错误信息，帮助前端定位问题。
        """
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "message": "请求参数校验失败",
                "data": exc.errors(),  # Pydantic 提供的详细错误列表
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """
        处理所有未捕获的异常 → 500

        说明：兜底处理器，捕获所有未被上面处理器匹配的异常。
             记录错误日志用于排查，但不向前端暴露内部错误详情（安全考虑）。
        """
        # 记录详细错误信息到日志（包含堆栈跟踪）
        logger.error(f"未处理异常: {type(exc).__name__}: {exc}", exc_info=True)

        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "服务器内部错误，请稍后重试",
                "data": None,
            },
        )
