import json
import logging
import time
import httpx
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, Any, Optional, List
from openai import AsyncAzureOpenAI
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from azure.search.documents.aio import SearchClient
from azure.core.credentials import AzureKeyCredential

from backend.settings import app_settings
from backend.utils import generateFilterStringFromFullDef


class AzureSearchService:
    """Service to handle Azure Search queries for Claude"""
    
    def __init__(self):
        self.search_client = None
        self.initialized = False
    
    async def close(self):
        """Close the search client and clean up resources"""
        if self.search_client:
            await self.search_client.close()
            self.search_client = None
            self.initialized = False
    
    
    async def search_documents(self, query: str, top_k: int = None, filters: str = None, user_permissions: str = None) -> List[Dict[str, Any]]:
        """Search for documents relevant to the query"""
        # Create a new client for this request to avoid session leaks
        search_client = None
        
        try:
            # Get Azure Search settings
            if not app_settings.datasource:
                logging.warning("Azure Search not configured")
                return []
                
            search_service = app_settings.datasource.service
            search_index = app_settings.datasource.index
            search_key = app_settings.datasource.key
            
            if not search_service or not search_index:
                logging.warning("Azure Search not configured - search service or index missing")
                return []
                
            # Build endpoint
            endpoint = f"https://{search_service}.search.windows.net"
            
            # Create credentials
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
            # Use top_k from parameters or default from settings
            if top_k is None:
                top_k = app_settings.datasource.top_k or 5
            
            # Build search parameters
            search_params = {
                "search_text": query,
                "top": top_k,
                "include_total_count": True
            }
            
            # Build permission-based filter
            permission_filter = None
            if user_permissions and hasattr(app_settings.datasource, 'permitted_groups_column') and app_settings.datasource.permitted_groups_column:
                try:
                    permission_filter = generateFilterStringFromFullDef(user_permissions)
                    logging.debug(f"Generated permission filter: {permission_filter}")
                except Exception as e:
                    logging.warning(f"Failed to generate permission filter: {e}")
            
            # Combine filters
            combined_filter = None
            if permission_filter and filters:
                combined_filter = f"({permission_filter}) and ({filters})"
            elif permission_filter:
                combined_filter = permission_filter
            elif filters:
                combined_filter = filters
            
            # Add filter if provided
            if combined_filter:
                search_params["filter"] = combined_filter
                logging.debug(f"Using combined filter: {combined_filter}")
            
            # Add semantic search if configured
            if hasattr(app_settings.datasource, 'use_semantic_search') and app_settings.datasource.use_semantic_search:
                if hasattr(app_settings.datasource, 'semantic_search_config') and app_settings.datasource.semantic_search_config:
                    search_params["query_type"] = "semantic"
                    search_params["semantic_configuration_name"] = app_settings.datasource.semantic_search_config
            
            logging.debug(f"Azure Search query: {query} with params: {search_params}")
            
            # Execute search
            results = await search_client.search(**search_params)
            
            # Process results
            documents = []
            async for result in results:
                # Extract content and metadata
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
            
            logging.debug(f"Azure Search returned {len(documents)} documents")
            return documents
            
        except Exception as e:
            logging.error(f"Azure Search query failed: {e}")
            return []
        finally:
            # Always close the search client to prevent session leaks
            if search_client:
                try:
                    await search_client.close()
                except Exception as e:
                    logging.warning(f"Error closing search client: {e}")
    
    def _extract_content(self, result: Dict[str, Any]) -> str:
        """Extract content from search result"""
        # Try different content fields
        content_columns = app_settings.datasource.content_columns or ["content", "merged_content"]
        
        for column in content_columns:
            if column in result:
                content = result[column]
                if isinstance(content, list):
                    return " ".join(str(item) for item in content)
                return str(content) if content else ""
        
        # Fallback to any text field
        for key, value in result.items():
            if isinstance(value, str) and len(value) > 50:  # Assume it's content if it's a long string
                return value
        
        return ""
    
    def _extract_field(self, result: Dict[str, Any], field_name: Optional[str]) -> Optional[str]:
        """Extract a specific field from search result"""
        if not field_name or field_name not in result:
            return None
        
        value = result[field_name]
        if isinstance(value, list):
            return " ".join(str(item) for item in value)
        return str(value) if value else None


