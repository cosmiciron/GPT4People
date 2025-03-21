import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
import os
import sys
from pathlib import Path
import threading
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI
from loguru import logger
from pydantic import BaseModel
from dotenv import dotenv_values
import yaml
from os import getenv
import simplematrixbotlib as botlib
from nio.rooms import MatrixRoom
from nio.events.room_events import Event

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from base.util import Util
from base.BaseChannel import ChannelMetadata, BaseChannel
from base.base import PromptRequest, AsyncResponse, ChannelType, ContentType



channel_app: FastAPI = FastAPI()  


class MatrixRequest(BaseModel):
    im_name: str
    sender: str
    message: str
    msg_id: str


class Channel(BaseChannel):
    def __init__(self, metadata: ChannelMetadata):
        super().__init__(metadata=metadata, app=channel_app)
        channels_path = Util().root_path() + '/channels/' + 'matrix/'
        env_path = os.path.join(channels_path, '.env')
        env_vars = dotenv_values(env_path)
        home_srv = env_vars['home_server']
        home_srv = home_srv.strip()
        username = env_vars['username']
        username = username.strip()
        password = env_vars['password']
        password = password.strip()
        if home_srv is None or len(home_srv) == 0:
            print("Please enter the home server of Matrix(输入Matrix的主服务器地址): Eg: https://matrix.org \n")
            home_srv = input("Input the home server of Matrix：(输入Matrix的主服务器地址): ")
            print("Please enter the username of Matrix(输入Matrix的用户名): Eg: @allenpeng:matrix.org \n")
            username = input("Input the username of Matrix(输入Matrix的用户名): ")
            print("Please enter the password of Matrix(输入Matrix的密码): Eg: Eficode232410@ \n")
            password = input("Input the password of Matrix(输入Matrix的密码): ")
            with open(env_path, 'w') as f:
                f.write(f"home_server={home_srv}\n")
                f.write(f"username={username}\n")
                f.write(f"password={password}\n")

        self.creds = botlib.Creds(home_srv, username, password)
        self.config = botlib.Config()
        #self.config.encryption_enabled = True
        self.config.ignore_unverified_devices = True

        self.bot = botlib.Bot(creds=self.creds, config=self.config)
        self.PREFIX = '!'
        self.message_queue = asyncio.Queue()
        self.bot_task = None
        self.message_queue_task = None

    # def core_url(self) -> str | None:
    #     """Get the core url from sub class's .env file"""
    #     channels_path = Util().root_path() + '/channels/'
    #     env_path = os.path.join(channels_path, '.env')
    #     env_vars = dotenv_values(env_path)
    #     core_url = None
    #     if 'core_host' in env_vars and 'core_port' in env_vars:
    #         host = env_vars['core_host']
    #         port = env_vars['core_port']
    #         core_url = f"http://{host}:{port}"
    #     else:
    #         core_url = None
    #     return core_url


    async def run_bot(self):
        @self.bot.listener.on_message_event
        async def on_message(room: MatrixRoom, message: Event):
            try:
                match = botlib.MessageMatch(room, message, self.bot, self.PREFIX)
                logger.debug(f'room: {room.name}')
                logger.debug(f"received message {message.sender} {message.source['content']['body']}")
                # Extract data from request
                im_name = 'matrix'
                sender = 'matrix:' + message.sender
                logger.debug(f"sender: {sender}")
                content = message.source['content']['body']
                msg_id =  message.event_id
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
                    request_metadata={'matrix_room_id': room.room_id},
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
                await self.transferTocore(request=request)

            except Exception as e:
                logger.exception(e)
                return {"message": "System Internal Error", "response": "Sorry, something went wrong. Please try again later."}
            
        logger.debug("Matrix Channel is running now")  
        await self.bot.main()
        

    async def process_message_queue(self):
        while True:
            try:
                response: AsyncResponse = await self.message_queue.get()
                logger.debug(f"Got response: {response} from message queue")
                """Handle the response from the core"""
                request_id = response.request_id
                response_data = response.response_data
                room_id = response.request_metadata['matrix_room_id']
                if 'text' in response_data:
                    text = response_data['text']
                    logger.debug(f"sending text: {text} to room {room_id}")   
                    try:
                        await self.bot.api.send_text_message(room_id, text)
                    except asyncio.TimeoutError:
                        logger.error(f"Timeout sending message to room {room_id}")
                    except Exception as e:
                        logger.error(f"Error sending message: {str(e)}")
                    
                if 'image' in response_data:
                    image_path = response_data['image']
                    await self.bot.api.send_image_message(room_id=room_id, image_filepath=image_path)
                if 'video' in response_data:
                    video_path = response_data['video']
                    await self.bot.api.send_video_message(room_id=room_id, video_filepath=video_path)   
                self.message_queue.task_done()
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error processing message queue: {str(e)}")


    def initialize(self):
        logger.debug("Natrix Channel initializing...")
        self.bot_task = asyncio.create_task(self.run_bot())
        # Start processing the message queue
        self.message_queue_task = asyncio.create_task(self.process_message_queue())
        super().initialize()


    def stop(self):
        # do some deinitialization here
        # Implement proper shutdown logic here
        self.bot_task.cancel()
        self.message_queue_task.cancel()
        super().stop()
        logger.debug("Matrix Channel is stopping!")
        
        
    async def handle_async_response(self, response: AsyncResponse):
        logger.debug(f"Put response: {response} into message queue")
        await self.message_queue.put(response)        
        
shutdown_url = ""    
def main():
    root = Util().channels_path()
    config_path = os.path.join(root, 'matrix', 'config.yml')
    with open(config_path, 'r', encoding='utf-8') as file:
        config = yaml.safe_load(file)
        metadata = ChannelMetadata(**config)
        global shutdown_url
        host = metadata.host
        if host == '0.0.0.0':
            host = '127.0.0.1'
        shutdown_url = "http://" + host + ":" + str(metadata.port) + "/shutdown"
    with Channel(metadata=metadata) as channel:
        try:
            asyncio.run(channel.run())
        except KeyboardInterrupt:
            logger.debug("Shutting down...")
        except Exception as e:
            logger.exception(f"An error occurred: {e}")
        finally:
            channel.stop()
        '''
        bot_task = asyncio.create_task(run_bot_in_thread(channel.bot))
        matrix_task = asyncio.create_task(channel.run())
        
        try:
            await asyncio.gather(bot_task, matrix_task)
        except asyncio.CancelledError:
            logger.debug("Tasks were cancelled")
        except Exception as e:
            logger.debug(f"An error occurred: {e}")
        finally:
            # Cancel tasks if they haven't completed
            for task in [bot_task, matrix_task]:
                if not task.done():
                    task.cancel()
            # Wait for tasks to be cancelled
            await asyncio.gather(*[bot_task, matrix_task], return_exceptions=True)    
        '''


def suicide():
    try:
        global shutdown_url
        httpx.get(shutdown_url)
    except Exception as e:
        logger.exception(e)
            

if __name__ == "__main__":
    main()

