Building ArthMitra: A Financial Literacy Voice Agent for India
When it comes to financial literacy, many people face a massive barrier: the jargon, the complex documents, and the sheer volume of information. Whether it's understanding eligibility for government schemes like PM-KISAN, checking the latest savings interest rates, or identifying a fraudulent SMS, navigating financial services can be daunting.

Typing out these questions or reading dense articles isn't always accessible. That's why I built ArthMitra — a voice-first financial literacy assistant designed for Indian users. With a voice interface, users can simply talk to Anisha in their native language or code-mixed Hinglish, making financial guidance as accessible as calling a friend.

Here is the story of how I built it during the 10 Days of Voice Agents — VoiceForBharat Edition, and a guide on how you can build your own.

Important Features
To make Anisha truly useful, I focused on a few core features:

An Indian Voice Powered by Murf Falcon
Anisha's voice is powered by Murf Falcon, using the "Anisha" (Indian English) voice profile. It’s incredibly fast (sub-130ms time-to-first-audio) and sounds natural, which is crucial for building trust in financial conversations.

Tools for Real-Time Data and Datasets
LLMs are great, but they shouldn't guess financial data. I gave Anisha tools to access real information:

check_exchange_rate: Fetches live currency exchange rates (e.g., USD to INR) using the open Frankfurter API. Perfect for users receiving remittances.

check_scheme_eligibility: Checks eligibility for government schemes (like PMJDY or Mudra) using a robust local dataset, preventing hallucination.

check_bank_interest_rate: Retrieves the latest FD and savings rates for major Indian banks.

Agent Handoffs and Human Escalation
Not every query can be handled by a generalist. If a user asks about complex government schemes, Anisha hands off the conversation to a Government Scheme Specialist Agent (using a different voice profile, "Samar"). If a user is facing a complex fraud issue, Anisha has a create_escalation tool to seamlessly escalate the request to a human support team.

Memory for Returning Users
Using lookup_caller and save_caller_info tools, Anisha remembers past interactions. If a returning user calls, she greets them by name and recalls their previous questions, making the experience highly personalized.

Support for Indian Languages and Code-Mixing
Anisha seamlessly handles code-mixed conversations, allowing users to speak in a natural blend of Hindi and English.

The Difficult Parts: Lessons Learned
Building a voice agent isn't always smooth sailing. Here are two challenges I faced and how I solved them:

Challenge 1: Code-Mixed Pronunciation Issues
Initially, when users spoke in Hindi, the LLM (Llama 3.3) would sometimes respond in romanized Hindi (e.g., "namaste, aap kaise ho"). When fed to the Murf TTS, this romanized text sounded robotic and unnatural because the TTS engine tried to read it with English pronunciation rules.

The Fix: I added a strict guardrail to the system prompt: "Always write every language in its own native script. Hindi → Devanagari (नमस्ते), never romanized." This simple prompt engineering fix ensured the TTS received Devanagari text, which it pronounced flawlessly.

Challenge 2: Hallucinating Scheme Eligibility
Government schemes have very specific age, income, and occupation rules. The LLM would confidently (and incorrectly) invent eligibility criteria.

The Fix: I instructed the agent to never explain schemes from memory. Instead, I built a local JSON dataset of scheme rules and created the check_scheme_eligibility tool. Now, the agent fetches deterministic answers based on the user's profile.

Build Your Own Voice Agent
Want to build your own voice agent? It's easier than you think. You need four main components:

Speech-to-Text (STT): Deepgram (turns user speech into text)

LLM: Groq / Llama 3.3 (the brain that decides what to say)

Text-to-Speech (TTS): Murf Falcon (turns text back into voice instantly)

Real-time Transport: LiveKit (handles the low-latency audio streaming)

Setup Instructions
You can inspect the full code in my public repository: murf-livekit-starter.

Clone the project and install dependencies You will need Python (with uv) for the backend and Node.js (with pnpm) for the frontend.
Bash
git clone https://github.com/SITXU/murf-livekit-starter.git
cd murf-livekit-starter

Install backend
cd backend
uv sync

Install frontend
cd ../frontend
pnpm install

Configure API Keys securely Create a .env.local file in both the backend/ and frontend/ folders. Never commit this file to GitHub. You will need keys from LiveKit, Murf AI, Deepgram, and Groq.
Code snippet
LIVEKIT_URL=your_url
LIVEKIT_API_KEY=your_key
LIVEKIT_API_SECRET=your_secret
MURF_API_KEY=your_murf_key
DEEPGRAM_API_KEY=your_deepgram_key
GROQ_API_KEY=your_groq_key

Run the agent Start the LiveKit server, the Python backend agent, and the Next.js frontend:
Bash

Terminal 1:
livekit-server --dev

Terminal 2:
cd backend && uv run python src/agent.py dev

Terminal 3:
cd frontend && pnpm dev
Open http://localhost:3000 in your browser, click "Talk to Anisha", and test the conversation!

Evidence: Under the Hood
Here is a quick look at how the check_exchange_rate tool is implemented in Python using the LiveKit Agents SDK. The @function_tool decorator automatically exposes this function to the LLM.

Python

python
@function_tool
async def check_exchange_rate(
    self,
    context: RunContext,
    base_currency: str = "USD",
    target_currency: str = "INR"
):
    """Check the latest real-time currency exchange rate."""
    import aiohttp

    url = f"https://api.frankfurter.app/latest?from={base_currency}&to={target_currency}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    rate = data["rates"].get(target_currency.upper())
                    date = data.get("date", "today")
                    self.call_successful = True
                    return f"Data source: Frankfurter API as of {date}. The exchange rate is 1 {base_currency.upper()} = {rate} {target_currency.upper()}."
                else:
                    return "I'm sorry, I couldn't retrieve the exchange rate right now."
    except Exception as e:
        return "Our financial API is experiencing issues."
By connecting real-time APIs and local datasets to a voice interface powered by Murf Falcon, we can build tools that truly expand financial literacy. Happy building!
