from abc import ABC
from typing import Optional, ClassVar, Dict, Any
from pydantic import BaseModel, Field, model_validator, field_validator
import os

from memory.setup import memory_dir

class BaseEmbedderConfig(ABC):
    """
    Config for Embeddings.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        embedding_dims: Optional[int] = None,
        # Default to use llama.cpp's embedding
        embedding_base_url: Optional[str] = None,
        # Huggingface specific
        model_kwargs: Optional[dict] = None,
    ):
        """
        Initializes a configuration class instance for the Embeddings.

        :param model: Embedding model to use, defaults to None
        :type model: Optional[str], optional
        :param embedding_dims: The number of dimensions in the embedding, defaults to None
        :type embedding_dims: Optional[int], optional
        :param model_kwargs: key-value arguments for the huggingface embedding model, defaults a dict inside init
        :type model_kwargs: Optional[Dict[str, Any]], defaults a dict inside init

        """

        self.model = model
        self.embedding_dims = embedding_dims

        self.embedding_base_url = embedding_base_url

        self.model_kwargs = model_kwargs or {}


class BaseLlmConfig(ABC):
    """
    Config for LLMs.
    """

    def __init__(
        self,
        llama_cpp_base_url: Optional[str] = None,
    ):
        """
        Initializes a configuration class instance for the LLM.
        :type llama_cpp_base_url: Optional[str], optional
        """

        self.llama_cpp_base_url = llama_cpp_base_url


class MemoryItem(BaseModel):
    id: str = Field(..., description="The unique identifier for the text data")
    memory: str = Field(
        ..., description="The memory deduced from the text data"
    )  # TODO After prompt changes from platform, update this
    hash: Optional[str] = Field(None, description="The hash of the memory")
    # The metadata value can be anything and not just string. Fix it
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional metadata for the text data"
    )
    score: Optional[float] = Field(
        None, description="The score associated with the text data"
    )
    created_at: Optional[str] = Field(
        None, description="The timestamp when the memory was created"
    )
    updated_at: Optional[str] = Field(
        None, description="The timestamp when the memory was updated"
    )


class MemoryConfig(BaseModel):
    history_db_path: str = Field(
        description="Path to the history database",
        default=os.path.join(memory_dir, "memory.db"),
    )
