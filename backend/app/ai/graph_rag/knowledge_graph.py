"""
HR 知识图谱（ai/graph_rag/knowledge_graph.py）

说明：基于 NetworkX 构建 HR 领域知识图谱，支持多跳关系查询和可视化。
     从 MySQL 数据库中提取员工、部门、职位、角色等实体及其关系，
     构建内存图结构，支持图遍历和关系推理。

核心功能：
    - build_from_database(): 从数据库构建知识图谱
    - query_relationships(): 多跳关系查询
    - get_visualization_data(): 获取前端可视化数据
    - sync_incremental(): 增量同步数据库变更

设计说明：
    使用 NetworkX 作为内存图引擎（无需 Neo4j 依赖）：
    - 节点（Node）：员工、部门、职位、角色
    - 边（Edge）：belongs_to（属于部门）、holds（担任职位）、has_role（拥有角色）
    - 属性：每个节点和边都可以携带属性数据

    图结构示例：
    [员工:张三] --belongs_to--> [部门:技术部]
    [员工:张三] --holds--> [职位:高级工程师]
    [员工:张三] --has_role--> [角色:普通员工]
    [部门:技术部] --parent_of--> [部门:前端组]

Java 对应关系：
    无直接对应（Python 新增的 GraphRAG 功能）

用法：
    from app.ai.graph_rag.knowledge_graph import HRKnowledgeGraph

    graph = HRKnowledgeGraph()
    await graph.build_from_database(db)
    results = graph.query_relationships("张三", max_hops=2)
"""

import logging
from datetime import datetime

