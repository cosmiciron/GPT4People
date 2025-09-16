"""Python implementation of a Tinode chatbot."""

# For compatibility between python 2 and 3
from __future__ import print_function
import asyncio
from pathlib import Path
import argparse
import base64
from concurrent import futures
from datetime import datetime
import json
import os
import threading
import httpx
import pkg_resources
import platform
try:
    import Queue as queue
except ImportError:
    import queue
import random
import signal
import sys
import time

import grpc
from google.protobuf.json_format import MessageToDict

# Import generated grpc modules
from tinode_grpc import pb
from tinode_grpc import pbx
from pydub import AudioSegment
from pydub.playback import play

# Import for Channel
from contextlib import asynccontextmanager
from fastapi import FastAPI
from loguru import logger
from pydantic import BaseModel
from dotenv import dotenv_values
import yaml
from os import getenv
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from base.util import Util
from base.BaseChannel import ChannelMetadata, BaseChannel
from base.base import PromptRequest, AsyncResponse, ChannelType, ContentType

channel_app: FastAPI = FastAPI() 

# For compatibility with python2
if sys.version_info[0] >= 3:
    unicode = str

APP_NAME = "Tinode GPT4People Channel"
APP_VERSION = "1.2.2"
LIB_VERSION = pkg_resources.get_distribution("tinode_grpc").version


# User ID of the current user
botUID = None

# Dictionary which contains lambdas to be executed when server response is received
onCompletion = {}

# This is needed for gRPC ssl to work correctly.
os.environ["GRPC_SSL_CIPHER_SUITES"] = "HIGH+ECDSA"


class Plugin(pbx.PluginServicer):
    def Account(self, acc_event, context):
        action = None
        if acc_event.action == pb.CREATE:
            action = "created"
            # TODO: subscribe to the new user.

        elif acc_event.action == pb.UPDATE:
            action = "updated"
        elif acc_event.action == pb.DELETE:
            action = "deleted"
        else:
            action = "unknown"

        #log("Account", action, ":", acc_event.user_id, acc_event.public)
        logger.debug(f"Account {action}: {acc_event.user_id} {acc_event.public}")

        return pb.Unused()
    
    
