import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import hashlib

# LangChain imports
from langchain.docstore.document import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_chroma import Chroma

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class VectorDBManager:
    """
    Simplified Vector Database Manager using only ChromaDB and HuggingFace embeddings
    Works with pre-processed data files to avoid re-scraping/re-processing
    """
    
    def __init__(self, 
                 embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
                 persist_directory: str = "./chroma_db",
                 collection_name: str = "angelone_support"):
        """
        Initialize the Vector Database Manager
        
        Args:
            embedding_model: HuggingFace sentence transformer model name
            persist_directory: Directory to persist ChromaDB
            collection_name: Name of the collection in ChromaDB
        """
        self.persist_directory = Path(persist_directory)
        self.collection_name = collection_name
        
        # Create persist directory if it doesn't exist
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        
        # Initialize embeddings (only HuggingFace)
        self.embeddings = self._initialize_embeddings(embedding_model)
        
        # Initialize vector store
        self.vector_store = None
        self.documents = []
        
        # Text splitter configuration
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        
    def _initialize_embeddings(self, embedding_model: str) -> HuggingFaceEmbeddings:
        """Initialize HuggingFace embedding model"""
        try:
            logger.info(f"Initializing HuggingFace embeddings: {embedding_model}")
            return HuggingFaceEmbeddings(
                model_name=embedding_model,
                model_kwargs={
                    'device': 'cpu',
                    'trust_remote_code': False
                },
                encode_kwargs={'normalize_embeddings': True}
            )
        except Exception as e:
            logger.error(f"Error initializing embeddings: {e}")
            logger.info("Falling back to default model: sentence-transformers/all-MiniLM-L6-v2")
            return HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2",
                model_kwargs={'device': 'cpu'},
                encode_kwargs={'normalize_embeddings': True}
            )
    
    def load_web_data(self, json_file: str = "chatbot/angelone_support_pages.json") -> List[Document]:
        """
        Load and process pre-scraped web data from JSON file
        
        Args:
            json_file: Path to the JSON file containing scraped web data
            
        Returns:
            List of Document objects with chunks
        """
        try:
            if not os.path.exists(json_file):
                logger.error(f"Web data file {json_file} not found!")
                return []
                
            logger.info(f"Loading web data from {json_file}")
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Handle the nested structure with crawl_info and support_pages
            if isinstance(data, dict):
                if 'support_pages' in data:
                    web_data = data['support_pages']
                    # Log crawl info if available
                    if 'crawl_info' in data:
                        crawl_info = data['crawl_info']
                        logger.info(f"Crawl info - Total pages: {crawl_info.get('total_pages_scraped', 'Unknown')}, "
                                   f"Content size: {crawl_info.get('total_content_size', 'Unknown')} chars")
                elif 'pages' in data:
                    web_data = data['pages']
                else:
                    # Assume the entire dict is the data
                    web_data = [data] if not isinstance(data, list) else data
            else:
                # If it's already a list
                web_data = data
            
            logger.info(f"Found {len(web_data)} web pages to process")
            
            web_documents = []
            processed_count = 0
            skipped_count = 0
            
            for item in web_data:
                # Handle both string content and dict content
                if isinstance(item, str):
                    logger.warning(f"Skipping string item (not a dict): {item[:50]}...")
                    skipped_count += 1
                    continue
                    
                if not isinstance(item, dict):
                    logger.warning(f"Skipping non-dict item: {type(item)}")
                    skipped_count += 1
                    continue
                
                content = item.get('content', '')
                if not content or not content.strip():
                    logger.warning(f"Skipping item with empty content: {item.get('url', 'Unknown URL')}")
                    skipped_count += 1
                    continue
                
                # Create document with metadata
                doc = Document(
                    page_content=content,
                    metadata={
                        'source': item.get('url', 'Unknown'),
                        'title': item.get('title', 'Unknown Title'),
                        'source_type': item.get('source_type', 'web'),
                        'timestamp': item.get('timestamp', 0),
                        'content_length': item.get('content_length', len(content))
                    }
                )
                
                # Split into chunks if content is long enough
                if len(content) > 500:  # Only split if content is substantial
                    chunks = self.text_splitter.split_documents([doc])
                else:
                    chunks = [doc]  # Keep as single chunk if small
                
                # Add enhanced metadata to chunks
                url_hash = hashlib.md5(item.get('url', '').encode()).hexdigest()[:8]
                for i, chunk in enumerate(chunks):
                    chunk.metadata.update({
                        'chunk_id': f"web_{url_hash}_{i}",
                        'chunk_index': i,
                        'total_chunks': len(chunks),
                        'chunk_content_length': len(chunk.page_content)
                    })
                
                web_documents.extend(chunks)
                processed_count += 1
            
            logger.info(f"Successfully processed {processed_count} web pages, skipped {skipped_count}")
            logger.info(f"Created {len(web_documents)} chunks from web data")
            return web_documents
            
        except Exception as e:
            logger.error(f"Error loading web data: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return []
    
    def _validate_json_structure(self, data: Any, data_type: str) -> bool:
        """
        Validate the structure of loaded JSON data
        
        Args:
            data: The loaded JSON data
            data_type: Type of data ("web" or "pdf")
            
        Returns:
            True if structure is valid, False otherwise
        """
        try:
            if data_type == "web":
                if isinstance(data, dict):
                    if 'support_pages' in data:
                        return isinstance(data['support_pages'], list)
                    elif 'pages' in data:
                        return isinstance(data['pages'], list)
                    else:
                        return False
                elif isinstance(data, list):
                    return len(data) > 0
                else:
                    return False
                    
            elif data_type == "pdf":
                if isinstance(data, list):
                    return len(data) > 0
                elif isinstance(data, dict):
                    return 'documents' in data and isinstance(data['documents'], list)
                else:
                    return False
                    
            return False
            
        except Exception as e:
            logger.error(f"Error validating {data_type} data structure: {e}")
            return False
    def load_pdf_data(self, json_file: str = "chatbot/processed_documents.json") -> List[Document]:
        """
        Load and process pre-processed PDF data from JSON file
        
        Args:
            json_file: Path to the JSON file containing processed PDF data
            
        Returns:
            List of Document objects
        """
        try:
            if not os.path.exists(json_file):
                logger.error(f"PDF data file {json_file} not found!")
                return []
                
            logger.info(f"Loading PDF data from {json_file}")
            with open(json_file, 'r', encoding='utf-8') as f:
                pdf_data = json.load(f)
            
            # Validate data structure
            if not self._validate_json_structure(pdf_data, "pdf"):
                logger.error("Invalid PDF data structure")
                return []
            
            pdf_documents = []
            
            # Handle different JSON structure possibilities
            if isinstance(pdf_data, list):
                # If it's a list of documents
                processed_data = pdf_data
            elif isinstance(pdf_data, dict) and 'documents' in pdf_data:
                # If it's wrapped in a documents key
                processed_data = pdf_data['documents']
            else:
                logger.error("Unexpected PDF data structure")
                return []
            
            logger.info(f"Processing {len(processed_data)} PDF documents")
            
            processed_count = 0
            skipped_count = 0
            
            for item in processed_data:
                if not isinstance(item, dict):
                    logger.warning(f"Skipping non-dict PDF item: {type(item)}")
                    skipped_count += 1
                    continue
                    
                content = item.get('content', '')
                if not content or not content.strip():
                    logger.warning(f"Skipping PDF item with empty content: {item.get('source', 'Unknown')}")
                    skipped_count += 1
                    continue
                
                # Create document
                doc = Document(
                    page_content=content,
                    metadata={
                        'source': item.get('source', item.get('file_name', 'Unknown')),
                        'source_type': 'pdf',
                        'page_number': item.get('page_number', 0),
                        'file_name': item.get('file_name', 'Unknown'),
                        'timestamp': item.get('timestamp', 0)
                    }
                )
                
                # For PDFs, we might want to split large pages into smaller chunks
                if len(doc.page_content) > 1500:  # Split large PDF pages
                    chunks = self.text_splitter.split_documents([doc])
                    
                    # Add chunk metadata
                    file_hash = hashlib.md5(item.get('source', '').encode()).hexdigest()[:8]
                    for i, chunk in enumerate(chunks):
                        chunk.metadata.update({
                            'chunk_id': f"pdf_{file_hash}_p{item.get('page_number', 0)}_{i}",
                            'chunk_index': i,
                            'total_chunks': len(chunks),
                            'chunk_content_length': len(chunk.page_content)
                        })
                    
                    pdf_documents.extend(chunks)
                else:
                    # Add metadata for single chunk
                    file_hash = hashlib.md5(item.get('source', '').encode()).hexdigest()[:8]
                    doc.metadata.update({
                        'chunk_id': f"pdf_{file_hash}_p{item.get('page_number', 0)}_0",
                        'chunk_index': 0,
                        'total_chunks': 1,
                        'chunk_content_length': len(doc.page_content)
                    })
                    pdf_documents.append(doc)
                
                processed_count += 1
            
            logger.info(f"Successfully processed {processed_count} PDF documents, skipped {skipped_count}")
            logger.info(f"Created {len(pdf_documents)} document chunks from PDF data")
            return pdf_documents
            
        except Exception as e:
            logger.error(f"Error loading PDF data: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return []
    
    def create_vector_store(self, 
                          web_data_file: str = "chatbot/angelone_support_pages.json",
                          pdf_data_file: str = "chatbot/processed_documents.json",
                          force_recreate: bool = False) -> Optional[Chroma]:
        """
        Create or load ChromaDB vector store with all documents
        
        Args:
            web_data_file: Path to web data JSON file
            pdf_data_file: Path to PDF data JSON file  
            force_recreate: Whether to recreate the database even if it exists
            
        Returns:
            ChromaDB vector store instance
        """
        try:
            # Check if database already exists and force_recreate is False
            if not force_recreate and self._database_exists():
                logger.info("Loading existing ChromaDB...")
                self.vector_store = Chroma(
                    collection_name=self.collection_name,
                    embedding_function=self.embeddings,
                    persist_directory=str(self.persist_directory)
                )
                logger.info("Existing ChromaDB loaded successfully")
                return self.vector_store
            
            # Load all documents from pre-processed files
            logger.info("Loading data from pre-processed files...")
            web_docs = self.load_web_data(web_data_file)
            pdf_docs = self.load_pdf_data(pdf_data_file)
            
            all_documents = web_docs + pdf_docs
            self.documents = all_documents
            
            if not all_documents:
                logger.error("No documents found to create vector store!")
                return None
            
            logger.info(f"Total documents to index: {len(all_documents)}")
            logger.info(f"Web documents: {len(web_docs)}, PDF documents: {len(pdf_docs)}")
            
            # Create new ChromaDB
            if force_recreate and self._database_exists():
                logger.info("Removing existing database...")
                self._remove_existing_database()
            
            logger.info("Creating new ChromaDB vector store...")
            self.vector_store = Chroma.from_documents(
                documents=all_documents,
                embedding=self.embeddings,
                collection_name=self.collection_name,
                persist_directory=str(self.persist_directory)
            )
            
            logger.info(f"Vector store created successfully with {len(all_documents)} documents")
            return self.vector_store
            
        except Exception as e:
            logger.error(f"Error creating vector store: {e}")
            return None
    
    def _database_exists(self) -> bool:
        """Check if ChromaDB database already exists"""
        chroma_sqlite = self.persist_directory / "chroma.sqlite3"
        return chroma_sqlite.exists()
    
    def _remove_existing_database(self):
        """Remove existing ChromaDB database"""
        import shutil
        if self.persist_directory.exists():
            shutil.rmtree(self.persist_directory)
            self.persist_directory.mkdir(parents=True, exist_ok=True)
    
    def search_similar(self, query: str, k: int = 5) -> List[Document]:
        """
        Search for similar documents
        
        Args:
            query: Search query
            k: Number of results to return
            
        Returns:
            List of similar documents
        """
        if not self.vector_store:
            logger.error("Vector store not initialized!")
            return []
        
        try:
            results = self.vector_store.similarity_search(query, k=k)
            logger.info(f"Found {len(results)} similar documents for query: '{query[:50]}...'")
            return results
        except Exception as e:
            logger.error(f"Error searching: {e}")
            return []
    
    def search_with_score(self, query: str, k: int = 5) -> List[tuple]:
        """
        Search for similar documents with similarity scores
        
        Args:
            query: Search query
            k: Number of results to return
            
        Returns:
            List of tuples (document, score)
        """
        if not self.vector_store:
            logger.error("Vector store not initialized!")
            return []
        
        try:
            results = self.vector_store.similarity_search_with_score(query, k=k)
            logger.info(f"Found {len(results)} similar documents with scores for query: '{query[:50]}...'")
            return results
        except Exception as e:
            logger.error(f"Error searching with score: {e}")
            return []
    
    def get_retriever(self, k: int = 5):
        """
        Get a retriever object for RAG applications
        
        Args:
            k: Number of documents to retrieve
            
        Returns:
            ChromaDB retriever object
        """
        if not self.vector_store:
            logger.error("Vector store not initialized!")
            return None
        
        return self.vector_store.as_retriever(
            search_type="similarity",
            search_kwargs={"k": k}
        )
    
    def add_documents(self, documents: List[Document]) -> bool:
        """
        Add new documents to the vector store
        
        Args:
            documents: List of documents to add
            
        Returns:
            True if successful, False otherwise    
        """
        if not self.vector_store:
            logger.error("Vector store not initialized!")
            return False
        
        try:
            self.vector_store.add_documents(documents)
            logger.info(f"Added {len(documents)} documents to vector store")
            return True
            
        except Exception as e:
            logger.error(f"Error adding documents: {e}")
            return False
    
    def get_collection_info(self) -> Dict[str, Any]:
        """Get information about the vector store collection"""
        if not self.vector_store:
            return {"status": "Vector store not initialized"}
        
        try:
            collection = self.vector_store._collection
            count = collection.count()
            
            return {
                "database_type": "ChromaDB",
                "collection_name": self.collection_name,
                "document_count": count,
                "persist_directory": str(self.persist_directory),
                "embedding_model": self.embeddings.model_name,
                "status": "active"
            }
        except Exception as e:
            return {"error": str(e), "status": "error"}
    
    def delete_collection(self) -> bool:
        """Delete the entire vector store collection"""
        try:
            if self.persist_directory.exists():
                import shutil
                shutil.rmtree(self.persist_directory)
                logger.info("ChromaDB database deleted")
            
            self.vector_store = None
            self.documents = []
            return True
            
        except Exception as e:
            logger.error(f"Error deleting collection: {e}")
            return False

def main():
    """Main function to test vector database operations"""
    print("=== Improved Vector Database Manager Test ===")
    
    # Initialize the manager
    db_manager = VectorDBManager(
        embedding_model="sentence-transformers/all-MiniLM-L6-v2",
        persist_directory="./angelone_chroma_db",
        collection_name="angelone_support"
    )
    
    try:
        # Create vector store from pre-processed data
        print("\n1. Creating vector store from pre-processed data...")
        vector_store = db_manager.create_vector_store(
            web_data_file="angelone_support_pages.json",
            pdf_data_file="processed_documents.json",
            force_recreate=False  # Set to True if you want to recreate
        )
        
        if vector_store:
            # Get collection info
            print("\n2. Collection info:")
            info = db_manager.get_collection_info()
            for key, value in info.items():
                print(f"   {key}: {value}")
            
            

            
            # Test retriever for RAG
            print("\n5. Testing retriever for RAG...")
            retriever = db_manager.get_retriever(k=10)
            if retriever:
                print("   Retriever created successfully - ready for RAG implementation!")
                
                # Example of how to use retriever
                retrieved_docs = retriever.invoke("trading charges and fees")
                print(f"   Retrieved {len(retrieved_docs)} documents for RAG context")
        
        else:
            print("❌ Failed to create vector store")
            print("Please ensure the following files exist:")
            print("- angelone_support_pages.json (web scraped data)")
            print("- processed_documents.json (processed PDF data)")
            
    except Exception as e:
        logger.error(f"Error in main: {e}")

if __name__ == "__main__":
    main()