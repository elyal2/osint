# Entity Relationship Extractor

Esta herramienta extrae entidades nombradas (personas, organizaciones, lugares, fechas) y sus relaciones a partir de documentos de texto, páginas web y **archivos PDF**. Utiliza modelos de lenguaje avanzados y multimodales para realizar un análisis sofisticado del contenido, y almacena los resultados en archivos JSON y opcionalmente en una base de datos Neo4j para visualización y análisis de grafos.

## Características

- **Extracción de entidades** en siete categorías: Persona, Organización, Lugar, Fecha, Evento, Objeto, Código
- **Identificación de relaciones** entre entidades en formato Sujeto-Acción-Objeto
- **Análisis de múltiples formatos**: Texto plano, páginas web y archivos PDF
- **Análisis avanzado de PDFs**: Procesamiento página por página con OCR y contexto solapado
- **Soporte para múltiples proveedores de LLM**: Anthropic Claude, Azure OpenAI, AWS Bedrock
- **Procesamiento multilingüe** con traducciones al español
- **Almacenamiento en base de datos Neo4j** para análisis de grafos
- **Visualización interactiva** de las relaciones entre entidades
- **Enriquecimiento progresivo** de la base de conocimiento a medida que se analizan más documentos
- **Deduplicación inteligente** de entidades y relaciones
- **Sistema robusto de UUIDs** para garantizar la integridad de las relaciones en la base de datos

## Análisis de PDFs Mejorado

### Procesamiento Página por Página
El sistema ahora analiza PDFs de manera más efectiva mediante:

- **OCR automático**: Extrae texto de PDFs escaneados o con imágenes
- **Análisis individual por página**: Cada página se procesa por separado para mayor precisión
- **Contexto solapado**: Incluye fragmentos de páginas adyacentes para mantener continuidad
- **Fusión inteligente**: Combina entidades y relaciones de todas las páginas eliminando duplicados
- **Análisis de relaciones entre páginas**: Identifica conexiones entre entidades de diferentes páginas

### Ventajas del Nuevo Sistema
- **Mayor precisión**: Mejor extracción de entidades en documentos complejos
- **Manejo de OCR**: Corrección automática de errores de reconocimiento óptico
- **Contexto preservado**: Mantiene la continuidad narrativa entre páginas
- **Escalabilidad**: Funciona eficientemente con documentos de cualquier tamaño

## Requisitos previos

- Python 3.8 o superior
- Docker y Docker Compose (para Neo4j)
- API Key de al menos uno de los proveedores de LLM soportados
- **Dependencias adicionales para OCR**:
  - `pytesseract` (para reconocimiento óptico de caracteres)
  - `Pillow` (para procesamiento de imágenes)
  - `PyMuPDF` (para manipulación de PDFs)

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

**Nota**: Para el análisis de PDFs con OCR, asegúrate de tener instalado Tesseract OCR en tu sistema:

**macOS:**
```bash
brew install tesseract
```

**Ubuntu/Debian:**
```bash
sudo apt-get install tesseract-ocr
```