class MockAzureOpenAIResponse:
    """Mock class to make Claude responses compatible with Azure OpenAI format functions"""
    def __init__(self, response_dict):
        self.id = response_dict.get("id")
        self.model = response_dict.get("model")
        self.created = response_dict.get("created")
        self.object = response_dict.get("object")
        self.choices = [MockChoice(choice) for choice in response_dict.get("choices", [])]
        
class MockChoice:
    def __init__(self, choice_dict):
        self.message = MockMessage(choice_dict.get("message", {}))
        self.delta = MockMessage(choice_dict.get("delta", {}))
        
        # For Claude streaming: if delta is empty but message has content, 
        # copy message content to delta so format_stream_response finds it
        if not self.delta.content and self.message.content:
            self.delta.role = self.message.role
            self.delta.content = self.message.content
        
class MockMessage:
    def __init__(self, message_dict):
        self.role = message_dict.get("role")
        self.content = message_dict.get("content")
        # Azure OpenAI specific attributes that Claude doesn't have
        self.tool_calls = message_dict.get("tool_calls")  # None for Claude
        self.context = message_dict.get("context")  # None for Claude
        self.function_call = message_dict.get("function_call")  # None for Claude


class LLMProvider(ABC):
    """Abstract base class for LLM providers"""
    
    @abstractmethod
    async def send_request(self, messages: List[Dict[str, Any]], stream: bool = True, **kwargs) -> Any:
        """Send a request to the LLM provider"""
        pass
    
    @abstractmethod
    def format_response(self, raw_response: Any, stream: bool = True) -> Dict[str, Any]:
        """Format the raw response to match Azure OpenAI format"""
        pass


class AzureOpenAIProvider(LLMProvider):
    """Azure OpenAI provider implementation"""
    
    def __init__(self):
        self.client = None
        self.initialized = False
    
    async def init_client(self):
        """Initialize Azure OpenAI client"""
        if self.initialized:
            return
            
        try:
            if app_settings.base_settings.auth_enabled and not app_settings.azure_openai.key:
                async with DefaultAzureCredential() as credential:
                    token_provider = get_bearer_token_provider(
                        credential, "https://cognitiveservices.azure.com/.default"
                    )
            else:
                token_provider = None

            self.client = AsyncAzureOpenAI(
                api_version=app_settings.azure_openai.preview_api_version,
                api_key=app_settings.azure_openai.key,
                azure_ad_token_provider=token_provider,
                default_headers={"x-ms-useragent": "GitHubSampleWebApp/AsyncAzureOpenAI/1.0.0"},
                azure_endpoint=app_settings.azure_openai.endpoint
            )
            self.initialized = True
        except Exception as e:
            logging.exception("Exception in Azure OpenAI initialization", e)
            raise e
    
    async def send_request(self, messages: List[Dict[str, Any]], stream: bool = True, **kwargs) -> Any:
        """Send request to Azure OpenAI"""
        await self.init_client()
        
        # Extract Azure-specific parameters
        model_args = {
            "messages": messages,
            "temperature": kwargs.get("temperature", app_settings.azure_openai.temperature),
            "max_tokens": kwargs.get("max_tokens", app_settings.azure_openai.max_tokens),
            "top_p": kwargs.get("top_p", app_settings.azure_openai.top_p),
            "stop": kwargs.get("stop", app_settings.azure_openai.stop_sequence),
            "stream": stream,
            "model": kwargs.get("model", app_settings.azure_openai.model),
            "user": kwargs.get("user"),
        }
        
        # Add optional parameters
        if "tools" in kwargs:
            model_args["tools"] = kwargs["tools"]
        if "extra_body" in kwargs:
            model_args["extra_body"] = kwargs["extra_body"]
            
        raw_response = await self.client.chat.completions.with_raw_response.create(**model_args)
        response = raw_response.parse()
        apim_request_id = raw_response.headers.get("apim-request-id")
        
        return response, apim_request_id
    
    def format_response(self, raw_response: Any, stream: bool = True) -> Dict[str, Any]:
        """Azure OpenAI responses are already in the correct format"""
        return raw_response