import networkx as nx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class HRKnowledgeGraph:
    """
    HR 知识图谱

    说明：基于 NetworkX 的内存知识图谱，存储 HR 领域的实体和关系。
         支持从数据库构建、多跳查询和可视化数据导出。

    节点类型：
        - employee: 员工
        - department: 部门
        - position: 职位（岗位）
        - role: 角色

    边类型（关系）：
        - belongs_to: 员工属于部门
        - holds: 员工担任职位
        - has_role: 员工拥有角色
        - parent_of: 部门的上下级关系
        - manages: 部门管理者关系

    用法：
        graph = HRKnowledgeGraph()
        stats = await graph.build_from_database(db)
        results = graph.query_relationships("技术部", max_hops=2)
        viz_data = graph.get_visualization_data()
    """

    def __init__(self):
        """初始化知识图谱（空图）"""
        self._graph: nx.DiGraph = nx.DiGraph()
        self._last_sync: datetime | None = None
        self._node_count: int = 0
        self._edge_count: int = 0

    @property
    def graph(self) -> nx.DiGraph:
        """获取底层 NetworkX 有向图实例"""
        return self._graph

    @property
    def last_sync(self) -> datetime | None:
        """获取最后一次同步时间"""
        return self._last_sync

    async def build_from_database(self, db: AsyncSession) -> dict:
        """
        从 MySQL 数据库构建知识图谱

        说明：查询员工、部门、职位、角色表，提取实体和关系，
             构建 NetworkX 有向图。

        流程：
            1. 查询部门表 → 创建部门节点 + 上下级关系边
            2. 查询职位表 → 创建职位节点
            3. 查询角色表 → 创建角色节点
            4. 查询员工表 → 创建员工节点 + 关系边

        参数：
            db: 异步数据库会话（MySQL）

        返回：
            dict: 构建统计信息
                {
                    "nodes": int,       # 节点总数
                    "edges": int,       # 边总数
                    "departments": int, # 部门节点数
                    "employees": int,   # 员工节点数
                    "positions": int,   # 职位节点数
                    "roles": int,       # 角色节点数
                    "build_time": str,  # 构建时间
                }
        """
        logger.info("开始从数据库构建知识图谱...")
        start_time = datetime.now()

        # 清空现有图
        self._graph.clear()

        stats = {
            "departments": 0,
            "employees": 0,
            "positions": 0,
            "roles": 0,
        }

        try:
            # Step 1: 构建部门节点和层级关系
            stats["departments"] = await self._build_departments(db)

            # Step 2: 构建职位节点
            stats["positions"] = await self._build_positions(db)

            # Step 3: 构建角色节点
            stats["roles"] = await self._build_roles(db)

            # Step 4: 构建员工节点和关系
            stats["employees"] = await self._build_employees(db)

        except Exception as e:
            logger.error(f"构建知识图谱失败: {e}")
            raise

        # 更新统计信息
        self._node_count = self._graph.number_of_nodes()
        self._edge_count = self._graph.number_of_edges()
        self._last_sync = datetime.now()

        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(
            f"知识图谱构建完成: " f"nodes={self._node_count}, edges={self._edge_count}, " f"time={elapsed:.2f}s"
        )

        return {
            "nodes": self._node_count,
            "edges": self._edge_count,
            **stats,
            "build_time": self._last_sync.isoformat(),
        }

    async def _build_departments(self, db: AsyncSession) -> int:
        """构建部门节点和层级关系"""
        result = await db.execute(text("SELECT dept_id, dept_name, parent_id FROM department"))
        rows = result.fetchall()
        count = 0

        for row in rows:
            dept_id, dept_name, parent_id = row
            node_id = f"dept:{dept_id}"

            # 添加部门节点
            self._graph.add_node(
                node_id,
                type="department",
                name=dept_name,
                entity_id=dept_id,
            )
            count += 1

            # 添加上下级关系
            if parent_id:
                parent_node_id = f"dept:{parent_id}"
                self._graph.add_edge(
                    parent_node_id,
                    node_id,
                    relation="parent_of",
                    label="下属部门",
                )

        logger.debug(f"部门节点: {count}")
        return count

    async def _build_positions(self, db: AsyncSession) -> int:
        """构建职位节点"""
        result = await db.execute(text("SELECT position_id, position_name, dept_id FROM job_position"))
        rows = result.fetchall()
        count = 0

        for row in rows:
            pos_id, pos_name, dept_id = row
            node_id = f"pos:{pos_id}"

            # 添加职位节点
            self._graph.add_node(
                node_id,
                type="position",
                name=pos_name,
                entity_id=pos_id,
            )
            count += 1

            # 职位属于部门
            if dept_id:
                dept_node_id = f"dept:{dept_id}"
                self._graph.add_edge(
                    node_id,
                    dept_node_id,
                    relation="in_department",
                    label="所属部门",
                )

        logger.debug(f"职位节点: {count}")
        return count

    async def _build_roles(self, db: AsyncSession) -> int:
        """构建角色节点"""
        result = await db.execute(text("SELECT role_id, role_name, role_desc FROM role"))
        rows = result.fetchall()
        count = 0

        for row in rows:
            role_id, role_name, role_desc = row
            node_id = f"role:{role_id}"

            # 添加角色节点
            self._graph.add_node(
                node_id,
                type="role",
                name=role_name,
                entity_id=role_id,
                description=role_desc or "",
            )
            count += 1

        logger.debug(f"角色节点: {count}")
        return count

    async def _build_employees(self, db: AsyncSession) -> int:
        """构建员工节点和关系边"""
        result = await db.execute(
            text(
                "SELECT e.emp_id, e.emp_name, e.dept_id, e.position_id, "
                "u.role_id "
                "FROM employee e "
                "LEFT JOIN sys_user u ON e.emp_id = u.emp_id"
            )
        )
        rows = result.fetchall()
        count = 0

        for row in rows:
            emp_id, emp_name, dept_id, position_id, role_id = row
            node_id = f"emp:{emp_id}"

            # 添加员工节点
            self._graph.add_node(
                node_id,
                type="employee",
                name=emp_name,
                entity_id=emp_id,
            )
            count += 1

            # 员工属于部门
            if dept_id:
                dept_node_id = f"dept:{dept_id}"
                self._graph.add_edge(
                    node_id,
                    dept_node_id,
                    relation="belongs_to",
                    label="属于",
                )

            # 员工担任职位
            if position_id:
                pos_node_id = f"pos:{position_id}"
                self._graph.add_edge(
                    node_id,
                    pos_node_id,
                    relation="holds",
                    label="担任",
                )

            # 员工拥有角色
            if role_id:
                role_node_id = f"role:{role_id}"
                self._graph.add_edge(
                    node_id,
                    role_node_id,
                    relation="has_role",
                    label="角色",
                )

        logger.debug(f"员工节点: {count}")
        return count

    def query_relationships(self, entity_name: str, max_hops: int = 4) -> list[dict]:
        """
        多跳关系查询

        说明：从指定实体出发，进行广度优先遍历（BFS），
             返回 max_hops 跳内的所有关联实体和关系路径。

        参数：
            entity_name: 实体名称（模糊匹配节点的 name 属性）
            max_hops: 最大跳数（默认 4，即最多遍历 4 层关系）

        返回：
            list[dict]: 关系路径列表
                [
                    {
                        "source": "emp:1",
                        "source_name": "张三",
                        "source_type": "employee",
                        "relation": "belongs_to",
                        "target": "dept:1",
                        "target_name": "技术部",
                        "target_type": "department",
                        "hops": 1,
                    },
                    ...
                ]
        """
        # 模糊匹配起始节点
        start_nodes = []
        for node_id, attrs in self._graph.nodes(data=True):
            if entity_name.lower() in attrs.get("name", "").lower():
                start_nodes.append(node_id)

        if not start_nodes:
            logger.info(f"未找到匹配实体: {entity_name}")
            return []

        # BFS 多跳遍历
        results = []
        visited = set()

        for start_node in start_nodes:
            # 使用 NetworkX 的 BFS 边遍历
            bfs_edges = nx.bfs_edges(self._graph, start_node, depth_limit=max_hops)

            for source, target in bfs_edges:
                edge_key = (source, target)
                if edge_key in visited:
                    continue
                visited.add(edge_key)

                # 获取节点和边属性
                source_attrs = self._graph.nodes.get(source, {})
                target_attrs = self._graph.nodes.get(target, {})
                edge_attrs = self._graph.edges.get((source, target), {})

                # 计算跳数（从起始节点到 source 的距离 + 1）
                try:
                    hops = nx.shortest_path_length(self._graph, start_node, target)
                except nx.NetworkXNoPath:
                    hops = max_hops

                results.append(
                    {
                        "source": source,
                        "source_name": source_attrs.get("name", source),
                        "source_type": source_attrs.get("type", "unknown"),
                        "relation": edge_attrs.get("relation", "related"),
                        "label": edge_attrs.get("label", ""),
                        "target": target,
                        "target_name": target_attrs.get("name", target),
                        "target_type": target_attrs.get("type", "unknown"),
                        "hops": hops,
                    }
                )

        logger.info(f"关系查询: entity='{entity_name}', " f"start_nodes={len(start_nodes)}, results={len(results)}")
        return results

    def get_visualization_data(self) -> dict:
        """
        获取前端可视化数据

        说明：将知识图谱转换为前端图可视化库（如 ECharts、D3.js）
             所需的 nodes + edges JSON 格式。

        返回：
            dict: 可视化数据
                {
                    "nodes": [
                        {"id": "emp:1", "name": "张三", "type": "employee", "category": 0},
                        {"id": "dept:1", "name": "技术部", "type": "department", "category": 1},
                        ...
                    ],
                    "edges": [
                        {"source": "emp:1", "target": "dept:1", "relation": "belongs_to", "label": "属于"},
                        ...
                    ],
                    "categories": [
                        {"name": "employee"},
                        {"name": "department"},
                        {"name": "position"},
                        {"name": "role"},
                    ],
                    "stats": {
                        "total_nodes": int,
                        "total_edges": int,
                        "last_sync": str,
                    }
                }
        """
        # 节点类型到分类索引的映射
        category_map = {
            "employee": 0,
            "department": 1,
            "position": 2,
            "role": 3,
        }

        # 构建节点列表
        nodes = []
        for node_id, attrs in self._graph.nodes(data=True):
            node_type = attrs.get("type", "unknown")
            nodes.append(
                {
                    "id": node_id,
                    "name": attrs.get("name", node_id),
                    "type": node_type,
                    "category": category_map.get(node_type, 0),
                    "entity_id": attrs.get("entity_id"),
                }
            )

        # 构建边列表
        edges = []
        for source, target, attrs in self._graph.edges(data=True):
            edges.append(
                {
                    "source": source,
                    "target": target,
                    "relation": attrs.get("relation", "related"),
                    "label": attrs.get("label", ""),
                }
            )

        # 分类定义
        categories = [
            {"name": "employee", "label": "员工"},
            {"name": "department", "label": "部门"},
            {"name": "position", "label": "职位"},
            {"name": "role", "label": "角色"},
        ]

        return {
            "nodes": nodes,
            "edges": edges,
            "categories": categories,
            "stats": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "last_sync": self._last_sync.isoformat() if self._last_sync else None,
            },
        }

    async def sync_incremental(self, db: AsyncSession) -> dict:
        """
        增量同步数据库变更

        说明：重新从数据库构建图谱（当前实现为全量重建）。
             后续可优化为基于时间戳的增量更新。

        参数：
            db: 异步数据库会话

        返回：
            dict: 同步结果统计
                {
                    "previous_nodes": int,
                    "previous_edges": int,
                    "current_nodes": int,
                    "current_edges": int,
                    "sync_time": str,
                }
        """
        previous_nodes = self._node_count
        previous_edges = self._edge_count

        # 当前实现：全量重建
        # TODO: 基于 updated_at 时间戳实现真正的增量同步
        build_stats = await self.build_from_database(db)

        return {
            "previous_nodes": previous_nodes,
            "previous_edges": previous_edges,
            "current_nodes": build_stats["nodes"],
            "current_edges": build_stats["edges"],
            "nodes_diff": build_stats["nodes"] - previous_nodes,
            "edges_diff": build_stats["edges"] - previous_edges,
            "sync_time": build_stats["build_time"],
        }


# ============================================================
# 全局知识图谱实例（单例）
#
# 说明：整个应用共享同一个知识图谱实例。
#      在应用启动时通过 build_from_database() 初始化。
# ============================================================
hr_knowledge_graph = HRKnowledgeGraph()
