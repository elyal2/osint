# Entity Relationship Extractor

Esta herramienta extrae entidades nombradas (personas, organizaciones, lugares, fechas) y sus relaciones a partir de documentos de texto, páginas web y **archivos PDF**. Utiliza modelos de lenguaje avanzados y multimodales para realizar un análisis sofisticado del contenido, y almacena los resultados en archivos JSON y opcionalmente en una base de datos Neo4j para visualización y análisis de grafos.

## Características

- **Extracción de entidades** en cuatro categorías: Persona, Organización, Lugar, Fecha
- **Identificación de relaciones** entre entidades en formato Sujeto-Acción-Objeto
- **Análisis de múltiples formatos**: Texto plano, páginas web y archivos PDF
- **Soporte para múltiples proveedores de LLM**: Anthropic Claude, Azure OpenAI, AWS Bedrock
- **Procesamiento multilingüe** con traducciones al español
- **Almacenamiento en base de datos Neo4j** para análisis de grafos
- **Visualización interactiva** de las relaciones entre entidades
- **Enriquecimiento progresivo** de la base de conocimiento a medida que se analizan más documentos

## Requisitos previos

- Python 3.8 o superior
- Docker y Docker Compose (para Neo4j)
- API Key de al menos uno de los proveedores de LLM soportados

## Configuración

### 1. Clonar el repositorio

```bash
git clone https://github.com/tu-usuario/entity-extractor.git
cd entity-extractor
```

### 2. Crear un entorno virtual

```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno

Crea un archivo `.env` basado en el template proporcionado:

```bash
cp env.template .env
```

Edita el archivo `.env` y configura las variables necesarias:

#### Configuración de Neo4j (requerida)
```
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=tupassword
```

#### Configuración de proveedores de LLM (al menos uno requerido)

**Anthropic Claude (recomendado):**
```
ANTHROPIC_API_KEY=tu_clave_api_anthropic_aqui
DEFAULT_LLM_PROVIDER=anthropic
```

**Azure OpenAI:**
```
AZURE_OPENAI_API_KEY=tu_clave_api_azure_aqui
AZURE_OPENAI_ENDPOINT=https://tu-recurso.openai.azure.com/
AZURE_OPENAI_API_VERSION=2024-02-15-preview
AZURE_DEPLOYMENT_NAME=gpt-4o
DEFAULT_LLM_PROVIDER=azure_openai
```

**AWS Bedrock:**
```
AWS_PROFILE=logicalisSH
AWS_REGION=eu-central-1
DEFAULT_AWS_MODEL=anthropic.claude-3-sonnet-20240229-v1:0
DEFAULT_LLM_PROVIDER=aws_bedrock
```

#### Configuración de la aplicación (opcional)
```
FLASK_PORT=5000
FLASK_HOST=0.0.0.0
FLASK_DEBUG=False
```

### 5. Iniciar Neo4j con Docker Compose

```bash
docker-compose up -d
```

## Uso

### Analizar un archivo de texto

```bash
python main.py --file ruta/al/documento.txt --store-db
```

### Analizar un archivo PDF

```bash
python main.py --pdf ruta/al/documento.pdf --store-db
```

### Analizar una página web

```bash
python main.py --url https://ejemplo.com --store-db
```

### Usar un proveedor específico de LLM

```bash
# Usar Azure OpenAI con un PDF
python main.py --pdf documento.pdf --provider azure_openai --store-db

# Usar AWS Bedrock
python main.py --file documento.txt --provider aws_bedrock --store-db

