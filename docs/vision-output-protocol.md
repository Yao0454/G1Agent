# 远程视觉输出协议

UnifoLM 远程服务使用扁平动作 JSON（RemoteVisionInvoker.response_protocol = "decision"）。输入仍包含全部 52 个工具的参数 Schema、运行状态、任务和本地动作历史。该变更只涉及发送给模型的提示词，不要求修改模型服务 HTTP 接口。

无参数动作，或全部使用默认值：

```json
{"action":"execute_skill","skill":"clap"}
```

有参数动作：

```json
{"action":"execute_skill","skill":"set_speed_mode","arguments":{"mode":1}}
```

等待：

```json
{"action":"ignore"}
```

仅允许 action、skill、arguments、speech 字段。action 可取 execute_skill、execute_and_speak、speak、continue、interrupt、ignore；speech 仅在说话时提供。参数必须符合所选工具的 Schema，必填参数不能省略。省略 arguments 时由现有解析器补为空对象，工具自身负责参数默认值和必填校验。

远程模型不再被要求生成 state_update：本地继续记录已执行动作并提供运行上下文，但此模式不主动生成跨窗口的场景描述记忆。需要模型生成描述性记忆的其他后端仍沿用原有 decision + state_update 协议。解析器继续兼容原有完整响应，不移除非法字段、不补猜必填参数、不修复截断动作 JSON。

验证使用真实远程模型和模拟机器人，见 evaluations/tool-protocol-v4。该测试使用固定灰色图像，不衡量真实视频中的感知与长期记忆能力。
