# Agentic AI frameworks for dynamic document intelligence in 2025–2026

**The best approach for a dynamic, goal-driven document extraction system isn't a single framework — it's a composable architecture combining LlamaIndex for document intelligence, PydanticAI for structured extraction, and a lightweight custom orchestrator following Anthropic's patterns.** No single framework fully satisfies all five requirements (high autonomy, dynamic workflows, multi-LLM, polyglot deployment, and 600+ page handling), but the ecosystem has matured enough that the right combination delivers production-ready results. The field is bifurcating: enterprise teams adopt heavyweight frameworks for governance, while technical teams building novel systems trend toward lightweight, composable code — and the evidence strongly favors the latter for this use case.

---

## The framework landscape has consolidated around five tiers

Fifteen frameworks were evaluated against the specific requirements of this document intelligence system. The research reveals a market that has matured significantly through 2025, with clear winners and notable casualties.

**Tier 1 — Production-proven at scale:** LangGraph (v1.0 GA, **400+ companies** in production, ~24K stars), LlamaIndex (~44K stars, purpose-built for document intelligence), and CrewAI (v1.9.3, **$18M Series A**, 100K+ agent executions/day). These three dominate community adoption and real-world deployments.

**Tier 2 — Strong and rapidly maturing:** PydanticAI (V1 since September 2025, **15M+ downloads**, best-in-class structured outputs), Agno (~37K stars, blazing performance at **5,000× faster instantiation** than LangGraph), and Microsoft Agent Framework (merging AutoGen + Semantic Kernel, enterprise Azure play).

**Tier 3 — Promising but early:** OpenAI Agents SDK (minimalist, dual Python/TypeScript), Google ADK (ambitious but "buggy and brittle" per independent testing), BeeAI (IBM/Linux Foundation backing, Docling integration), and Mastra (TypeScript-native, YC-backed).

**Tier 4 — Specialized/complementary:** DSPy (prompt optimization layer, not standalone), Anthropic's Claude patterns (architectural guidance + Agent SDK), HuggingFace Smolagents (minimalist code agents).

**Tier 5 — Deprecated or transitioning:** ControlFlow (archived August 2025), Semantic Kernel (maintenance mode, merging into Microsoft Agent Framework), AutoGen 0.2/AG2 (fragmenting ecosystem).

---

## How each framework handles the five core requirements

The user's requirements create a demanding filter. Here is how each viable framework performs against each axis, scored and analyzed from research evidence.

### Dynamic workflow construction — the critical differentiator

This is the most discriminating requirement because it directly contradicts how most frameworks work. The user explicitly rejects pre-defined static graphs.

**LangGraph** added the `Command` primitive enabling edgeless dynamic routing, but fundamentally still requires defining a `StateGraph` with nodes upfront. You can build a "dynamic plan-and-execute" meta-graph where the LLM generates plans and a loop executes them, but the skeleton is hardcoded. **The user's criticism remains valid** — it is "dynamic within a defined skeleton," not truly autonomous workflow generation. Community sentiment reinforces this: developers report "fighting the framework" and spending weeks understanding state management.

**CrewAI** comes closest to autonomous orchestration with its **planning agent + reasoning mode**. A manager agent dynamically creates step-by-step plans, delegates to worker agents, and adapts based on outcomes. The hierarchical process allows genuine goal-driven behavior. However, production teams report hitting a "low ceiling" after 3–6 months, requiring **50–80% rewrites** to migrate to more flexible alternatives.

**Anthropic's orchestrator-workers pattern** is inherently dynamic — a central LLM breaks tasks into subtasks at runtime, dispatches to specialized workers, and synthesizes results. No framework needed; this runs in pure Python with API calls. The Agent Skills specification (SKILL.md files) maps directly to the "skill instructions" concept, with progressive context loading and portable cross-platform skills.

**LlamaIndex AgentWorkflow** uses an event-driven architecture where each step emits typed events triggering subsequent steps. Supports branching, looping, and parallel execution. Multi-agent systems share a `Context` object for state. More flexible than graph definitions but still requires developer-defined event flows.

