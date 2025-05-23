"""
重构后的消息服务器和客户端模块，使用统一的通信接口
"""

import asyncio
import logging
from typing import Dict, Any, Callable, List, Optional, Literal

from .message_base import MessageBase
from .ws_connection import WebSocketServer, WebSocketClient
from .tcp_connection import TCPServerConnection, TCPClientConnection
from .log_utils import get_logger, setup_logger

logger = get_logger()


class BaseMessageHandler:
    """消息处理基类"""

    def __init__(self):
        self.message_handlers: List[Callable] = []
        self.background_tasks = set()

    def register_message_handler(self, handler: Callable):
        """注册消息处理函数"""
        if handler not in self.message_handlers:
            self.message_handlers.append(handler)

    async def process_message(self, message: Dict[str, Any]):
        """处理单条消息"""
        tasks = []

        # 处理全局处理器
        for handler in self.message_handlers:
            try:
                result = handler(message)
                if asyncio.iscoroutine(result):
                    task = asyncio.create_task(result)
                    tasks.append(task)
                    self.background_tasks.add(task)
                    task.add_done_callback(self.background_tasks.discard)
            except Exception as e:
                logger.error(f"处理消息时出错: {e}")
                import traceback

                logger.debug(traceback.format_exc())

        # 处理特定平台的处理器
        platform = None
        try:
            # 尝试从消息中获取平台信息
            if isinstance(message, dict):
                if "message_info" in message and isinstance(
                    message["message_info"], dict
                ):
                    platform = message["message_info"].get("platform")
                elif "platform" in message:
                    platform = message.get("platform")

        except Exception as e:
            logger.error(f"解析消息平台信息时出错: {e}")

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _handle_message(self, message: Dict[str, Any]):
        """后台处理单个消息"""
        try:
            await self.process_message(message)
        except Exception as e:
            raise RuntimeError(str(e)) from e


class MessageServer(BaseMessageHandler):
    """消息服务器，支持 WebSocket 和 TCP 两种模式"""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 18000,
        enable_token=False,
        app=None,
        path: str = "/ws",
        ssl_certfile: Optional[str] = None,
        ssl_keyfile: Optional[str] = None,
        mode: Literal["ws", "tcp"] = "ws",
        custom_logger: Optional[logging.Logger] = None,
        enable_custom_uvicorn_logger: Optional[bool] = False,
    ):
        super().__init__()
        # 设置日志
        if custom_logger:
            setup_logger(external_logger=custom_logger)
        # 更新全局logger引用
        global logger
        logger = get_logger()

        self.host = host
        self.port = port
        self.mode = mode
        self._running = False

        # 创建适当的连接实现
        if mode == "ws":
            self.connection = WebSocketServer(
                host=host,
                port=port,
                path=path,
                app=app,
                ssl_certfile=ssl_certfile,
                ssl_keyfile=ssl_keyfile,
                enable_token=enable_token,
                enable_custom_uvicorn_logger=enable_custom_uvicorn_logger,
            )
        else:  # mode == "tcp"
            self.connection = TCPServerConnection(
                host=host, port=port, enable_token=enable_token
            )

        # 注册消息处理器
        self.connection.register_message_handler(self.process_message)

    def register_message_handler(self, handler: Callable):
        """注册实例级别的消息处理器"""
        if handler not in self.message_handlers:
            self.message_handlers.append(handler)

    async def verify_token(self, token: str) -> bool:
        """验证令牌是否有效 (仅WebSocket模式)"""
        if self.mode == "ws":
            return await self.connection.verify_token(token)
        return True

    def add_valid_token(self, token: str):
        """添加有效令牌 (仅WebSocket模式)"""
        self.connection.add_valid_token(token)

    def remove_valid_token(self, token: str):
        """移除有效令牌 (仅WebSocket模式)"""
        self.connection.remove_valid_token(token)

    async def broadcast_message(self, message: Dict[str, Any]):
        """广播消息给所有连接的客户端"""
        await self.connection.broadcast_message(message)

    async def broadcast_to_platform(self, platform: str, message: Dict[str, Any]):
        """向指定平台的所有客户端广播消息"""
        await self.connection.send_message(platform, message)

    async def send_message(self, message: MessageBase):
        """发送消息给指定平台"""
        await self.connection.send_message(
            message.message_info.platform, message.to_dict()
        )

    def run_sync(self):
        """同步方式运行服务器 (仅WebSocket模式)"""
        if self.mode == "ws":
            self.connection.run_sync()
        else:
            logger.error("TCP模式不支持同步运行，请使用异步方式")
            raise RuntimeError("TCP模式不支持同步运行，请使用异步方式")

    async def run(self):
        """异步方式运行服务器"""
        # 获取最新的logger引用
        global logger
        logger = get_logger()

        self._running = True
        try:
            await self.connection.start()
        except KeyboardInterrupt:
            logger.info("收到键盘中断，服务器已停止")
            await self.stop()
            raise
        except Exception as e:
            await self.stop()
            raise RuntimeError(f"服务器运行错误: {str(e)}") from e

    async def start_server(self):
        """启动服务器的异步方法"""
        if not self._running:
            self._running = True
            await self.run()

    async def stop(self):
        """停止服务器"""
        self._running = False

        # 停止连接
        await self.connection.stop()

        # 取消所有后台任务
        for task in self.background_tasks:
            if not task.done():
                task.cancel()

        # 等待所有任务完成
        await asyncio.gather(*self.background_tasks, return_exceptions=True)
        self.background_tasks.clear()

        # 注意：不清除message_handlers和platform_handlers，以确保重启服务器时处理器继续有效
        # 如果确实需要清除，请手动调用clear_handlers方法


