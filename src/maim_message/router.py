from typing import Optional, Dict, Any, Callable, List, Set
from dataclasses import dataclass, asdict
from .message_base import MessageBase
from .api import MessageClient
from fastapi import WebSocket
import asyncio


@dataclass
class TargetConfig:
    url: str = None
    token: Optional[str] = None
    ssl_verify: Optional[str] = None  # SSL证书路径，用于验证服务器证书

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "TargetConfig":
        return cls(
            url=data.get("url"),
            token=data.get("token"),
            ssl_verify=data.get("ssl_verify"),
        )


@dataclass
class RouteConfig:
    route_config: Dict[str, TargetConfig] = None

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "RouteConfig":
        route_config = data.get("route_config")
        for k in route_config.keys():
            route_config[k] = TargetConfig.from_dict(route_config[k])
        return cls(route_config=route_config)


class Router:
    def __init__(self, config: RouteConfig):
        self.config = config
        self.clients: Dict[str, MessageClient] = {}
        self._running = False
        self._client_tasks: Dict[str, asyncio.Task] = {}
        self._monitor_task = None

    async def _monitor_connections(self):
        """监控所有客户端连接状态"""
        await asyncio.sleep(3)  # 等待初始连接建立
        while self._running:
            for platform in list(self.clients.keys()):
                client = self.clients[platform]
                # 根据不同模式检查连接状态
                if (client.mode == "ws" and not client.remote_ws_connected) or (
                    client.mode == "tcp"
                    and (not client.tcp_client or not client.tcp_client._running)
                ):
                    print(f"检测到平台 {platform} 连接断开，尝试重连...")
                    await self._reconnect_platform(platform)
            await asyncio.sleep(5)  # 每5秒检查一次

    async def _reconnect_platform(self, platform: str):
        """重新连接指定平台"""
        if platform in self._client_tasks:
            task = self._client_tasks[platform]
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            del self._client_tasks[platform]

        if platform in self.clients:
            await self.clients[platform].stop()
            del self.clients[platform]

        await self.connect(platform)

    async def add_platform(self, platform: str, config: TargetConfig):
        """动态添加新平台"""
        self.config.route_config[platform] = config
        if self._running:
            await self.connect(platform)

    async def remove_platform(self, platform: str):
        """动态移除平台"""
        if platform in self.config.route_config:
            del self.config.route_config[platform]

        if platform in self._client_tasks:
            task = self._client_tasks[platform]
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            del self._client_tasks[platform]

        if platform in self.clients:
            await self.clients[platform].stop()
            del self.clients[platform]

    async def connect(self, platform: str):
        """连接指定平台"""
        if platform not in self.config.route_config:
            raise ValueError(f"未找到平台配置: {platform}")

        config = self.config.route_config[platform]

        # 根据URL协议决定使用哪种模式
        mode = "tcp" if config.url.startswith(("tcp://", "tcps://")) else "ws"
        client = MessageClient(mode=mode)

        await client.connect(
            url=config.url,
            platform=platform,
            token=config.token,
            ssl_verify=config.ssl_verify,
        )
        self.clients[platform] = client

        if self._running:
            self._client_tasks[platform] = asyncio.create_task(client.run())

    async def run(self):
        """运行所有客户端连接"""
        self._running = True
        try:
            # 初始化所有平台的连接
            for platform in self.config.route_config:
                if platform not in self.clients:
                    await self.connect(platform)

            # 启动连接监控
            self._monitor_task = asyncio.create_task(self._monitor_connections())

            # 等待运行状态改变
            # try:
            while self._running:
                await asyncio.sleep(1)
            # except asyncio.CancelledError:
            #     pass

        except (
            asyncio.CancelledError,
            KeyboardInterrupt,
        ):
            await self.stop()
            raise

    async def stop(self):
        """停止所有客户端"""
        self._running = False

        # 取消监控任务
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            await asyncio.gather(self._monitor_task, return_exceptions=True)

        # 先取消所有后台任务
        for task in self._client_tasks.values():
            if not task.done():
                task.cancel()

        # 等待任务取消完成
        if self._client_tasks:
            await asyncio.gather(*self._client_tasks.values(), return_exceptions=True)
        self._client_tasks.clear()

        # 然后停止所有客户端
        stop_tasks = []
        for client in self.clients.values():
            stop_tasks.append(client.stop())
        if stop_tasks:
            await asyncio.gather(*stop_tasks, return_exceptions=True)

        self.clients.clear()

    def register_class_handler(self, handler):
        MessageClient.register_class_handler(handler)

    def get_target_url(self, message: MessageBase):
        platform = message.message_info.platform
        if platform in self.config.route_config.keys():
            return self.config.route_config[platform].url
        else:
            return None

    async def send_message(self, message: MessageBase):
        url = self.get_target_url(message)
        platform = message.message_info.platform
        if url is None:
            raise ValueError(f"不存在该平台url配置: {platform}")
        # print(f"发送消息到 {platform} 的 URL: {url}")

        if platform not in self.clients:
            config = self.config.route_config[platform]
            # 根据URL协议决定使用哪种模式
            mode = "tcp" if config.url.startswith(("tcp://", "tcps://")) else "ws"
            client = MessageClient(mode=mode)
            await client.connect(
                url=config.url,
                platform=platform,
                token=config.token,
                ssl_verify=config.ssl_verify,
            )
            self.clients[platform] = client

        await self.clients[platform].send_message(message.to_dict())

    async def _adjust_connections(self, new_config: RouteConfig):
        """根据新配置调整连接"""
        # 获取新旧配置的平台集合
        old_platforms = set(self.config.route_config.keys())
        new_platforms = set(new_config.route_config.keys())

        # 需要移除的平台
        for platform in old_platforms - new_platforms:
            await self.remove_platform(platform)

        # 需要更新或添加的平台
        for platform in new_platforms:
            new_target = new_config.route_config[platform]
            if platform in self.config.route_config:
                old_target = self.config.route_config[platform]
                # 如果配置发生变化，需要重新连接
                if (
                    new_target.url != old_target.url
                    or new_target.token != old_target.token
                ):
                    await self.remove_platform(platform)
                    await self.add_platform(platform, new_target)
            else:
                # 新增平台
                await self.add_platform(platform, new_target)

    async def update_config(self, config_data: Dict):
        """更新路由配置并动态调整连接"""
        new_config = RouteConfig.from_dict(config_data)
        if self._running:
            await self._adjust_connections(new_config)
        self.config = new_config
