import uuid
import os
import sys
import chromadb
from chromadb.config import Settings


from libs.common import convert_file, chunk_text, embed_with_ollama

import warnings
warnings.filterwarnings(action="ignore", message="unclosed", category=ResourceWarning)


class MemoryRetrievalPassResult(BaseModel):
    memories: List[str]
    summary: str
    should_continue: bool

class MemoryRetrievalResult(BaseModel):
    memories: List[str]
    summary: str
    should_continue: bool

class LongTermMemory:
    def __init__(self, repo_path, llm_server, embedding_model, buffer_size=10):
        self.repo_path = repo_path
        self.llm_server = llm_server
        self.embedding_model = embedding_model
        self.buffer_size = buffer_size
        self.recent_memory_retrievals = []

        # Initialize the Chroma client in-memory (no persistence)
        self.chroma_client = chromadb.Client()

        # Create or load a collection
        self.collection = self.chroma_client.create_collection(name="rag_collection")

    def get_complete_memory(self, memory_id: str):
        """
        {
            "toolset_id": "memories",
            "tool_name": "get_complete_memory",
            "description": "Get the complete memory from the db.",
            "parameters": [
                {"name": "memory_id", "type": "str", "description": "The id of the memory to get."}
            ]
        }
        """
        # get all memories from the with the memory_id
        pass

    def add_message(self, message: Message):
        """
        Chunk, and embed each memory, then store the vectors in Chroma.
        """
        # todo: attach tool call to tool result
        
        # Chunk it up
        if message.content:
            chunks = chunk_text(message.content, chunk_size=1024, overlap=100)
            memory_id = uuid.uuid4().hex[:8]
            
            # Embed each chunk and add to the collection
            for i, chunk in enumerate(chunks):
                embedding = embed_with_ollama(
                    server_url=self.llm_server,
                    text="search_document: " + chunk, # prefix for nomic-embed-text
                    model=self.embedding_model
                )

                # Use a unique ID for each chunk
                doc_id = f"{memory_id}-{i}"

                self.collection.add(
                    documents=[chunk],
                    metadatas=[{"memory_id": memory_id, "chunk_index": i}],
                    ids=[doc_id],
                    embeddings=[embedding]
                )

    def add_memory(self, memory: str):
        """
        Add a memory to the db.
        """
        pass

    def get_relevant_memories(self, agent: Agent):
        """
        {
            "toolset_id": "memories",
            "tool_name": "get_relevant_memories",
            "description": "Get relevant memories based on the current agent's context.",
            "parameters": []
        }
        """
        pass

    def search_memories(self, query, n_results=3):
        """
        {
            "toolset_id": "memories",
            "tool_name": "search_memories",
            "description": "Search for long term memories based on a query.",
            "parameters": []
        }
        """
        # Embed the query
        query_embedding = embed_with_ollama(
            server_url=self.llm_server,
            text="search_query: " + query, # prefix for nomic-embed-text
            model=self.embedding_model
        )

        # Query the Chroma collection
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results
        )

        # Chroma returns a dict with "documents", "ids", "metadatas", "distances" (lists of lists)
        # e.g. results["documents"][0], results["metadatas"][0], results["distances"][0]
        retrieved = []
        if "documents" in results and len(results["documents"]) > 0:
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0]
            ):
                retrieved.append((doc, meta, dist))

        return retrieved


def main():
    memory = "This is a test memory"

    # Instantiate RagRepo with your settings
    # Adjust llm_server and embedding_model as needed
    rag_repo = RagMemory(
        repo_path="my_rag_repo",
        llm_server="http://localhost:5000",
        embedding_model="nomic-embed-text"
    )

    # Add the PDF to the vector store
    rag_repo.add_memory(memory)

    # Now test a query
    query_text = "memory"
    results = rag_repo.search(query_text, n_results=1)

    print("Top relevant chunks:")
    for idx, (chunk, meta, dist) in enumerate(results, 1):
        print(f"\n--- Result #{idx} (distance: {dist:.4f}) ---")
        print(f"Memory ID: {meta['memory_id']}, chunk index: {meta['chunk_index']}")
        print(chunk)


if __name__ == "__main__":
    main()
