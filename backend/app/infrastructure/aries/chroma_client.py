import logging
import os
from typing import Any

import chromadb
from app.core.config import settings
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings

logger = logging.getLogger(__name__)


class ChromaManager:
    """Manager for ChromaDB vector storage and semantic search.

    This class serves as the 'Semantic Memory' layer for the Aries agent.
    It stores and retrieves high-dimensional vector embeddings representing
    user facts, problem logic, and architectural concepts.

    Attributes:
        persist_directory (str): Local path where vector data is stored.
        embeddings (OllamaEmbeddings): The embedding model instance (via Ollama).
        client (chromadb.PersistentClient): The underlying ChromaDB client.
    """

    def __init__(self, persist_directory: str = "chroma_db"):
        """Initializes the ChromaManager with local persistence and embeddings.

        Args:
            persist_directory (str): Path to the storage directory. Defaults to 'chroma_db'.
        """
        self.persist_directory = persist_directory
        # Ensure the persistence directory exists on the filesystem.
        os.makedirs(self.persist_directory, exist_ok=True)

        # Initialize Ollama embeddings for local vectorization.
        # OllamaEmbeddings class handles the HTTP communication with the local server.
        self.embeddings = OllamaEmbeddings(
            model=settings.EMBEDDING_MODEL.replace(":latest", "")
        )

        self.client = chromadb.PersistentClient(path=self.persist_directory)

    def get_collection(self, collection_name: str) -> Chroma:
        """Retrieves or creates a LangChain-wrapped Chroma collection.

        Args:
            collection_name (str): The name of the vector collection.

        Returns:
            Chroma: A LangChain Chroma vectorstore instance.
        """
        return Chroma(
            client=self.client,
            collection_name=collection_name,
            embedding_function=self.embeddings,
            persist_directory=self.persist_directory,
        )

    async def add_fact(
        self, collection_name: str, content: str, metadata: dict[str, Any], fact_id: str
    ) -> None:
        """Adds a new text fact to the specified vector collection.

        Args:
            collection_name (str): The target collection name.
            content (str): The raw text to vectorize and store.
            metadata (Dict[str, Any]): Structured data associated with the fact.
            fact_id (str): A unique identifier for the fact.
        """
        vectorstore = self.get_collection(collection_name)
        await vectorstore.aadd_texts(
            texts=[content], metadatas=[metadata], ids=[fact_id]
        )
        logger.info(f"CHROMA: Added fact '{fact_id}' to collection '{collection_name}'")

    async def similarity_search(
        self,
        collection_name: str,
        query: str,
        limit: int = 3,
        filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Performs a semantic similarity search against the vector collection.

        Args:
            collection_name (str): The collection to search within.
            query (str): The natural language query or concept string.
            limit (int): Maximum number of relevant hits to return. Defaults to 3.
            filter (Optional[Dict[str, Any]]): Metadata filters (e.g., {"username": "shridhar"}).

        Returns:
            List[Dict[str, Any]]: A list of matching facts with content and metadata.
        """
        vectorstore = self.get_collection(collection_name)
        docs = await vectorstore.asimilarity_search(query=query, k=limit, filter=filter)

        return [{"content": doc.page_content, "metadata": doc.metadata} for doc in docs]

    async def delete_fact(self, collection_name: str, fact_id: str) -> None:
        """Permanently removes a fact from the vector store.

        Args:
            collection_name (str): The collection name.
            fact_id (str): The unique identifier of the fact to delete.
        """
        vectorstore = self.get_collection(collection_name)
        await vectorstore.adelete(ids=[fact_id])
        logger.info(
            f"CHROMA: Deleted fact '{fact_id}' from collection '{collection_name}'"
        )


# Global singleton instance for use across the infrastructure layer.
chroma_manager = ChromaManager()
