# Entity Relationship Extractor

Esta herramienta extrae entidades nombradas (personas, organizaciones, lugares, fechas) y sus relaciones a partir de documentos de texto o páginas web. Utiliza el modelo Claude de Anthropic para realizar un análisis sofisticado del texto, y almacena los resultados en archivos JSON y opcionalmente en una base de datos Neo4j para visualización y análisis de grafos.

## Características

- **Extracción de entidades** en cuatro categorías: Persona, Organización, Lugar, Fecha
- **Identificación de relaciones** entre entidades en formato Sujeto-Acción-Objeto
- **Procesamiento multilingüe** con traducciones al español para nombres de lugares y fechas
- **Análisis de páginas web** con capacidad para extraer texto de URLs
- **Almacenamiento en base de datos Neo4j** para realizar análisis de grafos
- **Visualización interactiva** de las relaciones entre entidades
- **Enriquecimiento progresivo** de la base de conocimiento a medida que se analizan más documentos

## Requisitos previos

- Python 3.8 o superior
- Docker y Docker Compose (para Neo4j)
- API Key de Anthropic (para Claude)

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
cp .env.template .env
```

Edita el archivo `.env` y añade tu API key de Anthropic y configura las credenciales de Neo4j:

```
# API Keys
ANTHROPIC_API_KEY=tu_clave_api_aqui

# Neo4j Database Configuration
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=tupassword
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

### Analizar una página web

```bash
python main.py --url https://ejemplo.com --store-db
```

### Opciones adicionales

```
--language LANGUAGE    Idioma del texto (por defecto: en)
--output-dir DIR       Directorio para guardar resultados (por defecto: output)
--store-db             Almacenar resultados en la base de datos Neo4j
--skip-file            No guardar resultados en archivo (útil cuando solo se almacena en BD)
--reset-db             Resetear la base de datos antes de procesar
--reset-db-only        Resetear la base de datos sin procesar ningún documento
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
├── entity_extractor.py        # Clase para extraer entidades con Claude
├── web_scraper.py             # Funciones para obtener contenido web
├── graph_database.py          # Clase para interactuar con Neo4j
├── visualize.py               # Servidor web para visualizar el grafo
├── reset_db.py                # Utilidad para resetear la base de datos
├── docker-compose.yml         # Configuración de Neo4j en Docker
├── requirements.txt           # Dependencias de Python
├── .env.template              # Plantilla para variables de entorno
└── output/                    # Directorio para archivos de salida
```

## Análisis de Neo4j

Puedes acceder a la interfaz de Neo4j Browser en http://localhost:7474/ con las credenciales configuradas.

Algunas consultas útiles:

```cypher
// Ver todas las entidades
MATCH (e:Entity) RETURN e LIMIT 100;

// Ver todas las relaciones
MATCH (s)-[r:RELATES_TO]->(o) RETURN s, r, o LIMIT 100;

// Ver documentos analizados
MATCH (d:Document) RETURN d;

// Ver el grafo completo
MATCH p=()-[r:RELATES_TO]->() RETURN p LIMIT 100;

// Encontrar todas las entidades mencionadas en un documento específico
MATCH (e:Entity)-[:MENTIONED_IN]->(d:Document {title: "Nombre del Documento"}) 
RETURN e;
```

## Licencia

[MIT](https://opensource.org/licenses/MIT)

## Créditos

- Utiliza [LangChain](https://github.com/langchain-ai/langchain) para la integración con modelos de lenguaje
- Análisis de lenguaje natural mediante [Claude API](https://docs.anthropic.com/claude/reference/getting-started-with-the-api)
- Visualización con [D3.js](https://d3js.org/)
- Base de datos de grafos [Neo4j](https://neo4j.com/)
