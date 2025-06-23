"""
Sistema de proveedores de LLM para el extractor de entidades.
Soporta múltiples proveedores: Anthropic, Azure OpenAI y AWS Bedrock.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
import json
import logging
import base64
from io import BytesIO
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage
from config import LLMConfig, AppConfig

# Conditionally import fitz
try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

logger = logging.getLogger(__name__)

class LLMProvider(ABC):
    """Clase base abstracta para proveedores de LLM."""
    
    def __init__(self, provider_config: Dict[str, Any]):
        self.config = provider_config
        self.model = None
        self.relationship_model = None
        self._initialize_models()
    
    @abstractmethod
    def _initialize_models(self):
        """Inicializa los modelos de LLM."""
        pass
    
    @abstractmethod
    def generate_response(self, messages: List[BaseMessage], temperature: float = None, max_tokens: int = None) -> str:
        """Genera una respuesta del modelo."""
        pass
    
    def analyze_pdf(self, pdf_content: bytes) -> Dict:
        """Analyzes a PDF document and extracts entities and relationships."""
        if not fitz:
            raise ImportError("PyMuPDF no está instalado. Por favor, ejecuta 'pip install PyMuPDF'.")
            
        messages = self._construct_pdf_message(pdf_content)
        response_content = self.generate_response(
            messages, 
            temperature=self.config.get("temperature", 0),
            max_tokens=self.config.get("max_tokens", 8192)
        )
        return self._parse_json_response(response_content)
    
    def extract_entities(self, text: str) -> Dict:
        """Extrae entidades del texto."""
        prompt = self._create_extraction_prompt(text)
        messages = [SystemMessage(content=prompt)]
        
        response = self.generate_response(
            messages, 
            temperature=self.config.get("temperature", 0),
            max_tokens=self.config.get("max_tokens", 8192)
        )
        
        return self._parse_json_response(response)
    
    def extract_relationships(self, text: str, entities: Dict) -> List[Dict]:
        """Extrae relaciones del texto."""
        prompt = self._create_relationship_prompt(text, entities)
        messages = [SystemMessage(content=prompt)]
        
        response = self.generate_response(
            messages,
            temperature=self.config.get("relationship_temperature", 0.2),
            max_tokens=self.config.get("relationship_max_tokens", 4096)
        )
        
        return self._parse_json_response(response)
    
    def infer_additional_relationships(self, entities: Dict) -> List[Dict]:
        """Infiere relaciones adicionales basadas solo en las entidades."""
        prompt = self._create_additional_relationships_prompt(entities)
        messages = [SystemMessage(content=prompt)]
        
        response = self.generate_response(
            messages,
            temperature=self.config.get("relationship_temperature", 0.2),
            max_tokens=self.config.get("relationship_max_tokens", 4096)
        )
        
        return self._parse_json_response(response)
    
    def _convert_pdf_to_images_base64(self, pdf_content: bytes) -> List[str]:
        """Converts each page of a PDF to a base64 encoded image using PyMuPDF."""
        try:
            doc = fitz.open(stream=pdf_content, filetype="pdf")
            base64_images = []
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                pix = page.get_pixmap()
                img_bytes = pix.tobytes("png")
                base64_images.append(base64.b64encode(img_bytes).decode('utf-8'))
            doc.close()
            logger.info(f"PDF convertido a {len(base64_images)} imágenes usando PyMuPDF.")
            return base64_images
        except Exception as e:
            logger.error(f"Error al convertir PDF a imágenes con PyMuPDF: {e}")
            raise
            
    def _create_pdf_analysis_prompt(self) -> str:
        """Creates the system prompt for PDF analysis."""
        return """You will be provided with a series of images, which are pages from a single document.
