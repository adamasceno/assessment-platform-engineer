# async_writer

A single-pass, memory-efficient utility for streaming an `AsyncIterable` of tuples into a set of CSV files.

---

## Requirements

- Python 3.10+
- No third-party dependencies (standard library only)

---

## Installation

Copy `async_writer.py` into your project. No package installation is required.

---

## Function signature

```python
async def write_async_iterable_to_csvs(
    rows: AsyncIterable[Tuple],
    output_dir: str,
    file_prefix: str = "part",
    min_bytes_per_file: int = 512 * 1024,       # 512 KiB
    max_bytes_per_file: int = 1 * 1024 * 1024,  # 1 MiB
    files_multiple: int = 1,
    encoding: str = "utf-8",
    dialect: str = "excel",
) -> list[str]:
```

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `rows` | `AsyncIterable[Tuple]` | — | Source of data. Consumed exactly once, never materialised in memory. |
| `output_dir` | `str` | — | Directory for output files. Created automatically if it does not exist. |
| `file_prefix` | `str` | `"part"` | Filename prefix. Files are named `{prefix}_{index:04d}.csv`. |
| `min_bytes_per_file` | `int` | `524288` | A new file is not started until the current file has reached at least this many bytes. |
| `max_bytes_per_file` | `int` | `1048576` | Soft upper bound on file size. A new file is opened before writing a row that would push the current file over this limit — unless no rows have been written yet (see oversized-row behaviour below). |
| `files_multiple` | `int` | `1` | Total number of output files will be a multiple of this value. Empty padding files are appended as needed. Must be ≥ 1. |
| `encoding` | `str` | `"utf-8"` | File encoding. Allowed: `"utf-8"`, `"utf-8-sig"`. |
| `dialect` | `str` | `"excel"` | CSV dialect passed to `csv.writer`. Allowed: `"excel"`, `"excel-tab"`, `"unix"`, `"unixpwd"`. |

### Returns

A `list[str]` of absolute paths to every file created, in order. Padding files (if any) are included and will be empty (0 bytes).

---

## Design

### Single pass
The `AsyncIterable` is consumed exactly once with `async for`. No rows are buffered or re-read. This means the function works correctly even when the source is an infinite or very large stream.

### File-size bounds
File splitting follows a **min/max window** strategy:

1. While the current file is smaller than `min_bytes_per_file`, rows continue to be appended to it regardless of `max_bytes_per_file`.
2. Once the file has reached `min_bytes_per_file`, each incoming row is checked. If writing it would exceed `max_bytes_per_file`, the current file is closed and a new one is opened first.
3. **Oversized rows** — a single row whose serialised byte length exceeds `max_bytes_per_file` is always written. It will be the only row in its file, and that file will exceed the soft upper bound. Refusing to write such a row would cause data loss.

### Padding to a file-count multiple
After all rows are written, empty files are appended until `len(output_files) % files_multiple == 0`. If the count is already a multiple, nothing is added.

### Exception safety / cleanup
If the source iterable raises at any point during streaming, **all files created during that call are deleted** before the exception propagates. The caller will never receive a mix of complete and truncated files.

The iteration loop is wrapped in `try/except BaseException` (covering `Exception`, `KeyboardInterrupt`, and `asyncio.CancelledError`). On any error, the open file handle is closed and every path in `files_path` is removed before re-raising.

```python
try:
    async for row in rows:
        ...
except BaseException:
    try:
        current_file_handler.close()
    except Exception:
        pass
    for p in files_path:
        try:
            os.remove(p)
        except OSError:
            pass
    raise
```

---

## Validation

The following are checked before any I/O takes place. A `ValueError` is raised immediately if any constraint is violated:

| Check | Rule |
|---|---|
| `encoding` | Must be `"utf-8"` or `"utf-8-sig"` |
| `dialect` | Must be `"excel"`, `"excel-tab"`, `"unix"`, or `"unixpwd"` |
| `files_multiple` | Must be ≥ 1 |
| `min_bytes_per_file` | Must be ≥ 0 |
| `max_bytes_per_file` | Must be ≥ 1 |
| `min_bytes_per_file` vs `max_bytes_per_file` | `min` must be ≤ `max` |

---

## Usage examples

### Basic usage

```python
import asyncio
from async_writer import write_async_iterable_to_csvs

async def main():
    async def source():
        for i in range(100_000):
            yield (i, f"user_{i}", "some data")

    paths = await write_async_iterable_to_csvs(
        rows=source(),
        output_dir="output/",
    )
    print(f"Created {len(paths)} file(s)")

asyncio.run(main())
```

### Constrained file sizes with a count multiple

```python
paths = await write_async_iterable_to_csvs(
    rows=source(),
    output_dir="output/",
    file_prefix="export",
    min_bytes_per_file=256 * 1024,   # 256 KiB lower bound
    max_bytes_per_file=512 * 1024,   # 512 KiB upper bound
    files_multiple=4,                # always produce 4, 8, 12, … files
)
```

### UTF-8 with BOM (for Excel compatibility)

```python
paths = await write_async_iterable_to_csvs(
    rows=source(),
    output_dir="output/",
    encoding="utf-8-sig",
)
```

### Tab-separated values

```python
paths = await write_async_iterable_to_csvs(
    rows=source(),
    output_dir="output/",
    dialect="excel-tab",
)
```

---

## Running the tests

```bash
# unittest (no third-party dependencies required)
python -m unittest test_async_writer -v

# pytest (if installed)
python -m pytest test_async_writer.py -v
```

### Test coverage

| Test | What it verifies |
|---|---|
| `test_empty_iterable_creates_one_file` | An empty source produces exactly one empty file |
| `test_files_multiple_is_respected` | File count is always a multiple of `files_multiple` |
| `test_no_file_exceeds_max_bytes` | Non-padding files do not exceed `max_bytes_per_file` |
| `test_invalid_encoding_raises` | Bad encoding raises `ValueError` before any I/O |
| `test_invalid_dialect_raises` | Bad dialect raises `ValueError` before any I/O |
| `test_files_multiple_zero_raises` | `files_multiple=0` raises `ValueError` |
| `test_min_greater_than_max_raises` | `min > max` raises `ValueError` |
| `test_exception_cleans_up_files` | Mid-stream exception leaves no orphaned files on disk |
| `test_single_oversized_row_still_written` | A row larger than `max_bytes_per_file` is still written |
| `test_utf8_sig_encoding` | Files start with UTF-8 BOM; all rows are present |
| `test_output_dir_created_if_missing` | Missing `output_dir` is created automatically |
| `test_large_stream_files_multiple` | 500 000 rows, `files_multiple=4`; count is a multiple of 4 and all rows are present |

All 12 tests pass against the fixed implementation.