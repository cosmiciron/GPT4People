import os
from typing import List
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger
import litellm
from litellm import completion, acompletion, embedding, aembedding, EmbeddingResponse, image_generation, aimage_generation, ImageResponse
from base.util import Util
from base.base import ChatRequest, EmbeddingRequest, ImageGenerationRequest
import asyncio
from contextlib import asynccontextmanager

litellm.drop_params = True



class LiteLLMService:
    
    @asynccontextmanager
    async def lifespan(self, app: FastAPI):
        #await register_with_core()
        logger.debug("LiteLLM service lifespan started!")
        yield
        logger.debug("LiteLLM service lifespan end!")
        try:
            # Do some deinitialization
            pass
        except:
            pass
    
    def __init__(self):
        self.app = FastAPI()
        self.num_retries = 2
        self.max_tokens = 2048
        self._setup_routes()
        os.environ["OPENAI_API_KEY"] = "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"
 
    def _setup_routes(self):
        @self.app.exception_handler(RequestValidationError)
        async def validation_exception_handler(request: Request, exc: RequestValidationError):
            logger.error(f"Validation error: {exc} for request: {await request.body()}")
            return JSONResponse(
                status_code=422,
                content={"detail": exc.errors(), "body": exc.body},
            ) 
    

        @self.app.post("/v1/chat/completions")
        async def chat_completion(request: ChatRequest):
            '''
                def completion(
                    model: str,
                    messages: List = [],
                    # Optional OpenAI params
                    timeout: Optional[Union[float, int]] = None,
                    temperature: Optional[float] = None,
                    top_p: Optional[float] = None,
                    n: Optional[int] = None,
                    stream: Optional[bool] = None,
                    stream_options: Optional[dict] = None,
                    stop=None,
                    max_tokens: Optional[int] = None,
                    presence_penalty: Optional[float] = None,
                    frequency_penalty: Optional[float] = None,
                    logit_bias: Optional[dict] = None,
                    user: Optional[str] = None,
                    # openai v1.0+ new params
                    response_format: Optional[dict] = None,
                    seed: Optional[int] = None,
                    tools: Optional[List] = None,
                    tool_choice: Optional[str] = None,
                    parallel_tool_calls: Optional[bool] = None,
                    logprobs: Optional[bool] = None,
                    top_logprobs: Optional[int] = None,
                    deployment_id=None,
                    # soon to be deprecated params by OpenAI
                    functions: Optional[List] = None,
                    function_call: Optional[str] = None,
                    # set api_base, api_version, api_key
                    base_url: Optional[str] = None,
                    api_version: Optional[str] = None,
                    api_key: Optional[str] = None,
                    model_list: Optional[list] = None,  # pass in a list of api_base,keys, etc.
                    # Optional liteLLM function params
                    **kwargs,

                ) -> ModelResponse:
            '''
            try:
                model = request.model
                messages = request.messages
                
                response = await acompletion(model=model, messages=messages,
                                             num_retries=self.num_retries, response_format=request.response_format, timeout=request.timeout,
                                             tools= request.tools, tool_choice=request.tool_choice, parallel_tool_calls=request.parallel_tool_calls,
                                             temperature=request.temperature, presence_penalty=request.presence_penalty,
                                             frequency_penalty=request.frequency_penalty, seed=request.seed, logit_bias=request.logit_bias,
                                             top_p=request.top_p, n=request.n, max_tokens=request.max_tokens,
                                             stream=request.stream, stream_options=request.stream_options, logprobs=request.logprobs, top_logprobs=request.top_logprobs,
                                             function_call=request.function_call, functions=request.functions)
                
                logger.debug(f"Response from litellm's openAI, {response}")
                if request.stream is False or request.stream is None:
                    resp_json = response.to_json()
                    return resp_json
                else:
                    chunks = []
                    for chunk in response:
                        chunks.append(chunk)
                    resp = litellm.stream_chunk_builder(chunks)
                    resp_json = resp.to_json()
                    return JSONResponse(content=resp_json, media_type="application/json")
            except Exception as e:
                logger.exception(e)
                return JSONResponse(status_code=500, content={"detail": str(e)})            


        # This embedding function always give word embedding, not sentence embedding, deprecated!
        @self.app.post("/v1/embeddings")
        async def embedding(request: EmbeddingRequest):
            try:
                model = request.model
                input = request.input
                response: EmbeddingResponse = await aembedding(model=model, input=input, input_type=request.input_type,
                                  dimensions=request.dimensions, timeout=request.timeout, 
                                  api_base=request.api_base, api_version=request.api_version, 
                                  api_key=request.api_key, api_type=request.api_type)
                
                return response.data  # #List[List[float]]
            except Exception as e:
                logger.exception(e)
                return JSONResponse(status_code=500, content={"detail": str(e)})
            
            
        @self.app.post("/v1/image_generation")
        async def image_generation(request: ImageGenerationRequest):
            try:
                prompt = request.prompt
                model = request.model
                response: ImageResponse = await aimage_generation(prompt=prompt, model=model, n=request.n, quality=request.quality,
                                  response_format=request.response_format, size=request.size, style=request.style, timeout=request.timeout,
                                  api_base=request.api_base, api_version=request.api_version, 
                                  api_key=request.api_key)
                '''
                {
                    "created": 1703658209,
                    "data": [{
                        'b64_json': None, 
                        'revised_prompt': 'Adorable baby sea otter with a coat of thick brown fur, playfully swimming in blue ocean waters. Its curious, bright eyes gleam as it is surfaced above water, tiny paws held close to its chest, as it playfully spins in the gentle waves under the soft rays of a setting sun.', 
                        'url': 'https://oaidalleapiprodscus.blob.core.windows.net/private/org-ikDc4ex8NB5ZzfTf8m5WYVB7/user-JpwZsbIXubBZvan3Y3GchiiB/img-dpa3g5LmkTrotY6M93dMYrdE.png?st=2023-12-27T05%3A23%3A29Z&se=2023-12-27T07%3A23%3A29Z&sp=r&sv=2021-08-06&sr=b&rscd=inline&rsct=image/png&skoid=6aaadede-4fb3-4698-a8f6-684d7786b067&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2023-12-26T13%3A22%3A56Z&ske=2023-12-27T13%3A22%3A56Z&sks=b&skv=2021-08-06&sig=hUuQjYLS%2BvtsDdffEAp2gwewjC8b3ilggvkd9hgY6Uw%3D'
                    }],
                    "usage": {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}
                }
                '''
                return response  # #List[List[float]]
            except Exception as e:
                logger.exception(e)
                return JSONResponse(status_code=500, content={"detail": str(e)})    