Analyze the content of these pages to extract named entities (Person, Organization, Location, and Date) and their relationships.
- Extract entities and relationships and return them in a single JSON object.
- For each entity, include any aliases or pronouns by which the entity is referenced.
- Include a spanish translation only for traditional place names and standard dates.
- Be thorough and extract ALL entities and relationships mentioned in the text.
- Relationships must follow Subject-Action-Object (SAO) format.
- Identify both EXPLICIT relationships (directly mentioned) and INFERRED relationships (logically deduced from context).
- For each relationship, add a "source" field with value "explicit" or "inferred".

Output the result strictly as JSON, following the exact structure and formatting shown in the example. Do not provide any additional text, explanation, or commentary—only the JSON.

Example Output:
{
    "documentAnalysis": {
        "entities": {
            "Person": [
            {
                "name": "Alberto",
                "aliases": ["he"],
                "spanish": "Alberto"
            }],
            "Organization": [
            {
                "name": "ACME Inc.",
                "aliases": [],
                "spanish": ""
            }]
        },
        "relationships": [
            {
                "subject": { "type": "Person", "name": "Alberto" },
                "action": "joined",
                "object": { "type": "Organization", "name": "ACME Inc." },
                "source": "explicit"
            },
            {
                "subject": { "type": "Organization", "name": "ACME Inc." },
                "action": "is located in",
                "object": { "type": "Location", "name": "Paris" },
                "source": "inferred"
            }
        ]
    }
}"""
    
    def _construct_pdf_message(self, pdf_content: bytes) -> List[HumanMessage]:
        """Constructs a multimodal message for PDF analysis by converting PDF to images."""
        base64_images = self._convert_pdf_to_images_base64(pdf_content)
        
        message_content = [{"type": "text", "text": self._create_pdf_analysis_prompt()}]
        for b64_image in base64_images:
            message_content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64_image}"},
                }
            )
            
        return [HumanMessage(content=message_content)]
    
    def _create_extraction_prompt(self, text: str) -> str:
        """Crea el prompt para extracción de entidades."""
        return f"""Analyze the provided text to extract named entities (Person, Organization, Location, and Date).
- For each entity, include any aliases or pronouns by which the entity is referenced.
- Include a spanish translation only for:
  * Traditional place names that have official or commonly used Spanish versions (e.g., London -> Londres, New York -> Nueva York)
  * Dates in standard format
  * Do NOT translate widely recognized names, technology hubs, company names, or branded terms (e.g., Silicon Valley, Wall Street, Times Square)
- Identify relevant dates as "Date" entities.
- Be thorough and extract ALL entities mentioned in the text, even if they are only mentioned once.
- Be comprehensive in identifying aliases and coreferences.
- Output the result strictly as JSON, following the exact structure and formatting shown in the example.
- Do not provide any additional text, explanation, or commentary—only the JSON.

Example Input: Alberto was born on January 1, 1990. In 2010, he joined ACME Inc. and moved to Paris. He was often called "The Greatest" during his time at ACME Inc. In 2015, the young guy traveled to London with his colleagues.

Expected Output:
{{
    "documentAnalysis": {{
        "entities": {{
            "Person": [
            {{
                "name": "Alberto",
                "aliases": ["he", "The Greatest", "the young guy"],
                "spanish": "Alberto"
            }}],
            "Organization": [
            {{
                "name": "ACME Inc.",
                "aliases": [],
                "spanish": ""
            }}],
            "Location": [
            {{
                "name": "Paris",
                "aliases": [],
                "spanish": "París"
            }},
            {{
                "name": "London",
                "aliases": [],
                "spanish": "Londres"
            }}],
            "Date": [
            {{
                "name": "January 1, 1990",
                "year": "1990",
                "aliases": [],
                "spanish": "1 de enero de 1990"
            }},
            {{
                "name": "2010",
                "year": "2010",
                "aliases": [],
                "spanish": ""
            }},
            {{
                "name": "2015",
                "year": "2015",
                "aliases": [],
                "spanish": ""
            }}
            ]
        }}
    }}
}}

