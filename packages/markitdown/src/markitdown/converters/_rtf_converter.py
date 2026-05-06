# SPDX-FileCopyrightText: 2024-present Adam Fourney <adamfo@microsoft.com>
#
# SPDX-License-Identifier: MIT

import sys
from typing import BinaryIO, Any

from .._base_converter import DocumentConverter, DocumentConverterResult
from .._stream_info import StreamInfo
from .._exceptions import MissingDependencyException, MISSING_DEPENDENCY_MESSAGE

# Load dependencies
_dependency_exc_info = None
try:
    from striprtf.striprtf import rtf_to_text
except ImportError:
    _dependency_exc_info = sys.exc_info()

ACCEPTED_MIME_TYPE_PREFIXES = [
    "text/rtf",
    "application/rtf",
    "application/x-rtf",
]

ACCEPTED_FILE_EXTENSIONS = [".rtf"]


class RtfConverter(DocumentConverter):
    """
    Converts RTF (Rich Text Format) files to Markdown plain text.
    Requires the ``striprtf`` package.
    """

    def accepts(
        self,
        file_stream: BinaryIO,
        stream_info: StreamInfo,
        **kwargs: Any,
    ) -> bool:
        mimetype = (stream_info.mimetype or "").lower()
        extension = (stream_info.extension or "").lower()

        if extension in ACCEPTED_FILE_EXTENSIONS:
            return True

        for prefix in ACCEPTED_MIME_TYPE_PREFIXES:
            if mimetype.startswith(prefix):
                return True

        return False

    def convert(
        self,
        file_stream: BinaryIO,
        stream_info: StreamInfo,
        **kwargs: Any,
    ) -> DocumentConverterResult:
        if _dependency_exc_info is not None:
            raise MissingDependencyException(
                MISSING_DEPENDENCY_MESSAGE.format(
                    converter=type(self).__name__,
                    extension=".rtf",
                    feature="rtf",
                )
            ) from _dependency_exc_info[1].with_traceback(
                _dependency_exc_info[2]
            )  # type: ignore[union-attr]

        # RTF files are text-based; decode with latin-1 which is the standard RTF encoding
        raw = file_stream.read()
        try:
            rtf_string = raw.decode("latin-1")
        except UnicodeDecodeError:
            rtf_string = raw.decode("utf-8", errors="replace")

        text = rtf_to_text(rtf_string, errors="ignore")

        # Normalise line endings and strip excessive blank lines
        lines = text.splitlines()
        cleaned: list[str] = []
        blank_run = 0
        for line in lines:
            stripped = line.rstrip()
            if stripped:
                blank_run = 0
                cleaned.append(stripped)
            else:
                blank_run += 1
                if blank_run <= 2:
                    cleaned.append("")

        markdown = "\n".join(cleaned).strip()
        return DocumentConverterResult(markdown=markdown)
