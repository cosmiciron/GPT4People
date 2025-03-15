import asyncio
from datetime import datetime
from multiprocessing import Process
import os
import re
import runpy
import signal
import subprocess
import sys
import threading
from time import sleep
from fastapi import FastAPI
import httpx
from loguru import logger
import requests
import argparse

import yaml

from base.BaseChannel import BaseChannel, ChannelMetadata
from base.base import AsyncResponse, ChannelType, ContentType, PromptRequest
from base.util import Util
from core import core
from channels.wechat import channel as wechat
from channels.whatsapp import channel as whatsapp
from channels.matrix import channel as matrix


path = os.path.join(Util().root_path(), 'config')
core_config_file_path = os.path.join(path, 'core.yml')
llm_config_file_path = os.path.join(path, 'llm.yml')
user_config_file_path = os.path.join(path, 'user.yml')

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
        #logger.debug(f"Account exists: {email}")
        return True
    else:
        #logger.debug("Account does not exist")
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
        #logger.debug(f"Response code: {response.status_code} - {response.text}")
        if response.status_code == 200:
            #logger.debug(f"Sending verification code to {email}")
            return True, "Verification code sent to your email.(验证码已发送到你的邮箱)"
        else:
            # Handle different response codes accordingly
            return False,  "Failed to send verification code.(发送验证码失败)"
    except Exception as e:
        #logger.debug(f"An error occurred: {e}")
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
            #logger.debug(f"Account created for ) {response.json()['user']['email']}, {response.json()['user']['password']}")

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



    def core_url(self) -> str | None:
        core_url = super().core_url()
        if core_url is not None:
            return core_url
        # Read the core host and port from .env file in each helper folder
        return "http://127.0.0.1:9000"


    def initialize(self):
        super().initialize()


    def stop(self, register=True):
        # do some deinitialization here
        super().stop()
        

def run_core() ->threading.Thread:
    thread = threading.Thread(target=core.main, daemon=True)
    thread.start()
    return thread

wechat_flag = False
def run_wechat_channel() -> threading.Thread:
    global wechat_flag
    wechat_flag = True
    thread = threading.Thread(target=wechat.main)
    thread.start()    
    return thread    

def shutdown_wechat_channel():
    global wechat_flag
    if wechat_flag:
        wechat.suicide()
        wechat_flag = False

whatsapp_flag = False
def run_whatsapp_channel() -> threading.Thread:
    global whatsapp_flag
    whatsapp_flag = True
    thread = threading.Thread(target=whatsapp.main)
    thread.start()    
    return thread

def shutdown_whatsapp_channel():
    global whatsapp_flag
    if whatsapp_flag:
        whatsapp.suicide()
        whatsapp_flag = False

matrix_flag = False
def run_matrix_channel() -> threading.Thread:
    global matrix_flag
    matrix_flag = True
    thread = threading.Thread(target=matrix.main)
    thread.start()    
    return thread  

def shutdown_matrix_channel():
    global matrix_flag
    if matrix_flag:
        matrix.suicide()
        matrix_flag = False 

def start():
    if not account_exists():
        register_user()
    gpt4people_account = Util().get_gpt4people_account()
    email = gpt4people_account.email_user
    password = gpt4people_account.email_pass
    print(f"Your GPT4People account(你的GPT4People账号): {email}\n Password(密码): {password}\n")

    # Running start_core in a background thread
    print("Starting GPT4People Core...\n")
    llm_thread = run_core()

    channel_metadata = ChannelMetadata(name="gpt4people", host="localhost", port=0, endpoints=[])
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
        elif user_input == '':
            continue
            '''
            elif  user_input.lower() == 'channel':
                print("WeChat Channel: Install and login the specific wechat version, then input 'channel wechat' here.\n")
                print("微信频道: 安装并登录指定的微信版本, 然后在这里输入'channel wechat'。\n")
                print("Whatsapp Channel: Input 'channel whatsapp' here, then scan the QR code to login using one whatsapp account.\n")
                print("WhatsApp 频道: 输入'channel whatsapp', 然后扫描二维码登录使用一个 WhatsApp 账号。\n")
                print("Email Channel: Send email to your GPT4People account directly.\n")
                print("Email 频道: 直接发送邮件到你的 GPT4People 账户。\n")
                print("Matrix Channel: Input 'channel matrix' here.\n")
                print("Matrix 频道: 输入'channel matrix'。\n")
                continue
            elif user_input.lower() == 'channel wechat':
                wechat_thread = run_wechat_channel()
                continue
            elif user_input.lower() == 'channel whatsapp':
                whatsapp_thread = run_whatsapp_channel()
                continue
            elif user_input.lower() == 'channel matrix':
                matrix_thread = run_matrix_channel()
                continue'
            '''
        else:
            resp = asyncio.run(channel.on_message(user_input)) #channel.on_message(user_input)
            print("GPT4People:", resp)
            if comment:
                print("\nContinue chatting or Type 'quit' to exit. (继续聊天或输入'quit'退出)")
                comment = False
    url = channel.core_url() + "/shutdown"
    httpx.get(url)
    #shutdown_wechat_channel()
    #shutdown_whatsapp_channel()
    #shutdown_matrix_channel()
    sys.exit(0)

if __name__ == "__main__":
    try:
        start()
    except Exception as e:
        sys.exit(0)
