"""
score_module3_extraction.py
------------------------------------------------
Phase-1 eval harness for Module 3 rule extraction accuracy, scored against
eval_gold_code_9_8_stairs.py (hand-annotated ground truth for CODE 9.8.2-9.8.4.7,
data/uploads/..._pdf_stairs_mock.pdf).

Mirrors score_module1b.py's style (plain script, print()-based, no pytest).

Runs the REAL PDF through the REAL extraction primitives — not a hand-typed
stand-in — so results reflect what actually happens today, not a best case.

  PART A - structural diagnostics (free, no API key, always runs):
    A1. Heading detection   - does SectionChunker recognise CODE numbering in
                               the text the live document-upload flow actually
                               stores (pypdf), vs. the Docling markdown path?
    A2. sendable-chunk prep - replicate rule_extraction_service.py's chunk
                               pipeline (SectionChunker -> generic fallback ->
                               KeywordFilter -> DependencyParser ->
                               ConfidenceScorer) on the REAL live-path text.
    A3. SKIP leakage        - does the confidence scorer drop gold-bearing
                               text before the LLM ever sees it?
    A4. Table pipeline      - does TableRuleBuilder work on Docling's tables,
                               and does the live route ever call it?
    A5. Regex baseline      - free-extractor recall/precision vs gold, on the
                               real sendable chunks from A2.

  PART B - LLM accuracy (needs OPENAI_API_KEY / GEMINI_API_KEY; skipped with
    instructions if absent):
    Runs LiteLLMRuleExtractor over the same real sendable chunks from A2 and
    scores per-field precision/recall + property-name grounding against gold.

Usage:
    uv run python score_module3_extraction.py
"""

import asyncio
import glob
import os
import sys

from eval_gold_code_9_8_stairs import EXCLUDED_CLAUSES, GOLD_RULES

sys.path.insert(0, "app/modules")

from module1_doc_parser import Module1_DocReader  # noqa: E402
from module1_doc_parser.docling_extractor import DoclingExtractor  # noqa: E402
from module1_doc_parser.section_chunker import SectionChunker  # noqa: E402
from module1_doc_parser.keyword_filter import KeywordFilter  # noqa: E402
from module1_doc_parser.dependency_parser import DependencyParser  # noqa: E402
from module1_doc_parser.confidence_scorer import ConfidenceScorer  # noqa: E402
from module1_doc_parser.table_rule_builder import TableRuleBuilder  # noqa: E402
from module3_rule_builder.regex_rule_converter import RegexRuleConverter  # noqa: E402
from module2_ifc_read import _PROPERTY_ALIASES  # noqa: E402

PDF_PATH = glob.glob("data/uploads/*pdf_stairs_mock.pdf")[0]

# ── Property-name equivalence (mirrors module2_ifc_read's alias table) ──────
_ALIAS_GROUPS: list[set[str]] = [{canon, *aliases} for canon, aliases in _PROPERTY_ALIASES.items()]


def _same_property(a: str, b: str) -> bool:
    if not a or not b:
        return False
    a, b = a.strip().lower(), b.strip().lower()
    if a == b:
        return True
    return any(a in {g.lower() for g in grp} and b in {g.lower() for g in grp} for grp in _ALIAS_GROUPS)


def _num_close(a, b, tol=0.5) -> bool:
    if a is None or b is None:
        return a is None and b is None
    try:
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return False


def _extracted_value(rule: dict):
    return rule.get("value") if rule.get("value") is not None else rule.get("check_value")


def match_gold_to_extracted(gold: dict, extracted: list[dict]) -> dict | None:
    for rule in extracted:
        if str(rule.get("target", "")).strip().lower() != gold["target"].lower():
            continue
        if not _same_property(str(rule.get("property_name", "")), gold["property_name"]):
            continue
        if "value_min_property" in gold:
            if rule.get("value_min_property") or rule.get("value_max_property"):
                return rule
            continue
        if gold["operator"] == "between":
            if _num_close(rule.get("value_min"), gold.get("value_min")) and _num_close(
                rule.get("value_max"), gold.get("value_max")
            ):
                return rule
        else:
            if _num_close(_extracted_value(rule), gold.get("value")):
                return rule
    return None


