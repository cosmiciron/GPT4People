import asyncio
from datetime import datetime
import json
import os
import sys
from pathlib import Path
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Response
from loguru import logger
from pydantic import BaseModel
from base.BaseChannel import ChannelMetadata, BaseChannel
from base.base import PromptRequest, AsyncResponse, ChannelType, ContentType
from dotenv import dotenv_values
import yaml


@asynccontextmanager
async def lifespan(app: FastAPI):
    #await register_with_core()
    logger.debug("IM Channel lifespan started!")
    yield
    logger.debug("IM Channel lifespan end!")
    try:
        # Do some deinitialization
        pass
    except:
        pass

channel_app: FastAPI = FastAPI(lifespan=lifespan)  


class wechatRequest(BaseModel):
    im_name: str
    sender: str
    message: str
    msg_id: str


class Channel(BaseChannel):
    def __init__(self, metadata: ChannelMetadata):
        super().__init__(metadata=metadata, app=channel_app)

    def core(self) -> str | None:
        core_url = super().core()
        if core_url is not None:
            return core_url
        # Read the core host and port from .env file in each helper folder
        current_path = os.path.dirname(os.path.abspath(__file__))
        env_path = os.path.join(current_path, '.env')
        env_vars = dotenv_values(env_path)
        if 'core_host' in env_vars and 'core_port' in env_vars:
            host = env_vars['core_host']
            port = env_vars['core_port']
            core_url = f"http://{host}:{port}"
        else:
            core_url = None
        return core_url


    def initialize(self):
        logger.debug("IM Channel initializing...")
        super().initialize()

        @self.app.post("/on_wechat_message")
        async def on_wechat_message(request: wechatRequest):
            logger.debug(f"Received request: {request.json()}")
            try:
                # Extract data from request
                im_name = request.im_name
                sender = request.sender
                message = request.message
                msg_id = request.msg_id

                request = PromptRequest(
                    request_id= msg_id,
                    channel_name= self.metadata.name,
                    request_metadata={},
                    channelType=ChannelType.IM.value,
                    user_name= sender,
                    user_id= sender, # The wechaty will return like wechat:shileipeng
                    contentType=ContentType.TEXT.value,
                    text= message,
                    action='',
                    host = self.metadata.host,
                    port = self.metadata.port,
                    images=[],
                    videos=[],
                    audios=[],
                    timestamp= datetime.now().timestamp()
                )

                # Call handle_message with the extracted data
                response_message = await self.transferTocore(request=request)
                if response_message is None:
                    return ""
                # Return a suitable response
                return {"message": "Message processed successfully", "response": response_message}
            except Exception as e:
                logger.exception(e)
                return {"message": "System Internal Error", "response": "Sorry, something went wrong. Please try again later."}
            

         # add more endpoints here    
        logger.debug("IM Channel initialized and all the endpoints are registered!")
        
        
    async def handle_async_response(self, response: AsyncResponse):
        """Handle the response from the core"""
        pass


    def stop(self):
        # do some deinitialization here
        super().stop()
        logger.debug("Wechat Channel is stopping!")
    

if __name__ == "__main__":
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.yml')
    with open(config_path, 'r', encoding='utf-8') as file:
        config = yaml.safe_load(file)
        logger.debug(config)
        metadata = ChannelMetadata(**config)
    with Channel(metadata=metadata) as channel:
        asyncio.run(channel.run())

