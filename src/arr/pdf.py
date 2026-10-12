"""Impression des antisèches : une feuille A4 en colonnes, chaque morceau à la hauteur de son contenu."""

from __future__ import annotations

from pathlib import Path

PAGE = (210.0, 297.0)  # A4, en millimètres
MARGIN, GUTTER, HEADER = 8.0, 6.0, 6.0
MM = 0.3528  # un point typographique, en millimètres
LEADING = 1.22
SCALES = [s / 20 for s in range(32, 9, -1)]  # de 1,6 à 0,5 : la plus grande taille qui tient est gardée
SMALL = 0.75  # en dessous, le texte ne se lit plus debout
GREY = 110
# Tailles en points, à l'échelle 1.
NUMBER, TITLE, ARTIST, KEY, BPM, STRUCTURE, PART, CHORDS, NOTE = 20, 13, 9, 15, 9, 7.5, 8, 10.5, 9
SWAPS = {"–": "-", "—": "-", "…": "...", "•": "-", "’": "'", "‘": "'", "“": '"', "”": '"', "→": ">", "♭": "b", "♯": "#"}


def plain(text: str) -> str:
    """Le texte dans les caractères des polices de base (Latin-1) : les accents passent, pas les symboles."""
    for old, new in SWAPS.items():
        text = text.replace(old, new)
    return text.encode("latin-1", "replace").decode("latin-1")


class Sheet:
    """Un document en cours : sait mesurer et écrire du texte à une échelle donnée."""

    def __init__(self, scale: float = 1.0):
        from fpdf import FPDF

        self.pdf = FPDF(format="A4", unit="mm")
        self.pdf.set_auto_page_break(False)
        self.scale = scale

    def width(self, text: str, size: float, style: str = "") -> float:
        self.pdf.set_font("Helvetica", style, size * self.scale)
        return self.pdf.get_string_width(plain(text))

    def high(self, size: float) -> float:
        return size * self.scale * MM * LEADING

    def write(self, x: float, base: float, text: str, size: float, style: str = "", grey: int = 0) -> None:
        """Écrit `text` posé sur la ligne de base `base`."""
        self.pdf.set_font("Helvetica", style, size * self.scale)
        self.pdf.set_text_color(grey)
        self.pdf.text(x, base, plain(text))

    def fit(self, text: str, room: float, size: float, style: str = "") -> str:
        """`text`, coupé par des points de suspension s'il dépasse `room`."""
        if self.width(text, size, style) <= room:
            return text
        while text and self.width(text + "...", size, style) > room:
            text = text[:-1]
        return text.rstrip() + "..."

    def wrap(self, text: str, room: float, size: float, style: str = "", sep: str = " ") -> list[str]:
        """Coupe `text` en lignes d'au plus `room`, aux `sep` (« | » pour des accords : une mesure ne se coupe pas)."""
        lines, line = [], ""
        for word in text.split(sep):
            longer = f"{line}{sep}{word}" if line else word
            if line and self.width(longer, size, style) > room:
                lines.append(line + sep.rstrip())
                line = word.lstrip()
            else:
                line = longer
        return lines + [line] if line else lines


