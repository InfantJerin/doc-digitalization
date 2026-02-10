PageIndex Pre-Processing System — Implementation Plan                                         

 Context

 The current extraction pipeline feeds raw PDF text to the LLM agent. For large credit agreements (100-600 pages) and multi-document deals, this wastes tokens and reduces accuracy. The agent needs a navigable
 index — a map of the document(s) — so it can surgically retrieve only the pages that matter.

 The PageIndex system adds a pre-processing step that builds a rich, deal-spanning index before extraction runs. The LLM agent then navigates this index via tools rather than scanning full documents.

 ---
 Architecture

 Document arrives → Build per-doc index → Store in workspace/index/
                                               │
 All docs ready → Build deal-level index ──────┤
                                               │
 Extraction triggers → Agent navigates index via tools
                       → Pulls only relevant pages
                       → Reasons over focused context

 Two layers:
 - Per-document index: Structure tree + page layouts + keyword index
 - Deal-level index: Document registry + unified keywords + cross-document references

 Storage: JSON files in workspace ({workspace}/index/). Database stores only a pointer.

 ---
 Phase 1: Core Models + Storage

 New models in src/core/models.py

 Add after existing DocumentStructure class:
 ┌────────────────────────┬──────────────────────────────────────────────────────────────────────────────────────────────────────────────┬───────────────────────────────┐
 │         Model          │                                                    Fields                                                    │            Purpose            │
 ├────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────┤
 │ PageLayout             │ page_number, headers, paragraphs, tables, footnotes, images, word_count                                      │ Structured layout per page    │
 ├────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────┤
 │ KeywordEntry           │ term, canonical_term, pages, sections, term_type, definition_page                                            │ Inverted keyword index entry  │
 ├────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────┤
 │ CrossDocumentReference │ source_document_id, source_page, reference_text, target_document_id, target_node_id, target_page, confidence │ Edge linking docs             │
 ├────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────┤
 │ DocumentPageIndex      │ document_id, document_type, total_pages, structure, page_layouts, keyword_index                              │ Complete per-doc index        │
 ├────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────┤
 │ DealPageIndex          │ deal_id, document_registry, document_indexes, unified_keywords, cross_references                             │ Deal-spanning composite index │
 └────────────────────────┴──────────────────────────────────────────────────────────────────────────────────────────────────────────────┴───────────────────────────────┘
 All models follow the existing to_dict()/from_dict() pattern used by DocumentNode.

 New exceptions in src/core/exceptions.py

 - IndexingError(DocDigitalizationError) — Error during index construction
 - IndexNotFoundError(IndexingError) — Pre-built index not found

 New file: src/indexing/index_store.py

 JSON file I/O for index storage within workspace directories. Methods: save_document_index(), load_document_index(), save_deal_index(), load_deal_index(), has_document_index(), list_document_indexes(). Maintains
 an index_manifest.json for tracking.

 Modify: src/extraction/workspace.py

 Add index_dir: Path to ExtractionWorkspace dataclass. Create {root}/index/ directory in ExtractionWorkspaceManager.create().

 Workspace structure becomes:

 {extractions_root}/{run_id}/
     documents/
     artifacts/
     index/                          ← NEW
         index_manifest.json
         doc_index_{doc_id_1}.json
         doc_index_{doc_id_2}.json
         deal_index.json

 ---
 Phase 2: Page Layout Analyzer (Pass 1, No LLM)

 New file: src/indexing/page_layout_analyzer.py

 Class: PageLayoutAnalyzer
 Method: analyze_document(pdf_path) -> list[PageLayout]

 Per-page layout extraction using:
 - PyMuPDF get_text("dict") for blocks with font size/bold detection
 - pdfplumber extract_tables() for structured table data
 - Heuristics: median font size comparison for headers, page position for footnotes, regex for signatures

 No LLM calls. Pure computational extraction.

 ---
 Phase 3: Keyword Extraction (Pass 2a)

 New file: src/indexing/keyword_extractor.py

 Class: KeywordExtractor
 Method: async extract_keywords(page_layouts, structure) -> list[KeywordEntry]

 Hybrid approach:
 1. Regex candidates (no LLM): Defined terms ("Applicable Margin"), section references (Section 1.01), financial metrics (EBITDA, Leverage Ratio), entities
 2. Optional LLM normalization (configurable): Groups synonyms, normalizes domain terms
 3. Merge and deduplicate: By canonical term, capped at max_keywords
 4. Definition detection: Marks definition_page for terms found in Definitions section

 ---
 Phase 4: Per-Document Indexer

 New file: src/indexing/document_indexer.py

 Class: DocumentIndexer
 Method: async build_index(pdf_path, document_id, document_type) -> DocumentPageIndex

 Orchestrates the three passes:
 1. PageLayoutAnalyzer.analyze_document() — layout per page
 2. DocumentStructureExtractor.extract() — reuses existing 4-strategy extractor from src/extraction/structure_extractor.py
 3. KeywordExtractor.extract_keywords() — term extraction

 ---
 Phase 5: Cross-Reference Detection + Deal Indexer (Pass 2b)

 New file: src/indexing/cross_reference_detector.py

 Class: CrossReferenceDetector
 Method: async detect_cross_references(source_doc_id, source_index, all_indexes) -> list[CrossDocumentReference]

 Two phases:
 1. Regex candidates: Patterns like "as defined in Section X.Y of the Credit Agreement", "pursuant to Section X.Y", "in accordance with the [Document Name]"
 2. LLM resolution: Resolves candidates to target documents by providing doc summaries (types, sections) and asking the LLM to map each reference

 This handles cross-document references spanning the deal (e.g., compliance cert → credit agreement → financial statements).

 New file: src/indexing/deal_indexer.py

 Class: DealIndexer
 Method: async build_deal_index(deal_id, document_indexes) -> DealPageIndex

 Assembles the deal-level index:
 1. Build document registry (doc_id → doc_type)
 2. Merge per-document keyword indexes into unified index (preserving doc provenance)
 3. Run CrossReferenceDetector for each document pair
 4. Return DealPageIndex

 ---
 Phase 6: Navigation Tools

 New file: src/tools/index_tools.py

 Class: IndexTools — follows existing tool pattern (StructureTools, PDFTools)
 ┌─────────────────────────────────────┬─────────────────────┬─────────────────────────────────────────┬───────────────────────────────┐
 │             Tool Method             │        Input        │                 Output                  │            Purpose            │
 ├─────────────────────────────────────┼─────────────────────┼─────────────────────────────────────────┼───────────────────────────────┤
 │ find_section(query, doc_id?)        │ "covenant"          │ [{doc_id, node_id, title, path, pages}] │ Section lookup across docs    │
 ├─────────────────────────────────────┼─────────────────────┼─────────────────────────────────────────┼───────────────────────────────┤
 │ lookup_keyword(term)                │ "EBITDA"            │ [{term, pages, sections, type}]         │ Unified keyword search        │
 ├─────────────────────────────────────┼─────────────────────┼─────────────────────────────────────────┼───────────────────────────────┤
 │ find_term_across_docs(term)         │ "Leverage Ratio"    │ [{doc_id, doc_type, pages, sections}]   │ Cross-doc term search         │
 ├─────────────────────────────────────┼─────────────────────┼─────────────────────────────────────────┼───────────────────────────────┤
 │ get_definition(term)                │ "Applicable Margin" │ {term, doc_id, page, context}           │ Find formal definition        │
 ├─────────────────────────────────────┼─────────────────────┼─────────────────────────────────────────┼───────────────────────────────┤
 │ get_subtree(node_id, doc_id?)       │ "node_12"           │ {node with children}                    │ Drill into section tree       │
 ├─────────────────────────────────────┼─────────────────────┼─────────────────────────────────────────┼───────────────────────────────┤
 │ get_page_content(doc_id, pages)     │ doc_1, [42,43]      │ [{page layouts}]                        │ Retrieve specific pages       │
 ├─────────────────────────────────────┼─────────────────────┼─────────────────────────────────────────┼───────────────────────────────┤
 │ search_in_section(node_id, query)   │ node_12, "minimum"  │ [{page, context}]                       │ Search within section         │
 ├─────────────────────────────────────┼─────────────────────┼─────────────────────────────────────────┼───────────────────────────────┤
 │ resolve_reference(doc_id, page)     │ doc_2, 3            │ [{target_doc, target_section}]          │ Follow cross-doc ref          │
 ├─────────────────────────────────────┼─────────────────────┼─────────────────────────────────────────┼───────────────────────────────┤
 │ get_amendments_for_section(node_id) │ "node_12"           │ [{source_doc, ref_text}]                │ Check for amendments          │
 ├─────────────────────────────────────┼─────────────────────┼─────────────────────────────────────────┼───────────────────────────────┤
 │ get_index_summary()                 │ —                   │ {docs, keywords, cross_refs}            │ High-level summary for prompt │
 └─────────────────────────────────────┴─────────────────────┴─────────────────────────────────────────┴───────────────────────────────┘
 Update: src/tools/__init__.py

 Add IndexTools to exports.

 ---
 Phase 7: Pipeline Integration

 Modify: src/core/config_loader.py

 New config model:

 class PageIndexConfig(BaseModel):
     enabled: bool = True
     use_llm_keywords: bool = False
     detect_cross_references: bool = True
     max_keywords_per_doc: int = 500
     skip_layout_analysis: bool = False

 Add page_index: PageIndexConfig to ExtractionPipelineConfig.

 Update pipeline YAMLs:

 credit-agreement.yaml: page_index.enabled: true, use_llm_keywords: true, detect_cross_references: false
 covenant-compliance.yaml: page_index.enabled: true, use_llm_keywords: false, detect_cross_references: true

 Modify: src/core/settings.py

 Add: page_index_enabled: bool = True, page_index_max_build_time_seconds: int = 120

 Modify: src/extraction/service.py

 Add indexing step in run_extraction() between _download_documents() and orchestrator.run_extraction():

 document_paths = await self._download_documents(...)
 # NEW: Build PageIndex
 index_store = IndexStore(workspace.root)
 deal_index = await self._build_page_index(deal_id, document_ids, document_paths, index_store, config)
 # Pass index to orchestrator
 result = await self.orchestrator.run_extraction(..., deal_index=deal_index)

 New dependencies: DocumentIndexer, DealIndexer injected via __init__.

 Modify: src/agent/orchestrator.py

 - Add deal_index: Optional[DealPageIndex] = None parameter to run_extraction() and _run_hybrid()
 - New method _prepare_indexed_contexts() — builds DocumentContext from pre-built index (richer page_index with node IDs, levels, summaries, end pages)
 - Enhance _collect_relevant_snippets() — use section page ranges + keyword index for better page selection
 - Falls back to existing _prepare_document_contexts() when no index available

 Modify: src/agent/prompt_builder.py

 Add optional index_summary: dict parameter to build_extraction_prompt(). When present, includes:
 - List of available index navigation tools
 - Document summaries (types, page counts, top sections)
 - Top keywords and cross-reference count

 ---
 Phase 8: Testing

 Unit Tests (new files)
 ┌─────────────────────────────────────────────┬──────────────────────────────────────────────────────────────────────────┐
 │                  Test File                  │                                  Tests                                   │
 ├─────────────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤
 │ tests/unit/test_page_index_models.py        │ to_dict()/from_dict() roundtrip for all 5 new models                     │
 ├─────────────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤
 │ tests/unit/test_index_store.py              │ Save/load cycle using tmp_path fixture                                   │
 ├─────────────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤
 │ tests/unit/test_page_layout_analyzer.py     │ Layout extraction with synthetic PDFs (varying fonts, tables, footnotes) │
 ├─────────────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤
 │ tests/unit/test_keyword_extractor.py        │ Regex patterns against financial text, LLM mock for normalization        │
 ├─────────────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤
 │ tests/unit/test_cross_reference_detector.py │ Regex patterns against reference samples, LLM mock for resolution        │
 ├─────────────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤
 │ tests/unit/test_index_tools.py              │ Each tool method against pre-built DealPageIndex fixture                 │
 └─────────────────────────────────────────────┴──────────────────────────────────────────────────────────────────────────┘
 Integration Tests (new files)
 ┌─────────────────────────────────────────────────┬───────────────────────────────────────────────┐
 │                    Test File                    │                     Tests                     │
 ├─────────────────────────────────────────────────┼───────────────────────────────────────────────┤
 │ tests/integration/test_document_indexer.py      │ End-to-end per-doc indexing with mock LLM     │
 ├─────────────────────────────────────────────────┼───────────────────────────────────────────────┤
 │ tests/integration/test_deal_indexer.py          │ Multi-doc deal indexing with cross-references │
 ├─────────────────────────────────────────────────┼───────────────────────────────────────────────┤
 │ tests/integration/test_extraction_with_index.py │ Full extraction run with indexing enabled     │
 └─────────────────────────────────────────────────┴───────────────────────────────────────────────┘
 Smoke Test

 scripts/smoke_test_page_index.py — runs against resources/credit agreement/AbbieVie Term Loan Credit Agreement.pdf, builds index, prints summary, exercises each tool.

 ---
 Files Summary

 New files (10)
 ┌──────────────────────────────────────────┬────────────────────────────────────┐
 │                   File                   │              Purpose               │
 ├──────────────────────────────────────────┼────────────────────────────────────┤
 │ src/indexing/__init__.py                 │ Module init                        │
 ├──────────────────────────────────────────┼────────────────────────────────────┤
 │ src/indexing/page_layout_analyzer.py     │ Pass 1: per-page layout extraction │
 ├──────────────────────────────────────────┼────────────────────────────────────┤
 │ src/indexing/keyword_extractor.py        │ Pass 2a: keyword/term extraction   │
 ├──────────────────────────────────────────┼────────────────────────────────────┤
 │ src/indexing/cross_reference_detector.py │ Pass 2b: cross-document references │
 ├──────────────────────────────────────────┼────────────────────────────────────┤
 │ src/indexing/document_indexer.py         │ Per-document index orchestrator    │
 ├──────────────────────────────────────────┼────────────────────────────────────┤
 │ src/indexing/deal_indexer.py             │ Deal-level index assembler         │
 ├──────────────────────────────────────────┼────────────────────────────────────┤
 │ src/indexing/index_store.py              │ JSON file storage                  │
 ├──────────────────────────────────────────┼────────────────────────────────────┤
 │ src/tools/index_tools.py                 │ Navigation tools for agent         │
 ├──────────────────────────────────────────┼────────────────────────────────────┤
 │ scripts/smoke_test_page_index.py         │ End-to-end smoke test              │
 ├──────────────────────────────────────────┼────────────────────────────────────┤
 │ tests/unit/test_page_index_models.py     │ Unit tests                         │
 └──────────────────────────────────────────┴────────────────────────────────────┘
 Modified files (8)
 ┌──────────────────────────────────────────────────────┬──────────────────────────────────────────────────────┐
 │                         File                         │                        Change                        │
 ├──────────────────────────────────────────────────────┼──────────────────────────────────────────────────────┤
 │ src/core/models.py                                   │ Add 5 new dataclasses                                │
 ├──────────────────────────────────────────────────────┼──────────────────────────────────────────────────────┤
 │ src/core/exceptions.py                               │ Add IndexingError, IndexNotFoundError                │
 ├──────────────────────────────────────────────────────┼──────────────────────────────────────────────────────┤
 │ src/core/config_loader.py                            │ Add PageIndexConfig model                            │
 ├──────────────────────────────────────────────────────┼──────────────────────────────────────────────────────┤
 │ src/core/settings.py                                 │ Add page_index settings                              │
 ├──────────────────────────────────────────────────────┼──────────────────────────────────────────────────────┤
 │ src/extraction/workspace.py                          │ Add index_dir to workspace                           │
 ├──────────────────────────────────────────────────────┼──────────────────────────────────────────────────────┤
 │ src/extraction/service.py                            │ Add indexing step between download and orchestration │
 ├──────────────────────────────────────────────────────┼──────────────────────────────────────────────────────┤
 │ src/agent/orchestrator.py                            │ Accept DealPageIndex, use indexed contexts           │
 ├──────────────────────────────────────────────────────┼──────────────────────────────────────────────────────┤
 │ src/agent/prompt_builder.py                          │ Include index summary in agent prompt                │
 ├──────────────────────────────────────────────────────┼──────────────────────────────────────────────────────┤
 │ src/tools/__init__.py                                │ Export IndexTools                                    │
 ├──────────────────────────────────────────────────────┼──────────────────────────────────────────────────────┤
 │ config/pipelines/extraction/credit-agreement.yaml    │ Add page_index config                                │
 ├──────────────────────────────────────────────────────┼──────────────────────────────────────────────────────┤
 │ config/pipelines/extraction/covenant-compliance.yaml │ Add page_index config                                │
 └──────────────────────────────────────────────────────┴──────────────────────────────────────────────────────┘
 No new dependencies required

 PyMuPDF and pdfplumber already in pyproject.toml.

 ---
 Verification

 1. Unit tests: pytest tests/unit/test_page_index_models.py tests/unit/test_index_store.py tests/unit/test_page_layout_analyzer.py tests/unit/test_keyword_extractor.py tests/unit/test_cross_reference_detector.py
 tests/unit/test_index_tools.py -v
 2. Integration tests: pytest tests/integration/test_document_indexer.py tests/integration/test_deal_indexer.py tests/integration/test_extraction_with_index.py -v
 3. Smoke test: python scripts/smoke_test_page_index.py --document-path "resources/credit agreement/AbbieVie Term Loan Credit Agreement.pdf" --output ./page_index_output.json
 4. Backward compatibility: Existing tests pass unchanged — deal_index parameter is Optional everywhere, defaults to None, falls back to existing behavior