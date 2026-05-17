# 🔑 Environment Variables & Configuration

The project uses a `.env` file for local development and **GCP Secrets/Env Vars** for production. All configuration is managed via **Pydantic Settings** for strict type safety.

---

## 🏛️ Core Settings
| Variable | Description | Example |
| :--- | :--- | :--- |
| `PROJECT_ID` | Your GCP Project ID | `dmtxpress` |
| `LOCATION` | Primary GCP Region | `us-central1` |

## 🧠 AI & LLM (The Brain)
| Variable | Description | Example |
| :--- | :--- | :--- |
| `GROQ_API_KEY` | Key for Llama 3.3 models | `gsk_...` |
| `GROQ_MODEL` | Specific model version | `llama-3.3-70b-versatile` |
| `GCP_DOC_AI_PROCESSOR_ID` | ID of the OCR parser | `786e...` |

## 📥 Ingestion & Storage
| Variable | Description | Example |
| :--- | :--- | :--- |
| `RAW_BUCKET` | Destination for raw PDFs | `dmtxpress-rag-raw` |
| `PROCESSED_BUCKET` | Destination for JSON metadata | `dmtxpress-rag-processed` |

## 🗄️ Persistence (The Memory)
| Variable | Description | Example |
| :--- | :--- | :--- |
| `QDRANT_URL` | Cloud Qdrant Endpoint | `https://...` |
| `QDRANT_API_KEY` | Qdrant Access Token | `xyz...` |
| `DATABASE_URL` | Cloud SQL Postgres URI | `postgresql+pg8000://...` |

## 🕵️ Observability (The Vision)
| Variable | Description | Example |
| :--- | :--- | :--- |
| `LOGFIRE_TOKEN` | Token for system tracing | `logfire_...` |
| `LANGSMITH_API_KEY` | Token for agent logic tracing | `lsv2_...` |

---

## 🔒 Security Best Practices
1.  **Never** commit your `.env` file to Git.
2.  In **Cloud Run**, use the "Variables & Secrets" tab to inject these values at runtime.
3.  Use the `commands_example.md` as a template when setting up a new developer environment.
