import unittest
import os.path
from copy import deepcopy

from pony.orm import db_session, rollback

import settings
from handlers import handle_ask_date
import dispatcher
from bot import Bot
from models import UserState, Registration
from generate_ticket import generate_ticket, SOURCE_PATH
from unittest.mock import Mock, patch
from vk_api.bot_longpoll import VkBotMessageEvent


def isolate_db(test_func):
    def wrapper(*args, **kwargs):
        with db_session:
            test_func(*args, **kwargs)
            rollback()

    return wrapper


class BotTest(unittest.TestCase):

    def setUp(self):

        self.RAW_EVENT = {
            'type': 'message_new',
            'object': {
                'message': {'date': 1611906766,
                            'from_id': 34796333,
                            'id': 869,
                            'out': 0,
                            'peer_id': 34796333,
                            'text': 'hi',
                            'conversation_message_id': 869,
                            'fwd_messages': [],
                            'important': False,
                            'random_id': 0,
                            'attachments': [],
                            'is_hidden': False
                            },
                'client_info': {
                    'button_actions': [
                        'text', 'vkpay', 'open_app', 'location', 'open_link', 'intent_subscribe', 'intent_unsubscribe'
                    ],
                    'keyboard': True,
                    'inline_keyboard': True,
                    'carousel': False,
                    'lang_id': 0
                }
            },
            'group_id': 200177230,
            'event_id': '9a731ea16cc0d7d5e1fa12f073ed76a2ea63cc47'
        }
        self.user_id = self.RAW_EVENT['object']['message']['peer_id']

    def test_run(self):
        obj = {1: 2}
        call_count = 5
        events = [obj] * call_count
        with patch('bot.vk_api.VkApi'):
            with patch('bot.VkBotLongPoll'):
                bot = Bot('', '')
                bot.on_event = Mock()
                bot.send_image = Mock()
                bot.bot_longpoll.listen = Mock(return_value=events)
                bot.run()
                bot.on_event.assert_called_with(obj)
                assert bot.on_event.call_count == call_count

    CONTEXT = {
        'departure_city': 'МОСКВА',
        'destination_city': 'ТОКИО'
    }

    dispatcher.run()

    INPUTS = [
        'Здравствуйте!',
        '/help',
        'Заказ',
        'Санкт-Петербург',
        CONTEXT['departure_city'],
        CONTEXT['destination_city'],
        '45-01-2021',
        '12-03-2030',
        '14-01-2021',
        '6',
        '2',
        'Василий Васильев',
        '0',
        '1',
        'chatbot@test.com',
        'TEST',
        'не знаю',
        'да',
        '123456'
    ]

    handle_ask_date(INPUTS[8], CONTEXT)
    FLIGHT_DATE = CONTEXT['dates_to_choose'][int(INPUTS[10]) - 1]

    EXPECTED_OUTPUTS = [
        settings.INTENTS['Greetings']['answer'],
        settings.INTENTS['Help']['answer'],
        settings.SCENARIOS['order_ticket']['steps']['choose_departure_city']['initial_text'],
        settings.SCENARIOS['order_ticket']['steps']['choose_departure_city']['failure_text'],
        settings.SCENARIOS['order_ticket']['steps']['choose_departure_city']['answer_text'],
        settings.SCENARIOS['order_ticket']['steps']['choose_destination_city']['answer_text'],
        settings.SCENARIOS['order_ticket']['steps']['ask_date']['failure_text'],
        settings.SCENARIOS['order_ticket']['steps']['ask_date']['alternative_failure_text'],
        settings.SCENARIOS['order_ticket']['steps']['ask_date']['answer_text'].format(
            _dates_list=CONTEXT['_dates_list']
        ),
        settings.SCENARIOS['order_ticket']['steps']['choose_date']['failure_text'],
        settings.SCENARIOS['order_ticket']['steps']['choose_date']['answer_text'],
        settings.SCENARIOS['order_ticket']['steps']['choose_name']['answer_text'],
        settings.SCENARIOS['order_ticket']['steps']['choose_passengers_amount']['failure_text'],
        settings.SCENARIOS['order_ticket']['steps']['choose_passengers_amount']['answer_text'],
        settings.SCENARIOS['order_ticket']['steps']['choose_email']['answer_text'],
        settings.SCENARIOS['order_ticket']['steps']['write_comment']['answer_text'].format(
            departure_city=INPUTS[4].upper(),
            destination_city=INPUTS[5].upper(),
            flight_datetime=FLIGHT_DATE,
            name=INPUTS[11],
            passengers_amount=INPUTS[13],
            email=INPUTS[14],
            comment=INPUTS[15]
        ),
        settings.SCENARIOS['order_ticket']['steps']['get_feedback']['failure_text'],
        settings.SCENARIOS['order_ticket']['steps']['get_feedback']['answer_text'],
        settings.SCENARIOS['order_ticket']['steps']['get_phone_number']['answer_text'].format(phone_number=INPUTS[18])
    ]

    @isolate_db
    def test_run_ok(self):
        send_mock = Mock()
        api_mock = Mock()
        api_mock.messages.send = send_mock

        events = []
        for input_text in self.INPUTS:
            event = deepcopy(self.RAW_EVENT)
            event['object']['message']['text'] = input_text
            events.append(VkBotMessageEvent(event))

        long_poller_mock = Mock()
        long_poller_mock.listen = Mock(return_value=events)

        with patch('bot.VkBotLongPoll', return_value=long_poller_mock):
            bot = Bot(' ', ' ')
            bot.api = api_mock
            bot.send_image = Mock()
            bot.run()
        assert send_mock.call_count == len(self.INPUTS)

        real_outputs = []
        for call in send_mock.call_args_list:
            args, kwargs = call
            real_outputs.append(kwargs['message'])
        assert real_outputs == self.EXPECTED_OUTPUTS

    @isolate_db
    def test_choose_incorrect_destination_city(self):
        input_text = 'Канберра'
        event = deepcopy(self.RAW_EVENT)
        event['object']['message']['text'] = input_text
        raw_event = VkBotMessageEvent(event)

        with patch('bot.vk_api.VkApi'):
            with patch('bot.VkBotLongPoll'):
                bot = Bot(' ', ' ')
                UserState(
                    user_id=self.user_id,
                    scenario_name='order_ticket',
                    step_name='choose_destination_city',
                    context={'departure_city': 'МОСКВА'}
                )
                bot.on_event(raw_event)
                test_state = UserState.get(user_id=self.user_id)
        assert test_state.step_name == settings.SCENARIOS['order_ticket']['first_step']

    @isolate_db
    def test_negative_feedback(self):
        input_text = 'нет'
        event = deepcopy(self.RAW_EVENT)
        event['object']['message']['text'] = input_text
        raw_event = VkBotMessageEvent(event)

        with patch('bot.vk_api.VkApi'):
            with patch('bot.VkBotLongPoll'):
                bot = Bot(' ', ' ')
                UserState(
                    user_id=self.user_id,
                    scenario_name='order_ticket',
                    step_name='get_feedback',
                    context={}
                )
                bot.on_event(raw_event)
                test_state = UserState.get(user_id=self.user_id)
        assert test_state.step_name == settings.SCENARIOS['order_ticket']['first_step']

    def test_generate_ticket(self):
        context = dict(
            name='qwerty',
            email='ytrtr@ya.ru',
            flight_date='1480',
            flight_time='1012',
            departure_city='errer',
            destination_city='kmkmnm'
        )

        relative_ticket_path = 'files/ticket-file'
        relative_avatar_path = 'files/test-image.png'
        avatar_path = os.path.normpath(os.path.join(SOURCE_PATH, relative_avatar_path))
        expected_output_path = os.path.normpath(os.path.join(SOURCE_PATH, relative_ticket_path))

        with open(avatar_path, 'rb') as avatar_file:
            avatar_mock = Mock()
            avatar_mock.content = avatar_file.read()

        with patch('requests.get', return_value=avatar_mock):
            ticket_file = generate_ticket(context)

        with open(expected_output_path, 'rb') as expected_output:
            expected_bytes = expected_output.read()

        assert ticket_file.read() == expected_bytes


if __name__ == '__main__':
    unittest.main()
