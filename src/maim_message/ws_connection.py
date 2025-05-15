"""
WebSocket通信实现模块，提供基于WebSocket的服务器和客户端实现
"""

import asyncio
import logging
import ssl
import aiohttp
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Dict, Any, Callable, List, Set, Optional, Union

from .connection_interface import (
    ServerConnectionInterface,
    ClientConnectionInterface,
    BaseConnection,
)
from .log_utils import get_logger, configure_uvicorn_logging, get_uvicorn_log_config

logger = get_logger()


class WebSocketServer(BaseConnection, ServerConnectionInterface):
    """基于WebSocket的服务器实现"""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 18000,
        path: str = "/ws",
        app: Optional[FastAPI] = None,
        ssl_certfile: Optional[str] = None,
        ssl_keyfile: Optional[str] = None,
        enable_token: bool = False,
    ):
        super().__init__()
        self.host = host
        self.port = port
        self.path = path
        self.app = app or FastAPI()
        self.own_app = app is None
        self.ssl_certfile = ssl_certfile
        self.ssl_keyfile = ssl_keyfile

        # WebSocket连接管理
        self.active_websockets: Set[WebSocket] = set()
        self.platform_websockets: Dict[str, WebSocket] = {}

        # 令牌验证
        self.enable_token = enable_token
        self.valid_tokens: Set[str] = set()

        # 服务器实例
        self.server = None

        # 设置WebSocket路由
        self._setup_routes()
        # 获取最新的logger实例
        global logger
        logger = get_logger()

    def _setup_routes(self):
        """设置WebSocket路由"""

        @self.app.websocket(self.path)
        async def websocket_endpoint(websocket: WebSocket):
            """处理WebSocket连接"""
            await websocket.accept()

            # 获取平台标识
            platform = websocket.headers.get("platform", "unknown")

            # 如果开启了令牌验证，检查令牌
            if self.enable_token:
                auth_header = websocket.headers.get("authorization")
                if not auth_header or not await self.verify_token(auth_header):
                    await websocket.close(code=1008, reason="无效的令牌")
                    return

            # 记录连接
            self.active_websockets.add(websocket)
            if platform != "unknown":
                # 如果已存在相同平台的连接，关闭旧连接
                if platform in self.platform_websockets:
                    old_ws = self.platform_websockets[platform]
                    await old_ws.close(code=1000, reason="新连接取代")
                    if old_ws in self.active_websockets:
                        self.active_websockets.remove(old_ws)

                self.platform_websockets[platform] = websocket
                logger.info(f"平台 {platform} WebSocket已连接")
            else:
                logger.info("新WebSocket连接已建立")

            try:
                # 持续处理消息
                while True:
                    message = await websocket.receive_json()
                    task = asyncio.create_task(self.process_message(message))
                    self.add_background_task(task)

            except WebSocketDisconnect:
                logger.info(f"WebSocket连接断开: {platform}")
            except Exception as e:
                logger.error(f"WebSocket处理错误: {e}")
                import traceback

                logger.debug(traceback.format_exc())
            finally:
                self._remove_websocket(websocket, platform)

    def _remove_websocket(self, websocket: WebSocket, platform: str):
        """从所有集合中移除websocket"""
        if websocket in self.active_websockets:
            self.active_websockets.remove(websocket)
        if platform in self.platform_websockets:
            if self.platform_websockets[platform] == websocket:
                del self.platform_websockets[platform]

    async def verify_token(self, token: str) -> bool:
        """验证令牌是否有效"""
        if not self.enable_token:
            return True
        return token in self.valid_tokens

    def add_valid_token(self, token: str):
        """添加有效令牌"""
        # logger.info(f"添加有效令牌: {token}")
        self.valid_tokens.add(token)

    def remove_valid_token(self, token: str):
        """移除有效令牌"""
        self.valid_tokens.discard(token)

    async def start(self):
        """异步方式启动服务器"""
        # 获取最新的logger引用
        global logger
        logger = get_logger()

        self._running = True

        # 如果使用外部应用，只需设置标志位，不启动uvicorn
        if not self.own_app:
            logger.info("使用外部FastAPI应用，仅注册WebSocket路由")
            return

        # 获取当前日志级别
        log_level = get_logger().level

        # 为uvicorn准备日志配置
        log_config = get_uvicorn_log_config(log_level)

        # 配置服务器
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            ssl_certfile=self.ssl_certfile,
            ssl_keyfile=self.ssl_keyfile,
            log_config=log_config,
        )

        # 确保uvicorn日志系统使用我们的配置
        configure_uvicorn_logging(log_level)

        # 启动服务器
        self.server = uvicorn.Server(config)
        await self.server.serve()

    def run_sync(self):
        """同步方式运行服务器"""
        if not self.own_app:
            logger.info("使用外部FastAPI应用，仅注册WebSocket路由")
            self._running = True
            return

        # 获取当前日志级别
        log_level = get_logger().level

        # 为uvicorn准备日志配置
        log_config = get_uvicorn_log_config(log_level)

        # 打印SSL配置信息
        if self.ssl_certfile and self.ssl_keyfile:
            logger.info(
                f"启用SSL: certfile={self.ssl_certfile}, keyfile={self.ssl_keyfile}"
            )

        # 配置并启动服务器，使用我们的日志配置
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            ssl_certfile=self.ssl_certfile,
            ssl_keyfile=self.ssl_keyfile,
            log_config=log_config,
        )

        # 确保uvicorn日志系统使用我们的配置
        configure_uvicorn_logging(log_level)

        server = uvicorn.Server(config)
        server.run()

    async def stop(self):
        """停止服务器"""
        if not self._running:
            return

        self._running = False

        # 关闭所有WebSocket连接
        for websocket in list(self.active_websockets):
            try:
                await websocket.close(code=1000, reason="服务器关闭")
            except Exception:
                pass

        self.active_websockets.clear()
        self.platform_websockets.clear()

        # 清理后台任务
        await self.cleanup_tasks()

        # 仅当使用内部应用且服务器实例存在时尝试关闭服务器
        if self.own_app and self.server and hasattr(self.server, "shutdown"):
            await self.server.shutdown()

    async def broadcast_message(self, message: Dict[str, Any]):
        """广播消息给所有连接的客户端"""
        disconnected = set()
        for websocket in self.active_websockets:
            try:
                await websocket.send_json(message)
            except Exception:
                disconnected.add(websocket)

        for websocket in disconnected:
            self.active_websockets.remove(websocket)

    async def send_message(self, target: str, message: Dict[str, Any]) -> bool:
        """向指定平台发送消息"""
        if target not in self.platform_websockets:
            logger.warning(f"未找到目标平台: {target}")
            return False

        try:
            await self.platform_websockets[target].send_json(message)
            return True
        except Exception as e:
            logger.error(f"发送消息到平台 {target} 失败: {e}")
            self._remove_websocket(self.platform_websockets[target], target)
            return False


