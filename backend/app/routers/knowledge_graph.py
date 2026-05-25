"""
知识图谱路由（routers/knowledge_graph.py）

说明：定义 GraphRAG 知识图谱的 API 端点，包括节点查询、边查询、
     数据库同步和可视化数据导出。

端点列表：
    GET  /api/graph/nodes          → 列出节点（分页，按类型过滤）
    GET  /api/graph/edges          → 列出边（关系列表）
    POST /api/graph/sync           → 触发数据库同步
    GET  /api/graph/visualization  → 获取可视化数据（nodes + edges JSON）
    GET  /api/graph/query          → 查询实体关系（多跳遍历）

Java 对应关系：
    无直接对应（Python 新增的 GraphRAG 功能模块）

设计说明：
    - 使用 NetworkX 内存图作为后端存储
    - 数据来源为 MySQL 数据库（员工、部门、职位、角色）
    - 支持多跳关系查询（BFS 遍历）
    - 可视化数据格式兼容 ECharts 关系图
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.graph_rag.knowledge_graph import hr_knowledge_graph
from app.core.database import get_mysql_session
from app.core.dependencies import get_current_user, TokenPayload
from app.schemas.common import ApiResponse, ok, fail

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/nodes", summary="列出图谱节点")
async def list_nodes(
    node_type: Optional[str] = Query(
        default=None,
        description="节点类型过滤（employee/department/position/role）",
    ),
    page: int = Query(default=1, ge=1, description="页码"),
    size: int = Query(default=50, ge=1, le=500, description="每页大小"),
    user: TokenPayload = Depends(get_current_user),
) -> ApiResponse:
    """
    列出知识图谱节点（分页）

    说明：查询知识图谱中的节点，支持按类型过滤和分页。

    参数：
        node_type: 节点类型过滤（可选）
            - employee: 员工节点
            - department: 部门节点
            - position: 职位节点
            - role: 角色节点
        page: 页码（从 1 开始）
        size: 每页大小（默认 50，最大 500）

    返回：
        {
            "success": true,
            "data": {
                "items": [{"id": "emp:1", "name": "张三", "type": "employee"}, ...],
                "total": 100,
                "page": 1,
                "size": 50
            }
        }
    """
    graph = hr_knowledge_graph.graph

    # 获取所有节点
    all_nodes = []
    for node_id, attrs in graph.nodes(data=True):
        if node_type and attrs.get("type") != node_type:
            continue
        all_nodes.append({
            "id": node_id,
            "name": attrs.get("name", node_id),
            "type": attrs.get("type", "unknown"),
            "entity_id": attrs.get("entity_id"),
        })

    # 分页
    total = len(all_nodes)
    start = (page - 1) * size
    end = start + size
    items = all_nodes[start:end]

    return ok(
        data={"items": items, "total": total, "page": page, "size": size},
        message="查询成功",
    )


@router.get("/edges", summary="列出图谱边")
async def list_edges(
    relation: Optional[str] = Query(
        default=None,
        description="关系类型过滤（belongs_to/holds/has_role/parent_of）",
    ),
    page: int = Query(default=1, ge=1, description="页码"),
    size: int = Query(default=50, ge=1, le=500, description="每页大小"),
    user: TokenPayload = Depends(get_current_user),
) -> ApiResponse:
    """
    列出知识图谱边（关系列表）

    说明：查询知识图谱中的边（关系），支持按关系类型过滤和分页。

    参数：
        relation: 关系类型过滤（可选）
            - belongs_to: 属于（员工→部门）
            - holds: 担任（员工→职位）
            - has_role: 拥有角色（员工→角色）
            - parent_of: 上下级（部门→部门）
        page: 页码
        size: 每页大小

    返回：
        {
            "success": true,
            "data": {
                "items": [{"source": "emp:1", "target": "dept:1", "relation": "belongs_to"}, ...],
                "total": 200,
                "page": 1,
                "size": 50
            }
        }
    """
    graph = hr_knowledge_graph.graph

    # 获取所有边
    all_edges = []
    for source, target, attrs in graph.edges(data=True):
        edge_relation = attrs.get("relation", "related")
        if relation and edge_relation != relation:
            continue

        source_attrs = graph.nodes.get(source, {})
        target_attrs = graph.nodes.get(target, {})

        all_edges.append({
            "source": source,
            "source_name": source_attrs.get("name", source),
            "target": target,
            "target_name": target_attrs.get("name", target),
            "relation": edge_relation,
            "label": attrs.get("label", ""),
        })

    # 分页
    total = len(all_edges)
    start = (page - 1) * size
    end = start + size
    items = all_edges[start:end]

    return ok(
        data={"items": items, "total": total, "page": page, "size": size},
        message="查询成功",
    )


@router.post("/sync", summary="同步数据库到图谱")
async def sync_graph(
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse:
    """
    触发数据库同步

    说明：从 MySQL 数据库重新构建知识图谱。
         当前为全量重建，后续可优化为增量同步。

    返回：
        {
            "success": true,
            "data": {
                "previous_nodes": 50,
                "current_nodes": 55,
                "nodes_diff": 5,
                ...
            },
            "message": "同步完成"
        }
    """
    try:
        result = await hr_knowledge_graph.sync_incremental(db)
        return ok(data=result, message="知识图谱同步完成")
    except Exception as e:
        logger.error(f"知识图谱同步失败: {e}")
        return fail(message=f"同步失败: {e}")


@router.get("/visualization", summary="获取可视化数据")
async def get_visualization(
    user: TokenPayload = Depends(get_current_user),
) -> ApiResponse:
    """
    获取知识图谱可视化数据

    说明：返回前端图可视化库（ECharts 关系图）所需的 nodes + edges JSON 数据。

    返回：
        {
            "success": true,
            "data": {
                "nodes": [...],
                "edges": [...],
                "categories": [...],
                "stats": {"total_nodes": 100, "total_edges": 200, "last_sync": "..."}
            }
        }
    """
    viz_data = hr_knowledge_graph.get_visualization_data()
    return ok(data=viz_data, message="获取可视化数据成功")


@router.get("/query", summary="查询实体关系")
async def query_relationships(
    entity_name: str = Query(..., description="实体名称（模糊匹配）"),
    max_hops: int = Query(default=4, ge=1, le=6, description="最大跳数（1-6）"),
    user: TokenPayload = Depends(get_current_user),
) -> ApiResponse:
    """
    查询实体关系（多跳遍历）

    说明：从指定实体出发，进行多跳关系遍历（BFS），
         返回关联的实体和关系路径。

    参数：
        entity_name: 实体名称（模糊匹配，如 "张三" 或 "技术部"）
        max_hops: 最大跳数（默认 4，最大 6）

    返回：
        {
            "success": true,
            "data": {
                "entity_name": "张三",
                "max_hops": 4,
                "relationships": [
                    {
                        "source": "emp:1",
                        "source_name": "张三",
                        "relation": "belongs_to",
                        "target": "dept:1",
                        "target_name": "技术部",
                        "hops": 1
                    },
                    ...
                ],
                "total": 5
            }
        }
    """
    results = hr_knowledge_graph.query_relationships(
        entity_name=entity_name, max_hops=max_hops
    )

    return ok(
        data={
            "entity_name": entity_name,
            "max_hops": max_hops,
            "relationships": results,
            "total": len(results),
        },
        message="查询成功",
    )
