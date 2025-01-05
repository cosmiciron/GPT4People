import asyncio
from datetime import datetime
from itertools import count
from typing import List, Dict

from loguru import logger
from base.base import IntentType, Intent, PromptRequest
from base.util import Util
from core.coreInterface import CoreInterface
from core.tam import TAM

class Orchestrator:
    def __init__(self, coreInst: CoreInterface):
        self.coreInst = coreInst  # This should be an instance of the core's LLM
        self.tam = TAM(coreInst)
        self.tam.run()
        #asyncio.run(self.tam.start_intent_queue_handler()) #self.tam.start_intent_queue_handler()
        #self.intents = []

    def create_prompt(self, text: str, chat_history: str) -> str:
        return f"""
            You are an expert at understanding user intentions based on chat history and user input. Use the provided chat history and user input to determine the user's intent and classify it as either TIME or OTHER. Consider the entire chat history, as the intent might change based on multiple rounds of conversation.

            Guidelines:
            1. Use the provided chat history and user input to determine the user's intent.
            2. Ensure the intent classification is accurate, concise, and directly addresses the user's query.
            3. If the intent is related to scheduling or time-based events (like reminders, repeated events, or upcoming significant events), classify the intent type as TIME.
            4. For non-time-related intents, classify the intent type as OTHER.
            5. Recognize implicit time references (e.g., "Please remind me every 10 minutes", "Please call me in 5 minutes", "I have a meeting with Gary next Monday", "There are 10 days left in the US presidential election").
            6. If the first round of conversation does not provide enough time-related information, classify it as OTHER and wait for further rounds.
            7. If the user input or chat history contains time-related words but the context is not about scheduling, reminders, or significant events, classify it as OTHER.
            
            Provide the JSON object in the following format:
            {{
                "type": "TIME | OTHER"
            }}

            Examples:

            Chat History:
            User: Can you tell me a joke?
            AI: Why don't scientists trust atoms? Because they make up everything!

            User Input:
            Tell me another joke.

            Determine the user's intent and create a JSON object:
            {{
                "type": "OTHER"
            }}

            Chat History:
            User: I need to schedule a meeting for next Monday.
            AI: Sure, what time would you like to schedule the meeting?

            User Input:
            Schedule it for 10 AM.

            Determine the user's intent and create a JSON object:
            {{
                "type": "TIME"
            }}

            Chat History:
            User: Please remind me every 10 minutes.
            AI: Got it. I'll remind you every 10 minutes.

            User Input:
            Thanks!

            Determine the user's intent and create a JSON object:
            {{
                "type": "TIME"
            }}

            Chat History:
            User: Please call me in 5 minutes.

            Determine the user's intent and create a JSON object:
            {{
                "type": "TIME"
            }}

            User Input:
            User: I have a meeting with Gary next Monday.

            Determine the user's intent and create a JSON object:
            {{
                "type": "TIME"
            }}

            User Input:
            User: There are 10 days left in the US presidential election.

            Determine the user's intent and create a JSON object:
            {{
                "type": "TIME"
            }}

            User Input:
            User: I am investigating how to travel to WuTaiShan. It's the first time to meet you and I want to do investigation carefully and print the details.

            Determine the user's intent and create a JSON object:
            {{
                "type": "OTHER"
            }}

            Chat History:
            {chat_history}

            User Input:
            {text}

            Determine the user's intent and create a JSON object:
        """
    
    def get_hist_chats(self, request: PromptRequest) -> str:
        hist = self.coreInst.get_latest_chats(app_id=request.app_id, user_name=request.user_name, user_id=request.user_id, num_rounds=10)
        return Util().convert_chats_to_text(hist)

    async def translate_to_intent(self, request: PromptRequest) -> Intent:
        # Combine the input text and chat history into a single context
        text = request.text
        hist = self.get_hist_chats(request)
        logger.debug(f'Orchestrator get Chat history: {hist}')
        if hist is not None and len(hist) > 0:
            hist = await Util().llm_summarize(hist)
        else:
            hist = ""
        prompt = self.create_prompt(text, hist)
        logger.debug(f'Orchestrator Prompt: {prompt}')       
        messages = [{"role": "system", "content": prompt}]
        intent_str = await Util().openai_chat_completion(messages)
        intent_str = intent_str.strip()
        if not intent_str:
            logger.error('Orchestrator response is empty')
            return None
        logger.debug(f'Orchestrator got intent: {intent_str}')
        # Process the intent string to create an Intent object
        intent = await self.process_intent(hist, text, intent_str, request)
        #self.intents.append(intent)
        
        return intent
    

    async def process_intent(self, chatHistory: str, text: str, intent_str: str, request: PromptRequest) -> Intent:
        # Here you would parse the intent to extract the relevant time-based information.
        # For simplicity, let's assume the intent contains a date and a reminder message.
        intent: Intent = None
        if '"type": "time"' in intent_str.lower():
            intent = Intent(
                type=IntentType.TIME, 
                text=text,
                intent_text=intent_str.strip(),
                timestamp=datetime.now().timestamp(),
                chatHistory=chatHistory
            )
            await self.tam.process_intent(intent,request)
        else:
            intent = Intent(
                type=IntentType.OTHER, 
                text=text, 
                intent_text=intent_str.strip(), 
                timestamp=datetime.now().timestamp(),
                chatHistory=chatHistory
                )
                
        logger.debug(f'Orchestrator got intent: {intent.type} {intent.text} {intent.intent_text} {intent.timestamp} {intent.chatHistory}')
        return intent