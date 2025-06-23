import os
import json
import logging
import requests
import dataclasses

from typing import List

DEBUG = os.environ.get("DEBUG", "false")
if DEBUG.lower() == "true":
    logging.basicConfig(level=logging.DEBUG)

AZURE_SEARCH_PERMITTED_GROUPS_COLUMN = os.environ.get(
    "AZURE_SEARCH_PERMITTED_GROUPS_COLUMN"
)


class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        return super().default(o)


async def format_as_ndjson(r, provider_name="LLM_SERVICE"):
    try:
        async for event in r:
            yield json.dumps(event, cls=JSONEncoder) + "\n"
    except Exception as error:
        from backend.llm_providers.errors import LLMProviderErrorHandler
        
        logging.exception("Exception while generating response stream: %s", error)
        
        # Create user-friendly error response
        error_response = LLMProviderErrorHandler.create_provider_error_response(
            exception=error,
            provider_name=provider_name,
            language="fr"  # Default to French for AskMe
        )
        
        yield json.dumps(error_response) + "\n"


def parse_multi_columns(columns: str) -> list:
    if "|" in columns:
        return columns.split("|")
    else:
        return columns.split(",")


def fetchUserGroups(userToken, nextLink=None):
    # Recursively fetch group membership
    if nextLink:
        endpoint = nextLink
    else:
        endpoint = "https://graph.microsoft.com/v1.0/me/transitiveMemberOf?$select=id"

    headers = {"Authorization": "bearer " + userToken}
    try:
        r = requests.get(endpoint, headers=headers)
        if r.status_code != 200:
            logging.error(f"Error fetching user groups: {r.status_code} {r.text}")
            return []

        r = r.json()
        if "@odata.nextLink" in r:
            nextLinkData = fetchUserGroups(userToken, r["@odata.nextLink"])
            r["value"].extend(nextLinkData)

        return r["value"]
    except Exception as e:
        logging.error(f"Exception in fetchUserGroups: {e}")
        return []


def generateFilterString(userToken):
    # Get list of groups user is a member of
    userGroups = fetchUserGroups(userToken)

    # Construct filter string
    if not userGroups:
        logging.debug("No user groups found")

    group_ids = ", ".join([obj["id"] for obj in userGroups])
    return f"{AZURE_SEARCH_PERMITTED_GROUPS_COLUMN}/any(g:search.in(g, '{group_ids}'))"


def generateFilterStringFromFullDef(fullDef):
    splittedFullDef = fullDef.split('|')
    group_ids = ", ".join(splittedFullDef)
    return f"{AZURE_SEARCH_PERMITTED_GROUPS_COLUMN}/any(g:search.in(g, '{group_ids}'))"


def format_non_streaming_response(chatCompletion, history_metadata, apim_request_id):
    response_obj = {
        "id": chatCompletion.id,
        "model": chatCompletion.model,
        "created": chatCompletion.created,
        "object": chatCompletion.object,
        "choices": [{"messages": []}],
        "history_metadata": history_metadata,
        "apim-request-id": apim_request_id,
    }

    if len(chatCompletion.choices) > 0:
        message = chatCompletion.choices[0].message
        if message:
            if hasattr(message, "context"):
                # Log citation count for debugging document count issues
                citation_count = 0
                if hasattr(message.context, 'citations') and message.context.citations:
                    citation_count = len(message.context.citations)
                print(f"🔍 AZURE_OPENAI_RESPONSE: Received {citation_count} citations from Azure OpenAI")
                
                response_obj["choices"][0]["messages"].append(
                    {
                        "role": "tool",
                        "content": json.dumps(message.context),
                    }
                )
            response_obj["choices"][0]["messages"].append(
                {
                    "role": "assistant",
                    "content": message.content,
                }
            )
            return response_obj

    return {}

