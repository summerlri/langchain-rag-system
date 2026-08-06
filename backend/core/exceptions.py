"""
全局异常处理
"""
from fastapi import Request
from fastapi.responses import JSONResponse


class AppException(Exception):
    """自定义应用异常"""
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class NotFoundException(AppException):
    def __init__(self, message: str = "资源不存在"):
        super().__init__(message, status_code=404)


class ForbiddenException(AppException):
    def __init__(self, message: str = "没有权限"):
        super().__init__(message, status_code=403)


class BadRequestException(AppException):
    def __init__(self, message: str = "请求参数错误"):
        super().__init__(message, status_code=400)


async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )


async def general_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": f"服务器内部错误: {str(exc)}"},
    )


def register_exception_handlers(app):
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
