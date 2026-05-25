"""
多模态交互路由（routers/multimodal.py）

说明：定义多模态交互的 API 端点，包括语音转文字（STT）、文字转语音（TTS）、
     图像分析（Vision）和语音聊天（Voice Chat）完整流程。

端点列表：
    POST /api/multimodal/stt         → 上传音频，转录为文字
    POST /api/multimodal/tts         → 接收文本，返回语音音频流
    POST /api/multimodal/vision      → 上传图像，返回分析描述
    POST /api/multimodal/voice-chat  → 语音聊天完整流程（音频→转录→AI回复→TTS）

Java 对应关系：
    无直接对应（Python 新增的多模态功能模块）

设计说明：
    - STT 使用 Whisper 模型（或占位实现）
    - TTS 使用 edge-tts（微软 Edge TTS 引擎）
    - Vision 使用多模态视觉模型（当前为占位实现）
    - Voice Chat 整合 STT + AI Chat + TTS 的完整流程
"""

import logging
import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.multimodal.stt import transcribe_audio
from app.ai.multimodal.tts import text_to_speech
from app.ai.multimodal.vision import analyze_image
from app.ai.chat.service import ChatService
from app.core.database import get_mysql_session
from app.core.dependencies import get_current_user, TokenPayload
from app.schemas.common import ApiResponse, ok, fail

logger = logging.getLogger(__name__)

router = APIRouter()

# 聊天服务实例（用于 voice-chat 流程）
_chat_service = ChatService()


@router.post("/stt", summary="语音转文字")
async def speech_to_text(
    file: UploadFile = File(..., description="音频文件（WAV/MP3/WebM）"),
    user: TokenPayload = Depends(get_current_user),
) -> ApiResponse:
    """
    语音转文字（Speech-to-Text）

    说明：上传音频文件，使用 Whisper 模型转录为文本。
         支持 WAV、MP3、WebM 等常见音频格式。

    请求：
        - Content-Type: multipart/form-data
        - file: 音频文件

    返回：
        {
            "success": true,
            "data": {
                "text": "转录的文本内容",
                "language": "zh",
                "duration": 5.2
            }
        }
    """
    # 验证文件类型
    if not file.filename:
        return fail(message="未提供文件名")

    suffix = Path(file.filename).suffix.lower()
    allowed_formats = {".wav", ".mp3", ".webm", ".m4a", ".ogg", ".flac"}
    if suffix not in allowed_formats:
        return fail(
            message=f"不支持的音频格式: {suffix}，支持: {', '.join(allowed_formats)}"
        )

    # 保存临时文件
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            suffix=suffix, delete=False, prefix="hrms_stt_"
        ) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        # 调用转录服务
        result = await transcribe_audio(tmp_path)
        return ok(data=result, message="转录成功")

    except FileNotFoundError as e:
        return fail(message=str(e))
    except ValueError as e:
        return fail(message=str(e))
    except Exception as e:
        logger.error(f"语音转文字失败: {e}")
        return fail(message=f"语音转文字失败: {e}")
    finally:
        # 清理临时文件
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.post("/tts", summary="文字转语音")
async def text_to_speech_endpoint(
    text: str = Form(..., description="要转换的文本内容"),
    voice: str = Form(default=None, description="语音角色（可选）"),
    user: TokenPayload = Depends(get_current_user),
) -> Response:
    """
    文字转语音（Text-to-Speech）

    说明：接收文本内容，使用 edge-tts 合成语音，返回 MP3 音频流。

    请求：
        - Content-Type: application/x-www-form-urlencoded 或 multipart/form-data
        - text: 要转换的文本
        - voice: 语音角色（可选，默认 zh-CN-XiaoxiaoNeural）

    返回：
        - Content-Type: audio/mpeg
        - Body: MP3 音频字节流
    """
    if not text or not text.strip():
        return Response(
            content='{"success":false,"message":"文本内容不能为空"}'.encode("utf-8"),
            media_type="application/json",
            status_code=400,
        )

    try:
        audio_bytes = await text_to_speech(text, voice=voice)
        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": "attachment; filename=tts_output.mp3",
                "Content-Length": str(len(audio_bytes)),
            },
        )
    except ValueError as e:
        return Response(
            content=f'{{"success":false,"message":"{e}"}}'.encode("utf-8"),
            media_type="application/json",
            status_code=400,
        )
    except RuntimeError as e:
        return Response(
            content=f'{{"success":false,"message":"{e}"}}'.encode("utf-8"),
            media_type="application/json",
            status_code=500,
        )


