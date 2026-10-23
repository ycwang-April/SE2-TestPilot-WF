# 实际验收记录

## 2026-10-23：Generation preflight 有限自修正增量验收

- 新增针对性测试：17 passed；H2 Workflow 回归：58 passed。
- 完整 pytest：**343 passed, 3 skipped**，98.06 秒。[原始日志](evidence/preflight-20261023/pytest.txt)。跳过项仍为两个真实 API 集成测试及 Windows 符号链接权限测试，本次没有调用真实 DeepSeek。
- Ruff lint 通过，format check：102 files already formatted。[Lint](evidence/preflight-20261023/ruff-check.txt) · [Format](evidence/preflight-20261023/ruff-format.txt)。
- Fake 模型首次返回语法错误、第二次合法：FINISH，v1，7 passed，零 Repair/Coverage 轮数、仅两条正式消息。[运行报告](evidence/basic-demo-local-20261023-083323-713623f1/final_report.json) · [首次拒绝](evidence/basic-demo-local-20261023-083323-713623f1/rejected/000-attempt-01.json) · [第二次接受](evidence/basic-demo-local-20261023-083323-713623f1/generation_attempts/000/accepted-02.json)。已验证收集后的 Trace 所引用证据全部存在。
- 原有 Docker Demo：`runs/edge_cases-demo-docker-20261023-083243-3e8706b6`，FINISH，v3，9 passed，Repair=1、Coverage=1，行/分支覆盖率 100%。固定模型响应，不是真实 LLM 证据。
- 只新增 H2 preflight 的一次自修正；H1 内部校验和原有 API/格式重试保持原样，不叠加本地重试。已有断言保护优先，非法修复候选仍可能直接终止。未改 Controller、Builder、Registry、UI、H1 工具或验证规则，未提交或推送 Git。

以下为初版历史验收记录。

日期：2026-10-13（Asia/Shanghai）。工作目录：`D:/软件工程与项目实践/hw2`。

## 自动化检查

| 检查 | 实际结果 | 证据 |
|---|---|---|
| 全量 pytest（H1 回归 + H2） | **326 passed, 3 skipped**，86.13 秒 | [pytest.txt](evidence/pytest.txt) |
| Ruff lint | All checks passed | [ruff-check.txt](evidence/ruff-check.txt) |
| Ruff format --check | 99 files already formatted | [ruff-format.txt](evidence/ruff-format.txt) |
| Streamlit AppTest | 已包含在 pytest：Local Demo 完整循环、结果持久显示、v3、无 UI 异常 | `tests/wf/test_ui_wf.py` |
| 环境版本 | Python 3.13.16；主要依赖见记录 | [environment.json](evidence/environment.json) |

三个 skip：H1 和 H2 两个真实 API 集成测试均需 Key 和显式 opt-in；另一个继承的 Windows 符号链接测试因平台权限跳过。没有删掉失败测试来通过验收。

曾发现并修复：新测试使用 Windows 默认 GBK 读 UTF-8 报告、H1/H2 同名测试模块收集冲突、H1 UI 测试隐式依赖旧 fallback 配置。最后一项改为在该 H1 兼容测试中明确开启 fallback，H2 默认禁用保持不变。

## Docker 真实工具执行（固定模型响应 Demo）

Docker Desktop 已启动；daemon 版本 `29.8.1`。使用现有镜像 `testpilot-runner:latest`，镜像 ID `sha256:67ca62a8a73f82ea1ac0047e3d0039c5541809b3e55cea8176d4a418baedbb8c`。

| 场景 | 最终状态与事实 | 证据 |
|---|---|---|
| A：basic 正常路径 | FINISH，7 passed，v1，行/分支 100% / 100% | [报告](evidence/basic-demo-docker-20261013-114428-9df21c3a/final_report.json) |
| B + C：edge_cases 修复与补测 | FINISH，9 passed，v3，repair=1、coverage=1，行/分支 100% / 100% | [报告](evidence/edge_cases-demo-docker-20261013-114413-c26ce206/final_report.json) · [消息](evidence/edge_cases-demo-docker-20261013-114413-c26ce206/messages.json) · [Trace](evidence/edge_cases-demo-docker-20261013-114413-c26ce206/trace.json) |
| D：edge_cases 修复预算为 0 | FAIL，v1，pytest returncode=2、0 collected、1 collection error，原始 ImportError 保留 | [报告](evidence/edge_cases-demo-docker-20261013-114432-0d46cdd2/final_report.json) |

以上 **不含任何真实 LLM 调用**。Demo 的 Generation/Execution 响应是明确标注的脚本，Docker/pytest/coverage 数据是真实结果。真实模型诊断质量不能由 Demo 成功推出。

复现命令：

```powershell
python -m testpilot_wf examples/basic --demo --runner docker
python -m testpilot_wf examples/edge_cases --demo --runner docker
python -m testpilot_wf examples/edge_cases --demo --runner docker --max-repair 0
```

第三条预期退出码为 1，是正确终止验证，并非未处理崩溃。Local 模式也实际执行过正常路径、双循环和预算耗尽路径。

## 结构与防护验证

`tests/wf/` 覆盖双独立调用、双向消息、schema/消息方向/版本一致性、正常及低覆盖路由、源码缺陷/不确定性安全终止、伪 PASS 不覆盖工具结果、诊断格式和非法引用、临时超时重试、空收集/全 skip/超时、Docker 错误不回退、断言保留、非法 preflight、无变化候选不升级版本、两类预算耗尽、Registry、真实 LangGraph 插入 MockAgent 和写权限。

H1 的原测试继续覆盖 Scanner/AST、精确 Patch、结构化输出有限重试、去重、范围约束、Docker 命令与清理、Local 真实执行、覆盖率解析、报告、配置、上传工具及 UI 兼容行为。

## 尚未验证与已知限制

- **真实 DeepSeek + Docker 未执行**：用户明确告知 H1 原 API 已删除，没有可用 Key。此前尝试准备真实验证时，自动审批也拦截了读取 H1 凭据并发送源码的操作；此操作未执行，随后不再读取旧凭据。
- 准备好新 Key 后，可执行 README 中的真实命令，或 `tests/integration/test_wf_deepseek.py`。需要确认两个角色的 completed 调用和 Docker 后端，才能声称真实双 Agent 验证成功。
- 复用了现有 Conda 环境而非本次新建隔离环境。额外执行的 `pip check` 报告共享环境中 catboost/tensorflow 等非本项目包缺少依赖；未改动这些无关包。项目运行、全部测试与 Ruff 均通过，但不声称整个共享环境健康。新机器建议建立独立 Python 环境安装 `.[web,dev]`。
- UI 经 Streamlit AppTest 验证，未声称经过人工浏览器视觉验收。可选演示视频未录制，提供一分钟演示脚本。
- AST 保留检查是保守启发式，不能证明所有测试语义正确；Local 无隔离；只执行新生成测试；没有断点恢复、任意图或并行执行。

## H1 隔离确认

结束时再次检查 H1 Git 状态，仍只有原有未跟踪 `.vscode/`，没有修改 H1 源码。未复制任何 `.env`，未执行 commit/push。
