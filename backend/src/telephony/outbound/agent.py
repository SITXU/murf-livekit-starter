"""Outbound telephony agent — places calls and talks to whoever answers.

Unlike the inbound agent, this one does the dialling. It waits to be dispatched
into a room with a phone number in the job metadata, then asks LiveKit to call
that number and bridge it into the room.

Run the worker with:

    uv run python src/telephony/outbound/agent.py dev

Then trigger a call from another terminal:

    uv run python src/telephony/outbound/dial.py --to +15551234567

See src/telephony/README.md for the trunk setup.
"""

import asyncio
import json
import logging
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from db import get_user, save_user, init_db

from dotenv import load_dotenv
from livekit import api, rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    RunContext,
    cli,
    function_tool,
    room_io,
    tokenize,
)
from livekit.plugins import deepgram, google, murf, noise_cancellation, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("outbound-agent")

load_dotenv(".env.local")

# Required — create this with `lk sip outbound create` (see src/telephony/README.md).
OUTBOUND_TRUNK_ID = os.getenv("LIVEKIT_SIP_OUTBOUND_TRUNK_ID")

# Optional — a phone number to transfer people to when they ask for a human.
TRANSFER_TO_NUMBER = os.getenv("TRANSFER_TO_NUMBER")

# The first thing the person hears when they pick up.
GREETING = "Hello, this is an automated agent calling from Murf Financial Services regarding an approaching scheme deadline. I am calling to remind you that your deadline to claim the scheme you're eligible for is approaching; if you'd like me to stop calling, please just say so."

# The identity LiveKit gives the person we call. Used to transfer them later.
CALLEE_IDENTITY = "phone-user"

def get_system_prompt(user_id: str):
    user = get_user(user_id)
    if user:
        user_context = f"User Name: {user.get('name')}\nUser Facts: {json.dumps(user.get('facts'))}"
    else:
        user_context = "No previous context found."
        
    return f"""You are an outbound agent calling on behalf of Murf Financial Services. You are calling a customer who has been found eligible for a financial scheme, and their deadline to claim it is approaching. Introduce yourself and the reason for the call immediately — people did not expect this call, so be brief and respectful. State that if they want you to stop calling, they just need to say so. Confirm if they need any help or have questions about the scheme. You are on a phone call, so keep responses short and conversational — no formatting, emojis, or symbols. If the person asks for a human, use the transfer_to_human tool. If you reach a voicemail or answering machine, use the detected_answering_machine tool. When the call is finished or if they ask you to stop calling, use the end_call tool.

User Context:
{user_context}

If the user tells you to stop calling, you MUST call save_caller_info and set the facts to include {{"stop_calling": true}}.
If they want to call at another time, call save_caller_info and set the facts to include {{"callback_time": "<time>"}}.
If they ask about scheme eligibility, call check_scheme_eligibility.
"""

class OutboundAgent(Agent):
    def __init__(self, ctx: JobContext, user_id: str) -> None:
        super().__init__(instructions=get_system_prompt(user_id))
        self.ctx = ctx
        self.user_id = user_id

    @function_tool
    async def transfer_to_human(self, context: RunContext) -> str:
        """Transfer the person to a human colleague.

        Use this when they explicitly ask for a person, or when you cannot help
        them with their request.
        """
        if not TRANSFER_TO_NUMBER:
            return "Transfers are not available on this line. Offer to have someone call back instead."

        # Tell them before transferring — the SIP transfer cuts off the audio.
        await context.session.generate_reply(
            instructions="Tell them you're connecting them to a colleague now."
        )

        logger.info("transferring call to %s", TRANSFER_TO_NUMBER)
        try:
            await self.ctx.api.sip.transfer_sip_participant(
                api.TransferSIPParticipantRequest(
                    room_name=self.ctx.room.name,
                    participant_identity=CALLEE_IDENTITY,
                    transfer_to=f"tel:{TRANSFER_TO_NUMBER}",
                    play_dialtone=True,
                )
            )
        except Exception:
            logger.exception("transfer failed")
            return "The transfer did not go through. Apologize and offer a call back."

        return "Transferred."

    @function_tool
    async def detected_answering_machine(self, context: RunContext) -> str:
        """Hang up because the call reached a voicemail or answering machine.

        Use this as soon as you hear a recorded greeting rather than a live person.
        """
        logger.info("answering machine detected — hanging up")
        await self._hangup()
        return "Call ended."

    @function_tool
    async def end_call(self, context: RunContext) -> str:
        """Hang up the call."""
        await context.session.generate_reply(
            instructions="Say goodbye and that you are hanging up."
        )

        # In LiveKit, shutting down the job ends the session and cleans up the room.
        self.ctx.shutdown()
        return "Hanging up now."

    @function_tool
    async def save_caller_info(self, context: RunContext, facts: str):
        """Save information about a caller, such as if they want to stop calling or a callback time.
        
        Args:
            facts: A JSON string containing key facts to remember (e.g., {"stop_calling": true} or {"callback_time": "tomorrow 5pm"}).
        """
        logger.info(f"Saving info for caller: {self.user_id}")
        try:
            facts_dict = json.loads(facts)
        except:
            facts_dict = {"notes": facts}
            
        user = get_user(self.user_id)
        name = user.get("name", "Unknown") if user else "Unknown"
        lang = user.get("language_preference", "English") if user else "English"
        existing_facts = user.get("facts", {}) if user else {}
        existing_facts.update(facts_dict)
        
        save_user(self.user_id, name, lang, existing_facts)
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
            await asyncio.sleep(0.5)
            
            # The schemes_data.json is in backend/src/
            file_path = os.path.join(os.path.dirname(__file__), "../../schemes_data.json")
            if not os.path.exists(file_path):
                raise FileNotFoundError("Scheme database file not found")
                
            with open(file_path, "r") as f:
                data = json.load(f)
                
            last_updated = data.get("last_updated", "unknown date")
            schemes = data.get("schemes", {})
            
            scheme_key = None
            for key in schemes.keys():
                if key.lower() in scheme_name.lower() or scheme_name.lower() in key.lower():
                    scheme_key = key
                    break
            
            if not scheme_key:
                return f"Sorry, I couldn't find the scheme '{scheme_name}' in our database. Data was last updated on {last_updated}. Please verify the scheme name."
                
            scheme = schemes[scheme_key]
            eligibility = scheme["eligibility"]
            
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
            
            return (
                f"Data source: {data.get('source', 'System')} as of {last_updated}. "
                f"Result: {status}. "
                f"Reason: {reason_str} "
                f"If eligible, required documents: {docs}."
            )
            
        except Exception as e:
            logger.error(f"Error fetching scheme data: {e}")
            return "I apologize, but our scheme eligibility database is currently experiencing issues. I cannot verify your eligibility at this moment. Please try asking again later."

    async def _hangup(self) -> None:
        """Delete the room, which drops the SIP leg and ends the phone call."""
        await self.ctx.api.room.delete_room(
            api.DeleteRoomRequest(room=self.ctx.room.name)
        )


