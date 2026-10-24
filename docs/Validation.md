# 实验与验证记录

核对日期：2026-10-24。本页引用当前仓库中仍存在的源码和证据。最新一轮将 UI 历史记录测试迁移到稳定 fixture，并执行专项、Workflow、完整 pytest 与 Ruff 检查；未发起付费模型调用或重跑五组 Real/Demo 实验。此前文档维护和日志编码核验记录继续保留；旧证据路径依赖的修复及前后结果见第 5 节。

## 1. 证据范围与统计口径

现存材料包括四组 Real DeepSeek + Docker、一组 Demo + Docker、MockAgent 专项测试日志，以及本轮新增的 [最终检查日志](evidence/final_checks/)，入口为 [evidence/](evidence/)。

- Workflow 状态、模式、后端、版本、轮数取自各组 `final_report.json`。
- 通过率 = `execution.passed / execution.collected_test_cases × 100%`，只描述最终生成测试集；并非模型生成成功率，也不包含项目自带测试套件。
- 行/分支覆盖率取自 `coverage`，由 [CoverageAnalyzer](../testpilot/tools/coverage_analyzer.py) 对目标模块的覆盖计数汇总。显示百分比可四舍五入至两位小数；不平均不同项目的百分比。
- 模型调用真实性按保存的 `demo=false`、`llm_calls.json` 中两个角色的 completed 调用，以及 Docker 执行记录交叉核对。Demo 不用于证明真实 LLM 推理能力。
- 表中次数为保存记录的实际值，不把不同轮次、不同模块的 API 调用数当作测试版本数。

五组最终报告的 `returncode` 均为 0，failed、errors、skipped 均为 0，且 `timed_out=false`；每组 JSON 与 Markdown 报告均存在。来源为下表的报告及同目录 `execution_result.json`、`coverage_result.json`。

## 2. 四组 Real DeepSeek + Docker

四组报告均记录 `demo=false`、`execution_backend=docker`、`status=FINISH`，模型为 `deepseek-flash`，最终版本均为 v1，Repair/Coverage 轮数均为 0。

| 项目 | 通过 / 收集 | 通过率 | 行覆盖率 | 分支覆盖率 | 报告 |
|---|---:|---:|---:|---:|---|
| basic | 14 / 14 | 100% | 100% | 100% | [JSON][basic-report] · [Markdown][basic-md] |
| advanced_project | 127 / 127 | 100% | 99.19% | 100% | [JSON][advanced-report] · [Markdown][advanced-md] |
| edge_cases | 19 / 19 | 100% | 100% | 100% | [JSON][edge-report] · [Markdown][edge-md] |
| multi_module | 48 / 48 | 100% | 100% | 100% | [JSON][multi-report] · [Markdown][multi-md] |

`advanced_project` 的原始行覆盖率为 **99.19354838709677%**，不是 100%。四次保存运行全部 FINISH，只能说明这些运行成功，不能据此推断一般成功概率或生产级测试质量。

### 2.1 两个角色的实际调用记录

| 项目 | Generation PLAN completed | Generation GENERATE completed | Execution DIAGNOSE completed | 调用记录 |
|---|---:|---:|---:|---|
| basic | 1 | 1 | 1 | [llm_calls.json][basic-calls] |
| advanced_project | 6 | 6 | 1 | [llm_calls.json][advanced-calls] |
| edge_cases | 1 | 1 | 1 | [llm_calls.json][edge-calls] |
| multi_module | 3 | 3 | 1 | [llm_calls.json][multi-calls] |

这四份记录共 26 条调用，均为 completed；与各自最终报告的 `model_calls` 一致。多模块分析/生成可以产生多次 API 请求，而测试集仍只提交一个 v1。独立职责和 Prompt 的实现见 [llm.py](../testpilot_wf/llm.py)，Execution 上下文明确使用 `action=DIAGNOSE`，见 [agents.py](../testpilot_wf/agents.py)。

### 2.2 消息与路径交叉核对

| 项目 | 正式消息 | Trace 路径 | 仓库内证据 |
|---|---|---|---|
| basic | Generation(v1) → Execution；Execution(v1) → Generation | generation → execution → controller(FINISH) | [messages][basic-messages] · [trace][basic-trace] |
| advanced_project | 同上，版本均为 v1 | 同上 | [messages][advanced-messages] · [trace][advanced-trace] |
| edge_cases | 同上，版本均为 v1 | 同上 | [messages][edge-messages] · [trace][edge-trace] |
| multi_module | 同上，版本均为 v1 | 同上 | [messages][multi-messages] · [trace][multi-trace] |

