"""
天气查询服务（services/weather_service.py）

说明：调用高德地图天气 API 查询指定城市的实时天气信息。
     使用 httpx 进行异步 HTTP 请求。

核心功能：
    - get_weather(): 查询城市天气

API 调用流程：
    1. 地理编码：通过城市名称获取 adcode（行政区划代码）
       GET https://restapi.amap.com/v3/geocode/geo?address={city}&key={key}
    2. 天气查询：通过 adcode 获取实时天气
       GET https://restapi.amap.com/v3/weather/weatherInfo?city={adcode}&key={key}&extensions=base

依赖：
    - httpx（异步 HTTP 客户端）
    - 高德地图 Web 服务 API Key（配置在 .env 的 WEATHER_AMAP_KEY）

Java 对应关系：
    对应 Java 版的天气查询 Tool（AI Agent 工具）

用法：
    from app.services.weather_service import get_weather

    result = await get_weather("北京")
    print(result)
    # {"city": "北京市", "weather": "晴", "temperature": "25", "wind": "东南风", "humidity": "40"}
"""

import logging
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# 高德地图 API 基础 URL
# 注意：使用 HTTP 而非 HTTPS，避免某些网络环境（Clash TUN/fake-ip 模式等）
# 的 SSL 拦截导致连接失败。高德 API 同时支持 HTTP 和 HTTPS。
AMAP_GEO_URL = "http://restapi.amap.com/v3/geocode/geo"
AMAP_WEATHER_URL = "http://restapi.amap.com/v3/weather/weatherInfo"

# HTTP 请求超时时间（秒）
REQUEST_TIMEOUT = 10.0


async def get_weather(city_name: str) -> dict:
    """
    查询城市天气

    说明：调用高德地图 API 获取指定城市的实时天气信息。
         流程：城市名 → 地理编码获取 adcode → 查询天气。

    参数：
        city_name: 城市名称（如 "北京"、"上海"、"深圳"）

    返回：
        dict: 天气信息
            {
                "city": str,         # 城市名称（API 返回的标准名称）
                "weather": str,      # 天气现象（晴/多云/阴/雨等）
                "temperature": str,  # 温度（摄氏度）
                "wind": str,         # 风向 + 风力
                "humidity": str,     # 湿度（百分比）
            }

    异常处理：
        - API Key 未配置 → 返回错误提示
        - 城市未找到 → 返回错误提示
        - API 调用失败 → 返回错误提示
        - 网络超时 → 返回错误提示
    """
    # 检查 API Key 是否配置
    # 优先从 settings 读取（.env 或系统环境变量），再尝试直接读系统环境变量
    import os
    api_key = settings.WEATHER_AMAP_KEY
    if not api_key or api_key == "your_amap_key_here":
        api_key = os.environ.get("WEATHER_AMAP_KEY", "")
    if not api_key or api_key == "your_amap_key_here":
        logger.warning("高德地图 API Key 未配置")
        return {
            "city": city_name,
            "weather": "未知",
            "temperature": "未知",
            "wind": "未知",
            "humidity": "未知",
            "error": "天气 API Key 未配置，请在 .env 或系统环境变量中设置 WEATHER_AMAP_KEY",
        }

    if not city_name or not city_name.strip():
        return {
            "city": "",
            "weather": "未知",
            "temperature": "未知",
            "wind": "未知",
            "humidity": "未知",
            "error": "城市名称不能为空",
        }

    try:
        # verify=False: 跳过 SSL 证书验证
        # 说明：某些网络环境（公司代理、VPN）会做 HTTPS 中间人解密，
        #      导致 Python 的 SSL 验证失败。关闭验证后可正常调用。
        #      生产环境建议配置正确的 CA 证书而非关闭验证。
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, verify=False) as client:
            # Step 1: 地理编码 → 获取 adcode
            adcode = await _get_adcode(client, city_name, api_key)
            if not adcode:
                return {
                    "city": city_name,
                    "weather": "未知",
                    "temperature": "未知",
                    "wind": "未知",
                    "humidity": "未知",
                    "error": f"未找到城市: {city_name}",
                }

            # Step 2: 查询天气
            weather_data = await _get_weather_info(client, adcode, api_key)
            if not weather_data:
                return {
                    "city": city_name,
                    "weather": "未知",
                    "temperature": "未知",
                    "wind": "未知",
                    "humidity": "未知",
                    "error": "天气查询失败",
                }

            return weather_data

    except httpx.TimeoutException:
        logger.error(f"天气查询超时: city={city_name}")
        return {
            "city": city_name,
            "weather": "未知",
            "temperature": "未知",
            "wind": "未知",
            "humidity": "未知",
            "error": "天气查询超时，请稍后重试",
        }
    except httpx.HTTPError as e:
        logger.error(f"天气查询 HTTP 错误: {e}")
        return {
            "city": city_name,
            "weather": "未知",
            "temperature": "未知",
            "wind": "未知",
            "humidity": "未知",
            "error": f"天气查询网络错误: {e}",
        }
    except Exception as e:
        logger.error(f"天气查询异常: {e}")
        return {
            "city": city_name,
            "weather": "未知",
            "temperature": "未知",
            "wind": "未知",
            "humidity": "未知",
            "error": f"天气查询失败: {e}",
        }


