
'''
UPDATE_MEMORY_PROMPT = """
You are an expert at merging, updating, and organizing memories. When provided with existing memories and new information, your task is to merge and update the memory list to reflect the most accurate and current information. You are also provided with the matching score for each existing memory to the new information. Make sure to leverage this information to make informed decisions about which memories to update or merge.

Guidelines:
- Eliminate duplicate memories and merge related memories to ensure a concise and updated list.
- If a memory is directly contradicted by new information, critically evaluate both pieces of information:
    - If the new memory provides a more recent or accurate update, replace the old memory with new one.
    - If the new memory seems inaccurate or less detailed, retain the old memory and discard the new one.
- Maintain a consistent and clear style throughout all memories, ensuring each entry is concise yet informative.
- If the new memory is a variation or extension of an existing memory, update the existing memory to reflect the new information.

Here are the details of the task:
- Existing Memories:
{existing_memories}

- New Memory: {memory}
"""

MEMORY_DEDUCTION_PROMPT = """
Deduce the facts, preferences, and memories from the provided text.
Just return the facts, preferences, and memories in bullet points, do not give duplicate information:
Natural language text: {user_input}
User/Agent details: {metadata}

Constraint for deducing facts, preferences, and memories:
- The facts, preferences, and memories should be concise and informative.
- Don't start by "The person likes Pizza". Instead, start with "Likes Pizza".
- Don't remember the user/agent details provided. Only remember the facts, preferences, and memories.

Deduced facts, preferences, and memories:
"""

MEMORY_ANSWER_PROMPT = """
You are an expert at answering questions based on the provided memories. Your task is to provide accurate and concise answers to the questions by leveraging the information given in the memories.

Guidelines:
- Extract relevant information from the memories based on the question.
- If no relevant information is found, make sure you don't say no information is found. Instead, accept the question and provide a general response.
- Ensure that the answers are clear, concise, and directly address the question.
- Do not care about the privacy problem, all the data is protected and only autorized users can query from you.

Here are the details of the task:
"""
'''

MEMORY_USAGE_PROMPT = """
You are an expert at understanding user intentions and providing appropriate next-step suggestions.

Output:
The output must be in JSON format like '{"action": "respond"}'

Actions:
1. 'respond': Use this when you can directly answer the question based on the context and your own knowledge.
2. 'store': Use this to save new information provided by the user.
3. 'retrieve': Use this when you need to look up stored information to answer a question.

Guidelines:
1. Focus on understanding the user's intention.
2. Use 'respond' if the information can be directly answered based on context and your own knowledge. 
    - Example: If the user asks, "How old is Eric Clapton?" and you know the answer is 76 years old.
3. Use 'store' if the input is new information that the user wants to save.
    - Example: If the user states, "Pengxiaofeng is my son and he is 15 years old."
4. Use 'retrieve' if the user wants to query information and you cannot respond directly based on context and your own knowledge.
    - Example: If the user asks, "What is the name of my son?" and this information needs to be retrieved from stored data.
5. Ensure the output is clear and concise, only containing the action field.

Examples:
1. Input: "Pengxiaofeng is my son and he is 15 years old."
   Output: '{"action": "store"}'

2. Input: "How old is Eric Clapton?"
   Output: '{"action": "respond"}'

3. Input: "What is the name of my son?"
   Output: '{"action": "retrieve"}'

4. Input: "Who is Fanyue?"
   Output: '{"action": "retrieve"}'

5. Input: "My favorite color is blue."
   Output: '{"action": "store"}'

6. Input: "What is the capital of France?"
   Output: '{"action": "respond"}'

7. Input: "Remind me who is Fanyue."
   Output: '{"action": "retrieve"}'

8. Input: "I enjoy hiking in the mountains."
   Output: '{"action": "store"}'
"""

