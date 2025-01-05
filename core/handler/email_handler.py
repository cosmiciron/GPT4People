import json
from fastapi.responses import Response

class EmailHandler:
    def __init__(self, core):
        self.core = core

    async def handle_email_message(self, request: PromptRequest):
        user_name: str = request.user_name
        user_id: str = request.user_id
        channel_type: ChannelType = request.channelType
        content_type: ContentType = request.contentType

        if content_type.value == ContentType.TEXT.value:
            content = request.text                    
            if channel_type == ChannelType.Email:
                content_json = json.loads(content)
                msg_id = content_json["MessageID"]
                email_addr = content_json["From"]
                subject = content_json["Subject"]
                body = content_json["Body"]
                prompt_template = self.core.prompt_template(section=channel_type.value, prompt_name="entrypoint")
                for prompt_template_item in prompt_template:
                    prompt_template_item['content'] = prompt_template_item['content'].format(subject=subject, body=body)
                result = await self.core.openai_chat_completion(prompt_template, self.core.metadata.main_llm)
                logger.debug(f"OpenAI chat completion result: {result}")
                tmp = self.core.extract_json_str(result)
                logger.debug(f"tmp: {tmp}")
                result_json = json.loads(tmp)
                action = result_json['action']
                query = ""
                emails = []
                try:
                    if action == 'send':
                        emails = result_json['email']
                        email = ",".join(emails)
                        subject = result_json['subject']
                        body = result_json['body']
                        query = f"Send an email to '{email}' according to the given subject: '{subject}' and body: '{body}'"
                    elif action == 'reply':
                        query = f"Reply to one given email according to the given subject: '{subject}' and body: '{body}'"
                    # Further processing
                except Exception as e:
                    logger.exception(e)
                    return Response(content="Server Internal Error", status_code=500)
                # Continue processing
                return Response(content=json.dumps({"ai_response": result_json}, ensure_ascii=False).encode('utf-8'), media_type="application/json", status_code=200)