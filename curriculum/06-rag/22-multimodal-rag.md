# Multimodal RAG: Images, Audio, Video, Tables in Retrieval

> **Track:** T06 RAG · **Time:** 2h · **Prereqs:** 01-chunking, 02-embeddings-choice · **Updated:** 2026-10-31
> **Module id:** `T06-multimodal-rag` · **Tags:** advanced, retrieval

## The 30-second version

Standard RAG is text-only: embed text chunks, retrieve text, generate text. Multimodal RAG extends every stage to non-text modalities — images, audio, video, tables, charts. The approaches: (1) **unified embedding space** (CLIP, ImageBind) — embed images and text into the same vector space, so a text query retrieves relevant images. (2) **Caption-then-retrieve** — use a VLM (GPT-4V, Gemini) to caption images/tables, then run standard text RAG on the captions. (3) **Native multimodal retrieval** — models that jointly process text + image (ColPali, late-interaction models). (4) **Table-aware retrieval** — extract tables as structured data (not just text), with schema-aware chunking. The 2026 reality: caption-then-retrieve is the pragmatic default (works with any LLM, easy to debug); unified embedding (CLIP) is better for image-heavy corpora but requires multimodal embedding models; native multimodal retrieval (ColPali) is the frontier for document understanding. The key engineering challenge: evaluation — how do you measure retrieval quality when the "answer" is an image?

## Why this gets asked

Because enterprise RAG increasingly needs to handle PDFs with charts, product catalogs with images, and meeting transcripts with slides. Interviewers probe: "your RAG needs to answer questions about a product catalog with images — how?" The wrong answer is "just caption everything with GPT-4V" — that's expensive and loses spatial/visual detail. The right answer names the three approaches and their tradeoffs. Also probed: "how do you evaluate multimodal retrieval?" (answer: separate metrics for text-retrieval and image-retrieval, plus end-to-end answer quality with VLM-as-judge). The principal-level probe: "your RAG needs to handle 10,000 PDFs with charts and tables — design the pipeline."

## Lineage: past → present → future

**What came before.** Text-only RAG (2020-2023) dominated because embedding models were text-only and LLMs were text-only. The pain: enterprise documents are multimodal (PDFs with charts, slides with images, spreadsheets with tables). Captioning images with early VLMs (BLIP, 2022) was the first workaround but lost detail. CLIP (2021) showed that images and text could share an embedding space, but CLIP's retrieval quality was mediocre for fine-grained document understanding.

**Where it stands now.** Three approaches coexist: (1) **Caption-then-retrieve** (GPT-4V/Gemini captioning → standard text RAG) — pragmatic, works with any LLM, but loses visual detail and is expensive. (2) **Unified embedding** (CLIP, ImageBind, Nomic Embed Vision) — embed images and text together; good for image-heavy corpora but requires multimodal embedding models. (3) **Native multimodal retrieval** (ColPali, 2024) — late-interaction models that process document images directly, preserving layout and visual structure; the frontier for document understanding. Table-aware retrieval is a sub-problem: extract tables as structured data (not just text), with schema-aware chunking and SQL-like querying.

**Where it's heading.** High confidence: caption-then-retrieve remains the pragmatic default for most use cases. Medium confidence: native multimodal retrieval (ColPali-style) becomes standard for document understanding (PDFs, slides, forms). Speculative: end-to-end multimodal RAG where the retriever and generator are both multimodal, with no text intermediate — but this requires multimodal LLMs with long context and is still expensive.

## Mental model

```
MULTIMODAL RAG PIPELINE (caption-then-retrieve, the pragmatic default):

  ┌─────────────┐     ┌──────────────┐     ┌─────────────┐
  │  Document   │────►│ VLM Caption  │────►│ Text Chunk  │
  │  (PDF/image)│     │ (GPT-4V)     │     │ (caption)   │
  └─────────────┘     └──────────────┘     └──────┬──────┘
                                                    │
                                                    ▼
  ┌─────────────┐     ┌──────────────┐     ┌─────────────┐
  │  Query      │────►│ Embed (text) │────►│ Retrieve    │
  │  (text)     │     │              │     │ (top-k)     │
  └─────────────┘     └──────────────┘     └──────┬──────┘
                                                    │
                                                    ▼
  ┌─────────────┐     ┌──────────────┐     ┌─────────────┐
  │  Generate   │◄────│ LLM (text)   │◄────│ Context     │
  │  Answer     │     │              │     │ (captions)  │
  └─────────────┘     └──────────────┘     └─────────────┘

UNIFIED EMBEDDING (CLIP-style):

  Image ──► CLIP image encoder ──► vector ──► same space as text
  Text  ──► CLIP text encoder  ──► vector ──► retrieve cross-modally

NATIVE MULTIMODAL (ColPali-style):

  Document image ──► vision encoder ──► patch embeddings ──► late interaction
  Query text ──► text encoder ──► token embeddings ──► MaxSim scoring
```