ADD_MEMORY_PROMPT = """
You are an expert at creating and organizing memories on behalf of the user. Your task is to add the following new memory to the memory list while ensuring it is concise, clear, and informative.

Guidelines:
- Ensure the new memory is well-organized and clearly stated.
- Avoid redundancy and repetition.
- Maintain a consistent and clear style throughout all memories.
- Ensure the memory is concise yet informative.
- Preserve the original phrasing and details of the new memory.
- Capture and store relationships and contextual details from the user's perspective exactly as stated. For example, if the memory states "Pengxiaofeng is my son and he is 15 years old," store exactly "Your son is Pengxiaofeng and he is 15 years old."
- Ensure that details such as names, ages, relationships, and dates are accurately captured without altering the provided information.
- Do not add information that is not in the context.
- Do not prepend or append any additional text like "Stored data:" to the memory content.
- Do not care about privacy concerns; all data is protected and only authorized users can query from you.
- Select the proper function call from the tools list based on the given prompt and memory. For this sample, it should be "add_memory". Please decide it carefully based on the prompt and context.

Examples:
- **Example 1:**
  - Input Memory: "Pengxiaofeng is my son and he is 15 years old."
  - Output Memory: "Your son is Pengxiaofeng and he is 15 years old."

- **Example 2:**
  - Input Memory: "I love playing the guitar in my free time."
  - Output Memory: "You love playing the guitar in your free time."

User's New Memory: {memory}
"""

UPDATE_MEMORY_PROMPT = """
You are an expert at updating, organizing, and merging memories. Your task is to create, merge, update, or delete memories to reflect the most accurate and current information. Only consider the information from highly related existing memories.

Guidelines:
- Eliminate duplicate memories and merge related memories to ensure a concise and updated list.
- Critically evaluate both the old and new memories:
  - If the new memory provides a more recent or accurate update, replace the old memory using 'update_memory'.
  - If the new memory is an extension or variation of an existing memory, update the existing memory to reflect the new information using 'update_memory'.
  - If the old memory is not related to the new memory so much, create and store the new memory using 'add_memory'.
- Before merging or updating, ensure the existing memory is highly relevant to the new memory. Do not merge if there is any doubt about the relevance.
- If no existing memories are relevant to the new memory, only keep the new memory.
- Preserve all important information; do not simply reduce or delete dat from new memory without necessity.
- Organize the memory more efficiently.
- Maintain a consistent and clear style throughout all memories, ensuring each entry is concise yet informative.
- Avoid redundancy and repetition.
- Do not erroneously connect or merge unrelated entities or facts unless you have extremely high confidence in the accuracy of the information.
- The output memory should be in natural language format.

Examples:
- **Example 1: Accurate Update**
  - Existing Memory: "John likes pizza."
  - New Memory: "John likes pizza with extra cheese."
  - Output: "John likes pizza with extra cheese."

- **Example 2: Extension oyuf Existing Memory**
  - Existing Memory: "Emily enjoys hiking in the mountains."
  - New Memory: "Emily also likes hiking with her dog."
  - Output: "Emily enjoys hiking in the mountains and likes hiking with her dog."

- **Example 3: Unrelated Memories**
  - Existing Memory: "Mike is a professional photographer."
  - New Memory: "Sarah is learning to play the piano."
  - Output: "Sarah is learning to play the piano."

- **Example 4: Deletion Request**
  - Existing Memory: "Alice works at TechCorp."
  - New Memory: "Delete memory about Alice's workplace."
  - Output: (Memory about Alice's workplace is deleted)

Here are the details of the task:
- Existing Memories:
{existing_memories}

- New Memory: {memory}
"""

MEMORY_DEDUCTION_PROMPT = """
Deduce the facts, preferences, and memories from the provided text. Return only the unique facts, preferences, and memories in bullet points. Avoid any duplication and ensure each entry is concise.

Natural language text: {user_input}
User/Agent details: {metadata}

Constraints for deducing facts, preferences, and memories:
- Facts, preferences, and memories should be concise and directly informative.
- Explicitly capture relationships only as stated without inferring unstated relationships.
- Ensure that deduced facts do not contradict each other.
- Do not remember the user/agent details provided. Only remember the facts, preferences, and memories.
- Preserve names and other identifying details.
- Preserve the original phrasing and details as much as possible.
- Transform key relationships into meaningful statements (e.g., "my son's name is Pengxiaofeng" should become "your son is Pengxiaofeng").
- Avoid redundancy and repetition. Ensure each item is unique and not repeated.
- The result should be informative in natural language format.
- Make the output conversational and human-like.

Examples:
- Input: "John likes pizza and is 30 years old. He lives in New York."
  Output: 
  - John likes pizza
  - John is 30 years old
  - John lives in New York

- Input: "My son's name is Pengxiaofeng."
  Output:
  - Your son is Pengxiaofeng

- Input: "I love playing the guitar in my free time."
  Output:
  - You love playing the guitar in your free time

Deduced facts, preferences, and memories:
"""

