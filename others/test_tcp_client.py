from maim_message import (
    BaseMessageInfo,
    UserInfo,
    GroupInfo,
    FormatInfo,
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
        platform=platform,
        user_id="12348765",  # 修改为字符串类型
        user_nickname="maimai",
        user_cardname="mai god",
    )

    group_info = GroupInfo(
        platform=platform,
        group_id="12345678",  # 修改为字符串类型
        group_name="test_group",
    )

    format_info = FormatInfo(
        content_format=["text"],
        accept_format=["text"],
    )

    message_info = BaseMessageInfo(
        platform=platform,
        message_id="12345678",
        time=1234567.0,
        group_info=group_info,
        user_info=user_info,
        format_info=format_info,
        template_info=None,
        additional_config={},
    )

    message_segment = Seg(
        "seglist",
        [
            Seg("text", f"这是来自平台 {platform} 的测试消息"),
        ],
    )

    message = MessageBase(
        message_info=message_info,
        message_segment=message_segment,
        raw_message="test message",
    )
    return message


async def message_handler(message):
    """消息处理函数"""
    print(f"收到消息: {message}")


# 配置两个不同平台的路由，带有令牌认证
route_config = RouteConfig(
    route_config={
        "platform1": TargetConfig(
            url="tcp://127.0.0.1:8090",  # 本地测试服务器
            token="test_token_1",  # 使用有效令牌1
            ssl_verify=None,
        ),
        "platform2": TargetConfig(
            url="tcp://127.0.0.1:8090",  # 同一个服务器，不同平台
            token="test_token_2",  # 使用有效令牌2
            ssl_verify=None,
        ),
    }
)

# 创建路由器实例
router = Router(route_config)


async def main():
    # 注册消息处理器
    router.register_class_handler(message_handler)

    # 启动路由器（会自动连接所有配置的平台）
    router_task = asyncio.create_task(router.run())

    # 等待连接建立
    while len(router.clients.keys()) < 2:
        print("等待连接建立...")
        await asyncio.sleep(1)

    # 从不同平台发送测试消息
    print("发送 platform1 的消息...")
    await router.send_message(construct_message("platform1"))
    await router.send_message(construct_message("platform1"))
    await router.send_message(construct_message("platform1"))
    await router.send_message(construct_message("platform1"))

    print("发送 platform2 的消息...")
    await router.send_message(construct_message("platform2"))

    # 保持运行直到被中断
    await router_task


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("正在关闭连接...")
        asyncio.run(router.stop())
        print("已关闭所有连接")
