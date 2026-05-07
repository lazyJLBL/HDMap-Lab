# Resume Bullets

Use these bullets as role-specific variants. Keep the wording honest: HDMap-Lab is an algorithm workbench and prototype platform, not a production HD map system.

## A. 地图算法工程师版本

中文：

- 构建 HDMap-Lab 地图算法实验平台，将 ACM 计算几何能力工程化到鲁棒几何谓词、退化线段相交、polygon hole 判断、polyline 投影和路网 topology repair。
- 实现脏路网检测与修复流程，覆盖 duplicate edge、illegal crossing split、close-node snapping、dangling edge、overlapping roads、connected components，并输出 before/after metrics 与 debug GeoJSON。
- 设计 nearest / cost-based / HMM map matching 对比实验和多空间索引 benchmark，用 brute force 校验 recall，结合 A*/Dijkstra routing 展示路径解释能力。

English:

- Built HDMap-Lab, a computational-geometry based map algorithm workbench covering robust predicates, degenerate segment intersection, polygon holes, polyline projection, and road-network topology repair.
- Implemented dirty road-network validation and repair for duplicate edges, illegal crossing splits, close-node snapping, dangling edges, overlapping roads, and connected components with before/after metrics and debug GeoJSON.
- Designed nearest, cost-based, and HMM map matching experiments plus brute-force-checked spatial index benchmarks, and connected them to A*/Dijkstra explainable routing.

## B. GIS 后端工程师版本

中文：

- 使用 FastAPI 构建地图算法实验后端，提供 dataset loading、spatial query、topology validate/repair、map matching、routing、trajectory analysis 和 benchmark API。
- 实现 GeoJSON/OSM sample 数据处理 pipeline 与内存空间索引，支持 bbox/radius/nearest 查询，并用 benchmark API 输出 p50/p95/p99、candidate count、recall 与 debug layers。
- 搭建 Docker Compose 本地演示环境和 PostGIS 对比原型脚本，用于对比 Python 空间索引与 GiST 查询思路，但不包装成生产级 GIS 服务。

English:

- Built a FastAPI backend for map-algorithm experiments, exposing dataset loading, spatial query, topology validation/repair, map matching, routing, trajectory analysis, and benchmark APIs.
- Implemented a GeoJSON/OSM sample data pipeline with in-memory spatial indexes for bbox, radius, and nearest queries, returning p50/p95/p99, candidate count, recall, and debug layers.
- Added Docker Compose demo setup and a PostGIS comparison prototype script to contrast Python spatial indexes with GiST-style querying without claiming production GIS service readiness.

## C. 自动驾驶地图 / HD Map 版本

中文：

- 设计 lane-level HD map 原型数据模型，包含 Lane、LaneBoundary、LaneConnector、StopLine、Crosswalk、TrafficLight 等结构，用于表达道路拓扑与地图校验场景。
- 将 road topology validation、matching、routing 和 map data validation 串成可演示闭环，展示脏数据检测、修复后路网和 GPS 匹配路径的可解释结果。
- 实现 OpenDRIVE/Lanelet2 prototype 级导入导出与 XML/向量车道交换测试，明确定位为原型能力而非完整生产级规范支持。

English:

- Designed a prototype lane-level HD map model with Lane, LaneBoundary, LaneConnector, StopLine, Crosswalk, and TrafficLight structures for road topology and map validation scenarios.
- Connected road topology validation, matching, routing, and map-data validation into a demo loop showing dirty-map issues, repaired networks, and explainable GPS matched paths.
- Implemented prototype-level OpenDRIVE/Lanelet2 import/export and vector-lane exchange tests, explicitly scoped as prototype support rather than full production spec coverage.