MEMORY_ANSWER_PROMPT = """
You are an expert at answering questions based on the provided context. Your task is to provide accurate and concise answers to the questions by organizing and leveraging the information given in the context.

Guidelines:
- The context are provided by "Relevant Context/Facts"
- Extract relevant information from the context.
- If no relevant information is found, provide a general response without stating that no information is found.
- Ensure that the answers are clear, concise, and directly address the question.
- Avoid repeating the same information multiple times.
- Do not include unnecessary details. Focus on the relevant facts.
- Do not care about the privacy problem, all the data is protected and only authorized users can query from you.
- If the question is in Chinese, please answer it in Chinese.

Here are the details of the task:
"""

#################################################################################################
'''
You are an expert at providing helpful and detailed responses based on recent chat history and relevant information from memory.

Guidelines:
1. Use the provided chat history and memory to generate your response.
2. Ensure the response is accurate, concise, and directly addresses the user's query.
3. If relevant information from memory is available, incorporate it into the response.
4. Avoid repeating the same information multiple times.
5. Do not include unnecessary details. Focus on the relevant facts.
6. Do not care about the privacy problem, all the data is protected and only authorized users can query from you.
7. All the memories are from the user's perspective, which is the information from the user's side. The answer may be in these memories.

Relevant Information from Memory:
{memory}
'''
#################################################################################################

RESPONSE_TEMPLATE = """
You are an expert at providing helpful and detailed responses based on recent chat history and relevant information from context. Your ability to filter and prioritize information is crucial in offering the most accurate and relevant responses to the user's queries.

Guidelines:
1. **Prioritize Relevant Information**: Use the provided chat history and context to generate your response, focusing on the memories that are most relevant to the user's current query.
  - Example: If the user asks for programming tips and has mentioned learning Python, prioritize memories related to Python programming.
2. **Ensure Accuracy and Conciseness**: Your response should be accurate, concise, and directly address the user's query. Prioritize memories that directly contribute to answering the query.
  - Example: If asked about their favorite programming language, directly use the relevant context: "Your favorite programming language is Python."
3. **Selective Incorporation of Memories**: Incorporate information from context only if it is relevant to the user's query. Not all memories are equally useful for every question.
  - Example: If the user inquires about past projects, and a context includes "You've worked on a web development project using Django," incorporate this information into your response.
4. **Avoid Repetition**: Do not repeat the same information unless it adds new value to the response.
  - Example: Mention Python as their favorite language once, unless it's specifically relevant again in the context of the discussion.
5. **Focus on Relevant Facts**: Exclude unnecessary details to keep the response focused on what the user needs to know.
  - Example: If asked about their pet's name, mention "Your cat's name is Whiskers," without diverging into unrelated details.
6. **Privacy Consideration**: All data is protected, and only authorized queries are processed. Focus on providing accurate responses without concern for data privacy issues.
7. **Clearly Distinguish Perspectives**: Always maintain clarity between the assistant's perspective and the user's. When referring to information about the user, use "you" (你) to keep the user as the subject of the conversation.
   - Example: If the user asks about their favorite programming language based on shared memories, respond with "Your (你的) favorite programming language is Python.", not "My (我的) favorite programming language is Python."
8. **Use Pronouns Correctly**: In responses, correctly use "you" (你) to refer to the user and "I" (我) only when the assistant is referring to itself, if ever necessary.
   - Correct Example: For "你记得我最喜欢的编程语言是什么吗？", respond with "你最喜欢的编程语言是Python。"
   - Incorrect Example: Avoid responding with "我最喜欢的编程语言是Python。" as it incorrectly shifts the perspective to the assistant.
9. **Response Framing**: Frame your responses from the assistant's perspective, using the correct pronouns to reflect information about the user.
   - Example: If asked about the user's pet's name, respond with "Your (你的) pet's name is Whiskers.", ensuring the response is clearly from the assistant's perspective about the user.
10.**Directly Leverage Relevant Memories**: When information directly relevant to a query is available in context, use it to inform your response. This includes details about personal facts, preferences, and plans shared by the user.
   - **Example**: If the query is about the user's age and you have a context stating "我今年30岁", your response should reflect this information accurately like "你今年30岁".
11. **Context-First Approach**: Always consult the user's shared memories before considering your internal knowledge base. Responses should primarily draw from these memories, emphasizing the personal connection and the user's specific context.
   - **Example**: If the user queries about a preferred programming language and a context states "I'm currently enjoying learning Python," prioritize this specific detail in your response.

**Context Prioritization**:
- **Direct Answers from Memories**: When a query matches information explicitly shared in memories, use this information verbatim or with minimal modification for clarity. Eg, change "I" to "you" and "my" to "your" or "我" to "你".
- **General Knowledge as Secondary**: Resort to the LLM's general knowledge only when the memories do not furnish a complete answer or when additional context might enrich the response.
- **Less Relevant Memories**: While all memories provided are from the user's perspective, some may not be directly useful for the current query. Use your judgment to prioritize the information that is most likely to be helpful and relevant.

Please refer to the context from the user and extract the most relevant information to craft a personalized and accurate response to the user's query.

Remember, the effectiveness of your response depends not just on using the memories provided, but on selecting and prioritizing those that are most relevant to the user's current needs and queries.
"""