## Recognition heuristics

- **"Your RAG needs to handle PDFs with charts and tables"** → caption-then-retrieve (VLM captions) + table-aware extraction. Pragmatic default.
- **"Build image search for a product catalog"** → unified embedding (CLIP/ImageBind). Text query → image retrieval.
- **"Document understanding (forms, invoices, slides)"** → native multimodal (ColPali). Preserves layout and visual structure.
- **"How do you evaluate multimodal retrieval?"** → Separate text-retrieval and image-retrieval metrics + end-to-end answer quality with VLM-as-judge.

## Common bugs and how these get shipped wrong

- **Captioning everything with GPT-4V.** Expensive ($0.01-0.05/image) and loses spatial/visual detail. Use for complex images (charts, diagrams); use OCR + structured extraction for simple tables.
- **Not handling table structure.** Extracting tables as flat text loses row/column relationships. Use table-aware extraction (Camelot, pdfplumber) and store as structured data.
- **Evaluating only text retrieval.** If your RAG retrieves images, you need image-retrieval metrics (image recall@k, not just text recall@k).
- **Ignoring document layout.** Flat text extraction from PDFs loses reading order, headers, and section structure. Use layout-aware extraction (Docling, Unstructured) before chunking.

## Interview questions

1. **"Design a RAG system for a product catalog with images."** Answer: unified embedding (CLIP/ImageBind) for image retrieval + caption-then-retrieve for complex product descriptions. Evaluate with image recall@k and end-to-end answer quality.
2. **"How do you handle PDFs with charts and tables in RAG?"** Answer: caption-then-retrieve (VLM captions for charts) + table-aware extraction (structured data for tables). Layout-aware chunking (Docling/Unstructured). Evaluate with both text and image metrics.
3. **"ColPali vs CLIP vs caption-then-retrieve?"** Answer: ColPali = native multimodal retrieval (best for document understanding, preserves layout). CLIP = unified embedding (good for image search, mediocre for document understanding). Caption-then-retrieve = pragmatic default (works with any LLM, easy to debug, but loses visual detail).

## Red flags that fail you

- Captioning everything with GPT-4V without considering cost and detail loss.
- Not handling table structure (flat text extraction loses relationships).
- Evaluating only text retrieval when images are involved.
- Ignoring document layout (flat text extraction from PDFs).
- Not knowing the three approaches and their tradeoffs.

## Cheat card

- 3 approaches: (1) caption-then-retrieve (VLM captions → text RAG), (2) unified embedding (CLIP/ImageBind), (3) native multimodal (ColPali).
- Caption-then-retrieve = pragmatic default. ColPali = frontier for document understanding.
- Table-aware extraction: Camelot, pdfplumber → structured data, not flat text.
- Layout-aware chunking: Docling, Unstructured (preserves reading order, headers, sections).
- Evaluate: separate text-retrieval + image-retrieval metrics + VLM-as-judge for end-to-end.

## Sources

- [ColPali: Efficient Document Retrieval with Vision Language Models](https://github.com/illuin-tech/colpali) — accessed 2026-10-31
- [CLIP: Learning Transferable Visual Representations](https://github.com/openai/CLIP) — accessed 2026-10-31
- [ImageBind: One Embedding Space To Bind Them All](https://github.com/facebookresearch/ImageBind) — accessed 2026-10-31
- [Docling: Document Understanding](https://github.com/DS4SD/docling) — accessed 2026-10-31

## Changelog

- 2026-10-31: Created — Multimodal RAG identified as a gap (no dedicated module; only incidental mention in T26-05).
