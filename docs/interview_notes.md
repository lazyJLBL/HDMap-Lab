# Interview Notes

## 30 秒项目介绍

HDMap-Lab 是一个面向地图算法的计算几何实验平台。我把 ACM 计算几何里的鲁棒几何判断、退化 case 处理、图论和空间索引能力，工程化到脏路网修复、空间索引 benchmark、HMM 地图匹配、轨迹分析和可解释路径规划中。项目后端是 FastAPI，前端用 React + Leaflet 展示原始路网、修复结果、GPS 点、匹配路径、查询 bbox、routing 和 debug layers。

## 为什么做这个项目

求职方向是地图算法、GIS 后端、空间数据工程和自动驾驶地图相关岗位。普通 CRUD 项目很难体现计算几何和图算法能力，所以我做了一个算法 workbench，把地图场景里真实会遇到的 dirty data、GPS noise、空间查询和路径解释问题拆成可运行、可测试、可 benchmark、可演示的模块。

## 我作为 ACM 计算几何选手的优势如何体现在项目里

优势不是只会写模板，而是能识别几何退化情况并把它们变成工程边界条件。项目里有共线、端点相交、部分重叠、完全重叠、近似共线、零长度边、polygon boundary、polygon hole 等测试；topology repair 依赖这些 predicate 去判断 crossing、overlap、snapping 和 split point。

## 项目架构

数据从 GeoJSON/OSM sample 进入 runtime store，经过 geometry kernel、topology repair、spatial index、map matching、trajectory/routing 模块，再由 FastAPI 暴露实验接口，前端 React + Leaflet 展示地图图层、metrics、warnings、debug layers 和 JSON 结果。

```text
GeoJSON / OSM
 -> Geometry Kernel
 -> Topology Repair
 -> Spatial Index
 -> Map Matching
 -> Routing / Trajectory
 -> FastAPI
 -> React + Leaflet
```

## 核心算法

- Geometry kernel：orientation、segment intersection、point-in-polygon with holes、projection、polyline length、simplification。
- Topology repair：duplicate detection、illegal crossing split、close-node snapping、dangling edge mark/remove、overlap detection、component analysis。
- Spatial index：brute force、grid、quadtree、KD-tree、R-tree、STR R-tree、Morton index。
- Map matching：nearest baseline、candidate cost、HMM/Viterbi sequence optimization。
- Routing/trajectory：Dijkstra、A*、turn cost、avoid polygons、Frechet、Hausdorff、DTW、outlier/deviation analysis。

## 鲁棒几何如何处理退化情况

核心是不要只依赖一个固定 epsilon。orientation 先用平移后的 double determinant 降低大坐标局部差分的误差，再在模糊区间使用 Decimal 重算。segment intersection 会区分 cross、endpoint_touch、touch、overlap、collinear_disjoint，并单独处理零长度 segment。polygon 判断会把 outer boundary、hole inside、hole boundary 明确区分。

## topology repair 解决了什么问题

真实道路数据常见问题包括重复边、路口没有节点、端点很近但没 snap、短 dangling stub、重叠道路和多 connected components。repair 的目标不是“自动修好所有地图”，而是提供可解释的操作记录和 before/after report：哪些边被 split，哪些节点被 snap，哪些 duplicate 被删除，哪些 dangling 被标记或移除。

## 空间索引 benchmark 怎么设计

benchmark 统一生成道路 bbox items 和查询集，对每种 index 执行相同的 bbox/radius/nearest 查询，并用 brute force 作为 correctness baseline。输出 build time、p50/p95/p99、candidate count、recall、false-positive rate 和 memory estimate。重点是可复查的工程 benchmark，而不是声称某个 index 在所有场景最快。

## HMM map matching 为什么比 nearest matching 好

nearest 只看单个 GPS 点到道路的距离，遇到 parallel road drift、低频采样、桥下/桥上、outlier 时容易跳到局部最近但全局不连通的道路。HMM 把每个点的候选道路看成状态，结合 emission distance、transition/network distance、heading、road class、one-way compatibility 等 cost，用 Viterbi 找全局代价最小路径，因此能减少非法跳变和局部漂移。

## routing / trajectory 模块的作用

routing 用来验证路网修复后是否更可路由，也给 map matching 的 transition cost 提供 graph distance。trajectory 模块用于比较 GPS 轨迹和参考路径，比如 Frechet、Hausdorff、DTW、simplification、outlier/deviation detection，帮助解释匹配质量和轨迹偏差。

## 前端如何展示算法结果

前端不是营销首页，而是一个工作台。地图层区分原始路网、修复后路网、GPS/trajectory、matched path、query bbox、routing result 和 issue marker；侧边栏可以运行 repair、index benchmark、matching、routing、trajectory 等实验；结果面板展示 metrics、warnings、debug layer keys、benchmark table 和完整 JSON。

## 当前项目限制

- 默认数据是 sample/synthetic/toy data，不是已提交的城市级 benchmark。
- OpenDRIVE/Lanelet2 是 prototype 级支持，不是完整生产级 parser。
- benchmark 数字依赖本地机器、数据规模和查询分布。
- 几何和距离计算面向小区域 lon/lat 路网，完整投影/大地测量不是当前重点。
- repair 策略是可解释原型，不能替代人工地图质检或生产地图 conflation pipeline。

## 面试官可能追问的问题和回答

Q: 你怎么证明不是简单 demo？

A: 我用 tests 覆盖 geometry degeneracy、topology repair、spatial index consistency、map matching stress、API smoke；benchmark 里用 brute force 做 correctness baseline；前端展示 debug layers，不只是返回一个成功状态。

Q: 为什么不用 Shapely/GEOS？

A: 求职目标是展示计算几何和地图算法能力，所以核心 predicate 和 repair 逻辑自研。生产系统可以用 GEOS 做底层，但这个项目重点是我能解释退化 case、误差边界和算法流程。

Q: HMM 的状态、观测和转移是什么？

A: 状态是每个 GPS 点的候选 road projection；观测代价主要是 GPS 到候选道路的距离；转移代价比较相邻 GPS 点距离和路网 graph distance，并加入 heading、turn、road class、layer、one-way compatibility 等约束。

Q: spatial index benchmark 如何避免误读？

A: 每个 index 跑相同 query set，用 brute force 检查 recall 和 false positive。报告里写明数据规模、查询类型和本机环境，不把 toy/synthetic 结果包装成 city-scale 性能结论。

Q: topology repair 会不会误修？

A: 会，所以我把它定位为可解释 repair prototype。每个操作都有 operation log 和 debug layer，能区分 mark-only、remove-short、split-intersection、snap-close-nodes，并保留 before/after report。
