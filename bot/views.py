from rest_framework import status, generics
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from wechatpy import parse_message
from wechatpy.exceptions import InvalidSignatureException
from wechatpy.utils import check_signature
from wechatpy.replies import TextReply
from django.http import HttpResponse
from django.conf import settings
# from django.core.cache import cache
import json
from .serializers import QuestionSerializer, LearnSerializer, chatbot, cache


if hasattr(settings, 'COOKIE_MAX_AGE'):
    COOKIE_MAX_AGE = settings.COOKIE_MAX_AGE
else:
    COOKIE_MAX_AGE = 120


# Create your views here.
class QuestionView(generics.GenericAPIView):
    """
    """
    serializer_class = QuestionSerializer
    permission_classes = (AllowAny,)

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        question = serializer.validated_data['question']
        context_data = request.COOKIES.get('context')
        try:
            if context_data and json.loads(context_data).get('domain'):
                answer = chatbot.get_response(question, context=json.loads(context_data))
            else:
                # Get answer from the cache
                if cache.hexists('static_qa', question):
                    answer = {'text': cache.hget('static_qa', question).decode('utf-8')}
                    chatbot.logger.info('Get the answer to the "{}" question from the cache'.format(question))
                else:
                    # no answer in the cache, get answer from the chatbot
                    answer = chatbot.get_response(question)
        except Exception as e:
            chatbot.logger.error(str(e))
            answer = {'text': '机器人接口发生了错误，错误信息是:{}'.format(str(e))}

        # response
        response = Response(
            {'text': answer.get('text', '')},
            status=status.HTTP_200_OK
        )

        # set cookie
        context_data = answer.get('context')
        if context_data:
            response.set_cookie('context', json.dumps(context_data), max_age=COOKIE_MAX_AGE)
        return response


class LearnView(generics.GenericAPIView):
    serializer_class = LearnSerializer
    permission_classes = (AllowAny,)

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(
            serializer.learn(),
            status=status.HTTP_200_OK
        )


class WechatQuestionView(APIView):
    permission_classes = (AllowAny,)

    def post(self, request, *args, **kwargs):
        msg = parse_message(request.stream.read())
        user_id = request.GET.get('openid')
        response_xml = ''
        if msg.type == 'text':
            question = msg.content

            # The problem being processed is not repeated
            if cache.hexists('{}_asked_question'.format(user_id), msg.id):
                if cache.hget('{}_asked_question'.format(user_id), msg.id) == b'running':
                    return

            # If the question has already been asked, return answer from cache
            if cache.hexists('{}_asked_question'.format(user_id), msg.id):
                response_xml = cache.hget('{}_asked_question'.format(user_id), msg.id)
            else:
                # get the context from the cache
                context_data = cache.get('{}_context'.format(user_id))

                cache.hset('{}_asked_question'.format(user_id), msg.id, 'running')
                try:
                    if context_data and json.loads(context_data).get('domain'):
                        answer = chatbot.get_response(question, context=json.loads(context_data))
                    else:
                        # Get answer from the cache
                        if cache.hexists('static_qa', question):
                            answer = {'text': cache.hget('static_qa', question).decode('utf-8')}
                            chatbot.logger.info('Get the answer to the "{}" question from the cache'.format(question))
                        else:
                            # no answer in the cache, get answer from the chatbot
                            answer = chatbot.get_response(question)
                except Exception as e:
                    chatbot.logger.error(str(e))
                    answer = {'text': '机器人接口发生了错误，错误信息是:{}'.format(str(e))}

                reply = TextReply(content=answer.get('text', ''), message=msg)
                response_xml = reply.render()

                # set cookie
                context_data = answer.get('context')
                if context_data:
                    cache.set('{}_context'.format(user_id), json.dumps(context_data), COOKIE_MAX_AGE)

                # save the question that has been asked to the cache
                cache.hset('{}_asked_question'.format(user_id), msg.id, response_xml)

        # response
        response = HttpResponse(
            response_xml,
            status=status.HTTP_200_OK
        )
        return response

    def get(self, request, *args, **kwargs):
        try:
            check_signature(
                token='chatterbot',
                signature=request.GET.get('signature'),
                timestamp=request.GET.get('timestamp'),
                nonce=request.GET.get('nonce')
            )
        except InvalidSignatureException:
            pass

        return HttpResponse(
            request.GET.get('echostr'),
            status=status.HTTP_200_OK
        )

# class WechatQuestionView(APIView):
#     permission_classes = (AllowAny,)
#
#     def post(self, request, *args, **kwargs):
#         msg = parse_message(request.stream.read())
#         user_id = request.GET.get('openid')
#         response_xml = ''
#         if msg.type == 'text':
#             context_data = cache.get(user_id)
#             question = msg.content
#
#             try:
#                 if context_data and json.loads(context_data).get('domain'):
#                     answer = chatbot.get_response(question, context=json.loads(context_data))
#                 else:
#                     # Get answer from the cache
#                     if cache.hexists('static_qa', question):
#                         answer = {'text': cache.hget('static_qa', question).decode('utf-8')}
#                         chatbot.logger.info('Get the answer to the "{}" question from the cache'.format(question))
#                     else:
#                         # no answer in the cache, get answer from the chatbot
#                         answer = chatbot.get_response(question)
#             except Exception as e:
#                 chatbot.logger.error(str(e))
#                 answer = {'text': '机器人接口发生了错误，错误信息是:{}'.format(str(e))}
#
#             reply = TextReply(content=answer.get('text', ''), message=msg)
#             response_xml = reply.render()
#
#             # set cookie
#             context_data = answer.get('context')
#             if context_data:
#                 cache.set(user_id, json.dumps(context_data))
#
#         # response
#         response = HttpResponse(
#             response_xml,
#             status=status.HTTP_200_OK
#         )
#         return response
#
#     def get(self, request, *args, **kwargs):
#         try:
#             check_signature(
#                 token='chatterbot',
#                 signature=request.GET.get('signature'),
#                 timestamp=request.GET.get('timestamp'),
#                 nonce=request.GET.get('nonce')
#             )
#         except InvalidSignatureException:
#             pass
#
#         return HttpResponse(
#             request.GET.get('echostr'),
#             status=status.HTTP_200_OK
#         )
