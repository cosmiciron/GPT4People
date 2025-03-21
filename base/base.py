from datetime import datetime
from enum import Enum
import json
import os
from typing import List, Dict, Optional, Union
import uuid
from pydantic import BaseModel, Field
import uvicorn
import yaml
from dataclasses import dataclass, field
from typing import Dict, List, Any
    
class ChannelType(Enum):
    """Enum representing different communication channels."""
    Email = "EMAIL"
    SMS = "SMS"
    Phone = "PHONE"
    IM = "IM"

    @classmethod
    def list(cls):
        """Returns a list of all channel types."""
        return list(map(lambda c: c.value, cls))

class ContentType(Enum):
    """Enum representing different content types."""
    TEXT = "TEXT"
    TEXTWITHIMAGE = "TEXTWITHIMAGE"
    IMAGE = "IMAGE"
    AUDIO = "AUDIO"
    VIDEO = "VIDEO"
    HTML = "HTML"
    OTHER = "OTHER"

    @classmethod
    def list(cls):
        """Returns a list of all content types."""
        return list(map(lambda c: c.value, cls))
      

class PromptRequest(BaseModel):
    request_id: str
    channel_name: str
    request_metadata: dict
    channelType: ChannelType
    user_name: str
    app_id: str
    user_id: str # Eg Email address, phonenumber, IM_id 
    contentType: ContentType
    text: str
    action: str
    host: str
    port: int  
    images: List[str] # only for TEXTWITHIMAGE and IMAGE, the value is path with name of the images
    videos: List[str] # only for VIDEO, the value is path with the name of videos
    audios: List[str] # only for AUDIO, the value is path with the name of audios
    timestamp: float

class IntentType(Enum):
    TIME = "TIME"
    OTHER = "OTHER"

class Intent:
    def __init__(self, type: IntentType, text: str, intent_text: str, timestamp: float, chatHistory: str):
        self.type = type
        self.text = text
        self.intent_text = intent_text
        self.timestamp = timestamp
        self.chatHistory = chatHistory
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Intent':
        return cls(
            type=data.get('type'),
            text=data.get('text'),
            intent_text=data.get('intent_text'),
            timestamp=data.get('timestamp'),
            chatHistory = ''
        )

    def to_json(self) -> str:
        return json.dumps(self.__dict__)

    def from_json(cls, data: str) -> 'Intent':
        return cls.from_dict(json.loads(data))
    
    
class AsyncResponse(BaseModel):
    request_id: str
    host: str
    port: int
    from_channel: str
    request_metadata: Dict
    response_data: Dict
    
    
@dataclass
class User:
    name: str
    email: List[str] = field(default_factory=list)
    im: List[str] = field(default_factory=list)
    phone: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)

    @staticmethod
    def from_yaml(yaml_file: str) -> List['User']:
        with open(yaml_file, 'r', encoding='utf-8') as file:
            data = yaml.safe_load(file)

        return [User(**user) for user in data['users']]

    @staticmethod
    def to_yaml(users: List['User'], yaml_file: str):
        with open(yaml_file, 'w', encoding='utf-8') as file:
            yaml.safe_dump({'users': [user.__dict__ for user in users]}, file)


class GPT4PeopleAccount:
    def __init__(self, imap_host: str, imap_port: int, smtp_host: str, smtp_port: int, email_user: str, email_pass: str):
        self.imap_host = imap_host
        self.imap_port = imap_port
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.email_user = email_user
        self.email_pass = email_pass

    @classmethod
    def from_yaml(cls, filepath: str):
        with open(filepath, 'r', encoding='utf-8') as file:
            data = yaml.safe_load(file)
            account_data = data['gpt4people_account']
            return cls(**account_data)

    def to_yaml(self, filepath: str):
        """Serializes the account data to a YAML file."""
        account_data = {
            'gpt4people_account': {
                'imap_host': self.imap_host,
                'imap_port': self.imap_port,
                'smtp_host': self.smtp_host,
                'smtp_port': self.smtp_port,
                'email_user': self.email_user,
                'email_pass': self.email_pass,
            }
        }
        with open(filepath, 'w', encoding='utf-8') as file:
            yaml.dump(account_data, file, default_flow_style=False)

            
