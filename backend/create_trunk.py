import asyncio
import os
from dotenv import load_dotenv
from livekit import api

load_dotenv(".env.local")

async def main():
    livekit_api = api.LiveKitAPI()
    try:
        trunk = await livekit_api.sip.create_sip_outbound_trunk(
            api.CreateSIPOutboundTrunkRequest(
                trunk=api.SIPOutboundTrunkInfo(
                    name="linphone-trunk",
                    address="sip.linphone.org",
                    transport=api.SIPTransport.SIP_TRANSPORT_TLS,
                    numbers=["sip:sizi1313@sip.linphone.org"]
                )
            )
        )
        print("TRUNK_ID:", trunk.sip_trunk_id)
        
        with open(".env.local", "a") as f:
            f.write(f"\nLIVEKIT_SIP_OUTBOUND_TRUNK_ID={trunk.sip_trunk_id}\n")
    finally:
        await livekit_api.aclose()

asyncio.run(main())
