"""长连接压力测试服务器，定期向客户端回发消息。"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Dict

from maim_message import (
    BaseMessageInfo,
    GroupInfo,
    MessageBase,
    MessageServer,
    Seg,
    UserInfo,
)
from maim_message.log_utils import configure_uvicorn_logging, setup_logger
from starlette.websockets import WebSocketState


def _segment_to_text(seg: Seg) -> str:
    if seg.type == "seglist":
        return "".join(_segment_to_text(child) for child in seg.data)
    if seg.type == "text":
        return str(seg.data)
    return f"[{seg.type}:{seg.data}]"


def _build_text_message(platform: str, content: str) -> MessageBase:
    now = int(time.time())
    message_info = BaseMessageInfo(
        platform=platform,
        message_id=f"server-{now}",
        time=now,
        group_info=GroupInfo(
            platform=platform,
            group_id="longtime-group",
            group_name="LongTime Test Group",
        ),
        user_info=UserInfo(
            platform=platform,
            user_id="server_bot",
            user_nickname="ServerBot",
            user_cardname="Server",
        ),
    )
    message_segment = Seg("seglist", [Seg("text", content)])
    return MessageBase(
        message_info=message_info,
        message_segment=message_segment,
        raw_message=content,
    )


class LongTimeTestServer:
    """封装服务器逻辑，按需回发消息。"""

    def __init__(self, host: str = "0.0.0.0", port: int = 8090) -> None:
        logger = setup_logger()
        logger.setLevel(logging.DEBUG)
        for handler in logger.handlers:
            handler.setLevel(logging.DEBUG)
        configure_uvicorn_logging()

        self.server = MessageServer(
            host=host,
            port=port,
            mode="ws",
            enable_custom_uvicorn_logger=True,
        )
        self.server.register_message_handler(self.handle_message)

    def _log_connection_state(self, label: str) -> None:
        connection = getattr(self.server, "connection", None)
        if connection is None:
            print(f"[SERVER][STATE] {label}: 无 connection 对象")
            return

        platform_map = {}
        for platform, websocket in connection.platform_websockets.items():
            state = getattr(websocket, "client_state", None)
            if isinstance(state, WebSocketState):
                state_name = state.name
            else:
                state_name = str(state)
            platform_map[platform] = {
                "websocket_id": id(websocket),
                "state": state_name,
            }

        active_list = []
        for websocket in connection.active_websockets:
            state = getattr(websocket, "client_state", None)
            if isinstance(state, WebSocketState):
                state_name = state.name
            else:
                state_name = str(state)
            active_list.append(
                {
                    "websocket_id": id(websocket),
                    "state": state_name,
                }
            )

        print(
            "[SERVER][STATE] {label}: platforms={platforms}, active={active}, "
            "active_count={count}".format(
                label=label,
                platforms=platform_map,
                active=active_list,
                count=len(connection.active_websockets),
            )
        )

    async def handle_message(self, message_data: Dict) -> None:
        message = MessageBase.from_dict(message_data)
        platform = message.message_info.platform

        received_text = _segment_to_text(message.message_segment)
        print(f"[SERVER] 收到来自平台 {platform} 的消息: {received_text}")
        self._log_connection_state("after-receive")

        delay = random.randint(20, 60)
        print(f"[SERVER] {delay}s 后向 {platform} 回发消息")
        await asyncio.sleep(delay)
        self._log_connection_state("before-send")
        response = _build_text_message(
            platform,
            content=f"服务器延时 {delay}s 回复: {int(time.time())}",
        )
        send_ok = await self.server.send_message(response)
        if send_ok:
            print(f"[SERVER] 已向 {platform} 发送响应消息")
        else:
            print(f"[SERVER] 向 {platform} 发送响应消息失败")
        self._log_connection_state("after-send")

    def run(self) -> None:
        print("[SERVER] 长连接测试服务器启动：ws://0.0.0.0:8090/ws")
        self.server.run_sync()


if __name__ == "__main__":
    LongTimeTestServer().run()
