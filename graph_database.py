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
            for entity_type, entities in doc_analysis.get('entities', {}).items():
                for entity in entities:
                    # Handle both string and dictionary entity formats
                    if isinstance(entity, str):
                        entity_obj = {"name": entity}
                    else:
                        entity_obj = entity
                    
                    entity_uuid = self._create_entity(entity_obj, entity_type)
                    # Store UUID for relationship creation
                    entity_uuids[(entity_type, entity_obj['name'])] = entity_uuid
                    
                    # Link entity to document
                    self._link_entity_to_document(entity_uuid, document_uuid)
            
            # Process relationships
            for relationship in doc_analysis.get('relationships', []):
                self._create_relationship(relationship, entity_uuids, document_uuid)
                
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
        with self.driver.session() as session:
            result = session.write_transaction(self._tx_create_entity, entity, entity_type)
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
    
    def _create_relationship(self, relationship: Dict, entity_uuids: Dict, document_uuid: str):
        """Create a relationship between entities."""
        with self.driver.session() as session:
            session.write_transaction(
                self._tx_create_relationship, 
                relationship, 
                entity_uuids,
                document_uuid
            )
    
    def _tx_create_relationship(self, tx, relationship: Dict, entity_uuids: Dict, document_uuid: str):
        """Transaction function to create relationships between entities."""
        subject_type = relationship['subject']['type']
        subject_name = relationship['subject']['name']
        object_type = relationship['object']['type']
        object_name = relationship['object']['name']
        
        # Get UUIDs for subject and object
        subject_uuid = entity_uuids.get((subject_type, subject_name))
        object_uuid = entity_uuids.get((object_type, object_name))
        
        if not subject_uuid or not object_uuid:
            logger.warning(f"Could not find UUIDs for relationship: {subject_name} -> {object_name}")
            return
        
        # Determine relationship type based on source
        rel_type = "RELATES_TO"
        if relationship.get('source') == 'inferred':
            rel_type = "INFERRED"
        
        query = f"""
        MATCH (s:Entity {{uuid: $subject_uuid}})
        MATCH (o:Entity {{uuid: $object_uuid}})
        MERGE (s)-[r:{rel_type}]->(o)
        SET r.action = $action,
            r.source = $source
        RETURN r
        """
        
        return tx.run(
            query,
            subject_uuid=subject_uuid,
            object_uuid=object_uuid,
            action=relationship['action'],
            source=relationship.get('source', 'explicit')
        )
    
    def get_entity_graph(self, limit: int = 100):
        """
        Get entity graph data for visualization.
        
        Args:
            limit (int): Maximum number of nodes to return
        
        Returns:
            Dict: Graph data with nodes and links
        """
        with self.driver.session() as session:
            # Primero verificar si hay entidades
            count_result = session.run("MATCH (e:Entity) RETURN count(e) as count")
            entity_count = count_result.single()["count"]
            
            if entity_count == 0:
                return {"nodes": [], "links": []}
            
            # Get nodes
            nodes_query = f"""
                MATCH (e:Entity)
                RETURN e.uuid AS id, e.name AS name, e.type AS type, e.spanish AS spanish
            LIMIT {limit}
            """
            
            nodes_result = session.run(nodes_query)
            nodes = [
                {
                    "id": record["id"],
                    "name": record["name"],
                    "type": record["type"],
                    "spanish": record["spanish"] or ""
                }
                for record in nodes_result
            ]
            
            if not nodes:
                return {"nodes": [], "links": []}
            
            # Get node IDs for relationship query
            node_ids = [node["id"] for node in nodes]
            
            # Get relationships
            links_query = """
            MATCH (s:Entity)-[r]->(o:Entity)
            WHERE s.uuid IN $node_ids AND o.uuid IN $node_ids
            RETURN s.uuid AS source, o.uuid AS target, r.action AS action, 
                   type(r) AS rel_type, r.source AS source_type
            LIMIT 1000
            """
            
            links_result = session.run(links_query, node_ids=node_ids)
            links = [
                {
                    "source": record["source"],
                    "target": record["target"],
                    "action": record["action"],
                    "source": record["source_type"] or "explicit"
                }
                for record in links_result
            ]
            
            return {
                "nodes": nodes,
                "links": links
            }

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