**Windows:**
Descarga e instala desde [GitHub Tesseract](https://github.com/UB-Mannheim/tesseract/wiki)

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

### Analizar un archivo PDF (Nuevo sistema mejorado)

```bash
python main.py --pdf ruta/al/documento.pdf --store-db
```

**Características del análisis de PDFs:**
- Procesamiento automático página por página
- OCR automático para PDFs escaneados
- Contexto solapado entre páginas
- Deduplicación inteligente de entidades
- Análisis de relaciones entre páginas

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

### Modo debug

Para ver los prompts enviados al LLM y sus respuestas:

```bash
# Analizar con debug habilitado
python main.py --file documento.txt --debug

# Analizar PDF con debug
python main.py --pdf documento.pdf --provider azure_openai --debug --store-db
```

El modo debug mostrará:
- Los prompts completos enviados al LLM
- Las respuestas completas recibidas
- Información detallada del proceso de análisis
- Progreso del análisis página por página (para PDFs)
- Información de deduplicación de entidades

### Opciones adicionales

```
--file FILE            Ruta al archivo de texto a analizar
--pdf PDF              Ruta al archivo PDF a analizar (nuevo sistema OCR)
--url URL              URL de la página web a analizar
--language LANGUAGE    Idioma del texto (por defecto: en)
--output-dir DIR       Directorio para guardar resultados (por defecto: output)
--store-db             Almacenar resultados en la base de datos Neo4j
--skip-file            No guardar resultados en archivo (útil cuando solo se almacena en BD)
--reset-db             Resetear la base de datos antes de procesar
--reset-db-only        Resetear la base de datos sin procesar ningún documento
--provider PROVIDER    Proveedor de LLM a usar (anthropic, azure_openai, aws_bedrock)
--debug                Habilitar modo debug para mostrar prompts y respuestas del LLM
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
├── llm_providers.py           # Sistema de proveedores de LLM (incluye análisis PDF mejorado)
├── config.py                  # Configuración centralizada
├── web_scraper.py             # Funciones para obtener contenido web
├── graph_database.py          # Clase para interactuar con Neo4j (UUIDs corregidos)
├── visualize.py               # Servidor web para visualizar el grafo
├── reset_db.py                # Utilidad para resetear la base de datos
├── docker-compose.yml         # Configuración de Neo4j en Docker
├── requirements.txt           # Dependencias de Python
├── env.template               # Plantilla para variables de entorno
├── samples/                   # Documentos de ejemplo para pruebas
└── output/                    # Directorio para archivos de salida
```

## Mejoras Recientes

### Corrección del Sistema de UUIDs
- **Problema resuelto**: Inconsistencia en la normalización de tipos de entidades entre almacenamiento y búsqueda
- **Solución**: Normalización consistente de tipos de entidades en todo el flujo
- **Resultado**: Las relaciones ahora se crean correctamente en Neo4j

### Análisis de PDFs Avanzado
- **Procesamiento página por página**: Cada página se analiza individualmente
- **OCR automático**: Extracción de texto de PDFs escaneados
- **Contexto solapado**: Fragmentos de páginas adyacentes para continuidad
- **Deduplicación inteligente**: Eliminación automática de entidades duplicadas
- **Análisis de relaciones entre páginas**: Conexiones entre entidades de diferentes páginas

### Extracción de Entidades Mejorada
- **Tipos de entidades normalizados**: Uso consistente de "Person", "Organization", "Location", etc.
- **Deduplicación en tiempo real**: Evita entidades duplicadas durante la extracción
- **Aliases mejorados**: Mejor manejo de variantes y traducciones
- **Relaciones más precisas**: Categorización mejorada de relaciones

## Proveedores de LLM soportados

### 1. Anthropic Claude
- **Modelo**: claude-3-5-haiku-20241022
- **Configuración**: Solo requiere API key
- **Ventajas**: Excelente rendimiento, buena relación calidad-precio
- **Soporte PDF**: Completo con análisis página por página

### 2. Azure OpenAI
- **Modelo**: Configurable via `AZURE_DEPLOYMENT_NAME` (por defecto: gpt-4o)
- **Configuración**: Requiere endpoint, API key, versión de API y nombre de deployment
- **Ventajas**: Integración con ecosistema Azure, control de costos
- **Soporte PDF**: Completo con análisis página por página
- **Variables de configuración**:
  - `AZURE_OPENAI_API_KEY`: Tu clave de API de Azure
  - `AZURE_OPENAI_ENDPOINT`: Endpoint de tu recurso Azure OpenAI
  - `AZURE_OPENAI_API_VERSION`: Versión de la API (por defecto: 2024-02-15-preview)
  - `AZURE_DEPLOYMENT_NAME`: Nombre del deployment (por defecto: gpt-4o)

### 3. AWS Bedrock
- **Modelo**: Configurable via `DEFAULT_AWS_MODEL` (por defecto: anthropic.claude-3-haiku-20240307-v1:0)
- **Configuración**: Usa AWS profiles y regiones
- **Ventajas**: Integración con AWS, múltiples modelos disponibles
- **Soporte PDF**: Completo con análisis página por página
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

// Ver eventos y sus participantes
MATCH (e:Entity {type: "Event"})-[r:RELATES_TO]-(p:Entity)
WHERE p.type IN ["Person", "Organization"]
RETURN e, r, p;

// Ver objetos y sus propietarios/usuarios
MATCH (o:Entity {type: "Object"})-[r:RELATES_TO]-(e:Entity)
WHERE e.type IN ["Person", "Organization"]
RETURN o, r, e;

// Ver códigos y operaciones relacionadas
MATCH (c:Entity {type: "Code"})-[r:RELATES_TO]-(e:Entity)
RETURN c, r, e;

// Ver entidades por tipo
MATCH (e:Entity)
WHERE e.type IN ["Event", "Object", "Code"]
RETURN e.type, count(e) as count
ORDER BY count DESC;

// Ver relaciones por categoría
MATCH (s)-[r:RELATES_TO]->(o)
RETURN r.category, count(r) as count
ORDER BY count DESC;

// Ver documentos analizados con método de análisis
MATCH (d:Document)
RETURN d.title, d.provider, d.analysisDate
ORDER BY d.analysisDate DESC;
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

## Solución de problemas

### Problemas comunes con PDFs
- **OCR no funciona**: Asegúrate de tener Tesseract instalado correctamente
- **PDFs muy grandes**: El sistema procesa página por página, por lo que no hay límite de tamaño
- **Calidad de extracción**: Usa el modo debug para ver el proceso detallado

### Problemas con la base de datos
- **Relaciones no se crean**: Verifica que las entidades existan antes de crear relaciones
- **UUIDs no encontrados**: El sistema ahora normaliza correctamente los tipos de entidades
- **Errores de conexión**: Verifica que Neo4j esté ejecutándose con Docker Compose

### Optimización del rendimiento
- **PDFs grandes**: El procesamiento página por página es eficiente incluso para documentos extensos
- **Múltiples documentos**: Procesa documentos secuencialmente para evitar límites de API
- **Debug mode**: Usa solo cuando sea necesario para evitar logs excesivos

## Licencia

[MIT](https://opensource.org/licenses/MIT)

## Créditos

- Utiliza [LangChain](https://github.com/langchain-ai/langchain) para la integración con modelos de lenguaje
- Análisis de lenguaje natural mediante múltiples proveedores de IA
- Visualización con [D3.js](https://d3js.org/)
- Base de datos de grafos [Neo4j](https://neo4j.com/)
- OCR con [Tesseract](https://github.com/tesseract-ocr/tesseract)
- Procesamiento de PDFs con [PyMuPDF](https://pymupdf.readthedocs.io/)
