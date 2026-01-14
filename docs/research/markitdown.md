# MarkItDown Library Research

**Research Date**: 2026-01-14
**Library Version**: 0.1.4 (released Dec 1, 2025)
**Repository**: https://github.com/microsoft/markitdown
**PyPI**: https://pypi.org/project/markitdown/
**License**: MIT
**Author**: Adam Fourney (Microsoft)

---

## 1. What Is MarkItDown?

MarkItDown is a lightweight Python utility developed by Microsoft for converting various file formats to Markdown. It is designed for use with LLMs and text analysis pipelines, focusing on preserving document structure (headings, lists, tables, links) rather than just extracting raw text.

**Comparison**: Similar to `textract`, but with a focus on preserving document structure as Markdown output suitable for LLM consumption.

---

## 2. Supported File Formats

| Format | Extension(s) | Optional Extra | Notes |
|--------|--------------|----------------|-------|
| PDF | `.pdf` | `[pdf]` | Uses pdfminer; no built-in OCR |
| Word | `.docx` | `[docx]` | Uses mammoth library |
| PowerPoint | `.pptx` | `[pptx]` | Uses python-pptx |
| Excel | `.xlsx` | `[xlsx]` | Uses pandas |
| Excel (legacy) | `.xls` | `[xls]` | Uses xlrd |
| Images | `.jpg`, `.png` | - | EXIF metadata; LLM-based descriptions optional |
| Audio | `.wav`, `.mp3` | `[audio-transcription]` | Uses speech_recognition (Google API) |
| HTML | `.html` | - | Special handling for Wikipedia |
| CSV | `.csv` | - | Converts to Markdown tables |
| JSON | `.json` | - | Structured text output |
| XML | `.xml` | - | Structured text output |
| ZIP | `.zip` | - | Recursively processes contents |
| EPUB | `.epub` | - | E-book extraction |
| Outlook | `.msg` | `[outlook]` | Email message extraction |
| YouTube | URLs | `[youtube-transcription]` | Fetches transcripts |

---

## 3. Installation

**Requirements**: Python 3.10 or higher (supports 3.10, 3.11, 3.12, 3.13)

### Basic Installation (All Dependencies)
```bash
pip install 'markitdown[all]'
```

### Selective Installation
```bash
# Only PDF, Word, and PowerPoint support
pip install 'markitdown[pdf, docx, pptx]'

# Only PDF
pip install 'markitdown[pdf]'
```

### Available Optional Extras
- `all` - All dependencies
- `pdf` - PDF support (pdfminer)
- `docx` - Word document support (mammoth)
- `pptx` - PowerPoint support (python-pptx)
- `xlsx` - Excel support (pandas)
- `xls` - Legacy Excel support (xlrd)
- `outlook` - Outlook message support
- `audio-transcription` - Audio file transcription
- `youtube-transcription` - YouTube video transcription
- `az-doc-intel` - Azure Document Intelligence (enhanced PDF processing)

### From Source
```bash
git clone git@github.com:microsoft/markitdown.git
cd markitdown
pip install -e 'packages/markitdown[all]'
```

---

## 4. API Usage

### Basic File Conversion
```python
from markitdown import MarkItDown

md = MarkItDown()
result = md.convert("document.pdf")
print(result.text_content)
```

### Disabling Plugins
```python
md = MarkItDown(enable_plugins=False)
result = md.convert("document.docx")
```

### Stream-Based Conversion
```python
import io
from markitdown import MarkItDown

md = MarkItDown()

# From binary file handle
with open("document.pdf", "rb") as f:
    result = md.convert_stream(f)
    print(result.text_content)

# From BytesIO
binary_data = get_binary_data_somehow()
stream = io.BytesIO(binary_data)
result = md.convert_stream(stream)
```

**Important**: `convert_stream()` requires a **binary** file-like object (`io.BytesIO`, file opened with `"rb"`). Text-based objects like `io.StringIO` are NOT supported (breaking change in v0.1.0).

### LLM-Powered Image Descriptions
```python
from markitdown import MarkItDown
from openai import OpenAI

client = OpenAI()
md = MarkItDown(
    llm_client=client,
    llm_model="gpt-4o",
    llm_prompt="Write a detailed description for this image."  # optional
)
result = md.convert("photo.jpg")
print(result.text_content)
```

### Azure Document Intelligence (Enhanced PDF)
```python
from markitdown import MarkItDown

md = MarkItDown(docintel_endpoint="<your-azure-endpoint>")
result = md.convert("complex-document.pdf")
print(result.text_content)
```

### Batch Conversion Example
```python
from pathlib import Path
from markitdown import MarkItDown

def convert_directory(input_dir: str, output_dir: str = "output"):
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    md = MarkItDown()
    target_formats = (".docx", ".xlsx", ".pdf", ".pptx")

    for file_path in input_path.rglob("*"):
        if file_path.suffix.lower() in target_formats:
            try:
                result = md.convert(str(file_path))
                output_file = output_path / f"{file_path.stem}.md"
                output_file.write_text(result.text_content, encoding="utf-8")
                print(f"Converted: {file_path.name}")
            except Exception as e:
                print(f"Error converting {file_path.name}: {e}")
```

