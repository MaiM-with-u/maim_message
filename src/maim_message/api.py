from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import json
from typing import Optional, Dict, Any, Callable, List
import aiohttp
import asyncio
import uvicorn


class BaseMessageAPI:
    def __init__(self, host: str = "0.0.0.0", port: int = 18000):
        self.app = FastAPI()
        self.host = host
        self.port = port
        self.message_handlers: List[Callable] = []
        self._setup_routes()
        self._running = False

    def _setup_routes(self):
        """设置基础路由"""

        @self.app.post("/api/message")
        async def handle_message(message: Dict[str, Any]):
            # try:
            for handler in self.message_handlers:
                await handler(message)
            return {"status": "success"}
            # except Exception as e:
            #     raise HTTPException(status_code=500, detail=str(e)) from e

    def register_message_handler(self, handler: Callable):
        """注册消息处理函数"""
        self.message_handlers.append(handler)

    async def send_message(self, url: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """发送消息到指定端点"""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    url, json=data, headers={"Content-Type": "application/json"}
                ) as response:
                    return await response.json()
            except Exception as e:
                # logger.error(f"发送消息失败: {str(e)}")
                pass

    def run_sync(self):
        """同步方式运行服务器"""
        uvicorn.run(self.app, host=self.host, port=self.port)

    async def run(self):
        """异步方式运行服务器"""
        config = uvicorn.Config(
            self.app, host=self.host, port=self.port, loop="asyncio"
        )
        self.server = uvicorn.Server(config)
        try:
            await self.server.serve()
        except KeyboardInterrupt as e:
            self.stop()
            raise KeyboardInterrupt from e

    async def start_server(self):
        """启动服务器的异步方法"""
        if not self._running:
            self._running = True
            await self.run()

    async def stop(self):
        """停止服务器"""
        if hasattr(self, "server"):
            self._running = False
            # 正确关闭 uvicorn 服务器
            self.server.should_exit = True
            await self.server.shutdown()
            # 等待服务器完全停止
            if hasattr(self.server, "started") and self.server.started:
                await self.server.main_loop()
            # 清理处理程序
            self.message_handlers.clear()

    def start(self):
        """启动服务器的便捷方法"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.start_server())
        except KeyboardInterrupt:
            pass
        finally:
            loop.close()
