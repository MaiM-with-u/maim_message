from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Dict, Any, Callable, List, Set, Optional, Literal
import aiohttp
import asyncio
import uvicorn
import json
from .message_base import MessageBase
from .tcp_base import TCPServer, TCPClient


class BaseMessageHandler:
    """消息处理基类"""

    def __init__(self):
        self.message_handlers: List[Callable] = []
        self.background_tasks = set()

    def register_message_handler(self, handler: Callable):
        """注册消息处理函数"""
        self.message_handlers.append(handler)

    async def process_message(self, message: Dict[str, Any]):
        """处理单条消息"""
        tasks = []
        for handler in self.message_handlers:
            try:
                tasks.append(handler(message))
            except Exception as e:
                raise RuntimeError(str(e)) from e
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

    _class_handlers: List[Callable] = []  # 类级别的消息处理器

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 18000,
        enable_token=False,
        app: Optional[FastAPI] = None,
        path: str = "/ws",
        ssl_certfile: Optional[str] = None,
        ssl_keyfile: Optional[str] = None,
        mode: Literal["ws", "tcp"] = "ws",
    ):
        super().__init__()
        self.message_handlers.extend(self._class_handlers)
        self.host = host
        self.port = port
        self.mode = mode

        # WebSocket 相关的属性
        self.path = path
        self.app = app or FastAPI()
        self.own_app = app is None
        self.active_websockets: Set[WebSocket] = set()
        self.platform_websockets: Dict[str, WebSocket] = {}
        self.valid_tokens: Set[str] = set()
        self.enable_token = enable_token
        self.ssl_certfile = ssl_certfile
        self.ssl_keyfile = ssl_keyfile

        # TCP 相关的属性
        self.tcp_server = TCPServer(host, port) if mode == "tcp" else None

        if mode == "ws":
            self._setup_routes()
        self._running = False

    @classmethod
    def register_class_handler(cls, handler: Callable):
        """注册类级别的消息处理器"""
        if handler not in cls._class_handlers:
            cls._class_handlers.append(handler)

    def register_message_handler(self, handler: Callable):
        """注册实例级别的消息处理器"""
        if self.mode == "tcp":
            self.tcp_server.register_message_handler(handler)
        else:
            if handler not in self.message_handlers:
                self.message_handlers.append(handler)

    async def verify_token(self, token: str) -> bool:
        if not self.enable_token:
            return True
        return token in self.valid_tokens

    def add_valid_token(self, token: str):
        self.valid_tokens.add(token)

    def remove_valid_token(self, token: str):
        self.valid_tokens.discard(token)

    def _setup_routes(self):
        """设置WebSocket路由"""

        # 使用传入的path作为WebSocket endpoint
        @self.app.websocket(self.path)
        async def websocket_endpoint(websocket: WebSocket):
            headers = dict(websocket.headers)
            token = headers.get("authorization")
            platform = headers.get("platform", "default")
            if self.enable_token:
                if not token or not await self.verify_token(token):
                    await websocket.close(code=1008, reason="Invalid or missing token")
                    return

            await websocket.accept()
            self.active_websockets.add(websocket)

            # 添加到platform映射
            if platform not in self.platform_websockets:
                self.platform_websockets[platform] = websocket

            try:
                while True:
                    message = await websocket.receive_json()
                    asyncio.create_task(self._handle_message(message))
            except WebSocketDisconnect:
                self._remove_websocket(websocket, platform)
            except Exception as e:
                self._remove_websocket(websocket, platform)
                raise RuntimeError(str(e)) from e
            finally:
                self._remove_websocket(websocket, platform)

    def _remove_websocket(self, websocket: WebSocket, platform: str):
        """从所有集合中移除websocket"""
        if websocket in self.active_websockets:
            self.active_websockets.remove(websocket)
        if platform in self.platform_websockets:
            if self.platform_websockets[platform] == websocket:
                del self.platform_websockets[platform]

    async def broadcast_message(self, message: Dict[str, Any]):
        disconnected = set()
        for websocket in self.active_websockets:
            try:
                await websocket.send_json(message)
            except Exception:
                disconnected.add(websocket)
        for websocket in disconnected:
            self.active_websockets.remove(websocket)

    async def broadcast_to_platform(self, platform: str, message: Dict[str, Any]):
        """向指定平台的所有客户端广播消息"""
        if self.mode == "ws":
            if platform not in self.platform_websockets:
                return

            disconnected = set()
            try:
                await self.platform_websockets[platform].send_json(message)
            except Exception:
                disconnected.add(self.platform_websockets[platform])

            # 清理断开的连接
            for websocket in disconnected:
                self._remove_websocket(websocket, platform)
        else:
            # TCP 模式下向指定平台发送消息
            await self.tcp_server.send_to_platform(platform, message)

    async def send_message(self, message: MessageBase):
        await self.broadcast_to_platform(
            message.message_info.platform, message.to_dict()
        )

    def run_sync(self):
        """同步方式运行服务器"""
        if self.mode == "ws":
            if not self.own_app:
                raise RuntimeError("当使用外部FastAPI实例时，请使用该实例的运行方法")

            # 设置详细的调试日志
            import logging

            logging.basicConfig(level=logging.DEBUG)
            uvicorn_logger = logging.getLogger("uvicorn")
            uvicorn_logger.setLevel(logging.DEBUG)
            uvicorn_logger.handlers = []
            uvicorn_logger.addHandler(logging.StreamHandler())

            # 打印SSL配置信息
            if self.ssl_certfile and self.ssl_keyfile:
                print(f"启用SSL支持:")
                print(f"证书文件: {self.ssl_certfile}")
                print(f"密钥文件: {self.ssl_keyfile}")

                # 验证证书文件
                import ssl

                try:
                    ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
                    ctx.load_cert_chain(self.ssl_certfile, self.ssl_keyfile)
                    print("SSL证书验证成功")
                except Exception as e:
                    print(f"SSL证书验证失败: {e}")

            # 配置并启动服务器
            config = uvicorn.Config(
                self.app,
                host=self.host,
                port=self.port,
                ssl_certfile=self.ssl_certfile,
                ssl_keyfile=self.ssl_keyfile,
                log_level="debug",
            )
            server = uvicorn.Server(config)
            server.run()
        else:
            # TCP 模式
            asyncio.run(self.tcp_server.start())

    async def run(self):
        """异步方式运行服务器"""
        self._running = True
        try:
            if self.mode == "ws":
                if self.own_app:
                    # 设置详细的调试日志
                    import logging

                    logging.basicConfig(level=logging.DEBUG)
                    uvicorn_logger = logging.getLogger("uvicorn")
                    uvicorn_logger.setLevel(logging.DEBUG)

                    # 打印SSL配置信息
                    if self.ssl_certfile and self.ssl_keyfile:
                        print(f"启用SSL支持:")
                        print(f"证书文件: {self.ssl_certfile}")
                        print(f"密钥文件: {self.ssl_keyfile}")

                        # 验证证书文件
                        import ssl

                        try:
                            ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
                            ctx.load_cert_chain(self.ssl_certfile, self.ssl_keyfile)
                            print("SSL证书验证成功")
                        except Exception as e:
                            print(f"SSL证书验证失败: {e}")

                    # 配置并启动服务器
                    config = uvicorn.Config(
                        self.app,
                        host=self.host,
                        port=self.port,
                        loop="asyncio",
                        ssl_certfile=self.ssl_certfile,
                        ssl_keyfile=self.ssl_keyfile,
                        log_level="debug",
                    )
                    self.server = uvicorn.Server(config)
                    await self.server.serve()
                else:
                    # 如果使用外部 FastAPI 实例，保持运行状态以处理消息
                    while self._running:
                        await asyncio.sleep(1)
            else:
                # TCP 模式
                await self.tcp_server.start()
        except KeyboardInterrupt:
            print("收到键盘中断，服务器已停止")
            await self.stop()
            raise
        except Exception as e:
            await self.stop()
            raise RuntimeError(f"服务器运行错误: {str(e)}") from e
        finally:
            if not self.mode == "tcp":
                await self.stop()

    async def start_server(self):
        """启动服务器的异步方法"""
        if not self._running:
            self._running = True
            await self.run()

    async def stop(self):
        """停止服务器"""
        if self.mode == "ws":
            # 清理WebSocket相关资源
            self.platform_websockets.clear()

            # 取消所有后台任务
            for task in self.background_tasks:
                task.cancel()
            # 等待所有任务完成
            await asyncio.gather(*self.background_tasks, return_exceptions=True)
            self.background_tasks.clear()

            # 关闭所有WebSocket连接
            for websocket in self.active_websockets:
                await websocket.close()
            self.active_websockets.clear()

            if hasattr(self, "server") and self.own_app:
                self._running = False
                # 正确关闭 uvicorn 服务器
                self.server.should_exit = True
                await self.server.shutdown()
                # 等待服务器完全停止
                if hasattr(self.server, "started") and self.server.started:
                    await self.server.main_loop()
        else:
            # 停止TCP服务器
            await self.tcp_server.stop()

        # 清理处理程序
        self.message_handlers.clear()


