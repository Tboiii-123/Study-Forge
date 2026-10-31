from rest_framework import serializers
from .models import StudyPack

class FlashcardSerializer(serializers.Serializer):
    q = serializers.CharField()
    a = serializers.CharField()

class ExamQuestionSerializer(serializers.Serializer):
    question = serializers.CharField()
    options = serializers.ListField(child=serializers.CharField(), required=False)
    answer = serializers.CharField()

class StudyPackSerializer(serializers.ModelSerializer):
    flashcards = FlashcardSerializer(many=True, read_only=True)
    exam_questions = ExamQuestionSerializer(many=True, read_only=True)
    
    class Meta:
        model = StudyPack
        fields = ['id', 'entry', 'status', 'summary', 'flashcards', 'exam_questions', 'error', 'created_at']
        read_only_fields = ['id', 'status', 'created_at']