import httpx

from .config import settings

_MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"


class MistralError(RuntimeError):
    pass


async def complete(
    *,
    system: str,
    messages: list[dict[str, str]],
    temperature: float = 0.3,
    max_tokens: int = 700,
    json_mode: bool = False,
) -> str:
    """Calls the Mistral chat completions API and returns the assistant's
    text content. Raises MistralError on any non-2xx response or malformed
    payload so callers get a single failure mode to handle."""
    payload: dict[str, object] = {
        "model": settings.mistral_model,
        "messages": [{"role": "system", "content": system}, *messages],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            _MISTRAL_URL,
            headers={
                "Authorization": f"Bearer {settings.mistral_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
    if response.status_code != 200:
        raise MistralError(f"Mistral API error {response.status_code}: {response.text}")

    data = response.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise MistralError(f"Unexpected Mistral response shape: {data}") from exc
