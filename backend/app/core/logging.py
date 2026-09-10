"""日志配置"""
import sys
from loguru import logger
from .config import settings


def setup_logger():
    """配置 loguru 输出"""
    logger.remove()
    logger.add(
        sys.stdout,
        level="DEBUG" if settings.DEBUG else "INFO",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True,
    )
    logger.add(
        "data/logs/lbp_m_{time:YYYY-MM-DD}.log",
        level="INFO",
        rotation="10 MB",
        retention="7 days",
        encoding="utf-8",
    )


setup_logger()