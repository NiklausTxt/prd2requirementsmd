"""配置管理模块"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

# 工具包根目录
PACKAGE_DIR = Path(__file__).parent
PROMPTS_DIR = PACKAGE_DIR / "prompts"

DEFAULT_PROMPT_TEMPLATE = PROMPTS_DIR / "default.md"


@dataclass
class Config:
    """分析工具配置"""

    # Ollama 服务
    ollama_host: str = "http://localhost:11434"
    model: str = "qwen3-vl:8b"

    # 分析参数
    prompt_template: str = str(DEFAULT_PROMPT_TEMPLATE)
    timeout: int = 300          # 单张图片分析超时（秒）
    max_workers: int = 1        # 并行分析线程数（本地模型建议设为1）

    # 输入输出
    image_filter: str = "*.png"  # 图片文件匹配模式
    output_path: str = "figma_analysis.json"
    project_name: str = "未命名项目"

    # 语言
    language: str = "中文"

    def update_from_file(self, config_path: str) -> None:
        """从 JSON 配置文件加载配置"""
        path = Path(config_path)
        if not path.exists():
            return
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def update_from_dict(self, data: dict) -> None:
        """从字典更新配置（忽略 None 值）"""
        for key, value in data.items():
            if value is not None and hasattr(self, key):
                setattr(self, key, value)

    def load_prompt(self) -> str:
        """加载 prompt 模板"""
        path = Path(self.prompt_template)
        if not path.exists():
            # 尝试从 prompts 目录查找
            fallback = PROMPTS_DIR / path.name
            if fallback.exists():
                path = fallback
            else:
                raise FileNotFoundError(f"Prompt 模板不存在: {self.prompt_template}")
        return path.read_text(encoding="utf-8")

    def get_api_url(self, endpoint: str) -> str:
        """获取完整的 Ollama API URL"""
        host = self.ollama_host.rstrip("/")
        return f"{host}{endpoint}"