def format_stream_response(chatCompletionChunk, history_metadata, apim_request_id):
    response_obj = {
        "id": chatCompletionChunk.id,
        "model": chatCompletionChunk.model,
        "created": chatCompletionChunk.created,
        "object": chatCompletionChunk.object,
        "choices": [{"messages": []}],
        "history_metadata": history_metadata,
        "apim-request-id": apim_request_id,
    }
    

    if len(chatCompletionChunk.choices) > 0:
        delta = chatCompletionChunk.choices[0].delta
        if delta:
            if hasattr(delta, "context") and delta.context:
                # Log citation count for debugging document count issues (streaming)
                citation_count = 0
                if hasattr(delta.context, 'citations') and delta.context.citations:
                    citation_count = len(delta.context.citations)
                print(f"🔍 AZURE_OPENAI_STREAMING: Received {citation_count} citations from Azure OpenAI")
                
                messageObj = {"role": "tool", "content": json.dumps(delta.context)}
                response_obj["choices"][0]["messages"].append(messageObj)
                return response_obj
            if delta.role == "assistant" and hasattr(delta, "context") and delta.context:
                messageObj = {
                    "role": "assistant",
                    "context": delta.context,
                }
                response_obj["choices"][0]["messages"].append(messageObj)
                return response_obj
            if delta.tool_calls:
                messageObj = {
                    "role": "tool",
                    "tool_calls": {
                        "id": delta.tool_calls[0].id,
                        "function": {
                            "name" : delta.tool_calls[0].function.name,
                            "arguments": delta.tool_calls[0].function.arguments
                        },
                        "type": delta.tool_calls[0].type
                    }
                }
                if hasattr(delta, "context"):
                    messageObj["context"] = json.dumps(delta.context)
                response_obj["choices"][0]["messages"].append(messageObj)
                return response_obj
            else:
                if delta.content:
                    messageObj = {
                        "role": "assistant",
                        "content": delta.content,
                        "id": chatCompletionChunk.id,  # Ajouter l'ID du message
                        "date": f"{chatCompletionChunk.created}000"  # Timestamp en millisecondes
                    }
                    response_obj["choices"][0]["messages"].append(messageObj)
                    return response_obj
                # Handle OpenAI Direct empty content chunks (role=assistant but no content)
                elif hasattr(delta, 'role') and delta.role == 'assistant' and not hasattr(delta, 'context'):
                    # Empty assistant chunk - return empty response to indicate chunk was handled
                    return response_obj
    
    # Handle completely empty chunks (end of stream)
    if hasattr(chatCompletionChunk, 'choices') and len(chatCompletionChunk.choices) > 0:
        delta = chatCompletionChunk.choices[0].delta
        if delta:
            # Check if all properties are None/empty (end of stream chunk)
            role_empty = not hasattr(delta, 'role') or delta.role is None
            content_empty = not hasattr(delta, 'content') or delta.content is None
            context_empty = not hasattr(delta, 'context') or delta.context is None
            
            if role_empty and content_empty and context_empty:
                # Completely empty delta - return empty response to indicate chunk was handled
                return response_obj

    logging.warning(f"format_stream_response returning empty dict for: {chatCompletionChunk.id if hasattr(chatCompletionChunk, 'id') else 'unknown'}")
    return {}


def format_pf_non_streaming_response(
    chatCompletion, history_metadata, response_field_name, citations_field_name, message_uuid=None
):
    if chatCompletion is None:
        logging.error(
            "chatCompletion object is None - Increase PROMPTFLOW_RESPONSE_TIMEOUT parameter"
        )
        return {
            "error": "No response received from promptflow endpoint increase PROMPTFLOW_RESPONSE_TIMEOUT parameter or check the promptflow endpoint."
        }
    if "error" in chatCompletion:
        logging.error(f"Error in promptflow response api: {chatCompletion['error']}")
        return {"error": chatCompletion["error"]}

    logging.debug(f"chatCompletion: {chatCompletion}")
    try:
        messages = []
        if response_field_name in chatCompletion:
            messages.append({
                "role": "assistant",
                "content": chatCompletion[response_field_name] 
            })
        if citations_field_name in chatCompletion:
            citation_content= {"citations": chatCompletion[citations_field_name]}
            messages.append({ 
                "role": "tool",
                "content": json.dumps(citation_content)
            })

        response_obj = {
            "id": chatCompletion["id"],
            "model": "",
            "created": "",
            "object": "",
            "history_metadata": history_metadata,
            "choices": [
                {
                    "messages": messages,
                }
            ]
        }
        return response_obj
    except Exception as e:
        logging.error(f"Exception in format_pf_non_streaming_response: {e}")
        return {}


def convert_to_pf_format(input_json, request_field_name, response_field_name):
    output_json = []
    logging.debug(f"Input json: {input_json}")
    # align the input json to the format expected by promptflow chat flow
    for message in input_json["messages"]:
        if message:
            if message["role"] == "user":
                new_obj = {
                    "inputs": {request_field_name: message["content"]},
                    "outputs": {response_field_name: ""},
                }
                output_json.append(new_obj)
            elif message["role"] == "assistant" and len(output_json) > 0:
                output_json[-1]["outputs"][response_field_name] = message["content"]
    logging.debug(f"PF formatted response: {output_json}")
    return output_json


def comma_separated_string_to_list(s: str) -> List[str]:
    '''
    Split comma-separated values into a list.
    '''
    return s.strip().replace(' ', '').split(',')