# Supported models            
# https://github.com/BerriAI/litellm/blob/57f37f743886a0249f630a6792d49dffc2c5d9b7/model_prices_and_context_window.json#L835            
class ChatRequest(BaseModel):
    model: str
    messages: List[Dict[str, Union[str, List[Dict[str, str]]]]] = []
    extra_body: Dict[str, Union[str, int, float, dict, list]] = None
    timeout: Union[float, int, None] = None
    temperature: Union[float, None] = None
    top_p: Union[float, None] = None
    n: Union[int, None] = None
    stream: Union[bool, None] = None
    stream_options: Union[Dict[str, Union[str, int, float, dict, list]], None] = None
    max_tokens: Union[int, None] = 2048
    presence_penalty: Union[float, None] = None
    frequency_penalty: Union[float, None] = None
    logit_bias: Union[Dict[str, Union[str, int, float, dict, list]], None] = None
    user: Union[str, None] = None
    response_format: Union[Dict[str, Union[str, int, float, dict, list]], None] = None
    seed: Union[int, None] = None
    tools: Union[List, None] = None
    tool_choice: Union[str, None] = None
    parallel_tool_calls: Union[bool, None] = None
    logprobs: Union[bool, None] = None
    top_logprobs: Union[int, None] = None
    # soon to be deprecated params by OpenAI
    functions: Union[List, None] = None
    function_call: Union[str, None] = None
    # set api_base, api_version, api_key
    base_url: Union[str, None] = None
    api_version: Union[str, None] = None
    api_key: Union[str, None] = None

    
    
class EmbeddingRequest(BaseModel):
    model: str
    input: list[str]
    '''
    Cohere v3 Models have a required parameter: input_type, it can be one of the following four values:

    input_type="search_document": (default) Use this for texts (documents) you want to store in your vector database
    input_type="search_query": Use this for search queries to find the most relevant documents in your vector database
    input_type="classification": Use this if you use the embeddings as an input for a classification system
    input_type="clustering": Use this if you use the embeddings for text clustering
    '''
    dimensions: int | None = None,
    timeout: int = 600,
    input_type: Optional[str] = None,
    api_base: Optional[str] = None,
    api_version: Optional[str] = None,
    api_key: Optional[str] = None
    api_type: str | None = None
    
    
class ImageGenerationRequest(BaseModel):
    model: str  #The model to use for image generation. Defaults to openai/dall-e-2
    prompt: str
    n: Optional[int] = None, #The number of images to generate. Must be between 1 and 10. For dall-e-3, only n=1 is supported.
    quality: Optional[str] = None, #The quality of the image that will be generated. hd creates images with finer
    response_format: Optional[str] = None, #The format in which the generated images are returned. Must be one of url or b64_json.
    size: Optional[str] = None, #The size of the generated images. Must be one of 256x256, 512x512, or 1024x1024,for dall-e-2. Must be one of 1024x1024, 1792x1024, or 1024x1792 for dall-e-3 models.
    style: Optional[str] = None,
    timeout:Optional[int]=600,  # default to 10 minutes The maximum time, in seconds, to wait for the API to respond. Defaults to 600 seconds (10 minutes).
    api_key: Optional[str] = None, #The API key to authenticate and authorize requests. If not provided, the default API key is used.
    api_base: Optional[str] = None, #The api endpoint you want to call the model with
    api_version: Optional[str] = None #(Azure-specific) the api version for the call; required for dall-e-3 on Azure
    

@dataclass
class LLM:
    name: str
    type: str
    alias: str
    path: str
    description: str
    languages: List[str]
    introduction: str
    capabilities: List[str]
    host: str
    port: int
    parameters: Dict[str, Any]

    @staticmethod
    def from_yaml(yaml_file: str) -> List['LLM']:
        with open(yaml_file, 'r', encoding='utf-8') as file:
            data = yaml.safe_load(file)
        
        llms = []
        for name, details in data['llms'].items():
            llms.append(LLM(name=name, **details))
        
        return llms

    @staticmethod
    def to_yaml(llms: List['LLM'], yaml_file: str):
        with open(yaml_file, 'w', encoding='utf-8') as file:
            llms_dict = {'llms': {llm.name: llm.__dict__ for llm in llms}}
            for llm in llms_dict['llms'].values():
                llm.pop('name')
            yaml.safe_dump(llms_dict, file)
    
