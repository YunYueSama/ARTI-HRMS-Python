"""
Token 管理器单元测试（tests/unit/test_token_manager.py）

测试 app.ai.token_manager 中的预算分配、截断和统计功能。
"""

import pytest
from app.ai.token_manager import TokenManager


class TestBudgetAllocation:
    """预算分配测试"""

    def test_default_allocation(self):
        """默认预算分配比例"""
        manager = TokenManager(context_window=10000)
        budget = manager.allocate_budget()

        # 总预算 = 窗口 * 阈值(0.8)
        assert budget["total_budget"] == 8000
        assert budget["context_window"] == 10000
        assert budget["threshold"] == 0.8

        # 各部分比例
        assert budget["system_prompt"] == 1600  # 20%
        assert budget["conversation_history"] == 3200  # 40%
        assert budget["rag_context"] == 2400  # 30%
        assert budget["user_message"] == 800  # 10%

    def test_custom_threshold(self):
        """自定义阈值"""
        manager = TokenManager(context_window=10000)
        budget = manager.allocate_budget(threshold=0.9)
        assert budget["total_budget"] == 9000

    def test_custom_window(self):
        """自定义窗口大小"""
        manager = TokenManager(context_window=4096)
        budget = manager.allocate_budget()
        assert budget["context_window"] == 4096
        assert budget["total_budget"] == 3276  # 4096 * 0.8

    def test_allocation_sums_to_total(self):
        """各部分之和等于总预算"""
        manager = TokenManager(context_window=8192)
        budget = manager.allocate_budget()
        parts_sum = (
            budget["system_prompt"]
            + budget["conversation_history"]
            + budget["rag_context"]
            + budget["user_message"]
        )
        assert parts_sum == budget["total_budget"]


class TestMessageLimit:
    """消息限制测试"""

    def test_within_limit(self):
        """短消息应通过限制检查"""
        manager = TokenManager()
        is_ok, count = manager.check_message_limit("你好", max_tokens=100)
        assert is_ok is True
        assert count > 0

    def test_exceeds_limit(self):
        """超长消息应被拒绝"""
        manager = TokenManager()
        long_text = "很长的消息" * 1000
        is_ok, count = manager.check_message_limit(long_text, max_tokens=10)
        assert is_ok is False

    def test_empty_message(self):
        """空消息应通过"""
        manager = TokenManager()
        is_ok, count = manager.check_message_limit("", max_tokens=100)
        assert is_ok is True
        assert count == 0


class TestTruncateHistory:
    """历史截断测试"""

    def test_empty_messages(self):
        """空消息列表"""
        manager = TokenManager()
        result = manager.truncate_history([], budget=100)
        assert result == []

    def test_within_budget(self):
        """消息在预算内不截断"""
        manager = TokenManager()
        messages = [
            {"role": "system", "content": "系统提示"},
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好！"},
        ]
        result = manager.truncate_history(messages, budget=10000)
        assert len(result) == 3

    def test_system_messages_preserved(self):
        """系统消息应始终保留"""
        manager = TokenManager()
        messages = [
            {"role": "system", "content": "你是HR助手"},
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好！"},
        ]
        result = manager.truncate_history(messages, budget=5)
        system_msgs = [m for m in result if m["role"] == "system"]
        assert len(system_msgs) >= 1

    def test_recent_messages_kept(self):
        """应保留最近的消息"""
        manager = TokenManager()
        messages = [
            {"role": "system", "content": "系统"},
            {"role": "user", "content": "第一条消息"},
            {"role": "assistant", "content": "第一条回复"},
            {"role": "user", "content": "第二条消息"},
            {"role": "assistant", "content": "第二条回复"},
        ]
        result = manager.truncate_history(messages, budget=20)
        # 应保留系统消息和最近的消息
        non_system = [m for m in result if m["role"] != "system"]
        assert len(non_system) >= 1


class TestUsageStats:
    """使用统计测试"""

    def test_empty_messages(self):
        manager = TokenManager(context_window=8192)
        stats = manager.get_usage_stats([])
        assert stats["total_tokens"] == 0
        assert stats["usage_ratio"] == 0.0

    def test_usage_ratio(self):
        manager = TokenManager(context_window=100)
        messages = [
            {"role": "user", "content": "你好世界"},
        ]
        stats = manager.get_usage_stats(messages)
        assert stats["total_tokens"] > 0
        assert 0 < stats["usage_ratio"] < 1

    def test_warning_threshold(self):
        """接近阈值时应触发警告"""
        manager = TokenManager(context_window=10, warning_threshold=0.1)
        messages = [
            {"role": "user", "content": "这是一条比较长的消息用于测试"},
        ]
        stats = manager.get_usage_stats(messages)
        assert stats["is_warning"] is True
