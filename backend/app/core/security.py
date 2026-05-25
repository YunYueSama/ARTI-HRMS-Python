"""
JWT 认证与密码安全模块（core/security.py）

说明：实现 JWT Token 的生成和校验，以及密码的哈希和验证。
     JWT（JSON Web Token）是一种无状态的认证机制：
     1. 用户登录时，服务端生成一个包含用户信息的 Token
     2. 客户端在后续请求中携带此 Token（Authorization: Bearer <token>）
     3. 服务端校验 Token 的签名和有效期，无需查询数据库

JWT 工作流程：
    用户登录 → 验证密码 → 生成 JWT Token（包含 user_id、username、role_id）
    → 返回 Token 给前端 → 前端存储 Token
    → 后续请求携带 Token → 服务端解码验证 → 提取用户信息

密码安全：
    使用 BCrypt 算法哈希密码，与 Spring Security 的 BCryptPasswordEncoder 兼容。
    BCrypt 自带盐值（salt），相同密码每次哈希结果不同，防止彩虹表攻击。

用法：
    from app.core.security import create_access_token, verify_password, hash_password

    token = create_access_token({"user_id": 1, "username": "admin"})
    is_valid = verify_password("123456", hashed_password)
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# ============================================================
# 密码哈希上下文
#
# 说明：使用 passlib 的 CryptContext 管理密码哈希算法。
#      schemes=["bcrypt"] 指定使用 BCrypt 算法。
#      deprecated="auto" 表示自动处理旧算法的迁移。
#
# 兼容性：Spring Security 默认使用 BCrypt，Python 的 passlib
#         生成的哈希格式与 Spring 完全兼容（$2a$/$2b$ 前缀）。
# ============================================================
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """
    生成 JWT Access Token

    参数：
        data: 要编码到 Token 中的数据（如 user_id、username、role_id）
        expires_delta: 自定义过期时间，默认使用配置中的 JWT_EXPIRE_MINUTES

    返回：
        编码后的 JWT Token 字符串

    示例：
        token = create_access_token({"user_id": 1, "username": "admin", "role_id": 1})
    """
    # 复制数据，避免修改原始字典
    to_encode = data.copy()

    # 计算过期时间
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)

    # 添加标准 JWT 声明
    to_encode.update(
        {
            "exp": expire,  # 过期时间（Expiration Time）
            "iat": datetime.now(UTC),  # 签发时间（Issued At）
        }
    )

    # 使用密钥和算法签名生成 Token
    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return str(encoded_jwt)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """
    解码并校验 JWT Token

    参数：
        token: JWT Token 字符串

    返回：
        解码后的 payload 字典（包含 user_id、username 等），
        校验失败返回 None

    校验内容：
        1. 签名是否有效（防篡改）
        2. Token 是否过期（exp 字段）
        3. 签发时间是否合理（iat 字段）
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return dict(payload)
    except JWTError:
        # Token 无效（签名错误、已过期、格式错误等）
        return None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证明文密码与哈希密码是否匹配

    参数：
        plain_password: 用户输入的明文密码
        hashed_password: 数据库中存储的 BCrypt 哈希值

    返回：
        True 表示密码正确，False 表示密码错误

    说明：
        BCrypt 验证过程：从哈希值中提取盐值 → 用相同盐值哈希明文 → 比较结果
        时间复杂度固定，防止计时攻击（Timing Attack）
    """
    return bool(pwd_context.verify(plain_password, hashed_password))


def hash_password(password: str) -> str:
    """
    将明文密码哈希为 BCrypt 格式

    参数：
        password: 明文密码

    返回：
        BCrypt 哈希字符串（格式：$2b$12$...）

    说明：
        每次调用生成不同的哈希值（因为盐值随机），这是正常行为。
        哈希结果包含算法标识、轮数和盐值，验证时自动提取。
    """
    return str(pwd_context.hash(password))
