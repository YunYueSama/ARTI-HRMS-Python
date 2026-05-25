"""
安全工具单元测试（tests/unit/test_security.py）

说明：测试 JWT 令牌生成/解码、密码哈希/验证等核心安全功能。
"""

from app.core.security import create_access_token, decode_access_token, hash_password, verify_password


class TestPasswordHashing:
    """密码哈希与验证"""

    def test_hash_password_returns_bcrypt_string(self):
        hashed = hash_password("123456")
        assert hashed.startswith("$2")
        assert len(hashed) > 20

    def test_hash_password_different_each_time(self):
        h1 = hash_password("123456")
        h2 = hash_password("123456")
        assert h1 != h2  # 盐值不同，哈希结果不同

    def test_verify_correct_password(self):
        hashed = hash_password("mypassword")
        assert verify_password("mypassword", hashed) is True

    def test_verify_wrong_password(self):
        hashed = hash_password("mypassword")
        assert verify_password("wrongpassword", hashed) is False

    def test_verify_empty_password(self):
        hashed = hash_password("abc")
        assert verify_password("", hashed) is False


class TestJWTToken:
    """JWT 令牌生成与解码"""

    def test_create_and_decode_token(self):
        payload = {"user_id": 1, "username": "admin", "role_id": 1}
        token = create_access_token(payload)
        assert isinstance(token, str)
        assert len(token) > 20

        decoded = decode_access_token(token)
        assert decoded is not None
        assert decoded["user_id"] == 1
        assert decoded["username"] == "admin"
        assert decoded["role_id"] == 1
        assert "exp" in decoded
        assert "iat" in decoded

    def test_decode_invalid_token(self):
        assert decode_access_token("invalid.token.here") is None

    def test_decode_empty_token(self):
        assert decode_access_token("") is None

    def test_token_contains_expiration(self):
        token = create_access_token({"user_id": 1})
        decoded = decode_access_token(token)
        assert decoded is not None
        assert "exp" in decoded

    def test_different_payloads_produce_different_tokens(self):
        t1 = create_access_token({"user_id": 1})
        t2 = create_access_token({"user_id": 2})
        assert t1 != t2
