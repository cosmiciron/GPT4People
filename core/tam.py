import asyncio
from datetime import datetime, timedelta
import json
import random
import signal
import sys
import threading
import time
from typing import List, Dict
from loguru import logger
from pathlib import Path
from schedule import Scheduler

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from base.base import IntentType, Intent, PromptRequest
from base.util import Util
from core.coreInterface import CoreInterface

class TAM:
    def __init__(self, coreInst: CoreInterface):
        logger.debug("TAM initializing...")
        #self.intent_queue = asyncio.Queue(100)
        #self.intent_queue_task = None
        self.scheduler = Scheduler()
        self.scheduled_jobs = []
        self.coreInst = coreInst

        # Start the thread to handle the intent queue
        # Register signal handlers
        #signal.signal(signal.SIGINT, self.signal_handler)
        logger.debug("TAM initialized!")

    #def signal_handler(self, signum, frame):
    #    logger.debug('Received SIGINT, shutting down gracefully...')
    #    self.stop_intent_queue_handler()
        # Exit the program
        # sys.exit(0)

    #def add_intent(self, intent: Intent):
    #    logger.debug(f"TAM add intent: {intent}")
    #    self.intent_queue.put_nowait(intent)
    #    logger.debug(f"TAM added intent: {intent}")

    '''
    async def start_intent_queue_handler(self):
        logger.debug("Starting intent queue handler task...")
        self.intent_queue_task = asyncio.create_task(self.process_intent_queue())
        logger.debug("Intent queue handler task started.")

    async def stop_intent_queue_handler(self):
        # Add None to the queue to signal the task to shut down
        logger.debug("Stopping intent queue handler task...")
        await self.intent_queue.put(None)
        if self.intent_queue_task:
            await self.intent_queue_task
        logger.debug("Intent queue handler task stopped.")


    async def process_intent_queue(self):
        while True:
            try:
                logger.debug(f"TAM intent queue size before get: {self.intent_queue.qsize()}")
                intent: Intent = await self.intent_queue.get()
                logger.debug(f"TAM intent queue size after get: {self.intent_queue.qsize()}")
                if intent is None:
                    break

                    # Analyze the intent using LLM and create a data object
                    data_object = await self.analyze_intent_with_llm(intent)
                    
                    # Use the data object to schedule a job
                    self.schedule_job_from_intent(data_object)
            except Exception as e:
                logger.exception(f"TAM: Error processing intent: {e}")
            finally:
                self.intent_queue.task_done()
            await asyncio.sleep(0.1)  # Small sleep to avoid tight loop
    '''

    async def process_intent(self, intent: Intent, request: PromptRequest):
        if intent is None:
            return
        try:
            logger.debug(f"TAM process_intent: {intent}")
            # Analyze the intent using LLM and create a data object
            data_object = await self.analyze_intent_with_llm(intent)
            logger.debug(f"TAM got data_object: {data_object}")
            # Use the data object to schedule a job
            self.schedule_job_from_intent(data_object, request)
        except Exception as e:
            logger.exception(f"TAM: Error processing intent: {e}")


    async def analyze_intent_with_llm(self, intent: Intent) -> Dict:
        # Combine the input text and chat history into a single context
        text = intent.text
        hist = intent.chatHistory
        
        # Create the prompt
        prompt = self.create_prompt(text, hist)
        logger.debug(f'TAM Prompt: {prompt}')
        
        # Prepare messages for the language model
        messages = [{"role": "system", "content": prompt}]
        
        # Get the response from the language model
        response_str = await Util().openai_chat_completion(messages)
        response_str = response_str.strip()
        if not response_str:
            logger.error('TAM: LLM response is empty')
            return None
        logger.debug(f'TAM got response: {response_str}')
        
        # Parse the response into a JSON object
        try:
            response_str = Util().extract_json_str(response_str)
            logger.debug(response_str)
            response_json = json.loads(response_str)
        except json.JSONDecodeError:
            logger.error('TAM: Failed to decode LLM response JSON')
            return None
        
        return response_json

    '''
    def create_prompt(self, text: str, chat_history: str) -> str:

       # Get the current datetime
        current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
     # Create the prompt with the current datetime
        prompt = f"""
        You are an expert at understanding user intentions based on chat history and user input. Use the provided chat history, user input, and the current datetime to determine the user's intent and create a structured JSON object for scheduling a job.

        Current datetime: {current_datetime}

        Guidelines:
        1. Use the provided chat history and user input to determine the user's intent.
        2. Ensure the intent is accurate, concise, and directly addresses the user's query.
        3. If the intent is related to scheduling, extract relevant time-based information and create a JSON object.
        4. Use the current datetime as a reference to determine appropriate scheduling times.
        5. Prioritize the most recent time information in the chat history and user input.
        6. Calculate the exact start time for the reminder based on the user's input and the current datetime.
        7. Refine the message in the parameters to be in the voice of the AI assistant, not just extracted from the input.
        8. If a start time is not provided, use the current datetime as the start time.
        9. The JSON object should include the type of job, the interval, and any necessary parameters.

        Provide the JSON object in the following format:
        {{
            "type": "reminder",
            "sub_type": "repeated | fixed | random",
            "interval_unit": "seconds | minutes | hours | days | weeks | months | years",
            "interval": number,
            "start_time": "YYYY-MM-DD HH:MM:SS" (ISO 8601 format) (optional for repeated events),
            "params": {{
                "message": "The message to be reminded or the content of the conversation",
                "repeat": "true" (optional, for repeated events only)
            }}
        }}

        Examples:

        Current datetime: 2023-07-05 10:00:00

        Chat History:
        User: I have a meeting with John tomorrow at 8 AM.
        AI: Got it. Do you need a reminder?

        User Input:
        Yes, please remind me 30 minutes before.

        Determine the user's intent and create a JSON object:
        {{
            "type": "reminder",
            "sub_type": "fixed",
            "interval_unit": "minutes",
            "interval": 30,
            "start_time": "2023-07-06 07:30:00",
            "params": {{"message": "Reminder: You have a meeting with John tomorrow at 8 AM. This is your 30-minute reminder."}}
        }}

        Current datetime: 2023-07-05 10:00:00

        Chat History:
        User: My son's birthday is on 19th August.
        AI: Happy Birthday!

        User Input:
        Please remind me a week before his birthday every year.

        Determine the user's intent and create a JSON object:
        {{
            "type": "reminder",
            "sub_type": "repeated",
            "interval_unit": "years",
            "interval": 1,
            "start_time": "2023-08-12 08:00:00",
            "params": {{"message": "Reminder: Your son's birthday is on 19th August. This is your one-week reminder.", "repeat": "true"}}
        }}

        Current datetime: 2023-07-05 10:00:00

        Chat History:
        User: I have a lunch appointment at 2 PM today.
        AI: Sure, do you need a reminder?

        User Input:
        Yes, please remind me an hour before.

        Determine the user's intent and create a JSON object:
        {{
            "type": "reminder",
            "sub_type": "fixed",
            "interval_unit": "hours",
            "interval": 1,
            "start_time": "2023-07-05 13:00:00",
            "params": {{"message": "Reminder: You have a lunch appointment at 2 PM today. This is your one-hour reminder."}}
        }}

        Current datetime: 2023-07-05 10:00:00

        Chat History:
        User: I have an event the day after tomorrow.
        AI: Got it. Do you need a reminder?

        User Input:
        Yes, please remind me the day before.

        Determine the user's intent and create a JSON object:
        {{
            "type": "reminder",
            "sub_type": "fixed",
            "interval_unit": "days",
            "interval": 1,
            "start_time": "2023-07-06 00:00:00",
            "params": {{"message": "Reminder: You have an event the day after tomorrow. This is your one-day reminder."}}
        }}

        Current datetime: 2023-07-05 10:00:00

        Chat History:
        User: I have a meeting in 10 minutes.
        AI: Got it. Do you need a reminder?

        User Input:
        Yes, please remind me 5 minutes ahead.

        Determine the user's intent and create a JSON object:
        {{
            "type": "reminder",
            "sub_type": "fixed",
            "interval_unit": "minutes",
            "interval": 5,
            "start_time": "2023-07-05 10:05:00",
            "params": {{"message": "Reminder: You have a meeting in 10 minutes. This is your 5-minute reminder."}}
        }}

        Current datetime: 2023-07-05 10:00:00

        Chat History:
        User: Please remind me every 10 minutes.

        User Input:
        Sure, I will remind you every 10 minutes.

        Determine the user's intent and create a JSON object:
        {{
            "type": "reminder",
            "sub_type": "repeated",
            "interval_unit": "minutes",
            "interval": 10,
            "start_time": "2023-07-05 10:10:00",
            "params": {{"message": "Reminder: This is your 10-minute reminder.", "repeat": "true"}}
        }}

        Current datetime: 2023-07-05 10:00:00

        Chat History:
        User: Please say hello to me every 1 minute.

        User Input:
        Sure, I will remind you every minute.

        Determine the user's intent and create a JSON object:
        {{
            "type": "reminder",
            "sub_type": "repeated",
            "interval_unit": "minutes",
            "interval": 1,
            "start_time": "2023-07-05 10:01:00",
            "params": {{"message": "Reminder: Hello! This is your 1-minute reminder.", "repeat": "true"}}
        }}

        Current datetime: 2023-07-05 10:00:00

        Chat History:
        User: Please start to remind me from 9 am every 30 minutes.

        User Input:
        Sure, I will remind you every 30 minutes starting from 9 AM.

        Determine the user's intent and create a JSON object:
        {{
            "type": "reminder",
            "sub_type": "repeated",
            "interval_unit": "minutes",
            "interval": 30,
            "start_time": "2023-07-06 09:00:00",
            "params": {{"message": "Reminder: This is your 30-minute reminder.", "repeat": "true"}}
        }}

        Current datetime: 2023-07-05 10:00:00

        Chat History:
        User: Please send me some quotes in the morning.

        User Input:
        Sure, I will send you quotes every morning.

        Determine the user's intent and create a JSON object:
        {{
            "type": "reminder",
            "sub_type": "random",
            "interval_unit": "days",
            "interval": 1,
            "start_time": "{current_datetime}",
            "params": {{"message": "Reminder: Here is your morning quote.", "repeat": "true"}}
        }}

        Current datetime: 2023-07-05 10:00:00

        Chat History:
        User: Please send me some short stories in the evening.

        User Input:
        Sure, I will send you short stories every evening.

        Determine the user's intent and create a JSON object:
        {{
            "type": "reminder",
            "sub_type": "random",
            "interval_unit": "days",
            "interval": 1,
            "start_time": "{current_datetime}",
            "params": {{"message": "Reminder: Here is your evening short story.", "repeat": "true"}}
        }}

        Current datetime: {current_datetime}

        Chat History:
        {chat_history}

        User Input:
        {text}

        Determine the user's intent and create a JSON object:
        """
        return prompt
    '''
    def create_prompt(self, text: str, chat_history: str) -> str:
        # Get the current datetime
        current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Define the common prompt template
        prompt_template = """\
        You are an expert at understanding user intentions based on chat history and user input. Use the provided chat history, user input, and the current datetime to determine the user's intent and create a structured JSON object for scheduling a job.

        Current datetime: {current_datetime}

        Guidelines:
        - Use the chat history and user input to determine the user's intent.
        - Ensure the intent is accurate, concise, and addresses the user's query.
        - If the intent is related to scheduling, create a JSON object with time-based information.
        - Use the current datetime to determine appropriate scheduling times.
        - Prioritize recent information in the chat history and user input.
        - If no start time is provided, use the current datetime as the start time.
        - The JSON object should include the job type, interval, and necessary parameters.

        Provide the JSON object in the following format:
        {{
            "type": "reminder",
            "sub_type": "repeated | fixed | random",
            "interval_unit": "seconds | minutes | hours | days | weeks | months | years",
            "interval": number,
            "start_time": "YYYY-MM-DD HH:MM:SS" (ISO 8601 format),
            "params": {{
                "message": "Reminder content",
                "repeat": "true" (for repeated events)
            }}
        }}

        Examples:
        * Several examples can be listed here with a single instance of the current datetime *

        Current datetime: {current_datetime}

        Chat History:
        {chat_history}

        User Input:
        {text}

        Determine the user's intent and create a JSON object:"""

        # Format the prompt with the current datetime, chat history, and user input
        prompt = prompt_template.format(
            current_datetime=current_datetime,
            chat_history=chat_history,
            text=text
        )
        return prompt    

    def schedule_job_from_intent(self, data_object: Dict, request: PromptRequest):
        logger.debug(f"Scheduling job with data: {data_object}")
        job_type = data_object.get('type')
        sub_type = data_object.get('sub_type')
        interval_unit = data_object.get('interval_unit')
        interval = data_object.get('interval')
        start_time = data_object.get('start_time')
        params: Dict = data_object.get('params', {})

        if job_type == "reminder":
            async def task():
                await self.send_reminder_to_latest_channel(params.get("message"))
        else:
            logger.error(f'TAM: Unsupported job type: {job_type}')
            return
        if sub_type == "repeated":
            self.schedule_repeated_task(task, interval_unit, interval, start_time)
        elif sub_type == "fixed":
            self.schedule_fixed_task(task, start_time)
        elif sub_type == "random":
            self.schedule_random_task(task, interval_unit, interval, start_time)
        else:
            logger.error(f'TAM: Unsupported sub-type: {sub_type}')

    async def send_reminder(self, message: str, request: PromptRequest):
        await self.coreInst.send_response_to_request_channel(response=message, request=request)

    async def send_reminder_to_latest_channel(self, message: str):
        await self.coreInst.send_response_to_latest_channel(response=message)


    def schedule_repeated_task(self, task, interval_unit, interval, start_time=None):
        logger.debug(f"Scheduled task to repeat every {interval} {interval_unit} at {start_time}")
        def job_wrapper():
            asyncio.run(task())
            # Schedule the next run using the schedule library
            self._schedule_interval_task(task, interval_unit, interval)

        if start_time:
            now = datetime.now()
            start_time_obj = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
            start_time_delta = start_time_obj + timedelta(minutes=1)
            if now > start_time_delta:
                start_time_obj += timedelta(days=1)

            delay = (start_time_obj - now).total_seconds()
            threading.Timer(delay, job_wrapper).start()
            logger.debug(f"Scheduled task to start at {start_time_obj} and repeat every {interval} {interval_unit}")
        else:
            self._schedule_interval_task(task, interval_unit, interval)

    def _schedule_interval_task(self, task, interval_unit, interval):

        if interval_unit == 'seconds':
            job = self.scheduler.every(interval).seconds.do(lambda: asyncio.run(task()))
        elif interval_unit == 'minutes':
            job = self.scheduler.every(interval).minutes.do(lambda: asyncio.run(task()))
        elif interval_unit == 'hours':
            job = self.scheduler.every(interval).hours.do(lambda: asyncio.run(task()))
        elif interval_unit == 'days':
            job = self.scheduler.every(interval).days.do(lambda: asyncio.run(task()))
        elif interval_unit == 'weeks':
            job = self.scheduler.every(interval).weeks.do(lambda: asyncio.run(task()))
        else:
            raise ValueError(f"Unsupported interval unit: {interval_unit}")

        self.scheduled_jobs.append(job)
        logger.debug(f"Scheduled task to repeat every {interval} {interval_unit}")

    def schedule_fixed_task(self, task, run_time_str):
        run_time = datetime.strptime(run_time_str, "%Y-%m-%d %H:%M:%S")
        now = datetime.now()
        # Calculate the delay until the run_time
        delay = (run_time - now).total_seconds()
        
        if delay <= 0:
            logger.debug("The specified run time is in the past.")
            return
        
        # Schedule the task to run after the delay
        threading.Timer(delay, lambda: asyncio.run(task())).start()
        logger.debug(f"Task scheduled to run at {run_time}")


    def random_time_within_range(self, min_interval, max_interval):
        return random.uniform(min_interval, max_interval)


    def schedule_random_task(self, task, interval_unit, min_interval, max_interval):
        if interval_unit == 'seconds':
            pass
        elif interval_unit == 'minutes':
            min_interval = min_interval * 60
            max_interval = max_interval * 60
        elif interval_unit == 'hours':
            min_interval = min_interval * 60 * 60
            max_interval = max_interval * 60 * 60
        elif interval_unit == 'days':
            min_interval = min_interval * 60 * 60 * 24
            max_interval = max_interval * 60 * 60 * 24
        elif interval_unit == 'weeks':
            min_interval = min_interval * 60 * 60 * 24 * 7
            max_interval = max_interval * 60 * 60 * 24 * 7

        def wrapped_task():
            asyncio.run(task())
            next_run_in_seconds = self.random_time_within_range(min_interval, max_interval)
            next_run_time = datetime.now() + timedelta(seconds=next_run_in_seconds)
            job = self.scheduler.every().day.at(next_run_time.strftime("%H:%M:%S")).do(wrapped_task)
            self.scheduled_jobs.append(job)

        # Schedule the initial task
        next_run_in_seconds = self.random_time_within_range(min_interval, max_interval)
        next_run_time = datetime.now() + timedelta(seconds=next_run_in_seconds)
        job = self.scheduler.every().day.at(next_run_time.strftime("%H:%M:%S")).do(wrapped_task)
        self.scheduled_jobs.append(job)

    def run_scheduler(self):
        while True:
            self.scheduler.run_pending()
            time.sleep(10)

    def run(self):
        self.thread = threading.Thread(target=self.run_scheduler)
        self.thread.daemon = True
        self.thread.start()

    def cleanup(self):
        for job in self.scheduled_jobs:
            self.scheduler.cancel_job(job=job)
        self.scheduler.clear()
        self.thread.join()
        logger.debug("SchedulerPlugin cleanup done!")  


    
    