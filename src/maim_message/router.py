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

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "TargetConfig":
        return cls(url=data.get("url"), token=data.get("token"))


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

    async def connect(self, platform: str):
        """连接指定平台"""
        if platform not in self.config.route_config:
            raise ValueError(f"未找到平台配置: {platform}")

        config = self.config.route_config[platform]
        client = MessageClient()
        await client.connect(config.url, platform, config.token)
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

            # 等待所有客户端任务完成
            while self._running:
                await asyncio.sleep(1)

        except asyncio.CancelledError:
            await self.stop()

    async def stop(self):
        """停止所有客户端"""
        self._running = False

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
        if platform not in self.clients.keys():
            client = MessageClient()
            await client.connect(
                url, platform, self.config.route_config[platform].token
            )
            self.clients[platform] = client
        await self.clients[platform].send_message(message.to_dict())

    async def update_config(self, config_data: Dict):
        self.config = RouteConfig.from_dict(config_data)
