# Enterprise Agentic RAG: LangGraph · Guardrails · LLM Gateway · RAGAS Evals · GCP

```mermaid
graph LR

    %% ── Interfaces ───────────────────────────────────────────────────────────
    subgraph UI ["🖥️  Interface Layer"]
        direction TB
        CHAT["Streamlit\nChat UI"]
        EVAL_UI["Streamlit\nEval App"]
    end

    %% ── API + Safety ─────────────────────────────────────────────────────────
    subgraph SAFETY ["🛡️  API + Safety"]
        direction TB
        API["⚡ FastAPI\n/query"]
        GR{"NeMo\nGuardrails\nGate 1"}
        RC{"Redis\nSemantic Cache\nGate 2"}
    end

    %% ── LangGraph Agent ──────────────────────────────────────────────────────
    subgraph AGENT ["🧠  LangGraph Agentic Core"]
        direction TB
        PL["🗺️ Planner\nIntent Classification"]
        RT["🔍 Retriever\nVector Search"]
        RS["💬 Responder\nAnswer Generation"]
        MEM[("💾 PostgresSaver\nCloud SQL Postgres 15")]
    end

    %% ── Retrieval ────────────────────────────────────────────────────────────
    subgraph RETRIEVAL ["🔎  Retrieval Layer"]
        direction TB
        QD[("🗄️ Qdrant Cloud\nVector DB")]
        FR["⚡ FlashRank\nLocal Reranker"]
    end

    %% ── LLM Gateway ──────────────────────────────────────────────────────────
    subgraph GATEWAY ["🌐  LLM Gateway"]
        direction TB
        PK["🔀 Portkey\nUnified Gateway"]
        G1["🦙 Groq Primary\nLlama 3.3 · 70B"]
        G2["🦙 Groq Fallback\nLlama 3.1 · 8B"]
    end

    %% ── Ingestion ────────────────────────────────────────────────────────────
    subgraph INGEST ["📥  Ingestion Pipeline"]
        direction TB
        EA["📡 Eventarc\nGCS Trigger"]
        LOADER["Document Loaders\nPDF · HTML · DOCX · PPTX · TXT"]
        DOCAI["📋 Google\nDocument AI"]
        GCS1[("☁️ GCS\nRaw Bucket")]
        GCS2[("☁️ GCS\nProcessed Bucket")]
        EMB["🔢 Vertex AI\ntext-embedding-004"]
    end

    %% ── Observability ────────────────────────────────────────────────────────
    subgraph OBS ["📡  Observability"]
        direction LR
        LF["🔥 Pydantic\nLogfire"]
        LS["🦜 LangSmith\nTracing"]
    end

    %% ── Evals ────────────────────────────────────────────────────────────────
    subgraph EVALS ["🧪  RAGAS Evaluation Suite"]
        direction LR
        GD[("📋 Golden Dataset\n15 Samples · 6 Guardrail Tests")]
        RAGAS["RAGAS Metrics\nFaithfulness · Relevancy\nPrecision · Recall · Correctness"]
        TC["Tool Correctness\nJaccard · Zero LLM"]
        JUDGE["⚖️ Judge LLM\nGroq · JUDGE_GROQ Key"]
        HIST[("💾 GCS\nEval History")]
    end

    %% ── GCP Infrastructure ───────────────────────────────────────────────────
    subgraph GCP ["☁️  Google Cloud Platform Infrastructure"]
        direction LR
        CR["Cloud Run\n4 Microservices"]
        CB["Cloud Build\nCI/CD"]
        AR["Artifact\nRegistry"]
        VPC["Direct VPC Egress\nPrivate Networking"]
        REDIS[("🔴 Redis\nMemorystore")]
        SQL[("🐘 Cloud SQL\nPostgres 15")]
    end

    %% ── Main Query Flow ──────────────────────────────────────────────────────
    CHAT -->|query| API
    API --> GR
    GR -->|"❌ blocked"| CHAT
    GR -->|"✅ pass"| RC
    RC -->|"⚡ HIT ~50ms"| CHAT
    RC -->|"MISS"| PL
    PL -->|conversational| RS
    PL -->|technical| RT
    RT --> QD
    QD --> FR
    FR --> RS
    RS --> PK
    PL --> PK
    PK --> G1
    PK -.->|fallback| G2
    RS -.-> MEM
    MEM -.-> PL
    RS -->|store answer| RC

    %% ── Ingestion Flow ───────────────────────────────────────────────────────
    GCS1 -->|object.finalized| EA
    EA --> LOADER
    LOADER --> DOCAI
    DOCAI --> GCS2
    LOADER --> EMB
    EMB --> QD

    %% ── Eval Flow ────────────────────────────────────────────────────────────
    EVAL_UI -->|phase 1\nBACKEND_URL| API
    GD --> RAGAS
    GD --> TC
    RAGAS --> JUDGE
    RAGAS --> HIST
    TC --> HIST

    %% ── Observability Traces ─────────────────────────────────────────────────
    API -.->|spans| LF
    AGENT -.->|traces| LS

    %% ── Infra ────────────────────────────────────────────────────────────────
    CB --> AR
    AR --> CR
    CR --- VPC
    VPC --- REDIS
    MEM --- SQL

    %% ── Colors ───────────────────────────────────────────────────────────────
    classDef ui        fill:#3B82F6,stroke:#1D4ED8,color:#fff,rx:8
    classDef safety    fill:#EF4444,stroke:#B91C1C,color:#fff,rx:8
    classDef agent     fill:#8B5CF6,stroke:#6D28D9,color:#fff,rx:8
    classDef retrieval fill:#10B981,stroke:#047857,color:#fff,rx:8
    classDef gateway   fill:#F59E0B,stroke:#B45309,color:#fff,rx:8
    classDef ingest    fill:#6366F1,stroke:#4338CA,color:#fff,rx:8
    classDef obs       fill:#14B8A6,stroke:#0F766E,color:#fff,rx:8
    classDef evals     fill:#EC4899,stroke:#BE185D,color:#fff,rx:8
    classDef infra     fill:#64748B,stroke:#334155,color:#fff,rx:8
    classDef memory    fill:#7C3AED,stroke:#5B21B6,color:#fff,rx:8

    class CHAT,EVAL_UI ui
    class API,GR,RC safety
    class PL,RT,RS agent
    class QD,FR retrieval
    class PK,G1,G2 gateway
    class EA,LOADER,DOCAI,GCS1,GCS2,EMB ingest
    class LF,LS obs
    class GD,RAGAS,TC,JUDGE,HIST evals
    class CR,CB,AR,VPC,REDIS,SQL infra
    class MEM memory
```

