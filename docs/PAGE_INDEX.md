What's missing (the three new pieces)

  1. Pass 1 — Page Layout Extraction

  Right now you extract raw text. The upgrade is structured layout per page: blocks, tables, headers, paragraphs with spatial positioning. This is very feasible:

  - PyMuPDF already supports this via page.get_text("dict") — gives you blocks with font size, bold, position
  - For tables specifically, pdfplumber (already in your deps) has page.extract_tables() which returns structured table data
  - For complex layouts, you could optionally render page images and use vision models (pdf_get_page_image already exists)

  The output per page would look something like:
  {
    "page": 42,
    "layout": {
      "headers": ["Section 6.01 Financial Covenants"],
      "paragraphs": ["The Borrower shall maintain..."],
      "tables": [{"rows": [...], "caption": "..."}],
      "footnotes": ["..."]
    }
  }

  2. Pass 2 — Keyword/Term Index (the back-of-the-book index)

  This is the biggest new piece, but very doable:

  - Option A (no LLM cost): Use NLP keyword extraction (RAKE, YAKE, or simple TF-IDF) on extracted text. These libraries identify domain terms like "Leverage Ratio", "EBITDA", "Material Adverse Effect" purely from
  frequency/statistical patterns. Then build an inverted index: term → [page_numbers]
  - Option B (LLM-assisted, better quality): Send page chunks to the LLM asking "extract key financial/legal terms from this text." More expensive but catches domain nuance
  - Option C (hybrid, recommended): Use NLP for candidate extraction, then one LLM pass to filter/normalize/group synonyms (e.g., "Total Leverage Ratio" and "Leverage Ratio" map to same concept)

  The index structure:
  {
    "keywords": {
      "leverage ratio": {"pages": [42, 43, 67, 89], "sections": ["node_12", "node_34"]},
      "EBITDA": {"pages": [5, 42, 43, 44, 67], "sections": ["node_3", "node_12"]},
      "covenant": {"pages": [42, 43, 44, 45, 46], "sections": ["node_12"]},
      ...
    }
  }

  3. Tool Layer — Agent navigates the index

  Expose tools over the pre-processed index. The agent (LLM) decides which tool to call — this is the key to keeping it non-rule-based:
  ┌───────────────────────────────────┬──────────────────────────┬───────────────────────────────────────────┐
  │               Tool                │          Input           │                  Output                   │
  ├───────────────────────────────────┼──────────────────────────┼───────────────────────────────────────────┤
  │ find_section(query)               │ "covenant"               │ Tree path + page range (partially exists) │
  ├───────────────────────────────────┼──────────────────────────┼───────────────────────────────────────────┤
  │ lookup_keyword(term)              │ "EBITDA"                 │ Pages + sections where it appears         │
  ├───────────────────────────────────┼──────────────────────────┼───────────────────────────────────────────┤
  │ get_subtree(node_id)              │ "node_12"                │ Children, page ranges, summaries          │
  ├───────────────────────────────────┼──────────────────────────┼───────────────────────────────────────────┤
  │ get_page_content(pages)           │ [42, 43]                 │ Full text/layout of those pages (exists)  │
  ├───────────────────────────────────┼──────────────────────────┼───────────────────────────────────────────┤
  │ search_in_section(node_id, query) │ node_12, "minimum ratio" │ Narrowed search within section            │
  ├───────────────────────────────────┼──────────────────────────┼───────────────────────────────────────────┤
  │ get_cross_references(node_id)     │ "node_12"                │ "as defined in Section 1.01" links        │
  └───────────────────────────────────┴──────────────────────────┴───────────────────────────────────────────┘
  How a query flows (e.g., "Find the covenants")

  Agent receives question: "What are the financial covenants?"
      │
      ├─ Tool call: find_section("financial covenant")
      │   → Returns: node_12 "ARTICLE VI - FINANCIAL COVENANTS", pages 42-56
      │
      ├─ Tool call: get_subtree("node_12")
      │   → Returns: Section 6.01 Leverage Ratio (p42-45)
      │              Section 6.02 Interest Coverage (p46-48)
      │              Section 6.03 Minimum Liquidity (p49-51)
      │
      ├─ Tool call: get_page_content([42, 43, 44, 45])
      │   → Returns: Full text of those 4 pages
      │
      └─ Agent reasons over 4 pages (not 600) → structured answer

  Why this works well

  1. Massive token savings: Agent sees the index (~2K tokens) instead of 600 pages. Then pulls only the 5-10 pages it needs. Your current max_pages_per_batch: 80 shrinks to the exact pages that matter.
  2. Non-rule-based: The LLM decides which tools to call and how to navigate. The index is the map; the LLM is the navigator. No hardcoded "if covenant → go to page 42" rules.
  3. Pre-processing cost is amortized: Index once per document, query many times. A 600-page credit agreement takes maybe 2-3 minutes to index (structure + keywords), then every subsequent extraction field
  benefits.
  4. Composable: The keyword index + section tree complement each other. Some queries match section titles ("financial covenants"). Others match keywords that span sections ("EBITDA" appears in definitions AND
  covenants).

  Challenges to watch for
  ┌─────────────────────────────────────────────────────────────────┬─────────────────────────────────────────────────────────────────────────────────────────────┐
  │                            Challenge                            │                                         Mitigation                                          │
  ├─────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Table extraction quality — covenants are often in tables        │ Use pdfplumber.extract_tables() in Pass 1; flag table-heavy pages for vision model fallback │
  ├─────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Cross-references — "as defined in Section 1.01"                 │ Pass 2 can extract cross-refs via regex + LLM, add edges to the tree                        │
  ├─────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Synonym resolution — "Total Leverage Ratio" vs "Leverage Ratio" │ LLM normalization pass on keyword candidates                                                │
  ├─────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Scanned/image PDFs — no extractable text                        │ OCR pass before indexing (you already have ocr_required flag on Document)                   │
  ├─────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Structure extraction noise — documents without bookmarks/TOC    │ Your 4-strategy fallback chain handles this well already                                    │
  └─────────────────────────────────────────────────────────────────┴─────────────────────────────────────────────────────────────────────────────────────────────┘
  Bottom line

  This is a strong, feasible architecture. The core insight — build a navigable index, then let the LLM agent navigate it with tools — is exactly the right pattern for large documents. You're not building a search
  engine; you're building a document map that an intelligent agent can read. And you've already built most of the map.
