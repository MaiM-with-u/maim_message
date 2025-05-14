# 高级消息处理

`maim_message` 库提供了丰富的消息处理功能，支持类级别和实例级别的消息处理器，以及基于平台的消息过滤。

## 消息处理器类型

### 1. 类级别处理器

类级别处理器在所有实例间共享，一旦注册，所有该类的新实例都会自动继承这些处理器。

```python
from maim_message import MessageServer, MessageClient

# 注册全局处理器
async def handle_all_messages(message):
    print(f"收到消息: {message}")

MessageServer.register_class_handler(handle_all_messages)

# 创建的所有服务器实例都会自动使用这个处理器
server1 = MessageServer()
server2 = MessageServer()  # 也会使用handle_all_messages
```

### 2. 平台特定处理器

平台特定处理器只处理来自特定平台的消息，可以在类级别或实例级别注册。

```python
# 注册特定平台处理器
async def handle_qq_messages(message):
    print(f"收到QQ消息: {message}")

# 类级别平台处理器
MessageServer.register_class_platform_handler("qq", handle_qq_messages)

# 实例级别平台处理器
server = MessageServer()
server.register_platform_handler("wechat", lambda msg: print(f"微信消息: {msg}"))
```

### 3. 实例级别处理器

实例级别处理器只属于特定的实例，不会被其他实例共享。

```python
# 创建服务器实例
server = MessageServer()

# 添加实例级别处理器
async def instance_handler(message):
    print("此处理器只属于这个特定实例")

server.register_message_handler(instance_handler)
```

## 消息处理器管理与持久化

### 重连保持处理器

`maim_message` 库特别设计了在连接断开和重连后保持消息处理器的能力。

```python
# 启动服务器
server = MessageServer()
server.register_message_handler(my_handler)
await server.run()

# 停止服务器
await server.stop()

# 重新启动 - 处理器仍然注册
await server.run()  # my_handler 仍然有效
```

### 清除处理器

如果需要，可以清除所有实例级别的处理器（类级别处理器会保留）：

```python
# 清除实例级别处理器
server.clear_handlers()  # 只清除实例处理器，类级别处理器保持不变
```

## 实用案例

### 插件系统

```python
# 为不同插件设置处理器
MessageServer.register_class_platform_handler("plugin1", plugin1_handler)
MessageServer.register_class_platform_handler("plugin2", plugin2_handler)

# 消息可以指定发送给特定插件
await server.broadcast_to_platform("plugin1", some_message)
```

### 多平台聊天机器人

```python
# 注册不同平台的处理逻辑
MessageClient.register_class_platform_handler("qq", qq_message_processor)
MessageClient.register_class_platform_handler("discord", discord_message_processor)

# 创建客户端并连接
client = MessageClient()
await client.connect("ws://127.0.0.1:8000/ws", "bot_client")

# 现在客户端会根据消息的平台字段自动使用相应的处理器
```

## 完整示例

可以查看 `examples/platform_handlers_example.py` 文件，其中包含完整的服务器和客户端处理器示例。
