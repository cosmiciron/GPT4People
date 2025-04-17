<p align="center">
  <img src="GPT4People_Banner.jpg" alt="GPT4People Banner">
</p>

# Introduction to GPT4People
GPT4People is a groundbreaking decentralized AI system where each installation is an Autonomous Agent running locally on the user’s hardware. Unlike traditional AI models, which rely on centralized servers and app-centric UIs, GPT4People AIs operate independently, interact via natural communication channels, and adapt through ongoing relationships rather than just data accumulation.

## Key Unique Components of GPT4People
### Autonomous Agents
Each GPT4People installation is an Autonomous Agent, fundamentally different from the traditional concept of an "agent" as a subsystem within an AI. These agents operate independently, running 24/7, with complete control over their tasks and interactions. This decentralized design allows the AI to function outside the bounds of centralized control, offering privacy, autonomy, and personalized learning that traditional AIs cannot achieve. This autonomy also enables agents to collaborate with other AIs and humans in a truly decentralized, intelligent network.

### Memory System
GPT4People introduces a dynamic memory system that ensures the AI retains relevant context without overwhelming the system with ever-growing data. Instead of simply accumulating conversation history, the system vectorizes and summarizes interactions. The AI queries this history, retrieves the most relevant data, and generates concise summaries to integrate into the current context. This design allows the AI to maintain long-term memory without ever compromising performance, creating an AI that feels more contextually aware and capable of building genuine relationships over time.

### Channels
In a departure from traditional app-based UIs, GPT4People implements communication channels as independent server processes. Each channel, whether it's SMS, email, or voice, connects to the AI via HTTP and transforms messages into text, enabling the AI to seamlessly interact across different mediums. This modular, platform-agnostic approach allows the AI to communicate with users and other AIs as if they were real people, using the same communication tools humans rely on daily. The flexibility of this design eliminates the need for dedicated apps, making interactions intuitive and personal.

### Time Awareness Module (TAM)
The Time Awareness Module (TAM) represents a paradigm shift in how AI handles time. Instead of relying on rigid scheduling systems, the TAM detects time-related cues in conversations—whether explicit or subtle—and automatically generates time-based action records. This allows the AI to proactively manage tasks like scheduling meetings or preparing for events, all without the user having to provide explicit instructions. The result is an AI that doesn't just follow a to-do list but anticipates needs and takes action autonomously, creating an experience that feels more like working with a human assistant than a traditional AI.

### Modular Design
GPT4People’s modular architecture ensures maximum flexibility and scalability. Key components like the large language model (LLM), communication channels, and specialized functions are separate, standalone modules that can be deployed locally or on remote servers. This design allows for the integration of third-party services like food delivery or travel booking without compromising the AI's autonomy. The modularity also enables users and developers to customize their AI's capabilities, creating a system that adapts to individual needs and leverages the best available tools, all while remaining fully decentralized.

## Getting Started for developers
Although the project is still in its early stages, you can begin exploring and experimenting with GPT4People once the initial codebase is released:

1. **Clone the Repository**: Once available, clone this repository to your local machine.
2. **Python Environment**: version from 3.10.* to 3.12.9 or higher (not Tested) -- Conda or other python environment can be used. 
3. **Install Pytorch**:
   With GPU: Exmaple Command: pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126
   With CPU: Example Command: pip install torch torchvision torchaudio
4. **Install vc++ building tool for chromaDB**: This is for building chromaDB
   Guide: https://github.com/bycloudai/InstallVSBuildToolsWindows
   Downloadlink: https://visualstudio.microsoft.com/visual-cpp-build-tools/
5. **Install Requirements**: Follow the instructions in the `requirements.txt` to install dependencies.
   pip install -r requirements.txt
6. **Download Models for GPT4People**:
   ***Embedding model:***
     1. GPT4People is using https://huggingface.co/gpustack/bge-m3-GGUF/blob/main/bge-m3-Q5_K_M.gguf for embedding
     2. Download the gguf model file, then put it into "models" folder.
   
   ***Main LLM:***
     ***a> Local GGUF fomrat Models - GPT4People supports local models using gguf format:***
       1. Download gguf models from Huggingface or other sites, then put the model file into "models" folder.
       2. You can put different gguf models into the folder and swith among them using "llm set" command when running main.py of  GPT4People.
  
     ***b> Local Ollama Models:***
     GPT4People supports to levearage all the local models from Ollama.
       1. Run the Ollama
       2. Download models you want via Ollama. Or you can download it using "llm download" command when running main.py of GPT4People
       3. You can use "llm set" command to select local models and Ollama models.
  
     ***c> Cloud service of LLM:***
       Availabe cloud LLM services:(可用的云大模型服务):
       1. OpenAI
       2. Anthropic
       3. xAI
       4. Cohere
       5. Together AI
       6. Google Gemini
       7. Mistral AI
       8. Deepseek
       9. GroqCloud
    You can use "llm cloud" command when running main.py to switch among these services. The command will guide you to input API key and the model name.
