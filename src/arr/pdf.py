"""Impression des antisèches : une feuille A4 en colonnes, chaque morceau à la hauteur de son contenu."""

from __future__ import annotations

from pathlib import Path

from arr import sheet as sheets

PAGE = (210.0, 297.0)  # A4, en millimètres
MARGIN, GUTTER, HEADER = 8.0, 6.0, 6.0
MM = 0.3528  # un point typographique, en millimètres
LEADING = 1.22
SCALES = [s / 20 for s in range(32, 9, -1)]  # de 1,6 à 0,5 : la plus grande taille qui tient est gardée
SMALL = 0.75  # en dessous, le texte ne se lit plus debout
GREY = 110
# Tailles en points, à l'échelle 1.
NUMBER, TITLE, ARTIST, KEY, BPM, STRUCTURE, PART, CHORDS, NOTE, TAB = 20, 13, 9, 15, 9, 7.5, 8, 10.5, 9, 8
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

    def font(self, size: float, style: str) -> None:
        """Helvetica, ou Courier pour le style « C » (tablatures : les colonnes doivent tomber juste)."""
        self.pdf.set_font("Courier" if style == "C" else "Helvetica", "" if style == "C" else style, size * self.scale)

    def width(self, text: str, size: float, style: str = "") -> float:
        self.font(size, style)
        return self.pdf.get_string_width(plain(text))

    def high(self, size: float) -> float:
        return size * self.scale * MM * LEADING

    def write(self, x: float, base: float, text: str, size: float, style: str = "", grey: int = 0) -> None:
        """Écrit `text` posé sur la ligne de base `base`."""
        self.font(size, style)
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


def pieces(slots: int, kind: str, start: int, length: int) -> list[tuple[int, int]]:
    """Découpe une durée en valeurs qui s'écrivent : (case de départ, valeur en doubles croches : 1, 2, 3 ou 4).

    Ce qui remplit le temps est une noire ou un soupir. Dans un temps de quatre doubles
    croches, une valeur de croche ou plus commence sur une case paire, sauf la croche au
    milieu du temps (double, croche, double) ; ailleurs chaque case est une croche.
    """
    if length == slots:
        return [(start, 4)]
    if slots != 4:
        return [(start + i, 2) for i in range(length)]
    if length == 3 and start == 0 and kind == "note":
        return [(start, 3)]
    out = []
    while length:
        size = 2 if length >= 2 and (start % 2 == 0 or (start == 1 and kind == "note")) else 1
        out.append((start, size))
        start, length = start + size, length - size
    return out


def staff(doc: Sheet, bars: list, width: float) -> list[tuple]:
    """Les lignes de portée d'un rythme : (hauteur, [(0, dessin)]), les mesures repliées à la largeur."""
    u = doc.scale
    slot = min(2.3 * u, (width - 2 * u) / max(sum(n for n, _ in bar) + len(bar) * 0.6 for bar in bars))
    span = lambda bar: sum(n for n, _ in bar) * slot + len(bar) * 0.6 * slot + 1.5 * u
    rows: list[list] = [[]]
    for bar in bars:
        if rows[-1] and sum(map(span, rows[-1])) + span(bar) > width:
            rows.append([])
        rows[-1].append(bar)
    return [(13.0 * u, [(0.0, lambda d, x, y, row=row: draw_rhythm(d, x, y, row, slot, span))]) for row in rows]


