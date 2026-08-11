import asyncio
import os
import re
from dotenv import load_dotenv
from livekit import api

load_dotenv(".env.local")

async def main():
    livekit_api = api.LiveKitAPI()
    try:
        # Delete existing trunks to avoid confusion
        trunks = await livekit_api.sip.list_sip_outbound_trunk(api.ListSIPOutboundTrunkRequest())
        for t in trunks.items:
            await livekit_api.sip.delete_sip_trunk(
                api.DeleteSIPTrunkRequest(sip_trunk_id=t.sip_trunk_id)
            )
        
        # Create correct trunk
        trunk = await livekit_api.sip.create_outbound_trunk(
            api.CreateSIPOutboundTrunkRequest(
                trunk=api.SIPOutboundTrunkInfo(
                    name="linphone-trunk",
                    address="sip.linphone.org",
                    transport=api.SIPTransport.SIP_TRANSPORT_TLS,
                    numbers=["sip:sizi13"]
                )
            )
        )
        print("TRUNK_ID:", trunk.sip_trunk_id)
        
        # Rewrite .env.local to update the trunk ID correctly
        with open(".env.local", "r") as f:
            lines = f.readlines()
            
        with open(".env.local", "w") as f:
            for line in lines:
                if not line.startswith("LIVEKIT_SIP_OUTBOUND_TRUNK_ID"):
                    f.write(line)
            f.write(f"LIVEKIT_SIP_OUTBOUND_TRUNK_ID={trunk.sip_trunk_id}\n")
    finally:
        await livekit_api.aclose()

asyncio.run(main())
