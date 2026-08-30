# G1 voice demo

一个尽量短的语言驱动具身机器人 Demo：

```text
输入（文本或麦克风） -> Whisper ASR -> Ollama -> {speech, action}
                                             |             |
                                             v             v
                                            TTS       Unitree SDK2
```

## 快速开始：无硬件文本演示

先准备本地 Ollama（默认模型是中文友好的 `qwen2.5:3b`）：

```bash
ollama serve
ollama pull qwen2.5:3b
```

在本仓库的 Python 环境中运行：

```bash
uv run g1agent
```

输入例如 `给大家打个招呼`、`点头表示同意` 或 `跳一段舞`。没有运行 Ollama 时程序会打印提示并使用关键词回退，动作以 `[robot dry-run]` 显示，不会控制真机。

## 连接 G1

在 Jetson/机器人环境中，确认 SDK2 Python binding 已安装（本机绑定源码位于 `~/unitree_sdk2_bindings`），然后显式打开真机模式：

```bash
uv pip install -e ~/unitree_sdk2_bindings  # 如果当前环境尚未安装绑定
uv run g1agent --hardware --network eth0
```

程序会先要求输入 `G1` 确认。支持的动作固定为：`wave`、`shake_hand`、`nod`、`shake_head`、`stand`、`sit`、`move_forward`、`turn_left`、`turn_right`、`dance`、`stop`。LLM 无法生成列表外的动作，也不会接收电机或关节参数。

`move_forward` 和左右转使用 SDK 的限时速度接口（约 0.7 秒）；`shake_hand` 使用 SDK 原生握手动作，`nod`、`shake_head`、`dance` 通过 G1 上配置的自定义动作名调用 `G1ArmActionClient`，如果机器人没有对应动作，程序会显示 SDK 错误而不会生成新的底层控制。

## 麦克风模式

麦克风模式使用系统工具，不把音频依赖塞进 Demo 核心。Jetson 上建议使用带 CUDA 的 `whisper.cpp`，避免为 Python/Torch 安装一套很重的 ARM 依赖：

```bash
sudo apt install alsa-utils ffmpeg
uv run g1agent --input microphone \
  --whisper-bin whisper-cli \
  --whisper-model /opt/models/ggml-base.bin \
  --language zh --record-seconds 5
```

`whisper-cli`/`whisper-cpp` 使用 whisper.cpp 参数；如果已有 Python `whisper` 命令也可以直接使用。USB 麦克风不是默认设备时，加 `--audio-device hw:2,0`。没有麦克风或 ASR 时，使用默认文本模式仍可完整演示 Ollama、TTS 并发和动作 dispatch。

## TTS

程序自动探测 `espeak-ng`、`espeak` 或 macOS `say`。找不到时只打印回复文本：

```bash
sudo apt install espeak-ng
```

中文语音可按本机安装的 voice 名称指定，例如：`uv run g1agent --tts-voice cmn`。语音播放和动作执行通过 `asyncio.gather` 并发，便于现场展示机器人边说边动。