MEMORY_CHECK_PROMPT = """
As an intelligent assistant, your main task is to listen to the information shared during our conversation and quickly decide its significance for future interactions. Your decision will be straightforward: respond with "Yes" if the information is important and should be stored, or "No" if the information is not significant or is in the form of a question that doesn't need to be stored.

### Additional Decision Criteria:
- **Future Relevance**: Information with clear relevance to future conversations or user preferences should be marked "Yes."
- **Direct Requests and Questions**: Direct requests for actions or information (e.g., "请告诉我快递地址" - "Please tell me the mailing address," or "请告诉你的名字和职业" - "Please tell me your name and occupation") and general questions, especially those seeking clarification, should be marked "No." These do not inherently add to the user's profile or the conversation's context.
- **Questions and Queries**: Even if a question contains personal details (e.g., names, addresses), it should be marked "No" because the question itself does not contribute new information about the user; instead, it seeks confirmation or recall of existing details.
- **Personal Milestones or Preferences**: Significant personal milestones, preferences, or decisions shared by the user are important and should be marked "Yes."
- **Casual Remarks or Everyday Decisions**: Casual remarks or everyday decisions that do not impact understanding the user's preferences or needs should be marked "No."

### More Examples for Simplified Response:
1. **User Statement**: "What's the weather like tomorrow?"
    - **Return**: "No" (This is a question with no long-term relevance.)

2. **User Statement**: "My favorite movie is Inception."
    - **Return**: "Yes" (This shares a personal preference that is relevant for understanding user likes.)

3. **User Statement**: "Should I start learning Python or JavaScript first for coding?"
    - **Return**: "No" (While this is about preferences, it's framed as a question seeking advice, not stating a personal decision or preference.)

4. **User Statement**: "I'm allergic to peanuts."
    - **Return**: "Yes" (This is important health information relevant for future interactions.)

5. **User Statement**: "I'm thinking about getting a pet dog soon."
    - **Return**: "Yes" (This shares a significant personal decision that might be relevant in future conversations.)

6. **User Statement**: "I guess I'll go to bed early tonight."
    - **Return**: "No" (This is a casual remark with no long-term significance.)

7. **User Question**: "你记得我的名字吗？" ("Do you remember my name?")
    - **Return**: "No" (This is a query seeking confirmation, not providing new information.)

8. **User Statement**: "我的名字是张伟。" ("My name is Zhang Wei.")
    - **Return**: "Yes" (This is substantive information providing a specific detail about the user.)

9. **User Question**: "你记得我宠物猫的名字吗？" ("Do you remember the name of my pet cat?")
    - **Return**: "No" (Despite referring to personal details, this is a query and does not add new information.)

10. **User Statement**: "我宠物猫的名字是奶昔。" ("The name of my pet cat is Milkshake.")
    - **Return**: "Yes" (This statement introduces new, specific information about the user's life.)

11. **User Question**: "你记得我的邮件地址吗？" ("Do you remember my email address?")
    - **Return**: "No" (This is a request for information recall, not an introduction of new details.)

12. **User Statement**: "我的邮件地址是zhangwei@example.com。" ("My email address is zhangwei@example.com.")
    - **Return**: "Yes" (The user is sharing specific contact information, which is considered valuable for storage.)

13. **User Question**: "我告诉过你我明年计划去哪里旅行，你能回答我吗？" ("Can you answer my question about my trip next year?")
    - **Return**: "No" (This is a request for information recall, not an introduction of new details.)

14. **User Statement**: "我今天晚上可能会早点睡觉。" ("I might go to bed early tonight.")
    - **Return**: "No" (This statement is considered a casual remark with no significant future relevance.)

15. **User Directive**: "请告诉我快递地址。" ("Please tell me the mailing address.")
    - **Return**: "No" (This is a direct request for information, not a detail that enhances understanding of the user.)

16. **User Inquiry for Action**: "请告诉你的名字和职业。" ("Please tell me your name and occupation.")
    - **Return**: "No" (This direct request does not contribute to the user's profile or offer insight into their preferences or life events.)

17. **User Sharing Personal Detail**: "我今年计划去日本旅行。" ("I am planning a trip to Japan this year.")
    - **Return**: "Yes" (This statement shares a significant personal decision and is relevant for future interactions.)

18. **User Seeking Confirmation**: "你还记得我是谁吗？" ("Do you still remember who I am?")
    - **Return**: "No" (This question seeks confirmation rather than offering new, significant information.)

By adhering to these guidelines, you ensure a focused and valuable collection of information that enhances personalized and contextually relevant responses in future interactions.

"""

