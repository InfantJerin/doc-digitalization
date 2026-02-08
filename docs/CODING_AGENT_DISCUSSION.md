what about pi-agent, do you think that can be thought as the solution to my problem? if ever I have to make use of that, how do I use it to solve my problem?

6:16 PM
Good question — let me research Pi-Agent specifically to see what it offers and how it might fit your use case.


Searched the web


Now I have a clear picture. Let me give you an honest assessment.

Short answer: Pi is not the right solution for your problem, but some of its architectural ideas are worth borrowing.

Here's why:

What Pi actually is. Pi is an AI coding agent built by Mario Zechner — creator of the libGDX game framework — with exactly four tools (read, write, edit, bash), a system prompt under 1,000 tokens, and a philosophy that what you leave out matters more than what you put in. 
Medium
 It became the engine behind OpenClaw, which went viral with 145K+ GitHub stars. It's written in TypeScript and lives in a monorepo (badlogic/pi-mono).

Pi's core packages are: pi-ai (a unified LLM API with multi-provider support — Anthropic, OpenAI, Google, xAI, Groq, Cerebras, OpenRouter), pi-agent-core (an agent loop that handles tool execution, validation, and event streaming), pi-tui (a terminal UI framework), and pi-coding-agent (the CLI that wires it all together). 
Mariozechner

Why it doesn't fit your use case:

Pi is purpose-built for interactive coding assistance — a human sits at a terminal, asks a coding question, the agent reads/writes/edits files and runs bash commands. Your use case is fundamentally different: you need a programmatic, headless document intelligence pipeline that interprets skill instructions, processes 600+ page documents, extracts structured fields, and runs autonomously in a cloud-native backend.

Specifically, the misalignment comes in several areas. First, Pi's four tools (read, write, edit, bash) are file-system-centric coding tools. You need tools for document parsing, section navigation, keyword matching, structured extraction with confidence scoring, and schema validation. Second, Pi deliberately skips sub-agents, plan mode, and built-in orchestration 
Shittycodingagent
 — the exact capabilities you need for dynamically dispatching extraction tasks across a 600-page document. Third, Pi is designed for interactive terminal sessions with a human in the loop, not headless batch processing of documents at scale on Cloud Run or Lambda. Fourth, Pi has no built-in concept of structured output validation (like Pydantic models) — critical for your field extraction use case where you need guaranteed schema compliance.

What you could borrow from Pi's architecture:

Pi does have some genuinely clever ideas that align with your needs:

Skills as progressive context loading. Pi's skills are "capability packages with instructions and tools, loaded on-demand" with "progressive disclosure without busting the prompt cache." 
Shittycodingagent
 This maps directly to your "skill instructions" concept. You could adopt this same pattern — package each extraction instruction as a skill file (markdown with instructions + tool definitions) that gets loaded only when needed, keeping context windows lean.

AGENTS.md for project-level configuration. Pi loads project instructions from AGENTS.md files at startup from multiple directories. 
Shittycodingagent
 You could use a similar pattern where each document type or extraction task has its own instruction file that configures agent behavior.

Sessions as trees. Armin Ronacher highlighted that Pi's session branching is "incredibly powerful" — you can branch a conversation, do a "side-quest" exploration, and rewind. 
Armin Ronacher
 For document extraction, this could be useful: if the agent tries one extraction path and it fails, it branches to an alternative approach without polluting the main extraction context.

SDK embedding mode. Pi runs in four modes including "an SDK for embedding in your own apps." 
npm
 So pi-agent-core could theoretically be embedded in a backend service. But you'd be fighting against its coding-agent DNA the entire time.

If you still wanted to force-fit Pi, here's how it would look:

You'd use @mariozechner/pi-agent-core as the agent loop engine. You'd write custom extensions that replace the default coding tools with document-processing tools (PDF parser, section navigator, keyword searcher, field extractor). You'd write your skill instructions as Pi skill files. You'd use the SDK mode to embed it in a FastAPI or Express service. You'd spawn multiple Pi instances (via the RPC protocol) for parallel extraction of different fields.

