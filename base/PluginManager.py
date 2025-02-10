import importlib
from inspect import getmembers, isclass, isfunction, signature
from pathlib import Path
import sys
import threading
import time
import os
from threading import Thread
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from base.BasePlugin import BasePlugin
from base.util import Util
from core.coreInterface import CoreInterface

disable_plugins = True

class PluginManager:
    def __init__(self, coreInst: CoreInterface):
        self.coreInst = coreInst
        self.plugins_dir = Util.plugins_path()
        self.loaded_plugins = {}
        self.plugin_instances: list[BasePlugin] = []
        self.hot_reload_thread = None
        self.stop_hot_reload = threading.Event()
        self.plugin_descriptions = {}


    def register_plugin(self, plugin: BasePlugin):
        if plugin ==  None: 
            return
        logger.debug(f"Registering plugin: {plugin.description}")
        self.plugin_descriptions[plugin.description] = plugin


    def num_plugins(self):
        return len(self.plugin_instances)


    def load_plugins(self):
        if disable_plugins:
            return
        current_plugins = set()
        for folder_name in os.listdir(self.plugins_dir):
            plugin_folder = os.path.join(self.plugins_dir, folder_name)
            if os.path.isdir(plugin_folder):
                for filename in os.listdir(plugin_folder):
                    if filename.endswith('.py') and filename != '__init__.py':
                        module_name = filename[:-3]
                        module_path = f"plugins.{folder_name}.{module_name}"
                        plugin_mod_time = os.path.getmtime(plugin_folder)
                        current_plugins.add(module_path)
                        if (module_path not in self.loaded_plugins or
                                self.loaded_plugins[module_path] < plugin_mod_time):
                            module = importlib.import_module(module_path)
                            for attr_name, attr in getmembers(module, isclass):
                                # Filter out any intermediate base classes and only initialize final subclasses of BasePlugin
                                if issubclass(attr, BasePlugin) and attr is not BasePlugin:
                                    # Ensure we're dealing with the most derived class and not an intermediate class
                                    #if not any(issubclass(cls, attr) and cls is not attr for cls in BasePlugin.__subclasses__()):
                                        # Check if this plugin instance already exists
                                                                            # Skip loading intermediate base classes
                                    if len(attr.__subclasses__()) > 0:
                                        logger.info(f"Skipping intermediate base class: {attr.__name__}")
                                        continue

                                    existing_instance = next((instance for instance in self.plugin_instances if isinstance(instance, attr)), None)
                                    if not existing_instance:
                                        logger.info(f"Loading plugin: {module_path} - {attr_name}")
                                        # Log the [__init__](cci:1://file:///d:/GPT4People/base/PluginManager.py:15:4-19:52) method signature of the class
                                        init_method = attr.__init__
                                        
                                        if isfunction(init_method):
                                            init_signature = signature(init_method)
                                            logger.info(f"__init__ signature for {attr_name}: {init_signature}")
                                        #init_signature = signature(attr.__init__)
                                            if 'coreInst' in init_signature.parameters:
                                                plugin_instance = attr(coreInst=self.coreInst)

                                                if hasattr(plugin_instance, 'initialize'):
                                                    logger.info(f"Calling initialize for plugin: {module_path} - {attr_name}")
                                                    plugin_instance.initialize()
                                                self.plugin_instances.append(plugin_instance)
                                                self.loaded_plugins[module_path] = plugin_mod_time
                                                self.register_plugin(plugin_instance)
                                                logger.info(f"Loaded plugin: {module_path} - {attr_name}")
                                            else:
                                                logger.warning(f"__init__ method for {attr_name} is not a function or not defined")
                                    else:
                                        logger.info(f"Plugin already loaded: {module_path} - {attr_name}")

        # Detect and unload deleted plugins
        to_unload = set(self.loaded_plugins.keys()) - current_plugins
        for module_path in to_unload:
            self.unload_plugin(module_path)
            logger.info(f"Unloaded plugin: {module_path}")


    def unload_plugin(self, module_path):
        if disable_plugins:
            return
        # Find the plugin instance to remove
        plugin_instance = next((plugin for plugin in self.plugin_instances if plugin.__module__ == module_path), None)
        if plugin_instance:
            # Perform any necessary cleanup
            if hasattr(plugin_instance, 'cleanup'):
                plugin_instance.cleanup()
            self.plugin_instances.remove(plugin_instance)
            logger.info(f"Unloaded plugin: {module_path}")
        
        # Remove the plugin module from sys.modules
        if module_path in sys.modules:
            del sys.modules[module_path]
        
        # Remove from loaded plugins
        if module_path in self.loaded_plugins:
            del self.loaded_plugins[module_path]

    def initialize_plugins(self):
        if  disable_plugins:
            return
        for plugin in self.plugin_instances:
            plugin.initialize()

    def run(self):
        if disable_plugins:
            return
        pass

    def hot_reload(self):
        if disable_plugins:
            return
        while not self.stop_hot_reload.is_set():
            self.load_plugins()
            time.sleep(60)  # Adjust the interval as needed

        logger.debug("Hot reload thread stopped.")

    def start_hot_reload(self):
        if disable_plugins:
            return
        self.hot_reload_thread = threading.Thread(target=self.hot_reload)
        self.hot_reload_thread.daemon = True
        self.hot_reload_thread.start()


    def deinitialize_plugins(self):
        if self.hot_reload_thread is not None and self.hot_reload_thread.is_alive():
            # Signal the hot reload thread to stop
            self.stop_hot_reload.set()
            # Wait for the hot reload thread to finish
            self.hot_reload_thread.join()

        to_unload = set(self.loaded_plugins.keys())
        for module_path in to_unload:
            self.unload_plugin(module_path)
            logger.info(f"Unloaded plugin: {module_path}")

        #for plugin in self.plugin_instances:
        #    plugin.cleanup()
        self.loaded_plugins = {}
        self.plugin_instances = []
        self.plugin_descriptions = {}
        logger.info("Plugins deinitialized and hot reload thread stopped.")