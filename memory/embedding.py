import json
from typing import Optional
from abc import ABC, abstractmethod
import aiohttp
import requests
import sys
from pathlib import Path
from base.util import Util
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from memory.configs import BaseEmbedderConfig
from memory.base import EmbeddingBase
from loguru import logger


class LlamaCppEmbedding(EmbeddingBase):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)
        self.config.embedding_base_url = config.embedding_base_url

    async def embed(self, text):
        """
        Get the embedding for the given text using OpenAI.

        Args:
            text (str): The text to embed.

        Returns:
            list: The embedding vector.
        """
        text = text.replace("\n", " ")
        logger.debug(f"LlamaCppEmbedding.embed: text: {text}")
        text = await Util().llm_summarize(text)
        logger.debug(f"LlamaCppEmbedding.embed: summarizedtext: {text}")
        embedding_url = self.config.embedding_base_url + "/v1/embeddings"
        async with aiohttp.ClientSession() as session:
            async with session.post(
                embedding_url,
                headers={"accept": "application/json", "Content-Type": "application/json"},
                data=json.dumps({"input": text}),
            ) as response:
                response_json = await response.json()
                logger.debug(f"LlamaCppEmbedding.embed: response_json: {response_json}")
                ret = response_json["data"][0]["embedding"]
                return ret
    

# Example usage
if __name__ == "__main__":
    config = BaseEmbedderConfig(embedding_dims=4096, embedding_base_url="http://localhost:5066")  # Set the correct URL and dimensions
    embedder = LlamaCppEmbedding(config)
    embedding_vector = embedder.embed("Your sample text here")
    print(embedding_vector)
    print(len(embedding_vector))

