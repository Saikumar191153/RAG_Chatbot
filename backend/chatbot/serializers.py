from rest_framework import serializers

class QuestionSerializer(serializers.Serializer):
    question = serializers.CharField(
        max_length=1000,
        help_text="The question you want to ask"
    )
    max_results = serializers.IntegerField(
        default=5,
        min_value=1,
        max_value=20,
        help_text="Maximum number of documents to retrieve for context"
    )
    temperature = serializers.FloatField(
        default=0.7,
        min_value=0.0,
        max_value=1.0,
        help_text="Temperature for response generation (0.0 = deterministic, 1.0 = creative)"
    )

class AnswerSerializer(serializers.Serializer):
    question = serializers.CharField()
    answer = serializers.CharField()
    sources = serializers.ListField(
        child=serializers.DictField(),
        help_text="List of source documents used for the answer"
    )
    retrieval_count = serializers.IntegerField()
    processing_time = serializers.FloatField()

from rest_framework import serializers
from .models import ChatHistory

class QuestionSerializer(serializers.Serializer):
    question = serializers.CharField()

class AnswerSerializer(serializers.Serializer):
    answer = serializers.CharField()

class ChatHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatHistory
        fields = ['id', 'question', 'answer', 'created_at']
