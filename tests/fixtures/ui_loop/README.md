# UI 反馈循环测试产物

此 fixture 仅用于 `tests/wf/test_ui_state.py` 的历史 Trace 与消息投影测试，不调用模型、Docker 或外网。

## 来源与内容

从已保存的 Demo 运行 `docs/evidence/edge_cases-demo-docker-20261024-211020-dba414d0` 提取以下最小文件集合，四份文件均逐字节复制，未增加事件、改写消息或重新生成结果：

- `trace.json`：9 条真实节点/Controller 记录。
- `messages.json`：6 条正式 AgentMessage，保留方向、payload、版本、反馈及原始引用。
- `final_report.json`：原运行的 FINISH、v3、Repair=1、Coverage=1 等报告信息。
- `final_report.md`：同一运行的完整 Markdown 报告。

`load_run()` 的 UI 投影只读取这四份产物；保留完整字段可避免构造不合法的消息或伪造报告。未纳入 `generated_tests/`、`versions/` 等 UI 投影不读取的文件。

正式消息与 Trace 内的 `evidence_refs`、`tests_ref`、digest 等属于源运行的历史信息，保持原值；本 fixture 不执行或解析这些引用，也不是可重放的执行目录或完整实验副本。完整实验仍保存在原始 evidence 中。

## 稳定性约束

测试只从本目录读取数据，不在运行时从 `docs/evidence/` 复制，也不要求源运行目录继续存在。课程展示证据的清理或目录改名不应再影响该测试。

修改本 fixture 应视为测试行为变更，须保留或明确更新三轮 Generation 模式、三次 Controller 决策、消息顺序/方向、版本及报告终态断言。原始证据不应为配合测试而改写。