class ClaudeProvider(LLMProvider):
    """Claude AI provider implementation"""
    
    def __init__(self):
        self.api_key = None
        self.model = None
        self.api_url = "https://api.anthropic.com/v1/messages"
        self.initialized = False
        self.search_service = AzureSearchService()
    
    async def init_client(self):
        """Initialize Claude provider with settings"""
        if self.initialized:
            return
            
        # Get Claude-specific settings from app_settings
        self.api_key = app_settings.claude.api_key
        self.model = app_settings.claude.model
        
        if not self.api_key:
            raise ValueError("CLAUDE_API_KEY environment variable is required")
            
        self.initialized = True
    
    async def send_request(self, messages: List[Dict[str, Any]], stream: bool = True, **kwargs) -> Any:
        """Send request to Claude API"""
        await self.init_client()
        
        # Reset citation flags for new request
        if hasattr(self, '_citations_sent'):
            delattr(self, '_citations_sent')
        if hasattr(self, '_current_search_citations'):
            delattr(self, '_current_search_citations')
        
        # Convert messages format from OpenAI to Claude
        claude_messages = self._convert_messages_to_claude_format(messages)
        
        # Perform Azure Search if datasource is configured
        if app_settings.datasource:
            logging.debug(f"Azure Search datasource is configured: {app_settings.datasource.service}/{app_settings.datasource.index}")
            if len(claude_messages) > 0:
                user_query = self._extract_user_query(claude_messages)
                logging.debug(f"Extracted user query for search: '{user_query}'")
                if user_query:
                    # Get documents count from kwargs (passed from customization preferences)
                    documents_count = kwargs.get("documents_count")
                    search_filters = kwargs.get("search_filters")
                    user_permissions = kwargs.get("user_permissions")
                    
                    # Search for relevant documents
                    search_results = await self.search_service.search_documents(
                        query=user_query,
                        top_k=documents_count,
                        filters=search_filters,
                        user_permissions=kwargs.get("user_permissions")
                    )
                    
                    
                    
                    # Inject search results into Claude messages
                    if search_results:
                        claude_messages = self._inject_search_context(claude_messages, search_results)
                    else:
                        logging.warning("No search results found, Claude will respond with native knowledge")
                else:
                    logging.warning("No user query extracted for search")
            else:
                logging.warning("No Claude messages to process for search")
        else:
            logging.debug("No Azure Search datasource configured")
        
        # Extract Claude-compatible parameters
        request_body = {
            "model": self.model,
            "messages": claude_messages,
            "max_tokens": kwargs.get("max_tokens", app_settings.claude.max_tokens),
            "temperature": kwargs.get("temperature", app_settings.claude.temperature)
        }
        
        # Explicitly set streaming behavior
        request_body["stream"] = stream
        
        # Add optional parameters
        if kwargs.get("top_p"):
            request_body["top_p"] = kwargs["top_p"]
        if kwargs.get("stop"):
            request_body["stop_sequences"] = kwargs["stop"] if isinstance(kwargs["stop"], list) else [kwargs["stop"]]
        
        # Debug logging
        logging.debug(f"Claude API Request Body: {request_body}")
        logging.debug(f"Original messages count: {len(messages)}, Claude messages count: {len(claude_messages)}")
        
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key,
            "anthropic-version": "2023-06-01"
        }
        
        if stream:
            # For streaming requests, return a generator that manages its own client
            return self._create_streaming_generator(request_body, headers), None
        else:
            # For non-streaming requests, parse as JSON
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.api_url,
                    json=request_body,
                    headers=headers,
                    timeout=300.0
                )
                
                # Debug logging
                logging.debug(f"Claude API Response Status: {response.status_code}")
                logging.debug(f"Claude API Response Headers: {dict(response.headers)}")
                logging.debug(f"Claude API Response Content Length: {len(response.content)}")
                logging.debug(f"Claude API Response Content: {response.content[:500]}...")
                
                response.raise_for_status()
                
                if len(response.content) == 0:
                    raise ValueError("Claude API returned empty response")
                
                try:
                    response_json = response.json()
                    logging.debug(f"Parsed Claude response: {type(response_json)}")
                    return response_json, None
                except Exception as e:
                    logging.error(f"Failed to parse Claude response as JSON: {e}")
                    logging.error(f"Raw response content: {response.content}")
                    raise
    
    def _convert_messages_to_claude_format(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert OpenAI message format to Claude format"""
        claude_messages = []
        system_message = None
        
        for msg in messages:
            if msg["role"] == "system":
                # Claude handles system messages differently
                system_message = msg["content"]
            elif msg["role"] in ["user", "assistant"]:
                claude_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            # Skip function/tool messages for now as Claude handles them differently
            
        # If there's a system message, prepend it to the first user message
        if system_message and claude_messages:
            if claude_messages[0]["role"] == "user":
                claude_messages[0]["content"] = f"{system_message}\n\n{claude_messages[0]['content']}"
        
        return claude_messages
    
    def _extract_user_query(self, claude_messages: List[Dict[str, Any]]) -> Optional[str]:
        """Extract the user's query from Claude messages for search"""
        # Get the last user message as the search query
        for msg in reversed(claude_messages):
            if msg.get("role") == "user":
                return msg.get("content", "")
        return None
    
    def _inject_search_context(self, claude_messages: List[Dict[str, Any]], search_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Inject Azure Search results into Claude message context"""
        if not search_results:
            return claude_messages
        
        # Build context from search results
        context_parts = []
        citations = []
        
        for i, doc in enumerate(search_results):
            doc_id = i + 1
            content = doc.get("content", "").strip()
            title = doc.get("title", f"Document {doc_id}")
            source = doc.get("filename", doc.get("metadata", {}).get("source", "Document"))
            url = doc.get("url", "")
            
            if content:
                # Add document to context
                context_parts.append(f"[doc{doc_id}] {title}\n{content}")
                
                # Build citation
                citation = {
                    "id": f"doc{doc_id}",
                    "title": title,
                    "content": content[:200] + "..." if len(content) > 200 else content,
                    "url": url,
                    "filepath": source,
                    "chunk_id": str(doc_id)
                }
                citations.append(citation)
        
        if not context_parts:
            return claude_messages
        
        # Build the enhanced system message
        search_context = "\n\n".join(context_parts)
        
        # Get system message from configuration
        base_system_message = app_settings.claude.system_message
        
        enhanced_system_message = f"""{base_system_message}

Documents disponibles :
{search_context}"""

        # Store citations for later use in response formatting
        self._current_search_citations = citations
        
        # Update the first user message to include the enhanced system message
        updated_messages = claude_messages.copy()
        if updated_messages and updated_messages[0].get("role") == "user":
            updated_messages[0]["content"] = f"{enhanced_system_message}\n\nQuestion de l'utilisateur : {updated_messages[0]['content']}"
        else:
            # If no user message, prepend as a system instruction
            updated_messages.insert(0, {
                "role": "user",
                "content": f"{enhanced_system_message}\n\nVeuillez m'aider avec la question suivante."
            })
        
        return updated_messages
    
    async def _create_streaming_generator(self, request_body: Dict[str, Any], headers: Dict[str, str]) -> AsyncGenerator:
        """Create a streaming generator that manages its own HTTP client"""
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                self.api_url,
                json=request_body,
                headers=headers,
                timeout=300.0
            ) as response:
                logging.debug(f"Claude API Stream Response Status: {response.status_code}")
                response.raise_for_status()
                
                async for chunk in self._stream_claude_response(response):
                    yield chunk
    
    async def _stream_claude_response(self, response: httpx.Response) -> AsyncGenerator:
        """Convert Claude streaming response to OpenAI format"""
        first_content_chunk = True
        citations_sent = False
        
        async for line in response.aiter_lines():
            line = line.strip()
            if line.startswith("data: "):
                data = line[6:]
                if data == "[DONE]":
                    break
                    
                try:
                    chunk = json.loads(data)
                    logging.debug(f"Claude streaming chunk: {chunk}")
                    
                    # Convert Claude chunk to OpenAI format based on event type
                    if chunk.get("type") == "content_block_delta":
                        # This contains the actual text content
                        text_content = chunk.get("delta", {}).get("text")
                        if text_content:
                            if first_content_chunk:
                                
                                # Send citations in a separate chunk BEFORE the first content
                                if (hasattr(self, '_current_search_citations') and 
                                    self._current_search_citations and 
                                    not citations_sent):
                                    
                                    citations_chunk = self._create_citations_chunk()
                                    yield citations_chunk
                                    citations_sent = True
                                
                                first_content_chunk = False
                            
                            yield self._format_streaming_chunk(chunk)
                    elif chunk.get("type") == "content_block_start":
                        # Initial content block
                        logging.debug("Claude content block started")
                    elif chunk.get("type") == "message_delta":
                        # Message metadata changes
                        logging.debug("Claude message delta")
                    elif chunk.get("type") == "message_stop":
                        # End of message
                        logging.debug("Claude message stopped")
                        break
                        
                except json.JSONDecodeError as e:
                    logging.warning(f"Failed to parse Claude streaming data: {e}, data: {data}")
                    continue
    
    def _create_citations_chunk(self) -> 'MockAzureOpenAIResponse':
        """Create a separate chunk for citations only"""
        citations_context = {
            "citations": self._current_search_citations,
            "intent": "Azure Search results"
        }
        
        delta_obj = {
            "context": citations_context
        }
        
        chunk_dict = {
            "id": f"chatcmpl-{int(time.time())}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": self.model,
            "choices": [{
                "index": 0,
                "delta": delta_obj,
                "finish_reason": None
            }]
        }
        
        return MockAzureOpenAIResponse(chunk_dict)
    
    def _format_streaming_chunk(self, claude_chunk: Dict[str, Any]) -> 'MockAzureOpenAIResponse':
        """Format Claude streaming chunk to match OpenAI format"""
        delta_obj = {
            "role": "assistant",
            "content": claude_chunk.get("delta", {}).get("text", "")
        }
        
        chunk_dict = {
            "id": f"chatcmpl-{int(time.time())}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": self.model,
            "choices": [{
                "index": 0,
                "delta": delta_obj,
                "finish_reason": None
            }]
        }
        
        # Return a MockAzureOpenAIResponse object that's compatible with format_stream_response
        return MockAzureOpenAIResponse(chunk_dict)
    
    def format_response(self, raw_response: Any, stream: bool = True) -> Dict[str, Any]:
        """Format Claude response to match Azure OpenAI format"""
        if stream:
            # For streaming responses, return the generator as-is
            # Individual chunks are already formatted by _format_streaming_chunk
            return raw_response
        
        # Format non-streaming response
        claude_response = raw_response
        logging.debug(f"Formatting Claude response: {claude_response}")
        
        # Extract text content from Claude response
        content = ""
        if isinstance(claude_response.get("content"), list):
            for item in claude_response["content"]:
                if item.get("type") == "text":
                    content += item.get("text", "")
        else:
            content = str(claude_response.get("content", ""))
        
        # For non-streaming responses, use 'message'
        message_obj = {
            "role": "assistant",
            "content": content
        }
        
        # Add context/citations if available from Azure Search
        if hasattr(self, '_current_search_citations') and self._current_search_citations:
            citations_context = {
                "citations": self._current_search_citations,
                "intent": "Azure Search results"
            }
            message_obj["context"] = citations_context
        
        formatted_response = {
            "id": claude_response.get("id", f"chatcmpl-{int(time.time())}"),
            "object": "chat.completion",
            "created": int(time.time()),
            "model": claude_response.get("model", self.model),
            "choices": [{
                "index": 0,
                "message": message_obj,
                "finish_reason": claude_response.get("stop_reason", "stop")
            }],
            "usage": claude_response.get("usage", {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            })
        }
        
        logging.debug(f"Formatted response: {formatted_response}")
        
        # Return a mock object that's compatible with Azure OpenAI format functions
        return MockAzureOpenAIResponse(formatted_response)


class LLMProviderFactory:
    """Factory class to create LLM providers"""
    
    @staticmethod
    def create_provider(provider_type: str) -> LLMProvider:
        """Create and return the appropriate LLM provider"""
        provider_type = provider_type.upper()
        
        if provider_type == "AZURE_OPENAI":
            return AzureOpenAIProvider()
        elif provider_type == "CLAUDE":
            return ClaudeProvider()
        else:
            raise ValueError(f"Unknown provider type: {provider_type}")
    
    @staticmethod
    def get_default_provider() -> str:
        """Get the default provider from environment settings"""
        return app_settings.base_settings.llm_provider