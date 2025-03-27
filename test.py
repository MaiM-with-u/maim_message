import unittest
import asyncio
import aiohttp
from api import BaseMessageAPI
from message_base import (
    BaseMessageInfo,
    UserInfo,
    GroupInfo,
    FormatInfo,
    TemplateInfo,
    MessageBase,
    Seg,
)
from maim_message import global_api


class TestLiveAPI(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        """测试前的设置"""
        self.base_url = "http://localhost"
        self.receive_port = 18002  # 接收消息的端口
        self.send_port = 18000  # 发送消息的端口
        self.test_endpoint = "/api/message"

        # 创建并启动API实例
        self.api = BaseMessageAPI(host="0.0.0.0", port=self.receive_port)
        self.received_messages = []

        # 注册消息处理器
        async def message_handler(message):
            self.received_messages.append(message)

        self.api.register_message_handler(message_handler)

        # 启动API服务器任务
        self.server_task = asyncio.create_task(self.api.run())
        # 等待服务器启动
        await asyncio.sleep(1)

    async def asyncTearDown(self):
        """测试后的清理"""
        # 取消服务器任务
        self.server_task.cancel()
        try:
            await self.server_task
        except asyncio.CancelledError:
            pass

    async def test_send_and_receive_message(self):
        """测试向运行中的API发送消息并接收响应"""
        # 准备测试消息
        user_info = UserInfo(user_id=12345678, user_nickname="测试用户", platform="qq")
        group_info = GroupInfo(group_id=12345678, group_name="测试群", platform="qq")
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
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}:{self.send_port}{self.test_endpoint}",
                json=test_message,
            ) as response:
                response_data = await response.json()
                self.assertEqual(response.status, 200)
                self.assertEqual(response_data["status"], "success")
        while len(self.received_messages) == 0:
            await asyncio.sleep(1)
        received_message = self.received_messages[0]
        print(received_message)


async def message_handler(message):
    print(f"Received message: {message}")


def main():
    # 注册消息处理器
    global_api.register_message_handler(message_handler)

    # 使用同步方式运行（推荐）
    global_api.run_sync()


if __name__ == "__main__":
    main()
