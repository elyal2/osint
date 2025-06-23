from neo4j import GraphDatabase
from typing import Dict, List, Any
import logging
import os
from dotenv import load_dotenv
import uuid
from config import AppConfig

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class EntityGraph:
    """Handles storing and retrieving entity and relationship data in Neo4j."""
    
    def __init__(self):
        """Initialize connection to Neo4j database using configuration."""
        # Get Neo4j connection details from configuration
        neo4j_uri = AppConfig.NEO4J_URI
        neo4j_user = AppConfig.NEO4J_USER
        neo4j_password = AppConfig.NEO4J_PASSWORD
        
        if not neo4j_password:
            raise ValueError("NEO4J_PASSWORD no está configurado en el archivo .env")
        
        try:
            self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
            # Test connection
            with self.driver.session() as session:
                result = session.run("RETURN 'Connected to Neo4j' AS message")
                for record in result:
                    logger.info(record["message"])
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {str(e)}")
            raise ConnectionError(f"Could not connect to Neo4j database: {str(e)}")
    
    def close(self):
        """Close the Neo4j driver connection."""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed")
    
    def store_analysis_results(self, analysis_result: Dict, source_url: str = None):
        """
        Store document analysis results in Neo4j.
        
        Args:
            analysis_result (Dict): The analysis result from EntityRelationshipExtractor
            source_url (str, optional): The source URL for web content
            
        Returns:
            str: Document UUID
        """
        try:
            if 'documentAnalysis' not in analysis_result:
                raise ValueError("Invalid analysis result format: missing documentAnalysis key")
            
            doc_analysis = analysis_result['documentAnalysis']
            metadata = doc_analysis.get('metadata', {})
            
            # Create document node
            document_uuid = self._create_document(metadata, source_url)
            logger.info(f"Created document node with UUID: {document_uuid}")
            
            # Process entities
            entity_uuids = {}
            all_entities = []  # Store all entity objects for alias lookup
            for entity_type, entities in doc_analysis.get('entities', {}).items():
                for entity in entities:
                    # Handle both string and dictionary entity formats
                    if isinstance(entity, str):
                        entity_obj = {"name": entity}
                    else:
                        entity_obj = entity
                    entity_uuid = self._create_entity(entity_obj, entity_type)
                    # Store with lowercase entity type to match relationship lookup
                    entity_uuids[(entity_type.lower(), entity_obj['name'])] = entity_uuid
                    all_entities.append((entity_type.lower(), entity_obj['name'], entity_obj))
                    self._link_entity_to_document(entity_uuid, document_uuid)
            
            # Helper for normalization
            def normalize(s):
                import unicodedata
                s = s.lower()
                s = unicodedata.normalize('NFKD', s)
                s = ''.join(c for c in s if not unicodedata.combining(c))
                # Elimina puntuación y espacios
                for ch in "-_'\".,:;()[]{} ":
                    s = s.replace(ch, '')
                return s
            
            # Helper to find entity object by type and name
            def find_entity_obj(entity_type, name):
                for et, ename, eobj in all_entities:
                    if et == entity_type.lower() and normalize(ename) == normalize(name):
                        return eobj
                return None
            
            # Enhanced UUID lookup with alias support and debug logs
            def find_entity_uuid(entity_type, name):
                key = (entity_type, name)
                norm_name = normalize(name)
                
                # Debug: mostrar lo que estamos buscando
                logger.info(f"[UUID-SEARCH] Buscando: '{name}' (tipo: '{entity_type}', normalizado: '{norm_name}')")
                
                # Primero buscar coincidencia exacta
                if key in entity_uuids:
                    logger.info(f"[UUID-SEARCH] ✓ Encontrado coincidencia exacta: {entity_uuids[key]}")
                    return entity_uuids[key]
                
                # Debug: mostrar todas las claves disponibles
                logger.info(f"[UUID-SEARCH] Claves disponibles para tipo '{entity_type}':")
                for (et, ename), uuid in entity_uuids.items():
                    if et == entity_type:
                        logger.info(f"[UUID-SEARCH]   - '{ename}' -> {uuid}")
                
                # Buscar por nombre normalizado
                for (et, ename), uuid in entity_uuids.items():
                    if et != entity_type:
                        continue
                    norm_ename = normalize(ename)
                    logger.info(f"[UUID-SEARCH] Comparando normalizado: '{norm_name}' vs '{norm_ename}'")
                    if norm_ename == norm_name:
                        logger.info(f"[UUID-SEARCH] ✓ Encontrado por normalización: {uuid}")
                        return uuid
                
                # Buscar en aliases (normalizados)
                for (et, ename), uuid in entity_uuids.items():
                    if et != entity_type:
                        continue
                    entity_obj = find_entity_obj(et, ename)
                    if entity_obj and 'aliases' in entity_obj:
                        for alias in entity_obj['aliases']:
                            norm_alias = normalize(alias)
                            logger.info(f"[UUID-SEARCH] Comparando alias normalizado: '{norm_name}' vs '{norm_alias}'")
                            if norm_alias == norm_name:
                                logger.info(f"[UUID-SEARCH] ✓ Encontrado por alias '{alias}': {uuid}")
                                return uuid
                
                logger.warning(f"[UUID-SEARCH] ✗ No encontrado: '{name}' (tipo: '{entity_type}')")
                return None
            
            # Process relationships
            for relationship in doc_analysis.get('relationships', []):
                subject_type = relationship['subject']['type']
                subject_name = relationship['subject']['name']
                object_type = relationship['object']['type']
                object_name = relationship['object']['name']
                subject_uuid = find_entity_uuid(subject_type, subject_name)
                object_uuid = find_entity_uuid(object_type, object_name)
                if not subject_uuid or not object_uuid:
                    logger.warning(f"Could not find UUIDs for relationship: {subject_name} -> {object_name}")
                    continue
                self._create_relationship_with_uuids(relationship, subject_uuid, object_uuid, document_uuid)
            return document_uuid
        except Exception as e:
            logger.error(f"Error storing analysis results: {str(e)}")
            raise
    
    def _create_document(self, metadata: Dict, source_url: str = None) -> str:
        """Create a document node in Neo4j."""
        with self.driver.session() as session:
            result = session.write_transaction(self._tx_create_document, metadata, source_url)
            return result
    
    def _tx_create_document(self, tx, metadata: Dict, source_url: str = None) -> str:
        """Transaction function to create a document node."""
        # Generate a UUID for the document
        doc_uuid = str(uuid.uuid4())
        
        query = """
        CREATE (d:Document {
            uuid: $uuid,
            title: $title,
            analysisDate: $analysisDate,
            language: $language,
            source_url: $source_url,
            provider: $provider
        })
        RETURN d.uuid AS document_uuid
        """
        result = tx.run(
            query,
            uuid=doc_uuid,
            title=metadata.get('title', 'Untitled'),
            analysisDate=metadata.get('analysisDate', ''),
            language=metadata.get('language', 'en'),
            source_url=source_url,
            provider=metadata.get('provider', 'unknown')
        )
        record = result.single()
        return record["document_uuid"] if record else None
    
    def _create_entity(self, entity: Dict, entity_type: str) -> str:
        """Create an entity node in Neo4j if it doesn't exist."""
        entity_name = entity['name']
        logger.debug(f"Searching for entity: '{entity_name}' in database")
        with self.driver.session() as session:
            result = session.write_transaction(self._tx_create_entity, entity, entity_type)
            logger.info(f"Creating entity: {entity_name} with UUID: {result}")
            logger.debug(f"Found UUID: {result} for entity: {entity_name}")
            return result
    
    def _tx_create_entity(self, tx, entity: Dict, entity_type: str) -> str:
        """Transaction function to create an entity node."""
        # Prepare aliases as a string list for Neo4j
        aliases = entity.get('aliases', [])
        if not isinstance(aliases, list):
            aliases = []
        
        # Safely get spanish field
        spanish = entity.get('spanish', '')
        
        query = """
        MERGE (e:Entity {name: $name, type: $type})
        ON CREATE SET e.uuid = $uuid
        SET e.spanish = $spanish,
            e.aliases = $aliases
        RETURN e.uuid AS entity_uuid
        """
        # Generate a UUID for new entities
        entity_uuid = str(uuid.uuid4())
        
        result = tx.run(
            query,
            uuid=entity_uuid,
            name=entity['name'],
            type=entity_type,
            spanish=spanish,
            aliases=aliases
        )
        record = result.single()
        
        # If no UUID was returned (existing entity without UUID), update it
        if not record or not record["entity_uuid"]:
            update_query = """
            MATCH (e:Entity {name: $name, type: $type})
            WHERE e.uuid IS NULL
            SET e.uuid = $uuid
            RETURN e.uuid AS entity_uuid
            """
            update_result = tx.run(
                update_query,
                name=entity['name'],
                type=entity_type,
                uuid=entity_uuid
            )
            update_record = update_result.single()
            return update_record["entity_uuid"] if update_record else entity_uuid
            
        return record["entity_uuid"]
    
    def _link_entity_to_document(self, entity_uuid: str, document_uuid: str):
        """Create a relationship between an entity and a document."""
        with self.driver.session() as session:
            session.write_transaction(self._tx_link_entity_to_document, entity_uuid, document_uuid)
    
    def _tx_link_entity_to_document(self, tx, entity_uuid: str, document_uuid: str):
        """Transaction function to link entity to document."""
        query = """
        MATCH (e:Entity {uuid: $entity_uuid})
        MATCH (d:Document {uuid: $document_uuid})
        MERGE (e)-[r:MENTIONED_IN]->(d)
        RETURN r
        """
        return tx.run(query, entity_uuid=entity_uuid, document_uuid=document_uuid)
    
    def _create_relationship_with_uuids(self, relationship: Dict, subject_uuid: str, object_uuid: str, document_uuid: str):
        """Create a relationship between entities using their UUIDs."""
        with self.driver.session() as session:
            session.write_transaction(
                self._tx_create_relationship_with_uuids, 
                relationship, 
                subject_uuid,
                object_uuid,
                document_uuid
            )

    def _tx_create_relationship_with_uuids(self, tx, relationship: Dict, subject_uuid: str, object_uuid: str, document_uuid: str):
        """Transaction function to create relationships between entities using UUIDs."""
        # Determine relationship type based on source
        rel_type = "RELATES_TO"
        if relationship.get('source') == 'inferred':
            rel_type = "INFERRED"
        # Add category if present
        category_cypher = ", r.category = $category" if 'category' in relationship else ""
        query = f"""
        MATCH (s:Entity {{uuid: $subject_uuid}})
        MATCH (o:Entity {{uuid: $object_uuid}})
        MERGE (s)-[r:{rel_type}]->(o)
        SET r.action = $action,
            r.source = $source{category_cypher}
        RETURN r
        """
        params = {
            'subject_uuid': subject_uuid,
            'object_uuid': object_uuid,
            'action': relationship['action'],
            'source': relationship.get('source', 'explicit')
        }
        if 'category' in relationship:
            params['category'] = relationship['category']
        return tx.run(query, **params)
    
    def get_entity_graph(self, limit: int = 100):
        """
        Retrieve entity graph data from Neo4j.
        
        Args:
            limit (int): Maximum number of entities to retrieve
            
        Returns:
            Dict: Graph data with nodes and links
        """
        try:
            with self.driver.session() as session:
                # Get entities
                entity_query = f"""
                MATCH (e:Entity)
                RETURN e.name AS name, e.type AS type, e.uuid AS id, e.spanish AS spanish
                LIMIT {limit}
                """
                entity_result = session.run(entity_query)
                nodes = []
                for record in entity_result:
                    node = {
                        'id': record['id'],
                        'name': record['name'],
                        'type': record['type'],
                        'spanish': record['spanish'] if record['spanish'] else None
                    }
                    nodes.append(node)
                
                # Get relationships
                relationship_query = f"""
                MATCH (s:Entity)-[r:RELATES_TO]->(t:Entity)
                WHERE s.uuid IN $entity_ids AND t.uuid IN $entity_ids
                RETURN s.name AS source_name, s.uuid AS source_id, s.type AS source_type,
                       t.name AS target_name, t.uuid AS target_id, t.type AS target_type,
                       r.action AS action, r.category AS category, r.source AS source,
                       elementId(r) AS relationship_id
                """
                entity_ids = [node['id'] for node in nodes]
                if not entity_ids:
                    return {'nodes': [], 'links': []}
                
                relationship_result = session.run(relationship_query, entity_ids=entity_ids)
                links = []
                for record in relationship_result:
                    link = {
                        'source': record['source_id'],  # Solo el ID para D3
                        'target': record['target_id'],  # Solo el ID para D3
                        'source_name': record['source_name'],
                        'source_type': record['source_type'],
                        'target_name': record['target_name'],
                        'target_type': record['target_type'],
                        'action': record['action'],
                        'category': record['category'] or 'unknown',
                        'source_type': record['source'] or 'explicit',
                        'id': record['relationship_id']  # ID de la relación para resaltado de caminos
                    }
                    links.append(link)
                
                return {'nodes': nodes, 'links': links}
                
        except Exception as e:
            logger.error(f"Error retrieving entity graph: {str(e)}")
            return {'nodes': [], 'links': []}

    def get_all_entity_names(self) -> List[str]:
        """
        Get all entity names from the database for autocomplete.
        
        Returns:
            List[str]: List of all entity names
        """
        try:
            with self.driver.session() as session:
                query = """
                MATCH (e:Entity)
                RETURN DISTINCT e.name AS name
                ORDER BY e.name
                """
                result = session.run(query)
                names = [record['name'] for record in result]
                return names
        except Exception as e:
            logger.error(f"Error retrieving entity names: {str(e)}")
            return []

    def get_subgraph(self, entity_id: str, depth: int = 3):
        """
        Get a subgraph centered around a specific entity.
        
        Args:
            entity_id (str): The ID of the entity to center the subgraph around
            depth (int): The depth of the subgraph
            
        Returns:
            Dict: Graph data with nodes and links
        """
        try:
            with self.driver.session() as session:
                # Get entities within depth using variable length path without shortestPath
                entity_query = f"""
                MATCH (start:Entity {{uuid: $entity_id}})
                MATCH (start)-[:RELATES_TO*0..{depth}]-(e:Entity)
                RETURN DISTINCT e.name AS name, e.type AS type, e.uuid AS id, e.spanish AS spanish
                """
                entity_result = session.run(entity_query, entity_id=entity_id)
                nodes = []
                for record in entity_result:
                    node = {
                        'id': record['id'],
                        'name': record['name'],
                        'type': record['type'],
                        'spanish': record['spanish'] if record['spanish'] else None
                    }
                    nodes.append(node)
                
                # Get relationships between these entities
                if not nodes:
                    return {'nodes': [], 'links': []}
                
                relationship_query = """
                MATCH (s:Entity)-[r:RELATES_TO]->(t:Entity)
                WHERE s.uuid IN $entity_ids AND t.uuid IN $entity_ids
                RETURN s.name AS source_name, s.uuid AS source_id, s.type AS source_type,
                       t.name AS target_name, t.uuid AS target_id, t.type AS target_type,
                       r.action AS action, r.category AS category, r.source AS source,
                       elementId(r) AS relationship_id
                """
                entity_ids = [node['id'] for node in nodes]
                relationship_result = session.run(relationship_query, entity_ids=entity_ids)
                links = []
                for record in relationship_result:
                    link = {
                        'source': record['source_id'],  # Solo el ID para D3
                        'target': record['target_id'],  # Solo el ID para D3
                        'source_name': record['source_name'],
                        'source_type': record['source_type'],
                        'target_name': record['target_name'],
                        'target_type': record['target_type'],
                        'action': record['action'],
                        'category': record['category'] or 'unknown',
                        'source_type': record['source'] or 'explicit',
                        'id': record['relationship_id']  # ID de la relación para resaltado de caminos
                    }
                    links.append(link)
                
                return {'nodes': nodes, 'links': links}
                
        except Exception as e:
            logger.error(f"Error retrieving subgraph: {str(e)}")
            return {'nodes': [], 'links': []}

    def get_subgraph_by_name(self, entity_name: str, depth: int = 3):
        """
        Get a subgraph centered around a specific entity by name.
        
        Args:
            entity_name (str): The name of the entity to center the subgraph around
            depth (int): The depth of the subgraph
            
        Returns:
            Dict: Graph data with nodes and links
        """
        try:
            with self.driver.session() as session:
                # First find the entity by name
                find_query = """
                MATCH (e:Entity {name: $entity_name})
                RETURN e.uuid AS entity_id
                LIMIT 1
                """
                result = session.run(find_query, entity_name=entity_name)
                record = result.single()
                
                if not record:
                    logger.warning(f"Entity not found: {entity_name}")
                    return {'nodes': [], 'links': []}
                
                entity_id = record['entity_id']
                return self.get_subgraph(entity_id, depth)
                
        except Exception as e:
            logger.error(f"Error retrieving subgraph by name: {str(e)}")
            return {'nodes': [], 'links': []}

    def get_shortest_path(self, from_name: str, to_name: str):
        """
        Get the shortest path between two entities by name.
        
        Args:
            from_name (str): Name of the source entity
            to_name (str): Name of the target entity
            
        Returns:
            Dict: Path information with relationship details
        """
        try:
            with self.driver.session() as session:
                # Check if from and to are the same
                if from_name.lower().strip() == to_name.lower().strip():
                    logger.warning(f"Cannot find path between same entity: {from_name}")
                    return {'path': [], 'relationships': []}
                
                # Use variable length pattern with ordering instead of shortestPath
                # Return both elementId and relationship details for better frontend handling
                query = """
                MATCH (from:Entity {name: $from_name})
                MATCH (to:Entity {name: $to_name})
                MATCH path = (from)-[:RELATES_TO*1..6]-(to)
                WITH path, length(path) as pathLength
                ORDER BY pathLength ASC
                LIMIT 1
                RETURN path, 
                       [rel in relationships(path) | elementId(rel)] AS relationship_ids,
                       [rel in relationships(path) | {
                           id: elementId(rel),
                           source: startNode(rel).name,
                           target: endNode(rel).name,
                           action: rel.action,
                           category: rel.category
                       }] AS relationships
                """
                result = session.run(query, from_name=from_name, to_name=to_name)
                record = result.single()
                
                if record and record['relationship_ids']:
                    return {
                        'path': record['relationship_ids'],
                        'relationships': record['relationships']
                    }
                else:
                    logger.warning(f"No path found between {from_name} and {to_name}")
                    return {'path': [], 'relationships': []}
                    
        except Exception as e:
            logger.error(f"Error finding shortest path: {str(e)}")
            return {'path': [], 'relationships': []}

    def reset_database(self, confirm=False):
        """
        Reset the database by deleting all nodes and relationships.
        
        Args:
            confirm (bool): If True, skip confirmation prompt
            
        Returns:
            bool: True if reset was successful
        """
        if not confirm:
            logger.warning("reset_database called without confirmation")
            return False
        
        try:
            with self.driver.session() as session:
                # Delete all relationships first
                session.run("MATCH ()-[r]-() DELETE r")
                logger.info("Deleted all relationships")
                
                # Delete all nodes
                session.run("MATCH (n) DELETE n")
                logger.info("Deleted all nodes")
                
                return True
                
        except Exception as e:
            logger.error(f"Error resetting database: {str(e)}")
            return False