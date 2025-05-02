# maim_message: MaimBot 通用消息接口库

`maim_message` 是一个为 [MaimBot](https://github.com/MaiM-with-u/MaiBot) 生态系统设计的 Python 库，旨在提供一套标准化的消息格式定义和基于 WebSocket 的通信机制。它的核心目标是解耦 MaimBot 的各个组件（如核心服务 `maimcore`、平台适配器 `Adapter`、插件 `Plugin` 等），使得它们可以通过统一的接口进行交互，从而简化开发、增强可扩展性并支持多平台接入。

晦涩难懂的readme -> [点这里](./README_OLD.md)

## 主要特性

*   **标准化消息结构:** 定义了 `MessageBase` 作为统一的消息载体，使用 `Seg` (Segment) 来表示不同类型的消息内容（文本、图片、表情、@、回复等），支持嵌套和组合。
*   **WebSocket 通信:** 提供基于 WebSocket 的 `Router`、`MessageClient` 和 `MessageServer` 类，用于建立组件间的双向通信连接。
*   **多平台管理:** `Router` 类可以方便地管理到多个不同平台或 MaimBot 实例的连接。
*   **解耦设计:** 使得适配器、插件和核心服务可以独立开发和部署。

## 安装

```bash
pip install maim_message
```

如果需要手动安装最新版

```bash
git clone https://github.com/MaiM-with-u/maim_message
cd maim_message
pip install -e .
```

最新版支持特性

1. 增加wss支持，在构造服务器时填写合适的crt和key即可，访问时在route_config填写ssl_verify字段为crt。
   ```python
   # 服务端这样写
   server = MessageServer(
        host="0.0.0.0",
        port=8090,
        ssl_certfile="./ssl/server.crt",
        ssl_keyfile="./ssl/server.key",
        mode="ws",
    )
    # 客户端这样写
    route_config = RouteConfig(
    route_config={
        "qq123": TargetConfig(
            url="wss://127.0.0.1:8090/ws",  # 使用wss协议
            token=None,  # 如果需要token验证则在这里设置
            ssl_verify=os.path.join(
                os.path.dirname(__file__), "ssl", "server.crt"
            ),  # SSL验证证书
        )
    }
    )
   ```
2. 增加实验性的纯tcp支持，在构造服务器时填写mode='tcp'即可，此时url变更为tcp://host:port
   ```python
   server = MessageServer(
        host="0.0.0.0",
        port=8090,
        mode="tcp",  # 使用 TCP 模式
    )
    route_config = RouteConfig(
    route_config={
            "platform1": TargetConfig(
                url="tcp://127.0.0.1:8090",  # 本地测试服务器
                token=None,
                ssl_verify=None,
            )
        }
    )


   ```



## 核心概念

1.  **`MessageBase`**: 所有通过 `maim_message` 传输的消息的基础结构。它包含：
    *   `message_info`: 消息元数据 (`BaseMessageInfo`)，如来源平台 (`platform`)、用户 (`UserInfo`)、群组 (`GroupInfo`)、消息ID、时间戳等。
    *   `message_segment`: 消息内容 (`Seg`)，通常是一个 `type` 为 `seglist` 的 `Seg`，其 `data` 包含一个由不同类型 `Seg` 组成的列表。
    *   `raw_message` (可选): 原始消息字符串。

2.  **`Seg`**: 消息内容的基本单元。每个 `Seg` 有：
    *   `type`: 字符串，表示内容类型（如 `"text"`, `"image"`, `"emoji"`, `"at"`, `"reply"`, `"seglist"` 等）。`maimcore` 目前主要处理 `text`, `image`, `emoji`, `seglist`。
    *   `data`: 具体内容。对于 `"text"` 是字符串，对于 `"image"` 或 `"emoji"` 通常是 Base64 编码的字符串，对于 `"at"` 是目标用户ID，对于 `"reply"` 是原消息ID，对于 `"seglist"` 是一个 `Seg` 对象的列表。

3.  **WebSocket 通信**:
    *   **`Router`**: 用于管理一个或多个到下游服务（通常是 `maimcore` 或作为服务器的插件）的 `MessageClient` 连接。它负责连接建立、消息发送和接收分发。
    *   **`MessageServer`**: 用于创建一个 WebSocket 服务器，接收来自上游客户端（如适配器或其他插件）的连接和消息。
    *   **`MessageClient`**: (由 `Router` 内部管理) 用于创建到 WebSocket 服务器的单个连接。

## 使用场景与示例

`maim_message` 库主要支持两种基本的使用模式，取决于您的组件在 MaimBot 生态中的角色：

1.  **作为客户端**: 您的组件需要连接到一个已经存在的 WebSocket 服务（通常是 MaimCore 或一个扮演服务器角色的插件）。这种模式下，您主要使用 `Router` 类来管理连接和收发消息。
2.  **作为服务器**: 您的组件需要监听连接，接收来自其他客户端（如适配器）的消息。这种模式下，您主要使用 `MessageServer` 类来创建服务和处理消息。

以下示例分别演示了这两种场景：

### 场景一：构建适配器或客户端 (使用 `Router` 连接到服务器)

此场景下，您的组件（如平台适配器）作为 **客户端**，连接到 MaimCore 或某个插件提供的 **WebSocket 服务器**。

```python
import asyncio
from maim_message import (
    BaseMessageInfo, UserInfo, GroupInfo, MessageBase, Seg,
    Router, RouteConfig, TargetConfig
)

# 1. 定义连接目标 (例如 MaimCore)
route_config = RouteConfig(
    route_config={
        # "platform_name" 是自定义的标识符，用于区分不同连接
        "my_platform_instance_1": TargetConfig(
            url="ws://127.0.0.1:8000/ws", # MaimCore 或目标服务器的地址
            token=None, # 如果服务器需要 Token 认证
        ),
        # 可以配置多个连接
        # "another_platform": TargetConfig(...)
    }
)

# 2. 创建 Router 实例
router = Router(route_config)

# 3. 定义如何处理从 MaimCore 收到的消息
async def handle_response_from_maimcore(message: MessageBase):
    """处理 MaimCore 回复的消息"""
    print(f"收到来自 MaimCore ({message.message_info.platform}) 的回复: {message.message_segment}")
    # 在这里添加将消息发送回原始平台（如QQ、Discord等）的逻辑
    # ...

# 4. 注册消息处理器
# Router 会自动将从对应 platform 收到的消息传递给注册的处理器
router.register_class_handler(handle_response_from_maimcore)

# 5. 构造要发送给 MaimCore 的消息
def construct_message_to_maimcore(platform_name: str, user_id: str, group_id: str, text_content: str) -> MessageBase:
    """根据平台事件构造标准 MessageBase"""
    user_info = UserInfo(platform=platform_name, user_id=user_id)
    group_info = GroupInfo(platform=platform_name, group_id=group_id)
    message_info = BaseMessageInfo(
        platform=platform_name,
        message_id="some_unique_id_from_platform", # 平台消息的原始ID
        time=int(asyncio.get_event_loop().time()), # 当前时间戳
        user_info=user_info,
        group_info=group_info,
    )
    message_segment = Seg("seglist", [
        Seg("text", text_content),
        # 可以添加其他 Seg, 如 Seg("image", "base64data...")
    ])
    return MessageBase(message_info=message_info, message_segment=message_segment)

# 6. 运行并发送消息
async def run_client():
    # 启动 Router (它会自动尝试连接所有配置的目标，并开始接收消息)
    # run() 通常是异步阻塞的，需要 create_task
    router_task = asyncio.create_task(router.run())
    print("Router 正在启动并尝试连接...")

    # 等待连接成功 (实际应用中需要更健壮的连接状态检查)
    await asyncio.sleep(2)
    print("连接应该已建立...")

    # 构造并发送消息
    platform_id = "my_platform_instance_1"
    msg_to_send = construct_message_to_maimcore(
        platform_name=platform_id,
        user_id="12345",
        group_id="98765",
        text_content="你好 MaimCore！"
    )
    print(f"向 {platform_id} 发送消息...")
    await router.send_message(msg_to_send)
    print("消息已发送。")

    # 让 Router 持续运行 (或者根据需要停止)
    # await router_task # 这会阻塞直到 router 停止

    # 示例：运行一段时间后停止
    await asyncio.sleep(5)
    print("准备停止 Router...")
    await router.stop()
    print("Router 已停止。")
    # 等待任务完成
    try:
        await router_task
    except asyncio.CancelledError:
        print("Router 任务已被取消。")


if __name__ == "__main__":
    try:
        asyncio.run(run_client())
    except KeyboardInterrupt:
        print("用户中断。")
    # 注意：实际适配器中，Router 的启动和消息发送/接收会集成到适配器的主事件循环中。
```

### 场景二：构建服务器 (如 MaimCore 或中间件插件，使用 `MessageServer` 接受连接)

此场景下，您的组件作为 **服务器**，接收来自适配器或其他客户端的 **WebSocket 连接**。

```python
import asyncio
from maim_message import MessageBase, Seg, MessageServer

# 1. 定义如何处理接收到的消息
async def handle_incoming_message(message_data: dict):
    """处理从客户端接收到的原始消息字典"""
    try:
        # 将字典反序列化为 MessageBase 对象
        message = MessageBase.from_dict(message_data)
        print(f"收到来自 {message.message_info.platform} (User: {message.message_info.user_info.user_id}) 的消息:")
        print(f"  内容: {message.message_segment}")

        # 在这里添加消息处理逻辑，例如：
        # - 调用 AI 模型处理文本
        # - 将消息转发给下游服务
        # - 修改消息内容

        # 示例：简单处理后回复
        processed_text = f"已收到您的消息：'{message.message_segment.data[0].data}'" # 假设第一个 seg 是 text
        reply_segment = Seg("seglist", [Seg("text", processed_text)])

        # 创建回复消息 (注意：需要填充正确的 platform, user_info, group_info 等)
        # 这里仅为示例，实际应用中需要根据请求信息构造回复的 message_info
        reply_message = MessageBase(
            message_info=message.message_info, # 借用原始信息，实际应按需修改
            message_segment=reply_segment
        )

        # 将处理后的消息广播给所有连接的客户端 (或定向发送)
        # 注意：需要 MessageServer 实例 (通常在外部定义)
        await server.send_message(reply_message)
        print("已发送回复。")

    except Exception as e:
        print(f"处理消息时出错: {e}")
        # 可以考虑向客户端发送错误信息

# 2. 创建并运行服务器
if __name__ == "__main__":
    host = "0.0.0.0"
    port = 19000 # 监听的端口

    # 创建服务器实例
    server = MessageServer(host=host, port=port)
    print(f"启动消息服务器，监听地址 ws://{host}:{port}")

    # 注册消息处理器
    server.register_message_handler(handle_incoming_message)

    # 同步运行服务器 (会阻塞)
    # server.run_sync()

    # 或者异步运行 (需要事件循环)
    async def run_server_async():
        try:
            await server.run() # run() 是异步阻塞的
        except KeyboardInterrupt:
            print("收到停止信号，正在关闭服务器...")
            await server.stop()
            print("服务器已关闭。")
        except Exception as e:
            print(f"服务器运行时发生错误: {e}")
            await server.stop() # 尝试关闭

    try:
        asyncio.run(run_server_async())
    except KeyboardInterrupt:
        pass # asyncio.run 会处理后续清理

```

## 实际应用示例

*   **MaiBot-Napcat-Adapter**: 一个典型的适配器实现，它使用 `maim_message` 连接 NapcatQQ (作为消息来源) 和 MaimCore (作为消息处理后端)。您可以参考 [MaiBot-Napcat-Adapter-main](https://github.com/MaiM-with-u/MaiBot-Napcat-Adapter) 来了解 `maim_message` 在实际项目中的应用。

## API 概览 (主要类)

*   `MessageBase`: 消息传输的基本单位。
*   `BaseMessageInfo`, `UserInfo`, `GroupInfo`, `FormatInfo`, `TemplateInfo`: 构成 `MessageBase.message_info` 的数据类。
*   `Seg`: 消息内容的基本单元。
*   `Router`: 管理到多个 WebSocket 服务器的客户端连接。
*   `RouteConfig`, `TargetConfig`: 用于配置 `Router` 的连接目标。
*   `MessageServer`: 创建 WebSocket 服务器。
*   `MessageClient`: (内部使用) 创建到 WebSocket 服务器的连接。

## 许可证

MIT License