各版本的 `versions/001/` 下保留 tests、execution、coverage、feedback；每组消息中的证据引用均能在对应保存目录中解析到文件。四组真实实验未发生反馈循环，不把 Demo 的三轮路径归为真实模型实验结果。

## 3. Demo + Docker 反馈循环

该组明确记录 `demo=true`，模型调用记录为空；Generation 与 Execution 使用固定脚本响应，但三轮都调用 Docker 中真实的 pytest/coverage。实现依据为 [demo.py](../testpilot_wf/demo.py)。

[最终报告][demo-report] · [Markdown][demo-md] · [消息][demo-messages] · [Trace][demo-trace] · [模型调用记录][demo-calls]。

| 版本 | pytest returncode | 通过 / 收集 | errors | 行 / 分支覆盖率 | Execution 反馈 → Controller 决策 | 版本证据 |
|---|---:|---:|---:|---:|---|---|
| v1 | 2 | 0 / 0 | 1 | 无可确认数据 | REPAIR_TEST → REPAIR_TESTS | [versions/001/][demo-v1] |
| v2 | 0 | 1 / 1 | 0 | 54.55% / 37.50% | IMPROVE_COVERAGE → IMPROVE_COVERAGE | [versions/002/][demo-v2] |
| v3 | 0 | 9 / 9 | 0 | 100% / 100% | PASS → FINISH | [versions/003/][demo-v3] |

v1 为 `shipping_fe` 导入错误，不能把 0 收集的通过率写为 0% 或 100%，也不能把缺失覆盖率写为 0%。v2 的精确行覆盖率为 54.54545454545455%。最终 v3，Repair=1、Coverage=1，6 条正式消息的版本顺序为 `1,1,2,2,3,3`，Trace 中有三轮 generation → execution → controller。导入修复保留原断言，补测后再执行完整生成套件；可直接对照各版本 `tests.json` 与执行记录。

该证据支持“消息反馈、版本递增、修复/补测分支和真实重执行贯通”，不支持“Demo 包含真实 DeepSeek 调用”。

## 4. MockAgent 可扩展性专项验证

原始日志已由 UTF-16 LE（带 BOM）转换为 **UTF-8（无 BOM）**，便于 GitHub 预览。转换直接重编码原始字节解码得到的字符串，保留全部文本及原换行，不重新生成测试输出。转换前后均为 3047 个字符，UTF-8 文本 SHA-256 均为 `dcbbff39fc8a4b321016bd7f4987f9be05b8b870294480caead6248fadd5a657`，24 条 PASSED 与汇总完全不变；详见 [编码核验](evidence/final_checks/encoding-check.txt)。

原始日志：[mock_agent_tests.txt](evidence/extensibility/mock_agent_tests.txt)。日志记录 Python 3.13.16、pytest 9.1.1；收集 60 项，选择 24 项，**24 passed，36 deselected，耗时 22.70 秒**。这些是宿主测试会话信息，不作为 Docker 内部环境版本声明。

| 日志覆盖范围 | 通过项数 | 核对内容 |
|---|---:|---|
| 既有 Mock 插入、Registry、测试版本保护 | 3 | 前置扩展能被真实 LangGraph 调用，重复注册/非法图检查，扩展不能改版本 |
| basic / edge_cases × 前置、后置、组合链 | 6 | 顺序、反馈可见性、正式消息、digest 与多轮预算保持一致 |
| 后置节点的 Repair / Coverage 预算 | 2 | 对应预算耗尽时 FAIL，不因扩展而继续循环 |
| 后置扩展修改受保护字段 | 11 | 测试、版本、digest、消息、反馈、执行、覆盖率、计数、route、终态均被拒绝 |
| 前置 / 后置节点异常 | 2 | 错误直接进入 Controller 终止路径 |
| **合计** | **24** | 具体参数实例均在原始日志中列出 |

对应实现：[WorkflowBuilder / Registry](../testpilot_wf/workflow.py)、[Service wrapper](../testpilot_wf/service.py)；测试源码：[test_workflow.py](../tests/wf/test_workflow.py)。MockAuditAgent 不调用模型，只向 `extensions` 写观察记录。后置节点能看到 Execution 的当轮正式反馈，Controller 仍校验原消息；前置节点在后续轮次可能看到上一版本反馈。

可复现相同选择范围：

```powershell
python -m pytest tests/wf/test_workflow.py -k "mock_agent or registry or extension" -v
```

该专项日志仍保留原运行记录；本轮未单独重跑上述筛选命令，相关用例包含在完整 pytest 回归中。24 项是专项子集，不能替代第 5 节的全仓库回归结果。

