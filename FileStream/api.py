from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pyrogram import Client
from FileStream.utils.file_properties import get_file_info, send_file
from FileStream.utils.database import Database
from FileStream.config import Telegram
import logging

app = FastAPI()
logger = logging.getLogger(__name__)

# Initialize Pyrogram and Database
bot = Client(
    name="StreamBot",
    api_id=Telegram.API_ID,
    api_hash=Telegram.API_HASH,
    bot_token=Telegram.BOT_TOKEN
)
db = Database(Telegram.DATABASE_URL, "FileStream")

class StreamRequest(BaseModel):
    chat_id: int
    search_query: str

async def generate_stream_from_message_id(message_id: int, chat_id: int):
    """Generate stream/dl link from message ID."""
    try:
        async with bot:
            message = await bot.get_messages(chat_id, message_id)
            if not message or not message.caption:
                logger.warning(f"No valid message found for ID {message_id} in chat {chat_id}")
                return None
            file_info = get_file_info(message)
            if not file_info["file_id"]:
                logger.warning(f"No file in message {message_id}")
                return None
            inserted_id = await db.add_file(file_info)
            await send_file(bot, inserted_id, file_info["file_id"], message)
            return f"{Telegram.FQDN}:{Telegram.PORT}/dl/{inserted_id}"
    except Exception as e:
        logger.error(f"Error generating stream for message {message_id}: {str(e)}")
        return None

@app.post("/api/get_stream")
async def get_stream(request: StreamRequest):
    """Search for media in chat and return stream/dl link."""
    try:
        async with bot:
            async for message in bot.get_chat_history(request.chat_id):
                if message.caption and request.search_query in message.caption:
                    stream_url = await generate_stream_from_message_id(message.id, request.chat_id)
                    if stream_url:
                        return {"stream_url": stream_url}
            logger.warning(f"No matching media found for query {request.search_query} in chat {request.chat_id}")
            raise HTTPException(status_code=404, detail="Stream not found")
    except Exception as e:
        logger.error(f"Error in get_stream: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")