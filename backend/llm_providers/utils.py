"""
Utility classes and functions shared across LLM providers.

This module contains utilities that are used by multiple LLM providers,
such as Azure Search integration, response formatting helpers, and
common data processing functions.
"""

import logging
from typing import Any, Dict, List, Optional

from azure.search.documents.aio import SearchClient
from azure.core.credentials import AzureKeyCredential
from azure.identity.aio import DefaultAzureCredential

from backend.settings import app_settings
from backend.utils import generateFilterStringFromFullDef


class AzureSearchService:
    """
    Service to handle Azure Search queries for LLM providers.
    
    This service provides a unified interface for searching Azure Search indexes
    and retrieving relevant documents for LLM context. It's used by providers
    like Claude that need to augment responses with search results.
    
    Key features:
    - Connection management with automatic cleanup
    - Permission-based filtering
    - Multiple content field support
    - Semantic search capability
    """
    
    def __init__(self):
        """Initialize the Azure Search service."""
        self.search_client = None
        self.initialized = False
        self.logger = logging.getLogger(self.__class__.__name__)
    
    async def close(self):
        """Close the search client and clean up resources."""
        if self.search_client:
            try:
                await self.search_client.close()
                self.logger.debug("Azure Search client closed successfully")
            except Exception as e:
                self.logger.warning(f"Error closing search client: {e}")
            finally:
                self.search_client = None
                self.initialized = False
    
    async def search_documents(
        self, 
        query: str, 
        top_k: int = None, 
        filters: str = None, 
        user_permissions: str = None
    ) -> List[Dict[str, Any]]:
        """
        Search for documents relevant to the query.
        
        Args:
            query: The search query string
            top_k: Maximum number of documents to return
            filters: Additional OData filter string
            user_permissions: User permissions for document filtering
            
        Returns:
            List of documents with content, metadata, and relevance scores
            
        Note: This method creates a new client for each request to avoid
        session leaks and ensure proper resource management.
        """
        search_client = None
        
        try:
            # Validate Azure Search configuration
            if not app_settings.datasource:
                self.logger.warning("Azure Search not configured")
                return []
            
            # Debug logging for top_k parameter (using INFO to ensure visibility)
            self.logger.info(f"AzureSearchService: search_documents called with top_k parameter: {top_k}")
                
            search_service = app_settings.datasource.service
            search_index = app_settings.datasource.index
            search_key = app_settings.datasource.key
            
            if not search_service or not search_index:
                self.logger.warning("Azure Search not configured - service or index missing")
                return []
            
            # Build endpoint and credentials
            endpoint = f"https://{search_service}.search.windows.net"
            
            if search_key:
                credential = AzureKeyCredential(search_key)
            else:
                # Use managed identity if no key provided
                credential = DefaultAzureCredential()
            
            # Create search client for this request
            search_client = SearchClient(
                endpoint=endpoint,
                index_name=search_index,
                credential=credential
            )
            
            # Configure search parameters  
            if top_k is None:
                # Use datasource top_k configuration, with fallback to 5
                default_top_k = getattr(app_settings.datasource, 'top_k', 5)
                self.logger.info(f"AzureSearchService: Using default top_k from datasource: {default_top_k}")
                top_k = default_top_k
            
            search_params = {
                "search_text": query,
                "top": top_k,
                "include_total_count": True
            }
            
            self.logger.info(f"AzureSearchService: Final search top_k used: {top_k}")
            
            # Build and apply filters
            combined_filter = self._build_filters(filters, user_permissions)
            if combined_filter:
                search_params["filter"] = combined_filter
                self.logger.debug(f"Using combined filter: {combined_filter}")
            
            # Configure semantic search if available
            self._configure_semantic_search(search_params)
            
            self.logger.debug(f"Azure Search query: '{query}' with params: {search_params}")
            
            # Execute search
            results = await search_client.search(**search_params)
            
            # Process and return results
            documents = await self._process_search_results(results)
            self.logger.debug(f"Azure Search returned {len(documents)} documents")
            
            return documents
            
        except Exception as e:
            self.logger.error(f"Azure Search query failed: {e}")
            return []
        finally:
            # Always close the search client to prevent session leaks
            if search_client:
                try:
                    await search_client.close()
                except Exception as e:
                    self.logger.warning(f"Error closing search client: {e}")
    
    def _build_filters(
        self, 
        filters: Optional[str], 
        user_permissions: Optional[str]
    ) -> Optional[str]:
        """
        Build combined OData filter from user filters and permissions.
        
        Args:
            filters: Custom OData filter string
            user_permissions: User permissions for document access control
            
        Returns:
            Combined filter string or None if no filters needed
        """
        permission_filter = None
        
        # Generate permission-based filter if configured
        if (user_permissions and 
            hasattr(app_settings.datasource, 'permitted_groups_column') and 
            app_settings.datasource.permitted_groups_column):
            try:
                permission_filter = generateFilterStringFromFullDef(user_permissions)
                self.logger.debug(f"Generated permission filter: {permission_filter}")
            except Exception as e:
                self.logger.warning(f"Failed to generate permission filter: {e}")
        
        # Combine filters
        if permission_filter and filters:
            return f"({permission_filter}) and ({filters})"
        elif permission_filter:
            return permission_filter
        elif filters:
            return filters
        else:
            return None
    
    def _configure_semantic_search(self, search_params: Dict[str, Any]):
        """
        Configure semantic search parameters if available.
        
        Args:
            search_params: Dictionary of search parameters to modify
        """
        if (hasattr(app_settings.datasource, 'use_semantic_search') and 
            app_settings.datasource.use_semantic_search):
            if (hasattr(app_settings.datasource, 'semantic_search_config') and 
                app_settings.datasource.semantic_search_config):
                search_params["query_type"] = "semantic"
                search_params["semantic_configuration_name"] = app_settings.datasource.semantic_search_config
                self.logger.debug("Enabled semantic search")
    
    async def _process_search_results(self, results) -> List[Dict[str, Any]]:
        """
        Process raw search results into standardized document format.
        
        Args:
            results: Azure Search results iterator
            
        Returns:
            List of processed documents with standardized fields
        """
        documents = []
        
        async for result in results:
            # Extract document information
            doc = {
                "content": self._extract_content(result),
                "title": self._extract_field(result, app_settings.datasource.title_column),
                "url": self._extract_field(result, app_settings.datasource.url_column),
                "filename": self._extract_field(result, app_settings.datasource.filename_column),
                "score": result.get("@search.score", 0),
                "metadata": {
                    "id": result.get("id", ""),
                    "source": self._extract_field(result, app_settings.datasource.filename_column) or "Document"
                }
            }
            documents.append(doc)
        
        return documents
    
    def _extract_content(self, result: Dict[str, Any]) -> str:
        """
        Extract content from search result using configured content columns.
        
        Args:
            result: Single search result dictionary
            
        Returns:
            Extracted content as string
        """
        # Try configured content columns first
        content_columns = app_settings.datasource.content_columns or ["content", "merged_content"]
        
        for column in content_columns:
            if column in result:
                content = result[column]
                if isinstance(content, list):
                    return " ".join(str(item) for item in content)
                return str(content) if content else ""
        
        # Fallback: find any text field that looks like content
        for key, value in result.items():
            if isinstance(value, str) and len(value) > 50:
                return value
        
        return ""
    
    def _extract_field(self, result: Dict[str, Any], field_name: Optional[str]) -> Optional[str]:
        """
        Extract a specific field from search result.
        
        Args:
            result: Single search result dictionary
            field_name: Name of the field to extract
            
        Returns:
            Field value as string or None if not found
        """
        if not field_name or field_name not in result:
            return None
        
        value = result[field_name]
        if isinstance(value, list):
            return " ".join(str(item) for item in value)
        return str(value) if value else None


