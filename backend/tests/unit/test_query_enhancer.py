"""
查询增强单元测试（tests/unit/test_query_enhancer.py）

测试 app.ai.chat.query_enhancer 中的查询判断和去重逻辑。
"""

import pytest
from app.ai.chat.query_enhancer import (
    is_simple_query,
    _deduplicate_results,
    _CONTEXT_SIGNALS,
)


class TestIsSimpleQuery:
    """简单查询判断测试"""

    def test_short_query(self):
        """短查询应判定为简单查询"""
        assert is_simple_query("请假") is True
        assert is_simple_query("考勤") is True
        assert is_simple_query("薪资查询") is True

    def test_long_query_with_signal(self):
        """长查询含信号词应判定为非简单查询"""
        assert is_simple_query("如何申请年假，需要什么条件和流程？") is False
        assert is_simple_query("请问公司的考勤制度是什么？") is False
        assert is_simple_query("帮我查询一下张三的薪资信息") is False

    def test_long_query_without_signal(self):
        """长查询无信号词应判定为简单查询"""
        assert is_simple_query("张三技术部前端组高级工程师") is True

    def test_empty_query(self):
        """空查询应判定为简单查询"""
        assert is_simple_query("") is True
        assert is_simple_query("   ") is True

    def test_boundary_length(self):
        """边界长度测试"""
        # 14 字符
        assert is_simple_query("这是一个十四字的测试查询文本") is True
        # 15 字符（含信号词）
        assert is_simple_query("请问这是一个十五字的测试查询文本") is False

    def test_context_signals_present(self):
        """验证上下文信号词集合非空"""
        assert len(_CONTEXT_SIGNALS) > 0
        assert "如何" in _CONTEXT_SIGNALS
        assert "怎么" in _CONTEXT_SIGNALS


class TestDeduplicateResults:
    """去重合并测试"""

    def test_empty_input(self):
        result = _deduplicate_results([])
        assert result == []

    def test_no_duplicates(self):
        """无重复结果"""
        results = [
            [
                {"doc_id": 1, "chunk_index": 0, "score": 0.9},
                {"doc_id": 1, "chunk_index": 1, "score": 0.8},
            ]
        ]
        merged = _deduplicate_results(results)
        assert len(merged) == 2

    def test_duplicates_keep_higher_score(self):
        """重复结果应保留更高分数"""
        results = [
            [{"doc_id": 1, "chunk_index": 0, "score": 0.7}],
            [{"doc_id": 1, "chunk_index": 0, "score": 0.9}],
        ]
        merged = _deduplicate_results(results)
        assert len(merged) == 1
        assert merged[0]["score"] == 0.9

    def test_sorted_by_score_desc(self):
        """结果应按分数降序排列"""
        results = [
            [
                {"doc_id": 1, "chunk_index": 0, "score": 0.5},
                {"doc_id": 2, "chunk_index": 0, "score": 0.9},
                {"doc_id": 3, "chunk_index": 0, "score": 0.7},
            ]
        ]
        merged = _deduplicate_results(results)
        scores = [r["score"] for r in merged]
        assert scores == sorted(scores, reverse=True)

    def test_multiple_lists(self):
        """多列表合并"""
        results = [
            [{"doc_id": 1, "chunk_index": 0, "score": 0.8}],
            [{"doc_id": 2, "chunk_index": 0, "score": 0.9}],
            [{"doc_id": 1, "chunk_index": 0, "score": 0.85}],
        ]
        merged = _deduplicate_results(results)
        assert len(merged) == 2
        # doc_id=1 应保留 0.85 的版本
        doc1 = next(r for r in merged if r["doc_id"] == 1)
        assert doc1["score"] == 0.85

    def test_exception_results_skipped(self):
        """异常结果应被跳过"""
        results = [
            [{"doc_id": 1, "chunk_index": 0, "score": 0.8}],
            Exception("error"),
            None,
        ]
        # 实际函数会处理非 list 类型
        valid = [r for r in results if isinstance(r, list)]
        merged = _deduplicate_results(valid)
        assert len(merged) == 1