Text to analyze:
{text}"""

    def _create_relationship_prompt(self, text: str, entities: Dict) -> str:
        """Crea el prompt para extracción de relaciones."""
        entity_lists = {}
        for entity_type, entity_items in entities.items():
            entity_lists[entity_type] = [item["name"] for item in entity_items]
        
        entity_text = ""
        for entity_type, entities in entity_lists.items():
            if entities:
                entity_text += f"{entity_type} entities: {', '.join(entities)}\n"
        
        return f"""Analyze the provided text to identify Subject-Action-Object (SAO) relationships between entities. 
I've already identified the following entities in the text:

{entity_text}

Instructions:
- Extract ONLY relationships where both subject and object are from the provided entity lists.
- Relationships must follow Subject-Action-Object format, where both subject and object are entities.
- Focus on explicit relationships mentioned in the text AND strongly implied relationships.
- Be creative and thorough in identifying relationships between entities, even if the connection is indirect.
- For each entity pair, try to find at least one relationship if any connection exists in the text.
- Use actions that clearly describe the nature of the relationship.
- Look for relationships in both directions between entity pairs.
- If an entity belongs to a company, organization, or place, create that relationship.

Output Format:
Return ONLY a JSON array of relationships with no additional explanation or text. Each relationship should include:
- subject: Object with 'type' and 'name' matching an entity in the provided list
- action: String describing the relationship
- object: Object with 'type' and 'name' matching an entity in the provided list

Example Output:
[
  {{
    "subject": {{
      "type": "Person",
      "name": "Alberto"
    }},
    "action": "joined",
    "object": {{
      "type": "Organization",
      "name": "ACME Inc."
    }}
  }}
]

Text to analyze for relationships:
{text}"""

    def _create_additional_relationships_prompt(self, entities: Dict) -> str:
        """Crea el prompt para inferir relaciones adicionales."""
        entity_text = ""
        for entity_type, entity_items in entities.items():
            if entity_items:
                entity_names = [item["name"] for item in entity_items]
                entity_text += f"{entity_type} entities: {', '.join(entity_names)}\n"
        
        return f"""Based on the following entities, infer logical relationships that might exist between them, even if not explicitly mentioned in the original text:

{entity_text}

Instructions:
- Infer relationships based on common knowledge and logical connections.
- Focus on relationships that would make sense in a real-world context.
- Consider hierarchical relationships (e.g., person belongs to organization).
- Consider geographical relationships (e.g., organization located in city).
- Consider temporal relationships (e.g., events happening in specific years).
- Be conservative and only infer relationships that are highly likely.
- Output format should be the same as the relationship extraction.

