"""figma2req — 基于 Figma 截图生成需求文档的 CLI 工具"""

import argparse
import sys

from .analyzer import FigmaAnalyzer
from .config import Config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="figma2req",
        description="基于 Figma 设计截图，使用本地 VL 模型生成结构化需求文档",
    )
    parser.add_argument(
        "image_dir",
        help="包含 Figma 截图的目录路径",
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="输出 JSON 文件路径 (默认: ./figma_analysis.json)",
    )
    parser.add_argument(
        "-m", "--model",
        default=None,
        help="Ollama 模型名 (默认: qwen3-vl:8b)",
    )
    parser.add_argument(
        "-p", "--prompt",
        default=None,
        help="自定义 Prompt 模板文件路径",
    )
    parser.add_argument(
        "-n", "--name",
        default=None,
        help="项目名称",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="Ollama 服务地址 (默认: http://localhost:11434)",
    )
    parser.add_argument(
        "-w", "--workers",
        type=int,
        default=None,
        help="并行分析线程数 (默认: 3)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="单张图片分析超时秒数 (默认: 120)",
    )
    parser.add_argument(
        "-f", "--filter",
        default=None,
        help="图片文件匹配模式 (默认: *.png)",
    )
    parser.add_argument(
        "-l", "--language",
        default=None,
        help="输出语言 (默认: 中文)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # 构建配置：默认值 → CLI 参数覆盖
    config = Config()
    config.update_from_dict({
        "ollama_host": args.host,
        "model": args.model,
        "prompt_template": args.prompt,
        "output_path": args.output,
        "project_name": args.name,
        "max_workers": args.workers,
        "timeout": args.timeout,
        "image_filter": args.filter,
        "language": args.language,
    })

    analyzer = FigmaAnalyzer(config)

    try:
        # 1. 确保 Ollama 可用
        print(f"[figma2req] 检查 Ollama 服务 (模型: {config.model})...")
        analyzer.ensure_ollama()

        # 2. 收集图片
        images = analyzer.collect_images(args.image_dir, config.image_filter)
        print(f"[figma2req] 找到 {len(images)} 张图片")

        # 3. 加载 prompt
        prompt_template = config.load_prompt()
        prompt = prompt_template.replace("{language}", config.language)

        # 4. 并行分析
        results = analyzer.analyze_batch(images, prompt)

        if not results:
            print("[figma2req] 没有成功分析任何图片", file=sys.stderr)
            return 1

        # 5. 生成文档
        analyzer.generate_document(results, config.output_path, config.project_name)

        print("[figma2req] 完成!")
        return 0

    except FileNotFoundError as e:
        print(f"[figma2req] 错误: {e}", file=sys.stderr)
        return 1
    except RuntimeError as e:
        print(f"[figma2req] 错误: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n[figma2req] 用户中断")
        return 130
    finally:
        analyzer.stop_ollama()


if __name__ == "__main__":
    sys.exit(main())
