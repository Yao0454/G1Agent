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

当前 `test` 分支默认运行 2 秒滑动视频窗口策略；原来的稀疏事件 Agent 仍可作为
回退模式：

```text
                              ┌-> VideoBuffer -> Video VLM -> AgentDecision
RealSense -> CameraFrame -----|
                              └-> HOG/depth safety
                                      |
                 AgentDecision -> SkillRuntime -> G1
```

相机持续采集 30 FPS，环形缓冲只保留最近 2 秒；视频策略默认以 500 ms 为目标间隔，
从窗口中均匀抽取 8 帧进行一次判断。VLM 推理、Skill 执行和相机采集相互解耦，
模型不会逐帧运行。如果一次推理超过 500 ms，策略不会并发堆积请求，而是在本次
推理完成后再开始下一次。HOG/WorldEvent 保留用于可观测性，中心区域深度安全停止
不等待 VLM。

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

SkillExecutor 会在同一资源锁和执行超时内运行 `execute() -> verify() -> cleanup()`。
真机 Wave 从 `rt/arm/action/state` 依次观察到 `face wave`（动作 ID `25`）和
`release arm`（动作 ID `99`）后标记 `completion_verified=true`。部分 G1 固件在
物理执行动作时始终发布空闲状态 `id=0`；这种情况下 SDK 接受命令后仍返回
`succeeded`，但在 1 秒反馈探测后标记 `completion_verified=false`。已经观察到动作
25 后发生中断或在 6 秒内没有完成时，才返回 `verification_failed`。
Wave 的总 Skill 超时为 20 秒，覆盖最长 10 秒的 SDK RPC 和随后的反馈验证。

## 安装

安装项目依赖并准备 Ollama：

```bash
uv sync
ollama serve
ollama pull <model-name>
```

机器人主机已经有 Unitree Python bindings 时，直接从现有目录安装：

```bash
uv pip install -e ~/unitree_sdk2/unitree_sdk2_bindings
```

如果当前环境没有 `uv`，也可以使用机器人上运行项目的 Python：

```bash
python3 -m pip install -e ~/unitree_sdk2/unitree_sdk2_bindings
```

代码直接使用 bindings 中的：

- `unitree_sdk2_cpp.channel.initialize/release`
- `unitree_sdk2_cpp.robot.g1.LocoClient`
- `unitree_sdk2_cpp.robot.g1.G1ArmActionClient`
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

本地 Hugging Face 视频策略还需要：

```bash
uv sync --extra perception --extra vision
```

`vision` extra 安装 Transformers、Pillow 和 SmolVLM processor 的轻量依赖，但不会
替换 Jetson 的 CUDA PyTorch。当前 Jetson 保持 JetPack 5.1.1 / CUDA 11.4，不需要
升级系统 CUDA。默认 `cuda` 后端由主程序启动常驻 `/usr/bin/python3` 子进程，复用
系统已有的 `torch 2.0.0+nv23.05` CUDA 环境；主程序与 CUDA worker 之间只传视频帧
和 JSON 决策。CUDA 不可用时会直接报错，不会静默退回 CPU。

JetPack 5 的系统 glibc 较旧，PyPI 的 ARM64 `pyrealsense2` wheel 可能无法加载。
在 ARM64 上程序会先尝试当前 Python；如果 binding 不可用，会自动启动常驻的
`/usr/bin/python3` 相机 worker，复用 JetPack 系统中安装的 librealsense、NumPy 和
OpenCV，不会为每帧重启进程。先验证系统 Python 环境：

```bash
/usr/bin/python3 -c 'import pyrealsense2, numpy, cv2; print("RealSense ready")'
```

如果 binding 安装在其他解释器中，可传入 `--camera-python /path/to/python`，或设置
`G1_REALSENSE_PYTHON`。不要为此升级 JetPack 5 的系统 glibc。

默认视频模型是：

```text
HuggingFaceTB/SmolVLM2-500M-Video-Instruct
```

先用 Hugging Face CLI 下载模型：

```bash
HF_HUB_DISABLE_XET=1 hf download \
  HuggingFaceTB/SmolVLM2-500M-Video-Instruct \
  --exclude 'onnx/*'
```

只有一台 D435i 时无需传 `--camera-serial`。先使用模拟机器人验证真实摄像头和
CUDA VLM，不会连接或驱动实体 G1：

```bash
.venv/bin/python -m app.perception --once --no-audio
.venv/bin/python -m app.perception --no-audio
```

上面默认等价于 `--policy vision --vision-backend cuda --vision-frame-count 1`。
当前设备的真实 8 帧测量约为 9–12 秒/次、峰值显存约 1.9 GB，因此无法用于
实时动作响应；2 帧实测仍约为 5.5–7.5 秒。`--vision-interval-s 0.5` 只是最短
调度间隔，因此当前硬件默认使用最新单帧，并拒绝执行基于超过 5 秒旧画面的动作：

```bash
.venv/bin/python -m app.perception \
  --no-audio \
  --vision-frame-count 1
```

需要保留两帧时可显式传 `--vision-frame-count 2`，但不适合低延迟握手响应。
深度安全锁只停止和阻止使用 `mobile_base` 的移动/姿态动作；`handshake`、`wave`
等仅使用 `upper_body` 的原地动作不会因为人手伸入 0.4 m 安全区而被取消。

完成现场安全检查后，才显式增加真机参数：

```bash
.venv/bin/python -m app.perception \
  --hardware \
  --network eth0 \
  --no-audio
```

如果使用 Ollama 的 Qwen2.5-VL：

