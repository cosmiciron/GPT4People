import asyncio
from datetime import datetime
import os

import requests
from base.SchedulerPlugin import SchedulerPlugin
from loguru import logger
from base.util import Util
from core.coreInterface import CoreInterface
class NewsPlugin(SchedulerPlugin):
    def __init__(self, coreInst: CoreInterface):
        super().__init__(coreInst=coreInst)  
        # Automatically determine the path to the config.yml file
        logger.debug('NewsPlugin __init__...')
        config_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'config.yml')
        logger.debug(f'config_path: {config_path}')
        if not os.path.exists(config_path):
            logger.debug(f"Config file does not exist: {config_path}")  # Debugging line
            return
        self.config = Util().load_yml_config(config_path)
        logger.debug(f'NewsPlugin description: {self.config["description"]}')
        self.date = datetime.now().strftime("%Y-%m-%d")
        self.news = []
        self.prompt = """
            You are an expert at summarizing and refining news articles.

            Guidelines:
            1. Read through the provided news articles.
            2. Select the top 3 latest news articles.
            3. Reorganize and summarize the main points of each article in a concise manner.
            4. Refine the content to enhance readability and clarity.
            5. Generate a final summary to be sent to the user.

            News Articles:
            {news_articles}

            Final Summary:
        """
        logger.debug(f'NewsPlugin config: {self.config}')  

    async def fetch_latest_news(self):
        try:
            date = datetime.now().strftime("%Y-%m-%d")
            if self.date != date:
                self.date = date
                self.news = []
            base_url = self.config['base_url']
            api_key = self.config['apiKey']
            country = self.config['country']
            category = self.config['category']
            sources = self.config['sources']
            # Generate the URL using country and category for now.
            urls = []
            main_url = f"{base_url}?country={country}&category={category}&apiKey={api_key}"
            tech_url = f"{base_url}?sources={sources}&apiKey={api_key}"
            urls.append(main_url)
            urls.append(tech_url)

            for url in urls:
                resp: dict = requests.get(url).json()
                news: list = resp.get('articles', [])
                if not news:
                    logger.error("No news articles found.")
                    return

                logger.debug(f'NewsPlugin fetch_latest_news: {news}')   
                # Sort the news articles by publication date (assuming 'publishedAt' is in the article)
                sorted_news = sorted(news, key=lambda x: x.get('publishedAt', ''), reverse=True)
                i = 0
                articles = []
                for article in sorted_news:
                    if article not in self.news:
                        self.news.append(article)
                        articles.append(article)
                        i += 1
                        if i == 3:
                            break
                    else:
                        logger.debug("No new news articles found. Using the same set of news articles.")
                if len(articles) == 0:
                    return
                
                # Select the top 3 latest news articles
                news_articles = [{"title": article['title'], "content": article['content']} for article in articles]
                # Generate the prompt with top 3 news articles
                formatted_articles = "\n".join([f'{i+1}. {article["title"]}\n{article["content"]}' for i, article in enumerate(news_articles)])
                final_prompt = self.prompt.format(news_articles=formatted_articles)
                messages = []
                if not messages or messages[0]["role"] != "system":
                    messages = [{"role": "system", "content": final_prompt}]
                # Assuming `call_openai` is a function to get the response from the model
                refined_summary = await Util().openai_chat_completion(messages)
                
                # Send the refined summary to the user
                await self.coreInst.send_response_to_latest_channel(response=refined_summary)
        
        except requests.RequestException as e:
            logger.error(f"Failed to fetch news: {e}")


    async def run(self):
        await self.fetch_latest_news()

    def initialize(self):
        if self.initialized:
            return
        logger.debug("Initializing News plugin")
        super().initialize()
        self.initialized = True