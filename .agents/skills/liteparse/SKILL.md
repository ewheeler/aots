---
name: liteparse
description: Parse, convert, or spatially extract text from local unstructured files such as PDFs, Office documents, spreadsheets, and images without cloud dependencies.
---

# LiteParse

Use this skill when a task needs local document parsing or conversion for PDFs, DOCX, PPTX, XLSX, images, CSV/TSV, or similar files.

## Setup

Install the upstream skill when the agent harness supports skills:

```bash
npx skills add run-llama/llamaparse-agent-skills --skill liteparse
```

Install the local parser CLI when parsing is needed:

```bash
npm i -g @llamaindex/liteparse
lit --version
```

Office documents require LibreOffice. Images require ImageMagick.

## Workflow

1. Confirm `lit --version` works, or ask the user to install LiteParse.
2. Identify input files and desired output: text, JSON with bounding boxes, page screenshots, or batch output.
3. Prefer local parsing and do not upload sensitive documents to cloud services unless explicitly approved.
4. Produce the exact `lit` command or script before running it when files may contain sensitive data.
5. Save outputs to explicit paths and summarize what was extracted, skipped, or failed.

## Common Commands

Parse a single file:

```bash
lit parse document.pdf
lit parse document.pdf --format json -o output.json
lit parse document.pdf --target-pages "1-5,10,15-20"
lit parse document.pdf --no-ocr
```

Batch parse a directory:

```bash
lit batch-parse ./input-directory ./output-directory
lit batch-parse ./input ./output --extension .pdf --recursive
```

Generate page screenshots:

```bash
lit screenshot document.pdf -o ./screenshots
lit screenshot document.pdf --pages "1,3,5" -o ./screenshots
lit screenshot document.pdf --dpi 300 --format png -o ./screenshots
```

Use a config file:

```bash
lit parse document.pdf --config liteparse.config.json
```

## Options To Consider

- `--format json` for structured output with bounding boxes.
- `--format text` for plain text output.
- `--target-pages` or `--max-pages` to limit scope.
- `--no-ocr` for faster text-only PDFs.
- `--ocr-language <code>` for non-English OCR.
- `--ocr-server-url <url>` only when the user approves using an external OCR service.
- `--dpi 300` for higher-quality rendering when OCR or screenshots need detail.

## Rules

- Treat source documents as potentially sensitive.
- Prefer local parsing over cloud parsing by default.
- Do not commit parsed outputs unless the project explicitly treats them as review artifacts.
- Record command, input paths, output paths, page range, OCR settings, and known extraction limits in the task summary.
