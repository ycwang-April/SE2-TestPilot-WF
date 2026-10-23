# Homework 2 交付说明

## 实现内容

已完成 `testpilot_wf` 的 Generation/Execution Agent、独立角色模型适配、消息与共享状态、版本/摘要一致性、Controller、有界修复/补测、AgentProtocol/Registry/WorkflowBuilder、CLI、实时 Streamlit、分版本执行证据和报告下载。

H1 复用：Scanner、AST、ContextSelector、CoverageAnalyzer、TestPlan/GeneratedTest/ExecutionResult、Docker/Local Runner、临时工作区、pytest/JUnit、DeepSeek Structured Output 和重试、精确 Patch、保留测试/去重、ArtifactWriter、运行目录命名与 UI 下载工具。H1 package 和回归测试保留。必要改动仅有 LLM prompt 的可覆盖类属性，以及 H1 UI 回退测试的显式配置。

H2 新增：独立 Execution LLM 诊断、来源缺陷与不确定性终止、双向结构化消息、版本提交协议、字段写权限、受控扩展链、Agent 级日志、H2 CLI/UI 和专属验收。

## 对应四项评分

- 流程完整性 40%：真实运行正常、修复、补测、失败四条路径，Docker 验收有落盘证据。
- Agent 协作 30%：两个独立推理契约、GenerationResult/ExecutionFeedback 通信、共享状态分工、版本和证据绑定。真实 API 推理仍待用户提供新 Key 后验证。
- 可扩展性 20%：Protocol/Registry/Builder，MockAgent 在实际 LangGraph 中插入并传递状态，未改动原业务 Agent。
- 文档 10%：README、Design 的工作流/时序图、审计、运行命令、验收记录及演示脚本。

## 测试和未完成项

326 passed、3 skipped；Ruff lint/format 通过。Docker Demo basic 7 passed，edge_cases 经 1 次修复 + 1 次补测达到 9 passed；两者行/分支覆盖率 100%。预算耗尽正确 FAIL。详见 [Validation](Validation.md)。

缺有效 Key，真实 DeepSeek + Docker 和真实模型反馈循环未验证；不能将 Demo 报告作为真实模型证据。未录制可选视频，不实现提示词明确排除的持久化恢复、并行或拖拽图编辑器。保守断言保护拒绝自动修改已有期望值，复杂修复可能需要人工检查。

## 本机复现

```powershell
cd D:\软件工程与项目实践\hw2
& D:\conda_envs\testpilot\python.exe -m testpilot_wf examples/edge_cases --demo --runner docker
& D:\conda_envs\testpilot\python.exe -m streamlit run testpilot_wf/ui.py
& D:\conda_envs\testpilot\python.exe -m pytest
& D:\conda_envs\testpilot\python.exe -m ruff check .
& D:\conda_envs\testpilot\python.exe -m ruff format --check .
```

新 Key 只放本项目 `.env`，之后去掉 `--demo` 运行 basic。提交前排除 `.env`、runs、缓存和环境目录。项目位于独立 hw2 目录，未执行 Git 初始化、commit 或 push；仓库发布及课程提交由用户处理。
