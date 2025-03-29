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
