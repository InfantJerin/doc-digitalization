Why this matters for credit agreements                                                                                                                                                                              
   
  Credit agreements are inherently multi-document. A single deal typically has:                                                                                                                                       
                                         
  - The Credit Agreement itself (defines terms, covenants, conditions)
  - Compliance Certificates (references covenant definitions from the agreement)
  - Financial Statements (referenced by the compliance certificate for actuals)
  - Amendments/Side Letters (override specific sections of the agreement)
  - Schedules/Exhibits (sometimes separate PDFs, referenced by section)

  These documents form a web of references. A compliance certificate might say "Consolidated EBITDA (as defined in Section 1.01 of the Credit Agreement)" — and your agent needs to follow that link to understand
  what "Consolidated EBITDA" actually means, including all the add-backs and exclusions defined 400 pages away in a different document.

  What this means for the index architecture

  Instead of one flat index per document, you need two layers:

  Deal-Level Index (unified)
  ├── Document Registry
  │   ├── doc_1: Credit Agreement (600 pages)
  │   ├── doc_2: Compliance Certificate (12 pages)
  │   └── doc_3: Q3 Financial Statements (45 pages)
  │
  ├── Unified Keyword Index
  │   └── "Consolidated EBITDA"
  │       ├── doc_1 → pages [5, 42, 67]  (definition + usage)
  │       ├── doc_2 → pages [3, 4]       (calculated value)
  │       └── doc_3 → pages [8, 12]      (actuals)
  │
  ├── Cross-Document References (edges)
  │   ├── doc_2:page_3 → doc_1:node_12  "as defined in Section 1.01"
  │   ├── doc_2:page_4 → doc_3:page_8   "per Financial Statements"
  │   └── doc_1:node_45 → doc_1:node_3  "defined in Article I" (intra-doc)
  │
  └── Per-Document Indexes
      ├── doc_1: { structure_tree, keyword_index, page_layouts }
      ├── doc_2: { structure_tree, keyword_index, page_layouts }
      └── doc_3: { structure_tree, keyword_index, page_layouts }

  The cross-document references are the key new concept. Each reference is an edge:

  {
    "source": {"document_id": "doc_2", "page": 3, "text": "Consolidated EBITDA (as defined in Section 1.01 of the Credit Agreement)"},
    "target": {"document_id": "doc_1", "node_id": "node_5", "section": "Section 1.01 Defined Terms"},
    "reference_type": "definition",
    "confidence": 0.95
  }

  How the agent uses this

  The tool layer gains cross-document navigation:
  ┌───────────────────────────────────────────┬────────────────────────────────────────────────────────────────────────────────────┐
  │                   Tool                    │                                    What it does                                    │
  ├───────────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────┤
  │ resolve_reference(doc_id, page, ref_text) │ Follows a cross-doc reference to its target                                        │
  ├───────────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────┤
  │ find_term_across_docs(term)               │ Returns all occurrences across the deal                                            │
  ├───────────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────┤
  │ get_definition(term)                      │ Finds where the term is defined (usually the Credit Agreement), not just mentioned │
  ├───────────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────┤
  │ get_amendments_for_section(node_id)       │ Checks if any amendment overrides this section                                     │
  └───────────────────────────────────────────┴────────────────────────────────────────────────────────────────────────────────────┘
  A real query flow for "What is the current Leverage Ratio covenant?":

  Agent: find_section("leverage ratio")
    → doc_1, node_12: "Section 6.01 Maximum Leverage Ratio", pages 42-45

  Agent: get_page_content(doc_1, [42, 43])
    → "...shall not permit the Leverage Ratio (as defined in Section 1.01)
       to exceed 4.50:1.00..."

  Agent: resolve_reference(doc_1, 42, "as defined in Section 1.01")
    → doc_1, node_5, page 28: definition of Leverage Ratio
    → "Total Funded Debt / Consolidated EBITDA (see Compliance Certificate)"

  Agent: find_term_across_docs("Leverage Ratio")
    → doc_2, page 3: actual calculated value = 3.21:1.00
    → doc_3, page 8: underlying financials

  Agent: get_amendments_for_section(node_12)
    → None (no amendments modify this section)

  → Agent now has: definition + threshold + actual value + source financials

  The agent traversed three documents and pulled maybe 8 pages total out of 657 combined pages.

  Extraction of cross-document references

  This is the part that needs to be LLM-driven (not rule-based), because the reference patterns vary wildly:

  - "as defined in Section 1.01 of the Credit Agreement" (explicit)
  - "per the Financial Statements delivered pursuant to Section 5.01" (indirect)
  - "see Exhibit A" (could be same doc or separate PDF)
  - "in accordance with the terms of the First Amendment" (document name reference)

  During Pass 2, for each document you'd ask the LLM: "Identify all references to other documents or sections in this text. For each, tell me what document/section is being referenced and why." The LLM handles the
  variety; your code just stores the edges.

  Fits cleanly with your existing architecture

  Your Deal model already groups documents. The cross_validate extraction strategy already reconciles across documents. The pipeline config already lists document_types. This is a natural extension — you're just
  making the cross-document relationships explicit and navigable rather than implicit.

  The one design decision worth thinking about: when do you build the deal-level index? Two options:

  - Eager: Build per-document indexes as each document arrives, then merge into the deal-level index when all required documents are present
  - Lazy: Build the full deal-level index at extraction time, when the pipeline triggers

  Eager is better for your workflow — documents arrive at different times, and you want the index ready when the analyst triggers extraction.

