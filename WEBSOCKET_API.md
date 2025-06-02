# maim_message WebSocket API 文档

本文档描述了 maim_message 项目中 WebSocket 端点的详细规范，供开发者在不依赖此项目的情况下直接调用 WebSocket 接口。

## 概述

maim_message 提供基于 WebSocket 的消息通信服务，支持多平台消息路由、SSL/TLS 加密连接以及标准化的消息格式。

## 连接端点

### 基本信息
- **默认路径**: `/ws` (可通过服务器配置修改)
- **协议支持**: `ws://` (非加密) 和 `wss://` (SSL加密)
- **默认端口**: 8000 (MaimCore) 或 18000 (MessageServer)

### 连接 URL 示例
```
ws://127.0.0.1:8090/ws     # 非加密连接
wss://127.0.0.1:8090/ws    # SSL加密连接
```

## 连接认证

### 必需头部信息
| 头部字段 | 类型 | 必需 | 描述 |
|---------|------|------|------|
| `platform` | string | 否 | 平台标识符，默认为 "default" |
| `authorization` | string | 条件 | 认证令牌，当服务器启用token验证时必需 |

### 连接示例 (JavaScript)
```javascript
const ws = new WebSocket('wss://server:port/ws', [], {
  headers: {
    'platform': 'my_platform',
    'authorization': 'your_auth_token'  // 如果启用了认证
  }
});
```

### 认证失败处理
- **状态码**: 1008
- **原因**: "Invalid or missing token"
- 服务器将立即关闭连接

## 消息格式规范

### 基础消息结构 (MessageBase)

所有通过 WebSocket 传输的消息都遵循以下 JSON 结构：

```json
{
  "message_info": {
    "platform": "string",
    "message_id": "string",
    "time": 1234567.890,
    "user_info": {
      "platform": "string",
      "user_id": "string",
      "user_nickname": "string",
      "user_cardname": "string"
    },
    "group_info": {
      "platform": "string",
      "group_id": "string",
      "group_name": "string"
    },
    "format_info": {
      "content_format": ["text", "image", "emoji"],
      "accept_format": ["text", "emoji", "reply"]
    },
    "template_info": {
      "template_items": {},
      "template_name": "string",
      "template_default": true
    },
    "additional_config": {}
  },
  "message_segment": {
    "type": "seglist",
    "data": [...]
  },
  "raw_message": "string"
}
```

### 字段详细说明

#### message_info (消息元数据)
| 字段 | 类型 | 必需 | 描述 |
|------|------|------|------|
| `platform` | string | 是 | 消息来源平台标识 |
| `message_id` | string | 否 | 消息唯一标识符 |
| `time` | float | 否 | 消息时间戳 (Unix时间戳，秒) |
| `user_info` | object | 否 | 发送者信息 |
| `group_info` | object | 否 | 群组信息 (群消息时必需) |
| `format_info` | object | 否 | 支持的消息格式信息 |
| `template_info` | object | 否 | 模板相关信息 |
| `additional_config` | object | 否 | 额外配置信息 |

#### user_info (用户信息)
| 字段 | 类型 | 必需 | 描述 |
|------|------|------|------|
| `platform` | string | 是 | 用户所属平台 |
| `user_id` | string | 是 | 用户唯一标识符 |
| `user_nickname` | string | 否 | 用户昵称 |
| `user_cardname` | string | 否 | 用户群名片 |

#### group_info (群组信息)
| 字段 | 类型 | 必需 | 描述 |
|------|------|------|------|
| `platform` | string | 是 | 群组所属平台 |
| `group_id` | string | 是 | 群组唯一标识符 |
| `group_name` | string | 否 | 群组名称 |

### 消息片段 (Seg) 规范

#### 支持的片段类型

**1. 文本片段 (text)**
```json
{
  "type": "text",
  "data": "这是一段文本内容"
}
```

**2. 图片片段 (image)**
```json
{
  "type": "image",
  "data": "iVBORw0KGgoAAAANSUhEUgAA..."  // Base64编码的图片数据
}
```

**3. 表情片段 (emoji)**
```json
{
  "type": "emoji",
  "data": "😀"  // 表情符号或Base64编码数据
}
```

**4. @提及片段 (at)**
```json
{
  "type": "at",
  "data": "target_user_id"  // 被@用户的ID
}
```

**5. 回复片段 (reply)**
```json
{
  "type": "reply",
  "data": "original_message_id"  // 被回复消息的ID
}
```

**6. 片段列表 (seglist)**
```json
{
  "type": "seglist",
  "data": [
    {"type": "text", "data": "Hello "},
    {"type": "at", "data": "user123"},
    {"type": "text", "data": "!"}
  ]
}
```

## 完整消息示例

### 简单文本消息
```json
{
  "message_info": {
    "platform": "qq",
    "message_id": "msg_001",
    "time": 1703123456.789,
    "user_info": {
      "platform": "qq",
      "user_id": "123456789",
      "user_nickname": "张三"
    }
  },
  "message_segment": {
    "type": "seglist",
    "data": [
      {
        "type": "text",
        "data": "你好，这是一条测试消息！"
      }
    ]
  }
}
```

### 富媒体群消息
```json
{
  "message_info": {
    "platform": "discord",
    "message_id": "msg_002",
    "time": 1703123456.789,
    "user_info": {
      "platform": "discord",
      "user_id": "user#1234",
      "user_nickname": "Developer"
    },
    "group_info": {
      "platform": "discord",
      "group_id": "channel_5678",
      "group_name": "开发讨论"
    }
  },
  "message_segment": {
    "type": "seglist",
    "data": [
      {
        "type": "text",
        "data": "请查看这张图片："
      },
      {
        "type": "image",
        "data": "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAYEBQYFBAYGBQYHBwYIChAKCgkJChQODwwQFxQYGBcUFhYaHSUfGhsjHBYWICwgIyYnKSopGR8tMC0oMCUoKSj/..."
      },
      {
        "type": "text",
        "data": " 这是效果图。"
      }
    ]
  },
  "raw_message": "请查看这张图片：[图片] 这是效果图。"
}
```

### @用户并回复消息
```json
{
  "message_info": {
    "platform": "telegram",
    "message_id": "msg_003",
    "time": 1703123456.789,
    "user_info": {
      "platform": "telegram",
      "user_id": "@username",
      "user_nickname": "Admin"
    },
    "group_info": {
      "platform": "telegram",
      "group_id": "group_789",
      "group_name": "技术交流群"
    }
  },
  "message_segment": {
    "type": "seglist",
    "data": [
      {
        "type": "reply",
        "data": "msg_001"
      },
      {
        "type": "at",
        "data": "123456789"
      },
      {
        "type": "text",
        "data": " 你的问题已经解决了吗？"
      }
    ]
  }
}
```

## 客户端实现示例