But here's the problem: by the time you've replaced the tools, written the extensions, removed the TUI, and added structured output validation — you've essentially built a custom agent framework that happens to use Pi's agent loop. And that loop is ~50 lines of straightforward code. The core loop is intentionally minimal: stream LLM response → check for tool calls → execute tools → add results to context → repeat until done. 
Medium
 You can write this yourself in an afternoon.

My recommendation stays the same: For your use case, the composable stack I outlined earlier (LlamaIndex for document intelligence + PydanticAI for structured extraction + lightweight custom orchestration) is a much better fit. Pi's genius is in being the perfect minimal coding agent — but that's a different problem than what you're solving. Take inspiration from its skills system and progressive context loading, but build your orchestration layer with tools designed for document intelligence from the ground up.

https://claude.com/blog/building-agents-with-skills-equipping-agents-for-specialized-work if you read this link that I have provided and validate this along with our PI agent loop, so somewhere, it looks like we can have this coding agent interface for solving any of the domain-specific problems. So even for our 600-page credit agreement extractions, we can think about using this pattern of using Bash and Python to search the relevant information and available tools for us to provide some of the metadata of the document and then holistically identify the information required for us to get the right value of the field. Now, it makes sense for me to think everything as a kind of coding agent with the skills on top of that. And that coding agent can scale for different types of domain problems, specific domain problems.

9:27 PM
That's a really compelling insight — let me read that Anthropic article to validate your thinking properly.


Searched the web


You've had a genuinely important insight here, and the Anthropic blog post validates it powerfully. Let me articulate why your thinking is correct and what it means for your architecture.

You're right. The paradigm has shifted. "Code is the interface, skills are the expertise."

The key passage from Anthropic's blog is this: "We used to think agents in different domains would look very different. A coding agent, a research agent, one for finance, one for marketing—each seemed to need its own tools and scaffolding. But as models improved in intelligence and agent capabilities progressed, we converged on a different approach." 
Claude
 They came to see code less as just a use case and more as an interface for agents to do almost any digital work. Claude Code is a coding agent, but also a general-purpose agent that happens to work through code. 
Claude

This is exactly what you're converging on. The insight is: you don't need a "document intelligence agent" — you need a coding agent with document intelligence skills.

Here's why this works specifically for your 600-page credit agreement extraction use case, and why the Pi agent loop pattern (or any minimal coding agent loop) becomes the right foundation:

