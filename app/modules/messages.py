class Messages:        
    def __init__(self, logger, bot, message):
            self.logger = logger            
            self.bot = bot
            self.message = message

    async def process_message(self):
        # Если сообщение от пользователя
        if self.message.author != self.bot.user:
            if self.message.content == 'Hello':
                await self.message.channel.send('World!')