**PydanticAI** offers a beta Graph API with parallel execution and conditional branching, plus native durable execution via Temporal, Prefect, or DBOS. Agents autonomously decide tool usage and iterate. The key strength: **Pydantic-validated structured outputs with automatic retry on validation failure** — ideal for extraction tasks where output schemas are known.

**Google ADK** provides the best hybrid approach with `SequentialAgent`, `ParallelAgent`, and `LoopAgent` for deterministic pipelines alongside LLM-driven dynamic routing. However, independent testing found it "buggy" and "unclear abstractions" — not production-ready unless deeply embedded in Google's stack.

| Framework | Dynamic workflows | Skill instructions | Production evidence |
|-----------|------------------|-------------------|-------------------|
| Custom (Anthropic pattern) | ★★★★★ Full autonomy | ★★★★★ Agent Skills spec | ★★★★☆ Proven pattern |
| CrewAI | ★★★★☆ Planning agent | ★★★★☆ Role/task NL defs | ★★★☆☆ Ceiling concerns |
| LlamaIndex | ★★★★☆ Event-driven | ★★★☆☆ Developer-defined | ★★★★☆ ADW in production |
| PydanticAI | ★★★☆☆ Graph API (beta) | ★★★★★ Pydantic schemas | ★★★★☆ V1 stable |
| LangGraph | ★★☆☆☆ Graph skeleton required | ★★☆☆☆ Manual wiring | ★★★★★ 400+ companies |
| Google ADK | ★★★★☆ Hybrid routing | ★★★☆☆ Agent composition | ★★☆☆☆ Early/buggy |

### Long document handling — 600+ pages demands specialized tooling

For documents exceeding 600 pages, general-purpose agent frameworks are insufficient. The research reveals that **most production document intelligence deployments use specialized parsing tools** rather than relying on framework-native capabilities.

**LlamaIndex is the clear leader** for document processing. Its Agentic Document Workflows (ADW) architecture, introduced January 2025, combines **LlamaParse** (enterprise-grade document parser handling complex tables, hierarchical structures, and layouts), **LlamaExtract** (schema-based extraction with page citations and confidence scores), and **AgentWorkflow** for multi-agent coordination. Jeppesen (a Boeing company) reported saving **~2,000 engineering hours** using this framework. LlamaParse v2 launched in 2025 with up to **50% cost reduction**.

The optimal strategy for 600+ page documents uses **hierarchical processing**: build a document map first (section headers, page boundaries), create a multi-level index (document → sections → subsections → paragraphs), then dispatch section-specific extraction agents with isolated context windows. Anthropic's Claude Agent SDK specifically recommends this: "Subagents use their own isolated context windows, and only send relevant information back to the orchestrator."

**DSPy's `dspy.RLM` module** (Recursive Language Model) is particularly relevant — it explores large contexts through sandboxed Python REPL with recursive sub-LLM calls, designed for processing content that exceeds standard context windows.

For chunking, NVIDIA's 2024 benchmark found **page-level chunking** won with 0.648 accuracy across datasets. The emerging "agentic chunking" pattern has an AI agent evaluate document characteristics and **pick the right chunking method per section** — a research paper gets semantic chunking, a financial report gets page-level, a code file gets function-level splitting.

### Multi-LLM provider support

**PydanticAI** offers the broadest provider support: OpenAI, Anthropic, Gemini, DeepSeek, Grok, Cohere, Mistral, Perplexity, plus Azure AI Foundry, Amazon Bedrock, Vertex AI, Ollama, LiteLLM, Groq, OpenRouter, Together AI, Fireworks, and more. The OpenAI Agents SDK supports **100+ providers** via Chat Completions API compatibility. LangGraph inherits LangChain's extensive integrations. Google ADK uses LiteLLM for model-agnostic routing. **All major frameworks now support multi-provider LLM access** — this is no longer a meaningful differentiator.

### Polyglot deployment (Python + TypeScript)