def block(doc: Sheet, entry: dict, width: float) -> list[tuple]:
    """Les lignes d'un morceau : (hauteur, [(décalage x, texte, taille, style, gris)])."""
    sheet = entry["sheet"]
    if entry.get("break"):
        return [(doc.high(NOTE) * 1.6, [(0.0, entry.get("title", "Entracte"), NOTE, "I", GREY)])]
    lines = []
    number = str(entry.get("number", ""))
    right = [(f"{sheet['key']}", KEY, "B", 0), (f" {sheet['bpm']}", BPM, "", GREY)]
    right_width = sum(doc.width(t, size, style) for t, size, style, _ in right)
    x = doc.width(number, NUMBER, "B") + 2.0 * doc.scale
    room = width - x - right_width - 2.0
    # Un titre long est d'abord écrit plus petit, et coupé seulement s'il ne tient toujours pas.
    size = next((s for s in (TITLE, TITLE * 0.85, TITLE * 0.72) if doc.width(entry["title"], s, "B") <= room), None)
    title = entry["title"] if size else doc.fit(entry["title"], room, TITLE * 0.72, "B")
    size = size or TITLE * 0.72
    head = [(0.0, number, NUMBER, "B", 0), (x, title, size, "B", 0)]
    after = x + doc.width(title, size, "B") + 1.5
    if entry.get("artist") and after + doc.width(entry["artist"], ARTIST) <= x + room:
        head.append((after, entry["artist"], ARTIST, "", GREY))
    at = width - right_width
    for text, size, style, grey in right:
        head.append((at, text, size, style, grey))
        at += doc.width(text, size, style)
    lines.append((doc.high(NUMBER), head))
    for row in doc.wrap(sheet.get("structure", ""), width, STRUCTURE, sep=" · ")[:2]:
        lines.append((doc.high(STRUCTURE), [(0.0, row, STRUCTURE, "", GREY)]))
    parts = sheet.get("parts", [])
    indent = max((doc.width(str(p.get("name", "")), PART, "B") for p in parts), default=0.0) + 2.0
    for part in parts:
        times = f"  ×{part['repeat']}" if part.get("repeat", 1) > 1 else ""
        rows = doc.wrap(str(part.get("chords", "")) + times, width - indent, CHORDS, "B", sep=" | ")
        for i, row in enumerate(rows):
            name = [(0.0, str(part.get("name", "")), PART, "", GREY)] if i == 0 else []
            lines.append((doc.high(CHORDS), [*name, (indent, row, CHORDS, "B", 0)]))
    for note in [*sheet.get("notes", []), *([entry["note"]] if entry.get("note") else [])]:
        for i, row in enumerate(doc.wrap(note, width - 3.0, NOTE)):
            lines.append((doc.high(NOTE), [(0.0, "-" if i == 0 else "", NOTE, "", 0), (3.0, row, NOTE, "", 0)]))
    return lines


def layout(doc: Sheet, entries: list[dict], columns: int) -> list[list[tuple]]:
    """Range les morceaux en colonnes, sans jamais en couper un : pages de (x, y, lignes)."""
    width = (PAGE[0] - 2 * MARGIN - (columns - 1) * GUTTER) / columns
    gap = 2.2 * doc.scale
    pages: list[list[tuple]] = [[]]
    column, y = 0, MARGIN + HEADER
    for entry in entries:
        lines = block(doc, entry, width)
        height = sum(h for h, _ in lines) + 2 * gap
        if y + height > PAGE[1] - MARGIN and y > MARGIN + HEADER:
            column, y = column + 1, MARGIN + HEADER
            if column == columns:
                pages.append([])
                column = 0
        pages[-1].append((MARGIN + column * (width + GUTTER), y, width, lines, gap))
        y += height
    return pages


def render(entries: list[dict], title: str, path: Path, columns: int = 2, pages: int | None = None) -> dict:
    """Écrit le PDF des antisèches ; renvoie le nombre de pages, l'échelle du texte et si elle reste lisible.

    Avec `pages`, l'échelle est la plus grande qui fasse tenir le tout dans ce nombre de
    feuilles ; sans, le texte garde sa taille normale et prend la place qu'il faut.
    """
    for scale in SCALES if pages else [1.0]:
        doc = Sheet(scale)
        laid = layout(doc, entries, columns)
        if not pages or len(laid) <= pages:
            break
    for n, page in enumerate(laid, start=1):
        doc.pdf.add_page()
        doc.write(MARGIN, MARGIN + 2.0, title, 8 / doc.scale, "B", GREY)
        mark = f"{n} / {len(laid)}"
        doc.write(PAGE[0] - MARGIN - doc.width(mark, 8 / doc.scale), MARGIN + 2.0, mark, 8 / doc.scale, "", GREY)
        for x, y, width, lines, gap in page:
            doc.pdf.set_draw_color(170)
            doc.pdf.set_line_width(0.2)
            doc.pdf.line(x, y, x + width, y)
            at = y + gap
            for height, segments in lines:
                # Tous les textes d'une ligne reposent sur la même ligne de base, celle du plus grand.
                base = at + max(size for _, _, size, _, _ in segments) * doc.scale * MM
                for dx, text, size, style, grey in segments:
                    doc.write(x + dx, base, text, size, style, grey)
                at += height
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.pdf.output(str(path))
    return {
        "pages": len(laid),
        "scale": doc.scale,
        "readable": doc.scale >= SMALL,
        "fits": not pages or len(laid) <= pages,
    }