async def _get_adcode(
    client: httpx.AsyncClient, city_name: str, api_key: str
) -> Optional[str]:
    """
    通过城市名称获取行政区划代码（adcode）

    说明：调用高德地理编码 API，将城市名称转换为 adcode。
         adcode 是高德地图的行政区划编码，用于后续天气查询。

    参数：
        client: httpx 异步客户端
        city_name: 城市名称
        api_key: 高德地图 API Key

    返回：
        Optional[str]: adcode 字符串，未找到时返回 None
    """
    params = {
        "address": city_name,
        "key": api_key,
        "output": "JSON",
    }

    response = await client.get(AMAP_GEO_URL, params=params)
    response.raise_for_status()

    data = response.json()

    # 检查 API 返回状态
    if data.get("status") != "1":
        logger.warning(f"地理编码失败: {data.get('info', '未知错误')}")
        return None

    # 提取 adcode
    geocodes = data.get("geocodes", [])
    if not geocodes:
        logger.info(f"未找到城市: {city_name}")
        return None

    adcode = geocodes[0].get("adcode")
    logger.debug(f"地理编码: {city_name} → adcode={adcode}")
    return adcode


async def _get_weather_info(
    client: httpx.AsyncClient, adcode: str, api_key: str
) -> Optional[dict]:
    """
    通过 adcode 查询实时天气

    说明：调用高德天气查询 API，获取指定区域的实时天气信息。

    参数：
        client: httpx 异步客户端
        adcode: 行政区划代码
        api_key: 高德地图 API Key

    返回：
        Optional[dict]: 天气信息字典，查询失败时返回 None
    """
    params = {
        "city": adcode,
        "key": api_key,
        "extensions": "base",  # base=实时天气, all=预报天气
        "output": "JSON",
    }

    response = await client.get(AMAP_WEATHER_URL, params=params)
    response.raise_for_status()

    data = response.json()

    # 检查 API 返回状态
    if data.get("status") != "1":
        logger.warning(f"天气查询失败: {data.get('info', '未知错误')}")
        return None

    # 提取天气数据
    lives = data.get("lives", [])
    if not lives:
        logger.warning(f"天气数据为空: adcode={adcode}")
        return None

    weather = lives[0]

    result = {
        "city": weather.get("city", ""),
        "weather": weather.get("weather", "未知"),
        "temperature": weather.get("temperature", "未知"),
        "wind": f"{weather.get('winddirection', '')}风 {weather.get('windpower', '')}级",
        "humidity": weather.get("humidity", "未知"),
    }

    logger.info(
        f"天气查询成功: {result['city']} - "
        f"{result['weather']} {result['temperature']}°C"
    )
    return result
