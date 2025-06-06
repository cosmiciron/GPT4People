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
from base.base import User


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
    embedding_llm = core_config['embedding_llm']
    
    llm_options = list(llm_config['llms'].keys())
    
    return (name, host, port, mode, main_llm, embedding_llm, llm_options)


def update_core_config(host, port, mode, main_llm, embedding_llm):
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


    def initialize(self):
        pass


    def register_channel(self, name, host, port, endpoints):
       pass

    def deregister_channel(self, name, host, port, endpoints):
       pass

    def stop(self):
        logger.debug("local channel is stopping!")
        try:
            if self.server is not None:
                #asyncio.run(Util().stop_uvicorn_server(self.server))
                Util().stop_uvicorn_server(self.server)
        except Exception as e:
            logger.debug(e)
        

def run_core() ->threading.Thread:
    thread = threading.Thread(target=core.main, daemon=True)
    thread.start()
    return thread

def reset_memory():
    Util().clear_data()

def start():
    '''
    has_user = True
    if not account_exists():
        has_user = register_user()
    if not has_user:
        print("Account registration failed. Please try again or contact support.(账户注册失败，请重试或联系支持)\n")
        return
    gpt4people_account = Util().get_email_account()
    email = gpt4people_account.email_user
    password = gpt4people_account.email_pass
    print(f"Your GPT4People account(你的GPT4People账号): {email}\n Password(密码): {password}\n")
    '''
    llm_thread = run_core()
    # Running start_core in a background thread
    print("Starting GPT4People..., please wait... (启动GPT4People..., 请稍等...)\n")
    embedding_llm_health = Util().check_embedding_model_server_health()
    main_llm_health = Util().check_main_model_server_health()
    if not embedding_llm_health or not main_llm_health:
        print("Main LLM or embedding LLM is not available. Please check the server status.(主大模型或嵌入大模型不可用，请检查服务器状态)\n")
        return
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
        print('\n')
        if user_input == '' or user_input is None:    
            continue
        user_input = user_input.lower().strip()
        if user_input == '':
            continue
        if user_input == 'quit':
            flag = False
            break
        elif user_input == '':
            continue

        elif user_input == 'llm':
            available_llms = Util().available_llms()
            ollama_llms = Util().get_ollama_supported_models()
            i = 1
            for llm in available_llms:
                print(f"{i}. {llm}\n")
                i += 1

            for llm in ollama_llms:
                print(f"{i}. ollama/{llm}\n")
                i += 1
                
            _, name, type, host, port = Util().main_llm()
            if type == 'local':
                print(f"Current LLM: {name}\n")
            else:
                print(f"You are using cloud LLM: {name}\n")
            continue
        elif user_input == 'llm cloud':
            print("################################################################################################################################\n")
            print("Availabe cloud LLM services:(可用的云大模型服务):\n")
            print("1. OpenAI\n")
            print("2. Anthropic\n")
            print("3. xAI\n")
            print("4. Cohere\n")
            print("5. Together AI\n")
            print("6. Google Gemini\n")
            print("7. Mistral AI\n")
            print("8. Deepseek\n")
            print("9. GroqCloud\n")
            print("################################################################################################################################\n")
            cloud_llm_index = int(input("Enter the index of the LLM you want to set(输入你要设置的LLM的序号): "))
            if cloud_llm_index < 1 or cloud_llm_index > 9:
                print("Invalid input. Cancel.(输入无效，退出)\n")
                continue
            model_name = ""
            api_key_name = ""
            api_key_value = ""
            if cloud_llm_index == 1:
                # Logic for OpenAI
                model_name = input("Enter the model name (like gpt-4o) of OpenAI(输入你要设置的OpenAI模型名字) : ")
                model_name = "openai/" + model_name.strip()
                api_key_name = "OPENAI_API_KEY"
                api_key_value = input("Enter the OpenAI API key(输入OpenAI的API密钥): ")
            elif cloud_llm_index == 2:
                # Logic for Anthropic
                model_name = input("Enter the model name (like claude-3-sonnet-20240229) of Anthropic(输入你要设置的Anthropic模型名字) : ")
                model_name = "anthropic/" + model_name.strip()
                api_key_name = "ANTHROPIC_API_KEY"
                api_key_value = input("Enter the Anthropic API key(输入Anthropic的API密钥): ")
            elif cloud_llm_index == 3:
                # Logic for xAI
                model_name = input("Enter the model name (like grok-3-mini-beta) of xAI(输入你要设置的xAI模型名字) : ")
                model_name = "xai/" + model_name.strip()
                api_key_name = "XAI_API_KEY"
                api_key_value = input("Enter the xAI API key(输入Anthropic的API密钥): ")
            elif cloud_llm_index == 4:
                # Logic for VertexAI
                model_name = input("Enter the model name (like command-r) of Cohere(输入你要设置的Cohere模型名字) : ")
                model_name =  model_name.strip()
                api_key_name = "COHERE_API_KEY"
                api_key_value = input("Enter the Cohere API key(输入Cohere的API密钥): ")
            elif cloud_llm_index == 5:
                # Logic for Together AI
                model_name = input("Enter the model name (like 'togethercomputer/Llama-2-7B-32K-Instruct') of Together AI(输入你要设置的Together AI模型名字) : ")
                model_name = "together_ai/" + model_name.strip()
                api_key_name = "TOGETHERAI_API_KEY"
                api_key_value = input("Enter the Together AI API key(输入Together AI的API密钥): ")
            elif cloud_llm_index == 6:
                # Logic for Google
                model_name = input("Enter the model name (like 'gemini-1.5-pro') of Google Gemini(输入你要设置的Google Gemini模型名字) : ")
                model_name = "gemini/" + model_name.strip()
                api_key_name = "GEMINI_API_KEY"
                api_key_value = input("Enter the Google Gemini API key(输入Google Gemini的API密钥): ")
            elif cloud_llm_index == 7:
                # Logic for Mistral AI
                model_name = input("Enter the model name (like 'mistral-small-latest') of Mistral AI(输入你要设置的Mistral AI模型名字) : ")
                model_name = "mistral/" + model_name.strip()
                api_key_name = "MISTRAL_API_KEY"
                api_key_value = input("Enter the Mistral AI API key(输入Mistral AI的API密钥): ")
            elif cloud_llm_index == 8:
                # Logic for Openrouter
                model_name = input("Enter the model name (like 'deepseek-chat') of Deepseek(输入你要设置的Deepseek模型名字) : ")
                model_name = "deepseek/" + model_name.strip()
                api_key_name = "DEEPSEEK_API_KEY"
                #sk-3c8a08bc438244988cacffd1c41513d7
                api_key_value = input("Enter the Deepseek API key(输入Deepseek的API密钥): ")
            elif cloud_llm_index == 9:
                model_name = input("Enter the model name (like 'llama3-8b-8192') of GroqCloud(输入你要设置的GroqCloud模型名字) : ")
                model_name = "groq/" + model_name.strip()
                api_key_name = "GROQ_API_KEY"
                api_key_value = input("Enter the GroqCloud API key(输入GroqCloud的API密钥): ")
            else:
                # Default case if needed
                continue           

            Util().set_mainllm(model_name, type='litellm', api_key_name=api_key_name, api_key=api_key_value)
            print(f"Cloud LLM set to（云端大模型设置为）: {model_name}\n")
            print('Restart the app to use new cloud LLM.(重启应用以使用新的云端大模型)\n')
            break
        elif user_input == 'llm set':
            available_llms = Util().available_llms()
            ollama_llms = Util().get_ollama_supported_models()
            i = 1
            for llm in available_llms:
                print(f"{i}. {llm}\n")
                i += 1

            for llm in ollama_llms:
                print(f"{i}. ollama/{llm}\n")
                i += 1

            _, name, type, host, port = Util().main_llm()
            if type == 'local':
                print(f"Current LLM: {name}\n")
            else:
                print(f"You are using cloud LLM: {name}\n")
            llm_index = int(input("Enter the index of the LLM you want to set(输入你要设置的LLM的序号): "))
            if llm_index < 1 or llm_index > (len(available_llms) + len(ollama_llms)):
                print("Invalid input. Cancel.(输入无效，退出)\n")
                continue
            if llm_index <= len(available_llms):
                if name != available_llms[llm_index - 1]:
                    name = available_llms[llm_index - 1]
                    Util().set_mainllm(name, type='local')
                    print(f"LLM set to（大模型设置为）: {name}\n")
                    print('Restart the app to use new LLM.(重启应用以使用新的大模型)\n')
                    break
                else:
                    print("Current LLM is already set.(当前大模型已设置)\n")
                    continue
            else:
                if name != 'ollama/' + ollama_llms[llm_index - len(available_llms) - 1]:
                    name = 'ollama/' + ollama_llms[llm_index - len(available_llms) - 1]
                    Util().set_mainllm(name, type='litellm')
                    print(f"LLM set to（大模型设置为）: {name}\n")
                    print('Restart the app to use new LLM.(重启应用以使用新的大模型)\n')
                    break 
                else: 
                    print("Current LLM is already set.(当前大模型已设置)\n")
                    continue 
        elif user_input == 'llm download':  
            available_llms = Util().available_llms()
            ollama_llms = Util().get_ollama_supported_models()
            i = 1            
            for llm in available_llms:
                print(f"{i}. {llm}\n")    
                i += 1

            for llm in ollama_llms:     
                print(f"{i}. ollama/{llm}\n")
                i += 1

            _, name, type, host, port = Util().main_llm()
            print(f"Current LLM: {name}\n")
            model = input("Enter the name of the LLM you want to pull from Ollama(输入从Ollama下载的LLM的名称): ")
            if model in ollama_llms:
                print("{model} is already downloaded.(模型已下载)\n")
                continue                 
            else:
                print(f"Pulling {model} from Ollama... (从Ollama下载{model}...)")
                resp = Util().pull_model_from_ollama(model)
                print(resp)
                continue
        elif  user_input == 'channel':
            print('################################################################################################################################\n')
            print("How to use wechat channel: \n")
            print("Step 1: Install and login the specific wechat version on PC and login using one wechat account, then run wechat_channel app.\n")
            print("Step 2: Using 'wechat user' to define who can talk with your GPT4People.\n\n")
            print("如何使用微信连接GPT4People: \n")           
            print("Step 1: 安装并登录指定的微信版本并登录一个微信账号, 然后运行'wechat_channel' 程序。\n")
            print("Step 2: 输入'wechat user'来定义可以和你的 GPT4People 机器人交流的微信用户。\n")
            print('################################################################################################################################\n\n')

            print('################################################################################################################################\n')
            print("How to use whatsapp channel: \n")
            print("Step 1: Run whatsapp_channel app, then scan the QR code to login using one whatsapp account.\n")
            print("Step 2: Using 'whatsapp user' to define who can talk with your GPT4People.\n\n")
            print("如何使用 WhatsApp 连接 GPT4People: \n")
            print("Step 1: 运行'whatsapp_channel' 程序，然后扫描二维码登录使用一个 WhatsApp 账号。\n")
            print("Step 2: 输入'whatsapp user'来定义可以和你的 GPT4People 机器人交流的 WhatsApp 用户。\n")
            print('################################################################################################################################\n\n')

            print('################################################################################################################################\n')
            print("How to use email channel: \n")
            print("Step 1: Send email to your GPT4People account directly.\n")
            print("Step 2: Using 'email user' to define who can talk with your GPT4People .\n\n")
            print("如何使用 Email 连接 GPT4People: \n")
            print("Step 1: 直接发送邮件到你的 GPT4People 账户。\n")
            print("Step 2: 输入'email user'来定义可以和你的 GPT4People 机器人交流的 Email 用户。\n")
            print('################################################################################################################################\n\n')

            print('################################################################################################################################\n')
            print("How to use matrix channel: \n")
            print("Step 1: Run matrix_channel app, then input the required credentials.\n")
            print("Step 2: Using 'matrix user' to define who can talk with your GPT4People.\n\n")
            print("如何使用 Matrix 连接 GPT4People: \n")
            print("Step 1: 运行'matrix_channel' 程序，然后输入所需的服务器地址以及用户名密码。\n")
            print("Step 2: 输入'matrix user'来定义可以和你的 GPT4People 机器人交流的 Matrix 用户。\n\n")
            print('################################################################################################################################\n\n')
            continue

        elif user_input == 'wechat user':
            user: User = Util().get_first_user()
            if user is None:
                print("No user found. Please add a default user first.(找不到用户，请先添加一个默认用户)")
                continue
            print("Please input the wechat account accessing GPT4People(请输入微信账号, 用来访问GPT4People)\n")
            wechat_account = input("Enter the wechat account accessing GPT4People(输入微信账号, 用来访问GPT4People): ")
            im =  'wechat:' + wechat_account
            Util().add_im_to_user(user.name, im)

            continue
        elif user_input == 'whatsapp user':
            user: User = Util().get_first_user()
            if user is None:
                print("No user found. Please add a default user first.(找不到用户，请先添加一个默认用户)")
                continue
            whatsapp_account = input("Enter the whatsapp account accessing GPT4People(输入whatsapp账号, 用来访问GPT4People): ")
            im =  'whatsapp:' + whatsapp_account
            Util().add_im_to_user(user.name, im)
            continue
        elif user_input == 'matrix user':
            user: User = Util().get_first_user()
            if user is None:
                print("No user found. Please add a default user first.(找不到用户，请先添加一个默认用户)")
                continue
            matrix_account = input("Enter the matrix account accessing GPT4People(输入matrix账号, 用来访问GPT4People): ")
            im =  'matrix:' + matrix_account
            Util().add_im_to_user(user.name, im)
            continue
        elif user_input == 'email user':
            user: User = Util().get_first_user()
            if user is None:
                print("No user found. Please add a default user first.(找不到用户，请先添加一个默认用户)")
                continue
            emailaddress = input("Enter the email address accessing GPT4People(输入email地址, 用来访问GPT4People): ")
            im =  'matrix:' + emailaddress
            Util().add_email_to_user(user.name, emailaddress)
            continue

        elif user_input == 'wechat remove':
            user: User = Util().get_first_user()
            if user is None:
                print("No user found. Please add a default user first.(找不到用户，请先添加一个默认用户)")
                continue
            print("Please input the wechat account for removing (请输入微信账号, 用来删除)\n")
            wechat_account = input("Enter the wechat number for removing(输入微信账号, 用来删除): ")
            im =  'wechat:' + wechat_account
            Util().remove_im_from_user(user.name, im)

            continue     
        elif user_input == 'whatsapp remove':
            user: User = Util().get_first_user()
            if user is None:
                print("No user found. Please add a default user first.(找不到用户，请先添加一个默认用户)")
                continue
            print("Please input the whatsapp account for removing (请输入whatsapp账号, 用来删除)\n")
            whatsapp_account = input("Enter the whatsapp number for removing(输入whatsapp账号, 用来删除): ")
            im =  'whatsapp:' + whatsapp_account
            Util().remove_im_from_user(user.name, im)

            continue
        elif user_input == 'matrix remove':
            user: User = Util().get_first_user()
            if user is None:
                print("No user found. Please add a default user first.(找不到用户，请先添加一个默认用户)")
                continue
            print("Please input the matrix account for removing (请输入matrix账号, 用来删除)\n")
            matrix_account = input("Enter the matrix number for removing(输入matrix账号, 用来删除): ")
            im =  'matrix:' + matrix_account
            Util().remove_im_from_user(user.name, im)

            continue
        elif user_input == 'email remove':
            user: User = Util().get_first_user()
            if user is None:
                print("No user found. Please add a default user first.(找不到用户，请先添加一个默认用户)")
                continue
            emailaddress = input("Enter the email address for removing(输入email地址, 用来删除): ")
            Util().remove_email_from_user(user.name, emailaddress)
            continue
        elif user_input == 'wechat list':
            user: User = Util().get_first_user()
            if user is None:
                print("No user found. Please add a default user first.(找不到用户，请先添加一个默认用户)")
                continue
            for im in user.im:
                im_head = im.split(":")[0]
                if im_head == 'wechat':
                    result = im.split(":")[1]
                    print(result)
                    print('\n')

            continue     
        elif user_input == 'whatsapp list':
            user: User = Util().get_first_user()
            if user is None:
                print("No user found. Please add a default user first.(找不到用户，请先添加一个默认用户)")
                continue

            for im in user.im:
                im_head = im.split(":")[0]
                if im_head == 'whatsapp':
                    result = im.split(":")[1]
                    print(result)
                    print('\n')

            continue 
        elif user_input == 'matrix list':
            user: User = Util().get_first_user()
            if user is None:
                print("No user found. Please add a default user first.(找不到用户，请先添加一个默认用户)")
                continue

            for im in user.im:
                im_head = im.split(":")[0]
                if im_head == 'matrix':
                    result = im.split(":")[1]
                    print(result)
                    print('\n')

            continue
        elif user_input == 'email list':
            user: User = Util().get_first_user()
            if user is None:
                print("No user found. Please add a default user first.(找不到用户，请先添加一个默认用户)")
                continue

            for email in user.email:
                print(email)
                print('\n')
            continue
        elif user_input == 'reset':
            print("It will reset the conversation history and all the history data will be lost... (将重置对话历史，所有历史数据将丢失...)\n")
            print("Are you sure you want to reset? (你确定要重置吗?)\n")
            confirm = input("Enter 'CONFIRM' to confirm or any other string to cancel(输入'CONFIRM'确认或其他任意字符串取消): ")
            if confirm == 'CONFIRM':
                Util().reset_memory()
                flag = False
            continue
        else:
            resp = asyncio.run(channel.on_message(user_input)) #channel.on_message(user_input)
            print("GPT4People:", resp)
            if comment:
                print("\nContinue chatting or Type 'quit' to exit. (继续聊天或输入'quit'退出)")
                comment = False
    url = channel.core_url() + "/shutdown"
    httpx.get(url)
    sys.exit(0)

if __name__ == "__main__":
    try:
        start()
    except Exception as e:
        sys.exit(0)