class Channel(BaseChannel):
    def __init__(self, metadata: ChannelMetadata):
        super().__init__(metadata=metadata, app=channel_app)

        self.message_queue = asyncio.Queue()
        self.message_queue_task = None
        self.chats = {}
        
        # Tinode variables
        self.subscriptions = {}
        self.queue_out = queue.Queue()
        self.tid = 100
        self.tinode_server = None
        self.tinode_client = None


    # def handle_message(self, client: NewClient, message: MessageEv):
    #     try:
    #         #send receipt otherwise we keep receiving the same message over and over
    #         content = message.Message.conversation or message.Message.extendedTextMessage.text
    #         sender = message.Info.MessageSource.Sender.User
    #         msg_id = message.Info.ID
    #         chat = message.Info.MessageSource.Chat
    #         self.chats[msg_id] =  chat

    #         # Extract data from request
    #         im_name = 'whatsapp'
    #         sender = 'whatsapp:' + sender
    #         logger.debug(f"whatsapp Received message from {sender}: {content}")

    #         text = ''
    #         action = ''
    #         if content.startswith('+') or content.startswith('+'):
    #             action = 'store'
    #             text = content[1:]
    #         elif content.startswith('?') or content.startswith('？'):
    #             action = 'retrieve'
    #             text =content[1:]
    #         else:
    #             action = 'respond'
    #             text = content

    #         request = PromptRequest(
    #             request_id= msg_id,
    #             channel_name= self.metadata.name,
    #             request_metadata={'sender': sender, 'msg_id': msg_id, 'channel': 'whatsapp'},
    #             channelType=ChannelType.IM.value,
    #             user_name= sender,
    #             app_id= im_name,
    #             user_id= sender, # The wechaty will return like wechat:shileipeng
    #             contentType=ContentType.TEXT.value,
    #             text= text,
    #             action=action,
    #             host= self.metadata.host,
    #             port= self.metadata.port,
    #             images=[],
    #             videos=[],
    #             audios=[],
    #             timestamp= datetime.now().timestamp()
    #         )

    #         # Call handle_message with the extracted data
    #         self.syncTransferTocore(request=request)

    #     except Exception as e:
    #         logger.exception(e)
    #         return {"message": "System Internal Error", "response": "Sorry, something went wrong. Please try again later."}         
    


    async def process_message_queue(self):
        while True:
            try: 
                global client
                response: AsyncResponse = await self.message_queue.get()
                logger.debug(f"Got response: {response} from message queue")
                """Handle the response from the core"""
                request_id = response.request_id
                response_data = response.response_data
                to = response.request_metadata['sender']
                msg_id = response.request_metadata['msg_id']
                if 'text' in response_data:
                    text = response_data['text']
                    logger.debug(f"sending text: {text} to {to}") 
                    chat = self.chats.pop(msg_id)  
                    try:
                        client.send_message(chat, text)
                    except asyncio.TimeoutError:
                        logger.error(f"Timeout sending message to whatsapp user {to}")
                    except Exception as e:
                        logger.error(f"Error sending message: {str(e)}")
                    

                self.message_queue.task_done()
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error processing whatsapp message queue: {str(e)}")


    def initialize(self):
        logger.debug("Tinode Channel initializing...")
        self.message_queue_task = asyncio.create_task(self.process_message_queue())
        super().initialize()
        


    def stop(self):
        # do some deinitialization here
        super().stop()
        self.message_queue_task.cancel()
        logger.debug("Tinode Channel is stopping!")
        
        
    async def handle_async_response(self, response: AsyncResponse):
        logger.debug(f"Put response: {response} into message queue")
        await self.message_queue.put(response) 


    # Add bundle for future execution
    def add_future(self, tid, bundle):
        onCompletion[tid] = bundle

    def to_json(self, msg):
        return json.dumps(self.clip_long_string(MessageToDict(msg)))

    # Resolve or reject the future
    def exec_future(self, tid, code, text, params):
        bundle = onCompletion.get(tid)
        if bundle != None:
            del onCompletion[tid]
            try:
                if code >= 200 and code < 400:
                    arg = bundle.get('arg')
                    bundle.get('onsuccess')(arg, params)
                else:
                    logger.debug("Error: {} {} ({})".format(code, text, tid))
                    onerror = bundle.get('onerror')
                    if onerror:
                        onerror(bundle.get('arg'), {'code': code, 'text': text})
            except Exception as err:
                logger.debug("Error handling server response", err)

    # List of active subscriptions
    
    def add_subscription(self, topic):
        self.subscriptions[topic] = True

    def del_subscription(self,topic):
        self.subscriptions.pop(topic, None)

    def subscription_failed(self, topic, errcode):
        if topic == 'me':
            # Failed 'me' subscription means the bot is disfunctional.
            if errcode.get('code') == 502:
                # Cluster unreachable. Break the loop and retry in a few seconds.
                self.client_post(None)
            else:
                exit(1)

    def login_error(unused, errcode):
        # Check for 409 "already authenticated".
        if errcode.get('code') != 409:
            exit(1)

    def server_version(self, params):
        if params == None:
            return
        logger.debug("Server:", params['build'].decode('ascii'), params['ver'].decode('ascii'))

    def next_id(self):
        self.tid += 1
        return str(self.tid)
    

    def client_generate(self):
        while True:
            msg = self.queue_out.get()
            if msg == None:
                return
            logger.debug("out:", self.to_json(msg))
            yield msg

    def client_post(self, msg):
        self.queue_out.put(msg)

    def client_reset(self):
        # Drain the queue
        try:
            while self.queue_out.get(False) != None:
                pass
        except queue.Empty:
            pass

    def hello(self):
        tid = self.next_id()
        self.add_future(tid, {
            'onsuccess': lambda unused, params: self.server_version(params),
        })
        return pb.ClientMsg(hi=pb.ClientHi(id=tid, user_agent=APP_NAME + "/" + APP_VERSION + " (" +
            platform.system() + "/" + platform.release() + "); gRPC-python/" + LIB_VERSION,
            ver=LIB_VERSION, lang="EN"))

    def login(self, cookie_file_name, scheme, secret):
        tid = self.next_id()
        self.add_future(tid, {
            'arg': cookie_file_name,
            'onsuccess': lambda fname, params: self.on_login(fname, params),
            'onerror': lambda unused, errcode: self.login_error(unused, errcode),
        })
        return pb.ClientMsg(login=pb.ClientLogin(id=tid, scheme=scheme, secret=secret))

    def subscribe(self, topic):
        tid = self.next_id()
        self.add_future(tid, {
            'arg': topic,
            'onsuccess': lambda topicName, unused: self.add_subscription(topicName),
            'onerror': lambda topicName, errcode: self.subscription_failed(topicName, errcode),
        })
        return pb.ClientMsg(sub=pb.ClientSub(id=tid, topic=topic))

    def leave(self, topic):
        tid = self.next_id()
        self.add_future(tid, {
            'arg': topic,
            'onsuccess': lambda topicName, unused: self.del_subscription(topicName)
        })
        return pb.ClientMsg(leave=pb.ClientLeave(id=tid, topic=topic))

    def publish(self, topic, text):
        tid = self.next_id()
        return pb.ClientMsg(pub=pb.ClientPub(id=tid, topic=topic, no_echo=True,
            head={"auto": json.dumps(True).encode('utf-8')}, content=json.dumps(text).encode('utf-8')))

    def note_read(self, topic, seq):
        return pb.ClientMsg(note=pb.ClientNote(topic=topic, what=pb.READ, seq_id=seq))

    def init_server(self, listen):
        # Launch plugin server: accept connection(s) from the Tinode server.
        self.tinode_server = grpc.server(futures.ThreadPoolExecutor(max_workers=16))
        pbx.add_PluginServicer_to_server(Plugin(), self.tinode_server )
        self.tinode_server.add_insecure_port(listen)
        self.tinode_server.start()

        logger.debug("Plugin server running at '"+listen+"'")

    def init_client(self, addr, schema, secret, cookie_file_name, secure, ssl_host):
        
        logger.debug(f"Connecting to {addr}, {schema}, {secret}, {cookie_file_name}, {secure}, {ssl_host}")

        grpc_channel = None
        if secure:
            opts = (('grpc.ssl_target_name_override', ssl_host),) if ssl_host else None
            grpc_channel = grpc.secure_channel(addr, grpc.ssl_channel_credentials(), opts)
        else:
            grpc_channel = grpc.insecure_channel(addr)

        # Call the server
        self.tinode_client = pbx.NodeStub(grpc_channel).MessageLoop(self.client_generate())

        # Session initialization sequence: {hi}, {login}, {sub topic='me'}
        self.client_post(self.hello())
        self.client_post(self.login(cookie_file_name, schema, secret))


    def client_message_loop(self):
        try:
            # Read server responses
            for msg in self.tinode_client:

                if msg.HasField("ctrl"):
                    # Run code on command completion
                    self.exec_future(msg.ctrl.id, msg.ctrl.code, msg.ctrl.text, msg.ctrl.params)

                elif msg.HasField("data"):
                    logger.debug("Message Data:", msg.data)
                    logger.debug("message from:", msg.data.from_user_id)
                    
                    encoded_content = msg.data.content
                    # If encoded_content is bytes, decode it to get the string representation
                    if isinstance(encoded_content, bytes):
                        encoded_content = encoded_content.decode('utf-8')

                    data_type = 'text'
                    subtype = ''
                    content_dict = None
                    # Parse the JSON string into a Python dictionary
                    try:
                        # Attempt to parse the JSON string
                        content_dict = json.loads(encoded_content)
                        
                        # Access the MIME type
                        mime_type = content_dict["ent"][0]["data"]["mime"]
                        parts = mime_type.split('/')
                        data_type = parts[0]
                        subtype = parts[1] if len(parts) > 1 else None
                    except Exception as err:
                        # Handle the case where it's not JSON
                        data_type = 'text'
                        subtype = ''
                    

                    # Protection against the bot talking to self from another session.
                    if msg.data.from_user_id != botUID:
                        # Respond to message.
                        # Mark received message as read
                        self.client_post(self.note_read(msg.data.topic, msg.data.seq_id))
                        # Insert a small delay to prevent accidental DoS self-attack.
                        time.sleep(0.1)
                        # Respond with a witty quote
                        if data_type == 'text':
                            encoded_content = msg.data.content
                            if encoded_content is bytes:
                                encoded_content = encoded_content.decode('utf-8')
                            logger.debug("Message content:", encoded_content)
                            self.client_post(self.publish(msg.data.topic, encoded_content.decode('utf-8')))
                        elif data_type == 'image':
                            # TODO: Respond with image
                            pass
                        elif data_type == 'audio':
                            # TODO: Respond with audio
                            audio_bytes = base64.b64decode(content_dict['ent'][0]['data']['val'])
                            filename = 'output' + '.' + subtype
                            with open(filename, 'wb') as f:
                                f.write(audio_bytes)
                                
                            self.client_post(self.publish(msg.data.topic, 'Audio file received'))
                            audio = AudioSegment.from_file(filename, format=subtype)
                            # Play the audio file
                            play(audio)
                        else:
                            # TODO: Respond with unknown data type
                            pass

                elif msg.HasField("pres"):
                    # log("presence:", msg.pres.topic, msg.pres.what)
                    # Wait for peers to appear online and subscribe to their topics
                    if msg.pres.topic == 'me':
                        if (msg.pres.what == pb.ServerPres.ON or msg.pres.what == pb.ServerPres.MSG) \
                                and self.subscriptions.get(msg.pres.src) == None:
                            self.lient_post(self.subscribe(msg.pres.src))
                        elif msg.pres.what == pb.ServerPres.OFF and self.subscriptions.get(msg.pres.src) != None:
                            self.client_post(self.leave(msg.pres.src))

                else:
                    # Ignore everything else
                    pass
            return True        
        except grpc._channel._Rendezvous as err:
            logger.debug("Disconnected:", err)
            return False

    def read_auth_cookie(self, cookie_file_name):
        """Read authentication token from a file"""
        cookie = open(cookie_file_name, 'r')
        params = json.load(cookie)
        cookie.close()
        schema = params.get("schema")
        secret = None
        if schema == None:
            return None, None
        if schema == 'token':
            secret = base64.b64decode(params.get('secret').encode('utf-8'))
        else:
            secret = params.get('secret').encode('utf-8')
        return schema, secret

    def on_login(self, cookie_file_name, params):
        global botUID
        self.client_post(self.subscribe('me'))

        """Save authentication token to file"""
        if params == None or cookie_file_name == None:
            return

        if 'user' in params:
            botUID = params['user'].decode("ascii")[1:-1]

        # Protobuf map 'params' is not a python object or dictionary. Convert it.
        nice = {'schema': 'token'}
        for key_in in params:
            if key_in == 'token':
                key_out = 'secret'
            else:
                key_out = key_in
            nice[key_out] = json.loads(params[key_in].decode('utf-8'))

        try:
            cookie = open(cookie_file_name, 'w')
            json.dump(nice, cookie)
            cookie.close()
        except Exception as err:
            logger.debug(f"Failed to save authentication cookie: {err}")


    def work_loop(self):
        schema = None
        secret = None
        
        purpose = "GPT4People - Tinode Channel."
        parser = argparse.ArgumentParser(description=purpose)
        parser.add_argument('--host', default='200.69.21.246:16060', help='address of Tinode server gRPC endpoint')
        parser.add_argument('--ssl', action='store_true', help='use SSL to connect to the server')
        parser.add_argument('--ssl-host', help='SSL host name to use instead of default (useful for connecting to localhost)')
        parser.add_argument('--listen', default='127.0.0.1:40051', help='address to listen on for incoming Plugin API calls')
        parser.add_argument('--login-basic', default='gpt4people_pengshilei:232410', help='login using basic authentication username:password')
        parser.add_argument('--login-token', help='login using token authentication')
        parser.add_argument('--login-cookie', default='.tn-cookie', help='read credentials from the provided cookie file')
        
        args = parser.parse_args()
        
        logger.debug(f"Work Loop Args: {args}")

        if args.login_token:
            """Use token to login"""
            schema = 'token'
            secret = args.login_token.encode('ascii')
            logger.debug(f"Logging in with token: {args.login_token}")

        elif args.login_basic:
            """Use username:password"""
            schema = 'basic'
            secret = args.login_basic.encode('utf-8')
            logger.debug(f"Logging in with login:password, {secret}")

        else:
            """Try reading the cookie file"""
            try:
                schema, secret = self.read_auth_cookie(args.login_cookie)
                logger.debug(f"Logging in with cookie file: {args.login_cookie}")
            except Exception as err:
                logger.debug(f"Failed to read authentication cookie {err}")
                sys.exit(1)

        if schema:
            # Start Plugin server
            self.init_server(args.listen)

            # Initialize and launch client
            self.init_client(args.host, schema, secret, args.login_cookie, args.ssl, args.ssl_host)

            # Setup closure for graceful termination
            # def exit_gracefully(signo, stack_frame):
            #     logger.debug("Terminated with signal", signo)
            #     server.stop(0)
            #     client.cancel()
            #     sys.exit(0)

            # # Add signal handlers
            # signal.signal(signal.SIGINT, exit_gracefully)
            # signal.signal(signal.SIGTERM, exit_gracefully)

            # Run blocking message loop in a cycle to handle
            # server being down.
            while True:
                ret = self.client_message_loop()
                time.sleep(3)
                if ret:
                    continue
                else:
                    self.client_reset()
                    self.init_client(args.host, schema, secret, args.login_cookie, args.ssl, args.ssl_host)

            # Close connections gracefully before exiting
            self.tinode_server.stop(None)
            self.tinode_client.cancel()

        else:
            logger.debug("Error: authentication scheme not defined")  
            
    def stop(self):
        super().stop()
        self.tinode_server.stop(None)
        self.tinode_client.cancel()
        
                        
shutdown_url = ""
def main():
    random.seed()

    try:
        root = Util().channels_path()
        config_path = os.path.join(root, 'tinode', 'config.yml')
        with open(config_path, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
            metadata = ChannelMetadata(**config)
            global shutdown_url
            host = metadata.host
            if host == '0.0.0.0':
                host = '127.0.0.1'
            shutdown_url = "http://" + host + ":" + str(metadata.port) + "/shutdown"

        with Channel(metadata=metadata) as channel:
            channel.work_loop()
            #work_loop_thread = threading.Thread(target=channel.work_loop)
            #work_loop_thread.start()
            
            #asyncio.run(channel.run())
    except Exception as e:
        logger.exception(e)
        
def suicide():
    try:
        global shutdown_url
        httpx.get(shutdown_url)
    except Exception as e:
        logger.exception(e)


if __name__ == '__main__':
    """Parse command-line arguments. Extract server host name, listen address, authentication scheme"""
    main()

