import asyncio
import os

import urllib
import urllib.parse
import urllib.request as request
import urllib.response as response
import urllib.error as error
import json

from base.SchedulerPlugin import SchedulerPlugin
from loguru import logger
from base.util import Util
from core.coreInterface import CoreInterface

class WeatherPlugin(SchedulerPlugin):
    def __init__(self, coreInst: CoreInterface):
        super().__init__(coreInst=coreInst)
        # Automatically determine the path to the config.yml file
        logger.debug('WeatherPlugin __init__...')
        config_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'config.yml')
        logger.debug(f'config_path: {config_path}')
        if not os.path.exists(config_path):
            logger.debug(f"Config file does not exist: {config_path}")  # Debugging line
            return
        self.config = Util.load_yml_config(config_path)
        logger.debug(f'WeatherPlugin config: {self.config}')      

    async def fetch_weather(self):
        city = self.config['city']
        api_key = self.config['api_key']
        api_url = 'http://apis.juhe.cn/simpleWeather/query'
        params_dict = {
            "city": city,  # 查询天气的城市名称，如：北京、苏州、上海
            "key": api_key,  # 您申请的接口API接口请求Key
        }
        params = urllib.parse.urlencode(params_dict)
        try:
            req = request.Request(api_url, params.encode())
            response = request.urlopen(req)
            content = response.read()
            resp = None
            if content:
                try:
                    result = json.loads(content)
                    error_code = result['error_code']
                    if (error_code == 0):
                        temperature = result['result']['realtime']['temperature']
                        humidity = result['result']['realtime']['humidity']
                        info = result['result']['realtime']['info']
                        wid = result['result']['realtime']['wid']
                        direct = result['result']['realtime']['direct']
                        power = result['result']['realtime']['power']
                        aqi = result['result']['realtime']['aqi']
                        # Compose the prompt
                        prompt = (
                            f"Here is the current weather information for {city}:\n"
                            f"Temperature: {temperature}°C\n"
                            f"Humidity: {humidity}%\n"
                            f"Weather: {info}\n"
                            f"Wind Direction: {direct}\n"
                            f"Wind Power: {power}\n"
                            f"Air Quality Index (AQI): {aqi}\n"
                            "Reorganize the weather information for user friendly and please provide suggestions on Eg, whether to wash the car, "
                            "take an umbrella, wear more clothes, etc."
                        )
                        messages = []
                        if not messages or messages[0]["role"] != "system":
                            messages = [{"role": "system", "content": prompt}]

                        resp = await Util().openai_chat_completion(messages)
                        resp = resp.strip()
                        logger.debug(f"fetch_weather response: {resp}")
                    else:
                        logger.debug(f"faile to get weather: {result['error_code']}, {result['reason']}")
                except Exception as e:
                    logger.exception(e)
            else:
                # 可能网络异常等问题，无法获取返回内容，请求异常
                logger.debug("faile to get weather, maybe network error")
        except error.HTTPError as err:
            logger.debug(err)
        except error.URLError as err:
            # 其他异常
            logger.debug(err)

        if resp is None:
            resp = 'Failed to get the weather information.'
        await self.coreInst.send_response_to_latest_channel(response=resp)


    async def run(self):
        await self.fetch_weather()

    def initialize(self):
        if self.initialized:
            return
        logger.debug("Initializing Weather plugin")
        super().initialize()
        self.initialized = True