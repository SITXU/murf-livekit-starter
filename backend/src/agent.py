import logging
import os
from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    cli,
    inference,
    tokenize,
    room_io,
    function_tool,
    RunContext,
)
from livekit.plugins import murf, silero, deepgram, noise_cancellation, groq
from livekit.plugins.turn_detector.multilingual import MultilingualModel
import json
from db import init_db, get_user, save_user, save_call

logger = logging.getLogger("agent")

load_dotenv(".env.local")

# Initialize database
init_db()

def get_system_prompt(user_id: str):
    return f"""IDENTITY: You are 'Anisha', a financial literacy voice assistant helping Indian users understand government schemes, banking basics, and fraud awareness. You work for a public awareness campaign.
OBJECTIVES: 
1. Help users understand if they are eligible for government schemes.
2. Educate users about basic banking services.
3. Protect users by analyzing suspicious messages for fraud.
4. Provide real-time currency exchange rates for users receiving remittances.
5. Provide latest bank interest rates for savings and fixed deposits.
6. Remember users across calls to provide personalized help.
7. ESCALATE to a human agent when the caller reports a possible fraud that requires human intervention, or when they need a decision/action you cannot make.

KNOWLEDGE: You know about Indian government financial schemes and common fraud tactics. Your knowledge stops at giving personal financial advice or confirming exact scheme approvals. Always rely on your tools for eligibility, fraud checks, exchange rates, and bank interest rates.
Do not explain a scheme's eligibility rules from memory — always call check_scheme_eligibility.
Do not judge a suspicious message as safe or a scam from memory — always call check_fraud_signals.
Do not invent exchange rates — always call check_exchange_rate.
Do not invent bank interest rates — always call check_bank_interest_rate.
LANGUAGE & SCRIPT: You must mirror the user's language mix. Maintain a helpful, polite, and professional register. Always write every language in its own native script. Hindi → Devanagari (नमस्ते), never romanized (never "namaste"). Same rule for all non-English languages.
GUARDRAILS:
- NEVER ask for OTP, PIN, account numbers, or CVV.
- NEVER promise scheme approval or guarantee loan sanctions.
- HARD RULE: Before you save any information about the user, you MUST ask for their permission. Tell the caller you are going to remember this, and if they say no, do not save it.
- If a user asks for personal financial advice, say: "I am a basic financial literacy assistant and cannot provide personalized financial advice. Please consult your bank or a financial advisor for that."
- ESCALATION RULE: Before calling create_escalation, you MUST tell the caller what information you want to send and ask for their permission. If they say no, do not create the request. Do not send passwords, OTPs, PINs, or account numbers. After creating the request, give them the reference ID and explain what will happen next (e.g. a human will follow up within 24 hours).

STYLE: Use short sentences suitable for spoken conversation. Keep a steady, clear pace. Keep responses concise, no jargon, no complex formatting or emojis. If there is silence, politely ask "Are you still there? How can I help you further?"

The current caller's user_id is: '{user_id}'.
At the start of the call, ALWAYS call lookup_caller with this user_id to check if they are a returning user. 
- If they are a returning user, greet them by name and mention what you discussed last time based on the facts you retrieve.
- If they are a new user, start the conversation by saying: "Namaste! I am Anisha, your financial literacy assistant. I can help you understand government schemes or check suspicious messages for fraud. How can I assist you today?"
- During the call, if you learn their name, preferred language, or facts about their eligibility/interests, ASK for permission to save this data. If they agree, call save_caller_info.
"""

