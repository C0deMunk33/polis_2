import uuid
import os
import sys
import chromadb
from chromadb.config import Settings

from libs.common import convert_file, chunk_text, embed_with_ollama

import warnings
warnings.filterwarnings(action="ignore", message="unclosed", category=ResourceWarning)


class RagRepo:
    def __init__(self, repo_path, llm_server, embedding_model):
        self.repo_path = repo_path
        self.llm_server = llm_server
        self.embedding_model = embedding_model

        # Initialize the Chroma client in-memory (no persistence)
        self.chroma_client = chromadb.Client()

        # Create or load a collection
        self.collection = self.chroma_client.create_collection(name="rag_collection")

    def get_function_schemas(self):
        """
        returns list of function schemas
        """
        return [{
            "name": "search",
            "arguments": {
                "query": {
                    "type": "string",
                    "description": "The query to search for"
                }
            },
            "description": "Search the RAG repository for the most relevant chunks"
        },{
            "name": "add_files",
            "arguments": {
                "files": {
                    "type": "list",
                    "description": "The files to add to the RAG repository"
                }
            },
            "description": "Add files to the RAG repository"
        }]

    def add_files(self, files):
        """
        Convert, chunk, and embed each file, then store the vectors in Chroma.
        """
        for file in files:
            # Convert file to Markdown/text
            md_text = convert_file(file)

            # Chunk it up
            chunks = chunk_text(md_text, chunk_size=1024, overlap=100)

            # Embed each chunk and add to the collection
            for i, chunk in enumerate(chunks):
                embedding = embed_with_ollama(
                    server_url=self.llm_server,
                    text="search_document: " + chunk, # prefix for nomic-embed-text
                    model=self.embedding_model
                )

                # Use a unique ID for each chunk
                doc_id = f"{os.path.basename(file)}-{uuid.uuid4().hex[:8]}-{i}"

                self.collection.add(
                    documents=[chunk],
                    metadatas=[{"source_file": file, "chunk_index": i}],
                    ids=[doc_id],
                    embeddings=[embedding]
                )

    def search(self, query, n_results=3):
        """
        Embed the query, then retrieve the most relevant chunks from the in-memory vector DB.
        Returns a list of (chunk_text, metadata, distance).
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
    
    pdf_path = "test.pdf"
    if not os.path.isfile(pdf_path):
        print(f"File not found: {pdf_path}")
        sys.exit(1)

    # Instantiate RagRepo with your settings
    # Adjust llm_server and embedding_model as needed
    rag_repo = RagRepo(
        repo_path="my_rag_repo",
        llm_server="http://localhost:5000",
        embedding_model="nomic-embed-text"
    )

    # Add the PDF to the vector store
    rag_repo.add_files([pdf_path])

    # Now test a query
    query_text = "ex-situ stars"
    results = rag_repo.search(query_text, n_results=1)

    print("Top relevant chunks:")
    for idx, (chunk, meta, dist) in enumerate(results, 1):
        print(f"\n--- Result #{idx} (distance: {dist:.4f}) ---")
        print(f"Source file: {meta['source_file']}, chunk index: {meta['chunk_index']}")
        print(chunk)


if __name__ == "__main__":
    main()
