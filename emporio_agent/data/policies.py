"""Store policies: PDF -> cleaned text -> numbered sections -> keyword search.

The manual has ten numbered top-level sections, each one a coherent topic
small enough to return whole. Searching them with keywords is enough for ten
documents and keeps it obvious which policy the agent used. A vector store
would add dependencies without improving answers at this size.
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

from emporio_agent import config
from emporio_agent.text_utils import normalize

logger = logging.getLogger(__name__)

# Fixes for contradictions inside the manual, applied to the extracted text at
# load time (the PDF itself stays untouched). Written with single spaces: the
# match tolerates any whitespace, including PDF line breaks. See
# docs/data_notes.md, section 7.
POLICY_CORRECTIONS = {
    # Section 7 lists WhatsApp (67) 3321-4500, but the cover and the official
    # company data table (1.2, "Telefone / WhatsApp") both say 3341-4444.
    "(67) 3321-4500": "(67) 3341-4444",
    # Section 1.2 has an invalid accented domain; the cover has the plain one.
    "contato@empóriodamusica.com.br": "contato@emporiodamusica.com.br",
    # Section 3's table says "min. installment R$ 100" for every credit
    # payment; the tiered rules in 3.1 are more specific, so they win.
    "Parcela mínima de R$ 100,00": "Parcela mínima conforme a seção 3.1",
    # "No minimum installment (except below R$ 50.00)" is ambiguous; it is
    # read as a minimum installment of R$ 50.00 for 1x to 3x.
    "sem valor mínimo de parcela (exceto abaixo de R$ 50,00)": (
        "parcela mínima de R$ 50,00"
    ),
}

HEADER_LINE = "Empório da Música Manual de Políticas e Procedimentos"
FOOTER_PATTERN = re.compile(r"^\s*Página \d+\s*$")
# Top-level headings start at column 0 ("4. Política de Trocas..."). Numbered
# list items inside sections ("    3.   Consulta:") are indented, so they
# do not match.
SECTION_HEADING = re.compile(r"^(\d{1,2})\.[ \t]+(\S.*)$", re.MULTILINE)
EXPECTED_SECTION_COUNT = 10
LIST_MARKER = re.compile(r"^(•|\d+\.)\s+")
TABLE_GAP = re.compile(r"\s{3,}")

# --- Search settings -------------------------------------------------------

MAX_POLICY_RESULTS = 2
TITLE_WEIGHT = 3
SYNONYM_WEIGHT = 3
BODY_WEIGHT = 1
# Comparing the first 5 letters is a crude stemmer for Portuguese:
# "devolver" and "devoluções" both become "devol".
STEM_LENGTH = 5
MIN_WORD_LENGTH = 3  # keeps "pix", drops "de", "o", "em"
STOPWORDS = {
    "com", "como", "das", "dos", "ela", "ele", "emporio", "essa", "esse",
    "esta", "gostaria", "isso", "loja", "mais", "meu", "meus", "minha",
    "minhas", "musica", "nao", "nas", "nos", "obrigado", "ola", "para",
    "pode", "por", "posso", "pra", "qual", "quais", "que", "queria", "quero",
    "seu", "sim", "sobre", "sua", "tem", "ter", "uma", "voce", "voces",
}  # fmt: skip

# Customer words mapped to the section that best answers them: words missing
# from the manual ("abrem", "estorno"), plus a few that appear in several
# sections but belong to one ("endereço" is also in the privacy section).
TOPIC_SYNONYMS = {
    1: (
        "onde",
        "fica",
        "localizacao",
        "localizada",
        "endereco",
        "telefone",
        "whatsapp",
        "email",
        "contato",
        "vende",
        "vendem",
        "vender",
        "acessorio",
        "acessorios",
    ),  # fmt: skip
    2: ("abre", "abrem", "aberta", "aberto", "fecha", "fecham", "horas", "hoje"),
    3: ("pagar", "parcelar", "parcelo", "vezes", "pix"),
    4: ("arrependi", "arrependido", "desistir", "desisti", "estorno"),
    5: ("rastreio", "chega", "chegar", "demora", "demorar"),
    6: ("cupom", "oferta", "ofertas", "barato"),
    7: ("reclamar", "gerente", "problema", "insatisfeito"),
    8: ("quebrou", "quebrado", "estragou", "conserto", "consertar"),
    9: ("apagar", "cadastro"),
}


@dataclass(frozen=True)
class PolicySection:
    """One numbered top-level section of the manual, with its subsections."""

    number: int
    title: str
    text: str

    @property
    def heading(self) -> str:
        """Section number and title, e.g. "4. Política de Trocas e Devoluções"."""
        return f"{self.number}. {self.title}"


def load_policy_sections(pdf_path: Path = config.POLICIES_PDF) -> list[PolicySection]:
    """Extract, clean, correct and split the manual. Run once at startup."""
    text = extract_pdf_text(pdf_path)
    text = strip_header_and_footer(text)
    text = apply_corrections(text)
    sections = split_sections(text)
    logger.info("Loaded %d policy sections from %s", len(sections), pdf_path.name)
    return sections


def extract_pdf_text(pdf_path: Path) -> str:
    """Extract the PDF text, keeping lines, tables and indentation.

    pypdf's default mode puts every word on its own line; "layout" mode keeps
    the visual lines, which the section splitting relies on.
    """
    reader = PdfReader(pdf_path)
    pages = [page.extract_text(extraction_mode="layout") for page in reader.pages]
    return "\n".join(pages)


def strip_header_and_footer(text: str) -> str:
    """Remove the header and "Página N" footer repeated on every page."""
    kept_lines = [
        line
        for line in text.splitlines()
        if " ".join(line.split()) != HEADER_LINE and not FOOTER_PATTERN.match(line)
    ]
    return "\n".join(kept_lines)


def apply_corrections(text: str) -> str:
    """Apply POLICY_CORRECTIONS. Fails fast if one no longer matches the PDF."""
    for wrong, right in POLICY_CORRECTIONS.items():
        text, count = replace_ignoring_whitespace(text, wrong, right)
        if count == 0:
            raise ValueError(f"Policy correction not found in the PDF: {wrong!r}")
    return text


def replace_ignoring_whitespace(text: str, old: str, new: str) -> tuple[str, int]:
    """Replace `old` even where the PDF broke it across lines or padded spaces.

    Returns the new text and the number of replacements made.
    """
    words = [re.escape(word) for word in old.split()]
    pattern = re.compile(r"\s+".join(words))
    # A function as replacement inserts `new` literally (no "\1" escapes).
    return pattern.subn(lambda _match: new, text)


def split_sections(text: str) -> list[PolicySection]:
    """Split the text into the ten top-level sections (the cover is dropped)."""
    headings = list(SECTION_HEADING.finditer(text))
    numbers = [int(heading.group(1)) for heading in headings]
    if numbers != list(range(1, EXPECTED_SECTION_COUNT + 1)):
        raise ValueError(f"Unexpected policy section numbers: {numbers}")

    sections = []
    for index, heading in enumerate(headings):
        is_last = index + 1 == len(headings)
        end = len(text) if is_last else headings[index + 1].start()
        sections.append(
            PolicySection(
                number=int(heading.group(1)),
                title=heading.group(2).strip(),
                text=tidy_text(text[heading.end() : end]),
            )
        )
    return sections


def tidy_text(text: str) -> str:
    """Trim lines, shorten list markers, mark table columns, drop extra blanks.

    Layout mode pads table columns with long runs of spaces; they become
    " | " so a row like "Sábado | 09:00 às 13:00" stays readable.
    """
    lines = []
    for raw_line in text.splitlines():
        line = LIST_MARKER.sub(r"\1 ", raw_line.strip())
        lines.append(TABLE_GAP.sub(" | ", line))
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def keyword_stems(text: str) -> set[str]:
    """Return the stems of the meaningful words in a text."""
    return {
        word[:STEM_LENGTH]
        for word in normalize(text).split()
        if len(word) >= MIN_WORD_LENGTH and word not in STOPWORDS
    }


def score_section(section: PolicySection, query_stems: set[str]) -> int:
    """Score how well a section matches the query (0 means no match)."""
    title_hits = query_stems & keyword_stems(section.title)
    body_hits = query_stems & keyword_stems(section.text)
    synonyms = " ".join(TOPIC_SYNONYMS.get(section.number, ()))
    synonym_hits = query_stems & keyword_stems(synonyms)
    return (
        TITLE_WEIGHT * len(title_hits)
        + SYNONYM_WEIGHT * len(synonym_hits)
        + BODY_WEIGHT * len(body_hits)
    )


def search_policy_sections(
    sections: list[PolicySection], query: str, limit: int = MAX_POLICY_RESULTS
) -> list[PolicySection]:
    """Return the best matching sections, best first (empty if none match).

    A runner-up is only included if it scores at least half as much as the
    best section, so a clear question gets a single focused answer.
    """
    query_stems = keyword_stems(query)
    scored = [(score_section(section, query_stems), section) for section in sections]
    matches = [item for item in scored if item[0] > 0]
    matches.sort(key=lambda item: item[0], reverse=True)
    if not matches:
        return []
    best_score = matches[0][0]
    return [section for score, section in matches[:limit] if score * 2 >= best_score]