---

## System Architecture — Portal View

```mermaid
graph TB

    subgraph UI ["1. User Interface"]
        direction LR
        CHAT["Streamlit Chat UI\n(Cloud Run — Public)"]
        EAPP["Streamlit Eval App\n(Cloud Run — Public)"]
    end

    subgraph SAFETY ["2. API + Safety Gates"]
        direction LR
        API["⚡ FastAPI  /query"]
        GR{"🛡️ Gate 1: NeMo Guardrails\nBlocks jailbreak · off-topic · injection"}
        RC{"⚡ Gate 2: Redis Semantic Cache\ncosine distance < 0.15 → ~50ms HIT"}
    end

    subgraph AGENT ["3. Agent Engine  —  LangGraph"]
        direction LR
        PL["🗺️ Planner Node\nIntent Classification"]
        RT["🔍 Retriever Node\nVector Search + FlashRank Reranker"]
        RS["💬 Responder Node\nAnswer Generation"]
        MEM[("💾 PostgresSaver\nCloud SQL — persists across restarts")]
    end

    subgraph KNOWLEDGE ["4. Knowledge & LLMs"]
        direction LR
        QD[("🗄️ Qdrant Cloud\nVector DB")]
        FR["⚡ FlashRank\nLocal Reranker"]
        PK["🔀 Portkey Gateway\nRouting + Fallback + Observability"]
        G1["🦙 Groq Primary\nLlama 3.3 · 70B"]
        G2["🦙 Groq Fallback\nLlama 3.1 · 8B"]
    end

    subgraph INGEST ["5. Data Ingestion  —  Event-Driven"]
        direction LR
        UPLOAD["Admin uploads\nPDF · HTML · DOCX · PPTX · TXT"]
        GCS1[("☁️ GCS Raw Bucket")]
        EA["📡 Eventarc Trigger\nobject.finalized"]
        SVC["Ingestion Service\n(Cloud Run — Internal only)"]
        DOCAI["📋 Google Document AI\nPDF OCR + Parsing"]
        EMB["🔢 Vertex AI\ntext-embedding-004"]
        QD2[("🗄️ Qdrant Cloud")]
        GCS2[("☁️ GCS Processed Bucket")]
    end

    subgraph EVALS ["6. Evaluation Suite  —  RAGAS"]
        direction LR
        GD[("📋 Golden Dataset\n15 RAG Samples · 6 Guardrail Tests")]
        RAGAS["RAGAS Metrics\nFaithfulness · Relevancy · Precision\nRecall · Correctness"]
        TC["Tool Correctness\nJaccard · Zero LLM Cost"]
        JG["⚖️ Judge LLM\nGroq llama-3.1-8b-instant · JUDGE_GROQ key"]
        HIST[("💾 GCS Eval History\neval-results/ prefix\npersists across restarts")]
    end

    subgraph OBS ["7. Monitoring & Observability"]
        direction LR
        LF["🔥 Pydantic Logfire\nDistributed Tracing"]
        LS["🦜 LangSmith\nAgent Step Tracing"]
        PK2["🔀 Portkey Dashboard\nAll LLM calls visible"]
    end

    subgraph GCP ["8. GCP Infrastructure"]
        direction LR
        CR["Cloud Run\n4 Independent Microservices"]
        CB["Cloud Build\n4 parallel image builds"]
        AR["Artifact Registry\nDocker Images"]
        VPC["Direct VPC Egress\nno connector needed"]
        REDIS[("🔴 Redis Memorystore\n10.x.x.x private IP")]
        SQL[("🐘 Cloud SQL Postgres 15\nunix socket /cloudsql/...")]
        TF["Terraform\nAll infra as code"]
    end

    %% ── Query Flow ───────────────────────────────────────────────────────────
    CHAT -->|user query| API
    EAPP -->|phase 1 — BACKEND_URL| API
    API --> GR
    GR -->|"❌ blocked"| CHAT
    GR -->|"✅ pass"| RC
    RC -->|"⚡ cache HIT"| CHAT
    RC -->|"cache MISS"| PL
    PL -->|"technical"| RT
    PL -->|"conversational"| RS
    RT --> QD
    QD --> FR
    FR --> RS
    RS --> PK
    PL --> PK
    PK --> G1
    PK -.->|"fallback"| G2
    RS -.-> MEM
    MEM -.-> PL
    RS -->|"cache answer"| RC

    %% ── Ingestion Flow ───────────────────────────────────────────────────────
    UPLOAD --> GCS1
    GCS1 -->|"object.finalized event"| EA
    EA -->|"POST /ingest"| SVC
    SVC --> DOCAI
    SVC --> EMB
    EMB --> QD2
    SVC --> GCS2

    %% ── Eval Flow ────────────────────────────────────────────────────────────
    GD --> RAGAS
    GD --> TC
    RAGAS --> JG
    RAGAS --> HIST
    TC --> HIST

    %% ── Observability ────────────────────────────────────────────────────────
    API -.->|"spans"| LF
    AGENT -.->|"traces"| LS
    PK -.->|"LLM calls"| PK2

    %% ── Infra ────────────────────────────────────────────────────────────────
    TF --> CR
    CB --> AR --> CR
    CR --- VPC
    VPC --- REDIS
    MEM --- SQL

    %% ── Colours ──────────────────────────────────────────────────────────────
    classDef ui        fill:#2563EB,stroke:#1E40AF,color:#fff
    classDef safety    fill:#DC2626,stroke:#991B1B,color:#fff
    classDef agent     fill:#7C3AED,stroke:#5B21B6,color:#fff
    classDef knowledge fill:#D97706,stroke:#92400E,color:#fff
    classDef ingest    fill:#4F46E5,stroke:#3730A3,color:#fff
    classDef evals     fill:#DB2777,stroke:#9D174D,color:#fff
    classDef obs       fill:#0D9488,stroke:#0F766E,color:#fff
    classDef infra     fill:#475569,stroke:#1E293B,color:#fff
    classDef memory    fill:#6D28D9,stroke:#4C1D95,color:#fff

    class CHAT,EAPP ui
    class API,GR,RC safety
    class PL,RT,RS agent
    class QD,FR,PK,G1,G2,QD2 knowledge
    class UPLOAD,GCS1,EA,SVC,DOCAI,EMB,GCS2 ingest
    class GD,RAGAS,TC,JG,HIST evals
    class LF,LS,PK2 obs
    class CR,CB,AR,VPC,REDIS,SQL,TF infra
    class MEM memory
```

