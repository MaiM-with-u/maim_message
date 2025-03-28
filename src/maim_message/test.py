import unittest
import asyncio
import aiohttp
from .api import BaseMessageAPI
from .message_base import (
    BaseMessageInfo,
    UserInfo,
    GroupInfo,
    FormatInfo,
    TemplateInfo,
    MessageBase,
    Seg,
)


send_url = "http://localhost"
receive_port = 18002  # 接收消息的端口
send_port = 8090  # 发送消息的端口
test_endpoint = "/api/message"

# 创建并启动API实例
api = BaseMessageAPI(host="0.0.0.0", port=receive_port)


class TestLiveAPI(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        """测试前的设置"""
        self.received_messages = []

        async def message_handler(message):
            self.received_messages.append(message)

        self.api = api
        self.api.register_message_handler(message_handler)
        self.server_task = asyncio.create_task(self.api.run())
        try:
            await asyncio.wait_for(asyncio.sleep(1), timeout=5)
        except asyncio.TimeoutError:
            self.skipTest("服务器启动超时")

    async def asyncTearDown(self):
        """测试后的清理"""
        if hasattr(self, "server_task"):
            await self.api.stop()  # 先调用正常的停止流程
            if not self.server_task.done():
                self.server_task.cancel()
                try:
                    await asyncio.wait_for(self.server_task, timeout=100)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass

    async def test_send_and_receive_message(self):
        """测试向运行中的API发送消息并接收响应"""
        # 准备测试消息
        user_info = UserInfo(user_id=12345678, user_nickname="测试用户", platform="qq1")
        group_info = GroupInfo(group_id=12345678, group_name="测试群", platform="qq1")
        format_info = FormatInfo(
            content_format=["text"], accept_format=["text", "emoji", "reply"]
        )
        template_info = None
        message_info = BaseMessageInfo(
            platform="qq",
            message_id=12345678,
            time=12345678,
            group_info=group_info,
            user_info=user_info,
            format_info=format_info,
            template_info=template_info,
        )
        message = MessageBase(
            message_info=message_info,
            raw_message="测试消息",
            message_segment=Seg(type="text", data="测试消息"),
        )
        test_message = message.to_dict()

        # 发送测试消息到发送端口

        await self.api.send_message(
            f"{send_url}:{send_port}{test_endpoint}", test_message
        )
        try:
            async with asyncio.timeout(30):  # 设置5秒超时
                while len(self.received_messages) == 0:
                    await asyncio.sleep(0.1)
                received_message = self.received_messages[0]
                print(received_message)
                self.received_messages.clear()
        except asyncio.TimeoutError:
            self.fail("等待接收消息超时")


if __name__ == "__main__":
    unittest.main()
