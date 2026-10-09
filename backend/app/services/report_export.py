import re
import zipfile
from io import BytesIO
from xml.sax.saxutils import escape


def to_markdown(payload: dict) -> str:
    refs = "\n".join(
        f"- [{s['id']}] {s.get('title','')} {s.get('url','')}".strip()
        for s in payload.get("sources", [])
    ) or "No sources were available."
    return f"# {payload.get('topic','Research report')}\n\n**Report type:** {payload.get('report_type','')}\n\n{payload.get('report','')}\n\n## References\n\n{refs}\n"


def to_docx(payload: dict) -> bytes:
    stream = BytesIO()
    paragraphs = [payload.get("topic", "Research report"), f"Report type: {payload.get('report_type','')}", ""]
    paragraphs.extend(payload.get("report", "").splitlines())
    paragraphs.extend(["", "References"])
    paragraphs.extend(f"[{s.get('id','')}] {s.get('title','')} {s.get('url','')}" for s in payload.get("sources", []))
    body = "".join(f"<w:p><w:r><w:t xml:space=\"preserve\">{escape(line)}</w:t></w:r></w:p>" for line in paragraphs)
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>""")
        archive.writestr("_rels/.rels", """<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>""")
        archive.writestr("word/document.xml", f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>{body}<w:sectPr/></w:body></w:document>""")
    return stream.getvalue()


def to_pdf(payload: dict) -> bytes:
    text = [payload.get("topic", "Research report"), f"Report type: {payload.get('report_type','')}", ""]
    text.extend(payload.get("report", "").splitlines())
    text.extend(["", "References"])
    text.extend(f"[{s.get('id','')}] {s.get('title','')} {s.get('url','')}" for s in payload.get("sources", []))
    lines = []
    for paragraph in text:
        paragraph = re.sub(r"[^\x20-\x7E]", "?", paragraph)
        while len(paragraph) > 92:
            lines.append(paragraph[:92]); paragraph = paragraph[92:]
        lines.append(paragraph)
    pages = [lines[i:i + 48] for i in range(0, len(lines), 48)] or [[]]
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>"]
    page_refs = []
    for i, page_lines in enumerate(pages):
        page_obj_id = 3 + i * 2
        content_obj_id = page_obj_id + 1
        page_refs.append(f"{page_obj_id} 0 R")
        commands = ["BT", "/F1 10 Tf", "50 790 Td", "13 TL"]
        for line in page_lines:
            safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            commands.append(f"({safe}) Tj T*")
        commands.append("ET")
        content = "\n".join(commands).encode("ascii", "replace")
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] /Resources << /Font << /F1 {3 + len(pages) * 2} 0 R >> >> /Contents {content_obj_id} 0 R >>".encode())
        objects.append(b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream")
    objects.insert(1, f"<< /Type /Pages /Kids [{' '.join(page_refs)}] /Count {len(pages)} >>".encode())
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(output)); output.extend(f"{i} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]: output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    return bytes(output)
