"""Study pack endpoints (function-based).

Authorization rule: every query is filtered by the owner, so another user's
entry simply does not exist for you -> 404, never 403 (no information leak).
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    OpenApiTypes,
    extend_schema,
)
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from apps.common.throttles import AIRateThrottle
from apps.containers.models import Entry

from .models import StudyPack
from .serializers import StudyPackSerializer
from .tasks import generate_study_pack

_ENTRY_ID = OpenApiParameter(
    name="entry_id",
    type=OpenApiTypes.UUID,  # change to OpenApiTypes.INT if your ids are integers
    location=OpenApiParameter.PATH,
    description="ID of the entry the study pack belongs to.",
)

_NOT_FOUND = OpenApiResponse(
    description="Entry (or study pack) not found, or not owned by the caller.",
    examples=[
        OpenApiExample(
            "Not found",
            value={"error": {"code": "not_found", "message": "Entry not found.", "details": None}},
        )
    ],
)


def _own_entry(request, entry_id) -> Entry:
    # Same rule as the containers app: filter by owner -> 404, never 403.
    return get_object_or_404(Entry, pk=entry_id, container__user=request.user)


# --------------------------------------------------------------------------- study pack
@extend_schema(
    methods=["POST"],
    tags=["Study packs"],
    summary="Generate a study pack",
    description=(
        "Creates a study pack (summary, flashcards, exam questions) for an entry. "
        "Generation runs in the background: poll `GET` and check `status` until it is ready. "
        "Calling this again on a `failed` pack re-triggers generation."
    ),
    parameters=[_ENTRY_ID],
    request=None,
    responses={
        202: StudyPackSerializer,
        401: OpenApiResponse(description="Authentication credentials were not provided."),
        404: _NOT_FOUND,
        429: OpenApiResponse(description="Rate limit exceeded."),
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([UserRateThrottle, AIRateThrottle])
def create_study_pack(request, entry_id):
    entry = _own_entry(request, entry_id)

    study_pack, _created = StudyPack.objects.get_or_create(
        entry=entry,
        defaults={"user": request.user},
    )

    # 202 Accepted: stored, AI work continues in the background (poll `status`).
    if study_pack.status in ["pending", "failed"]:
        generate_study_pack.delay(study_pack.id)

    return Response(
        StudyPackSerializer(study_pack, context={"request": request}).data,
        status=status.HTTP_202_ACCEPTED,
    )


@extend_schema(
    methods=["GET"],
    tags=["Study packs"],
    summary="Get a study pack",
    description="Returns the study pack for an entry, including its generation `status`.",
    parameters=[_ENTRY_ID],
    responses={
        200: StudyPackSerializer,
        401: OpenApiResponse(description="Authentication credentials were not provided."),
        404: _NOT_FOUND,
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_study_pack(request, entry_id):
    entry = _own_entry(request, entry_id)
    study_pack = get_object_or_404(StudyPack, entry=entry)
    return Response(
        StudyPackSerializer(study_pack, context={"request": request}).data,
        status=status.HTTP_200_OK,
    )