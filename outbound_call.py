import os
import asyncio
import subprocess
from dotenv import load_dotenv
from livekit import api

load_dotenv()

async def make_outbound_call(phone_number: str):
    """
    1. Generates a LiveKit Token for the AI Agent.
    2. Starts the AI Agent in a new room.
    3. Uses LiveKit SIP API to dial the phone number via Vobiz.
    """
    # Clean room name
    room_name = f"outbound_{phone_number.replace('+', '').replace(' ', '')}"
    identity = "ai-agent"

    # 2. Start the AI Agent in the background
    print(f"🤖 Starting AI Agent for room: {room_name}")
    # Using subprocess to run the agent script independently with the new framework's 'connect' command
    # It will automatically use LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET from .env
    subprocess.Popen(["python", "livekit_agent.py", "connect", "--room", room_name])

    # 3. Trigger the SIP Outbound Call via Vobiz
    sip_trunk_id = os.getenv("VOBIZ_SIP_TRUNK_ID")
    if not sip_trunk_id:
        print("❌ Error: VOBIZ_SIP_TRUNK_ID is not set in .env")
        print("Please add VOBIZ_SIP_TRUNK_ID=ST_XXXXXX to your .env file from LiveKit dashboard.")
        return

    lkapi = api.LiveKitAPI(
        url=os.getenv("LIVEKIT_URL"),
        api_key=os.getenv("LIVEKIT_API_KEY"),
        api_secret=os.getenv("LIVEKIT_API_SECRET")
    )

    print(f"📞 Dialing {phone_number} via Vobiz...")
    try:
        # This sends the command to LiveKit to initiate the SIP call
        await lkapi.sip.create_sip_participant(
            api.CreateSIPParticipantRequest(
                sip_trunk_id=sip_trunk_id,
                sip_call_to=phone_number,
                room_name=room_name
            )
        )
        print("✅ SIP Call Request Sent Successfully!")
    except Exception as e:
        print(f"❌ Failed to initiate call: {e}")
    finally:
        await lkapi.aclose()

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        target_number = sys.argv[1]
        asyncio.run(make_outbound_call(target_number))
    else:
        print("Usage: python outbound_call.py <phone_number_with_country_code>")
        print("Example: python outbound_call.py +919999999999")
