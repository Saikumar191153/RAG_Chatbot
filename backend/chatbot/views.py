
import logging
from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from .serializers import QuestionSerializer, AnswerSerializer, ChatHistorySerializer
from .rag_service import RAGService
from .models import ChatHistory

logger = logging.getLogger(__name__)

# Initialize RAG service (you might want to do this in a more Django-appropriate way)
rag_service = None

def get_rag_service():
    """Get or initialize RAG service"""
    global rag_service
    if rag_service is None:
        try:
            rag_service = RAGService(
                google_api_key=settings.GOOGLE_API_KEY,
                model_name="gemini-2.5-flash"
            )
            logger.info("RAG service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize RAG service: {e}")
            raise
    return rag_service

@api_view(['GET'])
@permission_classes([AllowAny])
def chat_history(request):
    """
    GET /api/chat-history/
    """
    history = ChatHistory.objects.all().order_by('-created_at')
    serializer = ChatHistorySerializer(history, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def ask_question(request):
    """
    POST /api/ask/
    {
        "question": "How do I place a trade?"
    }
    """
    try:
        serializer = QuestionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': 'Invalid input', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        question = serializer.validated_data['question']
        max_results = 10
        temperature = 0.1
        
        service = get_rag_service()
        result = service.generate_answer(question=question, k=max_results, temperature=temperature)

        # Save to DB
        ChatHistory.objects.create(question=question, answer=result.get("answer", ""))

        return Response(result, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error in ask_question API: {e}")
        return Response(
            {'error': 'Internal server error', 'message': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([AllowAny])
def service_status(request):
    """
    API endpoint to check service status
    
    GET /api/status/
    """
    try:
        service = get_rag_service()
        status_info = service.get_service_status()
        return Response(status_info, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error getting service status: {e}")
        return Response(
            {'error': 'Failed to get service status', 'message': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([AllowAny])
def search_documents(request):
    """
    API endpoint to search documents without generating answers
    
    POST /api/search/
    {
        "question": "trading charges",
        "max_results": 10
    }
    """
    try:
        # Validate input
        data = request.data
        question = data.get('question', '')
        max_results = data.get('max_results', 5)
        
        if not question:
            return Response(
                {'error': 'Question is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get RAG service
        service = get_rag_service()
        
        # Retrieve documents
        documents = service.retrieve_documents(question, max_results)
        
        return Response({
            'question': question,
            'documents': documents,
            'count': len(documents)
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error in search_documents API: {e}")
        return Response(
            {'error': 'Internal server error', 'message': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )