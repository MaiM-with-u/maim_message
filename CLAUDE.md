# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

maim_message is a Python library that provides standardized message structures and WebSocket/TCP communication for the MaimBot ecosystem. It serves as a universal messaging interface library that decouples MaimBot components (core services, platform adapters, plugins) through unified message formats.

## Core Architecture

### Message System
- **MessageBase**: Core message container with `message_info` (metadata) and `message_segment` (content)
- **Seg**: Message content segments supporting different types (text, image, emoji, at, reply, seglist)
- **BaseMessageInfo**: Message metadata including platform, user info, group info, timestamps

### Communication Modes
- **WebSocket Mode** (default): Uses FastAPI + uvicorn for WebSocket connections
- **TCP Mode**: Direct TCP socket communication (experimental)
- **SSL/TLS Support**: Available for both WebSocket (WSS) and TCP connections

### Key Components
- **Router**: Client-side connection manager for multiple platform connections
- **MessageServer**: Server component accepting incoming connections from adapters/clients  
- **MessageClient**: Individual client connection (managed internally by Router)

## Development Commands

### Installation
```bash
# Install from PyPI
pip install maim_message

# Development installation
git clone https://github.com/MaiM-with-u/maim_message
cd maim_message
pip install -e .
```

### Code Quality
```bash
# Format code (Black)
black --line-length=100 src/

# Sort imports (isort)
isort --profile=black --line-length=100 src/

# Type checking (mypy)
mypy src/ --strict --ignore-missing-imports
```

### Testing
- Test files are located in `others/` directory
- Run individual test files: `python others/test_client.py`, `python others/test_server.py`
- TCP mode tests: `python others/test_tcp_client.py`, `python others/test_tcp_server.py`

## Usage Patterns

### As Client (Adapter/Plugin connecting to server)
Use `Router` with `RouteConfig` to connect to MaimCore or other services:
```python
router = Router(RouteConfig(route_config={
    "platform_name": TargetConfig(url="ws://host:port/ws", token=None)
}))
```

### As Server (MaimCore/middleware accepting connections)  
Use `MessageServer` to accept incoming adapter connections:
```python
server = MessageServer(host="0.0.0.0", port=18000, mode="ws")
server.register_message_handler(handler_function)
```

## Connection Protocols

- **WebSocket**: `ws://host:port/ws` or `wss://host:port/ws` (with SSL)
- **TCP**: `tcp://host:port` (experimental mode)
- Default ports: 8000 (typical MaimCore), 18000 (default MessageServer)

## Dependencies

Core dependencies from pyproject.toml:
- fastapi>=0.70.0 (WebSocket server)
- uvicorn>=0.15.0 (ASGI server)
- aiohttp>=3.8.0 (WebSocket client)
- pydantic>=1.9.0 (data validation)
- websockets>=10.0 (WebSocket support)
- cryptography (SSL/TLS support)