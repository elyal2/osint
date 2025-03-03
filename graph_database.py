from neo4j import GraphDatabase
from typing import Dict, List, Any
import logging
import os
from dotenv import load_dotenv
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class EntityGraph:
    """Handles storing and retrieving entity and relationship data in Neo4j."""
    
    def __init__(self):
        """Initialize connection to Neo4j database using environment variables."""
        # Get Neo4j connection details from environment variables
        neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        neo4j_password = os.getenv("NEO4J_PASSWORD", "neo4j")
        
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
                    entity_uuid = self._create_entity(entity, entity_type)
                    # Store UUID for relationship creation
                    entity_uuids[(entity_type, entity['name'])] = entity_uuid
                    
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
            source_url: $source_url
        })
        RETURN d.uuid AS document_uuid
        """
        result = tx.run(
            query,
            uuid=doc_uuid,
            title=metadata.get('title', 'Untitled'),
            analysisDate=metadata.get('analysisDate', ''),
            language=metadata.get('language', 'en'),
            source_url=source_url
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
            spanish=entity.get('spanish', ''),
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
        
        # Get entity UUIDs
        subject_key = (subject_type, subject_name)
        object_key = (object_type, object_name)
        
        if subject_key not in entity_uuids or object_key not in entity_uuids:
            logger.warning(f"Missing entity for relationship: {subject_name} ({subject_type}) -> {object_name} ({object_type})")
            
            # Create missing entities if necessary
            if subject_key not in entity_uuids:
                subject_uuid = self._create_entity({"name": subject_name, "aliases": []}, subject_type)
                entity_uuids[subject_key] = subject_uuid
                logger.info(f"Created missing subject entity: {subject_name} ({subject_type})")
                
                # Link to document
                self._link_entity_to_document(subject_uuid, document_uuid)
            
            if object_key not in entity_uuids:
                object_uuid = self._create_entity({"name": object_name, "aliases": []}, object_type)
                entity_uuids[object_key] = object_uuid
                logger.info(f"Created missing object entity: {object_name} ({object_type})")
                
                # Link to document
                self._link_entity_to_document(object_uuid, document_uuid)
        
        subject_uuid = entity_uuids[subject_key]
        object_uuid = entity_uuids[object_key]
        
        query = """
        MATCH (s:Entity {uuid: $subject_uuid})
        MATCH (o:Entity {uuid: $object_uuid})
        MERGE (s)-[r:RELATES_TO {action: $action, document_uuid: $document_uuid}]->(o)
        RETURN r
        """
        result = tx.run(
            query,
            subject_uuid=subject_uuid,
            object_uuid=object_uuid,
            document_uuid=document_uuid,
            action=relationship['action']
        )
        return result
    
    def get_entity_graph(self, limit: int = 100):
        """
        Retrieve entity graph data suitable for visualization.
        
        Returns:
            Dict: Contains nodes and relationships for visualization
        """
        with self.driver.session() as session:
            # Get entities (nodes)
            result_nodes = session.run("""
                MATCH (e:Entity)
                RETURN e.uuid AS id, e.name AS name, e.type AS type, e.spanish AS spanish
                LIMIT $limit
            """, limit=limit)
            
            nodes = [
                {
                    "id": record["id"],
                    "name": record["name"],
                    "type": record["type"],
                    "spanish": record["spanish"]
                }
                for record in result_nodes
            ]
            
            # Get relationships (edges)
            result_rels = session.run("""
                MATCH (s:Entity)-[r:RELATES_TO]->(o:Entity)
                RETURN s.uuid AS source, o.uuid AS target, r.action AS action
                LIMIT $limit
            """, limit=limit)
            
            relationships = [
                {
                    "source": record["source"],
                    "target": record["target"],
                    "action": record["action"]
                }
                for record in result_rels
            ]
            
            return {
                "nodes": nodes,
                "relationships": relationships
            }

    def reset_database(self, confirm=False):
        """
        Reset the entire database, removing all nodes and relationships.
        
        Args:
            confirm (bool): Safety parameter that must be set to True to perform reset
            
        Returns:
            bool: True if reset was successful, False otherwise
        """
        if not confirm:
            logger.warning("Database reset was requested but not confirmed. Set confirm=True to proceed.")
            return False
        
        try:
            with self.driver.session() as session:
                # Delete all relationships first
                session.run("MATCH ()-[r]-() DELETE r")
                logger.info("All relationships deleted")
                
                # Then delete all nodes
                session.run("MATCH (n) DELETE n")
                logger.info("All nodes deleted")
                
                # Verify the database is empty
                count_result = session.run("MATCH (n) RETURN count(n) AS node_count").single()
                relationship_count = session.run("MATCH ()-[r]-() RETURN count(r) AS rel_count").single()
                
                if count_result and relationship_count:
                    node_count = count_result["node_count"]
                    rel_count = relationship_count["rel_count"]
                    
                    if node_count == 0 and rel_count == 0:
                        logger.info("Database reset successful. Database is now empty.")
                        return True
                    else:
                        logger.warning(f"Database may not be completely empty. Found {node_count} nodes and {rel_count} relationships.")
                        return False
                
                return True
                
        except Exception as e:
            logger.error(f"Error resetting database: {str(e)}")
            return False