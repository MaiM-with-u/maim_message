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
import os


def construct_message(platform):
    # 构造消息
    user_info = UserInfo(
        # 必填
        platform=platform,
        user_id="12348765",
        # 选填
        user_nickname="maimai",
        user_cardname="mai god",
    )

    group_info = GroupInfo(
        # 必填
        platform=platform,  # platform请务必保持一致
        group_id="12345678",
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
            url="ws://127.0.0.1:8090/ws",  # 使用ws协议
            token=None,  # 如果需要token验证则在这里设置
        ),
        "qq321": TargetConfig(
            url="ws://127.0.0.1:8090/ws",
            token=None,
        ),
        "qq111": TargetConfig(
            url="ws://127.0.0.1:8090/ws",
            token=None,
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
                    "url": "ws://127.0.0.1:8090/ws",
                    "token": None,
                },
                # 移除qq321
                # 更改qq111的token
                "qq111": {
                    "url": "ws://127.0.0.1:8090/ws",
                    "token": None,
                },
                # 添加新平台
                "qq999": {
                    "url": "ws://127.0.0.1:8090/ws",
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

        while True:
            # 发送测试消息
            print("发送测试消息...")
            try:
                await router.send_message(construct_message("qq123"))
            except Exception as e:
                print(f"发送消息失败: {e}")
            await asyncio.sleep(5)

    finally:
        print("正在关闭连接...")
        await router.stop()
        print("已关闭所有连接")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass  # 让asyncio.run处理清理工作
