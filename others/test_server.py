from maim_message import MessageBase, Seg, MessageServer
import os


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
    message = MessageBase.from_dict(message_data)
    await process_seg(message.message_segment)

    # 将处理后的消息广播给所有连接的客户端
    await server.send_message(message)


if __name__ == "__main__":
    # 创建服务器实例，不使用SSL
    server = MessageServer(
        host="0.0.0.0",
        port=8090,
        # ssl_certfile="./ssl/server.crt",
        # ssl_keyfile="./ssl/server.key",
        mode="ws",
    )

    # 注册消息处理器
    server.register_message_handler(handle_message)

    print("服务器启动在 ws://0.0.0.0:8090")
    # 运行服务器
    server.run_sync()
