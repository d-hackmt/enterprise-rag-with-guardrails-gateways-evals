# Redis Semantic Caching & Memory

## 🚀 Overview
The Redis layer (GCP Memorystore) provides two critical functions: **Performance Caching** and **Conversation Memory**.

## 🧠 Semantic Caching
To reduce costs and improve user experience, the system implements a semantic cache.
- **Key Strategy**: `query:<sanitized_query_text>`
- **TTL**: 3600 seconds (1 hour).
- **Behavior**: If an identical question is asked within the TTL window, the system skips the entire RAG pipeline (Retrieval, Re-ranking, Groq) and returns the cached JSON response immediately.

## 💬 Conversation Memory
The agent maintains context across multiple turns using a rolling window.
- **Storage**: Redis Lists (`history:<session_id>`).
- **Window Size**: 10 messages (5 turns).
- **TTL**: 86,400 seconds (24 hours).
- **Benefit**: Allows the user to ask follow-up questions like "Tell me more about the first point" without re-stating the entire context.

## 🛠️ Local vs. Production
- **Local**: The service pings the host. If it fails (common on local machines without Redis), it enters **"Quiet Mode"** and disables caching to prevent `TimeoutError`.
- **Production**: Requires a **Serverless VPC Access Connector** on Cloud Run to reach the internal Memorystore IP (`10.x.x.x`).
