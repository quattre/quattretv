from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .models import VodCategory, Movie, Series, Season, Episode, WatchHistory
from .serializers import (
    VodCategorySerializer, MovieListSerializer, MovieDetailSerializer,
    SeriesListSerializer, SeriesDetailSerializer, SeasonSerializer,
    EpisodeSerializer, WatchHistorySerializer
)


class VodCategoryViewSet(viewsets.ModelViewSet):
    queryset = VodCategory.objects.filter(is_active=True)
    serializer_class = VodCategorySerializer
    filterset_fields = ['parent', 'is_adult']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated()]
        return [IsAdminUser()]


class MovieViewSet(viewsets.ModelViewSet):
    queryset = Movie.objects.filter(is_active=True)
    filterset_fields = ['category', 'is_hd', 'is_4k', 'is_adult', 'is_featured', 'year']
    search_fields = ['title', 'original_title', 'director', 'cast']
    ordering_fields = ['title', 'year', 'rating', 'created_at']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return MovieDetailSerializer
        return MovieListSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated()]
        return [IsAdminUser()]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.is_authenticated and not user.is_staff and not user.parental_password:
            queryset = queryset.filter(is_adult=False)
        return queryset

    @action(detail=False, methods=['get'])
    def featured(self, request):
        """Get featured movies."""
        movies = self.get_queryset().filter(is_featured=True)[:20]
        serializer = MovieListSerializer(movies, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Get recently added movies."""
        movies = self.get_queryset().order_by('-created_at')[:20]
        serializer = MovieListSerializer(movies, many=True)
        return Response(serializer.data)


class SeriesViewSet(viewsets.ModelViewSet):
    queryset = Series.objects.filter(is_active=True)
    filterset_fields = ['category', 'is_adult', 'is_featured']
    search_fields = ['title', 'original_title', 'cast']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return SeriesDetailSerializer
        return SeriesListSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated()]
        return [IsAdminUser()]

    @action(detail=True, methods=['get'])
    def seasons(self, request, pk=None):
        """Get all seasons for a series."""
        series = self.get_object()
        seasons = series.seasons.all()
        serializer = SeasonSerializer(seasons, many=True)
        return Response(serializer.data)


class SeasonViewSet(viewsets.ModelViewSet):
    queryset = Season.objects.all()
    serializer_class = SeasonSerializer
    filterset_fields = ['series']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated()]
        return [IsAdminUser()]


class EpisodeViewSet(viewsets.ModelViewSet):
    queryset = Episode.objects.filter(is_active=True)
    serializer_class = EpisodeSerializer
    filterset_fields = ['season']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated()]
        return [IsAdminUser()]


class WatchHistoryViewSet(viewsets.ModelViewSet):
    serializer_class = WatchHistorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return WatchHistory.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['post'])
    def update_position(self, request):
        """Update watch position."""
        movie_id = request.data.get('movie_id')
        episode_id = request.data.get('episode_id')
        position = request.data.get('position', 0)

        if movie_id:
            history, _ = WatchHistory.objects.update_or_create(
                user=request.user,
                movie_id=movie_id,
                defaults={'position': position}
            )
        elif episode_id:
            history, _ = WatchHistory.objects.update_or_create(
                user=request.user,
                episode_id=episode_id,
                defaults={'position': position}
            )
        else:
            return Response(
                {'error': 'movie_id or episode_id required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(WatchHistorySerializer(history).data)

    @action(detail=False, methods=['get'])
    def continue_watching(self, request):
        """Get content to continue watching."""
        history = self.get_queryset().filter(
            completed=False,
            position__gt=0
        )[:20]
        serializer = self.get_serializer(history, many=True)
        return Response(serializer.data)
