import asyncio
import datetime
import uuid
from src.telephony.outbound.dial import dial


TARGET_TIME = "23:00" # 24-hour format (HH:MM)
PHONE_NUMBER = "sizi13"
USER_ID = "voice_assistant_user_426" # Simran's web session ID

async def daily_job():
    print(f"Daily cron job started. Will call {PHONE_NUMBER} every day at {TARGET_TIME}.")
    
    while True:
        now = datetime.datetime.now()
        target_hour, target_minute = map(int, TARGET_TIME.split(":"))
        target = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
        
        # If the target time has already passed today, schedule for tomorrow
        if now >= target:
            target += datetime.timedelta(days=1)
            
        wait_seconds = (target - now).total_seconds()
        
        print(f"Next call scheduled for {target}. Waiting {wait_seconds:.0f} seconds...")
        await asyncio.sleep(wait_seconds)
        
        print(f"Time reached! Dispatching call to {PHONE_NUMBER}...")
        room_name = f"outbound-{uuid.uuid4().hex[:8]}"
        try:
            await dial(PHONE_NUMBER, room_name, USER_ID)
            print("Call dispatched successfully!")
        except Exception as e:
            print(f"Failed to dispatch call: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(daily_job())
    except KeyboardInterrupt:
        print("\nCron job stopped.")
