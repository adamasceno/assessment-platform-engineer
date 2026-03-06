"""
test_async_writer.py
====================
Unit tests for write_async_iterable_to_csvs (async_writer.py).

Run with:
    python -m pytest test_async_writer.py -v
    # or
    python -m unittest test_async_writer
"""

import csv
import os
import unittest
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from async_writer import write_async_iterable_to_csvs


class TestWriteAsyncIterableToCsvs(unittest.IsolatedAsyncioTestCase):
    """Unit tests for write_async_iterable_to_csvs."""

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _tmp(self, subdir: str) -> str:
        """Return an isolated temp directory path, creating it if needed."""
        path = os.path.join("/tmp", "async_writer_tests", subdir)
        os.makedirs(path, exist_ok=True)
        return path

    @staticmethod
    def _count_rows(paths: list, encoding: str = "utf-8") -> int:
        """Return the total number of CSV rows across all *paths*."""
        total = 0
        for p in paths:
            with open(p, newline="", encoding=encoding) as f:
                total += sum(1 for _ in csv.reader(f))
        return total

    @staticmethod
    async def _rows(n: int):
        """Async generator that yields *n* simple 3-tuples."""
        for i in range(n):
            yield (i, f"name_{i}", "data")

    @staticmethod
    async def _empty():
        """Async generator that yields nothing."""
        return
        yield  # pragma: no cover – makes this a generator function

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    async def test_empty_iterable_creates_one_file(self):
        """An empty source must produce exactly one (empty) output file."""
        out = self._tmp("empty")
        paths = await write_async_iterable_to_csvs(
            rows=self._empty(), output_dir=out, files_multiple=1
        )
        self.assertEqual(len(paths), 1)
        self.assertEqual(os.path.getsize(paths[0]), 0)

    async def test_files_multiple_is_respected(self):
        """Total file count must always be a multiple of *files_multiple*."""
        out = self._tmp("multiple")
        for multiple in (1, 2, 3, 4, 5, 7, 8):
            paths = await write_async_iterable_to_csvs(
                rows=self._rows(1000),
                output_dir=out,
                file_prefix=f"m{multiple}",
                min_bytes_per_file=1024,
                max_bytes_per_file=4096,
                files_multiple=multiple,
            )
            self.assertEqual(
                len(paths) % multiple,
                0,
                f"Expected a multiple of {multiple}, got {len(paths)} files",
            )

    async def test_no_file_exceeds_max_bytes(self):
        """
        Non-empty files must not exceed *max_bytes_per_file* bytes.
        (Empty padding files are excluded from this check.)
        """
        out = self._tmp("maxbytes")
        max_b = 4096
        paths = await write_async_iterable_to_csvs(
            rows=self._rows(5000),
            output_dir=out,
            min_bytes_per_file=1024,
            max_bytes_per_file=max_b,
            files_multiple=1,
        )
        data_files = [p for p in paths if os.path.getsize(p) > 0]
        for p in data_files:
            size = os.path.getsize(p)
            self.assertLessEqual(
                size, max_b,
                f"{p} is {size} bytes — exceeds max {max_b}",
            )

    async def test_invalid_encoding_raises(self):
        """An unsupported encoding must raise ValueError before any I/O."""
        out = self._tmp("bad_enc")
        with self.assertRaises(ValueError):
            await write_async_iterable_to_csvs(
                rows=self._rows(10), output_dir=out, encoding="latin-1"
            )

    async def test_invalid_dialect_raises(self):
        """An unsupported CSV dialect must raise ValueError before any I/O."""
        out = self._tmp("bad_dia")
        with self.assertRaises(ValueError):
            await write_async_iterable_to_csvs(
                rows=self._rows(10), output_dir=out, dialect="pipes"
            )

    async def test_files_multiple_zero_raises(self):
        """*files_multiple=0* is invalid and must raise ValueError."""
        out = self._tmp("bad_mult")
        with self.assertRaises(ValueError):
            await write_async_iterable_to_csvs(
                rows=self._rows(10), output_dir=out, files_multiple=0
            )

    async def test_min_greater_than_max_raises(self):
        """*min_bytes_per_file* > *max_bytes_per_file* must raise ValueError."""
        out = self._tmp("bad_range")
        with self.assertRaises(ValueError):
            await write_async_iterable_to_csvs(
                rows=self._rows(10),
                output_dir=out,
                min_bytes_per_file=1024,
                max_bytes_per_file=512,
            )

    async def test_exception_cleans_up_files(self):
        """
        If the source iterable raises mid-stream, all partially-written output
        files must be removed — the caller must not receive a mix of complete
        and truncated data.
        """
        out = self._tmp("cleanup")

        async def bad_rows():
            for i in range(50):
                yield (i, "x")
            raise RuntimeError("simulated upstream failure")

        before = set(os.listdir(out))
        with self.assertRaises(RuntimeError):
            await write_async_iterable_to_csvs(
                rows=bad_rows(),
                output_dir=out,
                min_bytes_per_file=128,
                max_bytes_per_file=512,
            )
        new_files = set(os.listdir(out)) - before
        self.assertEqual(len(new_files), 0, f"Leftover files found: {new_files}")

    async def test_single_oversized_row_still_written(self):
        """
        A row larger than *max_bytes_per_file* must still be written — it
        occupies its own file that exceeds the soft upper bound.
        """
        out = self._tmp("oversized")

        async def one_big_row():
            yield (1, "x" * 10_000)   # ~10 KiB

        paths = await write_async_iterable_to_csvs(
            rows=one_big_row(),
            output_dir=out,
            min_bytes_per_file=1,
            max_bytes_per_file=512,
        )
        self.assertEqual(self._count_rows(paths), 1)

    async def test_utf8_sig_encoding(self):
        """
        Files written with ``encoding="utf-8-sig"`` must open with the UTF-8
        BOM (EF BB BF) and contain the correct total number of rows.
        """
        out = self._tmp("bom")
        paths = await write_async_iterable_to_csvs(
            rows=self._rows(100),
            output_dir=out,
            min_bytes_per_file=512,
            max_bytes_per_file=4096,
            encoding="utf-8-sig",
        )
        BOM = b"\xef\xbb\xbf"
        for p in paths:
            if os.path.getsize(p) == 0:
                continue
            with open(p, "rb") as f:
                self.assertEqual(f.read(3), BOM, f"{p} is missing UTF-8 BOM")

        self.assertEqual(self._count_rows(paths, encoding="utf-8-sig"), 100)

    async def test_output_dir_created_if_missing(self):
        """*output_dir* must be created automatically when it does not exist."""
        out = os.path.join(self._tmp("autocreate"), "nested", "subdir")
        paths = await write_async_iterable_to_csvs(
            rows=self._rows(5), output_dir=out
        )
        self.assertTrue(os.path.isdir(out))
        self.assertGreater(len(paths), 0)

    async def test_large_stream_files_multiple(self):
        """
        Stress test: 500 000 rows, *files_multiple=4*.
        The file count must be a multiple of 4 and every row must be present.
        """
        out = self._tmp("large")
        n = 500_000

        async def many_rows():
            for i in range(n):
                yield (i, f"User_{i}", "Some text to fill bytes")

        paths = await write_async_iterable_to_csvs(
            rows=many_rows(),
            output_dir=out,
            file_prefix="large_test",
            min_bytes_per_file=256 * 1024,
            max_bytes_per_file=512 * 1024,
            files_multiple=4,
        )
        self.assertEqual(len(paths) % 4, 0, "File count is not a multiple of 4")
        self.assertEqual(self._count_rows(paths), n)


if __name__ == "__main__":
    unittest.main()