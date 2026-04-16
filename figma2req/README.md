# figma2req

基于 Figma 设计截图，使用本地 Ollama VL 模型生成结构化 JSON 需求文档。

## 前置条件

- Python >= 3.10
- [Ollama](https://ollama.com) 已安装并运行
- 已拉取 VL 模型：`ollama pull qwen3-vl:8b`

## 快速开始

```bash
# 分析 pic/ 目录下的所有 PNG 截图
python -m figma2req pic/ -n "项目名称"
```

执行后会在当前目录生成 `figma_analysis.json`。

## 命令行参数

```
python -m figma2req <image_dir> [OPTIONS]
```

| 参数 | 短写 | 默认值 | 说明 |
|------|------|--------|------|
| `image_dir` | - | 必填 | 截图所在目录 |
| `--output` | `-o` | `figma_analysis.json` | 输出 JSON 文件路径 |
| `--name` | `-n` | `未命名项目` | 项目名称（写入文档头部） |
| `--model` | `-m` | `qwen3-vl:8b` | Ollama 模型名 |
| `--host` | - | `http://localhost:11434` | Ollama 服务地址 |
| `--prompt` | `-p` | 内置模板 | 自定义 prompt 模板文件路径 |
| `--language` | `-l` | `中文` | 输出语言 |
| `--workers` | `-w` | `1` | 并行线程数（本地模型建议 1） |
| `--timeout` | - | `300` | 单张图片超时秒数 |
| `--filter` | `-f` | `*.png` | 图片文件匹配模式 |

## 示例

```bash
# 指定输出文件
python -m figma2req pic/ -o docs/requirements.json -n "临床试验管理系统"

# 使用自定义 prompt（偏后端分析）
python -m figma2req pic/ -p figma2req/prompts/backend.md

# 英文输出
python -m figma2req pic/ -l English

# 分析 JPG 格式截图
python -m figma2req screenshots/ -f "*.jpg"
```

## 输出格式

生成的 JSON 文档结构：

```json
{
  "project": "项目名称",
  "version": "1.0",
  "generated_at": "2026-04-16 16:30:00",
  "model_used": "ollama qwen3-vl:8b",
  "source": "Figma设计截图分析",
  "description": "基于N张Figma设计截图的UI/UX分析结果...",
  "screenshots": [
    {
      "file": "1.png",
      "content": "## markdown格式的详细分析内容...",
      "model": "qwen3-vl:8b",
      "duration": 15.2
    }
  ]
}
```

每张截图对应 `screenshots` 数组中的一个对象，`content` 字段为 markdown 格式的完整分析报告。

## 自定义 Prompt

在 `figma2req/prompts/` 下创建新的 `.md` 文件，通过 `-p` 指定即可。

模板中可用占位符：`{language}` — 会被替换为 `--language` 参数值。

## 注意事项

- 本地模型建议串行运行（`workers=1` 默认值），并行会导致资源争抢和空响应
- 首次推理较慢（模型加载），后续会快很多
- 工具会自动检测 Ollama 是否运行，未运行会尝试自动启动
