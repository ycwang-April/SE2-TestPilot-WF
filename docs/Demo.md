# 运行与一分钟演示

## 1. 准备

以下 PowerShell 命令均从项目根目录执行。先按 [README](../README.md) 安装 Python 环境与 `.[web,dev]`，启动 Docker Desktop（Linux 容器），再确认执行镜像：

```powershell
docker build -t testpilot-runner:latest .
docker info --format '{{.ServerVersion}}'
docker image inspect testpilot-runner:latest --format '{{.Id}}'
```

构建需要获取基础镜像与 Python 包；正常测试容器的网络限制由 Runner 实施。Docker 不可用时 Workflow 应保留失败报告，不自动回退到 Local。只有可信项目可显式选择 `--runner local`。

## 2. CLI：固定模型响应与真实执行

建议课堂演示使用内置 edge_cases：

```powershell
python -m testpilot_wf examples/edge_cases --demo --runner docker
```

这里 **Demo 固定的是 Generation 与 Execution 的 LLM 响应，不是执行结果**。测试真实送入 Docker，由 pytest 和 coverage 运行。按照当前内置脚本和默认配置，可观察：

```text
Generation(v1) -> Execution(REPAIR_TEST) -> Controller(REPAIR_TESTS)
Generation(v2) -> Execution(IMPROVE_COVERAGE) -> Controller(IMPROVE_COVERAGE)
Generation(v3) -> Execution(PASS) -> Controller(FINISH)
```

当前保存的同类运行最终为 v3、9 / 9 passed、行/分支覆盖率均为 100%，修复和补测各一次。依据为 [最终报告](evidence/edge_cases-demo-docker-20261024-211020-dba414d0/final_report.json)、[消息](evidence/edge_cases-demo-docker-20261024-211020-dba414d0/messages.json) 和 [Trace](evidence/edge_cases-demo-docker-20261024-211020-dba414d0/trace.json)。这些是既有运行结果，新运行仍应以自己的报告为准。

CLI 默认通过 observer 逐步输出 START / COMPLETED、Execution 的 PREFLIGHT / EXECUTE / DIAGNOSE、消息方向/类型/反馈/版本以及 Controller 决策和预算。重复快照会去重，新一轮阶段仍正常输出；不会虚构 Generation 内部阶段。报告返回并核验后才输出 `[Report] FINALIZED`。

只查看最终摘要：

```powershell
python -m testpilot_wf examples/edge_cases --demo --runner docker --quiet
```

演示预算耗尽的安全终止：

```powershell
python -m testpilot_wf examples/edge_cases --demo --runner docker --max-repair 0
```

最后一条按当前 Demo 的初始导入错误和 Controller 策略，**预期** FAIL / Repair budget exhausted，退出码 1；这是复现命令，不是本轮新增实验结果。失败报告应保留 v1 的执行错误。正常 FINISH 返回 0，REVIEW_REQUIRED 返回 2；配置或报告产物错误返回 1。

## 3. CLI：Real DeepSeek + Docker

先在进程环境或启动目录 `.env` 配置有效 `DEEPSEEK_API_KEY`，参考 [.env.example](../.env.example)。不要把密钥展示到录屏或输出中。以下命令均不带 `--demo`，会发送选定源码、测试和诊断上下文并产生 API 费用；按需选择项目，无需为了观看演示重新执行全部实验。

```powershell
python -m testpilot_wf examples/basic --runner docker
python -m testpilot_wf examples/advanced_project --runner docker
python -m testpilot_wf examples/edge_cases --runner docker
python -m testpilot_wf examples/multi_module --runner docker
```

每次运行结束，使用 CLI 的 `Artifacts:` 路径查看 `final_report.json`、`llm_calls.json`、`messages.json` 和 `trace.json`。确认 `demo=false`、实际 backend 为 docker，并且 Generation / Execution 均存在 completed 调用；终端的 REAL 标签只表示请求模式，不能单独证明模型调用成功。

仓库已保存上述四组真实实验，具体通过数、覆盖率和调用记录见 [Validation](Validation.md)。它们均在 v1 完成；不要把固定脚本演示的 Repair/Coverage Loop 说成四组真实模型实验共同经历的路径。

## 4. Streamlit

```powershell
python -m streamlit run testpilot_wf/ui.py
```

打开终端提示的地址，按以下顺序操作：

1. 选择 `edge_cases`，保留 Demo 勾选，执行后端选择 `docker`。
2. 保持默认覆盖率阈值与修复/补测预算，点击“运行 Workflow”。
3. 观察 Workflow 图与 Current Status。Execution 的三个内部阶段来自实时 observer；测试版本和轮数可在 Timeline 与通信记录中查看。
4. 展开 Agent Communication 消息详情，核对 `generation_result` / `execution_feedback`、版本和证据引用；Controller 路由在 Timeline 中单独显示。
5. 确认最终报告已生成，再查看 Results & Artifacts，下载 Markdown、生成测试 ZIP、Trace 等。

真实模式应取消 Demo 勾选并配置 Key；不能把 Demo 截图作为真实 DeepSeek 调用证据。界面依据实时状态和保存产物展示执行过程，只有确认最终报告存在后才标记完成；历史消息、Trace 与报告可交叉核对。

## 5. 一分钟视频与讲解建议

仓库视频：[Sample_Video.mp4](../Sample_Video.mp4)。文件大小 **5,010,068 字节**，按 MP4 容器元数据约 **59.21 秒**，可作为约一分钟演示材料入口。本轮只确认文件存在与元数据，未逐帧核对画面、音轨或字幕；提交前需人工播放确认可用性及模式标注。

下面是讲解建议，不声明现有视频逐秒对应本脚本：

| 时间 | 讲解重点 |
|---|---|
| 0–10 秒 | 说明 Generation 创作测试、Execution 独立执行诊断、Controller 确定性路由；明确当前演示为 Demo 或 Real |
| 10–30 秒 | 展示一次 Workflow，说明真实阶段、消息交付、版本及 Repair/Coverage 条件分支 |
| 30–45 秒 | 打开最终报告、messages 和 Trace，核对测试结果与证据；指出 Real 与 Demo 记录分开保存 |
| 45–60 秒 | 说明 Registry/Builder 支持前后置 MockAgent，并打开 24 项通过日志；给出设计文档与实验索引 |

API 或 Docker 的实际运行可能超过一分钟。可提前完成运行后展示已保存结果，或明确标注剪辑；不要用预设成功数字代替真实执行状态，也不要伪造实时运行。

## 6. 扩展性与证据演示

打开 [MockAgent 测试日志](evidence/extensibility/mock_agent_tests.txt)，其中记录 **24 passed，36 deselected**。前置、后置与组合链示例、只写 `extensions` 的限制和 Controller 回路说明见 [Design](../Design.md)。需要现场复现时可执行：

```powershell
python -m pytest tests/wf/test_workflow.py -k "mock_agent or registry or extension" -v
```

[Validation](Validation.md) 提供五组运行的有效相对链接。提交前确认视频能播放、相对链接可访问，并排除 `.env`、虚拟环境、缓存等本地文件。文件命名、体积限制和提交时间请以课程当前发布的要求为准。
