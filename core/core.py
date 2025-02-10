import asyncio
import copy
from datetime import datetime, timedelta
import importlib
import json
import os
import signal
import socket
import subprocess
import sys
from pathlib import Path
import threading
import uuid
import chromadb
import chromadb.config
import aiohttp
from fastapi import BackgroundTasks, FastAPI
from fastapi.exceptions import RequestValidationError
from typing import Optional, Dict, List, Tuple, Union
from fastapi.responses import JSONResponse
from fastapi import FastAPI, Request, Response
from loguru import logger
import requests
import yaml
import uvicorn
import httpx
from contextlib import asynccontextmanager
import re
from jinja2 import Template

# Ensure the project root is in the PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.orchestrator import Orchestrator
from base.PluginManager import PluginManager
from base.util import Util
from base.base import LLM, EmbeddingRequest, Intent, IntentType, RegisterChannelRequest, PromptRequest, AsyncResponse, User
from base.BaseChannel import BaseChannel
from base.BasePlugin import BasePlugin
from base.base import ChannelType, ContentType, User, CoreMetadata, Server
from llm.llmService import LLMServiceManager
from memory.chat.message import ChatMessage
from memory.chat.chat import ChatHistory
from memory.base import MemoryBase, VectorStoreBase, EmbeddingBase, LLMBase
from memory.prompts import RESPONSE_TEMPLATE
from coreInterface import CoreInterface




