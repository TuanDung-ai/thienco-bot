# Gọi /v1/embeddings tương tự cách gọi chat trong openrouter_provider
import httpx

class EmbeddingsProvider:
    def __init__(self, api_key: str, base_url: str, model: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        url = f"{self.base_url}/v1/embeddings"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {"model": self.model, "input": texts}
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(url, json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
            return [item["embedding"] for item in data["data"]]