class WebSocketClient(BaseConnection, ClientConnectionInterface):
    """基于WebSocket的客户端实现"""

    def __init__(self):
        super().__init__()

        # 连接配置
        self.url = None
        self.platform = None
        self.token = None
        self.ssl_verify = None
        self.headers = {}

        # WebSocket连接
        self.ws = None
        self.ws_connected = False
        self.session = None  # 保存ClientSession实例

        # 重连设置
        self.reconnect_interval = 5
        self.retry_count = 0

    async def configure(
        self,
        url: str,
        platform: str,
        token: Optional[str] = None,
        ssl_verify: Optional[str] = None,
    ):
        """配置连接参数"""
        self.url = url
        self.platform = platform
        self.token = token
        self.ssl_verify = ssl_verify

        # 设置请求头
        self.headers = {"platform": platform}
        if token:
            self.headers["Authorization"] = str(token)

    async def connect(self) -> bool:
        """连接到WebSocket服务器"""
        # 获取最新的logger引用
        global logger
        logger = get_logger()

        if not self.url or not self.platform:
            raise ValueError("连接前必须先调用configure方法配置连接参数")

        # 设置SSL上下文
        ssl_context = None
        if self.url.startswith("wss://"):
            ssl_context = ssl.create_default_context()
            if self.ssl_verify:
                logger.info(f"使用证书验证: {self.ssl_verify}")
                ssl_context.load_verify_locations(self.ssl_verify)
            else:
                logger.warning("警告: 未使用证书验证，已禁用证书验证")
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE

        try:
            logger.info(f"正在连接到 {self.url}")
            logger.debug(f"使用的头部信息: {self.headers}")

            # 配置连接
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            connector = aiohttp.TCPConnector(
                ssl=ssl_context, enable_cleanup_closed=True
            )

            # 创建会话并连接
            if self.session and not self.session.closed:
                await self.session.close()

            self.session = aiohttp.ClientSession(
                connector=connector, timeout=timeout, headers=self.headers
            )

            self.ws = await self.session.ws_connect(
                self.url,
                heartbeat=30,
                compress=15,
            )

            self.ws_connected = True
            self.retry_count = 0
            logger.info(f"已成功连接到 {self.url}")
            return True

        except aiohttp.ClientError as e:
            if isinstance(e, aiohttp.ClientConnectorError):
                logger.error(
                    f"无法建立连接: {e.strerror if hasattr(e, 'strerror') else str(e)}"
                )
            elif isinstance(e, aiohttp.ClientSSLError):
                logger.error(f"SSL错误: {str(e)}")
            else:
                logger.error(f"连接错误: {str(e)}")

            # 确保在错误情况下关闭会话
            if self.session and not self.session.closed:
                await self.session.close()
                self.session = None
            return False

        except Exception as e:
            logger.error(f"连接时发生未预期的错误: {str(e)}")
            import traceback

            logger.debug(traceback.format_exc())

            # 确保在错误情况下关闭会话
            if self.session and not self.session.closed:
                await self.session.close()
                self.session = None
            return False

    async def start(self):
        """开始接收消息循环"""
        # 获取最新的logger引用
        global logger
        logger = get_logger()

        if not self.ws_connected:
            await self.connect()

        self._running = True

        while self._running:
            try:
                if not self.ws_connected:
                    success = await self.connect()
                    if not success:
                        retry_delay = min(
                            30,
                            self.reconnect_interval * (2 ** min(self.retry_count, 5)),
                        )
                        logger.info(f"等待 {retry_delay} 秒后重试...")
                        await asyncio.sleep(retry_delay)
                        self.retry_count += 1
                        continue

                # 持续接收消息
                async for msg in self.ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        try:
                            data = msg.json()
                            logger.debug(f"接收到消息: {data}")
                            task = asyncio.create_task(self.process_message(data))
                            self.add_background_task(task)
                        except Exception as e:
                            logger.error(f"处理消息时出错: {e}")
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        logger.error(f"WebSocket连接错误: {self.ws.exception()}")
                        break
                    elif msg.type == aiohttp.WSMsgType.CLOSED:
                        logger.warning("WebSocket连接已关闭")
                        break

                # 如果到达这里，连接已关闭
                self.ws_connected = False

            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"WebSocket连接发生错误: {e}")
                self.ws_connected = False
                self.retry_count += 1

            # 等待重连
            if self._running and not self.ws_connected:
                retry_delay = min(
                    30, self.reconnect_interval * (2 ** min(self.retry_count, 5))
                )
                logger.info(f"等待 {retry_delay} 秒后重试...")
                await asyncio.sleep(retry_delay)

    async def stop(self):
        """停止客户端"""
        self._running = False

        # 关闭WebSocket连接
        if self.ws and not self.ws.closed:
            await self.ws.close()

        # 关闭ClientSession
        if self.session and not self.session.closed:
            await self.session.close()

        self.ws_connected = False
        self.ws = None
        self.session = None

        # 清理后台任务
        await self.cleanup_tasks()

    async def send_message(self, target: str, message: Dict[str, Any]) -> bool:
        """发送消息到服务器"""
        if not self.ws_connected:
            raise RuntimeError("未连接到服务器")

        try:
            await self.ws.send_json(message)
            return True
        except Exception as e:
            self.ws_connected = False
            logger.error(f"发送消息失败: {e}")
            return False

    def is_connected(self) -> bool:
        """
        判断当前连接是否有效（存活）

        Returns:
            bool: 连接是否有效
        """
        return self.ws_connected and self.ws is not None and not self.ws.closed
