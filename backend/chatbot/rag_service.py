
import os
import time
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

# Your existing VectorDBManager
from .vector_db_manager import VectorDBManager  # Adjust import path

# LangChain imports
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser

logger = logging.getLogger(__name__)

class RAGService:
    """
    RAG (Retrieval-Augmented Generation) service that combines
    vector database retrieval with Gemini LLM generation
    """
    
    def __init__(self, 
                 google_api_key: str,
                 model_name: str = "gemini-2.5-flash",
                 vector_db_path: str = "./angelone_chroma_db",
                 collection_name: str = "angelone_support"):
        """
        Initialize RAG service
        
        Args:
            google_api_key: Google API key for Gemini
            model_name: Gemini model name
            vector_db_path: Path to ChromaDB
            collection_name: ChromaDB collection name
        """
        self.google_api_key = google_api_key
        self.model_name = model_name
        
        # Initialize vector database manager
        self.db_manager = VectorDBManager(
            persist_directory=vector_db_path,
            collection_name=collection_name
        )
        
        # Initialize Gemini LLM
        self.llm = self._initialize_llm()
        
        # Initialize retriever
        self.retriever = None
        self._initialize_retriever()
        
        # Create prompt template
        self.prompt_template = self._create_prompt_template()
        
        # Create chain
        self.chain = self.prompt_template | self.llm | StrOutputParser()
    
    def _initialize_llm(self) -> ChatGoogleGenerativeAI:
        """Initialize Gemini LLM"""
        try:
            return ChatGoogleGenerativeAI(
                model=self.model_name,
                google_api_key=self.google_api_key,
                temperature=0.1,
                convert_system_message_to_human=True
            )
        except Exception as e:
            logger.error(f"Error initializing Gemini LLM: {e}")
            raise
    
    def _initialize_retriever(self):
        """Initialize vector database retriever"""
        try:
            # Load existing vector store
            vector_store = self.db_manager.create_vector_store(force_recreate=False)
            if vector_store:
                self.retriever = self.db_manager.get_retriever(k=10)
                logger.info("Vector database retriever initialized successfully")
            else:
                logger.error("Failed to initialize vector database")
                raise Exception("Vector database initialization failed")
        except Exception as e:
            logger.error(f"Error initializing retriever: {e}")
            raise
    
    def _create_prompt_template(self) -> ChatPromptTemplate:
        """Create prompt template for RAG"""
        system_prompt = """You are a helpful AI assistant specifically designed to answer questions about Angel One trading platform and related services. You MUST follow these strict guidelines:

        LANGUAGE REQUIREMENTS:
        - Respond ONLY in English language
        - Never use Hindi, regional languages, or any non-English text
        - If you don't know something, say "I don't know" in English only

        KNOWLEDGE BOUNDARIES:
        - Answer questions ONLY based on the provided context from Angel One documentation
        - If the context does not contain relevant information to answer the question, respond with: "I don't know. This information is not available in the Angel One support documentation."
        - Do NOT use any external knowledge or general information outside the provided context
        - If a question is about topics unrelated to Angel One services (trading, account management, platform features, etc.), respond with: "I don't know. I can only help with Angel One trading platform and support-related questions."

        RESPONSE GUIDELINES:
        1. Be concise and accurate based only on the provided context
        2. If the context partially answers the question, provide what information is available and clearly state what is missing
        3. For account-specific or personal issues, advise users to contact Angel One customer support directly
        4. Focus on practical, actionable information from the documentation
        5. If discussing trading or financial matters, remind users to consider their risk tolerance when relevant

        PROVIDED CONTEXT:
        {context}

        USER QUESTION: {question}

        Remember: If you cannot find relevant information in the context above to answer the question, simply respond with "I don't know" followed by appropriate guidance about contacting support or specifying that the information is not available in the documentation."""
        
        return ChatPromptTemplate.from_template(system_prompt)

    def retrieve_documents(self, question: str, k: int = 10) -> List[Dict[str, Any]]:
        """
        Retrieve relevant documents for the question
        
        Args:
            question: User question
            k: Number of documents to retrieve
            
        Returns:
            List of relevant documents with metadata
        """
        if not self.retriever:
            raise Exception("Retriever not initialized")
        
        try:
            # Retrieve documents
            docs = self.retriever.invoke(question)
            
            # Format documents for return
            formatted_docs = []
            for doc in docs[:k]:
                formatted_docs.append({
                    'content': doc.page_content,
                    'source': doc.metadata.get('source', 'Unknown'),
                    'title': doc.metadata.get('title', 'Unknown'),
                    'source_type': doc.metadata.get('source_type', 'unknown'),
                    'chunk_id': doc.metadata.get('chunk_id', 'unknown'),
                    'content_length': len(doc.page_content)
                })
            
            return formatted_docs
            
        except Exception as e:
            logger.error(f"Error retrieving documents: {e}")
            return []
    
    def generate_answer(self, 
                   question: str, 
                   k: int = 10, 
                   temperature: float = 0.1) -> Dict[str, Any]:  # Lower temperature for more consistent responses
        """
        Generate answer using RAG pipeline
        """
        start_time = time.time()
        
        try:
            # Update LLM temperature (keep it low for consistency)
            self.llm.temperature = temperature
            
            # Retrieve relevant documents
            retrieved_docs = self.retrieve_documents(question, k)
            
            # Check if we have relevant documents
            if not retrieved_docs:
                return {
                    'question': question,
                    'answer': "I don't know. This information is not available in the Angel One support documentation. Please contact Angel One customer support at 1800-309-8800 for assistance.",
                    'sources': [],
                    'retrieval_count': 0,
                    'processing_time': time.time() - start_time,
                    'confidence': 'low'
                }
            
            # Check if the retrieved documents seem relevant (basic relevance check)
            # You can implement more sophisticated relevance checking here
            context = "\n\n".join([
                f"Source: {doc['source']}\nContent: {doc['content']}"
                for doc in retrieved_docs
            ])
            
            # Generate answer using the chain
            answer = self.chain.invoke({
                "context": context,
                "question": question
            })
            
            # Additional check: if the answer starts with "I don't know", maintain that response
            if answer.strip().lower().startswith("i don't know"):
                final_answer = answer.strip()
            else:
                final_answer = answer.strip()
            
            # Prepare sources for response
            sources = []
            for doc in retrieved_docs:
                sources.append({
                    'source': doc['source'],
                    'title': doc['title'],
                    'source_type': doc['source_type'],
                    'content_preview': doc['content'][:200] + "..." if len(doc['content']) > 200 else doc['content'],
                    'content_length': doc['content_length']
                })
            
            return {
                'question': question,
                'answer': final_answer,
                'sources': sources,
                'retrieval_count': len(retrieved_docs),
                'processing_time': time.time() - start_time,
                'confidence': 'medium' if len(retrieved_docs) >= 3 else 'low'
            }
            
        except Exception as e:
            logger.error(f"Error generating answer: {e}")
            return {
                'question': question,
                'answer': "I don't know. There was an error processing your question. Please contact Angel One customer support for assistance.",
                'sources': [],
                'retrieval_count': 0,
                'processing_time': time.time() - start_time,
                'error': str(e),
                'confidence': 'low'
            }

    def get_service_status(self) -> Dict[str, Any]:
        """Get status of RAG service components"""
        try:
            db_info = self.db_manager.get_collection_info()
            
            return {
                'vector_db_status': 'active' if self.retriever else 'inactive',
                'llm_status': 'active' if self.llm else 'inactive',
                'database_info': db_info,
                'model_name': self.model_name
            }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }