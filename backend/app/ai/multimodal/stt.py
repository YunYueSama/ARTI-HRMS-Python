"""
语音转文字服务（ai/multimodal/stt.py）

说明：使用 OpenAI Whisper 模型将音频文件转录为文本。
     支持 WAV、MP3、WebM 格式。
     如果 Whisper 未安装，返回占位响应。

核心功能：
    - transcribe_audio(): 将音频文件转录为文本
    - 自动检测语言
    - 返回转录文本、语言和音频时长

依赖：
    - openai-whisper（可选，未安装时使用占位实现）
    - ffmpeg（Whisper 依赖的音频处理工具）

用法：
    from app.ai.multimodal.stt import transcribe_audio

    result = await transcribe_audio("/tmp/audio.wav")
    print(result["text"])  # 转录文本
"""

import logging
import os
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

# ============================================================
# 尝试导入 Whisper
# 说明：Whisper 是可选依赖，未安装时使用占位实现
# ============================================================
try:
    import whisper
    WHISPER_AVAILABLE = True
    logger.info("Whisper 模型已加载")
except ImportError:
    WHISPER_AVAILABLE = False
    logger.warning(
        "openai-whisper 未安装，语音转文字将使用占位实现。"
        "安装方式: pip install openai-whisper"
    )

# 支持的音频格式
SUPPORTED_AUDIO_FORMATS = {".wav", ".mp3", ".webm", ".m4a", ".ogg", ".flac"}

# Whisper 模型实例（延迟加载）
_whisper_model = None


def _get_whisper_model():
    """
    获取 Whisper 模型实例（单例，延迟加载）

    说明：首次调用时加载模型到内存，后续调用复用同一实例。
         模型大小由配置 WHISPER_MODEL 控制（tiny/base/small/medium/large-v3）。
    """
    global _whisper_model
    if _whisper_model is None and WHISPER_AVAILABLE:
        model_name = settings.WHISPER_MODEL
        device = settings.WHISPER_DEVICE
        logger.info(f"加载 Whisper 模型: {model_name} (device={device})")
        _whisper_model = whisper.load_model(model_name, device=device)
    return _whisper_model


async def transcribe_audio(file_path: str) -> dict:
    """
    将音频文件转录为文本

    说明：使用 Whisper 模型进行语音识别，自动检测语言。
         如果 Whisper 未安装，返回占位响应。

    参数：
        file_path: 音频文件路径（支持 WAV、MP3、WebM 等格式）

    返回：
        dict: 转录结果
            {
                "text": str,       # 转录文本
                "language": str,   # 检测到的语言（如 "zh", "en"）
                "duration": float, # 音频时长（秒）
            }

    异常：
        FileNotFoundError: 文件不存在
        ValueError: 不支持的音频格式
    """
    # 验证文件存在
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"音频文件不存在: {file_path}")

    # 验证文件格式
    suffix = Path(file_path).suffix.lower()
    if suffix not in SUPPORTED_AUDIO_FORMATS:
        raise ValueError(
            f"不支持的音频格式: {suffix}，"
            f"支持的格式: {', '.join(SUPPORTED_AUDIO_FORMATS)}"
        )

    # 如果 Whisper 不可用，返回占位响应
    if not WHISPER_AVAILABLE:
        logger.info(f"Whisper 未安装，返回占位转录结果: {file_path}")
        return {
            "text": "[占位] Whisper 未安装，无法进行语音转文字。请安装 openai-whisper。",
            "language": "zh",
            "duration": 0.0,
        }

    # 使用 Whisper 进行转录
    try:
        model = _get_whisper_model()
        if model is None:
            return {
                "text": "[错误] Whisper 模型加载失败",
                "language": "unknown",
                "duration": 0.0,
            }

        logger.info(f"开始转录音频: {file_path}")
        result = model.transcribe(file_path, language=None)  # 自动检测语言

        # 计算音频时长
        duration = 0.0
        if result.get("segments"):
            last_segment = result["segments"][-1]
            duration = last_segment.get("end", 0.0)

        transcription = {
            "text": result.get("text", "").strip(),
            "language": result.get("language", "unknown"),
            "duration": duration,
        }

        logger.info(
            f"转录完成: language={transcription['language']}, "
            f"duration={transcription['duration']:.1f}s, "
            f"text_length={len(transcription['text'])}"
        )
        return transcription

    except Exception as e:
        logger.error(f"音频转录失败: {e}")
        raise RuntimeError(f"音频转录失败: {e}") from e
