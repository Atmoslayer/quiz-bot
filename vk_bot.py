import argparse
import logging
import os

import redis
import vk_api
import random

from dotenv import load_dotenv
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.longpoll import VkLongPoll, VkEventType

from telegram_bot import State
from quiz_file_parser import get_quiz

logger = logging.getLogger('bot_logger')


NEW_QUESTION_BUTTON = 'Новый вопрос'
MY_SCORE_BUTTON = 'Мой счёт'
SURRENDER_BUTTON = 'Сдаться'


class BotLogsHandler(logging.Handler):

    def __init__(self, admin_chat_id, vk_api):
        self.admin_chat_id = admin_chat_id
        self.vk_api = vk_api
        super().__init__()

    def emit(self, record):
        log_entry = self.format(record)
        self.vk_api.messages.send(
            user_id=self.admin_chat_id,
            message=log_entry,
            random_id=random.randint(1, 1000)
        )


def get_vk_keyboard(buttons):
    keyboard = VkKeyboard(one_time=True)
    for button in buttons:
        keyboard.add_button(''.join(button), color=VkKeyboardColor.SECONDARY)

    return keyboard


def start(vk_api, vk_session, logger, redis_client, quiz):
    longpoll = VkLongPoll(vk_session)
    logger.info('VK bot started')
    message = 'Здравствуйте! Я бот для проверки викторин'
    keyboard = get_vk_keyboard(buttons=[NEW_QUESTION_BUTTON, MY_SCORE_BUTTON]).get_keyboard()
    for event in longpoll.listen():
        if event.type == VkEventType.MESSAGE_NEW and event.to_me and event.text == 'Начать':
            redis_client.set(f'State {event.user_id}', str(State.PROCESSED_START))
            vk_api.messages.send(
                user_id=event.user_id,
                message=message,
                keyboard=keyboard,
                random_id=random.randint(1, 1000)
            )
        elif event.type == VkEventType.MESSAGE_NEW and event.to_me:
            message_handler(vk_api, event, redis_client, quiz)


def message_handler(vk_api, event, redis_client, quiz):
    message = None
    user_id = event.peer_id
    user_state = redis_client.get(f'State {user_id}')
    if event.text == NEW_QUESTION_BUTTON \
            and (user_state == str(State.PROCESSED_START)
                 or user_state == str(State.ISSUED_SCORE)
                 or user_state == str(State.ISSUED_QUESTION)):
        keyboard = None
        message = random.choice(list(quiz.keys()))
        redis_client.set(user_id, message)
        redis_client.set(f'State {user_id}', str(State.ISSUED_QUESTION))

    elif event.text == SURRENDER_BUTTON \
            and (user_state == str(State.ISSUED_QUESTION)):
        question = redis_client.get(user_id)
        answer = quiz[question]
        message = f'Правильный ответ: {answer}'
        keyboard = get_vk_keyboard(buttons=[NEW_QUESTION_BUTTON, MY_SCORE_BUTTON]).get_keyboard()
        redis_client.set(f'State {user_id}', str(State.PROCESSED_START))

    elif event.text == MY_SCORE_BUTTON \
            and (user_state == str(State.PROCESSED_START)
                 or user_state == str(State.ISSUED_QUESTION)
                 or user_state == str(State.ANSWER_ACCEPTED)):
        user_score = redis_client.get(f'Score {user_id}')
        if user_score:
            message = f'Ваш текущий счёт: {user_score}'
        else:
            message = 'Пока что правильных ответов нет'
        keyboard = get_vk_keyboard(buttons=[NEW_QUESTION_BUTTON]).get_keyboard()
        redis_client.set(f'State {user_id}', str(State.ISSUED_SCORE))

    elif event.text and user_state == str(State.ISSUED_QUESTION):
        question = redis_client.get(user_id)
        answer = quiz[question]

        if event.text in answer:
            user_score = redis_client.get(f'Score {user_id}')
            if not user_score:
                user_score = 0
            user_score = int(user_score) + 1
            redis_client.set(f'Score {user_id}', user_score)
            message = f'Правильно! {answer}Поздравляю! Для следующего вопроса нажмите «{NEW_QUESTION_BUTTON}»'
            keyboard = get_vk_keyboard(buttons=[NEW_QUESTION_BUTTON, MY_SCORE_BUTTON]).get_keyboard()
            redis_client.set(f'State {user_id}', str(State.ANSWER_ACCEPTED))
        else:
            message = f'Ответ не верен. Попробуете ещё раз?'
            keyboard = get_vk_keyboard(buttons=[MY_SCORE_BUTTON, SURRENDER_BUTTON]).get_keyboard()
            redis_client.set(f'State {user_id}', str(State.ISSUED_QUESTION))

    if message:
        vk_api.messages.send(
            user_id=event.user_id,
            message=message,
            keyboard=keyboard,
            random_id=random.randint(1, 1000)
        )


def main(vk_api):
    load_dotenv()
    vk_token = os.getenv('VK_TOKEN')
    admin_chat_id = os.getenv('VK_ADMIN_CHAT_ID')
    host = os.getenv('HOST')
    port = os.getenv('PORT')
    db_password = os.getenv('DB_PASSWORD')

    parser = argparse.ArgumentParser(description='Questions parser')
    parser.add_argument('--questions_path', help='Enter path to save books', type=str)
    arguments = parser.parse_args()
    questions_path = arguments.questions_path

    vk_session = vk_api.VkApi(token=vk_token)
    vk_api = vk_session.get_api()

    redis_client = redis.Redis(
        host=host,
        port=port,
        password=db_password,
        decode_responses=True
    )

    logger.setLevel(logging.INFO)
    log_handler = BotLogsHandler(admin_chat_id, vk_api)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    log_handler.setFormatter(formatter)
    log_handler.setLevel(logging.INFO)

    logger.addHandler(log_handler)

    quiz = get_quiz(questions_path)

    start(vk_api, vk_session, logger, redis_client, quiz)


if __name__ == '__main__':
    main(vk_api)