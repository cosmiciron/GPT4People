import asyncio
from enum import Enum
import json
import os
import signal
import sys
import threading
import time
from typing import Dict, List
import aiohttp
from dotenv import dotenv_values
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import httpx
from pydantic import BaseModel
import uvicorn
from loguru import logger
from base.util import Util
from base.base import Server, PromptRequest, AsyncResponse


channel_current_path = Util().root_path() + '/channels'
channel_env_path = os.path.join(channel_current_path, '.env')
channel_config = dotenv_values(channel_env_path)
channel_mode = channel_config['mode']


class ChannelMetadata(BaseModel):
    name: str
    host: str
    port: int
    endpoints: List[Dict]


class BaseChannel:
    def __init__(self, metadata: ChannelMetadata, app: FastAPI):
        Util().setup_logging(metadata.name, channel_mode)
        # Use the config to create the metadata
        self.metadata = metadata
        # Initialize other attributes
        self.app = app
        self.server = None
        self.llm_host = ""
        self.llm_port = 0
        self.llm_language = ""

        @self.app.exception_handler(RequestValidationError)
        async def validation_exception_handler(request: Request, exc: RequestValidationError):
            logger.error(f"Validation error: {exc} for request: {await request.body()}")
            return JSONResponse(
                status_code=422,
                content={"detail": exc.errors(), "body": exc.body},
            )

        @self.app.get("/")
        def read_root():
            return {"channel": self.metadata.name}
        
        @self.app.get("/info")
        def get_info():
            return self.metadata

        @self.app.get("/status")
        def get_status():
            return {"status": "OK"}
        
        @self.app.get("/shutdown")
        async def shutdown():
            # Schedule shutdown
            def shutdown():
                self.stop()
                self.server.should_exit = True
                time.sleep(1)
                sys.exit(0)
            threading.Thread(target=shutdown).start()
            return {"message": "channel shutting down..."}
        
        @self.app.post("/get_response")
        async def async_response(response: AsyncResponse):
            # Process the response from the core
            logger.debug(f"Received response for request {response.request_id}: {response.response_data}")
            await self.handle_async_response(response)
            # You can also update your internal state or send the response to the user here
            return Response(status_code=200)

        
    async def handle_async_response(self, response: AsyncResponse):
        """Handle the response from the core"""
        pass
        
    '''Add the endpoints in the sub helper class'''
    def initialize(self):
        """Initialize the channel and you can add more channel functions here"""
        self.register_channel(self.metadata.name, self.metadata.host, self.metadata.port, self.metadata.endpoints)

    async def run(self):
        """Run the channel using uvicorn"""
        try:
            logger.debug(f"Running channel {self.metadata.name} on {self.metadata.host}:{self.metadata.port}")
            config = uvicorn.Config(self.app, host=self.metadata.host, port=self.metadata.port, log_level="info")
            self.initialize()
            self.server = uvicorn.Server(config)
            await self.server.serve()
        except Exception as e:
            logger.exception(e)
            
            
    def register_channel(self, name, host, port, endpoints):
        """Register the channel in the core"""
        try:
            core_url = self.core()
            logger.debug(f"core url: {core_url}")
            register_url = f"{core_url}/register_channel"
            if host == "0.0.0.0":
                host = "127.0.0.1"
            response = httpx.post(register_url, json={"name": name, "host": host, "port": str(port), "endpoints": endpoints}, timeout=60.0)

            if response.status_code == 200:
                resp = response.json()
                self.llm_host = resp["host"]
                self.llm_port = resp["port"]
                self.llm_language = resp["language"]
                logger.debug(f"Channel {name} registered result: {resp['result']}")
                return True
            else:
                return False
        except httpx.HTTPError as err:
            logger.error(f"RegisterRequest to core failed: {err}")
            return False
        except Exception as err:
            logger.exception(f"Unexpected error: {err}")
            return False


    def deregister_channel(self, name, host, port, endpoints):
        """Deregister the channel from the core"""
        try:
            core_url = self.core()
            deregister_url = f"{core_url}/deregister_channel"
            if host == "0.0.0.0":
                host = "127.0.0.1"
            response = httpx.post(deregister_url, json={"name": name, "host": host, "port": str(port), "endpoints": endpoints})
            if response.status_code == 200:
                return True
            else:
                return False
        except httpx.HTTPError as err:
            logger.error(f"Deregister Request to core failed: {err}")
            return False
        except Exception as err:
            logger.exception(f"Unexpected error: {err}")
            return False
        

    def core(self) -> str | None:
        """Get the core url from sub class's .env file"""
        channels_path = Util().root_path() + '/channels/'
        env_path = os.path.join(channels_path, '.env')
        env_vars = dotenv_values(env_path)
        core_url = None
        if 'core_host' in env_vars and 'core_port' in env_vars:
            host = env_vars['core_host']
            port = env_vars['core_port']
            core_url = f"http://{host}:{port}"
        else:
            core_url = None
        return core_url
    

    async def transferTocore(self, request: PromptRequest) -> bool | None:
        logger.debug("channel transfering messages to core...")
        try:
            core_url = self.core()
            logger.debug(f"core url: {core_url}")
            process_url = f"{core_url}/process"
            request_json = request.model_dump()
            request_json['channelType'] = request.channelType.value
            request_json['contentType'] = request.contentType.value
            async with httpx.AsyncClient() as client:
                response = await client.post(process_url, json=request_json, timeout=60.0)

            logger.debug(f"core response: {response}")
            if response.status_code == 200:
                return True
            else:
                return False
        except httpx.HTTPError as err:
            logger.error(f"core Process failed: {err}")
            return False
        except Exception as err:
            logger.exception(f"Unexpected error: {err}")
            return False
        
    async def localChatWithcore(self, request: PromptRequest) -> str | None:
        try:
            core_url = self.core()
            process_url = f"{core_url}/local_chat"
            request_json = request.model_dump()
            request_json['channelType'] = request.channelType.value
            request_json['contentType'] = request.contentType.value
            async with httpx.AsyncClient() as client:
                response = await client.post(process_url, json=request_json, timeout=60.0)

            if response.status_code == 200:
                return response.text
            else:
                return None
        except httpx.HTTPError as err:
            logger.error(f"core Process failed: {err}")
            return None
        except Exception as err:
            logger.exception(f"Unexpected error: {err}")
            return None
        

    def syncTransferTocore(self, request: PromptRequest) -> str | None:
        logger.debug("channel transfering messages to core...")
        try:
            core_url = self.core()
            logger.debug(f"core url: {core_url}")
            process_url = f"{core_url}/process"
            request_json = request.model_dump()
            request_json['channelType'] = request.channelType.value
            request_json['contentType'] = request.contentType.value
            with httpx.Client() as client:
                response = client.post(process_url, json=request_json, timeout=60.0)

            logger.debug(f"core response: {response}")
            if response.status_code == 200:
                return True
            else:
                return False
        except httpx.HTTPError as err:
            logger.error(f"core Process failed: {err}")
            return False
        except Exception as err:
            logger.exception(f"Unexpected error: {err}")
            return False
    

    def stop(self):
        """Deinitialize something before the helper is shutdown. Eg, Deregister the helper from the core"""
        self.deregister_channel(self.metadata.name, self.metadata.host, self.metadata.port, self.metadata.endpoints)
        def shutdown():
            self.server.should_exit = True
            self.server.force_exit= True
        threading.Thread(target=shutdown).start()
        
        
    
    
    def exit_gracefully(self, signum, frame):
        try: 
            logger.debug("CTRL+C received, shutting down...")
            # End the main thread
            self.stop()
            
            #sys.exit(0)
        except Exception as e:
            logger.debug("channel stopped")
    
    def __enter__(self):
        logger.debug("channel initializing..., register the ctrl+c signal handler")
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