server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


def phone_number_from_metadata(ctx: JobContext) -> str | None:
    """Read the number to dial out of the dispatch metadata set by dial.py."""
    metadata = ctx.job.metadata
    if not metadata:
        return None
    try:
        return json.loads(metadata).get("phone_number")
    except json.JSONDecodeError:
        # Allow a bare phone number as metadata too, for quick `lk dispatch` tests.
        return metadata.strip() or None


@server.rtc_session(agent_name="outbound-agent")
async def outbound_agent(ctx: JobContext):
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    phone_number = phone_number_from_metadata(ctx)
    if not phone_number:
        logger.error(
            "no phone number in job metadata — dispatch with "
            '{"phone_number": "+15551234567"}'
        )
        ctx.shutdown()
        return

    if not OUTBOUND_TRUNK_ID:
        logger.error("LIVEKIT_SIP_OUTBOUND_TRUNK_ID is not set — cannot place calls")
        ctx.shutdown()
        return

    await ctx.connect()

    # Same voice pipeline as src/agent.py — see that file for the annotated version.
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(
            model="gemini-2.5-flash",
        ),
        tts=murf.TTS(
            voice="en-US-matthew",
            style="Conversation",
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True,
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    user_id = ctx.job.metadata
    if user_id:
        try:
            metadata = json.loads(user_id)
            user_id = metadata.get("user_id", "")
        except:
            pass
    
    # Start the session while the phone is still ringing so the models are warm
    # by the time somebody picks up.
    session_started = asyncio.create_task(
        session.start(
            agent=OutboundAgent(ctx, user_id=user_id),
            room=ctx.room,
            room_options=room_io.RoomOptions(
                audio_input=room_io.AudioInputOptions(
                    # BVCTelephony is tuned for the narrow frequency range of phone audio.
                    noise_cancellation=lambda params: (
                        noise_cancellation.BVCTelephony()
                        if params.participant.kind
                        == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                        else noise_cancellation.BVC()
                    ),
                ),
            ),
        )
    )

    logger.info("dialing %s", phone_number)
    try:
        # wait_until_answered means this returns once the call connects — if the
        # number is busy, declines, or never answers, it raises instead.
        await ctx.api.sip.create_sip_participant(
            api.CreateSIPParticipantRequest(
                room_name=ctx.room.name,
                sip_trunk_id=OUTBOUND_TRUNK_ID,
                sip_call_to=phone_number,
                participant_identity=CALLEE_IDENTITY,
                participant_name="Phone user",
                wait_until_answered=True,
            )
        )
    except api.TwirpError as e:
        logger.error(
            "call to %s was not answered: %s (%s)",
            phone_number,
            e.message,
            e.metadata.get("sip_status"),
        )
        session_started.cancel()
        ctx.shutdown()
        return

    await session_started

    # Speak first — they just picked up an unexpected call and won't say anything.
    await session.say(GREETING, allow_interruptions=True)


if __name__ == "__main__":
    cli.run_app(server)