```bash
ollama serve
ollama pull qwen2.5vl:3b

uv run --extra perception g1-perception \
  --hardware \
  --network eth0 \
  --camera-serial <front-camera-serial> \
  --vision-backend ollama \
  --model qwen2.5vl:3b \
  --no-audio
```

视频决策沿用统一的 `AgentDecision` JSON，并增加两个控制动作：

```text
continue  -> 保持当前行为，不启动新 Skill
interrupt -> 取消当前可中断 Skill，并调用机器人软件 stop
```

相同 Skill/参数/语音正在执行时不会重复启动；执行结束后默认还有 5 秒冷却，可用
`--action-cooldown-s` 调整。旧事件策略仍可运行：

```bash
uv run --extra perception g1-perception \
  --policy event \
  --model qwen3:1.7b
```

事件策略处理三种稀疏事件：

```text
person_entered   -> Decision Agent -> wave / speech / ignore
person_left      -> Decision Agent -> normally ignore
person_too_close -> Decision Agent -> move_backward / speech / ignore
```

持续可见的同一个人不会重复产生 `person_entered`。默认距离小于等于 `0.8` 米时
产生一次 `person_too_close`，恢复到 `1.0` 米后才允许再次触发，可以分别使用
`--too-close-m` 和 `--too-close-release-m` 调整。

所有运行日志使用固定 JSON Lines envelope：

```json
{"schema":"g1agent.log.v1","timestamp":"...","level":"info","type":"vision_decision","owner":"agent.vision_policy","data":{}}
```

每一行都会显示 `owner`。启动日志的 `data.owners` 会列出完整 owner 清单；主要值为
`perception.camera`、`perception.realsense`、`perception.detector`、`perception.safety`、
`agent.vision_policy`、`runtime.skill` 和 `robot.adapter`。观测日志默认只打印首次结果、
状态变化和每 5 秒一条心跳；`--verbose-observations` 恢复逐帧输出，
`--observation-interval-s <seconds>` 可调整心跳间隔。

连接真实 G1 并使用旧事件策略：

```bash
uv run --extra perception g1-perception \
  --policy event \
  --hardware \
  --network eth0
```

真机模式下，Decision Agent 的 `speech` 通过现有 Unitree `AudioClient` 播放；
`--no-audio` 可以关闭。动作决策仍先经过 Pydantic `AgentDecision` 校验，然后只调用
`SkillRuntime.execute()`，不会让模型直接访问 Unitree SDK。

Decision Agent 的技能目录由当前 `SkillRegistry` 动态生成，新增 Skill 后不需要再
维护另一份硬编码的技能白名单；每个动作的参数仍由对应 Skill 的 `SkillArgs` 校验。

当前 G1 动作 Skill 由 `skills.register_g1_skills()` 统一注册。安全自治目录包括：

```text
手臂预设：wave / wave_hand / handshake / shake_hand / two_hand_kiss / left_kiss /
right_kiss / hands_up / clap / high_five / hug / heart / right_heart / reject /
right_hand_up / x_ray / high_wave / release_arm
姿态：squat / sit / stand_up / high_stand / low_stand / balance_stand
移动：move / move_forward / move_backward / move_left / move_right /
turn_left / turn_right / stop / stop_move
```

SDK 里同样存在但不默认暴露给视觉模型的 operator-only Skill 为：
`start`、`damp`、`zero_torque`、`wave_with_turn`、`continuous_gait`、
`switch_move_mode`、`set_speed_mode`、`set_fsm_id`、`set_balance_mode`、
`set_swing_height`、`set_stand_height`、`set_velocity`、`set_task_id`、
`move_sdk`、
`switch_to_user_ctrl`、`switch_to_internal_ctrl`、`fsm_api`、
`execute_custom_arm_action`、`stop_custom_arm_action`。通过
`register_g1_skills(runtime, include_operator_only=True)` 才会加入这些控制；
如果需要拿到完整目录而不注册，可调用 `build_g1_all_skills()`。
命令行显式加载完整目录时增加 `--include-operator-only-skills`。例如：

```bash
.venv/bin/python -m app.perception \
  --hardware --network eth0 --no-audio \
  --include-operator-only-skills
```

这个开关会把危险控制也加入模型可见目录，只用于人工监管测试；正常视觉自治不要加。
其中 `damp`、`zero_torque`、显式 FSM/任务 ID、控制模式切换、原始 `fsm_api` 和
自定义手臂动作会改变控制状态，不能让 VLM 自主选择。`set_velocity` 也只在
operator-only 目录中提供；默认视觉目录使用带硬限幅和软件 stop 的
`move`/方向移动 Skills。
SDK 头文件把 `left kiss` 与 `right kiss` 都映射为动作 ID `12`，代码保持这个
真实映射而不是伪造两个不同的底层动作。`handshake` 优先使用 arm preset ID `27`，
没有 `G1ArmActionClient` 时回退到 SDK 示例的 `shake_hand(0)`，持续有限时间后用
`shake_hand(1)` 释放。

`wave` 使用 G1 `G1ArmActionClient` 的内置 `face wave`（动作 ID `25`）；如果当前
bindings 没有该客户端，则回退到 `LocoClient.wave_hand()`。内置手臂动作只支持
FSM `500`、`501`、`801`（FSM `801` 还要求 mode `0` 或 `3`）。SDK 返回 `0` 只表示
命令被服务接受，不表示动作已经完成；程序会把非零状态转换成可读的失败原因，并
尽量通过 `rt/arm/action/state` 完成后置验证。旧 bindings 或始终报告 `id=0` 的固件
会返回成功并标记 `completion_verified=false`，不会把未验证误报成已完成验证。

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
