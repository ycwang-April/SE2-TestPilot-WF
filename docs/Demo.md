# 一分钟演示脚本

提前启动 Docker Desktop 并确认 `testpilot-runner:latest` 镜像存在，运行：

```powershell
python -m streamlit run testpilot_wf/ui.py
```

1. 0–10 秒：说明这是双 Agent 测试 Workflow。选择 edge_cases、Demo、Docker。明确 Demo 的模型响应是固定脚本，执行结果来自真实 pytest。
2. 10–25 秒：点击运行，展示 Generation 与 Execution 高亮、PREFLIGHT/EXECUTE/DIAGNOSE 阶段、v1 的反馈。初始导入拼写错误，已有断言未改。
3. 25–40 秒：展示 v2 修复后覆盖不足、v3 补测后的 9 passed 与 100% 行/分支覆盖率。实际耗时以机器为准，可提前运行后展示保存结果。
4. 40–50 秒：打开消息和 Trace：发送者、接收者、测试版本、证据引用、Controller 决策、两类预算。
5. 50–60 秒：下载报告。指出 Registry/Builder 的 MockAgent 插入测试，以及真实模型入口。当前没有有效 Key，不宣称本次已验证真实 DeepSeek。

终止演示可使用：

```powershell
python -m testpilot_wf examples/edge_cases --demo --runner docker --max-repair 0
```

应显示 FAIL / Repair budget exhausted，保留 v1 的导入错误证据。

视频为课程可选项，本次不生成模拟操作或虚构录屏。提交仓库/压缩包时排除 `.env`、`runs`、缓存、虚拟环境，保留 `docs/evidence`。PPT 要求最终压缩包小于 200 MB，文件名使用自己的学号姓名，截止时间为 2026-10-25 24:00。
