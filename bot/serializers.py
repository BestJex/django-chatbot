# -*- coding:utf-8 -*-
from rest_framework import serializers
from chatbot.chatbot import ChatBot
from chatbot.models import statement_table_name
from django_redis import get_redis_connection
from threading import Thread


cache = get_redis_connection("default")


class DjangoChatBot(ChatBot):
    def initialize(self):
        # Static question and answer pairs are saved to the cache
        def load():
            self.logger.info('start loading static qa pairs to the cache')
            for statement in self.storage.filter(statement_table_name, type=0):
                if not cache.hexists('static_qa', statement.question):
                    cache.hset('static_qa', statement.question, statement.answer)
            self.logger.info('loading data is complete')

        t = Thread(target=load)
        t.start()


chatbot = DjangoChatBot(
    'django',
    # storage={
    #     'import_path': 'chatbot.storage.SQLStorage',
    #     'database_uri': 'mysql+pymysql://root:123456@10.1.196.29:3306/chatbot'
    # },
)


class QuestionSerializer(serializers.Serializer):
    question = serializers.CharField(max_length=1000)


class LearnSerializer(serializers.Serializer):
    question = serializers.CharField(max_length=1000)
    answer = serializers.CharField(max_length=1000)
    category = serializers.CharField(max_length=100, default='其他')
    type_ = serializers.IntegerField(default=0)
    parameters = serializers.CharField(max_length=255, allow_blank=True, required=False)
    extractor = serializers.CharField(max_length=255, allow_blank=True, required=False)

    def learn(self):
        return chatbot.learn(**self.validated_data)

    def validate_type_(self, value):
        if value not in (0, 1):
            raise serializers.ValidationError('the type must be 0 or 1')
        return value