---

## System Architecture — Compact View

```mermaid
graph TB
    A["🖥️ 1. Streamlit UI\nChat + Eval App\n(2 Cloud Run services)"]
    B["⚡ 2. FastAPI\n🛡️ Gate 1: NeMo Guardrails\n⚡ Gate 2: Redis Semantic Cache"]
    C["🧠 3. LangGraph Agent\nPlanner → Retriever → Responder\n💾 PostgresSaver (Cloud SQL)"]
    D["🗄️ 4. Qdrant Cloud\n+ FlashRank Reranker\n+ Vertex AI text-embedding-004"]
    E["🌐 5. Portkey Gateway\nGroq Llama 3.3 70B · Fallback 8B"]
    F["📥 6. Auto-Ingestion\nEventarc → Cloud Run (internal)\nDoc AI · Vertex AI Embeddings"]
    G["🧪 7. RAGAS Evals\n5 metrics + Tool Correctness (Jaccard)\n💾 GCS history persistence"]
    H["📡 8. Monitoring\nLogfire · LangSmith · Portkey Dashboard"]
    I["☁️ 9. GCP Infra\nTerraform · Cloud Run (4 services)\nCloud SQL · Redis · Direct VPC Egress"]

    A --> B --> C
    C --> D --> C
    C --> E
    F --> D
    A -.-> G
    B -.-> H
    C -.-> H
    I -.- B

    classDef ui      fill:#2563EB,stroke:#1E40AF,color:#fff
    classDef safety  fill:#DC2626,stroke:#991B1B,color:#fff
    classDef agent   fill:#7C3AED,stroke:#5B21B6,color:#fff
    classDef db      fill:#059669,stroke:#065F46,color:#fff
    classDef llm     fill:#D97706,stroke:#92400E,color:#fff
    classDef ingest  fill:#4F46E5,stroke:#3730A3,color:#fff
    classDef evals   fill:#DB2777,stroke:#9D174D,color:#fff
    classDef obs     fill:#0D9488,stroke:#0F766E,color:#fff
    classDef infra   fill:#475569,stroke:#1E293B,color:#fff

    class A ui
    class B safety
    class C agent
    class D db
    class E llm
    class F ingest
    class G evals
    class H obs
    class I infra
```