This requirement eliminates several top contenders:

- **Both Python and TypeScript:** LangGraph, OpenAI Agents SDK, Google ADK (TypeScript added December 2025), BeeAI, Mastra (TypeScript-only), LlamaIndex Workflows
- **Python-only:** CrewAI, PydanticAI, Agno, DSPy
- **Python + .NET:** Microsoft Agent Framework, Semantic Kernel

For a Python + TypeScript requirement, **LangGraph**, **OpenAI Agents SDK**, and **Google ADK** are the strongest options. **BeeAI** offers full feature parity across both languages. However, the document processing ecosystem (LlamaParse, DSPy, most ML libraries) is overwhelmingly Python — the TypeScript requirement may be better served through API boundaries rather than framework-level polyglot support.

---

## Multi-agent architecture for document intelligence

Google's January 2026 publication defined **eight essential multi-agent design patterns**. For document intelligence, the research converges on a four-tier architecture combining several of these patterns:

**Tier 1 — Sequential pipeline (document processing):** Input document → Parser agent (LlamaParse/Docling) → Structure analyzer → Section indexer. This is deterministic and should use workflow agents, not LLM-driven routing.

**Tier 2 — Coordinator/dispatcher (dynamic task routing):** An orchestrator agent reads the skill instructions, interprets them, and dispatches extraction subtasks to specialized agents. This is where dynamic workflow construction happens. The orchestrator determines whether to process sections sequentially, in parallel, or with iteration based on document characteristics and instruction complexity.

**Tier 3 — Generator-critic (quality assurance):** Each extracted field passes through a validator agent that checks against the skill instruction's criteria, expected value ranges, and cross-references with other extracted fields. Low-confidence extractions loop back for refinement.

**Tier 4 — Human-in-the-loop (high-stakes decisions):** Extractions below a confidence threshold queue for human review. The system learns from corrections and improves skill instruction interpretation over time.

The critical insight from Anthropic's guidance: **"Start with 2–3 agents solving one specific problem; scale after proving value."** Separate content creation from validation (generator-critic pattern), and monitor token usage per agent with budgets to prevent runaway costs.

---

## Build custom vs. adopt a framework — the evidence favors a hybrid

Anthropic's influential December 2024 guide stated: **"The most successful implementations weren't using complex frameworks. They were building with simple, composable patterns."** They recommend starting with LLM APIs directly, noting that frameworks "create extra layers of abstraction that obscure underlying prompts and responses, making them harder to debug."

The practical tradeoffs break down as follows. A custom basic agent loop takes **1–2 weeks** to build. A framework-based prototype takes **1–3 days**. A production-grade custom system takes **4–8 weeks**. A production-grade framework system takes **3–6 weeks** but carries ongoing dependency risk — LangChain alone has had multiple API-breaking changes, and developers report documentation "changing entirely 3 times over."

For this use case, the evidence strongly supports a **hybrid approach**: use specialized libraries for what they're best at (LlamaIndex for document parsing, PydanticAI for structured extraction) while building lightweight custom orchestration for the dynamic workflow layer. This avoids framework lock-in while leveraging battle-tested components for the hard problems (document parsing, structured output validation, durable execution).

The Agent Skills specification (agentskills.io) provides an open standard for packaging skill instructions as portable, file-based skill packages with progressive disclosure — metadata loaded at startup (~100 tokens), full instructions on activation (<5,000 tokens), and scripts/references on demand. This maps directly to the user's "skill instructions" concept and works across Claude, Codex CLI, and other implementations.

---

## Cloud-native deployment for long-running document agents

The most significant infrastructure development for this use case is **AWS Lambda Durable Functions**, launched at re:Invent December 2025. These provide checkpoint-and-replay execution with two primitives: `context.step()` (automatic retries + checkpointing) and `context.wait()` (suspend without compute charges). Execution can **suspend for up to one year** with no charges during waits. Individual steps are limited to 15 minutes but async invocations support the full 1-year timeout. Community reaction was positive: "considerably simpler, less magical, and cheaper than Step Functions."

