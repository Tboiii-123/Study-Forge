from django.db import models
from django.contrib.auth.models import User
from apps.containers.models import Entry

class StudyPack(models.Model):
    """Generated study materials from an entry."""
    entry = models.OneToOneField(Entry, on_delete=models.CASCADE, related_name='study_pack')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # Generated content
    summary = models.TextField(null=True, blank=True)
    flashcards = models.JSONField(default=list)  # List of {q, a}
    exam_questions = models.JSONField(default=list)  # List of {question, options, answer}
    
    # Status
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('generating', 'Generating'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error = models.TextField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"StudyPack for {self.entry.id}"