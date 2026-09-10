"""Bluerank PDF layout and local rendering. No network or access to Meta credentials."""

import hashlib
import io
import json
import os
import unicodedata
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path
from xml.sax.saxutils import escape

from meta_ads_manager.errors import AppError
from meta_ads_manager.pdf_content import prepare
from meta_ads_manager.pdf_models import PdfDocument

TEMPLATE_VERSION = "bluerank-1.0"


def dependencies():
    try:
        import reportlab  # noqa: F401
        from pypdf import PdfReader  # noqa: F401
    except ImportError:
        raise AppError(
            "PDF_DEPENDENCY", "Zainstaluj dodatek PDF: uv sync --extra pdf.", 2
        ) from None


def build_document(doc: PdfDocument) -> tuple[bytes, list[str]]:
    dependencies()
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.platypus import (
        HRFlowable,
        KeepTogether,
        LongTable,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )
    from reportlab.platypus.doctemplate import LayoutError

    assets = files("meta_ads_manager").joinpath("assets")
    for font, filename in [("BR", "DejaVuSans.ttf"), ("BR-Bold", "DejaVuSans-Bold.ttf")]:
        if font not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(font, str(assets.joinpath("fonts", filename))))
    glyphs = set(pdfmetrics.getFont("BR").face.charToGlyph) & set(
        pdfmetrics.getFont("BR-Bold").face.charToGlyph
    )
    unsupported = set()

    def clean(text):
        text = unicodedata.normalize("NFC", str(text))
        substitutions = {
            "–": "-",
            "—": "-",
            "‑": "-",
            "−": "-",
            "\u00a0": " ",
            "\u202f": " ",
            "\ufe0f": "",
            "\u200d": "",
            "\t": "    ",
        }
        result = []
        for char in text:
            if char in substitutions:
                result.append(substitutions[char])
            elif char == "\n" or ord(char) in glyphs:
                result.append(char)
            else:
                label = f"U+{ord(char):04X}"
                unsupported.add(label)
                result.append(f"[{label}]")
        return "".join(result)

    ink, muted = colors.HexColor("#111820"), colors.HexColor("#586775")
    blue, pale, line = (
        colors.HexColor("#38B4E7"),
        colors.HexColor("#F0F8FC"),
        colors.HexColor("#DCE5EA"),
    )
    styles = {
        "title": ParagraphStyle(
            "title", fontName="BR-Bold", fontSize=25, leading=31, textColor=ink, spaceAfter=9
        ),
        "subtitle": ParagraphStyle(
            "subtitle", fontName="BR", fontSize=13, leading=18, textColor=muted, spaceAfter=18
        ),
        "body": ParagraphStyle(
            "body",
            fontName="BR",
            fontSize=9.4,
            leading=14.5,
            textColor=ink,
            spaceAfter=8,
            splitLongWords=True,
        ),
        "small": ParagraphStyle(
            "small",
            fontName="BR",
            fontSize=8,
            leading=11.5,
            textColor=muted,
            spaceAfter=5,
            splitLongWords=True,
        ),
        "heading": ParagraphStyle(
            "heading",
            fontName="BR-Bold",
            fontSize=12,
            leading=16,
            textColor=ink,
            spaceBefore=17,
            spaceAfter=9,
            keepWithNext=True,
        ),
        "cell": ParagraphStyle(
            "cell", fontName="BR", fontSize=8, leading=11.5, textColor=ink, splitLongWords=True
        ),
        "headcell": ParagraphStyle(
            "headcell",
            fontName="BR-Bold",
            fontSize=7.7,
            leading=11,
            textColor=ink,
            splitLongWords=True,
        ),
        "kpi": ParagraphStyle(
            "kpi",
            fontName="BR-Bold",
            fontSize=18,
            leading=24,
            textColor=ink,
            spaceBefore=5,
            spaceAfter=2,
        ),
    }

    def para(text, style="body", right=False):
        selected = styles[style]
        if right:
            selected = ParagraphStyle(selected.name + "Right", parent=selected, alignment=TA_RIGHT)
        return Paragraph(escape(clean(text)).replace("\n", "<br/>"), selected)

    width, height = A4
    margin, content_width = 42, width - 84
    source = {
        "meta": "DANE META API",
        "demo": "DANE DEMONSTRACYJNE",
        "manual": "OPRACOWANIE WŁASNE",
    }[doc.source]
    status = {"partial": "AUDYT CZĘŚCIOWY", "report": "RAPORT WYNIKÓW", "custom": "ANALIZA"}[
        doc.coverage
    ]
    logo = str(assets.joinpath("bluerank-logo.png"))

    class NumberedCanvas(Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.states = []

        def showPage(self):
            self.states.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self.states)
            for state in self.states:
                self.__dict__.update(state)
                self.setStrokeColor(line)
                self.setLineWidth(0.5)
                self.line(margin, 39, width - margin, 39)
                self.setFont("BR", 7)
                self.setFillColor(muted)
                self.drawString(margin, 25, f"{source}  /  {doc.report_date.isoformat()}")
                self.drawRightString(width - margin, 25, f"{self._pageNumber} / {total}")
                Canvas.showPage(self)
            Canvas.save(self)

    def header(canvas, _):
        canvas.saveState()
        canvas.drawImage(logo, margin, height - 60, width=108, height=108 * 305 / 1060, mask="auto")
        canvas.setFont("BR-Bold", 7.8)
        canvas.setFillColor(muted)
        canvas.drawRightString(width - margin, height - 40, "ANALIZY META ADS")
        canvas.setFont("BR", 7)
        canvas.drawRightString(width - margin, height - 54, status)
        canvas.setStrokeColor(blue)
        canvas.setLineWidth(1.8)
        canvas.line(margin, height - 75, width - margin, height - 75)
        canvas.restoreState()

    story = [para(source, "small"), para(doc.title, "title")]
    if doc.subtitle:
        story.append(para(doc.subtitle, "subtitle"))
    metadata = [
        f"Okres: {doc.period_since.isoformat()} - {doc.period_until.isoformat()}",
        f"Konto: {doc.account_id}  |  Klient: {doc.client_id}",
    ]
    if doc.currency or doc.timezone:
        metadata.append(
            f"Waluta: {doc.currency or 'nie dotyczy'}  |  Strefa: {doc.timezone or 'nie podano'}"
        )
    story.extend(para(text, "small") for text in metadata)
    story.append(Spacer(1, 12))
    if doc.metrics:
        for offset in range(0, len(doc.metrics), 3):
            chunk = doc.metrics[offset : offset + 3]
            cells = []
            for item in chunk:
                cell = [para(item.label.upper(), "small"), para(item.value, "kpi")]
                if item.detail:
                    cell.append(para(item.detail, "small"))
                cells.append(cell)
            card = Table([cells], colWidths=[content_width / len(cells)] * len(cells))
            card.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), pale),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 12),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                        ("TOPPADDING", (0, 0), (-1, -1), 11),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 11),
                        ("LINEBEFORE", (1, 0), (-1, -1), 2, colors.white),
                    ]
                )
            )
            story += [card, Spacer(1, 10)]
    if doc.summary:
        story.append(para("Najważniejsze informacje", "heading"))
        story.extend(para(text) for text in doc.summary)

    for section in doc.sections:
        if section.new_page:
            story.append(PageBreak())
        story.append(para(section.title, "heading"))
        story.extend(para(text) for text in section.paragraphs)
        for text in section.bullets:
            bullet = LongTable(
                [[para("•"), para(text)]],
                colWidths=[12, content_width - 12],
                splitByRow=1,
                splitInRow=1,
            )
            bullet.setStyle(
                TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ]
                )
            )
            story.append(bullet)
        if section.table:
            spec = section.table
            weights = spec.widths or [1] * len(spec.columns)
            widths = [content_width * weight / sum(weights) for weight in weights]
            cells = [
                [
                    para(text, "headcell", index in spec.numeric_columns)
                    for index, text in enumerate(spec.columns)
                ]
            ]
            cells += [
                [
                    para(text, "cell", index in spec.numeric_columns)
                    for index, text in enumerate(row)
                ]
                for row in spec.rows
            ]
            grid = LongTable(
                cells, colWidths=widths, repeatRows=1, splitByRow=1, splitInRow=1, hAlign=TA_LEFT
            )
            grid.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), pale),
                        ("LINEBELOW", (0, 0), (-1, 0), 1, blue),
                        (
                            "ROWBACKGROUNDS",
                            (0, 1),
                            (-1, -1),
                            [colors.white, colors.HexColor("#F7F9FA")],
                        ),
                        ("LINEBELOW", (0, 1), (-1, -1), 0.3, line),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 9),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                        ("TOPPADDING", (0, 0), (-1, -1), 9),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
                    ]
                )
            )
            story.append(grid)
    appendix = [
        Spacer(1, 15),
        HRFlowable(width="100%", thickness=0.6, color=line),
        para("Zakres i ograniczenia", "heading"),
    ]
    appendix.extend(para(text, "small") for text in doc.limitations)
    appendix.append(para("Źródła i identyfikacja raportu", "heading"))
    appendix.extend(para(text, "small") for text in doc.evidence)
    if unsupported:
        appendix.append(
            para(
                "Znaki bez dostępnego glifu zapisano kodem Unicode: "
                + ", ".join(sorted(unsupported)),
                "small",
            )
        )
    story.append(KeepTogether(appendix))
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=margin,
        leftMargin=margin,
        topMargin=94,
        bottomMargin=57,
        title=clean(doc.title),
        author="Bluerank",
        subject=source,
        pageCompression=1,
    )
    try:
        document.build(story, onFirstPage=header, onLaterPages=header, canvasmaker=NumberedCanvas)
    except LayoutError:
        raise AppError(
            "PDF_LAYOUT", "Treść nie mieści się w układzie. Podziel długi blok lub tabelę.", 2
        ) from None
    return buffer.getvalue(), sorted(unsupported)


