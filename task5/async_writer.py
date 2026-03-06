import asyncio
import csv
import io
import os
from collections.abc import AsyncIterable
from typing import Tuple


async def write_async_iterable_to_csvs(
    rows: AsyncIterable[Tuple],
    output_dir: str,
    file_prefix: str = "part",
    min_bytes_per_file: int = 512 * 1024,      # 512 KiB
    max_bytes_per_file: int = 1 * 1024 * 1024, # 1 MiB (hard upper bound per file)
    files_multiple: int = 1,   
    encoding: str = "utf-8",
    dialect: str = "excel",
) -> list[str]:
    """
    Writes an AsyncIterable to a set of CSV files.
    
    Args:
        rows: The source of data (tuples).
        output_dir: Directory in which output files are created.   
        file_prefix: Path/prefix for the filenames.
        max_bytes_per_file: Strict upper bound for file size.
        files_multiple: The total number of output files will be padded
                            with empty files until it is a multiple of this
                            value. Must be >= 1.
        encoding: File encoding, utf-8 or utf-8-sig.
            valid_values: ["utf-8", "utf-8-sig"]
        dialect: csv dialect for csv.writer.
            valid_values: ["excel", "excel-tab", "unix", "unixpwd"]
        
    Returns:
        A list of paths to the created files.
    """
        
    def _calc_row_bytes(row: Tuple) -> bytes:
        """
        Calculate row in bytes.
        
        Args:
            row: Tuple
            
        Returns:
            Value of the row in bytes
        """
        _size_buffer.seek(0)
        _size_buffer.truncate(0)
        _size_writer.writerow(row)
        return _size_buffer.getvalue().encode(encoding)

    def _write_file(index: int = 0):
        """
        Writes a CSV file.
        
        Args:
            Index: int = 0
            
        Returns:
            Tuple with created file data
            [handler, path, writer, size]

        """
        # 4 characters wide to ensure files sort correctly alphabetically.
        path = os.path.join(output_dir, f"{file_prefix}_{index:04d}.csv")
        handler = open(path, "w", encoding=encoding, newline="")
        writer = csv.writer(handler, dialect=dialect)
        size = 0
        
        return handler, path, writer, size
   
    # ------------------------------------------------------------------
    # Parameter validation
    # ------------------------------------------------------------------
    _VALID_ENCODINGS = ("utf-8", "utf-8-sig")
    _VALID_DIALECTS  = ("excel", "excel-tab", "unix", "unixpwd")

    if encoding not in _VALID_ENCODINGS:
        raise ValueError(
            f"Invalid encoding {encoding!r}. Must be one of {_VALID_ENCODINGS}."
        )
    if dialect not in _VALID_DIALECTS:
        raise ValueError(
            f"Invalid dialect {dialect!r}. Must be one of {_VALID_DIALECTS}."
        )
    if files_multiple < 1:
        raise ValueError(
            f"Invalid value: parameter files_multiple must be >= 1, got {files_multiple}."
        )
    if min_bytes_per_file < 0:
        raise ValueError(
            f"min_bytes_per_file must be >= 0, got {min_bytes_per_file}."
        )
    if max_bytes_per_file < 1:
        raise ValueError(
            f"max_bytes_per_file must be >= 1, got {max_bytes_per_file}."
        )
    if min_bytes_per_file > max_bytes_per_file:
        raise ValueError(
            f"min_bytes_per_file ({min_bytes_per_file}) must be <= "
            f"max_bytes_per_file ({max_bytes_per_file})."
        )    

    _size_buffer = io.StringIO()
    _size_writer = csv.writer(_size_buffer, dialect=dialect)
    
    # Create the output folder
    os.makedirs(output_dir, exist_ok=True)    
    
    # Prepare the list with the path of the created files  
    files_path: list[str] = []
    current_index = 0
    # Create the first file and setting current file variables with the file returned data
    # index, handler, path, writer, size
    current_file_handler, current_path, current_writer, current_size = _write_file(current_index)
    
    files_path.append(current_path)    

    try:
        async for row in rows:
            row_data = _calc_row_bytes(row)
            row_len = len(row_data)

            # We need to have be sure that will be at least one row already written, to avoid infinity loops
            if current_size >= min_bytes_per_file and current_size + row_len > max_bytes_per_file:
                # After we make sure that some content was written, kill the handler
                current_file_handler.close()
                current_index += 1
                # Create other files, passing the current index as parameter
                current_file_handler, current_path, current_writer, current_size = _write_file(current_index)
                files_path.append(current_path)            
            # If we still dont have enought to fill it a file, continue writting in the same one
            current_writer.writerow(row)
            current_size += row_len
    except BaseException:
        # Close the open file handle (suppress secondary errors) then delete
        # every file that was created so the caller sees a clean state.
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
    
    # Close the handler of the last created file
    current_file_handler.close()

    # ------------------------------------------------------------------
    # Padding -- ensure file count is a multiple of `files_multiple`
    #
    # Empty padding files are created so the count rounds up to the next
    # multiple. If the count is already a multiple, nothing is added.
    # ------------------------------------------------------------------
    if files_multiple > 1:
        while len(files_path) % files_multiple != 0:
            current_index += 1
            pad_handler, pad_path, _, _ = _write_file(current_index)
            pad_handler.close()
            files_path.append(pad_path)


    return files_path


# ---------------------------------------------------------------------------
# Smoke-test / demo
# ---------------------------------------------------------------------------
async def _demo() -> None:
    """
    Streams 500 000 rows into CSV files with:
      - 256 KiB lower bound
      - 512 KiB upper bound
      - file count rounded up to the nearest multiple of 4
    """
    print("Starting CSV demo...")

    async def fake_rows():
        for i in range(500_000):
            yield (i, f"User_{i}", "Some text to fill bytes")

    paths = await write_async_iterable_to_csvs(
        rows=fake_rows(),
        output_dir="tmp",
        file_prefix="demo_output",
        min_bytes_per_file=256 * 1024,   # 256 KiB
        max_bytes_per_file=512 * 1024,   # 512 KiB
        files_multiple=4
    )

    print(f"Wrote {len(paths)} files (multiple of 4: {len(paths) % 4 == 0})")
    for p in paths:
        size = os.path.getsize(p)
        print(f"  {p}: {size:,} bytes")


if __name__ == "__main__":
    asyncio.run(_demo())