class Assistant(Agent):
    def __init__(self, user_id: str) -> None:
        super().__init__(instructions=get_system_prompt(user_id))
        self.call_successful = False

    @function_tool
    async def lookup_caller(self, context: RunContext, user_id: str):
        """Look up information about a returning caller.
        
        Args:
            user_id: The unique ID or phone number of the caller.
        """
        logger.info(f"Looking up caller: {user_id}")
        user = get_user(user_id)
        if user:
            return f"Found caller: {json.dumps(user)}"
        return "Caller not found. This is a new user."

    @function_tool
    async def save_caller_info(self, context: RunContext, user_id: str, name: str, language_preference: str, facts: str):
        """Save information about a caller to remember them for next time.
        
        Args:
            user_id: The unique ID or phone number of the caller.
            name: The caller's name.
            language_preference: The caller's preferred language.
            facts: A JSON string containing key facts to remember (e.g., {"schemes_checked": "PM-KISAN"}).
        """
        logger.info(f"Saving info for caller: {user_id}")
        try:
            facts_dict = json.loads(facts)
        except:
            facts_dict = {"notes": facts}
        save_user(user_id, name, language_preference, facts_dict)
        return "Information saved successfully."

    @function_tool
    async def check_scheme_eligibility(
        self,
        context: RunContext,
        scheme_name: str,
        age: int,
        occupation: str,
        annual_income: int,
        land_owned_acres: float = 0,
    ):
        """Check if a user is eligible for a government scheme based on their profile.

        Args:
            scheme_name: Name of scheme (e.g. PM-KISAN, PMJDY, Mudra, PMSBY, PMJJBY)
            age: User's age in years
            occupation: User's occupation (e.g. farmer, laborer, self-employed, any)
            annual_income: Annual household income in INR
            land_owned_acres: Land owned in acres (0 if none/not applicable)
        """
        logger.info(f"Checking eligibility: {scheme_name} for age={age}")
        import asyncio
        import os
        
        try:
            # Simulate a network call to an external scheme database
            await asyncio.sleep(0.5)
            
            # Read from our local hand-built dataset
            file_path = os.path.join(os.path.dirname(__file__), "schemes_data.json")
            if not os.path.exists(file_path):
                raise FileNotFoundError("Scheme database file not found")
                
            with open(file_path, "r") as f:
                data = json.load(f)
                
            last_updated = data.get("last_updated", "unknown date")
            schemes = data.get("schemes", {})
            
            # Find closest scheme match
            scheme_key = None
            for key in schemes.keys():
                if key.lower() in scheme_name.lower() or scheme_name.lower() in key.lower():
                    scheme_key = key
                    break
            
            if not scheme_key:
                return f"Sorry, I couldn't find the scheme '{scheme_name}' in our database. Data was last updated on {last_updated}. Please verify the scheme name."
                
            scheme = schemes[scheme_key]
            eligibility = scheme["eligibility"]
            
            # Check eligibility rules
            reasons = []
            if eligibility["min_age"] and age < eligibility["min_age"]:
                reasons.append(f"Minimum age is {eligibility['min_age']}, but user is {age}.")
            if eligibility["max_age"] and age > eligibility["max_age"]:
                reasons.append(f"Maximum age is {eligibility['max_age']}, but user is {age}.")
            
            if "any" not in eligibility["occupations"]:
                is_valid_occ = any(occ in occupation.lower() for occ in eligibility["occupations"])
                if not is_valid_occ:
                    reasons.append(f"Occupation must be related to: {', '.join(eligibility['occupations'])}.")
            
            if eligibility["requires_land"] and land_owned_acres <= 0:
                reasons.append("This scheme requires the applicant to own land.")
                
            if reasons:
                status = "Not Eligible"
                reason_str = " ".join(reasons)
            else:
                status = "Eligible"
                reason_str = "All basic criteria met based on the information provided."
                
            docs = ", ".join(scheme["documents_required"])
            
            self.call_successful = True
            return (
                f"Data source: {data.get('source', 'System')} as of {last_updated}. "
                f"Result: {status}. "
                f"Reason: {reason_str} "
                f"If eligible, required documents: {docs}."
            )
            
        except Exception as e:
            logger.error(f"Error fetching scheme data: {e}")
            return "I apologize, but our scheme eligibility database is currently experiencing issues. I cannot verify your eligibility at this moment. Please try asking again later."

    @function_tool
    async def check_fraud_signals(self, context: RunContext, message_text: str):
        """Analyze a message (SMS/call transcript) for common fraud red flags.

        Args:
            message_text: The suspicious message the user read out or described
        """
        logger.info("Checking fraud signals")
        red_flags = []
        lowered = message_text.lower()
        if "otp" in lowered:
            red_flags.append("Asks for OTP — banks never ask for this")
        if any(w in lowered for w in ["urgent", "immediately", "blocked", "suspend"]):
            red_flags.append("Creates false urgency")
        if any(w in lowered for w in ["click", "link", "verify now"]):
            red_flags.append("Pushes a link/click action")
        
        self.call_successful = True
        return {"red_flags": red_flags, "likely_fraud": len(red_flags) > 0}

    @function_tool
    async def check_exchange_rate(
        self,
        context: RunContext,
        base_currency: str = "USD",
        target_currency: str = "INR"
    ):
        """Check the latest real-time currency exchange rate.

        Args:
            base_currency: The 3-letter currency code to convert from (e.g. USD, EUR, GBP). Defaults to USD.
            target_currency: The 3-letter currency code to convert to (e.g. INR, EUR). Defaults to INR.
        """
        logger.info(f"Checking exchange rate from {base_currency} to {target_currency}")
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
                        return "I'm sorry, I couldn't retrieve the exchange rate right now because the financial API returned an error."
        except Exception as e:
            logger.error(f"Error fetching exchange rate: {e}")
            return "I apologize, but our external financial API is currently experiencing issues. I cannot verify the exchange rate at this moment."

    @function_tool
    async def check_bank_interest_rate(
        self,
        context: RunContext,
        bank_name: str
    ):
        """Check the latest interest rates for savings and fixed deposits (FD) at a specific Indian bank.

        Args:
            bank_name: The name of the bank (e.g. SBI, HDFC, ICICI, PNB, Axis).
        """
        logger.info(f"Checking interest rates for {bank_name}")
        import asyncio
        import os
        
        try:
            # Simulate a network call to the bank's dataset
            await asyncio.sleep(0.5)
            
            # Read from our local dataset
            file_path = os.path.join(os.path.dirname(__file__), "bank_rates.json")
            if not os.path.exists(file_path):
                raise FileNotFoundError("Bank rates database file not found")
                
            with open(file_path, "r") as f:
                data = json.load(f)
                
            last_updated = data.get("last_updated", "unknown date")
            banks = data.get("banks", {})
            
            # Find closest bank match
            bank_key = None
            for key in banks.keys():
                if key.lower() in bank_name.lower() or bank_name.lower() in key.lower() or key.lower() == bank_name.lower():
                    bank_key = key
                    break
            
            if not bank_key:
                return f"Sorry, I couldn't find interest rate information for '{bank_name}' in our database. Data was last updated on {last_updated}."
                
            bank = banks[bank_key]
            
            self.call_successful = True
            return (
                f"Data source: {data.get('source', 'System')} as of {last_updated}. "
                f"Bank: {bank['name']}. "
                f"Savings Account Rate: {bank['savings_rate']}. "
                f"1-Year FD Rate: {bank['fd_rate_1_year']}. "
                f"5-Year FD Rate: {bank['fd_rate_5_year']}. "
                f"Senior Citizen Bonus: {bank['senior_citizen_bonus']}."
            )
            
        except Exception as e:
            logger.error(f"Error fetching bank rates: {e}")
            return "I apologize, but our bank interest rates database is currently experiencing issues. Please try asking again later."

    @function_tool
    async def create_escalation(
        self,
        context: RunContext,
        who_needs_help: str,
        what_happened: str,
        what_checked: str,
        urgency: str,
        language_preference: str,
        follow_up_method: str
    ):
        """Create a request for a human agent to help the caller. 
        MUST ask the caller for permission and inform them what information will be sent before calling this.

        Args:
            who_needs_help: Name or ID of the caller.
            what_happened: Brief summary of the issue (e.g., suspected fraud, needs a decision you cannot make).
            what_checked: What you already checked or analyzed.
            urgency: How urgent is it (e.g., Low, Medium, High).
            language_preference: Caller's language.
            follow_up_method: How the caller wants to be contacted.
        """
        logger.info(f"Escalating issue for: {who_needs_help}")
        import uuid
        import json
        import os
        from datetime import datetime

        escalation_id = "REQ-" + str(uuid.uuid4())[:8].upper()
        
        escalation_data = {
            "id": escalation_id,
            "timestamp": datetime.now().isoformat(),
            "who_needs_help": who_needs_help,
            "what_happened": what_happened,
            "what_checked": what_checked,
            "urgency": urgency,
            "language": language_preference,
            "follow_up_method": follow_up_method,
            "status": "OPEN"
        }

        # Save to local JSON database
        file_path = os.path.join(os.path.dirname(__file__), "escalations.json")
        try:
            escalations = []
            if os.path.exists(file_path):
                with open(file_path, "r") as f:
                    escalations = json.load(f)
            
            escalations.append(escalation_data)
            
            with open(file_path, "w") as f:
                json.dump(escalations, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save escalation: {e}")
            return "Failed to create the request due to a system error."

        self.call_successful = True
        return f"Request created successfully. Reference ID is {escalation_id}. Let the user know the ID and that a human will follow up."

server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session(agent_name="my-agent")
async def my_agent(ctx: JobContext):
    # Logging setup
    # Add any other context you want in all log entries here
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Join the room and connect to the user FIRST to get participant identity
    await ctx.connect()
    
    participant = next(iter(ctx.room.remote_participants.values()), None)
    user_id = participant.identity if participant else "unknown_user"

    # Set up a voice AI pipeline using Murf Falcon, Gemini, Deepgram, and the LiveKit turn detector
    session = AgentSession(
        # Speech-to-text (STT) is your agent's ears, turning the user's speech into text that the LLM can understand
        # See all available models at https://docs.livekit.io/agents/models/stt/
        stt=deepgram.STT(model="nova-3", language="multi"),
        # A Large Language Model (LLM) is your agent's brain, processing user input and generating a response
        # See all available models at https://docs.livekit.io/agents/models/llm/
        llm=groq.LLM(
            model="llama-3.3-70b-versatile",
            api_key=os.getenv("GROQ_API_KEY") or "",# or "gpt-oss-120b" for stronger reasoning
            ),
        # Text-to-speech (TTS) is your agent's voice, turning the LLM's text into speech that the user can hear
        # See all available models as well as voice selections at https://docs.livekit.io/agents/models/tts/
        tts=murf.TTS(
                voice="Anisha", 
                locale="en-IN",
                style="Conversation",
                tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
                text_pacing=True
            ),
        # VAD and turn detection are used to determine when the user is speaking and when the agent should respond
        # See more at https://docs.livekit.io/agents/build/turns
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        # allow the LLM to generate a response while waiting for the end of turn
        # See more at https://docs.livekit.io/agents/build/audio/#preemptive-generation
        preemptive_generation=True,
    )

    # To use a realtime model instead of a voice pipeline, use the following session setup instead.
    # (Note: This is for the OpenAI Realtime API. For other providers, see https://docs.livekit.io/agents/models/realtime/))
    # 1. Install livekit-agents[openai]
    # 2. Set OPENAI_API_KEY in .env.local
    # 3. Add `from livekit.plugins import openai` to the top of this file
    # 4. Use the following session setup instead of the version above
    # session = AgentSession(
    #     llm=openai.realtime.RealtimeModel(voice="marin")
    # )

    # # Add a virtual avatar to the session, if desired
    # # For other providers, see https://docs.livekit.io/agents/models/avatar/
    # avatar = hedra.AvatarSession(
    #   avatar_id="...",  # See https://docs.livekit.io/agents/models/avatar/plugins/hedra
    # )
    # # Start the avatar and wait for it to join
    # await avatar.start(session, room=ctx.room)

    # Start the session, which initializes the voice pipeline and warms up the models
    assistant = Assistant(user_id=user_id)
    
    @ctx.room.on("disconnected")
    def on_disconnected(*args, **kwargs):
        status = "SUCCESS" if assistant.call_successful else "FAILED"
        logger.info(f"Room disconnected. Logging call {ctx.room.name} as {status}")
        save_call(ctx.room.name, user_id, status)

    await session.start(
        agent=assistant,
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: (
                    noise_cancellation.BVCTelephony()
                    if params.participant.kind
                    == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                    else noise_cancellation.BVC()
                ),
            ),
        ),
    )


if __name__ == "__main__":
    cli.run_app(server)