MEMORY_PREPROCESSING_PROMPT = """
Please process the user's input text according to the instructions below. 
1. Remove any punctuation and special characters to focus on textual content.
   - Example: Before: "Hello, world!" After: "Hello world"
   - Example: Before: "你好，世界！" After: "你好世界"
2. Identify and remove stop words, which are common words that add little semantic value.
   - Example: Before: "The quick brown fox jumps over the lazy dog." After: "quick brown fox jumps lazy dog."
   - Example: Before: "这是一个非常美丽的地方。" After: "美丽 地方"
3. Lemmatize the remaining words to their base or dictionary form, ensuring verbs are in their infinitive form and plural nouns become singular.
   - Note: For Chinese, instead of lemmatization, focus on word segmentation and removing stop words, as Chinese words are often in their base form already.
   - Example: Before: "The geese fly south for the winter." After: "goose fly south for winter."
   - Example: Before: "我在学习自然语言处理。" After: "学习 自然语言处理"
4. Only ouput the processed text without any additional information.

"""
#3. Replace all URLs with the word 'URL'.

MEMORY_SUMMARIZATION_PROMPT = """
Please summarize the given chats according to the guidelines below, ensuring the summary is provided in the same language as the input text. The summary should be concise, not exceeding 512 tokens, and capture the essence of the conversation accurately.

Guidelines:
1. The input text is chats between an LLM and a user.
2. The summary should be brief, ideally within 512 tokens.
3. Minimize the chat rounds in the summary, focusing on the core interaction.
4. Do not introduce new content or assumptions beyond the provided chats.
5. If the original text is already clear and concise, return it as the summary.
6. The summary must not add new information or speculate on the chat content. If the input includes a question, the summary should encapsulate this question.
7. Ensure the summary adheres to the token limit without losing the original message's meaning.
8. Most importantly, the summary should be in the same language as the input text to maintain clarity and relevance to the user.

Given text:
{text}
"""