### JavaScript WebSocket 客户端
```javascript
class MaimMessageClient {
  constructor(url, platform, token = null) {
    this.url = url;
    this.platform = platform;
    this.token = token;
    this.ws = null;
    this.connected = false;
  }

  connect() {
    return new Promise((resolve, reject) => {
      const headers = { 'platform': this.platform };
      if (this.token) {
        headers['authorization'] = this.token;
      }

      this.ws = new WebSocket(this.url, [], { headers });

      this.ws.onopen = () => {
        this.connected = true;
        console.log('WebSocket 连接已建立');
        resolve();
      };

      this.ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          this.handleMessage(message);
        } catch (error) {
          console.error('解析消息失败:', error);
        }
      };

      this.ws.onclose = (event) => {
        this.connected = false;
        if (event.code === 1008) {
          console.error('认证失败');
          reject(new Error('认证失败'));
        } else {
          console.log('WebSocket 连接已关闭');
        }
      };

      this.ws.onerror = (error) => {
        console.error('WebSocket 错误:', error);
        reject(error);
      };
    });
  }

  sendMessage(messageInfo, segments, rawMessage = null) {
    if (!this.connected) {
      throw new Error('WebSocket 未连接');
    }

    const message = {
      message_info: messageInfo,
      message_segment: {
        type: 'seglist',
        data: segments
      }
    };

    if (rawMessage) {
      message.raw_message = rawMessage;
    }

    this.ws.send(JSON.stringify(message));
  }

  sendTextMessage(platform, userId, text, groupId = null) {
    const messageInfo = {
      platform: platform,
      message_id: `msg_${Date.now()}`,
      time: Date.now() / 1000,
      user_info: {
        platform: platform,
        user_id: userId
      }
    };

    if (groupId) {
      messageInfo.group_info = {
        platform: platform,
        group_id: groupId
      };
    }

    const segments = [{
      type: 'text',
      data: text
    }];

    this.sendMessage(messageInfo, segments);
  }

  handleMessage(message) {
    console.log('收到消息:', message);
    
    // 处理消息片段
    if (message.message_segment.type === 'seglist') {
      message.message_segment.data.forEach(segment => {
        switch (segment.type) {
          case 'text':
            console.log('文本:', segment.data);
            break;
          case 'image':
            console.log('图片数据长度:', segment.data.length);
            break;
          case 'at':
            console.log('@用户:', segment.data);
            break;
          case 'reply':
            console.log('回复消息ID:', segment.data);
            break;
          default:
            console.log('未知片段类型:', segment.type);
        }
      });
    }
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
    }
  }
}

// 使用示例
const client = new MaimMessageClient(
  'wss://127.0.0.1:8090/ws',
  'my_platform',
  'optional_auth_token'
);

client.connect().then(() => {
  console.log('连接成功');
  
  // 发送文本消息
  client.sendTextMessage('my_platform', 'user123', '你好，这是测试消息！');
  
  // 发送富媒体消息
  client.sendMessage(
    {
      platform: 'my_platform',
      message_id: 'msg_custom',
      time: Date.now() / 1000,
      user_info: {
        platform: 'my_platform',
        user_id: 'user123'
      }
    },
    [
      { type: 'text', data: '请查看：' },
      { type: 'image', data: 'base64_image_data_here' }
    ]
  );
}).catch(error => {
  console.error('连接失败:', error);
});
```