def compress_image_for_storage(image_data_url: str, max_size_kb: int = 300) -> str:
    """
    Compresse une image encodée en data URL pour qu'elle ne dépasse pas la taille maximale spécifiée.
    
    Args:
        image_data_url (str): L'image au format data:image/...;base64,...
        max_size_kb (int): Taille maximale en KB (défaut: 300KB)
        
    Returns:
        str: L'image compressée au format data URL
    """
    try:
        import base64
        import io
        from PIL import Image
        
        # Extraire le format et les données base64
        if not image_data_url.startswith('data:image/'):
            return image_data_url
            
        # Séparer le header du data
        header, base64_data = image_data_url.split(',', 1)
        
        # Décoder l'image
        image_bytes = base64.b64decode(base64_data)
        
        # Calculer la taille actuelle
        current_size_kb = len(image_bytes) / 1024
        
        # Si l'image est déjà assez petite, la retourner telle quelle
        if current_size_kb <= max_size_kb:
            return image_data_url
            
        logging.info(f"Compression d'image: taille actuelle {current_size_kb:.1f}KB, cible {max_size_kb}KB")
        
        # Ouvrir l'image avec PIL
        img = Image.open(io.BytesIO(image_bytes))
        
        # Convertir en RGB si nécessaire (pour JPEG)
        if img.mode in ('RGBA', 'LA', 'P'):
            # Créer un fond blanc pour les images avec transparence
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            img = background
        
        # Calculer le ratio de compression nécessaire
        compression_ratio = max_size_kb / current_size_kb
        
        # Réduire la taille de l'image
        if compression_ratio < 0.8:  # Si on doit beaucoup compresser, réduire aussi les dimensions
            scale_factor = min(0.8, compression_ratio ** 0.5)
            new_width = int(img.width * scale_factor)
            new_height = int(img.height * scale_factor)
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            logging.info(f"Redimensionnement: {img.width}x{img.height} -> {new_width}x{new_height}")
        
        # Essayer différents niveaux de qualité JPEG
        for quality in [85, 75, 65, 55, 45, 35, 25]:
            output_buffer = io.BytesIO()
            
            # Sauvegarder en JPEG avec la qualité spécifiée
            img.save(output_buffer, format='JPEG', quality=quality, optimize=True)
            compressed_bytes = output_buffer.getvalue()
            compressed_size_kb = len(compressed_bytes) / 1024
            
            if compressed_size_kb <= max_size_kb:
                # Encoder en base64 et recréer la data URL
                compressed_base64 = base64.b64encode(compressed_bytes).decode('utf-8')
                compressed_data_url = f"data:image/jpeg;base64,{compressed_base64}"
                
                logging.info(f"Image compressée: {current_size_kb:.1f}KB -> {compressed_size_kb:.1f}KB (qualité {quality})")
                return compressed_data_url
        
        # Si même avec la qualité minimale on dépasse encore, réduire davantage les dimensions
        while True:
            img = img.resize((int(img.width * 0.9), int(img.height * 0.9)), Image.Resampling.LANCZOS)
            output_buffer = io.BytesIO()
            img.save(output_buffer, format='JPEG', quality=25, optimize=True)
            compressed_bytes = output_buffer.getvalue()
            compressed_size_kb = len(compressed_bytes) / 1024
            
            if compressed_size_kb <= max_size_kb or img.width < 50 or img.height < 50:
                compressed_base64 = base64.b64encode(compressed_bytes).decode('utf-8')
                compressed_data_url = f"data:image/jpeg;base64,{compressed_base64}"
                
                logging.info(f"Image compressée (redimensionnée): {current_size_kb:.1f}KB -> {compressed_size_kb:.1f}KB")
                return compressed_data_url
                
    except Exception as e:
        logging.error(f"Erreur lors de la compression d'image: {e}")
        # En cas d'erreur, retourner l'image originale
        return image_data_url


def process_message_content_for_storage(content):
    """
    Traite le contenu d'un message pour compresser les images avant stockage.
    
    Args:
        content: Le contenu du message (string ou array multimodal)
        
    Returns:
        Le contenu traité avec les images compressées
    """
    if isinstance(content, str):
        return content
    
    if isinstance(content, list):
        processed_content = []
        for item in content:
            if isinstance(item, dict) and item.get('type') == 'image_url':
                # Compresser l'image
                original_url = item['image_url']['url']
                compressed_url = compress_image_for_storage(original_url, max_size_kb=300)
                
                processed_item = {
                    'type': 'image_url',
                    'image_url': {
                        'url': compressed_url
                    }
                }
                processed_content.append(processed_item)
            else:
                processed_content.append(item)
        
        return processed_content
    
    return content

