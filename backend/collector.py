import asyncio

class AsyncYieldCollector:
    # Initialize an asyncio queue for collecting yield messages from agents
    def __init__(self):
        self.queue = asyncio.Queue()
        
    #Callback to collect yielded messages from agents.
    async def on_yield(self, agent_name: str, message_content: str) -> None:
        await self.queue.put({
            "agent": agent_name,
            "content": message_content
        })
        
    #Retrieve the next message from the queue.
    async def get(self) -> dict:
        return await self.queue.get()