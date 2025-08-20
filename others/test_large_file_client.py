from maim_message import (
    BaseMessageInfo,
    UserInfo,
    GroupInfo,
    FormatInfo,
    TemplateInfo,
    MessageBase,
    Seg,
    Router,
    RouteConfig,
    TargetConfig,
)
import asyncio
import os
import base64
import logging
import time
import random

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("test_large_file_client")


def generate_random_data(size_mb):
    """生成指定大小的随机数据（用于模拟大文件）"""
    # 生成随机字节
    random_bytes = os.urandom(size_mb * 1024 * 1024)
    # 转换为base64字符串
    return base64.b64encode(random_bytes).decode("utf-8")


def construct_large_file_message(platform, file_size_mb=50):
    """构造包含大文件的消息"""
    # 生成随机数据作为文件内容
    logger.info(f"生成 {file_size_mb}MB 的随机数据...")
    start_time = time.time()
    file_data = generate_random_data(file_size_mb)
    logger.info(f"数据生成完成，耗时: {time.time() - start_time:.2f}秒")

    # 基本信息
    user_info = UserInfo(
        platform=platform,
        user_id="12348765",
        user_nickname="大文件测试用户",
        user_cardname="大文件测试",
    )

    group_info = GroupInfo(
        platform=platform,
        group_id="12345678",
        group_name="大文件测试群组",
    )

    format_info = FormatInfo(
        content_format=["text", "image", "file"],
        accept_format=["text", "image", "file"],
    )

    message_info = BaseMessageInfo(
        platform=platform,
        message_id=f"largefile_{int(time.time())}",
        time=int(time.time()),
        group_info=group_info,
        user_info=user_info,
        format_info=format_info,
        template_info=None,
        additional_config={"file_size_mb": file_size_mb},
    )

    # 创建包含大文件的消息段
    message_segment = Seg(
        "seglist",
        [
            Seg("text", f"这是一个 {file_size_mb}MB 大小的文件测试"),
            Seg("file", file_data),  # 使用生成的随机数据
        ],
    )

    # 创建消息
    message = MessageBase(
        message_info=message_info,
        message_segment=message_segment,
        raw_message=f"大文件传输测试: {file_size_mb}MB",
    )

    return message


async def message_handler(message):
    """消息处理函数"""
    logger.info(f"收到服务器回复消息")

    # 检查消息段
    if message.message_segment and message.message_segment.type == "seglist":
        for seg in message.message_segment.data:
            if seg.type == "file":
                size_mb = len(seg.data) / 1024 / 1024
                logger.info(f"收到文件数据，大小: {size_mb:.2f}MB")


# 配置路由
route_config = RouteConfig(
    route_config={
        "large_file_test": TargetConfig(
            url="ws://127.0.0.1:8099/ws",  # 连接到大文件测试服务器
            token=None,
        ),
    }
)

# 创建路由器实例
router = Router(route_config)


async def main():
    # 注册消息处理器
    router.register_class_handler(message_handler)

    try:
        # 启动路由器
        router_task = asyncio.create_task(router.run())
        logger.info("正在连接到服务器...")

        # 等待连接建立
        await asyncio.sleep(2)
        logger.info("连接已建立")

        # 测试不同大小的文件传输
        file_sizes = [1, 5, 20, 50, 80]  # MB

        for size in file_sizes:
            logger.info(f"======= 测试 {size}MB 大小的文件传输 =======")
            try:
                # 构造并发送大文件消息
                message = construct_large_file_message("large_file_test", size)
                start_time = time.time()
                await router.send_message(message)
                logger.info(f"发送完成，耗时: {time.time() - start_time:.2f}秒")

                # 等待服务器处理并回复
                await asyncio.sleep(3)

            except Exception as e:
                logger.error(f"发送 {size}MB 文件失败: {e}", exc_info=True)

            logger.info(f"测试 {size}MB 文件传输完成")
            logger.info("====================================")

            # 不同测试之间稍作间隔
            await asyncio.sleep(2)

        # 最后测试接近上限的文件大小 (95MB)
        logger.info("======= 测试 95MB 大小的文件传输 (接近限制) =======")
        try:
            message = construct_large_file_message("large_file_test", 95)
            start_time = time.time()
            await router.send_message(message)
            logger.info(f"发送完成，耗时: {time.time() - start_time:.2f}秒")
            await asyncio.sleep(5)  # 给服务器更多时间处理
        except Exception as e:
            logger.error(f"发送 95MB 文件失败: {e}", exc_info=True)

        logger.info("大文件传输测试完成")

        # 等待用户手动关闭
        logger.info("按Ctrl+C结束测试...")
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info("用户中断测试")
    finally:
        logger.info("正在关闭连接...")
        await router.stop()
        logger.info("已关闭所有连接")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("程序被用户中断")
