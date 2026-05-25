"""
认证服务单元测试（tests/unit/test_auth_service.py）

说明：测试登录、密码强度检测等认证相关功能。
"""

from app.services.auth_service import check_password_strength


class TestPasswordStrength:
    """密码强度检测（纯函数，无需数据库）"""

    def test_weak_short_password(self):
        result = check_password_strength("abc")
        assert result.level <= 2
        assert result.is_weak is True
        assert len(result.suggestions) > 0

    def test_strong_password(self):
        result = check_password_strength("MyP@ssw0rd!2024")
        assert result.level >= 3
        assert result.is_weak is False

    def test_medium_password(self):
        result = check_password_strength("Password1")
        assert result.level >= 2

    def test_empty_password(self):
        result = check_password_strength("")
        assert result.level == 1
        assert result.is_weak is True

    def test_numeric_only_password(self):
        result = check_password_strength("12345678")
        assert result.level == 2
        assert len(result.suggestions) > 0

    def test_all_lower_password(self):
        result = check_password_strength("abcdefgh")
        assert result.level == 2
        assert len(result.suggestions) > 0