'''
class EndPoint(BaseModel):
    path: str
    method: str
    description: str
    capabilities: List[str]
    input: Dict[str, str]
    output: Dict[str, str]


class VectorDB(BaseModel):
    host: str
    port: int
    api: str
    path: str
    persist_path: str
    is_persistent: bool
    anonymized_telemetry: bool
'''

import yaml
from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class Chroma:
    host: str
    port: int
    api: str
    is_persistent: bool
    anonymized_telemetry: bool

@dataclass
class VectorDB:
    Chroma: Chroma

@dataclass
class Endpoint:
    path: str
    method: str
    description: str
    capabilities: List[str]
    input: Dict[str, Any]
    output: Dict[str, Any]

@dataclass
class CoreMetadata:
    name: str
    host: str
    port: int
    mode: str
    model_path: str
    available_llms: List[str]
    embeddingTokensLen: int
    main_llm: str
    embedding_llm: str
    silent: bool
    use_memory: bool
    reset_memory: bool
    vectorDB: VectorDB
    endpoints: List[Endpoint]

    @staticmethod
    def from_yaml(yaml_file: str) -> 'CoreMetadata':
        with open(yaml_file, 'r', encoding='utf-8') as file:
            data = yaml.safe_load(file)
        
        # Parse the nested structures
        chroma = Chroma(**data['vectorDB']['Chroma'])
        vectorDB = VectorDB(Chroma=chroma)
        endpoints = [Endpoint(**ep) for ep in data['endpoints']]
        
        return CoreMetadata(
            name=data['name'],
            host=data['host'],
            port=data['port'],
            mode=data['mode'],
            model_path=data['model_path'],
            available_llms=data['available_llms'],
            embeddingTokensLen=data['embeddingTokensLen'],
            main_llm=data['main_llm'],
            embedding_llm=data['embedding_llm'],
            silent=data['silent'],
            use_memory=data['use_memory'],
            reset_memory=data['reset_memory'],
            vectorDB=vectorDB,
            endpoints=endpoints
        )

    # @staticmethod
    # def to_yaml(core: 'CoreMetadata', yaml_file: str):
    #     with open(yaml_file, 'w', encoding='utf-8') as file:
    #         # Convert the core instance to a dictionary
    #         yaml.safe_dump(core.__dict__, file, default_flow_style=False)

    @staticmethod
    def to_yaml(core: 'CoreMetadata', yaml_file: str):
        with open(yaml_file, 'w', encoding='utf-8') as file:
            # Manually prepare a dictionary to serialize
            core_dict = {
                'name': core.name,
                'host': core.host,
                'port': core.port,
                'mode': core.mode,
                'model_path': core.model_path,
                'available_llms': core.available_llms,
                'embeddingTokensLen': core.embeddingTokensLen,
                'main_llm': core.main_llm,
                'silent': core.silent,
                'use_memory': core.use_memory,
                'reset_memory': core.reset_memory,
                'embedding_llm': core.embedding_llm,
                'vectorDB': {
                    # Assuming Chroma has serializable attributes
                    'Chroma': vars(core.vectorDB.Chroma)
                },
                'endpoints': [
                    # Convert each Endpoint object to dictionary
                    vars(ep) for ep in core.endpoints
                ]
            }
            yaml.safe_dump(core_dict, file, default_flow_style=False)

 
class RegisterAgentRequest(BaseModel):
    name: str
    host: str
    port: str
    endpoints: List[Dict]


class RegisterChannelRequest(BaseModel):
    name: str
    host: str
    port: str
    endpoints: List[Dict]
    
    
class Server(uvicorn.Server):

    # Override
    def install_signal_handlers(self) -> None:

        # Do nothing
        pass
    