class MessageClient(BaseMessageHandler):
    """消息客户端，支持 WebSocket 和 TCP 两种模式"""

    def __init__(
        self,
        mode: Literal["ws", "tcp"] = "ws",
        custom_logger: Optional[logging.Logger] = None,
    ):
        super().__init__()
        # 设置日志
        if custom_logger:
            setup_logger(external_logger=custom_logger)
        # 更新全局logger引用
        global logger
        logger = get_logger()

        self.mode = mode
        self.platform = None
        self._running = False
        self._connection_configured = False  # 标记连接是否已经配置过

        # 连接实现将在connect方法中创建，因为我们需要platform信息

    def register_message_handler(self, handler: Callable):
        """注册实例级别的消息处理器"""
        if handler not in self.message_handlers:
            self.message_handlers.append(handler)

    async def connect(
        self,
        url: str,
        platform: str,
        token: Optional[str] = None,
        ssl_verify: Optional[str] = None,
    ):
        """设置连接参数并连接到服务器"""
        self.platform = platform
        self._running = True

        # 根据URL协议决定使用哪种模式
        if url.startswith(("tcp://", "tcps://")):
            from urllib.parse import urlparse

            parsed = urlparse(url)
            host = parsed.hostname
            port = parsed.port or 18000

            # 创建TCP客户端，并传入token
            self.connection = TCPClientConnection(platform=platform, token=token)
            self.connection.register_message_handler(self.process_message)
            self.connection.set_target(host, port)
        else:
            # WebSocket模式
            self.connection = WebSocketClient()
            self.connection.register_message_handler(self.process_message)
            await self.connection.configure(
                url=url,
                platform=platform,
                token=token,
                ssl_verify=ssl_verify,
            )

        # 标记连接已配置
        self._connection_configured = True

    async def run(self):
        """维持连接和消息处理"""
        # 获取最新的logger引用
        global logger
        logger = get_logger()

        if not hasattr(self, "connection"):
            raise RuntimeError("请先调用connect方法连接到服务器")

        self._running = True
        await self.connection.start()

    async def stop(self):
        """停止客户端"""
        self._running = False

        # 停止连接
        if hasattr(self, "connection"):
            await self.connection.stop()
            # 不清除连接，以便保持处理器注册状态，便于重连

        # 取消所有后台任务
        for task in self.background_tasks:
            if not task.done():
                task.cancel()

        # 等待所有任务完成
        await asyncio.gather(*self.background_tasks, return_exceptions=True)
        self.background_tasks.clear()

        # 注意：不清除message_handlers和platform_handlers，以确保重连时处理器继续有效

    async def send_message(self, message: Dict[str, Any]) -> bool:
        """发送消息到服务器"""
        if not hasattr(self, "connection"):
            raise RuntimeError("请先调用connect方法连接到服务器")

        return await self.connection.send_message(self.platform, message)

    def is_connected(self) -> bool:
        """
        判断当前连接是否有效（存活）

        Returns:
            bool: 连接是否有效
        """
        if not hasattr(self, "connection") or not self._connection_configured:
            return False

        return self.connection.is_connected()
