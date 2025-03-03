from typing import Dict, List, Any
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
import json
from datetime import datetime
import os
import re
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Check for required environment variables
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise ValueError(
        "ANTHROPIC_API_KEY environment variable is not set. "
        "Please set it in your .env file or environment variables."
    )

class EnhancedEntityRelationshipExtractor:
    """Extracts named entities and relationships from text using Claude with enhanced relation extraction."""
    
    def __init__(self):
        self.model = ChatAnthropic(
            model="claude-3-5-haiku-20241022",
            temperature=0,
            anthropic_api_key=ANTHROPIC_API_KEY,
            max_tokens=8192  # Increased max tokens for larger responses
        )
        self.relationship_model = ChatAnthropic(
            model="claude-3-5-haiku-20241022",
            temperature=0.2,  # Slightly higher temperature for more creative relationship extraction
            anthropic_api_key=ANTHROPIC_API_KEY,
            max_tokens=4096
        )

    def _create_extraction_prompt(self, text: str) -> str:
        """Creates the system prompt for entity extraction."""
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
        """Creates a prompt specifically for relationship extraction using extracted entities."""
        # Create formatted lists of entities by type
        entity_lists = {}
        
        for entity_type, entity_items in entities.items():
            entity_lists[entity_type] = [item["name"] for item in entity_items]
        
        # Format entities as text for the prompt
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

Example of inferred relationships:
1. If "John Smith" and "Acme Corp" are mentioned in the same context and John is described as working there, infer "John Smith - works at - Acme Corp"
2. If "Microsoft" released a product in "Seattle", infer "Microsoft - is based in - Seattle"
3. If "Dr. Jane" published research in "2021", infer "Dr. Jane - published in - 2021"

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
  }},
  {{
    "subject": {{
      "type": "Person",
      "name": "Alberto"
    }},
    "action": "moved to",
    "object": {{
      "type": "Location",
      "name": "Paris"
    }}
  }},
  {{
    "subject": {{
      "type": "Person",
      "name": "Alberto"
    }},
    "action": "traveled to",
    "object": {{
      "type": "Location",
      "name": "London"
    }}
  }}
]

Text to analyze for relationships:
{text}"""

    def _create_additional_relationships_prompt(self, entities: Dict) -> str:
        """Creates a prompt to infer additional relationships based only on the entities."""
        # Create formatted lists of entities by type
        entity_text = ""
        for entity_type, entity_items in entities.items():
            if entity_items:
                entity_names = [item["name"] for item in entity_items]
                entity_text += f"{entity_type} entities: {', '.join(entity_names)}\n"
        
        return f"""Based only on the following list of entities extracted from a document, infer logical relationships that likely exist between them.

{entity_text}

Instructions:
- Infer logical Subject-Action-Object relationships between these entities even without seeing the original text.
- Focus on creating connections between otherwise isolated entities.
- Use your knowledge of how these types of entities typically relate to each other.
- Be creative but reasonable in your inferences.
- Focus especially on:
  * Relationships between organizations and locations (headquarters, operations)
  * Relationships between people and organizations (employment, leadership)
  * Relationships between dates and major events
  * Logical connections between locations (is near, is part of)

Common patterns to consider:
- Organizations are typically located in Places
- Organizations are typically founded/established on Dates
- People typically work for Organizations
- People typically live in/visit Locations
- Events typically happen on Dates
- Locations can be geographically related to other Locations

Output Format:
Return ONLY a JSON array of relationships with no additional explanation or text. Each relationship should include:
- subject: Object with 'type' and 'name' matching an entity from the list
- action: String describing the relationship
- object: Object with 'type' and 'name' matching an entity from the list

Example Output:
[
  {{
    "subject": {{
      "type": "Organization",
      "name": "Microsoft"
    }},
    "action": "is headquartered in",
    "object": {{
      "type": "Location",
      "name": "Seattle"
    }}
  }},
  {{
    "subject": {{
      "type": "Person",
      "name": "John Smith"
    }},
    "action": "likely works at",
    "object": {{
      "type": "Organization",
      "name": "Acme Corp"
    }}
  }}
]

Be thorough but only make reasonable inferences based on the entity types and common knowledge."""

    def analyze_text(self, text: str, doc_title: str = "Untitled Document", language: str = "en") -> Dict:
        """Analyzes text to extract entities and relationships using a two-step process."""
        try:
            # Step 1: Extract entities
            entities_result = self._extract_entities(text)
            
            if 'documentAnalysis' not in entities_result:
                logger.error("Failed to extract entities")
                return self._create_error_response("Failed to extract entities")
            
            doc_analysis = entities_result['documentAnalysis']
            
            if 'entities' not in doc_analysis:
                logger.error("No entities found in analysis response")
                return self._create_error_response("No entities found in response")
            
            entities = doc_analysis['entities']
            
            # Step 2: Extract explicit relationships from text using entities
            explicit_relationships = self._extract_relationships(text, entities)
            
            # Step 3: Infer additional relationships based on entities only
            inferred_relationships = self._infer_additional_relationships(entities)
            
            # Combine relationships, removing duplicates
            combined_relationships = self._merge_relationships(explicit_relationships, inferred_relationships)
            
            # Add metadata
            doc_analysis['metadata'] = {
                "title": doc_title,
                "analysisDate": datetime.now().strftime("%Y-%m-%d"),
                "language": language
            }
            
            # Add relationships to result
            doc_analysis['relationships'] = combined_relationships
            
            return entities_result
            
        except Exception as e:
            logger.error(f"Error in text analysis: {str(e)}")
            return self._create_error_response(f"Analysis failed: {str(e)}")
    
    def _extract_entities(self, text: str) -> Dict:
        """Extract entities from text."""
        try:
            messages = [
                SystemMessage(content="""You are an expert at extracting entities from text.