class MessageClient(BaseMessageHandler):
    """消息客户端，支持 WebSocket 和 TCP 两种模式"""

    _class_handlers: List[Callable] = []  # 类级别的消息处理器

    def __init__(self, mode: Literal["ws", "tcp"] = "ws"):
        super().__init__()
        self.message_handlers.extend(self._class_handlers)
        self.mode = mode
        self.platform = None

        # WebSocket 相关属性
        self.remote_ws = None
        self.remote_ws_url = None
        self.remote_ws_token = None
        self.remote_ws_connected = False
        self.ssl_verify = None

        # TCP 相关属性
        self.tcp_client = None  # 延迟初始化，等待 platform 设置后再创建

        self.remote_reconnect_interval = 5
        self._running = False
        self.retry_count = 0

    async def connect(
        self,
        url: str,
        platform: str,
        token: Optional[str] = None,
        ssl_verify: Optional[str] = None,
    ):
        """设置连接参数并连接到服务器"""
        self.platform = platform

        if self.mode == "ws":
            self.remote_ws_url = url
            self.remote_ws_token = token
            self.ssl_verify = ssl_verify
            self._running = True
        else:
            # 解析 TCP 连接信息
            import re
            from urllib.parse import urlparse

            # 支持 tcp:// 或 tcps:// 协议
            if not url.startswith(("tcp://", "tcps://")):
                # 尝试从 ws(s):// 转换
                parsed = urlparse(url)
                host = parsed.hostname
                port = parsed.port or 18000
                url = f"tcp://{host}:{port}"

            parsed = urlparse(url)
            host = parsed.hostname
            port = parsed.port or 18000

            # 创建并连接 TCP 客户端
            self.tcp_client = TCPClient(platform)
            self.tcp_client.set_target(host, port)
            # self.tcp_client.set_ssl_verify(ssl_verify)
            # await self.tcp_client.connect(host, port)
            self._running = True

    @classmethod
    def register_class_handler(cls, handler: Callable):
        """注册类级别的消息处理器"""
        if handler not in cls._class_handlers:
            cls._class_handlers.append(handler)

    def register_message_handler(self, handler: Callable):
        """注册实例级别的消息处理器"""
        if handler not in self.message_handlers:
            self.message_handlers.append(handler)

    async def run(self):
        """维持连接和消息处理"""
        if self.mode == "ws":
            await self._run_websocket()
        else:
            # TCP 模式下，连接已经在 connect 方法中建立
            await self.tcp_client.connect()

    async def stop(self):
        """停止客户端"""
        self._running = False
        if self.mode == "ws":
            if self.remote_ws and not self.remote_ws.closed:
                await self.remote_ws.close()
            self.remote_ws_connected = False
            self.remote_ws = None
        else:
            await self.tcp_client.disconnect()

    async def send_message(self, message: Dict[str, Any]) -> bool:
        """发送消息到服务器"""
        if self.mode == "ws":
            if not self.remote_ws_connected:
                raise RuntimeError("未连接到服务器")
            try:
                await self.remote_ws.send_json(message)
                return True
            except Exception as e:
                self.remote_ws_connected = False
                raise RuntimeError(f"发送消息失败: {e}") from e
        else:
            try:
                await self.tcp_client.send_message(message)
                return True
            except Exception as e:
                raise RuntimeError(f"发送消息失败: {e}") from e

    async def _run_websocket(self):
        """WebSocket 模式的运行逻辑"""
        self.retry_count = 0
        headers = {"platform": self.platform}
        if self.remote_ws_token:
            headers["Authorization"] = str(self.remote_ws_token)

        # 设置 SSL 上下文并添加调试信息
        ssl_context = None
        if self.remote_ws_url.startswith("wss://"):
            import ssl

            ssl_context = ssl.create_default_context()
            if self.ssl_verify:
                print(f"使用证书验证: {self.ssl_verify}")
                ssl_context.load_verify_locations(self.ssl_verify)
            else:
                print("警告: 未使用证书验证，已禁用证书验证")
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE

            # 启用调试日志
            import logging

            logging.basicConfig(level=logging.DEBUG)
            logging.getLogger("asyncio").setLevel(logging.DEBUG)
            logging.getLogger("aiohttp").setLevel(logging.DEBUG)

        while self._running:
            try:
                print(f"正在连接到 {self.remote_ws_url}")
                print(f"使用的头部信息: {headers}")

                # 使用 TCPConnector 配置会话，设置更长的超时时间
                timeout = aiohttp.ClientTimeout(total=30, connect=10)
                connector = aiohttp.TCPConnector(
                    ssl=ssl_context, enable_cleanup_closed=True
                )
                async with aiohttp.ClientSession(
                    connector=connector, timeout=timeout, headers=headers
                ) as session:
                    try:
                        async with session.ws_connect(
                            self.remote_ws_url,
                            heartbeat=30,  # 添加心跳保持连接
                            compress=15,  # 启用压缩
                        ) as ws:
                            self.remote_ws = ws
                            self.remote_ws_connected = True
                            print(f"已成功连接到 {self.remote_ws_url}")
                            self.retry_count = 0

                            async for msg in ws:
                                if not self._running:
                                    break
                                if msg.type == aiohttp.WSMsgType.TEXT:
                                    try:
                                        message = msg.json()
                                        asyncio.create_task(
                                            self._handle_message(message)
                                        )
                                    except json.JSONDecodeError as e:
                                        print(f"收到无效的JSON消息: {e}")
                                elif msg.type in (
                                    aiohttp.WSMsgType.CLOSED,
                                    aiohttp.WSMsgType.ERROR,
                                ):
                                    print(f"WebSocket连接关闭或错误: {msg.type}")
                                    break

                    except aiohttp.ClientError as e:
                        print(f"连接错误详情: {str(e)}")
                        if isinstance(e, aiohttp.ClientConnectorError):
                            print(
                                f"无法建立连接: {e.strerror if hasattr(e, 'strerror') else str(e)}"
                            )
                        elif isinstance(e, aiohttp.ClientSSLError):
                            print(f"SSL错误: {str(e)}")
                        raise

            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                print(f"连接失败 ({self.retry_count}): {e}")
                if isinstance(e, aiohttp.ClientConnectorError):
                    print(f"连接器错误详情: {e}")
                self.retry_count += 1
            except asyncio.CancelledError:
                print("连接被取消")
                break
            except Exception as e:
                print(f"未预期的错误: {str(e)}")
                import traceback

                traceback.print_exc()
            finally:
                self.remote_ws_connected = False
                self.remote_ws = None

            if self._running:
                retry_delay = min(
                    30, self.remote_reconnect_interval * (2 ** min(self.retry_count, 5))
                )
                print(f"等待 {retry_delay} 秒后重试...")
                await asyncio.sleep(retry_delay)
