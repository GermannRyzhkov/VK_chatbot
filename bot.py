import logging
import random
import requests
from pony.orm import db_session
import models
from models import UserState, Registration
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
import handlers
import dispatcher

try:
    import settings
except ImportError:
    exit('Copy settings.py.default and set TOKEN')

logger = logging.getLogger('bot')


def configure_logging(log):
    log.setLevel(logging.DEBUG)

    stream_handler = logging.StreamHandler()
    file_handler = logging.FileHandler('bot.log', encoding='utf8')
    formatter = logging.Formatter(fmt='%(asctime)s - %(levelname)s - %(message)s',
                                  datefmt='%d-%m-%Y %H:%M')

    log.addHandler(stream_handler)
    log.addHandler(file_handler)

    stream_handler.setLevel(logging.WARNING)
    stream_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)


class Bot:
    """
    Бот для заказа авиабилетов в vk.com

    Получает событие из переписки с пользователем.

    Поддерживает:
     - Ввод городов отправления и прибытия
     - Дату отправления
     - Количество пассажиров
     - Комментарий пользователя и его номер телефона

    При некорректном вводе сообщения, просит повторить текущий шаг.
    Если некорректное сообщение получено на на шаге определения места назначения, сценарий завершается.

    После обработки сообщения пользователя отправлет ему ответ с требованием к следующему шагу сценария.

    Поддерживает вспомогательные команды:
    /ticket - Запускает сценарий бронирования билета с самого начала.
    /help - Предоставляет справку о работе программы.

    Use Python 3.8
    """

    def __init__(self, group_id, token, log=logger):

        """

        :param group_id: id группы ВКонтакте
        :param token: секретный ключ доступа
        :param log: объект, используемый для логирования сообщений
        """
        dispatcher.run()
        self.group_id = group_id
        self.token = token
        self.vk = vk_api.VkApi(token=self.token)
        self.bot_longpoll = VkBotLongPoll(vk=self.vk, group_id=self.group_id)
        self.api = self.vk.get_api()
        self.log = log

    def run(self):
        """
        Выполняет запуск бота
        """
        for event in self.bot_longpoll.listen():
            try:
                self.on_event(event)
            except Exception as error:
                self.log.exception(f'Что-то пошло не так {error}')

    @db_session
    def on_event(self, event):
        """
        Обрабатывает событие, полученное из группы.
        Отправляет ответ адресату.
        :param event: Новое событие из группы ВКонтакте
        """
        if event.type != VkBotEventType.MESSAGE_NEW:
            answer_message = 'Невозможно обработать ваше сообщение, ' \
                             'для начала работы отправьте сообщение боту в личном чате'
            self.log.debug(f'Я пока не умею обрабатывать сообщения типа {event.type}')
            self.api.messages.send(
                message=answer_message,
                random_id=random.randint(0, 2 ** 20),
                peer_id=event.object['from_id']
            )
            return

        user_id = event.object['message']['peer_id']
        user_message = event.object['message']['text']
        state = UserState.get(user_id=user_id)

        # Search user id in user states, if True → continue scenario.
        if state:
            if user_message == settings.TICKET_PATTERN:
                answer_message = settings.INTENTS['Ticket']['answer']
                self.send_text(answer_message, user_id)
                state.delete()
            elif user_message == settings.HELP_PATTERN:
                answer_message = settings.INTENTS['Help']['answer']
                self.send_text(answer_message, user_id)
            else:
                self.continue_scenario(user_id, state, user_message)

        # For new user. Search intent in config.
        else:
            for intent_name in settings.INTENTS.keys():
                intent = settings.INTENTS[intent_name]
                if any(token in user_message.lower() for token in intent['tokens']):
                    self.log.info(f'User {user_id} gets intent {intent_name}')
                    if intent['answer']:
                        self.send_text(intent['answer'], user_id)
                        break
                    else:
                        self.start_scenario(intent['scenario'], user_id)
                        break
            else:
                answer_message = settings.INTENTS['Help']['answer']
                self.send_text(answer_message, user_id)

    def send_text(self, answer_message, user_id):
        self.api.messages.send(
            message=answer_message,
            random_id=random.randint(0, 2 ** 20),
            peer_id=user_id
        )

    def send_image(self, image, user_id):
        upload_url = self.api.photos.getMessagesUploadServer(group_id=settings.GROUP_ID)['upload_url']
        upload_data = requests.post(url=upload_url, files={'photo': ('image.png', image, 'image/png')}).json()
        attachment_data = self.api.photos.saveMessagesPhoto(**upload_data)

        owner_id = attachment_data[0]['owner_id']
        media_id = attachment_data[0]['id']
        attachment = f'photo{owner_id}_{media_id}'

        self.api.messages.send(
            attachment=attachment,
            random_id=random.randint(0, 2 ** 20),
            peer_id=user_id
        )

    def send_step(self, step, user_id, answer_message, context):
        if answer_message:
            self.send_text(answer_message.format(**context), user_id)
        if 'image' in step:
            handler = getattr(handlers, step['image'])
            image = handler(answer_message, context)
            self.send_image(image, user_id)

    @db_session
    def start_scenario(self, scenario_name, user_id):
        scenario = settings.SCENARIOS[scenario_name]
        first_step = scenario['first_step']
        step = scenario['steps'][first_step]
        answer_message = step['initial_text']
        self.send_step(step, user_id, answer_message, context={})
        UserState(
            user_id=user_id,
            scenario_name=scenario_name,
            step_name=first_step,
            context=dict(
                want_break=None,
                alternative_failure_text=None
            )
        )
        self.log.debug(f'User {user_id} have started scenario {scenario_name}')

    @db_session
    def continue_scenario(self, user_id, state, user_message):
        steps = settings.SCENARIOS[state.scenario_name]['steps']
        step = steps[state.step_name]
        handler = getattr(handlers, step['handler'])
        if handler(text=user_message, context=state.context):
            if state.context['want_break']:
                answer_message = step['answer_text_2']
                self.send_step(step, user_id, answer_message, state.context)
                state.step_name = 'choose_departure_city'
                state.context['want_break'] = False
            else:
                answer_message = step['answer_text']
                self.send_step(step, user_id, answer_message, state.context)
                next_step_name = step['next_step']
                if next_step_name:
                    state.step_name = next_step_name
                else:
                    self.log.debug(f'User {user_id} has finished scenario {state.scenario_name} '
                                   f'with parameters {state.context}')
                    Registration(phone_number=state.context['phone_number'])
                    state.delete()
        else:
            if state.context['alternative_failure_text']:
                answer_message = step['alternative_failure_text']
                self.send_step(step, user_id, answer_message, state.context)
                state.context['alternative_failure_text'] = False
            else:
                answer_message = step['failure_text']
                self.send_step(step, user_id, answer_message, state.context)


if __name__ == '__main__':
    configure_logging(log=logger)
    bot = Bot(group_id=settings.GROUP_ID, token=settings.TOKEN)
    bot.run()
