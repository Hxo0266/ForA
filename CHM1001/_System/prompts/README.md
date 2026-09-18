# 跨平台 Prompt 使用说明

这套 prompt 与具体平台无关，可直接用于 **ChatGPT / OpenAI API / Claude / DeepSeek / 任意本地模型**。它们不依赖任何工具调用，纯文本进出。

## 两个 prompt 的分工

| Prompt | 输入 | 输出 | 什么时候用 |
|:--|:--|:--|:--|
| `01_inbox_triage.md` | `0_inbox/` 的文件名清单 | 分类表（文件 → 目标文件夹）+ 需人工确认项 | 想手动核对分类结果，或在不装 WorkBuddy 的机器上分类 |
| `02_essence_extraction.md` | 一份课件的提取文本 | 该课件的 Essence Markdown | 想用别的模型写笔记，或想把同一份课件喂给两个模型对比 |

## 各平台用法

**ChatGPT / Claude / DeepSeek 网页版**
1. 打开对应 prompt 文件，整段复制
2. 新开对话，粘贴 prompt
3. 按 prompt 里的 `## 输入` 小节，把你这边的内容（文件清单 / 提取文本）贴在后面
4. 发送

**OpenAI API / DeepSeek API / Ollama 等**
- `01` 建议 `temperature=0`（分类要确定性）
- `02` 建议 `temperature=0.2~0.4`（保准确，允许轻微改写）
- 两者都不需要 system prompt 之外的额外配置

**和 WorkBuddy 里的 skill 是什么关系**
- WorkBuddy 的 skill 会**自动**读文件、跑脚本、写结果到磁盘
- 这里的 prompt 是「**手动版**」：你自己把输入贴进去，拿到结果再自己保存
- 两者共用同一套判据与同一份输出格式，结果可以直接互相对照

## 怎么拿到 prompt 需要的输入

**文件清单（给 01）**
```bash
# WorkBuddy 端
python "_System/scripts/run_pipeline.py" --root "." --skip-triage
```
或直接看 `_System/logs/triage_<时间戳>.md` 的第一张表。

**课件提取文本（给 02）**
```bash
python "$HOME/.workbuddy/skills/essence-extraction/scripts/extract_slides.py" --root "."
```
然后打开 `_System/extracted/<课件名>.slides.txt`，整篇复制。

## 统一输出契约

两个 prompt 都要求模型输出**可直接落盘的 Markdown**，不含任何「好的，以下是……」之类的前言。02 的输出应当能直接存成 `3_Essence/<课件名>.md` 而不需要再加工。
