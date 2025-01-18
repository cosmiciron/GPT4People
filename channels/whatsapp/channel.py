import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
import os
import sys
from pathlib import Path
import threading
import httpx
from abc import ABC, abstractmethod

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from contextlib import asynccontextmanager
from fastapi import FastAPI
from loguru import logger
from pydantic import BaseModel
from base.BaseChannel import ChannelMetadata, BaseChannel
from base.base import PromptRequest, AsyncResponse, ChannelType, ContentType
from dotenv import dotenv_values
import yaml
from os import getenv
from yowsup.layers.interface                           import YowInterfaceLayer, ProtocolEntityCallback
from yowsup.layers.protocol_messages.protocolentities  import TextMessageProtocolEntity
from yowsup.layers.protocol_receipts.protocolentities  import OutgoingReceiptProtocolEntity
from yowsup.layers.protocol_acks.protocolentities      import OutgoingAckProtocolEntity
from yowsup.stacks import YowStack, YowStackBuilder
from yowsup.layers.network import YowNetworkLayer


class whatsappinterface(ABC):
    @abstractmethod
    def sendMessage(self, to, message):
        pass


class WhatsappLayer(YowInterfaceLayer, whatsappinterface):

    def __init__(self):
        super(WhatsappLayer, self).__init__()
        YowInterfaceLayer.__init__(self)
        self.channel = None
        logger.debug("WhatsappLayer initialized!")

    
    def __init__(self, channel: BaseChannel):
        super(WhatsappLayer, self).__init__()
        YowInterfaceLayer.__init__(self)
        self.channel: BaseChannel = channel 
        logger.debug("WhatsappLayer initialized with channel!") 

    @ProtocolEntityCallback("message")
    def onMessage(self, messageProtocolEntity: TextMessageProtocolEntity):
        try:
            #send receipt otherwise we keep receiving the same message over and over
            sender = messageProtocolEntity.getFrom()
            content = messageProtocolEntity.getBody()
            msg_id = messageProtocolEntity.getId()

            # Extract data from request
            im_name = 'whatsapp'
            sender = 'whatsapp:' + sender
            logger.debug(f"whatsapp Received message from {sender}: {content}")

            text = ''
            action = ''
            if content.startswith('+') or content.startswith('+'):
                action = 'store'
                text = content[1:]
            elif content.startswith('?') or content.startswith('？'):
                action = 'retrieve'
                text =content[1:]
            else:
                action = 'respond'
                text = content

            request = PromptRequest(
                request_id= msg_id,
                channel_name= self.metadata.name,
                request_metadata={'sender': sender, 'msg_id': msg_id, 'channel': 'whatsapp'},
                channelType=ChannelType.IM.value,
                user_name= sender,
                app_id= im_name,
                user_id= sender, # The wechaty will return like wechat:shileipeng
                contentType=ContentType.TEXT.value,
                text= text,
                action=action,
                host= self.metadata.host,
                port= self.metadata.port,
                images=[],
                videos=[],
                audios=[],
                timestamp= datetime.now().timestamp()
            )

            # Call handle_message with the extracted data
            if self.channel is not None:
                self.channel.syncTransferTocore(request=request)

        except Exception as e:
            logger.exception(e)
            return {"message": "System Internal Error", "response": "Sorry, something went wrong. Please try again later."}         

        logger.debug("Start to send receipt back to sender!")
        receipt = OutgoingReceiptProtocolEntity(messageProtocolEntity.getId(), 
                                                messageProtocolEntity.getFrom(), 'read', messageProtocolEntity.getParticipant())
        self.toLower(receipt)

    
    @ProtocolEntityCallback("receipt")
    def onReceipt(self, entity):
        ack = OutgoingAckProtocolEntity(entity.getId(), "receipt", entity.getType(), entity.getFrom())
        self.toLower(ack)


    def sendMessage(self, to, message):
        outgoingMessageProtocolEntity = TextMessageProtocolEntity(
            message,
            to = to)
        self.toLower(outgoingMessageProtocolEntity)



@asynccontextmanager
async def lifespan(app: FastAPI):
    #await register_with_core()
    logger.debug("whatsapp Channel lifespan started!")
    yield
    logger.debug("whatsapp Channel lifespan end!")
    try:
        # Do some deinitialization
        pass
    except:
        pass

channel_app: FastAPI = FastAPI(lifespan=lifespan)  


class whatsappRequest(BaseModel):
    im_name: str
    sender: str
    message: str
    msg_id: str

credentials = ("18618486218", "Eficode232410@") # replace with your phone and password
class Channel(BaseChannel):
    def __init__(self, metadata: ChannelMetadata):
        super().__init__(metadata=metadata, app=channel_app)

        self.message_queue = asyncio.Queue()
        self.whatsapp_task = None
        self.message_queue_task = None
        self.whatsapp_layer: WhatsappLayer = None
        self.stackBuilder = YowStackBuilder() 
        self.stack: YowStack = self.stackBuilder\
            .pushDefaultLayers()\
            .push(WhatsappLayer(self))\
            .build()
        self.stack.setCredentials(credentials)

    async def run_bot_async(self):
        logger.debug("Starting whatsapp bot...")
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as pool:
            await loop.run_in_executor(pool, self.run_bot)    

    def run_bot(self):
        logger.debug("Run whatsapp bot...")
        self.stack.broadcastEvent(YowNetworkLayer.EVENT_STATE_CONNECT)

        try:
            self.stack.loop()
        except Exception as e:
            logger.exception(e)
        

    async def process_message_queue(self):
        while True:
            try: 
                response: AsyncResponse = await self.message_queue.get()
                logger.debug(f"Got response: {response} from message queue")
                """Handle the response from the core"""
                request_id = response.request_id
                response_data = response.response_data
                to = response.request_metadata['sender']
                if 'text' in response_data:
                    text = response_data['text']
                    logger.debug(f"sending text: {text} to {to}")   
                    try:
                        self.whatsapp_layer.sendMessage(to, text)
                    except asyncio.TimeoutError:
                        logger.error(f"Timeout sending message to whatsapp user {to}")
                    except Exception as e:
                        logger.error(f"Error sending message: {str(e)}")
                    

                self.message_queue.task_done()
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error processing whatsapp message queue: {str(e)}")



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
        logger.debug("whatsapp Channel initializing...")
        self.bot_task = asyncio.create_task(self.run_bot_async())
        self.message_queue_task = asyncio.create_task(self.process_message_queue())
        super().initialize()
        


    def stop(self):
        # do some deinitialization here
        super().stop()
        self.bot_task.cancel()
        self.message_queue_task.cancel()
        logger.debug("Whatsapp Channel is stopping!")
        
        
    async def handle_async_response(self, response: AsyncResponse):
        logger.debug(f"Put response: {response} into message queue")
        await self.message_queue.put(response)        
        
          
async def main():
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.yml')
    with open(config_path, 'r', encoding='utf-8') as file:
        config = yaml.safe_load(file)
        metadata = ChannelMetadata(**config)
    
    with Channel(metadata=metadata) as channel:
        try:
            await channel.run()
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        except Exception as e:
            logger.exception(f"An error occurred: {e}")
        finally:
            channel.stop()
            


if __name__ == "__main__":
    asyncio.run(main())

