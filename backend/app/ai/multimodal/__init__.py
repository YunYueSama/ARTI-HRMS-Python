"""
多模态交互模块（ai/multimodal/）

说明：提供语音转文字（STT）、文字转语音（TTS）和图像分析（Vision）功能。

子模块：
    - stt: 语音转文字（Whisper）
    - tts: 文字转语音（edge-tts）
    - vision: 图像分析（视觉模型）
"""

from app.ai.multimodal.stt import transcribe_audio
from app.ai.multimodal.tts import text_to_speech
from app.ai.multimodal.vision import analyze_image

__all__ = ["transcribe_audio", "text_to_speech", "analyze_image"]
