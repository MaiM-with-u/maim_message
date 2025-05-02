import asyncio
import struct
import traceback
from typing import Optional, Dict, Any, Callable, List, Set
from .crypto import CryptoManager, FrameType


class BaseTCPHandler:
    """TCP 连接基类，实现基本的加密通信功能"""

    def __init__(self):
        self.crypto = CryptoManager()
        self.message_handlers: List[Callable] = []
        self._running = False
        self._sequence = 0
        self.background_tasks = set()  # 添加后台任务集合

    def _add_background_task(self, task: asyncio.Task):
        """添加后台任务到管理集合"""
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)

    async def _read_frame(self, reader: asyncio.StreamReader) -> tuple[bytes, bytes]:
        """读取一个完整的消息帧"""
        # 读取帧头（4字节长度 + 1字节类型）
        header = await reader.readexactly(5)
        frame_length, frame_type = struct.unpack("!IB", header)

        # 读取帧负载
        payload = await reader.readexactly(frame_length - 5)
        return frame_type, payload

    async def _write_frame(self, writer: asyncio.StreamWriter, frame: bytes):
        """写入一个消息帧"""
        writer.write(frame)
        await writer.drain()

    async def _handle_handshake(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        is_server: bool,
        crypto_manager: Optional[CryptoManager] = None,
    ) -> bool:
        """处理握手过程"""
        crypto = crypto_manager or self.crypto
        try:
            if is_server:
                # 服务器等待客户端的握手请求
                frame_type, client_public_key = await self._read_frame(reader)
                # print(f"握手请求: {frame_type}")
                if frame_type != FrameType.HANDSHAKE_REQUEST:
                    return False

                # 发送服务器的公钥
                server_handshake = crypto.create_handshake_frame(
                    crypto.get_public_bytes()
                )
                await self._write_frame(writer, server_handshake)

                # 计算共享密钥
                crypto.compute_shared_key(client_public_key)
            else:
                # 客户端发送握手请求
                client_handshake = crypto.create_handshake_frame(
                    crypto.get_public_bytes()
                )
                await self._write_frame(writer, client_handshake)

                # 等待服务器响应
                frame_type, server_public_key = await self._read_frame(reader)
                # print(f"握手响应: {frame_type}")
                if frame_type != FrameType.HANDSHAKE_REQUEST:
                    return False

                # 计算共享密钥
                crypto.compute_shared_key(server_public_key)

            return True

        except Exception as e:
            print(f"握手失败: {e} {traceback.format_exc()}")
            return False

    async def _handle_message(self, message: Dict[str, Any]):
        """处理接收到的消息"""
        for handler in self.message_handlers:
            try:
                await handler(message)
            except Exception as e:
                print(f"消息处理错误: {e}")

    def register_message_handler(self, handler: Callable):
        """注册消息处理器"""
        if handler not in self.message_handlers:
            self.message_handlers.append(handler)


class Connection:
    """连接类，用于存储连接信息"""

    def __init__(self, writer: asyncio.StreamWriter, crypto_manager: CryptoManager):
        self.writer = writer
        self.crypto_manager = crypto_manager
        self.sequence = 0

    def get_sequence(self):
        seq = self.sequence
        self.sequence += 1
        return seq


