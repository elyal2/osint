from typing import Dict, List, Any
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
import json
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Check for required environment variables
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise ValueError(
        "ANTHROPIC_API_KEY environment variable is not set. "
        "Please set it in your .env file or environment variables."
    )

class EntityRelationshipExtractor:
    """Extracts named entities and relationships from text using Claude."""
    
    def __init__(self):
        self.model = ChatAnthropic(
            model="claude-3-5-haiku-20241022",
            temperature=0,
            anthropic_api_key=ANTHROPIC_API_KEY,
            max_tokens=8192  # Increased max tokens for larger responses
        )

    def _create_extraction_prompt(self, text: str) -> str:
        """Creates the system prompt for entity and relationship extraction."""
        return f"""Analyze the provided text to extract named entities (Person, Organization, Location, and Date) and relationships (Subject-Action-Object) only where the subject and object are entities.
- For each entity, include any aliases or pronouns by which the entity is referenced.
- Include a spanish translation only for:
  * Traditional place names that have official or commonly used Spanish versions (e.g., London -> Londres, New York -> Nueva York)
  * Dates in standard format
  * Do NOT translate widely recognized names, technology hubs, company names, or branded terms (e.g., Silicon Valley, Wall Street, Times Square)
- Identify relevant dates as "Date" entities.
- Extract only Subject-Action-Object (SAO) relationships between entities (e.g., Person to Organization, Person to Location, Organization to Location, etc.).
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
                "spanish": "Paris"
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
        }},
        "relationships": [
        {{
            "type": "SAO",
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
            "type": "SAO",
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
            "type": "SAO",
            "subject": {{
                "type": "Person",
                "name": "Alberto"
            }},
            "action": "traveled to",
            "object": {{
                "type": "Location",
                "name": "London"
            }}
        }}]
    }}
}}

Text to analyze:
{text}"""

    def analyze_text(self, text: str, doc_title: str = "Untitled Document", language: str = "en") -> Dict:
        """Analyzes text to extract entities and relationships."""
        try:
            messages = [
                SystemMessage(content="""You are an expert at extracting entities and relationships from text.
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
                    print(f"Warning: Received incomplete JSON response: {content[:100]}...")
                    return self._create_error_response("Incomplete JSON response")
                
                result = json.loads(content)
                
                # Basic structure validation
                if not isinstance(result, dict) or 'documentAnalysis' not in result:
                    print(f"Warning: Invalid response structure. Received: {content[:100]}...")
                    return self._create_error_response("Invalid response structure")
                
                doc_analysis = result['documentAnalysis']
                
                if 'entities' not in doc_analysis:
                    print("Warning: Missing entities in response")
                    return self._create_error_response("Missing entities in response")
                
                # Update metadata
                doc_analysis['metadata'] = {
                    "title": doc_title,
                    "analysisDate": datetime.now().strftime("%Y-%m-%d"),
                    "language": language
                }
                
                return result
                
            except json.JSONDecodeError as e:
                print(f"Error parsing JSON: {str(e)}")
                print(f"Response content: {response.content[:200]}...")
                return self._create_error_response("Failed to parse JSON response")
                
        except Exception as e:
            print(f"Error in text analysis: {str(e)}")
            return self._create_error_response(f"Analysis failed: {str(e)}")
    
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