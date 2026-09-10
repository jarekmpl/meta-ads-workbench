"""Local, non-executing document readers. No remote services or linked resources."""

import hashlib
import io
import re
import xml.etree.ElementTree as ET
import zipfile

from meta_ads_manager.errors import AppError

MAX_FILE = 50 * 1024 * 1024
MAX_TEXT = 2_000_000
MAX_XML = 10 * 1024 * 1024
CHUNK_SIZE = 2400
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def fail(code, message):
    raise AppError(code, message, 2)


def docx_units(payload):
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        if len(archive.infolist()) > 10000:
            fail("CONTEXT_LIMIT", "Dokument zawiera zbyt wiele elementów.")
        entry = archive.getinfo("word/document.xml")
        if entry.file_size > MAX_XML:
            fail("CONTEXT_LIMIT", "Treść DOCX przekracza limit 10 MB.")
        xml = archive.read(entry)
    if b"<!DOCTYPE" in xml.upper() or b"<!ENTITY" in xml.upper():
        fail("CONTEXT_FORMAT", "Nieobsługiwane deklaracje XML w DOCX.")
    document = ET.fromstring(xml)
    body = document.find(f"{W}body")
    if body is None:
        fail("CONTEXT_FORMAT", "Brak treści dokumentu DOCX.")
    # Deleted revisions are excluded; inserted text is included and flagged for review.
    revised = any(document.iter(f"{W}ins")) or any(document.iter(f"{W}del"))

    def visible(element):
        if element.tag in (f"{W}del", f"{W}moveFrom"):
            return ""
        if element.tag == f"{W}t":
            return element.text or ""
        if element.tag in (f"{W}tab", f"{W}br", f"{W}cr"):
            return " "
        return "".join(visible(child) for child in element)

    units = []
    paragraph, table = 0, 0
    for element in body:
        if element.tag == f"{W}p":
            paragraph += 1
            units.append((f"paragraph:{paragraph}", visible(element)))
        elif element.tag == f"{W}tbl":
            table += 1
            for row, tr in enumerate(element.findall(f"{W}tr"), 1):
                cells = [visible(tc) for tc in tr.findall(f"{W}tc")]
                units.append((f"table:{table}/row:{row}", " | ".join(cells)))
    warnings = ["docx_body_only: bez nagłówków, stopek, komentarzy i załączników"]
    if revised or any(document.iter(f"{W}moveFrom")):
        warnings.append("tracked_changes: uzgodnij ostateczny tekst przed zatwierdzeniem zasad")
    return units, warnings


def read_units(payload, suffix):
    if len(payload) > MAX_FILE:
        fail("CONTEXT_LIMIT", "Materiał przekracza limit 50 MB.")
    if suffix in (".txt", ".md"):
        text = payload.decode("utf-8-sig")
        return [(f"line:{n}", line) for n, line in enumerate(text.splitlines(), 1)], []
    if suffix == ".docx":
        return docx_units(payload)
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            fail("CONTEXT_DEPENDENCY", "Odczyt PDF wymaga instalacji dodatku pdf.")
        reader = PdfReader(io.BytesIO(payload))
        if reader.is_encrypted:
            fail("CONTEXT_ENCRYPTED", "Zaimportuj odblokowaną kopię PDF.")
        if len(reader.pages) > 1000:
            fail("CONTEXT_LIMIT", "PDF przekracza limit 1000 stron.")
        units, warnings, size = [], [], 0
        for number, page in enumerate(reader.pages, 1):
            content = page.get_contents()
            if content is not None and len(content.get_data()) > MAX_XML:
                fail("CONTEXT_LIMIT", "Strumień strony PDF przekracza limit 10 MB.")
            text = page.extract_text() or ""
            size += len(text)
            if size > MAX_TEXT:
                fail("CONTEXT_LIMIT", "Tekst przekracza limit 2 mln znaków.")
            if not text.strip():
                warnings.append(f"page:{number}: brak warstwy tekstowej; sprawdź stronę lub OCR")
            units.append((f"page:{number}", text))
        return units, warnings
    fail("CONTEXT_UNSUPPORTED", "Odczyt obsługuje PDF, DOCX, TXT i MD (UTF-8).")


def extract(payload, suffix, client_id, material):
    try:
        units, warnings = read_units(payload, suffix)
        if sum(len(text) for _, text in units) > MAX_TEXT:
            fail("CONTEXT_LIMIT", "Tekst przekracza limit 2 mln znaków.")
        chunks = []
        for locator, text in units:
            # Normalized whitespace, retained wording; quote refers to extracted text.
            text = re.sub(r"\s+", " ", text).strip()
            for start in range(0, len(text), CHUNK_SIZE):
                quote = text[start : start + CHUNK_SIZE]
                location = f"{locator}/chars:{start + 1}-{start + len(quote)}"
                digest = hashlib.sha256(
                    (
                        client_id
                        + "\n"
                        + material["id"]
                        + "\n"
                        + material["sha256"]
                        + "\n"
                        + location
                        + "\n"
                        + quote
                    ).encode()
                ).hexdigest()
                chunks.append(
                    {
                        "client_id": client_id,
                        "material_id": material["id"],
                        "sha256": material["sha256"],
                        "chunk_id": digest,
                        "title": material["title"],
                        "locator": location,
                        "quote": quote,
                    }
                )
        return {
            "reader_version": "1",
            "status": "ok" if chunks else "no_text",
            "warnings": warnings,
            "chunks": chunks,
        }
    except AppError:
        raise
    except Exception:
        # Do not expose document contents or parser dumps in error messages.
        fail("CONTEXT_FORMAT", "Nie można odczytać dokumentu; sprawdź format i kodowanie.")
