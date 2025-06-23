"""
Configuración centralizada para el sistema de extracción de entidades.
Maneja múltiples proveedores de LLM y configuraciones de la aplicación.
"""

import os
from typing import Dict, Any, Optional
from dotenv import load_dotenv
import logging

# Cargar variables de entorno
load_dotenv()

logger = logging.getLogger(__name__)

class LLMConfig:
    """Configuración para diferentes proveedores de LLM."""
    
    # Configuraciones por defecto para cada proveedor
    DEFAULT_CONFIGS = {
        "anthropic": {
            "model": "claude-3-5-haiku-20241022",
            "temperature": 0,
            "max_tokens": 8192,
            "relationship_temperature": 0.2,
            "relationship_max_tokens": 4096
        },
        "azure_openai": {
            "model": "gpt-4o-mini",
            "temperature": 0,
            "max_tokens": 8192,
            "relationship_temperature": 0.2,
            "relationship_max_tokens": 4096
        },
        "aws_bedrock": {
            "model": "anthropic.claude-3-haiku-20240307-v1:0",
            "temperature": 0,
            "max_tokens": 8192,
            "relationship_temperature": 0.2,
            "relationship_max_tokens": 4096
        }
    }
    
    @classmethod
    def get_provider_config(cls, provider: str) -> Dict[str, Any]:
        """Obtiene la configuración para un proveedor específico."""
        if provider not in cls.DEFAULT_CONFIGS:
            raise ValueError(f"Proveedor no soportado: {provider}")
        
        config = cls.DEFAULT_CONFIGS[provider].copy()
        
        # Sobrescribir con configuraciones específicas del entorno
        if provider == "azure_openai":
            deployment_name = os.getenv("AZURE_DEPLOYMENT_NAME")
            if deployment_name:
                config["model"] = deployment_name
        
        elif provider == "aws_bedrock":
            aws_model = os.getenv("DEFAULT_AWS_MODEL")
            if aws_model:
                config["model"] = aws_model
        
        return config
    
    @classmethod
    def get_available_providers(cls) -> list:
        """Retorna la lista de proveedores disponibles."""
        return list(cls.DEFAULT_CONFIGS.keys())

class AppConfig:
    """Configuración general de la aplicación."""
    
    # Configuración de Neo4j
    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
    
    # Configuración de Flask
    FLASK_PORT = int(os.getenv("FLASK_PORT", 5000))
    FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
    FLASK_DEBUG = os.getenv("FLASK_DEBUG", "False").lower() in ('true', '1', 't')
    
    # Proveedor de LLM predeterminado
    DEFAULT_LLM_PROVIDER = os.getenv("DEFAULT_LLM_PROVIDER", "anthropic")
    
    # Configuración de API Keys
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
    AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
    AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
    AZURE_DEPLOYMENT_NAME = os.getenv("AZURE_DEPLOYMENT_NAME", "gpt-4o")
    
    # Configuración de AWS
    AWS_PROFILE = os.getenv("AWS_PROFILE", "default")
    AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
    DEFAULT_AWS_MODEL = os.getenv("DEFAULT_AWS_MODEL", "anthropic.claude-3-haiku-20240307-v1:0")
    
    @classmethod
    def validate_config(cls) -> bool:
        """Valida que la configuración sea correcta."""
        errors = []
        
        # Validar configuración de Neo4j
        if not cls.NEO4J_PASSWORD:
            errors.append("NEO4J_PASSWORD no está configurado")
        
        # Validar proveedor predeterminado
        if cls.DEFAULT_LLM_PROVIDER not in LLMConfig.get_available_providers():
            errors.append(f"Proveedor predeterminado no válido: {cls.DEFAULT_LLM_PROVIDER}")
        
        # Validar configuración según el proveedor predeterminado
        if cls.DEFAULT_LLM_PROVIDER == "anthropic" and not cls.ANTHROPIC_API_KEY:
            errors.append("ANTHROPIC_API_KEY no está configurado")
        elif cls.DEFAULT_LLM_PROVIDER == "azure_openai":
            if not cls.AZURE_OPENAI_API_KEY:
                errors.append("AZURE_OPENAI_API_KEY no está configurado")
            if not cls.AZURE_OPENAI_ENDPOINT:
                errors.append("AZURE_OPENAI_ENDPOINT no está configurado")
        elif cls.DEFAULT_LLM_PROVIDER == "aws_bedrock":
            # Para AWS Bedrock, verificamos que boto3 esté disponible
            try:
                import boto3
            except ImportError:
                errors.append("boto3 no está instalado (requerido para AWS Bedrock)")
        
        if errors:
            logger.error("Errores de configuración encontrados:")
            for error in errors:
                logger.error(f"  - {error}")
            return False
        
        return True
    
    @classmethod
    def get_llm_credentials(cls, provider: str) -> Dict[str, Any]:
        """Obtiene las credenciales para un proveedor específico."""
        credentials = {}
        
        if provider == "anthropic":
            if cls.ANTHROPIC_API_KEY:
                credentials["anthropic_api_key"] = cls.ANTHROPIC_API_KEY
            else:
                raise ValueError("ANTHROPIC_API_KEY no está configurado")
        
        elif provider == "azure_openai":
            if cls.AZURE_OPENAI_API_KEY and cls.AZURE_OPENAI_ENDPOINT:
                credentials.update({
                    "azure_openai_api_key": cls.AZURE_OPENAI_API_KEY,
                    "azure_openai_endpoint": cls.AZURE_OPENAI_ENDPOINT,
                    "azure_openai_api_version": cls.AZURE_OPENAI_API_VERSION,
                    "azure_deployment_name": cls.AZURE_DEPLOYMENT_NAME
                })
            else:
                raise ValueError("Configuración de Azure OpenAI incompleta")
        
        elif provider == "aws_bedrock":
            # Para AWS Bedrock, las credenciales se manejan a través de AWS profiles
            credentials.update({
                "aws_profile": cls.AWS_PROFILE,
                "aws_region": cls.AWS_REGION
            })
        
        else:
            raise ValueError(f"Proveedor no soportado: {provider}")
        
        return credentials

# Configuración global
def get_config() -> Dict[str, Any]:
    """Obtiene toda la configuración de la aplicación."""
    return {
        "neo4j": {
            "uri": AppConfig.NEO4J_URI,
            "user": AppConfig.NEO4J_USER,
            "password": AppConfig.NEO4J_PASSWORD
        },
        "flask": {
            "port": AppConfig.FLASK_PORT,
            "host": AppConfig.FLASK_HOST,
            "debug": AppConfig.FLASK_DEBUG
        },
        "llm": {
            "default_provider": AppConfig.DEFAULT_LLM_PROVIDER,
            "available_providers": LLMConfig.get_available_providers(),
            "provider_configs": {
                provider: LLMConfig.get_provider_config(provider)
                for provider in LLMConfig.get_available_providers()
            }
        },
        "aws": {
            "profile": AppConfig.AWS_PROFILE,
            "region": AppConfig.AWS_REGION,
            "default_model": AppConfig.DEFAULT_AWS_MODEL
        },
        "azure": {
            "deployment_name": AppConfig.AZURE_DEPLOYMENT_NAME
        }
    } 