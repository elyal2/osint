from typing import Dict, List, Any
from datetime import datetime
import json
import re
import logging
from config import AppConfig
from llm_providers import LLMProviderFactory

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EnhancedEntityRelationshipExtractor:
    """Extracts named entities and relationships from text using multiple LLM providers."""
    
    def __init__(self, provider_name: str = None, debug_mode: bool = False):
        """
        Initialize the extractor with a specific LLM provider.
        
        Args:
            provider_name (str, optional): Name of the LLM provider to use.
                If None, uses the default provider from configuration.
            debug_mode (bool): Enable debug mode to show LLM prompts and responses
        """
        # Validar configuración antes de inicializar
        if not AppConfig.validate_config():
            raise ValueError("Configuración inválida. Revisa los errores anteriores.")
        
        self.provider_name = provider_name or AppConfig.DEFAULT_LLM_PROVIDER
        self.debug_mode = debug_mode
        logger.info(f"Inicializando extractor con proveedor: {self.provider_name}")
        if debug_mode:
            logger.info("Modo debug habilitado - se mostrarán prompts y respuestas del LLM")
        
        try:
            self.llm_provider = LLMProviderFactory.create_provider(self.provider_name)
            # Pasar el modo debug al proveedor
            if hasattr(self.llm_provider, 'set_debug_mode'):
                self.llm_provider.set_debug_mode(debug_mode)
            logger.info(f"Proveedor {self.provider_name} inicializado correctamente")
        except Exception as e:
            logger.error(f"Error al inicializar proveedor {self.provider_name}: {str(e)}")
            raise

    def analyze_text(self, text: str, doc_title: str = "Untitled Document", language: str = "en") -> Dict:
        """
        Analyze text to extract entities and relationships.
        
        Args:
            text (str): Text to analyze
            doc_title (str): Title of the document
            language (str): Language of the text
            
        Returns:
            Dict: Analysis results with entities and relationships
        """
        try:
            logger.info(f"Analizando texto con proveedor: {self.provider_name}")
            
            # Extract entities
            logger.info("Extrayendo entidades...")
            entities_result = self.llm_provider.extract_entities(text)
            
            if not entities_result or 'documentAnalysis' not in entities_result:
                logger.error("No se pudieron extraer entidades del texto")
                return self._create_error_response("Error en la extracción de entidades")
            
            # Verificar si hay error en los metadatos
            metadata = entities_result['documentAnalysis'].get('metadata', {})
            if 'error' in metadata:
                logger.error(f"Error en extracción de entidades: {metadata['error']}")
                return entities_result  # Retornar el error tal como viene
            
            entities = entities_result['documentAnalysis']['entities']
            logger.info(f"Entidades extraídas: {sum(len(ents) for ents in entities.values())}")
            
            # Extract explicit relationships
            logger.info("Extrayendo relaciones explícitas...")
            explicit_relationships = self.llm_provider.extract_relationships(text, entities)
            if not isinstance(explicit_relationships, list):
                explicit_relationships = []
            logger.info(f"Relaciones explícitas encontradas: {len(explicit_relationships)}")
            
            # Infer additional relationships
            logger.info("Inferiendo relaciones adicionales...")
            inferred_relationships = self.llm_provider.infer_additional_relationships(entities)
            if not isinstance(inferred_relationships, list):
                inferred_relationships = []
            logger.info(f"Relaciones inferidas: {len(inferred_relationships)}")
            
            # Merge relationships
            all_relationships = self._merge_relationships(explicit_relationships, inferred_relationships)
            logger.info(f"Total de relaciones: {len(all_relationships)}")
            
            # Create final result
            result = {
                "documentAnalysis": {
                    "metadata": {
                        "title": doc_title,
                        "analysisDate": datetime.now().isoformat(),
                        "language": language,
                        "provider": self.provider_name
                    },
                    "entities": entities,
                    "relationships": all_relationships
                }
            }
            
            logger.info("Análisis completado exitosamente")
            return result
            
        except Exception as e:
            logger.error(f"Error durante el análisis: {str(e)}")
            return self._create_error_response(f"Error en el análisis: {str(e)}")
    
    def analyze_pdf(self, pdf_content: bytes, doc_title: str = "Untitled Document", language: str = "en") -> Dict:
        """
        Analyze a PDF document to extract entities and relationships.
        
        Args:
            pdf_content (bytes): The content of the PDF file
            doc_title (str): Title of the document
            language (str): Language of the document
            
        Returns:
            Dict: Analysis results with entities and relationships
        """
        try:
            logger.info(f"Analizando PDF con proveedor: {self.provider_name}")
            
            # Usar el método analyze_pdf del proveedor que ya maneja PDFs grandes
            result = self.llm_provider.analyze_pdf(pdf_content)
            
            if self.debug_mode:
                logger.info(f"[DEBUG] Resultado completo del análisis de PDF: {json.dumps(result, indent=2, ensure_ascii=False)}")
            
            if not result or 'documentAnalysis' not in result:
                logger.error("No se pudieron obtener resultados del análisis del PDF")
                return self._create_error_response("Error en el análisis del PDF")
            
            # Verificar si hay error en los metadatos
            metadata = result['documentAnalysis'].get('metadata', {})
            if 'error' in metadata:
                logger.error(f"Error en análisis de PDF: {metadata['error']}")
                return result  # Retornar el error tal como viene
            
            # Asegurar que metadata existe
            if 'metadata' not in result['documentAnalysis']:
                result['documentAnalysis']['metadata'] = {}
            result['documentAnalysis']['metadata'].update({
                'title': doc_title,
                'language': language,
                'provider': self.provider_name
            })
            
            entities = result['documentAnalysis']['entities']
            relationships = result['documentAnalysis'].get('relationships', [])
            
            logger.info(f"Entidades extraídas del PDF: {sum(len(ents) for ents in entities.values())}")
            logger.info(f"Relaciones encontradas en PDF: {len(relationships)}")
            
            logger.info("Análisis de PDF completado exitosamente")
            return result
            
        except Exception as e:
            logger.error(f"Error durante el análisis del PDF: {str(e)}", exc_info=True)
            return self._create_error_response(f"Error en el análisis del PDF: {str(e)}")

    def _merge_relationships(self, explicit_relationships: List[Dict], inferred_relationships: List[Dict]) -> List[Dict]:
        """
        Merge explicit and inferred relationships, removing duplicates.
        
        Args:
            explicit_relationships (List[Dict]): Relationships explicitly found in text
            inferred_relationships (List[Dict]): Relationships inferred from entities
            
        Returns:
            List[Dict]: Merged and deduplicated relationships
        """
        all_relationships = []
        seen_relationships = set()
        
        # Add explicit relationships first
        for rel in explicit_relationships:
            if self._is_valid_relationship(rel):
                rel_key = self._create_relationship_key(rel)
                if rel_key not in seen_relationships:
                    rel["source"] = "explicit"
                    all_relationships.append(rel)
                    seen_relationships.add(rel_key)
        
        # Add inferred relationships (avoiding duplicates)
        for rel in inferred_relationships:
            if self._is_valid_relationship(rel):
                rel_key = self._create_relationship_key(rel)
                if rel_key not in seen_relationships:
                    rel["source"] = "inferred"
                    all_relationships.append(rel)
                    seen_relationships.add(rel_key)
        
        return all_relationships

    def _is_valid_relationship(self, relationship: Dict) -> bool:
        """Check if a relationship has the required structure."""
        required_keys = ["subject", "action", "object"]
        return all(key in relationship for key in required_keys)

    def _create_relationship_key(self, relationship: Dict) -> str:
        """Create a unique key for a relationship to detect duplicates."""
        subject = relationship.get("subject", {})
        object_ = relationship.get("object", {})
        action = relationship.get("action", "")
        
        subject_key = f"{subject.get('type', '')}:{subject.get('name', '')}"
        object_key = f"{object_.get('type', '')}:{object_.get('name', '')}"
        
        return f"{subject_key}|{action}|{object_key}"
    
    def _create_error_response(self, error_message: str) -> Dict:
        """Create an error response with the specified message."""
        return {
            "documentAnalysis": {
                "metadata": {
                    "title": "Error",
                    "analysisDate": datetime.now().isoformat(),
                    "language": "en",
                    "provider": self.provider_name,
                    "error": error_message
                },
                "entities": {
                    "Person": [],
                    "Organization": [],
                    "Location": [],
                    "Date": [],
                    "Event": [],
                    "Object": [],
                    "Code": []
                },
                "relationships": []
            }
        }

    def get_provider_info(self) -> Dict[str, Any]:
        """Get information about the current LLM provider."""
        return {
            "provider": self.provider_name,
            "available_providers": LLMProviderFactory.get_available_providers(),
            "default_provider": AppConfig.DEFAULT_LLM_PROVIDER
        }