class Core(CoreInterface):   
    _instance = None
    _lock = threading.Lock() 

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(Core, cls).__new__(cls, *args, **kwargs)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.initialized = True
            self.latestPromptRequest: PromptRequest = None
            Util().setup_logging("core", Util().get_core_metadata().mode)
            root = Util().root_path()
            db_folder = os.path.join(root, 'database')
            if not os.path.exists(db_folder):
                os.makedirs(db_folder)

            self.app = FastAPI()
            self.plugin_manager: PluginManager = None
            self.channels: List[BaseChannel] = []
            self.server = None
            self.embedder: EmbeddingBase = None
            self.mem_instance: MemoryBase = None
            self.vector_store: VectorStoreBase = None
            self.memory_llm: LLMBase = None
            self.llmManager: LLMServiceManager = LLMServiceManager()
            
            #self.chroma_server_process = self.start_chroma_server()
            self.chromra_memory_client = None
            logger.debug("Before initialize chat history")
            self.chatDB: ChatHistory = ChatHistory()
            logger.debug("After initialize chat history")
            self.run_ids = {}
            self.session_ids = {}
            
            self.request_queue = asyncio.Queue(100)
            self.response_queue = asyncio.Queue(100)
            self.request_queue_task = None
            self.response_queue_task = None
            self.active_plugin = None
            logger.debug("Before initialize orchestrator")
            self.orchestratorInst = Orchestrator(self)
            logger.debug("After initialize orchestrator")


    def create_gpt4people_account(
        self,
        email: str,
        password: str
    ) ->int:
        url = "https://mail.gpt4people.ai/api/v1/user"  # Replace with your API URL
        headers = {
            "Content-Type": "application/json"
        }
        payload = {
            "email": email,
            "raw_password": password,
            "comment": "my comment",
            "quota_bytes": 1000000000,
            "global_admin": True,
            "enabled": True,
            "change_pw_next_login": False,
            "enable_imap": True,
            "enable_pop": True,
            "allow_spoofing": True,
            "forward_enabled": False,
            "forward_destination": [],
            "forward_keep": False,
            "reply_enabled": False,
            "reply_subject": "",
            "reply_body": "",
            "reply_startdate": "",
            "reply_enddate": "",
            "displayed_name": "",
            "spam_enabled": True,
            "spam_mark_as_read": True,
            "spam_threshold": 80
        }

        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code == 200:
            logger.debug(f"User created successfully: {response.json()}")
        elif response.status_code == 400:
            logger.debug(f"Input validation exception: {response.json()}")
        elif response.status_code == 401:
            logger.debug(f"Authorization header missing: {response.json()}")
        elif response.status_code == 403:
            logger.debug(f"Authorization header invalid: {response.json()}")
        elif response.status_code == 409:
            logger.debug(f"Duplicate user: {response.json()}")
        else:
            logger.debug(f"Unknown error: {response.json()}")

        return response.status_code



    def find_plugin_prompt(self, user_input: str) -> str:
        plugin_descriptions_text = "\n\n".join(
            [f"{i+1}. {desc}" for i, desc in enumerate(self.plugin_manager.plugin_descriptions.keys())]
        )
        
        return f"""
        You are an expert at understanding user intentions based on input text and available plugin descriptions. Analyze the latest user input and determine which plugin description best matches the user's needs. If the user input does not require any plugin, indicate that as well.
        Provide the index of the best matching plugin description. If no plugin is needed, return "None".
        Focus primarily on the latest user input, even if there is chat history.

        Examples:

        User Input:
        "What's the weather like today?"

        Plugin Descriptions:
        1. This plugin retrieves the latest news headlines and provides summaries of news articles based on specified categories, countries, sources, and keywords.
        2. This plugin generates motivational and uplifting quotes based on chat histories using a language model (LLM). It is designed to detect user emotions, such as depression or sadness, and provide comforting and encouraging quotes to help improve their mood. The plugin can be used to offer emotional support and positivity to users during their conversations.
        3. This plugin retrieves the current weather and weather forecast for specified locations. It provides detailed information including temperature, humidity, weather conditions, wind direction, wind power, and air quality index (AQI). This plugin can be used to provide users with real-time weather updates and forecasts for any city.

        Output:
        3

        User Input:
        "Can you tell me a joke?"

        Plugin Descriptions:
        1. This plugin retrieves the latest news headlines and provides summaries of news articles based on specified categories, countries, sources, and keywords.
        2. This plugin generates motivational and uplifting quotes based on chat histories using a language model (LLM). It is designed to detect user emotions, such as depression or sadness, and provide comforting and encouraging quotes to help improve their mood. The plugin can be used to offer emotional support and positivity to users during their conversations.
        3. This plugin retrieves the current weather and weather forecast for specified locations. It provides detailed information including temperature, humidity, weather conditions, wind direction, wind power, and air quality index (AQI). This plugin can be used to provide users with real-time weather updates and forecasts for any city.

        Output:
        None

        User Input:
        "I need some motivation."

        Plugin Descriptions:
        1. This plugin retrieves the latest news headlines and provides summaries of news articles based on specified categories, countries, sources, and keywords.
        2. This plugin generates motivational and uplifting quotes based on chat histories using a language model (LLM). It is designed to detect user emotions, such as depression or sadness, and provide comforting and encouraging quotes to help improve their mood. The plugin can be used to offer emotional support and positivity to users during their conversations.
        3. This plugin retrieves the current weather and weather forecast for specified locations. It provides detailed information including temperature, humidity, weather conditions, wind direction, wind power, and air quality index (AQI). This plugin can be used to provide users with real-time weather updates and forecasts for any city.

        Output:
        2

        User Input:
        "Give me the top news for today."

        Plugin Descriptions:
        1. This plugin retrieves the latest news headlines and provides summaries of news articles based on specified categories, countries, sources, and keywords.
        2. This plugin generates motivational and uplifting quotes based on chat histories using a language model (LLM). It is designed to detect user emotions, such as depression or sadness, and provide comforting and encouraging quotes to help improve their mood. The plugin can be used to offer emotional support and positivity to users during their conversations.
        3. This plugin retrieves the current weather and weather forecast for specified locations. It provides detailed information including temperature, humidity, weather conditions, wind direction, wind power, and air quality index (AQI). This plugin can be used to provide users with real-time weather updates and forecasts for any city.

        Output:
        1

        User Input:
        "我想看新闻！"

        Plugin Descriptions:
        1. This plugin retrieves the latest news headlines and provides summaries of news articles based on specified categories, countries, sources, and keywords.
        2. This plugin generates motivational and uplifting quotes based on chat histories using a language model (LLM). It is designed to detect user emotions, such as depression or sadness, and provide comforting and encouraging quotes to help improve their mood. The plugin can be used to offer emotional support and positivity to users during their conversations.
        3. This plugin retrieves the current weather and weather forecast for specified locations. It provides detailed information including temperature, humidity, weather conditions, wind direction, wind power, and air quality index (AQI). This plugin can be used to provide users with real-time weather updates and forecasts for any city.

        Output:
        1

        Please select the most proper plugin for the following user input and plugin descriptions:
        User Input:
        "{user_input}"

        Plugin Descriptions:
        {plugin_descriptions_text}

        Output:
        """
    async def is_proper_plugin(self, plugin: BasePlugin, text: str):
        """
        Implement logic to check if the active plugin is appropriate for the given text.
        This could involve checking for certain keywords or contextual clues.
        """
        return await plugin.check_best_plugin(text)
    
    async def find_plugin_for_text(self, text: str) -> Optional[BasePlugin]:
        if self.plugin_manager.num_plugins() == 0:
            logger.debug("No plugins loaded.")
            return None
        # Prioritize the active plugin if it is set
        if self.active_plugin:
            result, text = await self.is_proper_plugin(self.active_plugin, text)
            if result:
                logger.debug(f"Found plugin: {self.active_plugin.get_description()}")
                return self.active_plugin

        prompt = self.find_plugin_prompt(text)
        logger.debug(f"Find plugin Prompt: {prompt}")

        messages = [{"role": "system", "content": prompt}]
        best_description = await self.openai_chat_completion(messages=messages) # Replace with your actual method to get LLM response
        if best_description is None:
            return None
        if best_description.lower().strip() == "none" or best_description.strip() == "":
            return None

        logger.debug(f"Best description: {best_description}")
        # Convert plugin descriptions to a list
        original_descriptions = list(self.plugin_manager.plugin_descriptions.keys())

        # Extract the index of the best description from the LLM's output
        match = re.search(r"(\d+)", best_description)
        if match:
            best_index = int(match.group(1)) - 1  # Assuming LLM output is 1-indexed
        else:
            logger.error(f"Failed to extract index from best description: {best_description}")
            return None

        if 0 <= best_index < len(original_descriptions):
            best_match_description = original_descriptions[best_index]
            active_plugin = self.plugin_manager.plugin_descriptions.get(best_match_description, None)
            logger.debug(f"Update active plugin: {active_plugin.get_description()}")
            return active_plugin
        else:
            logger.error(f"Best index {best_index} is out of range for description keys")
            return None


    def initialize_embedder(self):
        from memory.embedding import EmbeddingBase, BaseEmbedderConfig, LlamaCppEmbedding
        # Initialize the embedder, now it is using one existing llama_cpp server with local LLM model
        llm: LLM = Util().embedding_llm()
        host = llm.host
        port = llm.port
        embedding_url = "http://" + host + ":" + str(port)
        embedding_config = BaseEmbedderConfig(embedding_base_url=embedding_url)  # Set the correct URL and dimensions
        self.embedder = LlamaCppEmbedding(embedding_config)
        
        
    def initialize_memory(self):
        from memory.mem import Memory  # Import here to avoid circular import
        self.mem_instance = Memory(embedding_model=self.embedder, vector_store=self.vector_store, llm=self.memory_llm)
        
          
    def initialize_memory_llm(self):
        from memory.llm import LlamaCppLLM
        from memory.configs import BaseLlmConfig
        memory_llm = Util().memory_llm()
        host = memory_llm.host
        port = memory_llm.port
        llama_cpp_base_url = "http://" + host + ":" + str(port)
        llm_config = BaseLlmConfig(llama_cpp_base_url=llama_cpp_base_url)
        self.memory_llm = LlamaCppLLM(config=llm_config)


    def load_plugins(self):
        self.plugin_manager.load_plugins()

    def initialize_plugins(self):
        self.plugin_manager.initialize_plugins()


    def start_hot_reload(self):
        self.plugin_manager.start_hot_reload()

    # try to reduce the misunderstanding. All the input tests in EmbeddingBase should be
    # in a list[str]. If you just want to embedding one string, ok, put into one list first.
    async def get_embedding(self, request: EmbeddingRequest)-> List[List[float]]:
        # Initialize the embedder, now it is using one existing llama_cpp server with local LLM model
        try:
            llm: LLM = Util().embedding_llm()
            host = llm.host
            port = llm.port
            embedding_url = "http://" + host + ":" + str(port) + "/v1/embeddings"
            text = text.replace("\n", " ")
            request_json = request.model_dump_json()
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    embedding_url,
                    headers={"accept": "application/json", "Content-Type": "application/json"},
                    data=request_json,
                ) as response:
                    response_json = await response.json()
                    # Extract embeddings from the response
                    embeddings = [item["embedding"] for item in response_json["data"]]
                    return embeddings
        except asyncio.CancelledError:
            logger.debug("Embedding request was cancelled.")
        except Exception as e:
            logger.error(f"Unexpected error in embedding: {e}")
            return {}


    def initialize_vector_store(self, collection_name: str, client: Optional[chromadb.Client] = None,
                                host: Optional[str] = None, port: Optional[int] = None,
                                path: Optional[str] = None,):
        from memory import chroma
        if client is None:
            self.chromra_memory_client = self.start_chroma_client()
        else:
            self.chromra_memory_client = client
        self.vector_store = chroma.ChromaDB(collection_name=collection_name, client=self.chromra_memory_client, host=host, port=port, path=path)


    def initialize(self):
        logger.debug("core initializing...")
        self.initialize_vector_store(collection_name="memory")
        self.initialize_embedder()
        self.initialize_memory_llm()
        self.initialize_memory()
        
        self.request_queue_task = asyncio.create_task(self.process_request_queue())
        self.response_queue_task = asyncio.create_task(self.process_response_queue())
        
        self.plugin_manager: PluginManager = PluginManager(self)

        @self.app.exception_handler(RequestValidationError)
        async def validation_exception_handler(request: Request, exc: RequestValidationError):
            logger.error(f"Validation error: {exc} for request: {await request.body()}")
            return JSONResponse(
                status_code=422,
                content={"detail": exc.errors(), "body": exc.body},
            ) 

        @self.app.post("/register_channel")
        async def register_channel(request: RegisterChannelRequest):
            logger.debug(f"Received channel registration request: {request.name}")
            try:
                self.register_channel(request.name, request.host, request.port, request.endpoints)
                main_llm: LLM = Util().main_llm()
                language = main_llm.languages[0]
                host = main_llm.host
                port = main_llm.port

                return {"result": "Succeed", "host": host, "port": port, "language": language}
            except Exception as e:
                logger.exception(e)
                return {"result": str(e)}

        
        @self.app.post("/deregister_channel")
        async def deregister_channel(request: RegisterChannelRequest):
            logger.debug(f"Received channel deregistration request: {request.name}")
            try:
                self.deregister_channel(request.name, request.host, request.port, request.endpoints)
                return {"result": "Channel deregistration successful " + request.name}
            except Exception as e:
                logger.exception(e)
                return {"result": str(e)}
            
        @self.app.post("/process")
        async def process_request(request: PromptRequest):
            try:
                if request is not None:
                    self.latestPromptRequest = copy.deepcopy(request)
                    logger.debug(f'latestPromptRequest set to: {self.latestPromptRequest}')
                    self.save_latest_prompt_request_to_file('latestPromptRequest.json') 

                user_name: str = request.user_name
                user_id: str = request.user_id
                channel_type: ChannelType = request.channelType
                content_type: ContentType = request.contentType
                logger.debug(f"Received request from channel: {user_name}, {user_id}, {channel_type}, {content_type}")
                user: User = None
                has_permission, user = self.check_permission(user_name, user_id, channel_type, content_type)
                if not has_permission or user is None:
                    return Response(content="Permission denied", status_code=401)
                
                if len(user.name) > 0:
                    request.user_name = user.name

                await self.request_queue.put(request)
                
                return Response(content="Request received", status_code=200)
            except Exception as e:
                logger.exception(e)
                return Response(content="Server Internal Error", status_code=500)
                     
        # add more endpoints here    
        logger.debug("core initialized and all the endpoints are registered!")


        @self.app.post("/local_chat")
        async def process_request(request: PromptRequest):
            try:
                user_name: str = request.user_name
                user_id: str = request.user_id
                channel_type: ChannelType = request.channelType
                content_type: ContentType = request.contentType
                logger.debug(f"Received request from channel: {user_name}, {user_id}, {channel_type}, {content_type}")
                user: User = None
                has_permission, user = self.check_permission(user_name, user_id, channel_type, content_type)
                if not has_permission or user is None:
                    return Response(content="Permission denied", status_code=401)
                
                if len(user.name) > 0:
                    request.user_name = user.name
                
                resp_text = await self.process_text_message(request)
                if resp_text is None:
                    return Response(content="Response is None", status_code=200)
                
                return Response(content=resp_text, status_code=200)
            except Exception as e:
                logger.exception(e)
                return Response(content="Server Internal Error", status_code=500)
                     
        # add more endpoints here    
        logger.debug("core initialized and all the endpoints are registered!")


    def save_latest_prompt_request_to_file(self, filename: str):
        try:
            with open(filename, 'w') as file:
                json.dump(self.latestPromptRequest.__dict__, file, default=str)
            logger.debug(f"latestPromptRequest saved to {filename}")
        except Exception as e:
            logger.error(f"Error saving latestPromptRequest: {e}")

    def read_latest_prompt_request_from_file(self, filename: str) -> PromptRequest:
        try:
            with open(filename, 'r') as file:
                data = json.load(file)
                logger.debug(f"latestPromptRequest read from {data}")
                channel_type = data['channelType'].split('.')[-1]
                content_type = data['contentType'].split('.')[-1]
                data['channelType'] = ChannelType[channel_type]
                data['contentType'] = ContentType[content_type]
                logger.debug(f"latestPromptRequest read from {data}")
                request = PromptRequest(**data)
                logger.debug(f"latestPromptRequest : {request}")
            logger.debug(f"latestPromptRequest read from {filename}")
            return request
        except Exception as e:
            logger.error(f"Error reading latestPromptRequest: {e}")
            return None
        
    
    async def process_request_queue(self):
        while True:
            request: PromptRequest = await self.request_queue.get()
            try:
                if request is None:
                    return
                intent: Intent = await self.orchestratorInst.translate_to_intent(request)
                if intent is not None:
                    logger.debug(f"Got intent: {intent.type} {intent.intent_text}")
                    if intent.type == IntentType.OTHER:
                        plugin: BasePlugin = await self.find_plugin_for_text(intent.text)
                        if plugin is not None:
                            plugin.user_input = intent.text
                            if plugin.promptRequest is not None:
                                plugin.promptRequest.app_id = request.app_id
                                plugin.promptRequest.request_id = request.request_id
                                plugin.promptRequest.request_metadata = request.request_metadata
                                plugin.promptRequest.channel_name = request.channel_name
                                plugin.promptRequest.user_name = request.user_name
                                plugin.promptRequest.user_id = request.user_id
                                plugin.promptRequest.contentType = request.contentType
                                plugin.promptRequest.channelType = request.channelType
                                plugin.promptRequest.text = request.text
                            else:
                                plugin.promptRequest = PromptRequest(**request.__dict__)
                            logger.debug(f"Found plugin's description: {plugin.get_description()}")
                            if plugin == self.active_plugin:
                                continue
                            await plugin.run()
                            self.active_plugin = plugin
                            continue

                #if intent is not None and (intent.type == IntentType.RESPOND or intent.type == IntentType.QUERY):
                if request.contentType == ContentType.TEXT:
                    resp_text = await self.process_text_message(request)
                    if resp_text is None:
                        logger.debug(f"response_text is None")
                        continue
                    resp_data = {"text": resp_text}
                    async_resp: AsyncResponse = AsyncResponse(request_id=request.request_id, request_metadata=request.request_metadata, host=request.host, port=request.port, from_channel=request.channel_name, response_data=resp_data)                    
                    await self.response_queue.put(async_resp)                 
                else:
                    # Handle other content types
                    pass

            except Exception as e:
                logger.exception(f"Error processing request: {e}")
            finally:
                self.request_queue.task_done()


    async def send_response_to_latest_channel(self, response: str):
        resp_data = {"text": response}
        request: PromptRequest = self.latestPromptRequest
        if request is None:
            request = self.read_latest_prompt_request_from_file('latestPromptRequest.json')
            if request is None:
                return
        async_resp: AsyncResponse = AsyncResponse(request_id=request.request_id, request_metadata=request.request_metadata, host=request.host, port=request.port, from_channel=request.channel_name, response_data=resp_data)                    
        await self.response_queue.put(async_resp) 


    async def send_response_to_request_channel(self, response: str, request: PromptRequest):
        resp_data = {"text": response}
        if request is None:
            return
        async_resp: AsyncResponse = AsyncResponse(request_id=request.request_id, request_metadata=request.request_metadata, host=request.host, port=request.port, from_channel=request.channel_name, response_data=resp_data)                    
        await self.response_queue.put(async_resp)                   
                
                
    async def process_response_queue(self):
        async with httpx.AsyncClient() as client:
            while True:
                response: AsyncResponse = await self.response_queue.get()
                try:
                    host = response.host if response.host != '0.0.0.0' else '127.0.0.1'
                    port = response.port
                    path = '/get_response'
                    resp_url = f"http://{host}:{port}{path}"
                    logger.debug(f"Attempting to send response to {resp_url}")
                    
                    response_dict = response.model_dump()
                    
                    try:
                        resp = await client.post(url=resp_url, json=response_dict, timeout=10.0)
                        if resp.status_code == 200:
                            logger.debug(f"Response sent to channel: {response.from_channel}")
                        else:
                            logger.error(f"Failed to send response to channel: {response.from_channel}. Status: {resp.status_code}")
                    except httpx.ConnectError as e:
                        logger.error(f"Connection error when sending to {resp_url}: {str(e)}")
                    except httpx.TimeoutException:
                        logger.error(f"Timeout when sending to {resp_url}")
                    except Exception as e:
                        logger.error(f"Unexpected error when sending to {resp_url}: {str(e)}")
                except Exception as e:
                    logger.exception(f"Error sending response back to channel {response.from_channel}: {e}")
                finally:
                    self.response_queue.task_done()

    
    def get_run_id(self, agent_id, user_name=None, user_id=None, validity_period=timedelta(hours=24)):
        if user_id in self.run_ids:
            run_id, timestamp = self.run_ids[user_id]
            if datetime.now() - timestamp < validity_period:
                return run_id
        
        current_time = datetime.now()
        runs: List[dict] =self.chatDB.get_runs(agent_id=agent_id, user_name=user_name, user_id=user_id, num_rounds=1, fetch_all=False)
        for run in runs:
            run_id = run['run_id']
            timestamp = run['created_at']
            if current_time - timestamp < validity_period:
                return run_id
        
        new_run_id = uuid.uuid4().hex
        self.run_ids[user_id] = (new_run_id, current_time)
        self.chatDB.add_run(agent_id=agent_id, user_name=user_name, user_id=user_id, run_id=new_run_id, created_at=current_time)
        return new_run_id
    
    def get_latest_chat_info(self, app_id=None, user_name=None, user_id=None) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        chat_sessions =  self.chatDB.get_sessions(app_id=app_id, user_name=user_name, user_id=user_id, num_rounds=1)
        if len(chat_sessions) == 0:
            return None, None, None
        logger.debug(f'chat_sessions: {chat_sessions}')
        if len(chat_sessions) > 0:
            chat_session: dict = chat_sessions[0]
            app_id = chat_session['app_id']
            user_name = chat_session['user_name']
            user_id = chat_session['user_id']
            logger.debug(f'app_id: {app_id}, user_id: {user_id}')
            return app_id, user_name, user_id
        
    def get_latest_chats(self, app_id=None, user_name=None, user_id=None, num_rounds=10, timestamp=None) -> List[ChatMessage]: 
        histories: List[ChatMessage] = self.chatDB.get(app_id=app_id, user_name=user_name, user_id=user_id, num_rounds=num_rounds, fetch_all=False, display_format=False)
        if timestamp is None:
            return histories
        else:
            histories = [history for history in histories if timestamp - history.created_at < timedelta(minutes=30)]           
        return histories
    
    def get_latest_chats_by_role(self, sender_name=None, responder_name=None, num_rounds = 10, timestamp=None):
        histories = self.chatDB.get_hist_by_role(sender_name, responder_name, num_rounds)
        if timestamp is None:
            return histories
        else:
            histories = [history for history in histories if timestamp - history.created_at < timedelta(minutes=30)]           
        return histories
    
    def get_session_id(self, app_id, user_name=None, user_id=None, validity_period=timedelta(hours=24)):
        if user_id in self.session_ids:
            session_id, timestamp = self.session_ids[user_id]
            if datetime.now() - timestamp < validity_period:
                return session_id
        
        current_time = datetime.now()
        sessions: List[dict] =self.chatDB.get_sessions(app_id=app_id, user_name=user_name, user_id=user_id, num_rounds=1, fetch_all=False)
        for session in sessions:
            session_id = session['session_id']
            timestamp = session['created_at']
            if current_time - timestamp < validity_period:
                return session_id
        
        new_session_id = uuid.uuid4().hex
        self.session_ids[user_id] = (new_session_id, current_time)
        logger.debug(f'user_name: {user_name}, user_id: {user_id}, session_id: {new_session_id}')
        self.chatDB.add_session(app_id=app_id, user_name=user_name, user_id=user_id, session_id=new_session_id, created_at=current_time)
        return new_session_id
    
    
    async def process_text_message(self, request: PromptRequest):
        try:
            user_name: str = request.user_name
            user_id: str = request.user_id
            action: str = request.action
            channel_type: ChannelType = request.channelType
            content_type: ContentType = request.contentType
            content = request.text
            app_id: str = request.app_id
            human_message = ''
            email_addr = ''
            subject = ''
            body = ''
            
            if channel_type == ChannelType.Email:
                content_json = json.loads(content)
                msg_id = content_json["MessageID"]
                email_addr = content_json["From"]
                subject = content_json["Subject"]
                body = content_json["Body"]
                human_message = body
                logger.debug(f"email_addr: {email_addr}, subject: {subject}, body: {body}")
            else:
                human_message = content
            session_id = self.get_session_id(app_id=app_id, user_name=user_name, user_id=user_id)
            run_id = self.get_run_id(agent_id=app_id, user_name=user_name, user_id=user_id)
            logger.debug(f"session_id: {session_id}, run_id: {run_id}")
            histories: List[ChatMessage] = self.chatDB.get(app_id=app_id, user_name=user_name, user_id=user_id, num_rounds=10, fetch_all=False, display_format=False)
            logger.debug(f"histories: {histories}")
            messages = []

            if histories is not None and len(histories) > 0: 
                for item in histories:
                    messages.append({'role': 'user', 'content': item.human_message.content})
                    messages.append({'role': 'assistant', 'content': item.ai_message.content})
            messages.append({'role': 'user', 'content': human_message})
            logger.debug(f"Input message: {messages}")
            answer = ''

            answer = await self.answer_from_memory(query=human_message, messages=messages, app_id=app_id, user_name=user_name, user_id=user_id, agent_id=app_id, session_id=session_id, run_id=run_id)
            logger.debug(f"Output message: {answer}")
            return answer
        except Exception as e:
            logger.exception(e)


    def prompt_template(self, section: str, prompt_name: str) -> List[Dict] | None:
        try:
            main_llm = Util().main_llm()
            main_language = main_llm.languages[0]
            current_path = os.path.dirname(os.path.abspath(__file__))
            prompt_file_name = "prompt_" + main_language + ".yml"
            prompt_file_path = os.path.join(current_path, 'prompts',prompt_file_name)
            with open(prompt_file_path, 'r', encoding='utf-8') as file:
                data = yaml.safe_load(file)

            for item in data['Prompts'][section]:
                if item['name'] == prompt_name:
                    template = item['prompt']
                    return template
                
        except Exception as e:
            logger.exception(e)
            return None


    def check_permission(self, user_name: str, user_id: str, channel_type: ChannelType, content_type: ContentType) -> bool:
        user: User = None
        users = Util().get_users()
        for user in users:
            logger.debug(f"User:  + {user}")
            if channel_type == ChannelType.Email:
                logger.debug(f"Email:  + {user.email}, email_id: {user_id}")
                if user_id in user.email:
                    return (ChannelType.Email in user.permissions or len(user.permissions) == 0), user
            if channel_type == ChannelType.IM:
                if user_id in user.im:
                    return (ChannelType.IM in user.permissions or len(user.permissions) == 0), user
                elif user_id  == 'gpt4people:local':
                    return True, user
            if channel_type == ChannelType.Phone:           
                if user_id in user.phone:
                    return (ChannelType.Phone in user.permissions or len(user.permissions) == 0), user
        return False, None


    def start_email_channel(self):
        subprocess.Popen(["python", os.path.join(Util().root_path(), 'core', 'emailChannel', "channel.py")])
 
   
    async def run(self):
        """Run the core using uvicorn"""
        try:
            logger.debug("core is running!")
            core_metadata: CoreMetadata = Util().get_core_metadata()
            logger.debug(f"Running core on {core_metadata.host}:{core_metadata.port}")
            config = uvicorn.Config(self.app, host=core_metadata.host, port=core_metadata.port, log_level="info")
            self.server = Server(config=config)
            self.initialize()
            self.start_email_channel()

            # Load plugins
            self.load_plugins()
            self.plugin_manager.run()            
            self.start_hot_reload()

            # Schedule llmManager.run() to run concurrently
            llm_task = asyncio.create_task(self.llmManager.run())

            # Start the server
            server_task = asyncio.create_task(self.server.serve())
            await asyncio.gather(llm_task, server_task)
        except asyncio.CancelledError:
            logger.info("core uvicorn server was cancelled.")
            sys.exit(0)

            
        except Exception as e:
            logger.exception(e)
            sys.exit(0)


    def stop(self):
        # do some deinitialization here
        logger.debug("core is stopping!")
        self.llmManager.stop_all_apps()
        logger.debug("LLM apps are stopped!")

        self.plugin_manager.deinitialize_plugins()
        logger.debug("Plugins are deinitialized!")


    def register_channel(self, name: str, host: str, port: str, endpoints: list):
        channel = {
            "name": name,
            "host": host,
            "port": port,
            "endpoints": endpoints
        }
        for  channel in self.channels:
            if channel["host"] == host and channel["port"] == port:
                return
        self.channels.append(channel)


    def deregister_channel(self, name: str, host: str, port: str, endpoints: list):
        for channel in self.channels:
            if channel["name"] == name and channel["host"] == host and channel["port"] == port and channel["endpoints"] == endpoints:
                self.channels.remove(channel)
                logger.debug(f"Channel {name} is deregistered from {host}:{port}")
                return
            

    async def shutdown_channel(self, name: str, host: str, port: str):
        for channel in self.channels:
            if channel["name"] == name and channel["host"] == host and channel["port"] == port:
                async with httpx.AsyncClient() as client:
                    await client.get(f"http://{host}:{port}/shutdown")

                self.channels.remove(channel)
                logger.debug(f"Channel {name} is deregistered from {host}:{port}")
                return
            

    async def shutdown_all_channels(self):
        for channel in self.channels.copy():
            await self.shutdown_channel(channel["name"], channel["host"], channel["port"])
        

    def start_chroma_client(self):  
        metadata = Util().get_core_metadata()
        db = metadata.vectorDB.Chroma
        '''
        settings = chromadb.config.Settings(chroma_server_host=None, 
                        chroma_server_http_port=None,
                        chroma_api_impl=db.api,
                        persist_directory=db.persist_path,
                        is_persistent=db.is_persistent,
                        anonymized_telemetry=db.anonymized_telemetry)
        '''

        settings = chromadb.config.Settings(anonymized_telemetry=False)
        path = db.persist_path
        settings.persist_directory = path
        settings.is_persistent = True
        client = chromadb.Client(settings=settings)
        # Here you can initialize collections or add more configurations as needed
        logger.debug(f"ChromaDB client created")
        return client
    
    
    def stop_chroma_client(self):
        #self.chromra_memory_client.()
        logger.debug("ChromaDB client disconnected")
    
    '''
    def start_chroma_server(self):
        db = self.metadata.vectorDB['Chroma']
        args = [
            "chroma-server",
            "--host", db.host,
            "--port", str(db.port),
            "--api", db.api,
            "--persist", db.persist_path,
            "--is-persistent", str(db.is_persistent).lower(),
            "--anonymized-telemetry", str(db.anonymized_telemetry).lower()
        ]
        logger.debug(f"args: {args}")
        try:
            self.chroma_server_process = subprocess.Popen(args)
        except Exception as e:
            logger.exception(f"Failed to start Chroma server: {e}")
            raise
        logger.debug(f"ChromaDB server started on {db.host}:{db.port}")
        return self.chroma_server_process


    def shutdown_chroma_server(self):
        if self.chroma_server_process:
            self.chroma_server_process.terminate()
            self.chroma_server_process.wait()
            logger.debug("ChromaDB server has been terminated.")
    '''
   
    
    async def openai_chat_completion(self, messages: list[dict], 
                                     grammar: str=None,
                                     tools: Optional[List[Dict]] = None,
                                     tool_choice: str = "auto", 
                                     llm_name: str = None) -> str | None:    
        try:      
            if not llm_name:
                llm_name = Util().main_llm().name              
            llm: LLM = Util().get_llm(llm_name)
            model_host = llm.host
            model_port = llm.port
            model = llm.path
            data = {}
            if grammar != None and len(grammar) > 0:
                data = {
                    "model": model,
                    "messages": messages,
                    "extra_body": {
                        "grammar": grammar
                    } 
                }
            else:
                data = {
                    "model": model,
                    "messages": messages,
                }
            if tools:
                data["tools"] = tools
                data["tool_choice"] = tool_choice
            headers = {
                'Content-Type': 'application/json',
                'Authorization': 'Anything'
            }
            data_json = json.dumps(data, ensure_ascii=False).encode('utf-8')
            chat_completion_api_url = 'http://' + model_host + ':' + str(model_port) + '/v1/chat/completions'
            async with aiohttp.ClientSession() as session:
                async with session.post(chat_completion_api_url, headers=headers, data=data_json) as resp:
                    resp_json = await resp.text(encoding='utf-8')
                    # Ensure resp_json is a dictionary
                    while isinstance(resp_json, dict) == False:
                        resp_json = json.loads(resp_json)
                    logger.debug(f"Resp: {resp_json}")
                    if isinstance(resp_json, dict) and 'choices' in resp_json:
                        if isinstance(resp_json['choices'], list) and len(resp_json['choices']) > 0:
                            if 'message' in resp_json['choices'][0] and 'content' in resp_json['choices'][0]['message']:
                                message_content = resp_json['choices'][0]['message']['content'].strip()
                                logger.debug(f"Message Content from LLM: {message_content}")
                                # Filter out the <think> tag and its content
                                filtered_message_content = re.sub(r'<think>.*?</think>', '', message_content, flags=re.DOTALL) 
                                logger.debug(f"Filtered Message Content from LLM: {filtered_message_content}")                              
                                return filtered_message_content.strip()
                    logger.error("Invalid response structure")
                    return None
        except Exception as e:
            logger.exception(e)
            return None
        
    def extract_json_str(self, response) -> str:
        # Allow {} to be matched in response
        # This regular expression pattern matches all JSON-like strings in the response.
        # The pattern is explained in the following steps:
        # 1. The pattern starts with a left curly brace "{" and matches any character (except newline) zero or more times.
        #    The "?" after "*" makes the match non-greedy, meaning it will match as few characters as possible.
        # 2. The pattern ends with a right curly brace "}" and matches any character (except newline) zero or more times.
        #    The "?" after "*" makes the match non-greedy, meaning it will match as few characters as possible.
        # 3. The pattern uses a negative lookbehind "(?<!\\)" to ensure that the left curly brace "{" is not preceded by a backslash.
        #    This ensures that the pattern does not match escaped curly braces "{\\}".
        # 4. The pattern uses a negative lookbehind "(?<!\\)" to ensure that the right curly brace "}" is not preceded by a backslash.
        #    This ensures that the pattern does not match escaped curly braces "\}{".
        # 5. The pattern is compiled with the flag "re.DOTALL" to allow the dot "." to match any character, including newline.
        #    This ensures that the pattern can match multiline JSON strings.
        json_pattern = re.compile(r'''
            (?<!\\)         # Negative lookbehind for a backslash (to avoid escaped braces)
            (\{             # Match the opening brace and start capturing
                [^{}]*      # Match any character except braces
                (?:         # Non-capturing group for nested braces
                    (?:     # Non-capturing group for repeated patterns
                        [^{}]   # Match any character except braces
                        |       # OR
                        \{[^{}]*\}  # Match nested braces
                    )*          # Zero or more times
                )*          # Zero or more times
            \})             # Match the closing brace and end capturing
        ''', re.VERBOSE | re.DOTALL)
        matches = json_pattern.findall(response)

        if matches:
            return matches[0]
        return response


    def extract_tuple_str(self, response):
        # Define the refined pattern to match one or more capability items
        pattern = re.compile(
            r"\(\{\{'capabilities':.*?, 'score':.*?, 'can_solve':.*?\}\}(?:, \{\{'capabilities':.*?, 'score':.*?, 'can_solve':.*?\}\})*\)"
        )
        matches = pattern.findall(response)
        if matches:
            return matches[0]
        return response
       
    async def openai_completion(self, prompt: str, llm_name: str = "") -> str | None:
        try:
            llm = Util().get_llm(llm_name)
            model_host = llm.host
            model_port = llm.port
            model = llm.path

            data = {
                "model": model,
                "prompt": prompt,
                "n": 1,
            }
            headers = {
                'Content-Type': 'application/json',
                'Authorization': 'Anything'
            }
            data_json = json.dumps(data, ensure_ascii=False).encode('utf-8')

            completion_api_url = 'http://' + model_host + ':' + str(model_port) + '/v1/completions'
            logger.debug(f"completion_api_url: {completion_api_url}")
            async with aiohttp.ClientSession() as session:
                async with session.post(completion_api_url, headers=headers, data=data_json) as resp:
                    ret = (await resp.json())
                    logger.debug(f"Resp: {ret}")
                    resp = ret['content']
                    logger.debug(f"Resp: {resp}")
                    ret = self.extract_json_str(resp)
                    return ret
                    #return (ret)['choices'][0]['text']
        except Exception as e:
            logger.exception(e) 
            return None


    async def answer_from_memory(self, 
                                 query: str,
                                 messages: List = [], 
                                 app_id: Optional[str] = None,
                                 user_name: Optional[str] = None,
                                 user_id: Optional[str] = None, 
                                 agent_id: Optional[str] = None, 
                                 session_id: Optional[str] = None,
                                 run_id: Optional[str] = None, 
                                 metadata: Optional[dict] = None, 
                                 filters: Optional[dict] = None,
                                 limit: Optional[int] = 10,
                                 response_format: Optional[dict] = None,
                                 tools: Optional[List] = None,
                                 tool_choice: Optional[Union[str, dict]] = None,
                                 logprobs: Optional[bool] = None,
                                 top_logprobs: Optional[int] = None,
                                 parallel_tool_calls: Optional[bool] = None,
                                 deployment_id=None,
                                 extra_headers: Optional[dict] = None,
                                 # soon to be deprecated params by OpenAI
                                 functions: Optional[List] = None,
                                 function_call: Optional[str] = None,
                                 host: Optional[str] = None,
                                 port: Optional[int] = None,
                                 ):
        if not any([user_name, user_id, agent_id, run_id]):
            raise ValueError("One of user_name, user_id, agent_id, run_id must be provided")
        try:
            relevant_memories = await self._fetch_relevant_memories(
                messages, user_name, user_id, agent_id, run_id, filters, limit
            )
            memories_text = ""
            if relevant_memories:
                logger.debug(f"Relevant memories: {relevant_memories}")
                memories_text = "\n".join(memory["memory"] for memory in relevant_memories)
            else: 
                memories_text = ""
            prompt = RESPONSE_TEMPLATE
            prompt = prompt.format(memory=memories_text)

            if not messages or messages[0]["role"] != "system":
                messages = [{"role": "system", "content": prompt}] + messages
            else:
                messages[0]["content"] = prompt

            main_llm = Util().main_llm()          
            response = await self.openai_chat_completion(messages=messages, llm_name=main_llm.name)
            message: ChatMessage = ChatMessage()
            message.add_user_message(query)
            message.add_ai_message(response)
            self.chatDB.add(app_id=app_id, user_name=user_name, user_id=user_id, session_id=session_id, chat_message=message)
            await self.mem_instance.add(query, user_name=user_name, user_id=user_id, agent_id=agent_id, run_id=run_id, metadata=metadata, filters=filters)
            return response
        except Exception as e:  
            logger.exception(e)
            return None
        
        
    def add_chat_history(self, user_message: str, ai_message: str, app_id: Optional[str] = None, user_name: Optional[str] = None, user_id: Optional[str] = None, session_id: Optional[str] = None):
        try:
            message: ChatMessage = ChatMessage()
            message.add_user_message(user_message)
            message.add_ai_message(ai_message)
            self.chatDB.add(app_id=app_id, user_name=user_name, user_id=user_id, session_id=session_id, chat_message=message)
        except Exception as e:
            logger.exception(e)


    def add_chat_history_by_role(self, sender_name, responder_name, sender_text, responder_text):
        return self.chatDB.add_by_role(sender_name, responder_name, sender_text, responder_text)
    
            
    async def add_user_input_to_memory(self, user_input:str, user_name: Optional[str] = None, user_id: Optional[str] = None, agent_id: Optional[str] = None, run_id: Optional[str] = None, metadata: Optional[dict] = None, filters: Optional[dict] = None):
        try:
            await self.mem_instance.add(user_input, user_name=user_name, user_id=user_id, agent_id=agent_id, run_id=run_id, metadata=metadata, filters=filters)
        except Exception as e:
            logger.exception(e)

    async def _fetch_relevant_memories(
        self, messages, user_name,user_id, agent_id, run_id, filters, limit
    ):
        # Currently, only pass the last 6 messages to the search API to prevent long query
        message_input = [
            f"{message['role']}: {message['content']}\n" for message in messages
        ][-6:]
        # TODO: Make it better by summarizing the past conversation
        return await self.mem_instance.search(
            query="\n".join(message_input),
            user_name=user_name,
            user_id=user_id,
            agent_id=agent_id,
            run_id=run_id,
            filters=filters,
            limit=limit,
        )
    
    def get_grammar(self, file: str, path: str = None) -> str | None:
        try:
            if not path:
                config_path = Util().config_path()
                path = os.path.join(config_path, "grammars")
            file_path = os.path.join(path, file)
            with open(file_path) as f:
                return f.read()
        except Exception as e:
            logger.exception(e)
            return None

    def stop_uvicorn_server(self):
        if self.server:
            logger.debug("Stopping uvicorn server...")
            self.server.should_exit = True
                       
    def exit_gracefully(self, signum, frame):
        try:
            logger.debug("CTRL+C received, shutting down...")
            # shut down the chromadb server
            # self.shutdown_chroma_server()  # Shut down ChromaDB server
            self.stop_chroma_client()
            self.stop_uvicorn_server()
            # End the main thread
            self.stop()
            # Schedule shutdown
            #def shutdown():
            #    self.server.should_exit = True
            #threading.Thread(target=shutdown).start()
            #sys.exit(0)
        except Exception as e:
            sys.exit(0)
    
    def __enter__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    
if __name__ == "__main__":
    try:
        with Core() as core:
            asyncio.run(core.run()) # core.run()
    except Exception as e:
        sys.exit(0)
