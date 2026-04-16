"""figma2req — 基于 Figma 截图生成需求文档"""

from .analyzer import FigmaAnalyzer
from .cli import main
from .config import Config

__all__ = ["FigmaAnalyzer", "Config", "main"]
__version__ = "0.1.0"