### Python asyncio 客户端示例
```python
import asyncio
import json
import websockets
import ssl
from datetime import datetime

class MaimMessageClient:
    def __init__(self, url, platform, token=None, ssl_verify=None):
        self.url = url
        self.platform = platform
        self.token = token
        self.ssl_verify = ssl_verify
        self.ws = None
        self.connected = False

    async def connect(self):
        headers = {'platform': self.platform}
        if self.token:
            headers['authorization'] = self.token

        # SSL 配置
        ssl_context = None
        if self.url.startswith('wss://'):
            ssl_context = ssl.create_default_context()
            if self.ssl_verify:
                ssl_context.load_verify_locations(self.ssl_verify)
            else:
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE

        try:
            self.ws = await websockets.connect(
                self.url,
                extra_headers=headers,
                ssl=ssl_context
            )
            self.connected = True
            print(f"WebSocket 连接已建立: {self.url}")
        except Exception as e:
            print(f"连接失败: {e}")
            raise

    async def send_message(self, message_info, segments, raw_message=None):
        if not self.connected:
            raise RuntimeError("WebSocket 未连接")

        message = {
            "message_info": message_info,
            "message_segment": {
                "type": "seglist",
                "data": segments
            }
        }

        if raw_message:
            message["raw_message"] = raw_message

        await self.ws.send(json.dumps(message))

    async def send_text_message(self, user_id, text, group_id=None):
        message_info = {
            "platform": self.platform,
            "message_id": f"msg_{int(datetime.now().timestamp() * 1000)}",
            "time": datetime.now().timestamp(),
            "user_info": {
                "platform": self.platform,
                "user_id": user_id
            }
        }

        if group_id:
            message_info["group_info"] = {
                "platform": self.platform,
                "group_id": group_id
            }

        segments = [{"type": "text", "data": text}]
        await self.send_message(message_info, segments)

    async def listen(self):
        try:
            async for message in self.ws:
                try:
                    data = json.loads(message)
                    await self.handle_message(data)
                except json.JSONDecodeError as e:
                    print(f"解析消息失败: {e}")
        except websockets.exceptions.ConnectionClosed:
            print("WebSocket 连接已关闭")
            self.connected = False

    async def handle_message(self, message):
        print(f"收到消息: {message}")
        
        # 处理消息片段
        if message["message_segment"]["type"] == "seglist":
            for segment in message["message_segment"]["data"]:
                seg_type = segment["type"]
                seg_data = segment["data"]
                
                if seg_type == "text":
                    print(f"文本: {seg_data}")
                elif seg_type == "image":
                    print(f"图片数据长度: {len(seg_data)}")
                elif seg_type == "at":
                    print(f"@用户: {seg_data}")
                elif seg_type == "reply":
                    print(f"回复消息ID: {seg_data}")

    async def disconnect(self):
        if self.ws:
            await self.ws.close()
            self.connected = False

# 使用示例
async def main():
    client = MaimMessageClient(
        'wss://127.0.0.1:8090/ws',
        'my_platform',
        token='optional_auth_token',
        ssl_verify='./ssl/server.crt'
    )

    await client.connect()
    
    # 发送测试消息
    await client.send_text_message('user123', '你好，这是来自Python客户端的消息！')
    
    # 监听消息
    await client.listen()

if __name__ == "__main__":
    asyncio.run(main())
```

## SSL/TLS 配置

### 服务器端 SSL 设置
```python
# 创建支持 SSL 的服务器
server = MessageServer(
    host="0.0.0.0",
    port=8090,
    ssl_certfile="./ssl/server.crt",  # 证书文件
    ssl_keyfile="./ssl/server.key",   # 私钥文件
    mode="ws"
)
```

### 客户端 SSL 验证
```python
# 客户端配置 SSL 证书验证
config = TargetConfig(
    url="wss://127.0.0.1:8090/ws",
    ssl_verify="./ssl/server.crt"  # 用于验证服务器证书
)
```

## 错误处理

### 常见错误码
| 错误码 | 描述 | 处理建议 |
|-------|------|----------|
| 1008 | 认证失败 | 检查 authorization 头部和令牌有效性 |
| 1000 | 正常关闭 | 正常的连接关闭 |
| 1006 | 异常关闭 | 网络问题或服务器异常，尝试重连 |

### 重连机制
建议实现指数退避重连机制：
```javascript
async function connectWithRetry(client, maxRetries = 5) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      await client.connect();
      return;
    } catch (error) {
      const delay = Math.min(1000 * Math.pow(2, i), 30000);
      console.log(`连接失败，${delay}ms 后重试...`);
      await new Promise(resolve => setTimeout(resolve, delay));
    }
  }
  throw new Error('达到最大重试次数');
}
```

## 最佳实践

1. **消息ID唯一性**: 确保每条消息的 `message_id` 在平台内唯一
2. **时间戳精度**: 使用秒级时间戳，支持小数部分以提供毫秒精度
3. **Base64编码**: 所有二进制数据（图片、文件等）必须进行 Base64 编码
4. **平台标识**: 保持 `platform` 字段在整个消息链路中的一致性
5. **错误处理**: 实现完善的重连机制和错误恢复策略
6. **消息大小**: 建议单条消息不超过 1MB，大文件应考虑分片传输

## 注意事项

- 所有字符串字段使用 UTF-8 编码
- JSON 字段名区分大小写
- 可选字段可以省略或设为 `null`
- 服务器会验证消息格式，无效消息可能导致连接关闭
- 长时间无活动的连接可能会被服务器主动关闭