import logging

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
from livekit.plugins import murf, silero, deepgram, noise_cancellation, cerebras
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")

load_dotenv(".env.local")

# Change this prompt to change what your voice agent does.
# See README.md for example prompts (customer support, language tutor, receptionist).
SYSTEM_PROMPT = """You are a financial literacy assistant helping Indian users understand government schemes, banking basics, and fraud awareness. Speak in simple, clear language (mix Hindi/English if the user does). Do not explain a scheme's eligibility rules from memory — always call check_scheme_eligibility. Do not judge a suspicious message as safe or a scam from memory — always call check_fraud_signals. Keep responses concise, no jargon, no complex formatting or emojis."""

class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=SYSTEM_PROMPT)

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
            occupation: User's occupation (e.g. farmer, laborer, self-employed)
            annual_income: Annual household income in INR
            land_owned_acres: Land owned in acres (0 if none/not applicable)
        """
        logger.info(f"Checking eligibility: {scheme_name} for age={age}")
        # TODO: replace with real rule lookup / RAG-retrieved scheme rules
        return f"Checked {scheme_name} eligibility for profile: age {age}, {occupation}, income {annual_income}, land {land_owned_acres} acres."

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
        return {"red_flags": red_flags, "likely_fraud": len(red_flags) > 0}

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

    # Set up a voice AI pipeline using Murf Falcon, Gemini, Deepgram, and the LiveKit turn detector
    session = AgentSession(
        # Speech-to-text (STT) is your agent's ears, turning the user's speech into text that the LLM can understand
        # See all available models at https://docs.livekit.io/agents/models/stt/
        stt=deepgram.STT(model="nova-3"),
        # A Large Language Model (LLM) is your agent's brain, processing user input and generating a response
        # See all available models at https://docs.livekit.io/agents/models/llm/
        llm=cerebras.LLM(
            model="gemma-4-31b",  # or "gpt-oss-120b" for stronger reasoning
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
    await session.start(
        agent=Assistant(),
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

    # Join the room and connect to the user
    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(server)
