import httpx
import math

OLLAMA_URL = "http://localhost:11434/v1/embeddings"
MODEL = "nomic-embed-text"

def embed(text: str) -> list[float]:
    response = httpx.post(
        OLLAMA_URL,
        json={"model": MODEL, "input": text},
        headers={"Authorization": "Bearer ollama"},
    )
    response.raise_for_status()
    return response.json()["data"][0]["embedding"]

def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    return dot / (norm_a * norm_b)

words = ["dog", "puppy", "canine", "car", "spreadsheet"]
vectors = {w: embed(w) for w in words}

print(f"Vector length: {len(vectors['dog'])} dimensions\n")

for w1 in words:
    for w2 in words:
        if w1 < w2:
            sim = cosine_similarity(vectors[w1], vectors[w2])
            print(f"{w1:12} vs {w2:12} -> {sim:.4f}")