@router.post("/vision", summary="图像分析")
async def vision_analyze(
    file: UploadFile = File(..., description="图像文件（JPEG/PNG/WebP）"),
    prompt: str = Form(default="", description="分析提示词（可选）"),
    user: TokenPayload = Depends(get_current_user),
) -> ApiResponse:
    """
    图像分析（Vision）

    说明：上传图像文件，使用视觉模型分析图像内容并返回描述文本。
         支持 JPEG、PNG、WebP 格式。

    请求：
        - Content-Type: multipart/form-data
        - file: 图像文件
        - prompt: 分析提示词（可选）

    返回：
        {
            "success": true,
            "data": {
                "description": "图像分析描述文本",
                "filename": "photo.jpg"
            }
        }
    """
    # 验证文件类型
    if not file.filename:
        return fail(message="未提供文件名")

    suffix = Path(file.filename).suffix.lower()
    allowed_formats = {".jpg", ".jpeg", ".png", ".webp"}
    if suffix not in allowed_formats:
        return fail(
            message=f"不支持的图像格式: {suffix}，支持: {', '.join(allowed_formats)}"
        )

    # 保存临时文件
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            suffix=suffix, delete=False, prefix="hrms_vision_"
        ) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        # 调用图像分析服务
        description = await analyze_image(tmp_path, prompt=prompt)
        return ok(
            data={"description": description, "filename": file.filename},
            message="分析完成",
        )

    except FileNotFoundError as e:
        return fail(message=str(e))
    except ValueError as e:
        return fail(message=str(e))
    except Exception as e:
        logger.error(f"图像分析失败: {e}")
        return fail(message=f"图像分析失败: {e}")
    finally:
        # 清理临时文件
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.post("/voice-chat", summary="语音聊天")
async def voice_chat(
    file: UploadFile = File(..., description="音频文件（WAV/MP3/WebM）"),
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse:
    """
    语音聊天完整流程（Voice Chat）

    说明：整合 STT + AI Chat + TTS 的完整语音交互流程：
         1. 接收用户上传的音频文件
         2. 使用 Whisper 转录为文本
         3. 将文本发送给 AI 聊天服务获取回复
         4. 将 AI 回复转换为语音（TTS）
         5. 返回文本回复和音频数据（Base64 编码）

    请求：
        - Content-Type: multipart/form-data
        - file: 音频文件

    返回：
        {
            "success": true,
            "data": {
                "user_text": "用户说的话",
                "ai_text": "AI 的回复",
                "audio_base64": "MP3音频的Base64编码（可选）",
                "language": "zh",
                "duration": 5.2
            }
        }
    """
    import base64

    # 验证文件类型
    if not file.filename:
        return fail(message="未提供文件名")

    suffix = Path(file.filename).suffix.lower()
    allowed_formats = {".wav", ".mp3", ".webm", ".m4a", ".ogg", ".flac"}
    if suffix not in allowed_formats:
        return fail(
            message=f"不支持的音频格式: {suffix}，支持: {', '.join(allowed_formats)}"
        )

    tmp_path = None
    try:
        # Step 1: 保存临时音频文件
        with tempfile.NamedTemporaryFile(
            suffix=suffix, delete=False, prefix="hrms_voice_"
        ) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        # Step 2: 语音转文字
        stt_result = await transcribe_audio(tmp_path)
        user_text = stt_result.get("text", "")

        if not user_text or user_text.startswith("[占位]") or user_text.startswith("[错误]"):
            return ok(
                data={
                    "user_text": user_text,
                    "ai_text": "抱歉，我没有听清楚你说的话，请再说一次。",
                    "audio_base64": None,
                    "language": stt_result.get("language", "unknown"),
                    "duration": stt_result.get("duration", 0.0),
                },
                message="转录结果为空或不可用",
            )

        # Step 3: AI 聊天获取回复
        ai_text = await _chat_service.chat_sync(
            user_id=user.user_id,
            message=user_text,
            db=db,
        )

        # Step 4: 文字转语音（TTS）
        audio_base64 = None
        try:
            audio_bytes = await text_to_speech(ai_text)
            audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
        except (RuntimeError, ValueError) as e:
            logger.warning(f"TTS 合成失败，仅返回文本: {e}")

        # Step 5: 返回结果
        return ok(
            data={
                "user_text": user_text,
                "ai_text": ai_text,
                "audio_base64": audio_base64,
                "language": stt_result.get("language", "zh"),
                "duration": stt_result.get("duration", 0.0),
            },
            message="语音聊天完成",
        )

    except Exception as e:
        logger.error(f"语音聊天失败: {e}")
        return fail(message=f"语音聊天失败: {e}")
    finally:
        # 清理临时文件
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
