import logging
import os

import telegram
from dotenv import load_dotenv
from telegram import ReplyKeyboardRemove
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters


logger = logging.getLogger('bot_logger')


class BotLogsHandler(logging.Handler):

    def __init__(self, bot, admin_chat_id):
        self.bot = bot
        self.admin_chat_id = admin_chat_id
        super().__init__()

    def emit(self, record):
        log_entry = self.format(record)
        self.bot.send_message(
            chat_id=self.admin_chat_id,
            text=log_entry,
        )


def start(update, context):
    reply_markup = ReplyKeyboardRemove()
    update.message.reply_text(
        text='Здравствуйте!',
        reply_markup=reply_markup,
    )


def main():
    load_dotenv()
    tg_bot_token = os.getenv('TG_BOT_TOKEN')
    admin_chat_id = os.getenv('TG_ADMIN_CHAT_ID')
    bot = telegram.Bot(token=tg_bot_token)

    logger.setLevel(logging.INFO)
    log_handler = BotLogsHandler(bot, admin_chat_id)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    log_handler.setFormatter(formatter)
    log_handler.setLevel(logging.INFO)

    logger.addHandler(log_handler)

    updater = Updater(token=tg_bot_token, use_context=True)
    dispatcher = updater.dispatcher

    start_handler = CommandHandler('start', start)
    dispatcher.add_handler(start_handler)
    logger.info('The bot started')
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()