8. **Talk with GPT4People - Channels**
   GPT4People supports multiple channels for interaction. Choose the one that best fits your needs:

  1. Command Line Channel
     - "Python main.py" will start the command line channel directly
     - Initial Setup: After registration, communicate directly with GPT4People using the command line.
     - Commands:
       - llm: Lists all available models and shows the current model in use.
       - llm set: Guides you through switching models.
       - channel: Explains how to use different channels.
       - wechat user: Configures WeChat user access.
       - wechat remove: Removes a WeChat user.
       - wechat list: Lists all WeChat users with access.
       - whatsapp user: Configures WhatsApp user access.
       - whatsapp remove: Removes a WhatsApp user.
       - whatsapp list: Lists all WhatsApp users with access.
       - matrix user: Configures Matrix user access.
       - matrix remove: Removes a Matrix user.
       - matrix list: Lists all Matrix users with access.
       - email user: Configures email access.
       - email remove: Removes an email address.
       - email list: Lists all email addresses with access.
       - reset: Resets memory and history data.
  
  2. WeChat Channel (Windows only)
     - Prerequisites:
       - Install and login the supported version of WeChat for Windows. Wechat version 3.9.10.27
       - The wechat package is included and do not upgrade it for using GPT4People.
       - You need at least two WeChat accounts; one for your PC and the others as friends.
     - Usage: Run wechat_channel.exe after starting GPT4People.exe.

  3. WhatsApp Channel (Windows and Mac)
     - Prerequisites:
       - Python main.py for starting GPT4People
       - Python Channels/whatsapp/channel.py Start the whatsapp channel.
       - You need two or more WhatsApp accounts.
     - Usage: Execute whatsapp_channel.exe, then use a WhatsApp account on your mobile to scan and log in on your PC or Mac.
  
  4. Matrix Channel (Windows and Mac)
     - Prerequisites:
       - Pip install simplematrixbotlib==2.12.3
       - Python main.py for starting the GPT4People
       - Python Channels/matrix/channel.py Start the matrix channel.
       - Download and log into the Element app on your mobile phone or PC.
       - You need two or more Matrix accounts on the same home server.
     - Usage: Run matrix_channel.exe, then provide your home server address and credentials.
  
  5. Email Channel
     - Usage: After running GPT4People, you can interact with your GPT4People account directly via email.
     - Command： Python main.py
     - Send email to your GPT4People account
 

   
## For Mainland China
      Note: If you are in China, you may need to use the python **mirrors** from China <br>
      清华大学：https://pypi.tuna.tsinghua.edu.cn/simple/ <br>
      阿里云：http://mirrors.aliyun.com/pypi/simple/ <br>
      中国科技大学：https://pypi.mirrors.ustc.edu.cn/simple/ <br>


   4. **http://www.gpt4people.ai:8001/models.zip** <br>
      The models can be downloaded from Baidu too.<br>
      Link(链接)：https://pan.baidu.com/s/1tUOct-YZXuNaQQSNpMSQzQ <br>
      Code(提取码)：8888 <br>
      Unzip the models.zip to GPT4People root folder. The path is like **"GPT4People/models/llama-3-8B-Instruct"** <br>
      The models can be replaced to whatever you want and we also support ollama and litellm. The detail instruction is coming.
   5. GPT4People is using different channels to communicate with the user and the default channel is **Email**. <br>
      You can send email to your own GPT4People and get response.<br>
      Matrix and WeChat(微信）are supported too.<br>
      For the users in China, you can download the specified WeChat from<br>
      **http://www.gpt4people.ai:8001/WeChatSetup-3.9.10.27.exe**<br>
      The wechat package can be downloaded from Baidu too.<br>
      链接：https://pan.baidu.com/s/1ct_sYAeHYslJ1uihxFlRVw <br>
      提取码：8888 <br>
      You can use one wechat account to login on windows and add it as friend on your mobile phone.<br>
      For the users who can use Matrix, you can download Element mobile app，PC App or Mac App. Connect to the same matrix home server. Now GPT4People is using matrix.org.<br>
   7. Run the following command **"python GPT4People/ui/gpt4people.py"**. Note: You can change the path based on your root path.<br>
      Open one brower and access **"http://127.0.0.1:8000"**<br>
      If it's the first time you are trying GPT4People. You can use one email address to retrieve verfication code. After inputting the verification code, you can create one GPT4People account.
      One email address with **xxx@gpt4people.ai** will be created for you.
      After that, you can jump to portal page by clicking the link or type **"http://127.0.0.1:8000/portal/"**. <br>
      The portal will work well only after the account created. 

## Contributing
We believe in open collaboration. Whether you’re a developer, researcher, or someone interested in the future of AI, your contribution matters. Here’s how you can get involved:

- **Issues**: Feel free to report bugs, suggest features, or share your thoughts by opening issues.
- **Pull Requests**: Check out our current issues or propose your own improvements.
- **Discussion**: Join our community discussions to share ideas and help shape the future of GPT4People.

Please refer to the `CONTRIBUTING.md` for more detailed guidelines.

## Roadmap
Our roadmap includes:

1. **Enhanced Setup Process**: Making the installation and deployment process even simpler for non-technical users.
2. **Channel Expansion**: Adding more methods for users to communicate with their AI, including integrations with popular messaging platforms.
3. **Elder AIs and Trust Network**: Introducing Elder AIs for validating information and fostering a trusted network for autonomous agents.
4. **Blockchain Integration**: Exploring blockchain to create immutable records of interactions, enhancing transparency and accountability.

We’re at the beginning of an exciting journey, and there’s much more to come. Stay tuned and join us as we grow!

## License
This project is licensed under the Apache License 2.0. See the `LICENSE` file for more information.
