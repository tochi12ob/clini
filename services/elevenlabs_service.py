"""
ElevenLabs Agent Creator
Simple service for creating conversational AI agents
"""
import os
import logging
import requests
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ElevenLabsAgentCreator:
    """Service for creating ElevenLabs conversational AI agents"""
    
    def __init__(self):
        # Use the new ElevenLabs API key
        self.api_key = "sk_911c468b5acba9938859200fdc4f9b8ffa8584b7b17e7487"
        self.base_url = "https://api.elevenlabs.io/v1"
        
        if not self.api_key:
            logger.error("ElevenLabs API key not found")
            raise ValueError("ElevenLabs API key is required")
        
        self.headers = {
            "Accept": "application/json",
            "xi-api-key": self.api_key,
            "Content-Type": "application/json"
        }
    
    def create_agent(self) -> Optional[str]:
        """
        Create a conversational AI agent
        
        Returns:
            Agent ID string or None if failed
        """
        try:
            # Default agent configuration
            agent_config = {
                "conversation_config": {}
            }
            
            # Create the agent
            response = requests.post(
                f"{self.base_url}/convai/agents/create",
                headers=self.headers,
                json=agent_config
            )
            
            if response.status_code in [200, 201]:
                agent_data = response.json()
                agent_id = agent_data.get("agent_id")
                
                logger.info(f"Successfully created ElevenLabs agent: {agent_id}")
                return agent_id
            else:
                logger.error(f"Failed to create ElevenLabs agent. Status: {response.status_code}, Response: {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error creating ElevenLabs agent: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error creating ElevenLabs agent: {str(e)}")
            return None


# Usage example
if __name__ == "__main__":
    creator = ElevenLabsAgentCreator()
    agent_id = creator.create_agent()
    
    if agent_id:
        print(f"Agent created successfully: {agent_id}")
    else:
        print("Failed to create agent")