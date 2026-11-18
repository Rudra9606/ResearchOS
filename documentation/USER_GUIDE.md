# ResearchOS user guide

## Create a workspace

Register or sign in, create a project, and write a specific research question. A project's topic sets its scope and keeps documents, runs, evidence, and reports together.

## Add materials

Upload PDF, DOCX, TXT, CSV, or XLSX files up to the configured size limit. Processing runs in the background worker; the document library polls status while a file is indexed. The RAG question panel searches the project's indexed documents and reports the answer and evidence-sufficiency signal returned by the model.

## Run research

Create a run from a focused question and choose basic, standard, or comprehensive depth. Start the run from Research runs. It includes the selected project's documents; CSV and XLSX files are also passed to dataset analysis. Runs continue in the worker if you leave the page. You may request cancellation, which takes effect between agent steps. On completion, review sources, verified claims, and the generated PDF. You can request PDF, DOCX, or HTML exports and preview report text. Failed or cancelled runs can be retried.

## Review evidence and the graph

Evidence & claims presents stored sources and verification results. Knowledge graph displays those persisted claims and sources. A connecting edge appears only when the claim's saved evidence text explicitly includes the exact source URL or a sufficiently distinctive source title. Similarity alone does not create a citation edge.

## Reports and conversations

Download available report artifacts from Reports. Research execution generates a PDF. In History, create or open a project conversation and ask a question about its indexed documents. Answers are grounded in retrieved project evidence, show citations, and save both messages for later review. If the documents do not provide evidence, ResearchOS says so instead of inventing an answer.

## Privacy and sign-out

Sign out removes the browser session cookie. Research records and uploaded files remain in the account until deleted through supported API actions or an administrator's retention process.
