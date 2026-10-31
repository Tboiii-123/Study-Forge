import json
from celery import shared_task
from adaption import Adaption
from .models import StudyPack
from apps.containers.models import Entry

@shared_task
def generate_study_pack(study_pack_id):
    """Generate summary, flashcards, and exam questions using Adaption."""
    import os
    
    study_pack = StudyPack.objects.get(id=study_pack_id)
    entry = study_pack.entry
    
    try:
        study_pack.status = 'generating'
        study_pack.save()
        
        client = Adaption(api_key=os.getenv('ADAPTION_API_KEY'))
        model_id = os.getenv('ADAPTION_MODEL_ID')
        
        # Entry text to process
        text = entry.transcript or entry.text
        
        # 1. Generate summary
        summary_response = client.messages.create(
            model=model_id,
            messages=[
                {
                    "role": "user",
                    "content": f"Summarize this note in 1-2 paragraphs:\n\n{text}"
                }
            ]
        )
        summary = summary_response.content[0].text if summary_response.content else ""
        
        # 2. Generate flashcards
        flashcards_response = client.messages.create(
            model=model_id,
            messages=[
                {
                    "role": "user",
                    "content": f"Create 5-10 flashcards from this note. Return as JSON array with 'q' and 'a' keys:\n\n{text}"
                }
            ]
        )
        flashcards_text = flashcards_response.content[0].text if flashcards_response.content else "[]"
        try:
            flashcards = json.loads(flashcards_text)
        except json.JSONDecodeError:
            flashcards = []
        
        # 3. Generate exam questions
        exam_response = client.messages.create(
            model=model_id,
            messages=[
                {
                    "role": "user",
                    "content": f"Create 3-5 exam-style questions from this note. Return as JSON array with 'question', 'options' (array), and 'answer' keys:\n\n{text}"
                }
            ]
        )
        exam_text = exam_response.content[0].text if exam_response.content else "[]"
        try:
            exam_questions = json.loads(exam_text)
        except json.JSONDecodeError:
            exam_questions = []
        
        # Save results
        study_pack.summary = summary
        study_pack.flashcards = flashcards
        study_pack.exam_questions = exam_questions
        study_pack.status = 'completed'
        study_pack.save()
        
    except Exception as e:
        study_pack.status = 'failed'
        study_pack.error = str(e)
        study_pack.save()
        raise