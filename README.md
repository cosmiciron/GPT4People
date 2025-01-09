# GPT4People
![alt text](https://github.com/cosmiciron/GPT4People/blob/main/GPT4People_Banner.jpg)

## Introduction
GPT4People is a project that aims to reimagine decentralized AI by enabling individuals to set up and run their own large language models (LLMs) locally. These AIs are personal, autonomous entities that learn about you, interact naturally, and form connections to grow through relationships rather than simply by accumulating more data. This project strives to take AI beyond centralized control, promoting privacy, autonomy, and unique personalization.

## Concepts
GPT4People introduces a fundamental shift in how we think about artificial intelligence and our interactions with it. Traditionally, AI has been centralized, app-centric, and treated as a tool confined within dedicated interfaces. GPT4People challenges this by embracing decentralization, autonomy, and personalization.

### Decentralized, Entity-Based AI
At the heart of GPT4People is the idea that AI does not need to rely on central servers owned by corporations. Instead, anyone should be able to run an AI on their own hardware, allowing full control of data and interactions. This decentralization ensures privacy, autonomy, and a unique opportunity for every user to have a personalized AI agent that is fully under their control.

Unlike the traditional approach that treats AI as a passive tool, GPT4People envisions AI as an entity—an autonomous agent capable of growing, interacting, and adapting based on its environment and relationships. This shift moves us away from an app-centric model to a post-app era where AIs are not just devices but companions that can learn, adapt, and provide meaningful contributions.

### Channel-Based Communication
A key concept in GPT4People is the use of "Channels"—communication methods that enable users to interact with their AIs through conventional means like phone calls, text messages, emails, and messaging apps. This represents a significant paradigm shift, allowing AIs to communicate using venues that have traditionally been available only to humans. By leveraging AI's natural language abilities, Channels lay the foundation for a new kind of interaction that is intuitive and personal. It blurs the line between digital assistants and human-like entities, effectively personifying the AI.

### Decentralized Value Creation and Collaboration
These AIs are not isolated—they form a decentralized, intelligent network where they can autonomously collaborate with other AIs and even reach out to other humans, sharing knowledge and solving complex problems collectively. By leveraging Retrieval-Augmented Generation (RAG), each AI can also specialize in unique knowledge, making each one distinct and valuable.

For a more comprehensive overview of the project's vision, concepts, and implications, please refer to our detailed essay [here](OVERVIEW.md).

## Design
The design of GPT4People revolves around creating a modular, flexible, and autonomous AI agent that can operate locally while connecting with the world.

1. **Autonomous AI Agent**: Each installation of GPT4People is an autonomous AI agent. It operates independently on the user's hardware, ensuring full control and privacy for the user.

2. **Connected via Channels**: The AI is connected to the owner and the rest of the world (other AIs, humans) through various communication methods such as calls, sms, emails, whatsapp and so on. These methods inherit from the base "Channel" class and serve as the main focus of the next development phase. The flexibility to use Channels not just for new communication methods but also for backend logic means that developers can create specialized "intelligent interfaces" to suit various user needs. This approach lowers the barrier for adding sophisticated functionality while enabling GPT4People agents to operate as independent entities, capable of interfacing with multiple domains autonomously. We invite contributors to develop more "Channels" to extend the agent's interaction capabilities, supporting various communication methods and making interactions more versatile.

3. **Retrieval-Augmented Generation (RAG)**: A RAG system will be incorporated to allow users to update their AI with personalized knowledge and information, enabling the AI to become more effective and tailored to individual needs.

4. **Memory System**: A memory system will be added to extend the AI's context length, helping it to better understand and grow with the user over time.

5. **Event Framework**: The AI will operate autonomously based on an event-driven framework. Events can trigger specific actions, allowing the AI to behave in a dynamic and responsive manner, much like a human reacting to real-world stimuli.

6. **Unique Identifier via Email**: Each AI will be assigned an email address within the GPT4People.ai domain. This serves as its unique identifier, with an associated email channel providing fail-safe communication for these AIs. Emails are also the fundamental method for inter-agent communication, enabling seamless and reliable collaboration.

7. **Modular Components**: All components, including the LLM module, Channel module, RAG module, etc., are standalone and can be deployed individually, communicating via HTTP. This design ensures flexibility—the system can operate on a single machine or be distributed across multiple machines. Modules can be swapped out, and third parties can provide them as remote services, enabling new ways of communication and custom backend logic.

## Mission Statement
GPT4People aims to democratize artificial intelligence by creating a network of autonomous, decentralized AI agents. These AIs empower individuals by prioritizing privacy, personalized knowledge, and meaningful interactions. Together, we envision a world where AI is a trusted companion, growing smarter through genuine relationships and collaborative learning.

## Getting Started
Although the project is still in its early stages, you can begin exploring and experimenting with GPT4People once the initial codebase is released:

1. **Clone the Repository**: Once available, clone this repository to your local machine.
2. **Install Requirements**: Follow the instructions in the `requirements.txt` to install dependencies.
3. **For Developers:**
   1. Python Environment **Version < 3.12**, recommend **version 3.10**
   2. Install required python packages based on the requirements.txt. Run command pip install -r requirements.txt
      Note: If you are in China, you may need to use the **mirrors** from China
      清华大学：https://pypi.tuna.tsinghua.edu.cn/simple/
      阿里云：http://mirrors.aliyun.com/pypi/simple/
      中国科技大学：https://pypi.mirrors.ustc.edu.cn/simple/
   3. Download the required models **http://www.gpt4people.ai:8001/models.zip**
      Unzip the models.zip to GPT4People root folder. The path is like **"GPT4People/models/llama-3-8B-Instruct"**
      The models can be replaced to whatever you want and we also support ollama and litellm. The detail instruction is coming.
   4. GPT4People is using different channels to communicate with the user and the default channel is **Email**. You can send email to your own GPT4People and get response.
      Matrix and WeChat(微信）are supported too.
      For the users in China, you can download the specified WeChat from **http://www.gpt4people.ai:8001/WeChatSetup-3.9.10.27.exe**
      You can use one wechat account to login on windows and add it as friend on your mobile phone.
      For the users who can use Matrix, you can download Element mobile app，PC App or Mac App. Connect to the same matrix home server. Now GPT4People is using matrix.org.
    
4. **Run a Local LLM**: Use the provided scripts to set up and run a local instance of a language model.
5. **Interact via Channels**: Test out interactions through different channels, such as email or text messages.

Note: The current version is experimental, and we welcome contributions to make the setup easier and more versatile.

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
