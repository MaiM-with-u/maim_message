"""
Router 自定义消息测试示例
演示如何通过 Router 发送和接收自定义消息类型
"""

from maim_message import (
    BaseMessageInfo,
    UserInfo,
    GroupInfo,
    FormatInfo,
    MessageBase,
    Seg,
    Router,
    RouteConfig,
    TargetConfig,
)
import asyncio
import uuid


def construct_normal_message(platform):
    """构造普通MessageBase消息"""
    # 构造用户信息
    user_info = UserInfo(
        platform=platform,
        user_id="12345678",
        user_nickname="路由测试用户",
    )

    # 构造群组信息
    group_info = GroupInfo(
        platform=platform,
        group_id="87654321",
        group_name="路由测试群组",
    )

    # 构造格式信息
    format_info = FormatInfo(
        content_format=["text"],
        accept_format=["text"],
    )

    # 构造消息信息
    message_info = BaseMessageInfo(
        platform=platform,
        message_id=str(uuid.uuid4()),
        time=int(asyncio.get_event_loop().time()),
        group_info=group_info,
        user_info=user_info,
        format_info=format_info,
    )

    # 构造消息段
    message_segment = Seg(
        "seglist",
        [
            Seg("text", "这是通过Router发送的普通消息"),
        ],
    )

    # 构造完整消息
    message = MessageBase(
        message_info=message_info,
        message_segment=message_segment,
        raw_message="这是通过Router发送的普通消息",
    )
    
    return message


async def handle_normal_message(message):
    """处理普通消息的函数"""
    print(f"收到普通消息: {message}")


async def handle_status_response(message):
    """处理状态响应的自定义消息处理函数"""
    print("\n收到状态响应:")
    content = message.get("content", {})
    print(f"  状态: {content.get('status')}")
    print(f"  版本: {content.get('version')}")
    print(f"  运行时间: {content.get('uptime')} 秒")
    print(f"  请求ID: {content.get('request_id')}")


async def handle_command_response(message):
    """处理命令响应的自定义消息处理函数"""
    print("\n收到命令响应:")
    content = message.get("content", {})
    print(f"  命令: {content.get('command')}")
    print(f"  状态: {content.get('status')}")
    print(f"  结果: {content.get('result')}")
    print(f"  命令ID: {content.get('command_id')}")


async def main():
    # 配置路由
    route_config = RouteConfig(
        route_config={
            "test_platform": TargetConfig(
                url="ws://127.0.0.1:8090/ws",  # 使用ws协议
                token=None,  # 如果需要token验证则在这里设置
            ),
        }
    )

    # 创建路由器实例
    router = Router(route_config)

    # 注册消息处理器
    router.register_class_handler(handle_normal_message)
    
    # 注册自定义消息类型处理器
    router.register_custom_message_handler("status_response", handle_status_response)
    router.register_custom_message_handler("command_response", handle_command_response)

    # 启动路由器（会自动连接所有配置的平台）
    router_task = asyncio.create_task(router.run())

    # 等待连接建立
    await asyncio.sleep(2)
    
    platform = "test_platform"
    
    try:
        # 循环发送测试消息
        while True:
            print("\n===== 测试菜单 =====")
            print("1. 发送普通消息")
            print("2. 发送状态请求")
            print("3. 发送命令请求")
            print("q. 退出")
            
            choice = input("请选择操作: ")
            
            if choice == "1":
                # 发送普通消息
                message = construct_normal_message(platform)
                print("发送普通消息...")
                await router.send_message(message)
                
            elif choice == "2":
                # 发送状态请求
                request_id = str(uuid.uuid4())[:8]
                status_request = {
                    "request_id": request_id,
                    "timestamp": asyncio.get_event_loop().time()
                }
                print(f"发送状态请求 (ID: {request_id})...")
                await router.send_custom_message(platform, "status_request", status_request)
                
            elif choice == "3":
                # 发送命令请求
                command = input("输入命令名称 (如 'restart', 'status'): ")
                args = input("输入命令参数 (用逗号分隔): ").split(",")
                command_id = str(uuid.uuid4())[:8]
                
                command_request = {
                    "command": command,
                    "args": args,
                    "command_id": command_id,
                    "timestamp": asyncio.get_event_loop().time()
                }
                print(f"发送命令请求 '{command}' (ID: {command_id})...")
                await router.send_custom_message(platform, "command", command_request)
                
            elif choice.lower() == "q":
                print("退出...")
                break
                
            # 给服务器一点时间来响应
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        print("接收到中断信号，正在退出...")
    finally:
        # 关闭客户端连接
        await router.stop()
        if not router_task.done():
            router_task.cancel()
            try:
                await router_task
            except asyncio.CancelledError:
                pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("程序已终止")