def export_pdf(
    input_path: Path, output: Path, client: str, account: str, notes: Path | None = None
):
    if output.suffix.lower() != ".pdf":
        raise AppError("VALIDATION_ERROR", "Plik wynikowy musi mieć rozszerzenie .pdf.", 2)
    manifest = output.with_suffix(".pdf.json")
    if output.exists() or manifest.exists():
        raise AppError(
            "OUTPUT_EXISTS", "PDF lub jego metadane już istnieją; wybierz nową nazwę.", 2
        )
    doc = prepare(input_path, client, account, notes)
    payload, unsupported = build_document(doc)
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(payload))
    if not reader.pages or any(not page.extract_text().strip() for page in reader.pages):
        raise AppError("PDF_VALIDATION", "Dokument zawiera pustą stronę.", 2)
    result = {
        "pdf": str(output.resolve()),
        "manifest": str(manifest.resolve()),
        "template_version": TEMPLATE_VERSION,
        "client_id": client,
        "account_id": account,
        "source": doc.source,
        "page_count": len(reader.pages),
        "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
        "notes_sha256": hashlib.sha256(notes.read_bytes()).hexdigest() if notes else None,
        "pdf_sha256": hashlib.sha256(payload).hexdigest(),
        "created_at": datetime.now(UTC).isoformat(),
        "unsupported_characters": unsupported,
        "automated_checks": "passed",
        "visual_review": "required",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    created_pdf = False
    created_manifest = False
    try:
        fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        created_pdf = True
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
        fd = os.open(manifest, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        created_manifest = True
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(result, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    except OSError as error:
        if created_pdf:
            output.unlink()
        if created_manifest:
            manifest.unlink()
        if isinstance(error, FileExistsError):
            raise AppError(
                "OUTPUT_EXISTS", "Plik wynikowy już istnieje; wybierz nową nazwę.", 2
            ) from None
        raise
    return result


def render_pdf(path: Path, directory: Path, dpi: int = 110):
    if directory.exists():
        raise AppError("OUTPUT_EXISTS", "Katalog podglądu już istnieje; wybierz nową nazwę.", 2)
    if not 72 <= dpi <= 200:
        raise AppError("VALIDATION_ERROR", "Rozdzielczość podglądu: 72-200 DPI.", 2)
    try:
        import pypdfium2 as pdfium
    except ImportError:
        raise AppError(
            "PDF_DEPENDENCY", "Zainstaluj dodatek PDF: uv sync --extra pdf.", 2
        ) from None
    rendered = []
    with pdfium.PdfDocument(str(path)) as pdf:
        if not 1 <= len(pdf) <= 200:
            raise AppError("PDF_VALIDATION", "Podgląd obsługuje 1-200 stron.", 2)
        directory.mkdir(parents=True, mode=0o700)
        for index in range(len(pdf)):
            page = pdf[index]
            bitmap = page.render(scale=dpi / 72)
            target = directory / f"page-{index + 1:03d}.png"
            bitmap.to_pil().save(target)
            bitmap.close()
            page.close()
            rendered.append(str(target.resolve()))
    return {
        "pdf": str(path.resolve()),
        "pages": rendered,
        "page_count": len(rendered),
        "visual_review": "required",
    }
