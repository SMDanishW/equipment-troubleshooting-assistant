from pathlib import Path

import pdfplumber


def extract_pdf_pages(pdf_path: Path) -> tuple[int, list[tuple[int, str]]]:
    pages: list[tuple[int, str]] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for index, page in enumerate(pdf.pages, start=1):
            text = page.extract_text(x_tolerance=2, y_tolerance=3) or page.extract_text() or ""
            pages.append((index, text))
        return len(pdf.pages), pages
