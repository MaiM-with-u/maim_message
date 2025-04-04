# Maim Message

一个用于定义maimcore消息通用接口的Python库。

## 安装

```bash
git clone https://github.com/MaiM-with-u/maim_message
cd maim_message
pip install -e .
```

## 使用方法

```python
from maim_message import MessageBase
```

## 简要构造一个maimcore plugin
plugin与上下游交互分为两个部分，api和message_base，api提供了异步的可暴露的websocket接口以及uvicorn服务器，以及向别的api接口发送数据的方法，message_base中提供了消息数据的序列化和反序列化。在plugin中，我们需要接受来自上游的消息数据，反序列化成message，经过处理后发送给下游（在这里为了方便简单模仿了maimcore的架构，即作为server收到消息后返回给发送消息的client，实际制作插件时应当另开client向下游发送），一个简单的流程如下：
```python
from maim_message import MessageBase, Seg, MessageServer


async def process_seg(seg: Seg):
    """处理消息段的递归函数"""
    if seg.type == "seglist":
        seglist = seg.data
        for single_seg in seglist:
            await process_seg(single_seg)
    # 实际内容处理逻辑
    if seg.type == "voice":
        seg.type = "text"
        seg.data = "[音频]"
    elif seg.type == "at":
        seg.type = "text"
        seg.data = "[@某人]"


async def handle_message(message_data):
    """消息处理函数"""
    message = MessageBase.from_dict(message_data)
    await process_seg(message.message_segment)

    # 将处理后的消息广播给所有连接的客户端
    await server.send_message(message)


if __name__ == "__main__":
    # 创建服务器实例
    server = MessageServer(host="0.0.0.0", port=19000)

    # 注册消息处理器
    server.register_message_handler(handle_message)

    # 运行服务器
    server.run_sync()

```
## 简要构造一个消息客户端
涉及到标准消息的构建与客户端的建立，maim_message提供了一个Router类，可用于管理一个客户端程序处理多种不同平台的数据时建立的多个MessageClient，可参考如下。
```python
from maim_message import (
    BaseMessageInfo,
    UserInfo,
    GroupInfo,
    FormatInfo,
    TemplateInfo,
    MessageBase,
    Seg,
    Router,
    RouteConfig,
    TargetConfig,
)
import asyncio


def construct_message(platform):
    # 构造消息
    user_info = UserInfo(
        # 必填
        platform=platform,
        user_id=12348765,
        # 选填
        user_nickname="maimai",
        user_cardname="mai god",
    )

    group_info = GroupInfo(
        # 必填
        platform=platform,  # platform请务必保持一致
        group_id=12345678,
        # 选填
        group_name="aaabbb",
    )

    format_info = FormatInfo(
        # 消息内容中包含的Seg的type列表
        content_format=["text", "image", "emoji", "at", "reply", "voice"],
        # 消息发出后，期望最终的消息中包含的消息类型，可以帮助某些plugin判断是否向消息中添加某些消息类型
        accept_format=["text", "image", "emoji", "reply"],
    )

    # 暂时不启用，可置None
    template_info_custom = TemplateInfo(
        template_items={
            "detailed_text": "[{user_nickname}({user_nickname})]{user_cardname}: {processed_text}",
            "main_prompt_template": "...",
        },
        template_name="qq123_default",
        template_default=False,
    )

    template_info_default = TemplateInfo(template_default=True)

    message_info = BaseMessageInfo(
        # 必填
        platform=platform,
        message_id="12345678",  # 只会在reply和撤回消息等功能下启用，且可以不保证unique
        time=1234567,  # 时间戳
        group_info=group_info,
        user_info=user_info,
        # 选填和暂未启用
        format_info=format_info,
        template_info=None,
        additional_config={
            "maimcore_reply_probability_gain": 0.5  # 回复概率增益
        },
    )

    message_segment = Seg(
        "seglist",
        [
            Seg("text", "111(raw text)"),
            Seg("emoji", "base64(raw base64)"),
            Seg("image", "base64(raw base64)"),
            Seg("at", "111222333(qq number)"),
            Seg("reply", "123456(message id)"),
            Seg("voice", "wip"),
        ],
    )

    raw_message = "可有可无"

    message = MessageBase(
        # 必填
        message_info=message_info,
        message_segment=message_segment,
        # 选填
        raw_message=raw_message,
    )
    return message


async def message_handler(message):
    """消息处理函数"""
    print(f"收到消息: {message}")


# 配置路由
route_config = RouteConfig(
    route_config={
        "qq123": TargetConfig(
            url="ws://127.0.0.1:19000/ws",
            token=None,  # 如果需要token验证则在这里设置
        ),
        "qq321": TargetConfig(
            url="ws://127.0.0.1:19000/ws",
            token=None,  # 如果需要token验证则在这里设置
        ),
        "qq111": TargetConfig(
            url="ws://127.0.0.1:19000/ws",
            token=None,  # 如果需要token验证则在这里设置
        ),
    }
)

# 创建路由器实例
router = Router(route_config)


async def main():
    # 注册消息处理器
    router.register_class_handler(message_handler)

    try:
        # 启动路由器（会自动连接所有配置的平台）
        router_task = asyncio.create_task(router.run())

        # 等待连接建立
        await asyncio.sleep(2)

        # 发送测试消息
        await router.send_message(construct_message("qq123"))

        # 等待3秒后更新配置
        await asyncio.sleep(3)
        print("\n准备更新连接配置...")

        # 测试新的配置更新
        new_config = {
            "route_config": {
                # 保持qq123不变
                "qq123": {
                    "url": "ws://127.0.0.1:19000/ws",
                    "token": None,
                },
                # 移除qq321
                # 更改qq111的token
                "qq111": {
                    "url": "ws://127.0.0.1:19000/ws",
                    "token": None,
                },
                # 添加新平台
                "qq999": {
                    "url": "ws://127.0.0.1:19000/ws",
                    "token": None,
                },
            }
        }

        await router.update_config(new_config)
        print("配置更新完成")

        # 等待新连接建立
        await asyncio.sleep(2)

        # 测试新配置下的消息发送
        await router.send_message(construct_message("qq111"))
        await router.send_message(construct_message("qq999"))

        # 保持运行直到被中断
        await router_task

    finally:
        print("正在关闭连接...")
        await router.stop()
        print("已关闭所有连接")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass  # 让asyncio.run处理清理工作

```

## 许可证

MIT