class TCPServer(BaseTCPHandler):
    """TCP 服务器实现"""

    def __init__(self, host: str = "0.0.0.0", port: int = 18000):
        super().__init__()
        self.host = host
        self.port = port
        self.active_connections: Set[asyncio.StreamWriter] = set()
        self.platform_connections: Dict[str, Connection] = {}  # 平台到连接的映射
        self._server = None
        self._serve_task = None

    async def start(self):
        """启动服务器"""
        self._running = True
        self._server = await asyncio.start_server(
            self._handle_client, self.host, self.port
        )
        print(f"TCP服务器启动在 {self.host}:{self.port}")

        async with self._server:
            self._serve_task = asyncio.create_task(self._server.serve_forever())
            try:
                while self._running:
                    await asyncio.sleep(1)
            except (KeyboardInterrupt, asyncio.CancelledError):
                print("服务器正在关闭...")
                await self.stop()
                raise KeyboardInterrupt()

    async def stop(self):
        """停止服务器"""
        if not self._running:
            return
        self._running = False

        if self.active_connections:
            for writer in list(self.active_connections):
                writer.write_eof()
                writer.close()
                await writer.wait_closed()
        if self._serve_task:
            self._serve_task.cancel()
            try:
                await self._serve_task
            except asyncio.CancelledError:
                pass
        if self._server:
            self._server.close()
            await self._server.wait_closed()

        # 取消所有后台任务
        for task in self.background_tasks:
            task.cancel()

        # 等待所有任务完成
        if self.background_tasks:
            await asyncio.gather(*self.background_tasks, return_exceptions=True)
        self.background_tasks.clear()

        # 关闭所有连接
        for writer in self.active_connections:
            writer.close()
            await writer.wait_closed()
        self.active_connections.clear()
        self.platform_connections.clear()

    async def _handle_platform_registration(
        self, reader: asyncio.StreamReader, crypto_manager: CryptoManager
    ) -> Optional[str]:
        """处理平台注册"""
        # 等待客户端发送平台信息
        frame_type, payload = await self._read_frame(reader)
        if frame_type != FrameType.DATA:
            return None

        # 解密并验证平台信息
        iv, encrypted_data, sequence = crypto_manager.parse_data_frame(payload)
        platform_data = crypto_manager.decrypt_message(iv, encrypted_data, sequence)
        # print(platform_data)

        if not isinstance(platform_data, dict) or "platform" not in platform_data:
            return None

        return platform_data["platform"]

    async def _remove_connection(self, platform: str):
        """移除连接"""
        conn = self.platform_connections.get(platform)
        if conn:
            writer = conn.writer
            if writer in self.active_connections:
                self.active_connections.remove(writer)
            del self.platform_connections[platform]
            writer.close()
            await writer.wait_closed()

    async def _process_message(
        self,
        frame_type: FrameType,
        payload: bytes,
        writer: asyncio.StreamWriter,
        crypto_manager: CryptoManager,
    ):
        """异步处理单条消息"""
        try:
            # print(f"接收到消息类型: {frame_type}, 长度: {len(payload)}")
            if frame_type == FrameType.DATA:
                # 解析并处理数据帧
                iv, encrypted_data, sequence = crypto_manager.parse_data_frame(payload)
                message = crypto_manager.decrypt_message(iv, encrypted_data, sequence)
                await self._handle_message(message)
            elif frame_type == FrameType.HEARTBEAT:
                # 响应心跳
                await self._write_frame(
                    writer, crypto_manager.create_frame(FrameType.HEARTBEAT, b"")
                )
        except Exception as e:
            print(f"处理消息时出错: {e}")

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        """处理客户端连接"""
        platform = None
        # 为每个连接创建独立的加密管理器
        connection_crypto = CryptoManager()
        try:
            # 进行握手(使用连接特定的加密管理器)
            if not await self._handle_handshake(
                reader, writer, True, crypto_manager=connection_crypto
            ):
                writer.close()
                await writer.wait_closed()
                return

            # 等待平台注册(使用连接特定的加密管理器)
            platform = await self._handle_platform_registration(
                reader, crypto_manager=connection_crypto
            )
            if not platform:
                print("平台注册失败")
                writer.close()
                await writer.wait_closed()
                return

            # 记录连接
            self.active_connections.add(writer)
            self.platform_connections[platform] = Connection(
                writer=writer, crypto_manager=connection_crypto
            )  # 存储加密管理器
            print(f"客户端已连接，平台: {platform}")

            try:
                while self._running:
                    # 读取消息帧
                    frame_type, payload = await self._read_frame(reader)

                    # 创建异步任务处理消息
                    task = asyncio.create_task(
                        self._process_message(
                            frame_type, payload, writer, connection_crypto
                        )
                    )
                    self._add_background_task(task)

            except asyncio.IncompleteReadError:
                print(f"客户端断开连接 (平台: {platform})")
            finally:
                await self._remove_connection(platform)

        except KeyboardInterrupt:
            print("服务器关闭")
            raise
        except Exception as e:
            print(
                f"处理客户端连接时出错 (平台: {platform}): {e} {traceback.format_exc()}"
            )
            if platform:
                await self._remove_connection(platform)
            else:
                print("平台注册失败")
                writer.close()
                await writer.wait_closed()
                return

    async def broadcast_message(self, message: Dict[str, Any]):
        """广播消息给所有连接的客户端"""
        if not self.platform_connections:
            return

        # 发送给所有客户端
        disconnected = set()
        for platform, conn in self.platform_connections.items():
            try:
                # 使用连接特定的加密管理器
                sequence = conn.get_sequence()
                iv, encrypted = conn.crypto_manager.encrypt_message(message, sequence)
                frame = conn.crypto_manager.create_data_frame(iv, encrypted, sequence)
                await self._write_frame(conn.writer, frame)
            except Exception:
                disconnected.add(platform)

        # 清理断开的连接
        for platform in disconnected:
            await self._remove_connection(platform)

    async def send_to_platform(self, platform: str, message: Dict[str, Any]) -> bool:
        """发送消息给指定平台"""
        if platform not in self.platform_connections:
            return False

        conn = self.platform_connections[platform]
        try:
            # 使用连接特定的加密管理器加密消息
            sequence = conn.get_sequence()
            iv, encrypted = conn.crypto_manager.encrypt_message(message, sequence)
            frame = conn.crypto_manager.create_data_frame(iv, encrypted, sequence)

            # 发送消息
            await self._write_frame(conn.writer, frame)
            return True
        except Exception as e:
            print(f"发送消息到平台 {platform} 失败: {e}")
            await self._remove_connection(platform)
            return False