---

## 5. CLI Usage

### Basic Conversion
```bash
# Output to stdout
markitdown document.pdf

# Redirect to file
markitdown document.pdf > output.md

# Explicit output file
markitdown document.pdf -o output.md
```

### Pipe Input
```bash
cat document.pdf | markitdown
```

### With Plugins
```bash
# List available plugins
markitdown --list-plugins

# Enable plugins
markitdown --use-plugins document.pdf
```

### Azure Document Intelligence via CLI
```bash
markitdown document.pdf -o output.md -d -e "<azure-endpoint>"
```

### Using uvx (No Install)
```bash
uvx markitdown document.pdf
```

---

## 6. Output Format

MarkItDown produces **GitHub-compatible Markdown** that preserves:

- **Headings**: Detected via font size in source documents
- **Lists**: Ordered and unordered lists preserved
- **Tables**: Converted to Markdown table syntax
- **Links**: Hyperlinks preserved
- **Bold/Italic**: Text formatting preserved
- **Code blocks**: Detected and formatted

### Example Output Structure

**From Excel:**
```markdown
## Sheet1

| Column A | Column B | Column C |
|----------|----------|----------|
| Value 1  | Value 2  | Value 3  |
| Value 4  | Value 5  | Value 6  |

## Sheet2

| Name | Amount |
|------|--------|
| Item | 100    |
```

**From Word:**
```markdown
# Document Title

## Section 1

This is paragraph text with **bold** and *italic* formatting.

- Bullet point 1
- Bullet point 2

### Subsection 1.1

More content here...
```

### Result Object Properties

```python
result = md.convert("file.pdf")

# Primary content access
result.text_content  # The markdown string

# Alternative (same content)
result.markdown  # Alias for text_content
```

---

## 7. PDF Handling Details

### Default Behavior
- Uses **pdfminer** library for text extraction
- Extracts text content and basic structure
- **No built-in OCR** - image-based PDFs require preprocessing

### Performance Concerns
Based on GitHub issue #1276, pdfminer has notable performance limitations:

| Document | MarkItDown (pdfminer) | PyMuPDF4LLM |
|----------|----------------------|-------------|
| 122-page, 1.6MB PDF | 33 seconds | 9.24 seconds |

**Key Issue**: pdfminer is completely synchronous, causing performance to degrade significantly with larger files.

### Limitations
1. **No OCR**: Scanned PDFs or image-based PDFs return empty or minimal content
2. **Formatting Loss**: Headings and styled text are not distinguished from regular text
3. **Complex Layouts**: Tables and multi-column layouts may not be preserved accurately
4. **Performance**: Slower than alternatives like PyMuPDF for large documents

### Enhanced PDF Processing (Azure)
For better PDF handling, use Azure Document Intelligence:
```python
md = MarkItDown(docintel_endpoint="<endpoint>")
result = md.convert("document.pdf")
```

This provides:
- Layout-aware conversion
- Better table detection
- Header/footer recognition
- Improved structure preservation

---

## 8. Limitations and Gotchas

### General Limitations

| Limitation | Details |
|------------|---------|
| Python Version | Requires Python 3.10+ |
| PDF OCR | No built-in OCR; image-based PDFs need preprocessing |
| PDF Performance | pdfminer is slow for large files |
| Complex Tables | Merged cells, nested structures may be lost |
| Image Descriptions | Requires LLM integration (not standalone) |
| Audio Transcription | Uses Google's API (requires internet) |

### Breaking Changes (v0.0.x to v0.1.x)

1. **`convert_stream()` requires binary objects**: Must use `io.BytesIO` or `open("file", "rb")`, not `io.StringIO`
2. **DocumentConverter interface changed**: Custom converters need updates
3. **Optional dependencies modularized**: Must install specific extras for each format

### Known Issues

1. **Table Formatting**: DOCX-to-Markdown loses critical formatting for:
   - Merged cells (rowspan/colspan)
   - Nested table structures
   - Multi-level headers
   - Cell alignment and borders

2. **Plugins Disabled by Default**: Must explicitly enable with `enable_plugins=True`

3. **LLM Image Descriptions**: Only works for PPTX and image files, not embedded images in PDFs/Word

### Error Handling Considerations

```python
from markitdown import MarkItDown

md = MarkItDown()

try:
    result = md.convert("document.pdf")
    if not result.text_content.strip():
        print("Warning: Empty output - file may be image-based")
except Exception as e:
    print(f"Conversion failed: {e}")
```

---

## 9. Alternatives Comparison