# Usar Anthropic (por defecto)
python main.py --file documento.txt --provider anthropic --store-db
```

### Opciones adicionales

```
--file FILE            Ruta al archivo de texto a analizar
--pdf PDF              Ruta al archivo PDF a analizar
--url URL              URL de la página web a analizar
--language LANGUAGE    Idioma del texto (por defecto: en)
--output-dir DIR       Directorio para guardar resultados (por defecto: output)
--store-db             Almacenar resultados en la base de datos Neo4j
--skip-file            No guardar resultados en archivo (útil cuando solo se almacena en BD)
--reset-db             Resetear la base de datos antes de procesar
--reset-db-only        Resetear la base de datos sin procesar ningún documento
--provider PROVIDER    Proveedor de LLM a usar (anthropic, azure_openai, aws_bedrock)
```

### Resetear la base de datos

Para eliminar todos los datos de la base de datos:

```bash
python main.py --reset-db-only
```

### Visualizar el grafo de entidades

```bash
python visualize.py
```

Luego, abre tu navegador en http://localhost:5000 para ver la visualización interactiva.

## Estructura del proyecto

```
entity-extractor/
├── main.py                    # Script principal
├── entity_extractor_improved.py # Clase para extraer entidades con múltiples LLMs
├── llm_providers.py           # Sistema de proveedores de LLM
├── config.py                  # Configuración centralizada
├── web_scraper.py             # Funciones para obtener contenido web
├── graph_database.py          # Clase para interactuar con Neo4j
├── visualize.py               # Servidor web para visualizar el grafo
├── reset_db.py                # Utilidad para resetear la base de datos
├── docker-compose.yml         # Configuración de Neo4j en Docker
├── requirements.txt           # Dependencias de Python
├── env.template               # Plantilla para variables de entorno
└── output/                    # Directorio para archivos de salida
```

## Proveedores de LLM soportados

### 1. Anthropic Claude
- **Modelo**: claude-3-5-haiku-20241022
- **Configuración**: Solo requiere API key
- **Ventajas**: Excelente rendimiento, buena relación calidad-precio

### 2. Azure OpenAI
- **Modelo**: Configurable via `AZURE_DEPLOYMENT_NAME` (por defecto: gpt-4o)
- **Configuración**: Requiere endpoint, API key, versión de API y nombre de deployment
- **Ventajas**: Integración con ecosistema Azure, control de costos
- **Variables de configuración**:
  - `AZURE_OPENAI_API_KEY`: Tu clave de API de Azure
  - `AZURE_OPENAI_ENDPOINT`: Endpoint de tu recurso Azure OpenAI
  - `AZURE_OPENAI_API_VERSION`: Versión de la API (por defecto: 2024-02-15-preview)
  - `AZURE_DEPLOYMENT_NAME`: Nombre del deployment (por defecto: gpt-4o)

### 3. AWS Bedrock
- **Modelo**: Configurable via `DEFAULT_AWS_MODEL` (por defecto: anthropic.claude-3-haiku-20240307-v1:0)
- **Configuración**: Usa AWS profiles y regiones
- **Ventajas**: Integración con AWS, múltiples modelos disponibles
- **Variables de configuración**:
  - `AWS_PROFILE`: Perfil de AWS a usar (por defecto: default)
  - `AWS_REGION`: Región de AWS (por defecto: us-east-1)
  - `DEFAULT_AWS_MODEL`: Modelo de Bedrock a usar

## Análisis de Neo4j

Puedes acceder a la interfaz de Neo4j Browser en http://localhost:7474/ con las credenciales configuradas.

Algunas consultas útiles:

```cypher
// Ver todas las entidades
MATCH (e:Entity) RETURN e LIMIT 100;

// Ver todas las relaciones
MATCH (s)-[r:RELATES_TO]->(o) RETURN s, r, o LIMIT 100;

// Ver relaciones inferidas
MATCH (s)-[r:INFERRED]->(o) RETURN s, r, o LIMIT 100;

// Ver documentos analizados
MATCH (d:Document) RETURN d;

// Ver el grafo completo
MATCH p=()-[r:RELATES_TO]->() RETURN p LIMIT 100;

// Encontrar todas las entidades mencionadas en un documento específico
MATCH (e:Entity)-[:MENTIONED_IN]->(d:Document {title: "Nombre del Documento"}) 
RETURN e;

// Ver entidades por proveedor de LLM
MATCH (d:Document)-[:MENTIONED_IN]-(e:Entity)
WHERE d.provider = "anthropic"
RETURN e;
```

## Configuración avanzada

### Personalizar modelos por proveedor

Puedes modificar los modelos y configuraciones en `config.py`:

```python
DEFAULT_CONFIGS = {
    "anthropic": {
        "model": "claude-3-5-sonnet-20241022",  # Cambiar modelo
        "temperature": 0.1,                      # Ajustar temperatura
        "max_tokens": 16384                      # Aumentar tokens
    }
}
```

### Configurar AWS Bedrock

1. Instala AWS CLI: `pip install awscli`
2. Configura tu perfil: `aws configure --profile tu-perfil`
3. Asegúrate de tener permisos para Bedrock en tu cuenta AWS
4. Configura las variables en `.env`:
   ```
   AWS_PROFILE=logicalisSH
   AWS_REGION=eu-central-1
   DEFAULT_AWS_MODEL=anthropic.claude-3-sonnet-20240229-v1:0
   ```

### Configurar Azure OpenAI

1. Crea un recurso Azure OpenAI en el portal de Azure
2. Crea un deployment con el modelo deseado
3. Configura las variables en `.env`:
   ```
   AZURE_OPENAI_API_KEY=tu_clave_api
   AZURE_OPENAI_ENDPOINT=https://tu-recurso.openai.azure.com/
   AZURE_DEPLOYMENT_NAME=gpt-4o
   ```

## Licencia

[MIT](https://opensource.org/licenses/MIT)

## Créditos

- Utiliza [LangChain](https://github.com/langchain-ai/langchain) para la integración con modelos de lenguaje
- Análisis de lenguaje natural mediante múltiples proveedores de IA
- Visualización con [D3.js](https://d3js.org/)
- Base de datos de grafos [Neo4j](https://neo4j.com/)