## 5. 最终回归与验证入口

在当前 Python 环境于 **2026-10-24 22:40–22:43（UTC+08:00）** 顺序执行以下检查。日志均为 UTF-8、无 BOM，包含实际运行时间、命令、完整输出与退出码。pytest 显式关闭付费集成 opt-in 与 `.env` 加载，未运行真实 DeepSeek 请求；业务代码、其他测试和配置未修改。

| 检查 | 实际结果 | 退出码 | 日志 |
|---|---|---:|---|
| `python -m pytest tests/wf/test_ui_state.py::test_actual_loop_history_and_messages_rebuilt_from_artifacts -v` | **1 passed**；1.67 秒 | 0 | [ui-fixture-focused.txt](evidence/final_checks/ui-fixture-focused.txt) |
| `python -m pytest tests/wf -q` | **149 passed**；63.50 秒 | 0 | [workflow-after-fixture.txt](evidence/final_checks/workflow-after-fixture.txt) |
| `python -m pytest -q` | **434 passed，3 skipped**；121.76 秒 | 0 | [pytest-after-fixture.txt](evidence/final_checks/pytest-after-fixture.txt) |
| `python -m ruff check .` | All checks passed | 0 | [ruff-check-after-fixture.txt](evidence/final_checks/ruff-check-after-fixture.txt) |
| `python -m ruff format --check .` | 106 files already formatted | 0 | [ruff-format-after-fixture.txt](evidence/final_checks/ruff-format-after-fixture.txt) |

**已修复的历史失败**：上述 UI 用例此前固定引用已删除的 `docs/evidence/edge_cases-demo-docker-20261013-114413-c26ce206`，导致 `load_run()` 无法读取报告及 Trace，实际得到 0 行而非预期 10 行。修复前完整回归的 **433 passed、1 failed、3 skipped** 保留于 [pytest.txt](evidence/final_checks/pytest.txt)，本轮修复前的单项复现见 [ui-fixture-before.txt](evidence/final_checks/ui-fixture-before.txt)。这些是历史结果，不代表当前仍存在失败。旧目录已不存在，无法逐字段比较其内容；现存 Demo 满足原测试所要求的三轮流程。

[test_ui_state.py](../tests/wf/test_ui_state.py) 现使用 [tests/fixtures/ui_loop/](../tests/fixtures/ui_loop/README.md)。fixture 的四份文件 `trace.json`、`messages.json`、`final_report.json`、`final_report.md` 均逐字节复制自 [2026-10-24 Demo](evidence/edge_cases-demo-docker-20261024-211020-dba414d0/)，仅保留 UI 加载所需文件集合：9 条 Trace、6 条正式消息、三种 Generation 模式、三种 Controller 决策及 FINISH/v3 终态均保持原样。原有 10 条断言完整保留，另加产物读取无异常、报告确认完成且版本为 v3 的检查。fixture 不依赖原实验目录，不调用模型、Docker 或网络；内部历史证据引用保持原样，不作为独立可重执行的运行目录。

三个 skipped 分别为 H1/H2 两项需要显式 opt-in 与有效 Key 的付费集成测试，以及一项需要 Windows 平台权限的符号链接测试。当前回归无失败，但这三项未执行，不能据此声明它们已经通过。

| 验证主题 | 测试 / 源码入口 | 本轮结果口径 |
|---|---|---|
| 独立诊断上下文、证据保留与预算 | [test_execution_context.py](../tests/wf/test_execution_context.py) | 已包含在本轮通过的全量 pytest 中 |
| 协议方向、结构化输出、断言保护与安全边界 | [test_contracts.py](../tests/wf/test_contracts.py)、[test_boundaries.py](../tests/wf/test_boundaries.py) | 同上 |
| Generation preflight 有限自修正 | [test_generation_preflight.py](../tests/wf/test_generation_preflight.py) | 同上；旧自修正专项日志不再引用 |
| CLI 实时输出、去重、退出码与报告检查 | [test_cli.py](../tests/wf/test_cli.py) | 已包含在本轮通过的全量 pytest 中 |
| UI 终态、重绘、类型与状态投影 | [test_ui_wf.py](../tests/wf/test_ui_wf.py)、[test_ui_state.py](../tests/wf/test_ui_state.py) | 同上；旧路径依赖已修复 |

