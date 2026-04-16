"""核心分析引擎 — 调用 Ollama VL 模型分析 Figma 截图"""

import base64
import json
import os
import signal
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from .config import Config


class FigmaAnalyzer:
    """Figma 截图分析器"""

    def __init__(self, config: Config):
        self.config = config
        self._ollama_proc = None  # 如果自行启动了 Ollama，记录进程

    # ── Ollama 生命周期 ──────────────────────────────────────

    def check_ollama(self) -> bool:
        """检测 Ollama 服务是否可用"""
        try:
            req = Request(self.config.get_api_url("/api/tags"))
            with urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read())
                    models = [m["name"] for m in data.get("models", [])]
                    # 检查目标模型是否存在（支持模糊匹配）
                    model_name = self.config.model
                    return any(
                        m == model_name or m.startswith(model_name.split(":")[0])
                        for m in models
                    )
        except (URLError, OSError):
            pass
        return False

    def ensure_ollama(self) -> None:
        """确保 Ollama 服务运行且模型可用"""
        if self.check_ollama():
            return

        print("[figma2req] Ollama 服务未运行，尝试启动...")
        try:
            proc = subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._ollama_proc = proc
            # 等待服务就绪
            for _ in range(15):
                time.sleep(1)
                if self.check_ollama():
                    print("[figma2req] Ollama 服务已启动")
                    return
            raise RuntimeError("Ollama 启动超时")
        except FileNotFoundError:
            raise RuntimeError("未找到 ollama 命令，请先安装 Ollama: https://ollama.com")

        if not self.check_ollama():
            raise RuntimeError(f"模型 {self.config.model} 不存在，请先拉取: ollama pull {self.config.model}")

    def stop_ollama(self) -> None:
        """停止自行启动的 Ollama 进程"""
        if self._ollama_proc is not None:
            try:
                self._ollama_proc.terminate()
                self._ollama_proc.wait(timeout=5)
            except Exception:
                try:
                    self._ollama_proc.kill()
                except Exception:
                    pass
            self._ollama_proc = None

    # ── 图片处理 ─────────────────────────────────────────────

    @staticmethod
    def encode_image(image_path: str) -> str:
        """将图片文件编码为 base64 字符串"""
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    @staticmethod
    def collect_images(image_dir: str, pattern: str = "*.png") -> list[str]:
        """收集目录下匹配的图片文件，按文件名排序"""
        dir_path = Path(image_dir)
        if not dir_path.is_dir():
            raise FileNotFoundError(f"目录不存在: {image_dir}")
        images = sorted(dir_path.glob(pattern))
        if not images:
            raise FileNotFoundError(f"目录 {image_dir} 中没有匹配 {pattern} 的文件")
        return [str(img) for img in images]

    # ── Ollama API 调用 ──────────────────────────────────────

    def analyze_single(self, image_path: str, prompt: str, retries: int = 2) -> dict:
        """分析单张图片，返回结果字典（支持重试）"""
        b64 = self.encode_image(image_path)

        payload = json.dumps({
            "model": self.config.model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [b64],
                }
            ],
            "stream": False,
        }, ensure_ascii=False).encode("utf-8")

        last_error = None
        for attempt in range(1, retries + 2):
            try:
                req = Request(
                    self.config.get_api_url("/api/chat"),
                    data=payload,
                    headers={"Content-Type": "application/json"},
                )
                with urlopen(req, timeout=self.config.timeout) as resp:
                    data = json.loads(resp.read())

                content = data.get("message", {}).get("content", "")
                if not content:
                    raise RuntimeError("模型返回空内容，可能模型尚未就绪")

                return {
                    "file": Path(image_path).name,
                    "content": content,
                    "model": self.config.model,
                    "duration": data.get("total_duration", 0) / 1e9,  # 纳秒→秒
                }
            except Exception as e:
                last_error = e
                if attempt <= retries:
                    print(f"    重试 {attempt}/{retries}...")
                    time.sleep(5)

        raise RuntimeError(f"分析 {image_path} 失败（已重试 {retries} 次）: {last_error}")

    def analyze_batch(self, image_paths: list[str], prompt: str) -> list[dict]:
        """分析多张图片，max_workers=1 时串行执行，>1 时并行"""
        results = []
        total = len(image_paths)

        if self.config.max_workers <= 1:
            # 串行模式 — 本地模型更稳定
            print(f"[figma2req] 开始分析 {total} 张图片 (串行模式)")
            for i, path in enumerate(image_paths):
                filename = Path(path).name
                try:
                    print(f"  [{i + 1}/{total}] {filename} 分析中...")
                    result = self.analyze_single(path, prompt)
                    results.append(result)
                    print(f"  [{i + 1}/{total}] {filename} 完成 ({result['duration']:.1f}s)")
                except Exception as e:
                    print(f"  [{i + 1}/{total}] {filename} 失败: {e}", file=sys.stderr)
                    results.append({
                        "file": filename,
                        "content": f"分析失败: {e}",
                        "model": self.config.model,
                        "duration": 0,
                    })
        else:
            # 并行模式
            results_slot = [None] * total
            print(f"[figma2req] 开始分析 {total} 张图片 (并行数: {self.config.max_workers})")

            with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
                future_to_idx = {}
                for i, path in enumerate(image_paths):
                    future = executor.submit(self.analyze_single, path, prompt)
                    future_to_idx[future] = i

                for future in as_completed(future_to_idx):
                    idx = future_to_idx[future]
                    filename = Path(image_paths[idx]).name
                    try:
                        result = future.result()
                        results_slot[idx] = result
                        print(f"  [{idx + 1}/{total}] {filename} 完成 ({result['duration']:.1f}s)")
                    except Exception as e:
                        print(f"  [{idx + 1}/{total}] {filename} 失败: {e}", file=sys.stderr)
                        results_slot[idx] = {
                            "file": filename,
                            "content": f"分析失败: {e}",
                            "model": self.config.model,
                            "duration": 0,
                        }

            results = [r for r in results_slot if r is not None]

        return [r for r in results if r is not None]

    # ── 文档生成 ─────────────────────────────────────────────

    def generate_document(
        self,
        results: list[dict],
        output_path: str,
        project_name: str | None = None,
    ) -> str:
        """将分析结果汇总为 JSON 需求文档"""
        project_name = project_name or self.config.project_name

        document = {
            "project": project_name,
            "version": "1.0",
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "model_used": f"ollama {self.config.model}",
            "source": "Figma设计截图分析",
            "description": f"基于{len(results)}张Figma设计截图的UI/UX分析结果，提取页面内容、布局、交互及后端需求",
            "screenshots": results,
        }

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        with open(output, "w", encoding="utf-8") as f:
            json.dump(document, f, ensure_ascii=False, indent=2)

        size_kb = output.stat().st_size / 1024
        print(f"[figma2req] 文档已生成: {output} ({size_kb:.1f} KB)")
        return str(output)
