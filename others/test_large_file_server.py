from maim_message import MessageBase, Seg, MessageServer
import asyncio
import os
import base64
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("test_large_file_server")


async def process_seg(seg: Seg):
    """处理消息段的递归函数"""
    if seg.type == "seglist":
        seglist = seg.data
        for single_seg in seglist:
            await process_seg(single_seg)

    # 打印消息段类型和大小
    if hasattr(seg, "data") and isinstance(seg.data, str):
        size_kb = len(seg.data) / 1024
        size_mb = size_kb / 1024
        logger.info(
            f"收到 {seg.type} 类型消息段，大小：{size_mb:.2f}MB ({size_kb:.2f}KB)"
        )


async def handle_message(message_data):
    """消息处理函数"""
    logger.info(f"收到消息，数据大小: {len(str(message_data)) / 1024 / 1024:.2f}MB")

    try:
        message = MessageBase.from_dict(message_data)
        await process_seg(message.message_segment)

        # 将处理后的消息回传给发送者
        platform = message.message_info.platform
        logger.info(f"向平台 {platform} 发送回复消息")
        await server.send_message(message)
    except Exception as e:
        logger.error(f"处理消息时出错: {e}", exc_info=True)


if __name__ == "__main__":
    # 创建服务器实例，不使用SSL，设置最大消息大小为100MB
    server = MessageServer(
        host="0.0.0.0",
        port=8099,
        # ssl_certfile="./ssl/server.crt",
        # ssl_keyfile="./ssl/server.key",
        mode="ws",
    )

    # 注册消息处理器
    server.register_message_handler(handle_message)

    logger.info("大文件传输测试服务器启动在 ws://0.0.0.0:8091")
    logger.info("最大消息大小: 100MB")

    # 运行服务器
    server.run_sync()
