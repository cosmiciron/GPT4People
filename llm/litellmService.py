'''
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
                return response  # #List[List[float]]
            except Exception as e:
                logger.exception(e)
                return JSONResponse(status_code=500, content={"detail": str(e)})    
'''