import argparse
import logging
import os
from enum import Enum
from functools import partial
import random
import redis
import telegram
from dotenv import load_dotenv
from telegram import ReplyKeyboardRemove, ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler, RegexHandler

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


class State(Enum):
    PROCESSED_START = 1
    ISSUED_QUESTION = 2
    ANSWER_ACCEPTED = 3
    ISSUED_SCORE = 4
    SURRENDER_HANDLED = 5


NEW_QUESTION_BUTTON = ['Новый вопрос']
MY_SCORE_BUTTON = ['Мой счёт']
SURRENDER_BUTTON = ['Сдаться']


def get_keyboard(buttons, one_time_keyboard=False):
    reply_markup = ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        one_time_keyboard=one_time_keyboard,
    )
    return reply_markup


def get_quiz(questions_path):
    quiz = {}
    with open(f'{questions_path}', 'r', encoding='KOI8-R') as file:
        question = ''
        for line in file:
            line = line.replace('\n', '')
            if 'Вопрос' in line:
                question = ''
                line = next(file)
                while not line == '\n':
                    question += line.replace('\n', ' ')
                    line = next(file)
            elif 'Ответ' in line:
                answer = ''
                line = next(file)
                while not line == '\n':
                    answer += line.replace('\n', ' ')
                    line = next(file)
                quiz[question] = answer
    return quiz


def start(update, context):
    buttons = [NEW_QUESTION_BUTTON, MY_SCORE_BUTTON]
    reply_markup = get_keyboard(buttons)
    message = 'Здравствуйте! Я бот для проверки викторин'
    update.message.reply_text(
        text=message,
        reply_markup=reply_markup,
    )
    return State.PROCESSED_START


def handle_new_question_request(update, context, redis_client, questions_path):
    user_id = update['message']['chat']['id']
    quiz = get_quiz(questions_path)
    reply_markup = ReplyKeyboardRemove()
    message = random.choice(list(quiz.keys()))
    redis_client.set(user_id, message)
    update.message.reply_text(
        text=message,
        reply_markup=reply_markup,
    )
    return State.ISSUED_QUESTION


def handle_solution_attempt(update, context, redis_client, questions_path):
    user_id = update['message']['chat']['id']
    buttons = [NEW_QUESTION_BUTTON, MY_SCORE_BUTTON]
    question = redis_client.get(user_id)
    quiz = get_quiz(questions_path)
    answer = quiz[question]
    text = update.message.text

    if text in answer:
        user_score = redis_client.get(f'Score {user_id}')
        if not user_score:
            user_score = 0
        user_score = int(user_score) + 1
        redis_client.set(f'Score {user_id}', user_score)
        message = f'Правильно! {answer}Поздравляю! Для следующего вопроса нажмите «{"".join(NEW_QUESTION_BUTTON)}»'
        reply_markup = get_keyboard(buttons)
        update.message.reply_text(
            text=message,
            reply_markup=reply_markup,
        )
        return State.ANSWER_ACCEPTED
    else:
        message = f'Ответ не верен. Попробуете ещё раз?'
        buttons = [MY_SCORE_BUTTON, SURRENDER_BUTTON]
        reply_markup = get_keyboard(buttons)
        update.message.reply_text(
            text=message,
            reply_markup=reply_markup,
        )
        return State.ISSUED_QUESTION


def handle_surrender(update, context, redis_client, questions_path):
    user_id = update['message']['chat']['id']
    question = redis_client.get(user_id)
    quiz = get_quiz(questions_path)
    answer = quiz[question]
    message = f'Правильный ответ: {answer}'
    buttons = [NEW_QUESTION_BUTTON, MY_SCORE_BUTTON]
    reply_markup = get_keyboard(buttons)
    update.message.reply_text(
        text=message,
        reply_markup=reply_markup,
    )
    return State.PROCESSED_START


def handle_user_score(update, context, redis_client):
    user_id = update['message']['chat']['id']
    user_score = redis_client.get(f'Score {user_id}')
    buttons = [NEW_QUESTION_BUTTON, ['']]
    if user_score:
        message = f'Ваш текущий счёт: {user_score}'
    else:
        message = 'Пока что правильных ответов нет'
    reply_markup = get_keyboard(buttons)
    update.message.reply_text(
        text=message,
        reply_markup=reply_markup,
    )
    return State.ISSUED_SCORE


def done(update, context):
    message = 'Работа завершена'
    buttons = [NEW_QUESTION_BUTTON, ['']]
    reply_markup = get_keyboard(buttons)
    update.message.reply_text(
        text=message,
        reply_markup=reply_markup,
    )
    return CommandHandler.END


def main():
    load_dotenv()
    tg_bot_token = os.getenv('TG_BOT_TOKEN')
    admin_chat_id = os.getenv('TG_ADMIN_CHAT_ID')
    host = os.getenv('HOST')
    port = os.getenv('PORT')
    db_password = os.getenv('DB_PASSWORD')
    bot = telegram.Bot(token=tg_bot_token)

    parser = argparse.ArgumentParser(description='Questions parser')
    parser.add_argument('--questions_path', help='Enter path to save books', type=str)
    arguments = parser.parse_args()
    questions_path = arguments.questions_path

    logger.setLevel(logging.INFO)
    log_handler = BotLogsHandler(bot, admin_chat_id)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    log_handler.setFormatter(formatter)
    log_handler.setLevel(logging.INFO)

    logger.addHandler(log_handler)

    redis_client = redis.Redis(
        host=host,
        port=port,
        password=db_password,
        decode_responses=True
    )

    updater = Updater(token=tg_bot_token, use_context=True)
    dispatcher = updater.dispatcher

    conversation_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            State.PROCESSED_START: [
                MessageHandler(
                    Filters.regex(''.join(NEW_QUESTION_BUTTON)),
                    partial(handle_new_question_request, redis_client=redis_client, questions_path=questions_path),
                ),
                MessageHandler(
                    Filters.regex(''.join(MY_SCORE_BUTTON)),
                    partial(handle_user_score, redis_client=redis_client),
                )
            ],
            State.ISSUED_QUESTION: [
                MessageHandler(
                    Filters.regex(''.join(MY_SCORE_BUTTON)),
                    partial(handle_user_score, redis_client=redis_client),
                ),
                MessageHandler(
                    Filters.regex(''.join(SURRENDER_BUTTON)),
                    partial(handle_surrender, redis_client=redis_client, questions_path=questions_path),
                ),
                MessageHandler(
                    Filters.text,
                    partial(handle_solution_attempt, redis_client=redis_client, questions_path=questions_path),
                ),
            ],
            State.ANSWER_ACCEPTED: [
                MessageHandler(
                    Filters.regex(''.join(MY_SCORE_BUTTON)),
                    partial(handle_user_score, redis_client=redis_client),
                ),
                MessageHandler(
                    Filters.regex(''.join(NEW_QUESTION_BUTTON)),
                    partial(handle_new_question_request, redis_client=redis_client, questions_path=questions_path),
                ),
            ],
            State.ISSUED_SCORE: [
                MessageHandler(
                    Filters.regex(''.join(NEW_QUESTION_BUTTON)),
                    partial(handle_new_question_request, redis_client=redis_client, questions_path=questions_path),
                ),
            ],
        },
        fallbacks=[
            MessageHandler(Filters.regex('Done'), done)
        ]
    )

    dispatcher.add_handler(conversation_handler)
    logger.info('The bot started')
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()