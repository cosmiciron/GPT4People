import asyncio
from datetime import datetime
import os
import re
import subprocess
import sys
import threading
from time import sleep
from fastapi import FastAPI
from loguru import logger
import requests
import argparse

import yaml

from base.BaseChannel import BaseChannel, ChannelMetadata
from base.base import AsyncResponse, ChannelType, ContentType, PromptRequest
from base.util import Util

BASE_URL = "http://localhost:8000"  # Assuming your BaseChannel app runs here


path = os.path.join(Util().root_path(), 'config')
core_config_file_path = os.path.join(path, 'core.yml')
llm_config_file_path = os.path.join(path, 'llm.yml')
user_config_file_path = os.path.join(path, 'user.yml')
llm_process: subprocess.Popen = None

def read_config(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        config = yaml.safe_load(file)
    return config

def write_config(file_path, config):
    with open(file_path, 'w', encoding='utf-8') as file:
        yaml.safe_dump(config, file, default_flow_style=False, sort_keys=False)
        
def get_core_config():
    core_config = read_config(core_config_file_path)
    llm_config = read_config(llm_config_file_path)
    
    name = core_config['name']
    host = core_config['host']
    port = core_config['port']
    mode = core_config['mode']
    main_llm = core_config['main_llm']
    memory_llm = core_config['memory_llm']
    embedding_llm = core_config['embedding_llm']
    
    llm_options = list(llm_config['llms'].keys())
    
    return (name, host, port, mode, main_llm, memory_llm, embedding_llm, llm_options)


def update_core_config(host, port, mode, main_llm, memory_llm, embedding_llm):
    core_config = read_config(core_config_file_path)  # Read the existing config to preserve the name field
    name = core_config['name']
    model_path = core_config['model_path']
    vectorDB = core_config['vectorDB']
    endpoints = core_config['endpoints']
    core_config.update({
        'name': name,
        'host': host,
        'port': port,
        'mode': mode,
        'model_path': model_path,
        'main_llm': main_llm,
        'memory_llm': memory_llm,
        'embedding_llm': embedding_llm,
        'vectorDB': vectorDB,
        'endpoints': endpoints
    })
    write_config(core_config_file_path, core_config)
    return "Configuration updated successfully!"


def account_exists():
    # Implement logic to check for an existing account
    # Return True if account exists, False otherwise
    gpt4people_account = Util().get_gpt4people_account()
    email = gpt4people_account.email_user
    password = gpt4people_account.email_pass
    if email and len(email) > 0 and password and len(password) > 0:
        logger.debug(f"Account exists: {email}")
        return True
    else:
        logger.debug("Account does not exist")
        return False

def register_user():
    email_inputted = False
    email = None
    verified_email = None
    while not email_inputted:
        email = input("Enter your email address for receiving verification code(输入一个有效的邮件地址，用来接收验证码):\n")
        if not is_valid_email(email):
            print("Invalid email format. Please enter a valid email address.(输入一个有效的邮件地址，用来接收验证码)\n")
            continue
        verified_email = input("Enter your email address again for verification(再次输入你的邮件地址): ")
        if email != verified_email:
            print("Emails do not match. Please try again.(两次输入的邮件地址不一致，请重新输入)")
            continue

        email_inputted = True

    ret, text = send_verification_code(email)
    if not ret:
        print(text)
        return False
    print(text)
    for i in range(3):
        code = input("Enter the verification code you received(输入你收到的验证码): ")
        print("Verifying(验证)...")
        ret, text = create_account(email, code)
        if not ret:
            print("Verification failed. Please try again.(验证失败，请重试)")
            continue
        print(text)
        return True


# Function to check email format
def is_valid_email(email_addr):
    # Simple regex for validating an email address
    regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    if re.fullmatch(regex, email_addr):
        return True
    else:
        return False

def send_verification_code(email):
    # First, verify the email format
    if not is_valid_email(email):
        return False, "Invalid email format. Please enter a valid email address.(输入一个有效的邮件地址，用来接收验证码)"
    
    # URL of the API endpoint
    url = "http://mail.gpt4people.ai:3000/send_verification"
    
    # Data to be sent in the request
    data = {
        'email': email
    }
    
    # Headers, if required (e.g., API keys, Content-Type)
    headers = {
        'Content-Type': 'application/json'
    }
    
    try:
        # Sending a POST request to the endpoint
        response = requests.post(url, json=data, headers=headers)
        logger.debug(f"Response code: {response.status_code} - {response.text}")
        if response.status_code == 200:
            logger.debug(f"Sending verification code to {email}")
            return True, "Verification code sent to your email.(验证码已发送到你的邮箱)"
        else:
            # Handle different response codes accordingly
            return False,  "Failed to send verification code.(发送验证码失败)"
    except Exception as e:
        logger.debug(f"An error occurred: {e}")
        return False, "An error occurred while sending the verification code.(发送验证码时发生错误)"

def create_account(email, code):
    # URL of the API endpoint
    url = "http://mail.gpt4people.ai:3000/create_user"
    
    # Data to be sent in the request, using the provided email and code
    data = {
        "email": email,
        "verificationCode": code
    }
    
    # Headers specifying that the request body is JSON
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        # Sending a POST request to the endpoint
        response = requests.post(url, json=data, headers=headers)
        
        # Check the response status code to determine if the request was successful
        if response.status_code == 200 or response.status_code == 201:
            # Assuming a successful response code means the account was created successfully
            logger.debug(f"Account created for ) {response.json()['user']['email']}, {response.json()['user']['password']}")

            gpt4people_account = Util().get_gpt4people_account()
            gpt4people_account.email_user = response.json()['user']['email']
            gpt4people_account.email_pass = response.json()['user']['password']
            Util().gpt4people_account = gpt4people_account
            Util().save_gpt4people_account()
            return True, "Account created successfully. Welcome to GPT4People!（账户创建成功，欢迎使用GPT4People！）"
        else:
            # If the response code is not 200, assume verification failed
            return False, "Verification failed. Please try again.（验证失败，请重试）"
    except Exception as e:
        # Catch any exceptions that occur during the request and report them
        return False, f"An error occurred(发生错误): {e}"


channel_app: FastAPI = FastAPI() 
class Channel(BaseChannel):
    def __init__(self, metadata: ChannelMetadata):
        super().__init__(metadata=metadata, app=channel_app)

        self.message_queue = asyncio.Queue()
        self.message_queue_task = None

    async def on_message(self, message: str) -> str | None:
        try:
            # Extract data from request
            im_name = 'gpt4people'
            sender = 'gpt4people:' + 'local'
            content = message
            msg_id: str =  str(datetime.now().timestamp())
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
                request_metadata={'sender': sender, 'msg_id': msg_id, 'channel': 'gpt4people'},
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
            resp = await self.localChatWithcore(request=request)
            return resp
        except Exception as e:
            logger.exception(e)
            return None

        

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



    def core(self) -> str | None:
        core_url = super().core()
        if core_url is not None:
            return core_url
        # Read the core host and port from .env file in each helper folder
        return "http://127.0.0.1:9000"


    def initialize(self):
        logger.debug("GPT4People Channel initializing...")
        # Start processing the message queue
        self.message_queue_task = asyncio.create_task(self.process_message_queue())
        super().initialize()


    def stop(self):
        # do some deinitialization here
        super().stop()
        # Implement proper shutdown logic here
        self.message_queue_task.cancel()
        logger.debug("GPT4People Channel is stopping!")
        
        
    async def handle_async_response(self, response: AsyncResponse):
        logger.debug(f"Put response: {response} into message queue")
        await self.message_queue.put(response)        
        
def start_core():
    root = Util().root_path()
    core_path = os.path.join(root, 'core', 'core.py')
    logger.debug("Starting GPT4People Core...\n")
    global llm_process
    llm_process = subprocess.Popen(["python", core_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

async def main():
    # If we want to add some  parameters,  we can use the following code.

    # parser = argparse.ArgumentParser(description="CLI Chat Tool")
    # parser.add_argument('--register', action='store_true', help='Register a new user')
    # parser.add_argument('--login', action='store_true', help='Login an existing user')
    # parser.add_argument('--chat', action='store_true', help='Start a chat session')

    # args = parser.parse_args()

    # if args.register:
    #    register_user()
    # elif args.login:
    #    login_user()
    # elif args.chat:
    #    chat()
    # else:
    #    parser.print_help()
    if not account_exists():
        register_user()
    global llm_process
    gpt4people_account = Util().get_gpt4people_account()
    email = gpt4people_account.email_user
    password = gpt4people_account.email_pass
    print(f"Your GPT4People account(你的GPT4People账号): {email}\n Password(密码): {password}\n")

    #start_core()
    # Running start_core in a background thread
    thread = threading.Thread(target=start_core)
    thread.start()
    channel_metadata = ChannelMetadata(name="gpt4people", host="", port=0, endpoints=[])
    sleep(30)
    with Channel(metadata=channel_metadata) as channel:
        try:
            channel.initialize()
        except Exception as e:
            logger.exception(f"An error occurred: {e}")
    flag = True
    comment = True
    while flag:
        user_input = input("You: ")
        if user_input.lower() == 'quit':
            flag = False
            break
        resp = await channel.on_message(user_input)
        print("GPT4People:", resp)
        if comment:
            print("\nContinue chatting or Type 'quit' to exit. (继续聊天或输入'quit'退出)")
            comment = False
    
    if llm_process is None:
        logger.debug("llm process is None!")
    llm_process.terminate()
    llm_process.wait()
    sleep(5)

    # Optionally, check if process needs to be killed (forcefully stopped)
    if llm_process.poll() is None:  # Process has not exited yet
        logger.debug("Not terminated, Killing llm process...")
        llm_process.kill()  # Forcefully terminate the process
    else:
        logger.debug("llm process is terminated!")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        sys.exit(0)
