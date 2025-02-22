import atexit
import json
import os
import re
import sys
import threading
from typing import Dict, List, Optional, Tuple
import aiohttp
import yaml
from pathlib import Path
from loguru import logger
import watchdog.events
import watchdog.observers

from memory.chat.message import ChatMessage
from memory.prompts import MEMORY_SUMMARIZATION_PROMPT
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from base.base import CoreMetadata, User, LLM, GPT4PeopleAccount


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
            self.core_metadata : CoreMetadata = CoreMetadata.from_yaml(os.path.join(self.config_path(), 'core.yml'))
            self.users : list = User.from_yaml(os.path.join(self.config_path(), 'user.yml'))
            self.llms: list[LLM]= LLM.from_yaml(os.path.join(self.config_path(), 'llm.yml'))
            self.gpt4people_account: GPT4PeopleAccount = GPT4PeopleAccount.from_yaml(os.path.join(self.config_path(), 'gpt4people_account.yml'))
            
            # Start to monitor the specified config files
            self.watch_config_file()


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
    
      
    def root_path(self):
        current_path = os.path.dirname(os.path.abspath(__file__))
        return os.path.dirname(current_path)
    
    def log_path(self):
        root = self.root_path()
        return os.path.join(root, 'logs')
    
    def data_path(self):
        root = self.root_path()
        return os.path.join(root, 'database')
    
    def plugins_path(self):
        root = self.root_path()
        return os.path.join(root, 'plugins')
                 
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
            logger.add(sys.stdout, format=log_format, level="DEBUG")
            # The filter is to avoid to record long text into file
            logger.add(log_file, format=log_format, filter=filter_debug, level="DEBUG")
   
              
    def main_llm(self) -> LLM:
        main_llm = self.core_metadata.main_llm
        for llm in self.llms:
            if llm.name == main_llm:
                return llm
            
            
    def memory_llm(self) -> LLM:
        memory_llm = self.core_metadata.memory_llm
        for llm in self.llms:
            if llm.name == memory_llm:
                return llm
            
            
    def embedding_llm(self) -> LLM:
        embedding_llm = self.core_metadata.embedding_llm
        for llm in self.llms:
            if llm.name == embedding_llm:
                #llm.port = 5066
                return llm
            

    def process_text(self, text):
        # Check if both <think> and </think> are in the text
        if '<think>' in text and '</think>' in text:
            # If so, remove the entire content within the first <think> to </think> (inclusive)
            processed_text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        elif '<think>' in text:
            # If there is a <think> without a corresponding </think>, remove the <think> tag
            processed_text = re.sub(r'<think>', '', text)
        elif '</think>' in text:
            # If there is a </think> without a corresponding <think>, keep the text after </think>
            processed_text = text.split('</think>', 1)[-1]
        else:
            # If neither tag is present, keep the text as is
            processed_text = text
        
        if len(processed_text.strip()) >0:
            return processed_text.strip()
        

    def is_utf8_compatible(self, data):
        try:
            # Attempt to convert the data to a JSON string without ASCII encoding,
            # then encode it to UTF-8. This will raise an error if data can't be
            # represented in UTF-8.
            json.dumps(data, ensure_ascii=False).encode('utf-8')
        except UnicodeEncodeError:
            return False
        return True
            

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
            data_json = None
            if self.is_utf8_compatible(data):
                data_json = json.dumps(data, ensure_ascii=False)
            else:
                data_json = json.dumps(data, ensure_ascii=False).encode('utf-8')

            logger.debug(f"Message Request to LLM: {data_json}")
            chat_completion_api_url = 'http://' + model_host + ':' + str(model_port) + '/v1/chat/completions'
            async with aiohttp.ClientSession() as session:
                async with session.post(chat_completion_api_url, headers=headers, data=data_json) as resp:
                    resp_json = await resp.text(encoding='utf-8')
                    # Ensure resp_json is a dictionary
                    while isinstance(resp_json, dict) == False:
                        resp_json = json.loads(resp_json)
                    logger.debug(f"Original Response from LLM: {resp_json}")
                    if isinstance(resp_json, dict) and 'choices' in resp_json:
                        if isinstance(resp_json['choices'], list) and len(resp_json['choices']) > 0:
                            if 'message' in resp_json['choices'][0] and 'content' in resp_json['choices'][0]['message']:
                                message_content = resp_json['choices'][0]['message']['content'].strip()
                                # Filter out the <think> tag and its content
                                filtered_message_content = self.process_text(message_content)
                                logger.debug(f"Message Response from LLM: {message_content}")
                                return filtered_message_content
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
        

    async def llm_summarize(self, text: str) -> str:
        if len(text) <= 1024 or text == None:
            return text
        prompt = MEMORY_SUMMARIZATION_PROMPT
        prompt = prompt.format(text=text)
        resp = await self.openai_chat_completion([{"role": "user", "content": prompt}])
        if resp:
            logger.debug(f"Summary from LLM: {resp}")
            return resp
        else:
            logger.debug(f"Failed to get summary from LLM, return the original text, {text}")
            return text   

    def get_users(self):
        """
        Loads the users from the configuration file.

        Returns:
            Users: The users object, or None if the loading failed.
        """
        if self.users == None:
            self.users = User.from_yaml(os.path.join(self.config_path(), 'user.yml'))    
        return self.users
    
    def get_gpt4people_account(self):
        if self.gpt4people_account == None:
            self.gpt4people_account = GPT4PeopleAccount.from_yaml(os.path.join(self.config_path(), 'gpt4people_account.yml'))
        return self.gpt4people_account
    
    def save_gpt4people_account(self):
        self.gpt4people_account.to_yaml(os.path.join(self.config_path(), 'gpt4people_account.yml'))

    def get_core_metadata(self):
        if self.core_metadata == None:
            self.core_metadata = CoreMetadata.from_yaml(os.path.join(self.config_path(), 'core.yml'))
        return self.core_metadata
        
        
    def get_llms(self):
        if self.llms == None:
            self.llms = LLM.from_yaml(os.path.join(self.config_path(), 'llm.yml'))
        return self.llms
        
    def get_llm(self, name: str) -> LLM:        
        for llm in self.llms:
            if llm.name == name:
                return llm
    
           
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
        
        
    def get_core_metadata(self):
        try:
            if self.core_metadata is not None:
                return self.core_metadata
        except Exception as e:
            logger.exception(e)
            return None
        
        
    def watch_config_file(self):
        """
        Monitor the user.yml and core.yml changes in the config path.
        If some change happened, the users and core metadata can be reload automatically.
        """
        if self.config_observer is None:  
            class Handler(watchdog.events.PatternMatchingEventHandler):
                def __init__(self, util: Util):
                    super().__init__(patterns=['user.yml', 'core.yml', 'llm.yml'])
                    self.util: Util = util

                def on_modified(self, event):
                    if event.src_path.endswith('user.yml'):
                        self.util.users = None
                        self.util.get_users()
                    elif event.src_path.endswith('core.yml'):
                        self.util.core_metadata = None
                        self.util.get_core_metadata()
                    elif event.src_path.endswith('llm.yml'):
                        self.util.llms = None
                        self.util.get_llms()
        
      
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
    
    # Load and print core metadata
    core_metadata = util.get_core_metadata()
    print("core Metadata:", core_metadata)

    # Load and print users
    users = util.get_users()
    print("Users:", users)

    # Load and print llms
    llms = util.get_llms()
    print("LLMs:", llms)

    # Print main LLM
    main_llm = util.main_llm()
    print("Main LLM:", main_llm)

    # Print memory LLM
    memory_llm = util.memory_llm()
    print("Memory LLM:", memory_llm)

    # Print embedding LLM
    embedding_llm = util.embedding_llm()
    print("Embedding LLM:", embedding_llm)

