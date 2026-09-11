# G1 机器人控制台（Flutter）

仓库内 FastAPI 控制面的 Flutter 客户端，支持 Web 与 macOS。

## 已实现

- 通过 REST 启动/停止会话、保存系统提示词、提交及取消任务
- 通过 WebSocket 实时接收状态、日志、心跳和摄像头帧事件
- 显示 D435i RGB 画面、机器人连接状态和通信延迟
- 展示 Agent 输出、工具调用和 SkillRuntime 执行进度
- 日志等级筛选、搜索、暂停与清空
- 桌面、平板和手机响应式布局

前端不会直接调用 Unitree SDK。所有动作都经过 FastAPI、`RobotAgent` 和
`SkillRuntime`；是否连接真机由后端启动参数决定。

## 项目结构

```text
lib/
  main.dart                         # 启动入口，只调用 runApp
  app.dart                          # MaterialApp 与首页装配
  core/theme/                       # 应用主题、公共颜色
  features/console/
    models/                         # 后端快照、日志、工具调用数据模型
    services/console_api.dart       # REST/WebSocket API 客户端
    controllers/console_controller.dart
                                    # 服务状态、事件流、日志与界面状态
    presentation/
      console_page.dart             # 响应式布局、快捷键、消息提示
      console_intents.dart          # 快捷键动作定义
      widgets/                      # 摄像头、配置、输入、执行、日志等面板
test/
  support/fake_console_api.dart      # 可控的 API 测试替身
  widget_test.dart                   # 桌面/手机布局与任务流程
  features/console/                 # 控制器与事件流测试
```

状态使用 Flutter 自带的 `ChangeNotifier`，页面通过 `ListenableBuilder`
订阅更新。控制器启动时读取 `/api/v1/console`，之后订阅 `/api/v1/events`，
并保留低频 REST 轮询作为断线容错。

## 运行方式

先启动默认模拟后端：

```bash
cd ~/G1Agent
uv run g1-api
```

再启动前端：

```bash
cd ~/G1Agent/frontend
flutter run -d chrome
```

运行 macOS 桌面版：

```bash
flutter run -d macos
```

后端运行在机器人或另一台主机时，显式指定地址：

```bash
flutter run -d chrome \
  --dart-define=G1_API_BASE_URL=http://ROBOT_IP:8000
```

真机和 D435i 后端示例：

```bash
cd ~/G1Agent
uv run g1-api \
  --hardware \
  --network eth0 \
  --camera-source local \
  --host 0.0.0.0
```

`--host 0.0.0.0` 会把控制接口暴露到局域网，只应在可信网络中使用。

## 检查与构建

```bash
flutter analyze
flutter test
flutter build web
```

Web 发布文件位于 `build/web/`。

## 接口边界

默认 API 地址为 `http://127.0.0.1:8000`。摄像头下拉框中的“本机摄像头”指
FastAPI 所在主机通过 USB 连接的 RealSense D435i，不会申请浏览器或 macOS
客户端自身的摄像头权限。
