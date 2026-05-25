"""
文字转语音服务（ai/multimodal/tts.py）

说明：将文本转换为语音音频（MP3 格式）。
     使用 edge-tts（微软 Edge 浏览器 TTS 引擎）作为主要实现。
     如果 edge-tts 未安装，抛出错误提示。

核心功能：
    - text_to_speech(): 将文本转换为 MP3 音频字节

依赖：
    - edge-tts（可选，未安装时抛出提示错误）

用法：
    from app.ai.multimodal.tts import text_to_speech

    audio_bytes = await text_to_speech("你好，我是亚托莉")
    # audio_bytes 为 MP3 格式的字节数据
"""

import io
import logging
import tempfile
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

# ============================================================
# 尝试导入 edge-tts
# 说明：edge-tts 是可选依赖，未安装时 TTS 功能不可用
# ============================================================
try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
    logger.info("edge-tts 已加载")
except ImportError:
    EDGE_TTS_AVAILABLE = False
    logger.warning(
        "edge-tts 未安装，文字转语音功能不可用。"
        "安装方式: pip install edge-tts"
    )


async def text_to_speech(text: str, voice: str = None) -> bytes:
    """
    将文本转换为语音音频（MP3 格式）

    说明：使用 edge-tts 将文本合成为语音。
         edge-tts 调用微软 Edge 浏览器的在线 TTS 服务，
         支持多种语言和语音角色，质量较高且免费。

    参数：
        text: 要转换的文本内容（不能为空）
        voice: 语音角色名称（可选，默认使用配置中的 TTS_VOICE）
               常用中文语音：
               - zh-CN-XiaoxiaoNeural（女声，温柔）
               - zh-CN-YunxiNeural（男声，自然）
               - zh-CN-XiaoyiNeural（女声，活泼）

    返回：
        bytes: MP3 格式的音频字节数据

    异常：
        ValueError: 文本为空
        RuntimeError: edge-tts 未安装或合成失败
    """
    if not text or not text.strip():
        raise ValueError("文本内容不能为空")

    if not EDGE_TTS_AVAILABLE:
        raise RuntimeError(
            "edge-tts 未安装，无法进行文字转语音。"
            "请安装: pip install edge-tts"
        )

    # 使用配置中的默认语音或传入的语音
    voice_name = voice or settings.TTS_VOICE
    logger.info(f"开始 TTS 合成: voice={voice_name}, text_length={len(text)}")

    try:
        # 使用 edge-tts 进行语音合成
        communicate = edge_tts.Communicate(text=text, voice=voice_name)

        # 收集音频数据到内存
        audio_buffer = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_buffer.write(chunk["data"])

        audio_bytes = audio_buffer.getvalue()

        if not audio_bytes:
            raise RuntimeError("TTS 合成结果为空")

        logger.info(f"TTS 合成完成: size={len(audio_bytes)} bytes")
        return audio_bytes

    except Exception as e:
        logger.error(f"TTS 合成失败: {e}")
        raise RuntimeError(f"文字转语音失败: {e}") from e


async def get_available_voices(language: str = "zh") -> list[dict]:
    """
    获取可用的语音角色列表

    说明：查询 edge-tts 支持的语音角色，按语言过滤。

    参数：
        language: 语言前缀过滤（如 "zh" 表示中文，"en" 表示英文）

    返回：
        list[dict]: 语音角色列表
            [{"name": "zh-CN-XiaoxiaoNeural", "gender": "Female", "locale": "zh-CN"}, ...]
    """
    if not EDGE_TTS_AVAILABLE:
        return []

    try:
        voices = await edge_tts.list_voices()
        filtered = [
            {
                "name": v["ShortName"],
                "gender": v.get("Gender", "Unknown"),
                "locale": v.get("Locale", ""),
            }
            for v in voices
            if v.get("Locale", "").startswith(language)
        ]
        return filtered
    except Exception as e:
        logger.error(f"获取语音列表失败: {e}")
        return []
