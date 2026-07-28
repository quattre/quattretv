"""URLs the recording servers (record1 / storage1) call on us."""
from django.urls import path, re_path

from . import storage_views

# The storages build these URLs by string concatenation from API_URL, so accept
# them with and without the trailing slash.
urlpatterns = [
    re_path(
        r'^tv_archive/(?P<storage_name>[^/]+)/?$',
        storage_views.tv_archive_tasks,
        name='tv_archive_tasks',
    ),
    re_path(
        r'^stream_recorder/(?P<rec_id>\d+)/?$',
        storage_views.stream_recorder_callback,
        name='stream_recorder_callback',
    ),
    re_path(
        r'^catchup/(?P<channel_id>\d+)/(?P<start_ts>\d+)/(?P<duration>\d+)\.m3u8$',
        storage_views.catchup_playlist,
        name='catchup_playlist',
    ),
]

portal_api_urlpatterns = [
    path(
        'chk_storage_token.php',
        storage_views.chk_storage_token,
        name='chk_storage_token',
    ),
    path(
        'chk_tmp_archive_link.php',
        storage_views.chk_tmp_archive_link,
        name='chk_tmp_archive_link',
    ),
]
