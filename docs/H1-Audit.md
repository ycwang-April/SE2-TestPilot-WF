# H1 源码审计与实施计划

审计日期：2026-10-13。来源：用户本人 https://github.com/ycwang-April/SE1-TestPilot ，本地 `../hw1`，HEAD `b74bd8ffcd510176224d06828fc028d91a6f1076`。原目录仅有未跟踪 `.vscode/`，不修改、不复制该目录。没有复制 `.env`、Git 历史、缓存、旧运行证据或视频。

## 实际调用关系

`service.run_project → build_graph → AgentNodes.perform → controller.decide`。H1 每个工具节点返回同一 AgentState；PLAN/GENERATE/REPAIR/IMPROVE 共用 DeepSeekClient，EXECUTE 仅调用 TestRunner，因此 H1 不是两个独立推理 Agent。

阅读范围包括 README/Design、agent 四个模块、service、LLM client/fake/patches、prompts、runners、schemas、reporting、扫描/AST/context/coverage/validation/repair scope 工具、CLI/Streamlit、workflow/LLM/runner/scoped repair 测试、examples 和配置。

## 复用边界

| 部分 | 处理 |
|---|---|
| Scanner / AST / ContextSelector / CoverageAnalyzer | 保留基础实现，由 Generation 和 Execution 按权限调用 |
| TestRunner / Docker / Local / 临时工作区 / pytest JUnit | 原样复用；H2 直接选择后端，不使用 FallbackRunner |
| TestPlan / GeneratedTest / ExecutionResult | 原样复用，外层增加 H2 消息、版本、反馈契约 |
| AgentNodes 的 analyze/plan/generate/repair/improve 方法 | 作为 Generation 内部能力适配；不调用 H1 graph/controller/execute |
| DeepSeekClient / exact TestPatch / retain_tests | 复用结构化调用、有限重试、精确补丁；增加可覆盖的角色 prompt 接口 |
| ArtifactWriter / run directory / UI downloads | 复用 JSON 脱敏、命名、下载工具；新增 H2 trace/report |
| H1 tests / examples | 保留回归测试和示例，另建 H2 测试；Demo 明确标注 |
| H2 AgentProtocol / Registry / Builder / Controller | 新建；使用 LangGraph 顺序执行和受控循环 |
| Execution Agent | 新建独立诊断 prompt、模型实例与结构化输出，通过路径也调用诊断 |

## 风险及处理

- H1 对所有非零退出直接 repair：H2 增加证据引用与源码缺陷/不确定性终止，不能盲信模型 PASS。
- H1 默认 Docker 回退 Local：H2 禁止自动回退，Local 必须由调用者显式选择。
- H1 校验允许 SyntaxError 进入 pytest 且漏过 skip 装饰器：H2 preflight 更严格，非法候选保留但不提交版本。
- H1 保留函数及参数行数不能证明断言未削弱：H2 采用保守 AST 断言保留规则，无法自动安全修复时要求检查。
- 原始报告可能重复大型对象：H2 每版本证据落盘，消息只携带引用，当前状态不积累执行历史。
- 当前 Docker daemon 不可用；发现 `D:/conda_envs/testpilot/python.exe` 可复用依赖环境。真实调用和 Docker 结果需独立验证，不能引用 H1 证据冒充 H2。

## 实施顺序和目录

1. `testpilot/` 保留 H1 基础能力；`testpilot_wf/` 新建 schemas、agents、controller、registry/builder、service、CLI、UI。
2. 实现原子提交版本、反馈验证、独立诊断、确定性决策、有界循环。
3. 增加逐节点 observer、Agent 调用记录、消息与报告下载。
4. `tests/wf/` 验证 A/B/C/D、MockAgent 插入和安全边界，运行 H1 回归及 Ruff。
5. README/Design/Validation 和精选 `docs/evidence/` 记录实际结果；`runs/` 只保留本地产物。

PPT 第 2–4 页确认双 Agent、通信、顺序流程为必需，条件/循环、可视化、日志、错误恢复为推荐；评分 40/30/20/10。第 4 页的演示视频为可选，截止 2026-10-25 24:00，提交压缩包小于 200 MB。