class TCPClient(BaseTCPHandler):
    """TCP 客户端实现"""

    _class_handlers: List[Callable] = []  # 类级别的消息处理器

    def __init__(self, platform: str):
        super().__init__()
        self.platform = platform
        self.reader = None
        self.writer = None
        self._heartbeat_task = None
        self.message_handlers.extend(self._class_handlers)

    def set_target(self, host: str, port: int):
        """设置目标服务器地址和端口"""
        self.host = host
        self.port = port

    @classmethod
    def register_class_handler(cls, handler: Callable):
        """注册类级别的消息处理器"""
        if handler not in cls._class_handlers:
            cls._class_handlers.append(handler)

    async def connect(self):
        """连接到服务器"""
        if not self.host or not self.port:
            raise ValueError("目标地址和端口未设置")
        host, port = self.host, self.port
        try:
            self.reader, self.writer = await asyncio.open_connection(host, port)

            # 进行握手
            if not await self._handle_handshake(self.reader, self.writer, False):
                raise RuntimeError("握手失败")

            # 发送平台注册信息
            platform_info = {"platform": self.platform}
            iv, encrypted = self.crypto.encrypt_message(platform_info, self._sequence)
            frame = self.crypto.create_data_frame(iv, encrypted, self._sequence)
            self._sequence += 1

            await self._write_frame(self.writer, frame)

            self._running = True

            # 启动心跳任务
            self._heartbeat_task = asyncio.create_task(self._heartbeat())
            print(f"platform: {self.platform} 已连接到服务器: {host}:{port}")

            # 开始接收消息
            try:
                while self._running:
                    frame_type, payload = await self._read_frame(self.reader)
                    # print(f"接收到消息类型: {frame_type}, 长度: {len(payload)}")

                    if frame_type == FrameType.DATA:
                        # 解析并处理数据帧
                        # print(f"接收到数据帧: {len(payload)}")
                        iv, encrypted_data, sequence = self.crypto.parse_data_frame(
                            payload
                        )
                        message = self.crypto.decrypt_message(
                            iv, encrypted_data, sequence
                        )
                        # print(f"接收到msg: {message}")
                        task = asyncio.create_task(self._handle_message(message))
                        self._add_background_task(task)

            except asyncio.IncompleteReadError:
                print("与服务器的连接断开")
            except Exception as e:
                print(f"处理消息时出错: {e} {traceback.format_exc()}")
            finally:
                await self.disconnect()

        except Exception as e:
            print(f"连接失败: {e}")
            raise

    async def disconnect(self):
        """断开连接"""
        self._running = False

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
        # 取消所有后台任务
        for task in self.background_tasks:
            task.cancel()

        # 等待所有任务完成
        if self.background_tasks:
            await asyncio.gather(*self.background_tasks, return_exceptions=True)
        self.background_tasks.clear()
        # print("已断开连接")

    async def send_message(self, message: Dict[str, Any]):
        """发送消息到服务器"""
        if not self.writer or self.writer.is_closing():
            raise RuntimeError("未连接到服务器")

        # 加密并发送消息
        iv, encrypted = self.crypto.encrypt_message(message, self._sequence)
        frame = self.crypto.create_data_frame(iv, encrypted, self._sequence)
        self._sequence += 1

        # print(f"发送消息: {message}")

        await self._write_frame(self.writer, frame)

    async def _heartbeat(self):
        """发送心跳包"""
        while self._running:
            try:
                await asyncio.sleep(30)  # 每30秒发送一次心跳
                if self.writer and not self.writer.is_closing():
                    await self._write_frame(
                        self.writer, self.crypto.create_frame(FrameType.HEARTBEAT, b"")
                    )
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"发送心跳失败: {e}")
                break