The coding agent already has the primitives you need. Think about what you actually need to do with a 600-page credit agreement: read it (bash: pdftotext, Python's pdfplumber, PyMuPDF), search for sections (bash: grep, ripgrep, Python regex), navigate structure (Python script that parses ToC and builds a page map), extract specific fields (Python function that takes a section and returns structured data), validate results (Python with Pydantic models), and output structured JSON. All of these are just code execution. The four basic tools — read, write, edit, bash — are sufficient to orchestrate all of this, because bash gives you access to the entire Python ecosystem, every CLI tool, and every library ever written.

Skills become your extraction instructions. Your "skill instructions" — the step-by-step guidance for extracting each field — map perfectly to the Agent Skills format. For example, a credit_agreement_security_classification/SKILL.md could contain:

yaml
---
name: Security Classification Extractor
description: Classifies loan security level from credit agreements by analyzing collateral sections, pledge clauses, and guarantee structures.
---
Then the skill body contains your human-expert extraction logic: "Look for Section X. Search for keywords like 'collateral', 'pledge', 'lien'. If found, classify as Secured Level 1. If not found, search for 'guarantee', 'surety'..." along with reference Python scripts the agent can execute.

The progressive disclosure architecture ensures this scales: metadata uses ~50 tokens per skill, full SKILL.md files ~500 tokens, and reference files 2,000+ tokens only when specifically needed. 
Claude
 So you could have hundreds of extraction skills loaded without overwhelming the context window — the agent only pulls in the ones relevant to the current extraction task.

Why this is better than the framework-heavy approach I originally recommended:

The original recommendation (LlamaIndex + PydanticAI + custom orchestrator) treated document intelligence as a special domain requiring special tools. Your reframing treats it as any other work that can be done through code, guided by skills. The second approach is simpler, more composable, and more maintainable. Anthropic explicitly says: "Instead of building fragmented, custom-designed agents for each use case, anyone can now specialize their agents with composable capabilities by capturing and sharing expertise." 
Claude

How Pi's agent loop fits into this:

Pi's architecture aligns almost perfectly with Anthropic's emerging architecture of four layers: the agent loop (core reasoning), the agent runtime (code execution, filesystem), MCP servers (connections to external tools and data), and skills library (domain expertise and procedural knowledge). 
Claude

Pi's pi-agent-core is the loop. Bash + filesystem is the runtime. Skills provide the domain expertise. The one thing Pi lacks natively is MCP, but its extension system lets you build MCP support or any other integration. 
Shittycodingagent
 And crucially, Pi runs in four modes including "an SDK for embedding in your own apps" 
npm
 — so you could embed it in a FastAPI backend service that receives extraction requests and processes documents headlessly.

The practical architecture for your credit agreement system would look like this:

Your agent runtime is a coding agent (Pi, Claude Code via Agent SDK, or a minimal custom loop — the loop itself is trivial). Your skills library contains one skill per extraction field type (security classification, interest rate extraction, covenant identification, maturity date parsing, etc.). Each skill contains markdown instructions + Python helper scripts the agent can execute. When a new document arrives, the orchestrator loads the document to the filesystem, activates relevant skills, and the agent reads the skill, writes and executes Python scripts to parse the PDF, searches for relevant sections, extracts and validates the field, and outputs structured JSON.

The beauty is that adding a new field to extract is just adding a new skill folder — no code changes to the agent, no framework modifications, no redeployment. A domain expert (your credit analyst) can write the extraction logic in natural language, pair it with Python helper scripts, and the agent absorbs this new capability instantly. As Anthropic notes, "skill creation isn't limited to engineers. Product managers, analysts, and domain experts are already building skills to codify their workflows." 
Claude

The scaling story is compelling too. Anthropic is already deploying this exact pattern to financial services: DCF model builders, comparable company analysis, earnings analysis, due diligence — all as skills on top of the same general-purpose coding agent. 
Claude
 Your credit agreement extraction is the same pattern applied to a different financial domain.

So to directly answer your question: Yes, the coding agent + skills pattern is the right architecture for your problem, and it generalizes across domain-specific problems. Whether you use Pi's pi-agent-core, Claude's Agent SDK, or build a minimal 50-line agent loop yourself — the loop is commoditized. The real value is in the skills you write. Focus your energy there.

pi-agent vs claude agent sdk - honest answer

9:54 PM
Let me research the Claude Agent SDK properly to give you a fair comparison.


Searched the web

Here's the honest, no-BS comparison.

Claude Agent SDK wins for your use case. Pi is the better product for individual developers. They're solving different problems.

Let me be direct about what each one actually is, where each one is stronger, and what matters for your credit agreement extraction system.

What they share: Both are coding agent loops with the same core philosophy — give the LLM a few basic tools (read, write, edit, bash), let it reason and execute code to solve problems. Both support multi-provider LLMs. Both support skills/AGENTS.md for domain expertise. Both are TypeScript-native. The agent loop itself is nearly identical conceptually.

Where Pi genuinely wins:

Pi is a better developer experience for individual use. Armin Ronacher (creator of Flask) described it well: Pi has a tiny core with the shortest system prompt of any agent he's aware of, and it makes up for this by providing an extension system that lets extensions persist state into sessions, which is "incredibly powerful." 
Armin Ronacher
 Pi's session-as-trees, mid-stream steering messages, branch-and-rewind, hot-reloading extensions — these are genuinely innovative features for interactive work. The system prompt is under 1,000 tokens 
Medium
 compared to Claude Code's multi-thousand-token prompt, meaning more of the context window is available for your actual work. Pi gives you total control over context engineering — no magic, no hidden behavior.

Pi is also fully open-source with MIT license, no usage restrictions, no branding requirements, and no dependency on Anthropic's infrastructure. You can self-host models, use any provider, and the entire codebase is readable and hackable. It's been used in seven different production projects. 
Mariozechner

Where Claude Agent SDK genuinely wins:

The Claude Agent SDK is a production infrastructure platform, not just an agent loop. Here's what it gives you that Pi doesn't:

The Agent SDK includes built-in tools for reading files, running commands, and editing code 
Claude API Docs
 — same as Pi — but it also provides checkpoint mechanisms for breakpoint resumption of long-process tasks, strict permission boundaries, automatic context compaction, prompt caching optimizations, and session management 
DataCamp
 — all things you'd have to build yourself on Pi.

It works with Amazon Bedrock, Google Vertex AI, and Microsoft Azure AI Foundry 
Claude API Docs
 out of the box — critical for enterprise cloud deployments. Pi supports multi-provider via its own pi-ai layer, but you'd need to wire up the enterprise cloud provider integrations yourself.

The SDK is available in both TypeScript and Python 
Substack
, with shared concepts across stacks. Pi is TypeScript-only. For your use case where Python is important (document processing libraries, ML ecosystem), this matters.

The Claude Agent SDK has Anthropic's institutional weight behind it. Apple's Xcode just integrated it natively. 
Anthropic
 GitHub integrated it. It's the same engine powering Claude Code, which millions of developers use daily. This means bugs get fixed fast, edge cases get found, and the infrastructure gets battle-tested at a scale Pi can't match.

And critically for your use case: the Agent Skills ecosystem is native to the Claude Agent SDK. Anthropic is already deploying financial services skills (DCF models, due diligence, earnings analysis) and healthcare skills on this exact platform. 
Claude
 The skill format, progressive disclosure, and skill discovery were designed for the Claude Agent SDK first. Pi adopted a compatible concept, but it's not the canonical implementation.

Where Pi and Claude Agent SDK are roughly equal:

The core agent loop quality — both are minimal, well-designed loops. Multi-LLM provider support — both handle it, with different trade-offs. Extension/customization — Pi's extension system is arguably more elegant, but the Claude Agent SDK's MCP integration gives it broader tool connectivity. Community energy — Pi has passionate indie/hacker community; Claude Agent SDK has massive enterprise adoption.

The honest trade-off for your specific problem:

Dimension	Pi	Claude Agent SDK
Agent loop quality	Excellent, minimal	Excellent, production-hardened
Skills / domain expertise	Compatible pattern	Native, canonical implementation
Python support	❌ TypeScript-only	✅ Python + TypeScript
Enterprise cloud (Bedrock, Vertex)	Manual wiring	✅ Built-in
Context management	More control (manual)	More automated (compaction, caching)
Long-running tasks	You build it	✅ Checkpointing, session resume
Subagents for parallel extraction	You build it (tmux spawn)	✅ Built-in subagent support
Permission/safety controls	You build it (extensions)	✅ Built-in policy modes
Vendor lock-in	None (MIT, any LLM)	Moderate (Anthropic-centric)
Observability/debugging	Session trees, export	Built-in monitoring
Community/ecosystem	Small but passionate	Massive, growing fast
Cost to deploy	Free (bring your own LLM keys)	Free SDK, but optimized for Claude models
My honest recommendation:

For your 600-page credit agreement extraction system that needs to run headlessly in cloud-native infrastructure, scale across document types, and be maintainable by a team — go with the Claude Agent SDK. The Python support, built-in subagents for parallel field extraction, checkpoint/resume for long documents, enterprise cloud provider support, and the canonical skills implementation all directly address your requirements. You'll spend your time writing skills and extraction logic instead of building infrastructure.

The one legitimate concern is vendor lock-in. The Claude Agent SDK is optimized for Claude models. If multi-provider flexibility is a hard requirement (you mentioned it is), then you have two options: use the Claude Agent SDK as your primary runtime but design your skills to be portable (the Agent Skills spec is an open standard), or use Pi's pi-agent-core for the LLM-agnostic loop and accept that you'll need to build the production infrastructure (subagents, checkpointing, permissions, context compaction) yourself.

For most teams, the pragmatic choice is the Claude Agent SDK — the infrastructure it provides out of the box would take months to replicate, and the skills you write are portable by design anyway.



