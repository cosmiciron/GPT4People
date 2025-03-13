from asyncio import subprocess
import os
import asyncio
from pathlib import Path
from subprocess import PIPE, Popen
import platform
import sys
import threading
from time import sleep
from typing import Dict, List
import torch
import uvicorn
import signal
from loguru import logger  # Ensure you import the logger appropriately

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import base
from base.util import Util
from base.base import LLM, Server
#from llm.llamaCppPython import LlamaCppPython
#from llm.litellmService import LiteLLMService

class LLMServiceManager:
    
    _instance = None
    _lock = threading.Lock() 

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(LLMServiceManager, cls).__new__(cls, *args, **kwargs)
        return cls._instance
        
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.initialized = True
            self.llama_cpp_processes = []
            self.apps: List[asyncio.Task] = []
            self.llms: List[LLM] = []
            #self.llm_to_app: Dict[str, asyncio.Task] = {}
            self.gather_task: asyncio.Task = None
        
        
    def start_llama_cpp_process(self, cmd: str, name:str, host:str, port:str):
        """
        Start an LLM process asynchronously and record its details.
        """
        try:
            process = Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            #process = await asyncio.to_thread(Popen, cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            # shell=True is not necessary here, as we're passing the command as a list of strings.
            # This is safer, as it prevents shell injection attacks.
            
            self.llama_cpp_processes.append({
                'name': name,
                'process': process,
                'host': host,
                'port': port,
            })
            logger.debug(f"Started LLM process on {host}:{port} with PID {process.pid}")
            return process
        except Exception as e:
            logger.error(f"Failed to start LLM process on {host}:{port}: {e}")
            return None


    def stop_llama_cpp_process(self, name:str):
        """
        Stop a specific LLM process asynchronously.
        """
        try:
            for process_info in self.llama_cpp_processes:
                if process_info['name'] == name:
                    process_info['process'].terminate()
                    #await asyncio.to_thread(process_info['process'].wait)
                    self.llama_cpp_processes.remove(process_info)
                    logger.debug(f"Stopped LLM process on {process_info['host']}:{process_info['port']}")
                    return
        except Exception as e:
            logger.error(f"Failed to stop LLM process on {process_info['host']}:{process_info['port']}: {e}")


    def stop_all_llama_cpp_processes(self):
        """
        Stop all LLM processes asynchronously.
        """
        (self.stop_llama_cpp_process(process_info['name']) for process_info in self.llama_cpp_processes)
        self.llama_cpp_processes = []


    def get_llama_cpp_processes(self):
        """
        Get the list of all running LLM processes.
        """
        return self.llama_cpp_processes
    
    
    def get_llama_cpp_process_names(self):
        """
        Get the list of names of all running LLM processes.
        """
        return [process_info['name'] for process_info in self.llama_cpp_processes]


    def start_llama_cpp_server(self, name:str, host:str, port:int, model_path:str, 
                                     ctx_size:str = '2048', predict:str = '1024', temp:str = '0.7', 
                                     threads:str = '8', n_gpu_layers:str = '99', 
                                     chat_format:str = None, verbose:str = 'false', pooling:bool = False):
        logger.debug(f"model path {model_path}")
        model_sub_path = os.path.normpath(model_path)
        model_path = os.path.join(Util().models_path(), model_sub_path)
        logger.debug(f"Full model path: {model_path}")
        llama_cpp_args = "-m " + model_path
        if verbose != 'false' and verbose != 'False':
            llama_cpp_args += " --verbose "
        llama_cpp_args += " --ctx-size " + ctx_size
        llama_cpp_args += " --predict " + predict
        llama_cpp_args += " --temp " + temp
        llama_cpp_args += " --threads " + threads
        llama_cpp_args += " --host " + host
        llama_cpp_args += " --port " + str(port)
        if pooling:
            llama_cpp_args += " --embedding"
            llama_cpp_args += " --pooling cls -ub 8192"
            logger.debug("Pooling is enabled.")
        if chat_format:
            llama_cpp_args += " --chat_format " + chat_format

        root_path = Util().root_path()
        llama_cpp_path = os.path.join(root_path, 'llama.cpp-master')
        if platform.system() == "Windows":
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            if device.type == 'cuda':
                llama_cpp_args += " --n-gpu-layers 99"
                #cmd = "..\\llama.cpp-master\\win_cuda\\llama-server.exe" + " " + llama_cpp_args
                cmd = os.path.join(llama_cpp_path, "win_cuda", "llama-server.exe") + " " + llama_cpp_args
                logger.debug("LLama.cpp is Running on GPU, cmd: " + cmd)
            else:
                #cmd = "..\\llama.cpp-master\\win_cpu\\llama-server.exe" + " " + llama_cpp_args
                cmd = os.path.join(llama_cpp_path, "win_cpu", "llama-server.exe") + " " + llama_cpp_args
                logger.debug("LLama.cpp is Running on CPU, cmd: " + cmd)
        else:
            cmd = os.path.join(llama_cpp_path, "mac_arm_cpu", "llama-server") + " " + llama_cpp_args
            logger.debug("LLama.cpp is Running on Mac Arm CPU, cmd: " + cmd)

        try:
            process = self.start_llama_cpp_process(cmd, name, host, port)
            logger.debug("LLama.cpp is Running on " + host + ":" + str(port)
                         + "\nwith model \n" +  os.path.basename(model_path))
            #_, stderr = await asyncio.to_thread(process.communicate)
            #logger.debug("llama-server exited with code " + str(process.returncode))
            #if process.returncode != 0:
            #    logger.debug(f"llama-server failed with code {process.returncode}, stderr: {stderr.decode()}")
        except asyncio.CancelledError:
            logger.debug("Shutting down the daemon.")
        except Exception as e:
            logger.debug(f"An error occurred: {e}")
            
 
    def run_llama_cpp_llm(self, name: str, ctx_size:str = '2048', predict:str = '1024', temp:str = '0.7', 
                                     threads:str = '8', n_gpu_layers:str = '99', 
                                     chat_format:str = None, verbose:str = 'false', pooling:bool = False):
        try:
            llm = Util().get_llm(name)
            name = llm.name
            host = llm.host
            port = llm.port
            path = llm.path
            
            if llm in self.llms:
                logger.debug(f"LLM {name} is already running")
                return
            
            # Initialize and start the Uvicorn server for the LLM service
            #server_task = asyncio.create_task(self.start_llama_cpp_server(name, host, port, path, ctx_size=ctx_size, predict=predict, temp=temp,
            #                        threads=threads, n_gpu_layers=n_gpu_layers, chat_format=chat_format, verbose=verbose, pooling=pooling))
            #self.apps.append(server_task)
            #self.llm_to_app[name] = server_task
            self.start_llama_cpp_server(name, host, port, path, ctx_size=ctx_size, predict=predict, temp=temp,
                                    threads=threads, n_gpu_layers=n_gpu_layers, chat_format=chat_format, verbose=verbose, pooling=pooling)
            self.llms.append(llm)      
            #self.apps.append(self.start_llama_cpp_server(name, host, port, path))
            logger.debug(f"Running LLM Server {path} on {host}:{port}")
        except asyncio.CancelledError:
            logger.debug("LLM from llama.cpp was cancelled.")
            # Handle any cleanup if necessary
        
            
    def run_main_llm(self, ctx_size:str = '2048', predict:str = '1024', temp:str = '0.7', 
                                     threads:str = '8', n_gpu_layers:str = '99', 
                                     chat_format:str = None, verbose:str = 'false'):
        llm = self.main_llm()
        type = llm.type
        name = llm.name
        ret = None
        if type == 'local':       
            self.run_llama_cpp_llm(name, ctx_size=ctx_size, predict=predict, temp=temp,
                                threads=threads, n_gpu_layers=n_gpu_layers, chat_format=chat_format, verbose=verbose)
        #elif type == 'litellm':
        #    ret = self.run_litellm_service(name)
            
    '''       
    async def start_llama_cpp_python(self, host, port, model_path, 
                                     chat_format='chatml-function-calling', 
                                     embedding=False, verbose=False, n_gpu_layers=99, n_ctx=2048):
        # Initialize the LLM service
        llm_service = LlamaCppPython()
        llm_service.initialize_llm(model_path, chat_format=chat_format, 
                                   embedding=embedding, verbose=verbose, n_gpu_layers=n_gpu_layers, n_ctx=n_ctx)

        # Run the FastAPI app
        if host == '127.0.0.1' or host == 'localhost':
            host = '0.0.0.0'
        config = uvicorn.Config(llm_service.app, host=host, port=port, log_level="info")
        server = Server(config)
        logger.debug(f"Running Llama.cpp.python on {host}:{port}, model is {model_path}")
        try:
            await server.serve()
            logger.debug("LLM from llama.cpp.python server done.")
        except asyncio.CancelledError:
            logger.debug("LLM from llama.cpp.python was cancelled.")
    '''    
    '''  
    def run_llama_cpp_python_llm(self, name: str, chat_format='chatml-function-calling', 
                                     embedding=False, verbose=False, n_gpu_layers=99, n_ctx=2048):
        try:
            llm = Util().get_llm(name)
            name = llm.name
            host = llm.host
            port = llm.port
            path = llm.path
            
            if llm in self.llms:
                logger.debug(f"LLM {name} is already running")
                return None
            
            # Initialize and start the Uvicorn server for the LLM service
            server_task = asyncio.create_task(self.start_llama_cpp_python(host, port, path,chat_format=chat_format, 
                                    embedding=embedding, verbose=verbose, n_gpu_layers=n_gpu_layers, n_ctx=n_ctx))
            #self.apps.append(server_task)
            self.llm_to_app[name] = server_task
            self.llms.append(llm)
            #self.apps.append(self.start_llama_cpp_server(name, host, port, path))
            logger.debug(f"Running LLM Server {path} on {host}:{port}")
            return server_task
        except asyncio.CancelledError:
            logger.debug("LLM from llama.cpp.python was cancelled.")
            # Handle any cleanup if necessary
    '''    
    '''   
    async def start_litellm_service(self, host, port, model):
        # Initialize the LLM service
        litellm_service = LiteLLMService()

        # Run the FastAPI app
        if host == '127.0.0.1' or host == 'localhost':
            host = '0.0.0.0'
        config = uvicorn.Config(litellm_service.app, host=host, port=port, log_level="info")
        server = Server(config)
        logger.debug(f"Running litellm on {host}:{port}, model is {model}")
        try:
            await server.serve()
        except asyncio.CancelledError:
            logger.debug("LLM from liteLLM was cancelled.")

        
        
    def run_litellm_service(self, name: str):
        try:
            llm = Util().get_llm(name)
            type = llm.type
            if type != 'litellm':
                logger.debug(f"LLM {name} is not a litellm")
                return None
            name = llm.name
            host = llm.host
            port = llm.port
            model = llm.path
            
            if llm in self.llms:
                logger.debug(f"LLM {name} is already running")
                return None
            
            # Initialize and start the Uvicorn server for the LLM service
            server_task = asyncio.create_task(self.start_litellm_service(host, port, model))
            #self.apps.append(server_task)
            self.llm_to_app[name] = server_task
            self.llms.append(llm)
            logger.debug(f"Running litellm Service {model} on {host}:{port}")
            return server_task
        except asyncio.CancelledError:
            logger.debug("LLM from litellm service was cancelled.")
    '''
            
    '''
    def run_memory_llm(self, chat_format='chatml-function-calling', 
                                     embedding=False, verbose=False, n_gpu_layers=99, n_ctx=2048):
        try:
            llm = self.memory_llm()
            name = llm.name
            host = llm.host
            port = llm.port
            model_path = llm.path
            ret = self.run_llama_cpp_python_llm(name, chat_format=chat_format, embedding=embedding, verbose=verbose, n_gpu_layers=n_gpu_layers, n_ctx=n_ctx)
            logger.debug(f"Memory LLM services running on {host}:{port} with {model_path}!")
            return ret
        except asyncio.CancelledError:
            logger.debug("LLM for memory cancelled.") 
    '''

    def run_memory_llm_cpp(self, ctx_size:str = '2048', predict:str = '1024', temp:str = '0.7', 
                                     threads:str = '8', n_gpu_layers:str = '99', 
                                     chat_format:str = None, verbose:str = 'false'):
        llm = self.memory_llm()
        name = llm.name
        host = llm.host
        port = llm.port
        model_path = llm.path
        ret =  None       
        if type == 'local':       
            self.run_llama_cpp_llm(name, ctx_size=ctx_size, predict=predict, temp=temp,
                                    threads=threads, n_gpu_layers=n_gpu_layers, chat_format=chat_format, verbose=verbose)
        #elif type == 'litellm':
        #    ret = self.run_litellm_service(name)
        logger.debug(f"Memory LLM services running on {host}:{port} with {model_path}!")   


    def run_embedding_llm(self, ctx_size:str = '4096', predict:str = '1024', temp:str = '0.7', 
                                     threads:str = '8', n_gpu_layers:str = '99', 
                                     chat_format:str = None, verbose:str = 'false'):
        try:
            llm = self.embedding_llm()
            name = llm.name
            self.run_llama_cpp_llm(name, ctx_size=ctx_size, predict=predict, temp=temp,
                                threads=threads, n_gpu_layers=n_gpu_layers, chat_format=chat_format, verbose=verbose, pooling=True)
            logger.debug("Embedding services added!")
        except asyncio.CancelledError:
            logger.debug("LLM for embeddingwas cancelled.")


    def main_llm(self):
        return Util().main_llm()

    def memory_llm(self):
        return Util().memory_llm()

    def embedding_llm(self):
        return Util().embedding_llm()
    
    
    async def add_and_start_new_app(self, app):
        logger.debug("Adding app.")
        if not asyncio.iscoroutinefunction(app) and not isinstance(app, asyncio.Task):
            raise ValueError("App must be a coroutine function or asyncio.Task")

        if asyncio.iscoroutinefunction(app):
            task = asyncio.create_task(app())
        elif isinstance(app, asyncio.Task):
            task = app
        else:
            raise ValueError("Invalid app type")

        self.apps.append(task)
        
        try:
            result = await task
            logger.debug(f"New app completed with result: {result}")
        except asyncio.CancelledError:
            logger.debug(f"New app cancelled successfully.")
        except Exception as e:
            logger.error(f"Exception in new app: {e}")
            
  
    async def start_all_apps(self):
        #await asyncio.gather(*self.apps)
        #for app in self.apps:
        try:
            logger.debug("Starting all apps.")
            if len(self.apps) > 0:
                self.gather_task = asyncio.gather(*self.apps, return_exceptions=True)
                await self.gather_task
    
        except asyncio.CancelledError:
            logger.debug("Gathering task was cancelled.")
        except Exception as e:
            logger.exception(e)
   
            
    # if you run some LLMs after the start_all_apps(), you can call this function
    # This function will gather self.apps again
    async def restart_all_apps(self):
        try:
            logger.debug("Restarting all apps.")
            # Cancel the current gather task
            if self.gather_task and not self.gather_task.done():
                self.gather_task.cancel()
            
            #start all the apps again
            await self.start_all_apps()
        except asyncio.CancelledError:
            logger.debug("All the apps were cancelled.")
        except Exception as e:
            logger.error(f"Unexpected error in restart_all_apps: {e}")
        
    
    def stop_all_apps(self):
        """
        Stop all running apps.
        """
        try:
            logger.debug("LLM Service Stopping all apps...")
            if len(self.apps) == 0:
                return
            for app in self.apps:
                app.cancel()
            self.apps = []
            # Because all the apps are in unicorn server, when Ctrl + C is pressed, it will exit all the apps.
            logger.debug("All apps have been stopped.")
        except asyncio.CancelledError:
            logger.debug("All the apps were cancelled.")
        except Exception as e:
            logger.error(f"Unexpected error in stop_all_apps: {e}")
     
        
    def exit_gracefully(self, signum, frame):
        try:
            logger.debug("LLM Service CTRL+C received, shutting down...")
            # End the main thread
            #asyncio.run(self.stop_all_llama_cpp_processes())
            self.stop_all_llama_cpp_processes()
            self.stop_all_apps()
            sys.exit(0)
        except asyncio.CancelledError:
            logger.debug("All the apps were cancelled.")
        except Exception as e:
            logger.error(f"Unexpected error in stop_all_apps: {e}")
        
    
    def __enter__(self):
        if threading.current_thread() == threading.main_thread():
            try:
                #logger.debug("channel initializing..., register the ctrl+c signal handler")
                signal.signal(signal.SIGINT, self.exit_gracefully)
                signal.signal(signal.SIGTERM, self.exit_gracefully)
            except Exception as e:
                # It's a good practice to at least log the exception
                # logger.error(f"Error setting signal handlers: {e}")
                pass

        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass
        
    # This funciton is for testing    
    def run(self):
        try:
            self.run_main_llm()
            #self.run_memory_llm()
            self.run_memory_llm_cpp()
            self.run_embedding_llm()
            
            #await self.start_all_apps()
            
            #await self.restart_all_apps()
            # Wait for the server to finish
        except Exception as e:
            logger.exception(f"Unexpected error in run: {e}")

            
    
if __name__ == "__main__":   
    try:
        llm_manager = LLMServiceManager()
        llm_manager.run()
        #asyncio.run(llm_manager.run())
    except KeyboardInterrupt:
        logger.debug("Ctrl+C received, shutting down...")
        # End the main thread
        llm_manager.stop_all_llama_cpp_processes()
        #llm_manager.stop_all_apps()
    except Exception as e:
        logger.exception(e)