def _score(label: str, extracted: list[dict]):
    hits, misses = [], []
    for gold in GOLD_RULES:
        (hits if match_gold_to_extracted(gold, extracted) else misses).append(gold)
    recall = len(hits) / len(GOLD_RULES) if GOLD_RULES else 0.0
    print(f"\n     {label}: {len(hits)}/{len(GOLD_RULES)} gold rules recovered "
          f"({recall:.0%} recall), {len(extracted)} rules extracted total")
    if misses:
        print("     missed:")
        for g in misses:
            print(f"       - {g['ref']:30s} {g['desc'][:65]}")


def prepare_sendable_chunks(text: str) -> list[dict]:
    """Replicates rule_extraction_service.py's steps 3-7 (deterministic part,
    BERT/Module1b omitted — no fine-tuned model on disk / annotation-only)."""
    code_chunks = SectionChunker().chunk(text)
    if code_chunks:
        chunks_to_process = code_chunks
    else:
        generic = Module1_DocReader().extract_text_sections(text)
        chunks_to_process = [
            {"section_number": str(i + 1), "section_name": f"Section {i + 1}",
             "text": t, "char_count": len(t)}
            for i, t in enumerate(generic)
        ]

    filtered = KeywordFilter().score_chunks(chunks_to_process)
    dep = DependencyParser().analyse_chunks(filtered)
    final = ConfidenceScorer().combine(filtered_chunks=filtered, dep_chunks=dep, bert_chunks=None)
    return [c for c in final if c.get("filtered_text", "").strip()]


# ══════════════════════════════════════════════════════════════════════════
# PART A
# ══════════════════════════════════════════════════════════════════════════

def part_a():
    print("=" * 70)
    print("  PART A - structural diagnostics (no LLM, no API key)")
    print("=" * 70)

    pdf_bytes = open(PDF_PATH, "rb").read()
    pypdf_text = Module1_DocReader().parse_pdf(pdf_bytes)
    docling_text, docling_tables = DoclingExtractor().extract(PDF_PATH)

    # ── A1: heading detection gap ────────────────────────────────────────
    print("\n[A1] SectionChunker heading detection — live path (pypdf) vs Docling path")
    chunks_pypdf = SectionChunker().chunk(pypdf_text)
    chunks_docling = SectionChunker().chunk(docling_text)
    print(f"     pypdf-extracted text   (what document-upload stores as extracted_text): "
          f"{len(chunks_pypdf)} sections detected")
    print(f"     Docling-extracted text (only used by the parallel-race extract_rules(bytes) path): "
          f"{len(chunks_docling)} sections detected")
    if len(chunks_pypdf) == 0 and len(chunks_docling) > 0:
        print("     -> CONFIRMED: the live document-upload -> extract-rules flow stores pypdf text,")
        print("        whose CODE headings ('9.8.2.  Stair Dimensions') match none of SectionChunker's")
        print("        3 heading patterns (needs markdown '#', a bare top-level digit+space, or the")
        print("        literal word 'SECTION'/'CHAPTER'/'PART'). It silently falls back to the")
        print("        generic size-bounded chunker, losing real section_number/section_name context.")

    # ── A2: build the real sendable chunks (live path) ──────────────────
    print("\n[A2] Building sendable chunks exactly as rule_extraction_service.py does, "
          "on the REAL live-path text (pypdf)")
    sendable = prepare_sendable_chunks(pypdf_text)
    total_send = sum(c.get("count_send", 0) for c in sendable) or len(sendable)
    print(f"     {len(sendable)} chunk(s) with non-empty filtered_text reaching the LLM stage")

    # ── A3: SKIP leakage ──────────────────────────────────────────────────
    print("\n[A3] Confidence-scorer SKIP check — does filtering drop gold-bearing text?")
    sent_all = " ".join(c.get("filtered_text", "") for c in sendable)
    full_all = pypdf_text
    leaked = 0
    for gold in GOLD_RULES:
        needles = []
        for key in ("value", "value_min", "value_max"):
            v = gold.get(key)
            if v is not None:
                needles.append(str(int(v)) if float(v).is_integer() else str(v))
        if not needles:
            continue
        norm = lambda s: s.replace(",", " ")
        in_full = any(n in norm(full_all) for n in needles)
        in_sent = any(n in norm(sent_all) for n in needles)
        if in_full and not in_sent:
            leaked += 1
            print(f"     DROPPED before LLM: {gold['ref']:30s} ({gold['desc'][:60]})")
    if leaked == 0:
        print("     none — all gold clauses' numbers survive into filtered_text")
    else:
        print(f"     {leaked}/{len(GOLD_RULES)} gold rules had their source text filtered out "
              f"by the spaCy confidence scorer before the LLM ever saw them")

    # ── A4: table pipeline ────────────────────────────────────────────────
    print("\n[A4] Table pipeline — TableRuleBuilder vs live route")
    table_gold = [g for g in GOLD_RULES if g["ref"].startswith("Table ")]
    print(f"     Docling found {len(docling_tables)} table(s) in the source PDF")
    table_rules = TableRuleBuilder().extract_all_as_dicts(docling_tables)
    print(f"     TableRuleBuilder produced {len(table_rules)} rule(s) from those tables")
    found = sum(1 for g in table_gold if match_gold_to_extracted(g, table_rules))
    print(f"     matched {found}/{len(table_gold)} Table 9.8.4.1 gold rules "
          f"when TableRuleBuilder IS invoked directly on Docling's tables")
    print("\n     BUT app/services/rule_extraction_service.py's extract_rules_from_text() —")
    print("     the method app/routes/library.py:786 calls for the document-upload -> extract")
    print("     UI flow — always passes table_rules=[] and never invokes TableRuleBuilder.")
    print(f"     -> structurally, all {len(table_gold)} Table-9.8.4.1-sourced gold rules above")
    print("        can NEVER be produced by that code path, regardless of LLM quality.")

    # ── A5: regex baseline on the REAL sendable chunks ───────────────────
    print("\n[A5] Regex converter (free baseline) vs GOLD_RULES, on the real live-path chunks")
    regex_rules = []
    for chunk in sendable:
        regex_rules.extend(RegexRuleConverter().extract_rules(chunk))
    print(f"     RegexRuleConverter produced {len(regex_rules)} rule(s) total")
    _score("Regex converter (live-path chunks)", regex_rules)

    return sendable


