# G1 Agent

一个以 Robot Skill Runtime 为执行边界的 Unitree G1 Agent。文本、麦克风和视觉
事件都不能直接分发机器人动作；所有动作最终只能通过 SkillRuntime 执行。

```text
文本输入 ──────────────────────┐
                              v
麦克风 -> Whisper ASR -> LangChain Agent -> 最终回复 -> AudioClient TTS
                              |
                              v
                       LangChain tools
                              |
                              v
                         SkillRuntime
                              |
                         RobotSkill
                              |
                    UnitreeG1Adapter
                              |
               unitree_sdk2_cpp bindings
```

Milestone 2 验证了不经过 LLM 的固定视觉触发链；当前 `test` 分支已经升级为
Milestone 3 的事件决策链：

```text
RealSense D435i USB -> person detection -> WorldState -> WorldEvent
    -> Decision Agent -> AgentDecision -> SkillRuntime -> G1 -> next frame
```

## 目录

```text
src/
├── agent/       # 对话 Agent、事件 Decision Agent 和决策执行闭环
├── app/         # 文本/麦克风 CLI 入口
├── adapters/    # LangChain tools、Whisper 输入、Unitree AudioClient
├── core/        # Skill Runtime 核心协议与执行器
├── perception/  # D435i 取流、人员检测、最小状态和事件检测
├── robot/       # RobotAdapter、G1 SDK 适配器、模拟适配器
└── skills/      # 具体 Robot Skill
```

## Wave 闭环验收

先完全绕过 Agent 和 Ollama，直接验证唯一 Runtime 入口：

```bash
uv run g1-wave
```

默认使用模拟适配器，输出至少包含：

```json
{"success": true, "status": "succeeded"}
```

在机器人主机上直接跑真实 G1：

```bash
uv run g1-wave --hardware --network eth0
```

这个命令的完整路径是
`SkillRuntime -> SkillExecutor -> SkillRegistry -> WaveSkill -> UnitreeG1Adapter -> bindings`，
不导入 Agent，也不调用 LLM。`--hardware` 会直接连接真机，没有二次交互确认。

## 安装

安装项目依赖并准备 Ollama：

```bash
uv sync
ollama serve
ollama pull <model-name>
```

在机器人主机上还要安装本地 Unitree Python bindings：

```bash
git clone https://github.com/Yao0454/unitree_sdk2_bindings.git
cd unitree_sdk2_bindings
uv pip install -e .
```

代码直接使用 bindings 中的：

- `unitree_sdk2_cpp.channel.initialize/release`
- `unitree_sdk2_cpp.robot.g1.LocoClient`
- `unitree_sdk2_cpp.robot.g1.AudioClient`

## 文本入口

无硬件时使用模拟 `RobotAdapter`，便于验证 Agent 和工具调用：

```bash
uv run g1agent --input text
```

文本会先送入 LangChain `create_agent`。例如用户要求挥手时，Agent 调用 `wave`
工具，工具只调用 `SkillRuntime.execute()`，不会生成或解析 action 字符串。
模拟模式只打印 Agent 回复，不调用任何本机系统 TTS。

## 麦克风入口

麦克风输入通过 `arecord` 或 `ffmpeg` 录音，再交给本地 Whisper CLI：

```bash
sudo apt install alsa-utils ffmpeg

uv run g1agent --input microphone \
  --whisper-bin whisper-cli \
  --whisper-model /opt/models/ggml-base.bin \
  --language zh \
  --record-seconds 5
```

USB 麦克风不是默认设备时增加 `--audio-device hw:2,0`。ASR 的输出只是普通
用户文本，后续路径与文本入口完全一致。

## 连接真机

```bash
uv run g1agent \
  --hardware \
  --network eth0 \
  --input microphone \
  --whisper-bin whisper-cli \
  --whisper-model /opt/models/ggml-base.bin \
  --language zh
```

指定 `--hardware` 后程序会直接连接机器人。连接顺序为：

```text
初始化 DDS -> LocoClient.init() -> AudioClient.init() -> Agent 循环
```

Agent 的最终文字回复通过 `AudioClient.tts_maker(text, speaker_id)` 播放。默认
`speaker_id` 为 `0`，可以用 `--speaker-id` 修改；`--no-audio` 可以禁用语音输出。
`AudioClient` 复用 `UnitreeG1Adapter` 已初始化的 DDS channel，不会重复初始化或
释放全局 channel。

`connect()` 不调用 `start()` 或运动命令，`close()` 只释放 DDS。`wave` 与显式
`stop()` 都会改变实体机器人状态；真机运行前必须完成现场安全检查并准备物理急停。

## D435i 视觉闭环

D435i 通过 USB 直接连接运行本程序的 Linux 主机。相机取流使用
`pyrealsense2`，不经过 Unitree SDK；Unitree bindings 仍只负责 G1 动作。

安装可选视觉依赖：

```bash
uv sync --extra perception
```

部分 ARM64/Jetson 环境没有可用的 `pyrealsense2` wheel，需要按 Intel
librealsense 文档在目标机安装或编译 Python bindings。

启动 Ollama 并准备 Decision Agent 使用的模型：

```bash
ollama serve
ollama pull qwen2.5:3b
```

先用模拟机器人验证相机、事件、决策和状态去重：

```bash
uv run --extra perception g1-perception --once
uv run --extra perception g1-perception
```

默认闭环只处理三种稀疏事件：

```text
person_entered   -> Decision Agent -> wave / speech / ignore
person_left      -> Decision Agent -> normally ignore
person_too_close -> Decision Agent -> move_backward / speech / ignore
```

持续可见的同一个人不会重复产生 `person_entered`。默认距离小于等于 `0.8` 米时
产生一次 `person_too_close`，恢复到 `1.0` 米后才允许再次触发，可以分别使用
`--too-close-m` 和 `--too-close-release-m` 调整。

连接真实 G1：

```bash
uv run --extra perception g1-perception --hardware --network eth0
```

真机模式下，Decision Agent 的 `speech` 通过现有 Unitree `AudioClient` 播放；
`--no-audio` 可以关闭。动作决策仍先经过 Pydantic `AgentDecision` 校验，然后只调用
`SkillRuntime.execute()`，不会让模型直接访问 Unitree SDK。

多台 RealSense 同时连接时可增加 `--camera-serial <serial>`。默认读取
`640x480@30 FPS` 的彩色和深度流，将深度对齐到彩色画面，并忽略有效深度超过
`4` 米的检测。当前第一版使用 OpenCV HOG 全身检测器，适合验证闭环；实际场地
仍需根据视角、光照和人员距离调整阈值并做真机验收。

`move_backward` 将距离限制在 `0.05 <= distance_m <= 0.3` 米，并把速度限制在
`0.1` 到 `0.3` 米/秒。它使用 SDK 的非连续一秒运动命令作为硬件侧超时兜底，并且
只有 `stop_move()` 成功后才返回成功；异常、超时或取消仍会在 Skill 清理阶段再次
请求停止。当前距离来自速度乘时间的开环估计，不是定位系统提供的精确位移；真机
测试必须使用隔离场地并准备物理急停。

## 类型检查与测试

仓库根目录的 `pyrightconfig.json` 把本目录设为 `standard` 等级，并指向项目
`.venv`，避免编辑器使用错误解释器造成第三方类型缺失或 `create_agent` 的严格
Unknown 诊断。

```bash
uv run python -m unittest discover -s tests -v
uv run ruff check src tests
pyright src tests
uv build
```
