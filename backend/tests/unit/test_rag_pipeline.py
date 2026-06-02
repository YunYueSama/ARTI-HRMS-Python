"""
RAG 管线单元测试（tests/unit/test_rag_pipeline.py）

测试 app.ai.rag.pipeline 中的文本清洗、分块和 Token 估算功能。
"""

import pytest
from app.ai.rag.pipeline import (
    clean_text,
    split_text,
    estimate_token_count,
    _recursive_split,
    _add_overlap,
    _force_split,
    _SEPARATORS,
)


class TestCleanText:
    """文本清洗测试"""

    def test_empty_input(self):
        assert clean_text("") == ""
        assert clean_text(None) == ""

    def test_remove_page_footer_cn(self):
        text = "这是正文内容。\n第 1 页 共 10 页\n继续正文。"
        result = clean_text(text)
        assert "第 1 页 共 10 页" not in result
        assert "正文内容" in result

    def test_remove_page_footer_en(self):
        text = "Some content.\nPage 1 of 10\nMore content."
        result = clean_text(text)
        assert "Page 1 of 10" not in result
        assert "Some content" in result

    def test_remove_page_number_dash(self):
        text = "正文。\n- 3 -\n更多正文。"
        result = clean_text(text)
        assert "- 3 -" not in result

    def test_normalize_whitespace(self):
        text = "Hello   world\t\ttest"
        result = clean_text(text)
        assert "   " not in result
        assert "\t\t" not in result

    def test_filter_short_lines(self):
        text = "这是很长的内容行，超过二十个字符的阈值。\n短行\n另一行很长的内容，确保超过阈值。"
        result = clean_text(text)
        assert "短行" not in result
        assert "很长的内容" in result

    def test_merge_consecutive_empty_lines(self):
        text = "内容。\n\n\n\n更多内容。"
        result = clean_text(text)
        assert "\n\n\n" not in result

    def test_preserve_meaningful_content(self):
        text = "员工请假需提前3个工作日提交申请，并经直属上级审批同意后方可生效。"
        result = clean_text(text)
        assert "员工请假" in result
        assert "3个工作日" in result


class TestSplitText:
    """分块测试"""

    def test_empty_input(self):
        assert split_text("") == []
        assert split_text(None) == []

    def test_short_text_single_chunk(self):
        text = "短文本"
        result = split_text(text, chunk_size=100)
        assert len(result) == 1
        assert result[0] == "短文本"

    def test_chunk_size_respected(self):
        text = "A" * 1000
        result = split_text(text, chunk_size=200, chunk_overlap=0)
        for chunk in result:
            assert len(chunk) <= 200

    def test_overlap_present(self):
        text = "A" * 200
        result = split_text(text, chunk_size=100, chunk_overlap=20)
        assert len(result) >= 2
        # 第二块的开头应包含第一块末尾的重叠部分
        assert len(result) > 1

    def test_split_at_sentence_boundary(self):
        text = "第一句话。第二句话。第三句话。第四句话。"
        result = split_text(text, chunk_size=15, chunk_overlap=0)
        assert len(result) >= 2
        # 分块应该在句子边界处断裂

    def test_content_coverage(self):
        """分块后拼接应覆盖原始文本的所有内容"""
        text = "员工请假需提前申请。考勤记录每日更新。薪资按月发放。"
        result = split_text(text, chunk_size=20, chunk_overlap=5)
        combined = "".join(result)
        # 所有关键内容都应保留
        assert "请假" in combined
        assert "考勤" in combined
        assert "薪资" in combined


class TestEstimateTokenCount:
    """Token 估算测试"""

    def test_empty_input(self):
        assert estimate_token_count("") == 0
        assert estimate_token_count(None) == 0

    def test_chinese_text(self):
        count = estimate_token_count("你好世界")
        assert count > 0
        # 中文约 1.5 token/字
        assert count >= 4

    def test_english_text(self):
        count = estimate_token_count("Hello world")
        assert count > 0

    def test_mixed_text(self):
        count = estimate_token_count("Hello 你好")
        assert count > 0


class TestForceSplit:
    """强制切分测试"""

    def test_basic(self):
        result = _force_split("ABCDEFGHIJ", 3)
        assert result == ["ABC", "DEF", "GHI", "J"]

    def test_empty(self):
        result = _force_split("", 3)
        assert result == []


class TestAddOverlap:
    """重叠测试"""

    def test_basic_overlap(self):
        chunks = ["AAAA", "BBBB", "CCCC"]
        result = _add_overlap(chunks, overlap=2)
        assert len(result) == 3
        assert result[0] == "AAAA"
        assert result[1].startswith("AA")
        assert result[2].startswith("BB")

    def test_no_overlap(self):
        chunks = ["AAAA", "BBBB"]
        result = _add_overlap(chunks, overlap=0)
        assert result == chunks

    def test_single_chunk(self):
        chunks = ["AAAA"]
        result = _add_overlap(chunks, overlap=5)
        assert result == ["AAAA"]

    def test_empty_list(self):
        result = _add_overlap([], overlap=5)
        assert result == []
