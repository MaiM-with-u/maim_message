import logging
import sys
from typing import Optional, Union

# 默认日志格式
DEFAULT_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# 全局日志对象
_logger = None


def setup_logger(
    name: str = "maim_message",
    level: Union[int, str] = logging.INFO,
    format_str: str = DEFAULT_FORMAT,
    external_logger: Optional[logging.Logger] = None,
) -> logging.Logger:
    """
    配置并返回日志记录器

    Args:
        name: 日志记录器名称
        level: 日志级别
        format_str: 日志格式
        external_logger: 外部提供的日志记录器

    Returns:
        已配置的日志记录器
    """
    global _logger

    if external_logger:
        _logger = external_logger
        # 确保外部logger至少具有指定的日志级别
        # if isinstance(level, str):
        #     level = getattr(logging, level.upper())
        # if _logger.level > level:
        #     _logger.setLevel(level)
        return _logger

    if _logger is not None:
        # 如果已有logger，可能需要更新日志级别
        # if isinstance(level, str):
        #     level = getattr(logging, level.upper())
        # if _logger.level > level:
        #     _logger.setLevel(level)
        return _logger

    # 创建新的日志记录器
    logger = logging.getLogger(name)

    # 设置日志级别
    if isinstance(level, str):
        level = getattr(logging, level.upper())
    logger.setLevel(level)

    # 创建处理器和格式化器
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(format_str)
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    _logger = logger
    return logger


def get_logger() -> logging.Logger:
    """
    获取已配置的日志记录器，如果未配置则创建一个默认的

    Returns:
        日志记录器
    """
    global _logger
    if _logger is None:
        return setup_logger()
    return _logger


def set_external_logger(
    external_logger: logging.Logger, level: Optional[Union[int, str]] = None
):
    """
    设置外部日志记录器作为全局日志记录器。这是外部系统集成的首选方法。

    Args:
        external_logger: 外部提供的日志记录器
        level: 可选的日志级别，如果提供则会覆盖外部日志记录器的级别

    Returns:
        已设置的日志记录器
    """
    if level is not None:
        if isinstance(level, str):
            level = getattr(logging, level.upper())
        external_logger.setLevel(level)

    return setup_logger(external_logger=external_logger)


def reset_logger():
    """
    重置日志记录器到未初始化状态，以便重新配置
    """
    global _logger
    _logger = None


def configure_uvicorn_logging(level: Union[int, str] = None):
    """
    配置uvicorn日志系统以使用我们的日志设置

    Args:
        level: 日志级别，如果不提供则使用当前的日志级别
    """
    # 获取当前日志级别
    if level is None:
        current_logger = get_logger()
        level = current_logger.level

    if isinstance(level, str):
        level = getattr(logging, level.upper())

    # 获取或创建一个格式化器
    current_logger = get_logger()
    formatter = None
    if current_logger.handlers:
        formatter = current_logger.handlers[0].formatter
    else:
        formatter = logging.Formatter(DEFAULT_FORMAT)

    # 配置uvicorn相关的日志记录器
    loggers = [
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
        "uvicorn.asgi",
    ]

    for logger_name in loggers:
        logger = logging.getLogger(logger_name)
        # 移除所有现有处理器
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

        # 添加到控制台的处理器
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        # 设置日志级别
        logger.setLevel(level)
        logger.propagate = False  # 避免日志重复

    return True


def get_uvicorn_log_config(level: Union[int, str] = None) -> dict:
    """
    获取适用于uvicorn的日志配置字典

    Args:
        level: 日志级别，如果不提供则使用当前的日志级别

    Returns:
        uvicorn日志配置字典
    """
    # 获取当前日志级别
    if level is None:
        current_logger = get_logger()
        level = current_logger.level

    # 将日志级别转换为uvicorn可接受的字符串格式
    if isinstance(level, int):
        if level <= logging.DEBUG:
            level_name = "DEBUG"
        elif level <= logging.INFO:
            level_name = "INFO"
        elif level <= logging.WARNING:
            level_name = "WARNING"
        elif level <= logging.ERROR:
            level_name = "ERROR"
        else:
            level_name = "CRITICAL"
    else:
        level_name = level.upper()  # 假设它是一个字符串

    # 从当前记录器获取格式
    current_logger = get_logger()
    log_format = DEFAULT_FORMAT
    if current_logger.handlers:
        formatter = current_logger.handlers[0].formatter
        if hasattr(formatter, "_fmt"):
            log_format = formatter._fmt

    # 返回uvicorn配置
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": log_format,
            },
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": sys.stderr,
            },
        },
        "loggers": {
            "uvicorn": {
                "handlers": ["default"],
                "level": level_name,
                "propagate": False,
            },
            "uvicorn.error": {
                "handlers": ["default"],
                "level": level_name,
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": ["default"],
                "level": level_name,
                "propagate": False,
            },
        },
    }
