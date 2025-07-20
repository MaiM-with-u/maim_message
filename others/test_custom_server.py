"""
自定义消息测试服务器
演示如何接收和发送自定义消息类型
"""

from maim_message import MessageServer, MessageBase
import asyncio


async def handle_status_request(message):
    """处理状态请求的自定义处理函数"""
    print(f"收到状态请求: {message}")

    # 从自定义消息中提取内容
    content = message.get("content", {})
    request_id = content.get("request_id")

    # 构建响应数据
    response_data = {
        "status": "online",
        "version": "1.0.0",
        "uptime": 3600,
        "request_id": request_id,
        "timestamp": asyncio.get_event_loop().time(),
    }

    # 发送自定义响应消息
    platform = message.get("platform")
    await server.send_custom_message(platform, "status_response", response_data)
    print(f"已发送状态响应到平台 {platform}")


async def handle_command(message):
    """处理命令请求的自定义处理函数"""
    print(f"收到命令请求: {message}")

    # 从自定义消息中提取内容
    content = message.get("content", {})
    command = content.get("command")
    args = content.get("args", [])
    command_id = content.get("command_id")

    # 构建响应数据
    response_data = {
        "command": command,
        "status": "executed" if command != "invalid" else "failed",
        "result": f"执行了命令 {command}，参数: {args}"
        if command != "invalid"
        else "无效命令",
        "command_id": command_id,
        "timestamp": asyncio.get_event_loop().time(),
    }

    # 发送自定义响应消息
    platform = message.get("platform")
    await server.send_custom_message(platform, "command_response", response_data)
    print(f"已发送命令响应到平台 {platform}")


async def handle_normal_message(message_data):
    """处理普通MessageBase类型消息的函数"""
    try:
        # 尝试解析为MessageBase对象
        message = MessageBase.from_dict(message_data)
        print(
            f"收到普通消息: 来自 {message.message_info.platform} 的 {message.message_info.user_info.user_nickname}"
        )

        # 简单回复
        await server.send_message(message)
        print("已回复普通消息")
    except Exception as e:
        print(f"处理普通消息时出错: {e}")


if __name__ == "__main__":
    # 创建服务器实例
    server = MessageServer(
        host="0.0.0.0",
        port=8090,
        mode="ws",
    )

    # 注册普通消息处理器
    server.register_message_handler(handle_normal_message)

    # 注册自定义消息类型的处理器
    server.register_custom_message_handler("status_request", handle_status_request)
    server.register_custom_message_handler("command", handle_command)

    print("自定义消息测试服务器启动在 ws://0.0.0.0:8090")
    print("已注册处理器:")
    print("- 普通消息: handle_normal_message")
    print("- 自定义消息 'status_request': handle_status_request")
    print("- 自定义消息 'command': handle_command")

    # 运行服务器
    server.run_sync()