fixture 内容一致性、原断言保留、文档链接及修改范围核验见 [ui-fixture-checks.txt](evidence/final_checks/ui-fixture-checks.txt)。此前架构图、实验指标与文档核验仍保留于 [documentation-checks.txt](evidence/final_checks/documentation-checks.txt)；此前 Ruff 记录为 [ruff-check.txt](evidence/final_checks/ruff-check.txt) 和 [ruff-format.txt](evidence/final_checks/ruff-format.txt)，当前结果以上表为准。

README 架构图使用常见 Mermaid flowchart、subgraph、classDef 和标准节点形状；Design 使用 sequenceDiagram 展开调用和状态更新，避免复制主图。此前环境未安装 Mermaid CLI 或解析包，仅进行了语法形式与结构核对，**未完成本地渲染或 GitHub 页面视觉验证**；本轮未修改架构图。

## 6. 演示材料与验收边界

[Sample_Video.mp4](../Sample_Video.mp4) 文件现存，大小 5,010,068 字节，MP4 容器元数据时长约 **59.21 秒**。本轮核对了文件与时长，未逐帧审查画面及音轨，也不根据视频推断实验指标。播放前的准备和一分钟讲解建议见 [Demo](Demo.md)。

仍需人工确认：视频播放和音画是否清晰、画面与文字说明是否一致，以及课程提交平台的文件命名、体积和截止要求。本文不将已删除的课程附件说明当作当前提交规则。

当前保存结果不证明测试语义完全正确、模型诊断普遍可靠或整个依赖环境健康。AST 保护不等于形式化验证；仅执行生成套件；Local 无隔离；Docker 非生产级沙箱；没有持久化续跑。限制与设计理由见 [Design](../Design.md)。

[basic-report]: evidence/basic-deepseek-docker-20261024-210203-57db2d3a/final_report.json
[basic-md]: evidence/basic-deepseek-docker-20261024-210203-57db2d3a/final_report.md
[basic-calls]: evidence/basic-deepseek-docker-20261024-210203-57db2d3a/llm_calls.json
[basic-messages]: evidence/basic-deepseek-docker-20261024-210203-57db2d3a/messages.json
[basic-trace]: evidence/basic-deepseek-docker-20261024-210203-57db2d3a/trace.json
[advanced-report]: evidence/advanced_project-deepseek-docker-20261024-210520-c2e05592/final_report.json
[advanced-md]: evidence/advanced_project-deepseek-docker-20261024-210520-c2e05592/final_report.md
[advanced-calls]: evidence/advanced_project-deepseek-docker-20261024-210520-c2e05592/llm_calls.json
[advanced-messages]: evidence/advanced_project-deepseek-docker-20261024-210520-c2e05592/messages.json
[advanced-trace]: evidence/advanced_project-deepseek-docker-20261024-210520-c2e05592/trace.json
[edge-report]: evidence/edge_cases-deepseek-docker-20261024-210911-d5a1dbbe/final_report.json
[edge-md]: evidence/edge_cases-deepseek-docker-20261024-210911-d5a1dbbe/final_report.md
[edge-calls]: evidence/edge_cases-deepseek-docker-20261024-210911-d5a1dbbe/llm_calls.json
[edge-messages]: evidence/edge_cases-deepseek-docker-20261024-210911-d5a1dbbe/messages.json
[edge-trace]: evidence/edge_cases-deepseek-docker-20261024-210911-d5a1dbbe/trace.json
[multi-report]: evidence/multi_module-deepseek-docker-20261024-210942-55a23432/final_report.json
[multi-md]: evidence/multi_module-deepseek-docker-20261024-210942-55a23432/final_report.md
[multi-calls]: evidence/multi_module-deepseek-docker-20261024-210942-55a23432/llm_calls.json
[multi-messages]: evidence/multi_module-deepseek-docker-20261024-210942-55a23432/messages.json
[multi-trace]: evidence/multi_module-deepseek-docker-20261024-210942-55a23432/trace.json
[demo-report]: evidence/edge_cases-demo-docker-20261024-211020-dba414d0/final_report.json
[demo-md]: evidence/edge_cases-demo-docker-20261024-211020-dba414d0/final_report.md
[demo-messages]: evidence/edge_cases-demo-docker-20261024-211020-dba414d0/messages.json
[demo-trace]: evidence/edge_cases-demo-docker-20261024-211020-dba414d0/trace.json
[demo-calls]: evidence/edge_cases-demo-docker-20261024-211020-dba414d0/llm_calls.json
[demo-v1]: evidence/edge_cases-demo-docker-20261024-211020-dba414d0/versions/001/
[demo-v2]: evidence/edge_cases-demo-docker-20261024-211020-dba414d0/versions/002/
[demo-v3]: evidence/edge_cases-demo-docker-20261024-211020-dba414d0/versions/003/