def create_citation_from_document(doc: Dict[str, Any], doc_id: int) -> Dict[str, Any]:
    """
    Create a citation object from a search document.
    
    Args:
        doc: Document dictionary from search results
        doc_id: Unique identifier for the document
        
    Returns:
        Citation dictionary compatible with frontend display
    """
    title = doc.get("title", f"Document {doc_id}")
    content = doc.get("content", "")
    
    return {
        "id": f"doc{doc_id}",
        "title": title,
        "content": content[:200] + "..." if len(content) > 200 else content,
        "url": doc.get("url", ""),
        "filepath": doc.get("filename", doc.get("metadata", {}).get("source", "Document")),
        "chunk_id": str(doc_id)
    }


def build_search_context(search_results: List[Dict[str, Any]]) -> tuple[str, List[Dict[str, Any]]]:
    """
    Build search context and citations from search results.
    
    Args:
        search_results: List of documents from Azure Search
        
    Returns:
        Tuple of (context_string, citations_list)
    """
    if not search_results:
        return "", []
    
    context_parts = []
    citations = []
    
    for i, doc in enumerate(search_results):
        doc_id = i + 1
        content = doc.get("content", "").strip()
        title = doc.get("title") or doc.get("filename") or f"Document {doc_id}"
        
        if content:
            # Limit content size to prevent Claude API errors (max ~8000 chars per doc)
            if len(content) > 8000:
                content = content[:7900] + "... [contenu tronqué]"
            
            # Add document to context
            context_parts.append(f"[doc{doc_id}] {title}\n{content}")
            
            # Create citation
            citation = create_citation_from_document(doc, doc_id)
            citations.append(citation)
    
    search_context = "\n\n".join(context_parts)
    return search_context, citations