# ══════════════════════════════════════════════════════════════════════════
# PART B
# ══════════════════════════════════════════════════════════════════════════

async def part_b(sendable: list[dict]):
    print("\n" + "=" * 70)
    print("  PART B - LLM extraction accuracy (needs an API key)")
    print("=" * 70)

    model = os.getenv("BIM_GUARD_RULE_MODEL", "gpt-4o-mini")
    key_present = bool(os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY"))
    if not key_present:
        print(f"\n     SKIPPED — no OPENAI_API_KEY/GEMINI_API_KEY in the environment.")
        print(f"     Live app default model is {model!r}. To run this part:")
        print(f"       set OPENAI_API_KEY=sk-...   (PowerShell: $env:OPENAI_API_KEY = 'sk-...')")
        print(f"       uv run python score_module3_extraction.py")
        return

    from app.services.rule_extractor import LiteLLMRuleExtractor
    from app.services.llm_client import LiteLLMClient

    extractor = LiteLLMRuleExtractor(client=LiteLLMClient(model=model))
    llm_rules = []
    for idx, chunk in enumerate(sendable, start=1):
        rules = await extractor.extract_rules_from_text(
            chunk["filtered_text"], chunk_index=idx, total_chunks=len(sendable)
        )
        llm_rules.extend(rules)

    print(f"\n     model={model}  chunks_sent={len(sendable)}  rules_returned={len(llm_rules)}")
    _score(f"LiteLLMRuleExtractor ({model}) — live-path chunks", llm_rules)

    canonical = {c.lower() for group in _ALIAS_GROUPS for c in group}
    unresolvable = [r for r in llm_rules if str(r.get("property_name", "")).lower() not in canonical]
    print(f"\n     property_name grounding: {len(llm_rules) - len(unresolvable)}/{len(llm_rules)} "
          f"extracted property names are in module2_ifc_read's known vocabulary")
    if unresolvable:
        seen = sorted({r.get("property_name") for r in unresolvable})
        print(f"     unresolvable property_names seen: {seen}")


# ══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print(f"GOLD_RULES: {len(GOLD_RULES)}   EXCLUDED_CLAUSES: {len(EXCLUDED_CLAUSES)}")
    print(f"Source PDF: {PDF_PATH}\n")
    sendable_chunks = part_a()
    asyncio.run(part_b(sendable_chunks))
