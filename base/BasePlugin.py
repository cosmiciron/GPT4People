
import os
import sys
from typing import Tuple

import yaml
from loguru import logger
from base.base import PromptRequest
from base.util import Util
from core.coreInterface import CoreInterface
class BasePlugin:
    def __init__(self, coreInst: CoreInterface):
        self.config: dict = None
        self.initialized = False
        self.coreInst = coreInst
        self.user_input = ''
        self.promptRequest: PromptRequest = None
        self.description = ''
        self.keywords = []
        self.parameters = {}  

    def initialize(self):
        logger.debug(f"Initializing plugin: {self.config['description']}")
        self.set_description(self.config['description'])
        #self.set_keywords(self.config['keywords'])
        #self.set_parameters(self.config.get('parameters', {}))


    def get_description(self):
        return self.description
    
    def set_description(self, description):
        self.description = description

    def get_keywords(self):
        return self.keywords
    
    def set_keywords(self, keywords):
        self.keywords = keywords

    def add_keyword(self, keyword):
        self.keywords.append(keyword)

    def remove_keyword(self, keyword):
        self.keywords.remove(keyword)

    def get_parameters(self):
        return self.parameters
  
    def set_parameters(self, parameters):
        self.parameters = parameters

    async def run(self):       
        pass

    async def check_best_plugin(self, text: str) -> Tuple[bool, str]:
        return False, ''

    def cleanup(self):
        if not self.initialized:
            self.initialized = True