Return ONLY a JSON array of inferred relationships:
[]"""

    def _parse_json_response(self, response: str) -> Any:
        """Parsea la respuesta JSON del modelo."""
        try:
            # Limpiar la respuesta de posibles caracteres extra
            cleaned_response = response.strip()
            if cleaned_response.startswith("```json"):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.endswith("```"):
                cleaned_response = cleaned_response[:-3]
            
            return json.loads(cleaned_response.strip())
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON response: {e}")
            logger.error(f"Response was: {response}")
            return {}

class AnthropicProvider(LLMProvider):
    """Proveedor para Anthropic Claude."""
    
    def _initialize_models(self):
        """Inicializa los modelos de Anthropic."""
        from langchain_anthropic import ChatAnthropic
        
        credentials = AppConfig.get_llm_credentials("anthropic")
        
        self.model = ChatAnthropic(
            model=self.config["model"],
            temperature=self.config["temperature"],
            anthropic_api_key=credentials["anthropic_api_key"],
            max_tokens=self.config["max_tokens"]
        )
        
        self.relationship_model = ChatAnthropic(
            model=self.config["model"],
            temperature=self.config["relationship_temperature"],
            anthropic_api_key=credentials["anthropic_api_key"],
            max_tokens=self.config["relationship_max_tokens"]
        )
    
    def generate_response(self, messages: List[BaseMessage], temperature: float = None, max_tokens: int = None) -> str:
        """Genera una respuesta usando Anthropic."""
        model = self.relationship_model if temperature and temperature > 0 else self.model
        response = model.invoke(messages)
        return response.content

class AzureOpenAIProvider(LLMProvider):
    """Proveedor para Azure OpenAI."""
    
    def _initialize_models(self):
        """Inicializa los modelos de Azure OpenAI."""
        from langchain_openai import AzureChatOpenAI
        
        credentials = AppConfig.get_llm_credentials("azure_openai")
        
        self.model = AzureChatOpenAI(
            azure_deployment=credentials["azure_deployment_name"],
            azure_endpoint=credentials["azure_openai_endpoint"],
            api_key=credentials["azure_openai_api_key"],
            api_version=credentials["azure_openai_api_version"],
            temperature=self.config["temperature"],
            max_tokens=self.config["max_tokens"]
        )
        
        self.relationship_model = AzureChatOpenAI(
            azure_deployment=credentials["azure_deployment_name"],
            azure_endpoint=credentials["azure_openai_endpoint"],
            api_key=credentials["azure_openai_api_key"],
            api_version=credentials["azure_openai_api_version"],
            temperature=self.config["relationship_temperature"],
            max_tokens=self.config["relationship_max_tokens"]
        )
    
    def generate_response(self, messages: List[BaseMessage], temperature: float = None, max_tokens: int = None) -> str:
        """Genera una respuesta usando Azure OpenAI."""
        model = self.relationship_model if temperature and temperature > 0 else self.model
        response = model.invoke(messages)
        return response.content

class AWSBedrockProvider(LLMProvider):
    """Proveedor para AWS Bedrock."""
    
    def _initialize_models(self):
        """Inicializa los modelos de AWS Bedrock."""
        from langchain_community.chat_models import BedrockChat
        
        credentials = AppConfig.get_llm_credentials("aws_bedrock")
        
        # Configurar el profile de AWS
        import boto3
        session = boto3.Session(
            profile_name=credentials["aws_profile"],
            region_name=credentials["aws_region"]
        )
        
        self.model = BedrockChat(
            model_id=self.config["model"],
            client=session.client("bedrock-runtime"),
            temperature=self.config["temperature"],
            max_tokens=self.config["max_tokens"]
        )
        
        self.relationship_model = BedrockChat(
            model_id=self.config["model"],
            client=session.client("bedrock-runtime"),
            temperature=self.config["relationship_temperature"],
            max_tokens=self.config["relationship_max_tokens"]
        )
    
    def generate_response(self, messages: List[BaseMessage], temperature: float = None, max_tokens: int = None) -> str:
        """Genera una respuesta usando AWS Bedrock."""
        model = self.relationship_model if temperature and temperature > 0 else self.model
        response = model.invoke(messages)
        return response.content

class LLMProviderFactory:
    """Factory para crear proveedores de LLM."""
    
    _providers = {
        "anthropic": AnthropicProvider,
        "azure_openai": AzureOpenAIProvider,
        "aws_bedrock": AWSBedrockProvider
    }
    
    @classmethod
    def create_provider(cls, provider_name: str = None) -> LLMProvider:
        """Crea un proveedor de LLM."""
        if provider_name is None:
            provider_name = AppConfig.DEFAULT_LLM_PROVIDER
        
        if provider_name not in cls._providers:
            raise ValueError(f"Proveedor no soportado: {provider_name}")
        
        provider_config = LLMConfig.get_provider_config(provider_name)
        provider_class = cls._providers[provider_name]
        
        return provider_class(provider_config)
    
    @classmethod
    def get_available_providers(cls) -> list:
        """Retorna la lista de proveedores disponibles."""
        return list(cls._providers.keys()) 