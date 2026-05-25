"""
API 集成测试（tests/integration/test_api.py）

说明：测试 HTTP 端点的请求/响应流程。
"""

import pytest
from httpx import AsyncClient


class TestHealthCheck:
    """健康检查端点"""

    @pytest.mark.asyncio
    async def test_health_endpoint(self, client: AsyncClient):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
