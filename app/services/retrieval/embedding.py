import vertexai
from vertexai.language_models import TextEmbeddingModel
from app.config import settings

model = None
BATCH_SIZE = 50 

def get_embedding_model():
    global model
    if model is None:
        # Initialize Vertex AI before loading the model
        vertexai.init(project=settings.PROJECT_ID, location=settings.LOCATION)
        # Reverting to TextEmbeddingModel for stability
        model = TextEmbeddingModel.from_pretrained("text-embedding-004")
    return model

def embed_query(query: str):
    """Embeds a single query string using the stable Vertex AI API."""
    model = get_embedding_model()
    embeddings = model.get_embeddings([query])
    return embeddings[0].values

def embed_texts(texts: list[str]):
    """Embeds a list of text strings in batches."""
    model = get_embedding_model()
    all_embeddings = []

    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i:i+BATCH_SIZE]
        embeddings = model.get_embeddings(batch)
        all_embeddings.extend([e.values for e in embeddings])

    return all_embeddings