| Library | PDF Quality | Speed | OCR | License |
|---------|-------------|-------|-----|---------|
| MarkItDown | Basic | Slow | No | MIT |
| PyMuPDF4LLM | Excellent | Fast | Yes | AGPL-3.0 |
| pdfplumber | Good | Medium | No | MIT |
| textract | Good | Medium | Optional | MIT |

**Note**: PyMuPDF uses AGPL-3.0 license which has copyleft implications.

---

## 10. Integration Proposal for Recursive Data Cleaner

### Use Case

Allow users to input various document formats (PDF, Word, Excel, etc.) that get converted to text/structured data before the LLM-based cleaning process begins.

### Proposed Architecture

```
User Input                    Preprocessing                   Existing Pipeline
    |                              |                               |
    v                              v                               v
[PDF/DOCX/XLSX]  -->  [MarkItDown Converter]  -->  [Text/Markdown]  -->  [DataCleaner]
```

### Integration Options

#### Option A: Preprocessing Function (Minimal)

Add a simple preprocessing step before the cleaner runs:

```python
# New file: recursive_cleaner/preprocessing.py

from pathlib import Path
from typing import Optional

def preprocess_file(file_path: str, output_format: str = "text") -> str:
    """
    Convert document files to text/markdown for cleaning.

    Supported: PDF, DOCX, XLSX, PPTX, HTML, CSV, JSON
    Returns: Text content suitable for DataCleaner
    """
    try:
        from markitdown import MarkItDown
    except ImportError:
        raise ImportError(
            "markitdown is required for document preprocessing. "
            "Install with: pip install 'markitdown[all]'"
        )

    path = Path(file_path)
    supported = {'.pdf', '.docx', '.xlsx', '.pptx', '.html', '.csv', '.json', '.xml'}

    if path.suffix.lower() not in supported:
        # Return None to signal file should be processed as-is
        return None

    md = MarkItDown()
    result = md.convert(str(path))
    return result.text_content
```

#### Option B: Extended DataCleaner (Integrated)

Add document support directly to DataCleaner:

```python
class DataCleaner:
    def __init__(
        self,
        llm_backend,
        file_path,
        chunk_size=50,
        instructions="",
        max_iterations=5,
        context_budget=8000,
        preprocess_documents=True,  # NEW
    ):
        self.preprocess_documents = preprocess_documents
        # ... existing init ...

    def _load_file(self) -> str:
        """Load file, preprocessing documents if needed."""
        if self.preprocess_documents and self._is_document():
            return self._convert_document()
        return self._load_raw()

    def _is_document(self) -> bool:
        ext = Path(self.file_path).suffix.lower()
        return ext in {'.pdf', '.docx', '.xlsx', '.pptx'}

    def _convert_document(self) -> str:
        from markitdown import MarkItDown
        md = MarkItDown()
        result = md.convert(self.file_path)
        return result.text_content
```

### Recommended Approach

**Option A (Preprocessing Function)** is recommended because:

1. **Separation of Concerns**: Document conversion is a distinct step from data cleaning
2. **User Control**: Users can inspect/modify the converted text before cleaning
3. **Flexibility**: Can be used standalone or with other tools
4. **Minimal Changes**: Doesn't modify the core DataCleaner class

### Proposed User Experience

```python
from recursive_cleaner import DataCleaner, preprocess_file

# For document files
text = preprocess_file("report.pdf")
if text:
    # Save intermediate result for inspection
    Path("report_converted.txt").write_text(text)

# Then clean as usual
cleaner = DataCleaner(
    llm_backend=my_backend,
    file_path="report_converted.txt",  # Use converted file
    instructions="Extract and clean tabular data..."
)
cleaner.run()
```

### Dependency Considerations

```toml
# pyproject.toml
[project.optional-dependencies]
documents = [
    "markitdown[pdf,docx,xlsx,pptx]>=0.1.4",
]
all = [
    "markitdown[all]>=0.1.4",
]
```

### Limitations to Document

1. **PDF Quality**: Image-based PDFs will produce empty output without OCR preprocessing
2. **Large PDFs**: Performance may be slow; consider chunking or using Azure Doc Intelligence
3. **Table Preservation**: Complex table structures may be simplified
4. **No OCR Built-in**: Recommend documenting OCR alternatives for scanned documents

---

## 11. Sources

- [GitHub - microsoft/markitdown](https://github.com/microsoft/markitdown)
- [markitdown on PyPI](https://pypi.org/project/markitdown/)
- [PDF performance (PDFMiner) - Issue #1276](https://github.com/microsoft/markitdown/issues/1276)
- [Deep Dive into Microsoft MarkItDown - DEV Community](https://dev.to/leapcell/deep-dive-into-microsoft-markitdown-4if5)
- [MarkItDown: Microsoft's open-source tool - InfoWorld](https://www.infoworld.com/article/3963991/markitdown-microsofts-open-source-tool-for-markdown-conversion.html)
- [Stream Handling - DeepWiki](https://deepwiki.com/microsoft/markitdown/2.2-stream-handling)