Output ONLY valid JSON with no additional text or explanation.
Follow the example structure EXACTLY, including all fields."""),
                HumanMessage(content=self._create_extraction_prompt(text))
            ]
            
            # Get model response
            response = self.model.invoke(messages)
            
            try:
                # Parse the JSON response
                content = response.content.strip()
                if not (content.startswith('{') and content.endswith('}')):
                    logger.warning(f"Received incomplete JSON response: {content[:100]}...")
                    return self._create_error_response("Incomplete JSON response")
                
                result = json.loads(content)
                return result
                
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing JSON: {str(e)}")
                logger.debug(f"Response content: {response.content[:200]}...")
                return self._create_error_response("Failed to parse JSON response")
                
        except Exception as e:
            logger.error(f"Error in entity extraction: {str(e)}")
            return self._create_error_response(f"Entity extraction failed: {str(e)}")

    def _extract_relationships(self, text: str, entities: Dict) -> List[Dict]:
        """Extract relationships between entities from text."""
        try:
            messages = [
                SystemMessage(content="""You are an expert at extracting relationships between entities.
Output ONLY valid JSON with no additional text or explanation.
Follow the example structure EXACTLY, including all fields."""),
                HumanMessage(content=self._create_relationship_prompt(text, entities))
            ]
            
            # Get model response
            response = self.relationship_model.invoke(messages)
            
            try:
                # Parse the JSON response
                content = response.content.strip()
                
                # Extract JSON array if embedded in backticks or other formatting
                json_match = re.search(r'(\[.*?\])', content, re.DOTALL)
                if json_match:
                    content = json_match.group(1)
                
                relationships = json.loads(content)
                return relationships
                
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing relationships JSON: {str(e)}")
                logger.debug(f"Response content: {response.content[:200]}...")
                return []
                
        except Exception as e:
            logger.error(f"Error in relationship extraction: {str(e)}")
            return []

    def _infer_additional_relationships(self, entities: Dict) -> List[Dict]:
        """Infer additional relationships based only on the entities."""
        try:
            messages = [
                SystemMessage(content="""You are an expert at inferring logical relationships between entities.
Output ONLY valid JSON with no additional text or explanation.
Follow the example structure EXACTLY, including all fields."""),
                HumanMessage(content=self._create_additional_relationships_prompt(entities))
            ]
            
            # Get model response
            response = self.relationship_model.invoke(messages)
            
            try:
                # Parse the JSON response
                content = response.content.strip()
                
                # Extract JSON array if embedded in backticks or other formatting
                json_match = re.search(r'(\[.*?\])', content, re.DOTALL)
                if json_match:
                    content = json_match.group(1)
                
                relationships = json.loads(content)
                
                # Tag inferred relationships
                for rel in relationships:
                    # Add a flag to indicate this is an inferred relationship
                    rel["inferred"] = True
                
                return relationships
                
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing inferred relationships JSON: {str(e)}")
                logger.debug(f"Response content: {response.content[:200]}...")
                return []
                
        except Exception as e:
            logger.error(f"Error in relationship inference: {str(e)}")
            return []

    def _merge_relationships(self, explicit_relationships: List[Dict], inferred_relationships: List[Dict]) -> List[Dict]:
        """Merge explicit and inferred relationships, removing duplicates."""
        # Create a set of relationship signatures for deduplication
        relationship_signatures = set()
        merged_relationships = []
        
        # Process explicit relationships first (we prioritize these)
        for rel in explicit_relationships:
            # Create a signature for this relationship
            signature = (
                rel["subject"]["type"],
                rel["subject"]["name"],
                rel["action"],
                rel["object"]["type"],
                rel["object"]["name"]
            )
            
            if signature not in relationship_signatures:
                relationship_signatures.add(signature)
                # Add type to make it compatible with original structure
                if "type" not in rel:
                    rel["type"] = "SAO"
                merged_relationships.append(rel)
        
        # Then add inferred relationships if they don't duplicate existing ones
        for rel in inferred_relationships:
            # Create a signature for this relationship
            signature = (
                rel["subject"]["type"],
                rel["subject"]["name"],
                rel["action"],
                rel["object"]["type"],
                rel["object"]["name"]
            )
            
            if signature not in relationship_signatures:
                relationship_signatures.add(signature)
                # Add type to make it compatible with original structure
                if "type" not in rel:
                    rel["type"] = "SAO"
                merged_relationships.append(rel)
        
        return merged_relationships
    
    def _create_error_response(self, error_message: str) -> Dict:
        """Creates a structured error response."""
        return {
            "documentAnalysis": {
                "metadata": {
                    "title": "Error",
                    "analysisDate": datetime.now().strftime("%Y-%m-%d"),
                    "language": "en",
                    "error": error_message
                },
                "entities": {
                    "Person": [],
                    "Organization": [],
                    "Location": [],
                    "Date": []
                },
                "relationships": []
            }
        }