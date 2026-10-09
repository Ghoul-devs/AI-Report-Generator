from pypdf import PdfReader


def load_pdf_pages(file_path: str) -> list[dict]:
    reader = PdfReader(file_path)
    pages = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            pages.append({"page": page_number, "text": text})
    return pages


def load_pdf(file_path: str) -> str:
    return "\n".join(page["text"] for page in load_pdf_pages(file_path))