**Temporal** remains the industry standard for durable execution. PydanticAI natively integrates with Temporal, Prefect, and DBOS for fault-tolerant workflows. On GCP Cloud Run, Temporal requires disabling CPU throttling but delivers **73–78% faster execution** than Google Workflows with no cold starts, at ~$18–24/month for two always-on worker instances.

**Google ADK** offers `adk deploy cloud_run` for one-command deployment. **AWS AgentCore** provides 8-hour execution windows with built-in state persistence and A2A protocol support. **LangGraph Platform** offers purpose-built infrastructure with horizontal scaling, task queues, and Postgres checkpointing.

For a 600+ page document processing agent that may run for extended periods, the recommended patterns are: checkpoint/replay (Lambda Durable or Temporal) for the overall workflow, event-driven decomposition for breaking work into sub-tasks that fit within compute limits, and async processing with callbacks for human-in-the-loop steps.

---

## Framework-by-framework verdict for this use case

**LlamaIndex Workflows + AgentWorkflow** — ★★★★★ for document intelligence. Purpose-built ADW architecture with LlamaParse, LlamaExtract, and multi-agent coordination. Event-driven, async-first. Python and TypeScript support. The only framework where document intelligence is the primary design goal rather than an afterthought. Limitation: agent orchestration is "very little beyond basic workflows" per community feedback — needs pairing with a stronger orchestration layer for complex dynamic behavior.

**PydanticAI** — ★★★★★ for structured extraction. Pydantic-validated outputs with automatic retry guarantee schema compliance. Type-safe agent definitions match the skill instruction pattern perfectly. Broadest model provider support. Native durable execution (Temporal/Prefect/DBOS) handles 600+ page documents. Limitation: Python-only, no built-in RAG or document handling — needs pairing with document processing tools.

**Custom lightweight orchestrator (Anthropic patterns)** — ★★★★★ for dynamic workflows. The orchestrator-workers pattern with Agent Skills maps directly to the skill instructions concept. Full control, full debuggability, no framework risk. Claude's native PDF support, extended thinking, programmatic tool calling, and 200K token context windows are powerful for document processing. Limitation: requires more upfront engineering time.

**CrewAI** — ★★★★☆ for rapid prototyping. Planning agent + reasoning mode provides genuine goal-driven behavior. Fastest path from concept to working implementation. Limitation: Python-only, **reported "low ceiling"** with teams hitting limitations requiring 50–80% rewrites, not ideal for this complex use case long-term.

**BeeAI Framework** — ★★★★☆ for enterprise document processing. **Docling integration** specifically converts unstructured business documents into LLM-digestible format. ReAct architecture with reflection suits complex extraction where agents need to evaluate and retry. Full Python/TypeScript parity. Linux Foundation governance. Limitation: smaller community, less ecosystem breadth.

**OpenAI Agents SDK** — ★★★☆☆ for this use case. Clean, minimalist, dual Python/TypeScript. Good for simple multi-agent handoffs. Limitation: no built-in RAG, document handling, or workflow orchestration — you build everything yourself, at which point a custom solution with more document-specific tooling is preferable.

**LangGraph** — ★★★☆☆ for this use case. Most battle-tested in production (400+ companies), excellent debugging with LangSmith, lowest latency in benchmarks. But the user's existing criticism is valid: it requires defining graph skeletons upfront, and the learning curve is steep. Better suited for teams that want explicit control over every state transition than for dynamic, goal-driven systems.

**Google ADK** — ★★★☆☆ for this use case. Best hybrid of structured and dynamic workflows in theory. Multi-language support (Python, TypeScript, Java). First-class Google Cloud deployment. But independent testing found it "buggy, brittle, unclear abstractions" — not production-ready unless you're deeply committed to Google's ecosystem.

**Agno** — ★★★☆☆ for this use case. Built-in RAG with 20+ vector stores, blazing performance, learning capability for improving over time. But Python-only, no formal workflow orchestration, and dynamic workflows are less precisely controllable.

