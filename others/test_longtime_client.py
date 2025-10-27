"""长连接压力测试客户端，周期性与服务器互发消息。"""

from __future__ import annotations

import asyncio
import contextlib
import random
import time
from typing import Dict

from maim_message import (
    BaseMessageInfo,
    GroupInfo,
    MessageBase,
    Router,
    RouteConfig,
    Seg,
    TargetConfig,
    UserInfo,
)


CLIENT_PLATFORM = "longtime-test"


def _segment_to_text(seg: Seg) -> str:
    if seg.type == "seglist":
        return "".join(_segment_to_text(child) for child in seg.data)
    if seg.type == "text":
        return str(seg.data)
    return f"[{seg.type}:{seg.data}]"


def _build_text_message(content: str) -> MessageBase:
    now = int(time.time())
    message_info = BaseMessageInfo(
        platform=CLIENT_PLATFORM,
        message_id=f"client-{now}",
        time=now,
        group_info=GroupInfo(
            platform=CLIENT_PLATFORM,
            group_id="longtime-group",
            group_name="LongTime Test Group",
        ),
        user_info=UserInfo(
            platform=CLIENT_PLATFORM,
            user_id="client_bot",
            user_nickname="ClientBot",
            user_cardname="Client",
        ),
    )
    message_segment = Seg("seglist", [Seg("text", content)])
    return MessageBase(
        message_info=message_info,
        message_segment=message_segment,
        raw_message=content,
    )

incoming_queue: asyncio.Queue[MessageBase] | None = None


async def message_handler(message_data: Dict) -> None:
    message = MessageBase.from_dict(message_data)
    if message.message_info.platform != CLIENT_PLATFORM:
        print(f"[CLIENT] 收到来自未知平台 {message.message_info.platform} 的消息，忽略")
        return

    text = _segment_to_text(message.message_segment)
    print(f"[CLIENT] 收到服务器消息: {text}")

    if incoming_queue is None:
        raise RuntimeError("incoming_queue 尚未初始化")

    await incoming_queue.put(message)


async def send_message(router: Router, content: str) -> None:
    message = _build_text_message(content)
    await router.send_message(message)
    print(f"[CLIENT] 已发送消息: {content}")


async def main() -> None:
    route_config = RouteConfig(
        route_config={
            CLIENT_PLATFORM: TargetConfig(
                url="ws://127.0.0.1:8090/ws",
                token=None,
            )
        }
    )

    global incoming_queue
    incoming_queue = asyncio.Queue()

    router = Router(route_config)
    router.register_class_handler(message_handler)

    router_task = asyncio.create_task(router.run())

    try:
        await asyncio.sleep(2)

        initial_delay = random.randint(2, 10)
        print(f"[CLIENT] {initial_delay}s 后发送首条消息")
        await asyncio.sleep(initial_delay)
        await send_message(router, f"客户端首发消息，延时 {initial_delay}s")

        if incoming_queue is None:
            raise RuntimeError("incoming_queue 尚未初始化")

        while True:
            await incoming_queue.get()
            delay = random.randint(2, 6)
            print(f"[CLIENT] {delay}s 后准备发送下一条消息")
            await asyncio.sleep(delay)
            await send_message(router, f"客户端延时 {delay}s 回复: {int(time.time())}")

    except asyncio.CancelledError:
        raise
    except KeyboardInterrupt:
        print("[CLIENT] 收到中断信号，准备退出")
    finally:
        await router.stop()
        router_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await router_task


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
