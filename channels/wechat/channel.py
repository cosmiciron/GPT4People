import asyncio
from datetime import datetime
import json
import os
import sys
from pathlib import Path
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Response
from loguru import logger
from pydantic import BaseModel
from dotenv import dotenv_values
import yaml
from wcferry import Wcf, WxMsg
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from base.util import Util
from base.base import PromptRequest, AsyncResponse, ChannelType, ContentType
from base.BaseChannel import ChannelMetadata, BaseChannel



@asynccontextmanager
async def lifespan(app: FastAPI):
    #await register_with_core()
    logger.debug("Wechat Channel lifespan started!")
    yield
    logger.debug("Wechat Channel lifespan end!")
    try:
        # Do some deinitialization
        pass
    except:
        pass

channel_app: FastAPI = FastAPI(lifespan=lifespan)  

class Channel(BaseChannel):
    def __init__(self, metadata: ChannelMetadata):
        super().__init__(metadata=metadata, app=channel_app)
        # Determine the root running path
        root_running_path = Path.cwd()  # This gives the current working directory

        # Define the logs folder and wcf.txt file path relative to the root running directory
        logs_folder = os.path.join(root_running_path, "logs")
        if not os.path.exists(logs_folder):
            os.makedirs(logs_folder)
        wcf_file = os.path.join(logs_folder, "wcf.txt")

        if not os.path.isfile(wcf_file):
            with open(wcf_file, "x") as f:
                pass
        self.wcf_file = wcf_file
        self.wcf = Wcf(debug=False)
        self.wcf.LOG = False
        self.wcf.enable_recv_msg(self.on_wechat_message)


    def on_wechat_message(self, msg: WxMsg):
        logger.debug(f"Received request: {msg}")
        contacts = self.wcf.get_contacts()
        name = ''
        for contact in contacts:
            logger.debug(contact)

        name = msg.sender
        roomid = msg.roomid
        action = ''
        text = msg.content.lower()
        if text.startswith('+') or text.startswith('+'):
            action = 'store'
            text = msg.content[1:]
        elif text.startswith('?') or text.startswith('？'):
            action = 'retrieve'
            text = msg.content[1:]
        else:
            action = 'respond'
            text = msg.content

        logger.debug(f"msg_id: {msg.id}, msg sender: {name}, roomid: {roomid}, action: {action}, text: {text}")
        #if roomid == 'filehelper':
        #    action = 'query'
        try:
            request = PromptRequest(
                request_id= str(msg.id),
                channel_name= self.metadata.name,
                request_metadata={'sender': msg.sender},
                channelType=ChannelType.IM.value,
                user_name= name,
                app_id= 'wechat',
                user_id= 'wechat:' + name,  #msg.sender, The wechaty will return like wechat:shileipeng
                contentType=ContentType.TEXT.value,
                text= text,
                action= action,
                host = self.metadata.host,
                port=self.metadata.port,
                images=[],
                videos=[],
                audios=[],
                timestamp= datetime.now().timestamp()   
            )


            # Call handle_message with the extracted data
            self.syncTransferTocore(request=request)

        except Exception as e:
            logger.exception(e)


    def initialize(self):
        logger.debug("Wechat Channel initializing...")
        super().initialize()
            
         # add more endpoints here    
        logger.debug("IM Channel initialized and all the endpoints are registered!")


    def stop(self):
        # do some deinitialization here
        self.wcf.cleanup()
        super().stop()    
        logger.debug("Wechat Channel is stopping!")
        
        
    async def handle_async_response(self, response: AsyncResponse):
        """Handle the response from the core"""
        request_id = response.request_id
        response_data = response.response_data
        sender = response.request_metadata['sender']
        if 'text' in response_data:
            text = response_data['text']
            self.wcf.send_text(text, sender)
        if 'image' in response_data:
            # Eg. C:/Projs/WeChatRobot/TEQuant.jpeg
            # or https://raw.githubusercontent.com/lich0821/WeChatFerry/master/assets/TEQuant.jpg
            image_path = response_data['image']
            await asyncio.to_thread(self.wcf.send_image, image_path, sender)
        if 'video' in response_data:
            video_path = response_data['video']
            await asyncio.to_thread(self.wcf.send_file, video_path, sender)
        if 'file' in response_data:
            file_path = response_data['file']
            await asyncio.to_thread(self.wcf.send_file, file_path, sender)
        if 'audio' in response_data:
            audio_path = response_data['audio']
            await asyncio.to_thread(self.wcf.send_file, audio_path, sender)   

shutdown_url = ""
def main():
    try:
        root = Util().channels_path()
        config_path = os.path.join(root, 'wechat', 'config.yml')
        with open(config_path, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
            #logger.debug(config)
            metadata = ChannelMetadata(**config)

        global shutdown_url
        host = metadata.host
        if host == '0.0.0.0':
            host = '127.0.0.1'
        shutdown_url = "http://" + host + ":" + str(metadata.port) + "/shutdown"
        with Channel(metadata=metadata) as channel:
                asyncio.run(channel.run())
    except Exception as e:
        logger.exception(e)


def suicide():
    try:
        global shutdown_url
        httpx.get(shutdown_url)
    except Exception as e:
        logger.exception(e)

if __name__ == "__main__":
    main()

