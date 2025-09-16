import atexit
import json
from multiprocessing import Process
import os
import re
import runpy
import shutil
import subprocess
import sys
import threading
import time
from typing import Dict, List, Optional, Tuple
import aiohttp
import uvicorn
import yaml
from pathlib import Path
from loguru import logger
import watchdog.events
import watchdog.observers
import torch
import requests


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from memory.chat.message import ChatMessage
from memory.prompts import MEMORY_SUMMARIZATION_PROMPT
from base.base import CoreMetadata, User, LLM, EmailAccount

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
core_metadata =CoreMetadata.from_yaml(os.path.join(root_dir, 'config', 'core.yml'))
data_root = os.path.join(root_dir, 'database')
if  (os.path.exists(data_root) and core_metadata.reset_memory == True):
    core_metadata.reset_memory = False
    CoreMetadata.to_yaml(core_metadata, os.path.join(root_dir, 'config', 'core.yml'))
    shutil.rmtree(data_root)

def run_script_silent(script_path):
    with open(os.devnull, 'w') as devnull:
        sys.stdout = devnull
        sys.stderr = devnull
        result = runpy.run_path(script_path, run_name='__main__')

def run_script(script_path):
    result = runpy.run_path(script_path, run_name='__main__')

class Util:
    _instance = None
    _lock = threading.Lock() 

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(Util, cls).__new__(cls, *args, **kwargs)
        return cls._instance
    
    
    def __init__(self) -> None:
        if not hasattr(self, 'initialized'):
            self.initialized = True
            self.config_observer = None
            self.core_metadata = CoreMetadata.from_yaml(os.path.join(self.config_path(), 'core.yml'))
            self.silent = self.core_metadata.silent
            self.llms = self.get_llms()

            if self.has_gpu_cuda():
                if self.core_metadata.main_llm is None or len(self.core_metadata.main_llm) == 0:
                    self.core_metadata.main_llm = self.llm_for_gpu()
                    self.core_metadata.main_llm_type = "local"
                    CoreMetadata.to_yaml(self.core_metadata, os.path.join(self.config_path(), 'core.yml'))
                logger.debug("CUDA is available. Using GPU.")
            else:
                if self.core_metadata.main_llm is None or len(self.core_metadata.main_llm) == 0:
                    self.core_metadata.main_llm = self.llm_for_cpu()
                    self.core_metadata.main_llm_type = "local"
                    CoreMetadata.to_yaml(self.core_metadata, os.path.join(self.config_path(), 'core.yml'))
                logger.debug("CUDA is not available. Using CPU.")
            self.users : list = User.from_yaml(os.path.join(self.config_path(), 'user.yml'))
            self.email_account: EmailAccount = EmailAccount.from_yaml(os.path.join(self.config_path(), 'email_account.yml'))
            
            # Start to monitor the specified config files
            self.watch_config_file()

    def is_silent(self) -> bool:
        return self.silent
    
    def set_silent(self, silent: bool):
        self.silent = silent
        self.core_metadata.silent = silent
        CoreMetadata.to_yaml(self.core_metadata, os.path.join(self.config_path(), 'core.yml'))

        log_format = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
        if self.silent:
            logger.remove(sys.stdout)
            logger.add(sys.stdout, format=log_format, level="INFO")
        else:
            logger.remove(sys.stdout)
            logger.add(sys.stdout, format=log_format, level="DEBUG")

    def has_memory(self) -> bool:
        return self.core_metadata.use_memory
    
    def set_memory(self, use_memory: bool):
        self.core_metadata.use_memory = use_memory
        CoreMetadata.to_yaml(self.core_metadata, os.path.join(self.config_path(), 'core.yml'))


    def run_script_in_process(self, script_path) -> Process:
        process = None
        if self.silent:
            process = Process(target=run_script_silent, args=(script_path,))
        else:
            process = Process(target=run_script, args=(script_path,))

        process.start()
        return process
     
    
    def run_script_in_thread(self, script_path):
        thread = threading.Thread(target=run_script, args=(script_path,))
        thread.start()
        return thread

    def load_yml_config(self, config_path):
        """
        Load configuration from a YAML file.
        """
        config_file = Path(config_path)
        if not config_file.is_file():
            raise FileNotFoundError(f"Configuration file {config_path} not found.")
        
        with open(config_file, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
        return config
    
    def has_gpu_cuda(self) -> bool:
        return torch.cuda.is_available()


    def root_path(self):
        current_path = os.path.dirname(os.path.abspath(__file__))
        return os.path.dirname(current_path)
    
    def log_path(self):
        root = self.root_path()
        return os.path.join(root, 'logs')
    
    def data_path(self):
        root = self.root_path()
        return os.path.join(root, 'database')    

    def reset_memory(self): 
        self.core_metadata.reset_memory = True
        CoreMetadata.to_yaml(self.core_metadata, os.path.join(self.config_path(), 'core.yml'))
    
    def plugins_path(self):
        root = self.root_path()
        return os.path.join(root, 'plugins')
    
    def channels_path(self):
        root = self.root_path()
        return os.path.join(root, 'channels')
                 
    def config_path(self):
        return os.path.join(self.root_path(), 'config')
    
      
    def models_path(self):
        return os.path.join(self.root_path(), 'models')
    
    def setup_logging(self, module_name, mode):
        """
        Setup logging configuration using the configuration file.
        """
        log_path = self.log_path()
        log_format = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
        def filter_production(record):
            return record["extra"].get("production", False)

        def filter_debug(record):
            return record["extra"].get("shorttext", True)

        # remove the stdio logger
        logger.remove()
        if mode == "production":
            file_name = module_name + '_production.log'
            log_file = os.path.join(log_path, file_name)
            logger.add(log_file, format="{time} {level} {message}", filter=filter_production, level="INFO")
            logger.add(sys.stdout, format="{time} {level} {message}", filter=filter_production, level="INFO")
        else:
            file_name = module_name + '_debug.log'
            log_file = os.path.join(log_path, file_name)
            if self.silent:
                logger.add(sys.stdout, format=log_format, level="INFO")
            else:
                logger.add(sys.stdout, format=log_format, level="DEBUG")
            # The filter is to avoid to record long text into file
            logger.add(log_file, format=log_format, filter=filter_debug, level="DEBUG")
   
              
    def main_llm(self):
        main_llm_name = self.core_metadata.main_llm
        if self.core_metadata.main_llm_type == "local":
            for llm_name in self.llms:
                if llm_name == main_llm_name:
                    return os.path.join(self.models_path(), llm_name), llm_name, self.core_metadata.main_llm_type, self.core_metadata.main_llm_host, self.core_metadata.main_llm_port
            return None
        else:
            return main_llm_name, main_llm_name, self.core_metadata.main_llm_type, self.core_metadata.main_llm_host, self.core_metadata.main_llm_port
            
            
    def set_mainllm(self, main_llm_name, type = "local", language = "en", api_key_name = "", api_key = ""):
        if type == "local":
            if main_llm_name in self.llms:
                self.core_metadata.main_llm = main_llm_name 
                self.core_metadata.main_llm_type = type
                self.core_metadata.main_llm_language = language
                self.core_metadata.main_llm_api_key_name = api_key_name
                self.core_metadata.main_llm_api_key = api_key
                CoreMetadata.to_yaml(self.core_metadata, os.path.join(self.config_path(), 'core.yml'))
                return main_llm_name
            else:
                return None
        else:
            self.core_metadata.main_llm = main_llm_name 
            self.core_metadata.main_llm_type = type
            self.core_metadata.main_llm_language = language
            self.core_metadata.main_llm_api_key_name = api_key_name
            self.core_metadata.main_llm_api_key = api_key
            CoreMetadata.to_yaml(self.core_metadata, os.path.join(self.config_path(), 'core.yml'))
            return main_llm_name
        

    def set_api_key_for_llm(self):
        if self.core_metadata.main_llm_type == "local":
            return
        if self.core_metadata.main_llm_api_key_name == None or len(self.core_metadata.main_llm_api_key_name) == 0:
            return
        if self.core_metadata.main_llm_api_key == None or len(self.core_metadata.main_llm_api_key) == 0:
            return
        os.environ[self.core_metadata.main_llm_api_key_name] = self.core_metadata.main_llm_api_key
        
            
    def embedding_llm(self):
        embedding_llm_name = self.core_metadata.embedding_llm
        if self.core_metadata.embedding_llm_type == "local":
            for llm_name in self.llms:
                if llm_name == embedding_llm_name:
                    return os.path.join(self.models_path(), llm_name), llm_name, self.core_metadata.embedding_llm_type, self.core_metadata.embedding_host, self.core_metadata.embedding_port
            return None
        else:
            return embedding_llm_name, embedding_llm_name, self.core_metadata.embedding_llm_type, self.core_metadata.embedding_host, self.core_metadata.embedding_port
        
            
    def main_llm_size(self):
        name = self.core_metadata.main_llm.lower()  
        # Regular expression to find the model size (e.g., "14b")
        model_size_pattern = re.compile(r'(\d+)b')
        
        # Find all matches of the pattern in the name
        matches = model_size_pattern.findall(name)
        if matches:
            # Assuming you want the first match if there are multiple
            size = matches[0]
            # Convert size to integer representing billions
            return int(size)
        else:
            return 0
        
    def llm_size(self, llm_name):
        name = llm_name.lower()  
        # Regular expression to find the model size (e.g., "14b")
        model_size_pattern = re.compile(r'(\d+)b')
        
        # Find all matches of the pattern in the name
        matches = model_size_pattern.findall(name)
        if matches:
            # Assuming you want the first match if there are multiple
            size = matches[0]
            # Convert size to integer representing billions
            return int(size)
        else:
            return 0
        
    def llm_for_cpu(self):
        llms = self.available_llms()
        llm_num = len(llms)
        if llm_num < 1:
            return None
        if len(llms) == 1:
            return llms[0]
        for llm_name in llms:
            if self.llm_size(llm_name) <= 7:
                return llm_name
        return llms[0]
        
            
    def llm_for_gpu(self):
        llms = self.available_llms()
        llm_num = len(llms)
        if llm_num < 1:
            return None
        if len(llms) == 1:
            return llms[0]
        for llm_name in llms:
            size = self.llm_size(llm_name)
            if size >= 7 and size <= 14 :
                return llm_name
        return llms[0]
        
    def main_llm_language(self):
        return self.core_metadata.main_llm_language
    
    def main_llm_type(self):
        return self.core_metadata.main_llm_type
    

    def get_ollama_supported_models(self):
        try:
            url = "http://localhost:11434/api/tags"
            response = requests.get(url)
            if response.status_code == 200:
                models_data = response.json()
                # Extract the first part of model names before the colon
                model_prefixes = [model["name"].split(':')[0] for model in models_data["models"]]
                return model_prefixes
            else:
                # Handle errors or unexpected status codes
                return []
        except Exception as e:
            # Handle exceptions
            return []
        
    def pull_model_from_ollama(self, model_name):
        url = "http://localhost:11434/api/pull"
        payload = {"model": model_name}
        headers = {'Content-Type': 'application/json'}
        response = requests.post(url, data=json.dumps(payload), headers=headers)

        if response.ok:
            # Assuming the response contains multiple JSON objects (not standard JSON)
            # Split response by lines and parse each line as JSON
            #statuses = [json.loads(line) for line in response.iter_lines() if line.strip()]

            # Extract the 'status' values from the parsed JSON objects
            #status_contents = [status_dict["status"] for status_dict in statuses]
            return "Model successfully pulled from Ollama."
        else:
            # Handle errors, e.g., by returning None or raising an exception
            return "Failed to pull model from Ollama."
        
            
    def process_text(self, text):
        # Check if both <think> and </think> are in the text
        if '<think>' in text and '</think>' in text:
            # If so, remove the entire content within the first <think> to </think> (inclusive)
            processed_text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        elif '<think>' in text:
            # If there is a <think> without a corresponding </think>, remove the <think> tag
            logger.debug(f'There is a <think> without a corresponding </think> in the text: {text}')
            processed_text = ''
        elif '</think>' in text:
            # If there is a </think> without a corresponding <think>, keep the text after </think>
            processed_text = text.split('</think>', 1)[-1]
        else:
            # If neither tag is present, keep the text as is
            processed_text = text
        
        answer_index = processed_text.find('**Step-by-Step Explanation and Answer:**')
        if answer_index != -1:
            answer_index = processed_text.find('**Answer:**')
            if answer_index != -1:
                processed_text = processed_text[answer_index + len('**Answer:**'):]
            else:
                answer_index = processed_text.find('**Final Answer:**')
                if answer_index != -1:
                    processed_text = processed_text[answer_index + len('**Final Answer:**'):]
                else:
                    processed_text = ''
        else:
            answer_index = processed_text.find('**Step-by-Step Explanation:**')
            if answer_index != -1:
                answer_index = processed_text.find('**Answer:**')
                if answer_index != -1:
                    processed_text = processed_text[answer_index + len('**Answer:**'):]
                else:
                    answer_index = processed_text.find('**Final Answer:**')
                    if answer_index != -1:
                        processed_text = processed_text[answer_index + len('**Final Answer:**'):]
                    else:
                        processed_text = ''

        if len(processed_text.strip()) > 0:
            return processed_text.strip()
        else:
            return None
        

    def is_utf8_compatible(self, data):
        try:
            # Attempt to convert the data to a JSON string without ASCII encoding,
            # then encode it to UTF-8. This will raise an error if data can't be
            # represented in UTF-8.
            json.dumps(data, ensure_ascii=False).encode('utf-8')
        except UnicodeEncodeError:
            return False
        return True
    
    def check_main_model_server_health(self, timeout: int = 300) -> bool:
        """Check if the LLM server is ready by making a request to its health endpoint."""
        _, model, type, model_host, model_port = Util().main_llm()
        health_url = f"http://{model_host}:{model_port}/health"
        logger.debug(f"Main model Health URL: {health_url}")
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = requests.get(health_url, timeout=10)
                if response.status_code == 200:
                    logger.debug("Main model server is healthy and ready to accept requests.")
                    return True
                elif response.status_code == 503:
                    # The server is not ready yet
                    #logger.debug("Main model server is not ready yet, retrying...")
                    time.sleep(1)  # Wait for 1 second before trying again
                    continue
                else:
                    # The server is up but returned an unexpected status code
                    logger.error(f"Main model server returned unexpected status code: {response.status_code}")
                    return False
            except requests.exceptions.ConnectionError:
                # The request failed because the server is not up yet
                logger.debug("Main model server is not connected yet, retrying...")
            time.sleep(1)  # Wait for 1 second before trying again
        logger.error(f"Main model server did not become ready within {timeout} seconds.")
        return False
    
    def check_embedding_model_server_health(self, timeout: int = 120) -> bool:
        """Check if the LLM server is ready by making a request to its health endpoint."""
        _, model, type, model_host, model_port = Util().embedding_llm()
        health_url = f"http://{model_host}:{model_port}/health"
        logger.debug(f"Embedding model Health URL: {health_url}")
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = requests.get(health_url, timeout=10)
                if response.status_code == 200:
                    logger.debug("Embedding server is healthy and ready to accept requests.")
                    return True
                elif response.status_code == 503:
                    # The server is not ready yet
                    # logger.debug("Embedding server is not ready yet, retrying...")
                    time.sleep(1)  # Wait for 1 second before trying again
                    continue
                else:
                    # The server is up but returned an unexpected status code
                    logger.error(f"Embedding server returned unexpected status code: {response.status_code}")
                    return False
            except requests.exceptions.ConnectionError:
                # The request failed because the server is not up yet
                logger.debug("Embedding server is not connected yet, retrying...")
            time.sleep(1)  # Wait for 1 second before trying again
        logger.error(f"LLM server did not become ready within {timeout} seconds.")
        return False
            

    async def openai_chat_completion(self, messages: list[dict], 
                                     grammar: str=None,
                                     tools: Optional[List[Dict]] = None,
                                     tool_choice: str = "auto", 
                                     functions: Optional[List] = None,
                                     function_call: Optional[str] = None,
                                     ) -> str | None:    
        try:      
            _, model, type, model_host, model_port = Util().main_llm()
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
            if functions:
                data["functions"] = functions
            if function_call:
                data["function_call"] = function_call
            headers = {
                'Content-Type': 'application/json',
                'Authorization': 'Anything'
            }
            data_json = None
            if self.is_utf8_compatible(data):
                data_json = json.dumps(data, ensure_ascii=False)
            else:
                data_json = json.dumps(data, ensure_ascii=False).encode('utf-8')

            #logger.debug(f"Message Request to LLM: {data_json}")
            chat_completion_api_url = 'http://' + model_host + ':' + str(model_port) + '/v1/chat/completions'
            async with aiohttp.ClientSession() as session:
                async with session.post(chat_completion_api_url, headers=headers, data=data_json) as resp:
                    resp_json = await resp.text(encoding='utf-8')
                    # Ensure resp_json is a dictionary
                    while isinstance(resp_json, dict) == False:
                        resp_json = json.loads(resp_json)
                    #logger.debug(f"Original Response from LLM: {resp_json}")
                    if isinstance(resp_json, dict) and 'choices' in resp_json:
                        if isinstance(resp_json['choices'], list) and len(resp_json['choices']) > 0:
                            if 'message' in resp_json['choices'][0] and 'content' in resp_json['choices'][0]['message']:
                                message_content = resp_json['choices'][0]['message']['content'].strip()
                                # Filter out the <think> tag and its content
                                filtered_message_content = self.process_text(message_content)
                                if filtered_message_content is not None:
                                    logger.debug(f"Message Response from LLM: {message_content}")
                                    return filtered_message_content
                                else:
                                    #logger.error("filtered message content is None")
                                    return None
                    logger.error("Invalid response structure")
                    return None
        except Exception as e:
            logger.exception(e)
            return None
        
    
    def convert_chats_to_text(self, chats: list[ChatMessage]) -> str:
        text = ""
        for chat in chats:
            text += chat.human_message.content + "\n"
            text += chat.ai_message.content + "\n"
        return text
        

    async def llm_summarize(self, text: str,  lenLimit: int = 4096) -> str:
        if len(text) <= lenLimit or text == None:
            return text
        prompt = MEMORY_SUMMARIZATION_PROMPT
        prompt = prompt.format(text=text, size=lenLimit)
        resp = await self.openai_chat_completion([{"role": "user", "content": prompt}])
        if resp:
            logger.debug(f"Summary from LLM: {resp}")
            return resp
        else:
            logger.debug(f"Failed to get summary from LLM, return the original text, {text}")
            return text   


    def read_config(self, file_path):
        with open(file_path, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
        return config


    def write_config(self, file_path, config):
        with open(file_path, 'w', encoding='utf-8') as file:
            yaml.safe_dump(config, file, default_flow_style=False, sort_keys=False)


    def get_users(self):
        """
        Loads the users from the configuration file.

        Returns:
            Users: The users object, or None if the loading failed.
        """
        if self.users == None:
            self.users = User.from_yaml(os.path.join(self.config_path(), 'user.yml'))    
        return self.users
    
    def add_user(self, user: User):
        if self.users == None or len(self.users) == 0:
            self.users = self.get_users()
        for u in self.users:
            if user.name == u.name:
                return
        if self.users == None:
            self.users = []
        self.users.append(user)
        self.save_users(self.users)

    def remove_user(self, user: User):
        if self.users == None or len(self.users) == 0:
            return
        self.users = self.get_users()
        for u in self.users:
            if user.name == u.name:
                self.users.remove(u)
                self.save_users(self.users)
                break 

    def embedding_tokens_len(self):
        return self.core_metadata.embeddingTokensLen
    
    async def embedding(self, text):
        """
        Get the embedding for the given text using OpenAI.

        Args:
            text (str): The text to embed.

        Returns:
            list: The embedding vector.
        """
        text = text.replace("\n", " ")
        logger.debug(f"LlamaCppEmbedding.embed: text: {text}")
        embeddingTokenslen = self.embedding_tokens_len()
        if len(text) > embeddingTokenslen // 2:
            text = await self.llm_summarize(text, embeddingTokenslen // 2)
        logger.debug(f"LlamaCppEmbedding.embed: summarizedtext: {text}")
        host = self.core_metadata.embedding_host
        port = self.core_metadata.embedding_port
        embedding_txt = text.encode("utf-8")
        embedding_url = "http://" + host + ":" + str(port) + "/v1/embeddings"
        logger.debug(f"Embedding URL: {embedding_url}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    embedding_url,
                    headers={"accept": "application/json", "Content-Type": "application/json"},
                    data=json.dumps({"input": text}),
                ) as response:
                    response_json = await response.json()
                    #logger.debug(f"Response from embedding LLM: {response_json}")
                    ret = response_json["data"][0]["embedding"]
                    return ret
        except Exception as e:
            logger.debug("Embedding error:Failed to get embedding from LLM")
            logger.debug(e)
            return None

    def get_user(self, name: str):
        if self.users == None or len(self.users) == 0:
            self.users = self.get_users()
        for u in self.users:
            if u.name == name:
                return u
        return None
    
    def get_first_user(self) -> User:
        self.users = self.get_users()
        if self.users == None or len(self.users) == 0:
            self.create_default_user()
        return self.users[0]
    
    def create_default_user(self):
        user: User = User()
        user.name = 'GPT4People'
        user.email = []
        user.phone = []
        user.im = []
        self.add_user(user)

    def change_user_name(self, old_name: str, new_name: str):
        if self.users == None or len(self.users) == 0:
            self.users = self.get_users()
        for u in self.users:
            if u.name == old_name:
                u.name = new_name
                self.save_users(self.users)
                return

    def add_im_to_user(self, user_name: str, im: str):
        if self.users == None or len(self.users) == 0:
            self.users = self.get_users()
        for u in self.users:
            if u.name == user_name:
                u.im.append(im)
                self.save_users(self.users)
                return

    def remove_im_from_user(self, user_name: str, im: str):
        if self.users == None or len(self.users) == 0:
            self.users = self.get_users()
        for u in self.users:
            if u.name == user_name:
                u.im.remove(im)
                self.save_users(self.users)
                return
            
    def add_email_to_user(self, user_name: str, email: str):
        if self.users == None or len(self.users) == 0:
            self.users = self.get_users()
        for u in self.users:
            if u.name == user_name:
                u.email.append(email)
                self.save_users(self.users)
                return
            
    def remove_email_from_user(self, user_name: str, email: str):
        if self.users == None or len(self.users) == 0:
            self.users = self.get_users()
        for u in self.users:
            if u.name == user_name:
                u.email.remove(email)
                self.save_users(self.users)
                return
            
    def add_phone_to_user(self, user_name: str, phone: str):
        if self.users == None or len(self.users) == 0:
            self.users = self.get_users()
        for u in self.users:
            if u.name == user_name:
                u.phone.append(phone)
                self.save_users(self.users)
                return
            
    def remove_phone_from_user(self, user_name: str, phone: str):
        if self.users == None or len(self.users) == 0:
            self.users = self.get_users()
        for u in self.users:
            if u.name == user_name:
                u.phone.remove(phone)
                self.save_users(self.users)
                return
        
    def save_users(self, users: List[User] = None):
        User.to_yaml(users, os.path.join(self.config_path(), 'user.yml'))
    
    def get_email_account(self):
        if self.email_account == None:
            self.email_account = EmailAccount.from_yaml(os.path.join(self.config_path(), 'email_account.yml'))
        return self.email_account
    
    def save_email_account(self):
        self.email_account.to_yaml(os.path.join(self.config_path(), 'email_account.yml'))

    def get_core_metadata(self):
        if self.core_metadata == None:
            self.core_metadata = CoreMetadata.from_yaml(os.path.join(self.config_path(), 'core.yml'))
            if self.has_gpu_cuda():
                if self.core_metadata.main_llm is None or len(self.core_metadata.main_llm) == 0:
                    self.core_metadata.main_llm = self.llm_for_gpu
                    CoreMetadata.to_yaml(self.core_metadata, os.path.join(self.config_path(), 'core.yml'))

            else:
                if self.core_metadata.main_llm is None or len(self.core_metadata.main_llm) == 0:
                    self.core_metadata.main_llm = self.llm_for_cpu()
                    CoreMetadata.to_yaml(self.core_metadata, os.path.join(self.config_path(), 'core.yml'))
                
        return self.core_metadata
    
    def switch_llm(self, llm_name: str):
        if llm_name not in self.llms:
            return
        self.core_metadata.main_llm = llm_name
        CoreMetadata.to_yaml(self.core_metadata, os.path.join(self.config_path(), 'core.yml'))
    
    def stop_uvicorn_server(self, server: uvicorn.Server):
        try:
            if server:
                server.should_exit = True
                server.force_exit = True
                #await server.shutdown()
        except Exception as e:
            logger.exception(e)
        

    def get_llms(self):
        models_directory = self.models_path()
        if not os.path.exists(models_directory):
            return []  # Return an empty list if the models directory does not exist

        # Filter for files with a .gguf extension
        self.llms = [f for f in os.listdir(models_directory) if f.endswith('.gguf') and os.path.isfile(os.path.join(models_directory, f))]

        logger.debug(f"llms: {self.llms}")
        return self.llms
    
    def available_llms(self):
        llms = self.llms
        if self.core_metadata.embedding_llm in llms:
            llms.remove(self.core_metadata.embedding_llm)
        return llms
        
    def get_llm(self, name: str):        
        for llm_name in self.llms:
            if llm_name == name:
                return os.path.join(self.models_path(), llm_name), llm_name
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
    
        
    def watch_config_file(self):
        """
        Monitor the user.yml and core.yml changes in the config path.
        If some change happened, the users and core metadata can be reload automatically.
        """
        if self.config_observer is None:  
            class Handler(watchdog.events.PatternMatchingEventHandler):
                def __init__(self, util: Util):
                    super().__init__(patterns=['user.yml'])
                    self.util: Util = util

                def on_modified(self, event):
                    if event.src_path.endswith('user.yml'):
                        self.util.users = None
                        self.util.get_users()
        
      
            self.config_observer = watchdog.observers.Observer()
            self.config_observer.schedule(Handler(self), self.config_path(), recursive=False)
            self.config_observer.start()
                
            # Gracefully stop the observer
            atexit.register(lambda: self.stop_watching_config)
    
    
    def stop_watching_config(self):
        self.config_observer.stop()
        self.config_observer.join()    

        
# Example usage
if __name__ == "__main__":
    # Initialize Util
    util = Util()
    
    # Load and logger.debug core metadata
    core_metadata = util().get_core_metadata()
    logger.debug("core Metadata:", core_metadata)

    # Load and logger.debug users
    users = util().get_users()
    logger.debug("Users:", users)

    # Load and logger.debug llms
    llms = util().get_llms()
    logger.debug("LLMs:", llms)

    # logger.debug main LLM
    #main_llm = util().main_llm()
    #logger.debug("Main LLM:", main_llm)

    # logger.debug embedding LLM
    #embedding_llm = util.embedding_llm()
    #logger.debug("Embedding LLM:", embedding_llm)

