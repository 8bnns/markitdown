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
    from odf.opendocument import load as odf_load
    from odf import text as odf_text
    from odf import table as odf_table
    from odf.element import Element
except ImportError:
    _dependency_exc_info = sys.exc_info()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _get_text(element: "Element") -> str:
    """Recursively extract plain text from an ODF element."""
    parts: list[str] = []
    for child in element.childNodes:
        if hasattr(child, "data"):
            parts.append(child.data)
        else:
            parts.append(_get_text(child))
    return "".join(parts)


def _table_to_markdown(table_element: "Element") -> str:
    """Convert an ODF table element to a Markdown table string."""
    rows: list[list[str]] = []
    for row in table_element.getElementsByType(odf_table.TableRow):
        cells: list[str] = []
        for cell in row.getElementsByType(odf_table.TableCell):
            # Handle repeated cells (table:number-columns-repeated)
            repeat = int(cell.getAttribute("numbercolumnsrepeated") or 1)
            cell_text = _get_text(cell).strip()
            for _ in range(repeat):
                cells.append(cell_text)
        # Strip trailing empty cells (padding artefacts)
        while cells and not cells[-1]:
            cells.pop()
        if cells:
            rows.append(cells)

    if not rows:
        return ""

    # Normalise column count
    num_cols = max(len(r) for r in rows)
    for r in rows:
        while len(r) < num_cols:
            r.append("")

    col_widths = [max(len(r[i]) for r in rows) for i in range(num_cols)]
    col_widths = [max(w, 3) for w in col_widths]

    def fmt_row(row: list[str]) -> str:
        return "| " + " | ".join(cell.ljust(col_widths[i]) for i, cell in enumerate(row)) + " |"

    lines = [fmt_row(rows[0])]
    lines.append("| " + " | ".join("-" * col_widths[i] for i in range(num_cols)) + " |")
    for row in rows[1:]:
        lines.append(fmt_row(row))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# ODT – Writer documents
# ---------------------------------------------------------------------------

ACCEPTED_MIME_TYPES_ODT = [
    "application/vnd.oasis.opendocument.text",
    "application/vnd.oasis.opendocument.text-template",
]
ACCEPTED_EXTENSIONS_ODT = [".odt", ".ott"]


class OdtConverter(DocumentConverter):
    """
    Converts OpenDocument Text files (.odt) to Markdown.
    Requires the ``odfpy`` package.
    """

    def accepts(
        self,
        file_stream: BinaryIO,
        stream_info: StreamInfo,
        **kwargs: Any,
    ) -> bool:
        mimetype = (stream_info.mimetype or "").lower()
        extension = (stream_info.extension or "").lower()
        return extension in ACCEPTED_EXTENSIONS_ODT or mimetype in ACCEPTED_MIME_TYPES_ODT

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
                    extension=".odt",
                    feature="odf",
                )
            ) from _dependency_exc_info[1].with_traceback(
                _dependency_exc_info[2]
            )  # type: ignore[union-attr]

        doc = odf_load(file_stream)
        chunks: list[str] = []

        for element in doc.text.childNodes:
            tag = element.qname[1] if hasattr(element, "qname") else ""

            if tag == "h":
                level = int(element.getAttribute("outlinelevel") or 1)
                heading_text = _get_text(element).strip()
                if heading_text:
                    chunks.append("#" * level + " " + heading_text)

            elif tag == "p":
                para_text = _get_text(element).strip()
                if para_text:
                    chunks.append(para_text)

            elif tag == "table":
                md_table = _table_to_markdown(element)
                if md_table:
                    chunks.append(md_table)

            elif tag == "list":
                for item in element.getElementsByType(odf_text.ListItem):
                    item_text = _get_text(item).strip()
                    if item_text:
                        chunks.append("- " + item_text)

        markdown = "\n\n".join(chunks).strip()
        return DocumentConverterResult(markdown=markdown)


# ---------------------------------------------------------------------------
# ODS – Calc spreadsheets
# ---------------------------------------------------------------------------

ACCEPTED_MIME_TYPES_ODS = [
    "application/vnd.oasis.opendocument.spreadsheet",
    "application/vnd.oasis.opendocument.spreadsheet-template",
]
ACCEPTED_EXTENSIONS_ODS = [".ods", ".ots"]


class OdsConverter(DocumentConverter):
    """
    Converts OpenDocument Spreadsheet files (.ods) to Markdown tables.
    Requires the ``odfpy`` package.
    """

    def accepts(
        self,
        file_stream: BinaryIO,
        stream_info: StreamInfo,
        **kwargs: Any,
    ) -> bool:
        mimetype = (stream_info.mimetype or "").lower()
        extension = (stream_info.extension or "").lower()
        return extension in ACCEPTED_EXTENSIONS_ODS or mimetype in ACCEPTED_MIME_TYPES_ODS

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
                    extension=".ods",
                    feature="odf",
                )
            ) from _dependency_exc_info[1].with_traceback(
                _dependency_exc_info[2]
            )  # type: ignore[union-attr]

        doc = odf_load(file_stream)
        chunks: list[str] = []

        for sheet in doc.spreadsheet.getElementsByType(odf_table.Table):
            sheet_name = sheet.getAttribute("name") or "Sheet"
            chunks.append(f"## {sheet_name}")
            md_table = _table_to_markdown(sheet)
            if md_table:
                chunks.append(md_table)

        markdown = "\n\n".join(chunks).strip()
        return DocumentConverterResult(markdown=markdown)


# ---------------------------------------------------------------------------
# ODP – Impress presentations
# ---------------------------------------------------------------------------

ACCEPTED_MIME_TYPES_ODP = [
    "application/vnd.oasis.opendocument.presentation",
    "application/vnd.oasis.opendocument.presentation-template",
]
ACCEPTED_EXTENSIONS_ODP = [".odp", ".otp"]


class OdpConverter(DocumentConverter):
    """
    Converts OpenDocument Presentation files (.odp) to Markdown.
    Requires the ``odfpy`` package.
    """

    def accepts(
        self,
        file_stream: BinaryIO,
        stream_info: StreamInfo,
        **kwargs: Any,
    ) -> bool:
        mimetype = (stream_info.mimetype or "").lower()
        extension = (stream_info.extension or "").lower()
        return extension in ACCEPTED_EXTENSIONS_ODP or mimetype in ACCEPTED_MIME_TYPES_ODP

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
                    extension=".odp",
                    feature="odf",
                )
            ) from _dependency_exc_info[1].with_traceback(
                _dependency_exc_info[2]
            )  # type: ignore[union-attr]

        from odf.draw import Page as DrawPage  # local import avoids top-level odf coupling

        doc = odf_load(file_stream)
        chunks: list[str] = []

        for slide_idx, page in enumerate(doc.presentation.getElementsByType(DrawPage), start=1):
            slide_name = page.getAttribute("name") or f"Slide {slide_idx}"
            slide_chunks: list[str] = [f"## {slide_name}"]

            for frame in page.childNodes:
                frame_tag = frame.qname[1] if hasattr(frame, "qname") else ""
                if frame_tag == "frame":
                    for child in frame.childNodes:
                        child_tag = child.qname[1] if hasattr(child, "qname") else ""
                        if child_tag == "text-box":
                            for para in child.getElementsByType(odf_text.P):
                                para_text = _get_text(para).strip()
                                if para_text:
                                    slide_chunks.append(para_text)

            if len(slide_chunks) > 1:
                chunks.append("\n\n".join(slide_chunks))

        markdown = "\n\n---\n\n".join(chunks).strip()
        return DocumentConverterResult(markdown=markdown)
