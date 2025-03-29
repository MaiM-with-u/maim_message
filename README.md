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
plugin与上下游交互分为两个部分，api和message_base，api提供了异步的可暴露的fastapi接口以及uvicorn服务器，以及向别的api接口发送数据的方法，message_base中提供了消息数据的序列化和反序列化。在plugin中，我们需要接受来自上游的消息数据，反序列化成message，经过处理后序列化发送给下游，一个简单的流程如下：
```python
from maim_message import (
    BaseMessageInfo,
    UserInfo,
    GroupInfo,
    FormatInfo,
    TemplateInfo,
    MessageBase,
    Seg,
    BaseMessageAPI
)

global_api = BaseMessageAPI("0.0.0.0", 19000)


async def handle(message_data):
    message = MessageBase.from_dict(message_data)

    def seg_process(seg: Seg):
        # 递归逻辑
        if seg.type == "seglist":
            seglist = seg.data
            for single_seg in seglist:
                seg_process(single_seg)
        # 实际内容处理逻辑
        if seg.type == "voice":
            seg.type = "text"
            seg.data = "[音频]"
        elif seg.type == "at":
            seg.type = "text"
            seg.data = "[@某人]"

    # seg示例
    seg_example = Seg(
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
    seg_process(seg_example)
    print(seg_example.to_dict())

    # 实际处理消息
    seg_process(message.message_segment)

    # 发送消息
    await global_api.send_message(
        "http://127.0.0.1:19001/api/message", message.to_dict()
    )


global_api.register_message_handler(handle)

global_api.run_sync()

```
## 简要构造一个消息终端
对一个与平台相连的模块，通常涉及到标准消息的构建，可参考如下。
```python
from maim_message import (
    BaseMessageInfo,
    UserInfo,
    GroupInfo,
    FormatInfo,
    TemplateInfo,
    MessageBase,
    Seg,
    BaseMessageAPI,
)

import asyncio


api = BaseMessageAPI("0.0.0.0", 19001)

# 构造消息
user_info = UserInfo(
    # 必填
    platform="qq123",
    user_id=12348765,
    # 选填
    user_nickname="maimai",
    user_cardname="mai god",
)

group_info = GroupInfo(
    # 必填
    platform="qq123",  # platform请务必保持一致
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
    platform="qq123",
    message_id="12345678",  # 只会在reply和撤回消息等功能下启用，且可以不保证unique
    time=1234567,  # 时间戳
    group_info=group_info,
    user_info=user_info,
    # 选填和暂未启用
    format_info=format_info,
    template_info=None,
    # 自定义设置，需要参考每个模块支持的设置
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


async def handle(message_data):
    print(message_data)


api.register_message_handler(handle)


# 构造函数使得消息发送晚于server启动
async def send_message():
    await asyncio.sleep(2)
    await api.send_message("http://127.0.0.1:19000/api/message", message.to_dict())


loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
api_task = asyncio.gather(api.run(), send_message())
loop.run_until_complete(api_task)

```

## 许可证

MIT