def draw_rhythm(doc: Sheet, x: float, y: float, bars: list, slot: float, span) -> None:
    """Dessine des mesures de rythme sur une ligne : têtes, hampes, ligatures, points, liaisons, silences."""
    pdf, u = doc.pdf, doc.scale
    line, top = y + 9.6 * u, y + 3.4 * u  # la ligne des têtes, et le haut des hampes
    pdf.set_draw_color(0)
    pdf.set_fill_color(0)
    last_head = None
    at = x
    for bar in bars:
        pdf.set_line_width(0.15 * u)
        pdf.set_draw_color(150)
        pdf.line(at, line, at + span(bar) - 1.5 * u, line)
        pdf.set_draw_color(0)
        for slots, events in bar:
            left = at + 0.3 * slot
            notes = []  # (x de la hampe, durée) des notes du temps, pour les ligatures
            for kind, start, length, tied in events:
                for i, (where, size) in enumerate(pieces(slots, kind, start, length)):
                    cx = left + (where + 0.5) * slot
                    if kind == "rest":
                        draw_rest(doc, cx, line, size)
                        continue
                    pdf.ellipse(cx - 1.05 * u, line - 0.72 * u, 2.1 * u, 1.44 * u, style="F")
                    stem = cx + 0.95 * u
                    pdf.set_line_width(0.28 * u)
                    pdf.line(stem, line - 0.2 * u, stem, top)
                    if size == 3:
                        pdf.circle(cx + 1.9 * u, line - 0.9 * u, 0.3 * u, style="F")
                    if (tied or i > 0) and last_head is not None:
                        a, b = last_head + 0.6 * u, cx - 0.6 * u
                        pdf.set_line_width(0.22 * u)
                        pdf.bezier([(a, line + 1.3 * u), ((a + b) / 2, line + 2.6 * u), (b, line + 1.3 * u)])
                    last_head = cx
                    notes.append((stem, size))
            short = [n for n in notes if n[1] < 4]
            if len(short) > 1:
                pdf.rect(short[0][0] - 0.14 * u, top, short[-1][0] - short[0][0] + 0.28 * u, 0.85 * u, style="F")
                for j, (stem, size) in enumerate(short):
                    if size == 1:
                        # La seconde barre va vers la voisine si elle est aussi une double, sinon un court tronçon.
                        to_next = j + 1 < len(short) and (short[j + 1][1] == 1 or j == 0)
                        end = (
                            short[j + 1][0]
                            if to_next and short[j + 1][1] == 1
                            else stem + (1.3 * u if to_next else -1.3 * u)
                        )
                        pdf.rect(
                            min(stem, end) - 0.14 * u, top + 1.25 * u, abs(end - stem) + 0.28 * u, 0.85 * u, style="F"
                        )
            elif short:
                stem, size = short[0]
                pdf.set_line_width(0.4 * u)
                for k in range(2 if size == 1 else 1):
                    pdf.line(stem, top + k * 1.2 * u, stem + 1.5 * u, top + (k * 1.2 + 2.0) * u)
            if slots == 3 and notes:
                doc.write(left + 1.2 * slot, top - 0.6 * u, "3", 6, "I")
            at += slots * slot + 0.6 * slot
        pdf.set_line_width(0.25 * u)
        pdf.line(at + 0.4 * u, line - 3.0 * u, at + 0.4 * u, line + 3.0 * u)
        at += 1.5 * u


def draw_rest(doc: Sheet, cx: float, line: float, size: int) -> None:
    """Un silence : soupir (une noire), demi-soupir (une croche), quart de soupir (une double croche)."""
    pdf, u = doc.pdf, doc.scale * 0.72
    if size >= 4:
        pdf.set_line_width(0.55 * u)
        points = [(-0.6, -4.2), (0.6, -2.8), (-0.7, -1.4), (0.6, 0.0), (-0.4, 0.1), (-0.6, 1.2)]
        pdf.polyline([(cx + a * u, line - 0.6 * u + b * u) for a, b in points])
        return
    pdf.set_line_width(0.34 * u)
    pdf.line(cx + 0.8 * u, line - 4.2 * u, cx - 0.1 * u, line + 0.6 * u)
    for k in range(2 if size == 1 else 1):
        yy = line - 3.5 * u + k * 1.6 * u
        pdf.circle(cx - 0.9 * u - k * 0.35 * u, yy - 0.5 * u, 0.5 * u, style="F")
        pdf.line(cx - 0.6 * u - k * 0.35 * u, yy + 0.3 * u, cx + 0.7 * u - k * 0.35 * u, yy - 0.5 * u)


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
    for groove in sheet.get("grooves", []):
        label = " · ".join(filter(None, (str(groove.get("instrument", "")), str(groove.get("part", "")))))
        lines.append((doc.high(PART), [(0.0, label, PART, "", GREY)]))
        if groove.get("rhythm"):
            lines += staff(doc, sheets.rhythm(str(groove["rhythm"])), width)
        for row in groove.get("tab", []):
            lines.append((doc.high(TAB) * 0.92, [(0.0, doc.fit(str(row), width, TAB, "C"), TAB, "C", 0)]))
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
                if callable(segments[0][1]):
                    segments[0][1](doc, x, at)
                    at += height
                    continue
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
