from maim_message import MessageBase, Seg, MessageServer
import asyncio


async def process_seg(seg: Seg):
    """处理消息段的递归函数"""
    if seg.type == "seglist":
        seglist = seg.data
        for single_seg in seglist:
            await process_seg(single_seg)
    # 实际内容处理逻辑
    if seg.type == "voice":
        seg.type = "text"
        seg.data = "[音频]"
    elif seg.type == "at":
        seg.type = "text"
        seg.data = "[@某人]"


async def handle_message(message_data):
    """消息处理函数"""
    print(message_data)
    message = MessageBase.from_dict(message_data)
    await process_seg(message.message_segment)

    # 将处理后的消息发送给特定平台
    await server.send_message(message)  # MessageServer已经会处理平台路由


if __name__ == "__main__":
    # 创建服务器实例，使用 TCP 模式
    server = MessageServer(
        host="0.0.0.0",
        port=8090,
        mode="tcp",  # 使用 TCP 模式
        enable_token=True,  # 启用令牌认证
    )

    # 添加有效令牌
    server.add_valid_token("test_token_1")
    server.add_valid_token("test_token_2")

    # 注册消息处理器
    server.register_message_handler(handle_message)

    print("TCP 服务器启动在 tcp://0.0.0.0:8090")
    print("已启用令牌认证，有效令牌: test_token_1, test_token_2")
    # 运行服务器
    asyncio.run(server.run())