**DSPy** — ★★★☆☆ as a complementary layer. Signature-based approach maps naturally to skill instructions → structured output. GEPA optimizer achieved **91% accuracy** on tax form extraction with auto-optimized prompts. Not a standalone solution — pair with a document processing and orchestration layer.

**Microsoft Agent Framework** — ★★☆☆☆ for this use case. Enterprise-grade with Azure integration, but heavily Azure-centric, still in public preview (GA targeted Q1 2026), and the AutoGen/Semantic Kernel merger creates migration uncertainty.

**Mastra** — ★★☆☆☆ for this use case. Excellent if you're TypeScript-only, but Python's NLP/ML ecosystem is essential for serious document intelligence.

**ControlFlow** — ❌ Archived August 2025. Not viable for new projects.

---

## Recommended architecture for this document intelligence system

Based on all evidence gathered, the strongest architecture combines specialized components rather than relying on any single framework:

**1. Document processing layer — LlamaIndex.** Use LlamaParse for document parsing (handles complex tables, hierarchical structures, nested layouts). Build a hierarchical section index. Use LlamaExtract for schema-based field extraction with confidence scores and page citations. This handles the 600+ page requirement with proven, production-tested tooling.

**2. Structured extraction layer — PydanticAI.** Define each extraction skill as a PydanticAI agent with typed dependencies and Pydantic output models. The automatic retry on validation failure ensures schema compliance. Durable execution via Temporal handles long-running extractions gracefully. The type-safe dependency injection system cleanly manages document context per extraction task.

**3. Dynamic orchestration layer — Custom, following Anthropic's patterns.** Build a lightweight orchestrator-workers system where a planner agent interprets natural language skill instructions, decomposes them into extraction subtasks, and dispatches to specialized PydanticAI extractor agents. Use the Agent Skills specification (SKILL.md) for packaging skill instructions as portable, progressively-loaded context. This gives full dynamic workflow construction without framework constraints.

**4. Optimization layer (optional) — DSPy.** Apply DSPy's GEPA or MIPROv2 optimizers to automatically tune extraction prompts against labeled examples. This can yield **20%+ accuracy improvements** on extraction tasks. Requires labeled training data but pays dividends at scale.

**5. Deployment — AWS Lambda Durable Functions or Temporal on Cloud Run.** Checkpoint-and-replay execution ensures long-running document processing survives failures. Lambda Durable Functions are simpler and cheaper; Temporal is more mature and portable.

This architecture satisfies all five requirements: high autonomy (orchestrator-workers with LLM-driven planning), dynamic workflows (no pre-defined graphs), multi-LLM (PydanticAI's broad provider support), polyglot deployment (LlamaIndex and the orchestrator expose APIs consumable from TypeScript), and long document handling (LlamaParse + hierarchical processing + durable execution).

## Conclusion

The agentic AI framework market in 2025–2026 has reached a critical inflection point. Gartner predicts **40% of enterprise applications will embed AI agents by end of 2026**, up from under 5% in 2025. Multi-agent systems are the dominant architectural pattern, and standardized protocols (MCP for tools, A2A for agent communication) are enabling interoperability across frameworks.

For this specific document intelligence use case, three insights emerged that weren't obvious at the outset. First, **no single framework solves the full problem** — the best architectures are composable stacks, not monolithic framework adoptions. Second, **the "skill instructions" pattern has an emerging open standard** in the Agent Skills specification, which should be adopted rather than invented from scratch. Third, the dynamic workflow requirement actually argues *against* most frameworks — the most genuinely dynamic orchestration comes from lightweight custom code where an LLM interprets instructions and dispatches work, not from frameworks that impose graph structures.

The recommended stack — LlamaIndex for documents, PydanticAI for extraction, custom orchestration for dynamics, DSPy for optimization — represents a pragmatic middle ground: leveraging proven specialized tools while maintaining full control over the system's most critical component: how it interprets and executes human-written instructions.