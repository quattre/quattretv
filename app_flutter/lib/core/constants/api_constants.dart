class ApiConstants {
  // Base URL - Change this to your server
  static const String baseUrl = 'http://localhost:8000';

  // API Endpoints
  static const String apiVersion = '/api/v1';

  // Auth
  static const String login = '$apiVersion/accounts/token/';
  static const String refreshToken = '$apiVersion/accounts/token/refresh/';
  static const String profile = '$apiVersion/accounts/users/me/';

  // Channels
  static const String channels = '$apiVersion/channels/';
  static const String categories = '$apiVersion/channels/categories/';
  static const String favorites = '$apiVersion/channels/favorites/';

  // EPG
  static const String epgNow = '$apiVersion/epg/programs/now/';
  static const String epgSchedule = '$apiVersion/epg/programs/schedule/';
  static const String epgGrid = '$apiVersion/epg/programs/grid/';

  // VOD
  static const String vodCategories = '$apiVersion/vod/categories/';
  static const String movies = '$apiVersion/vod/movies/';
  static const String series = '$apiVersion/vod/series/';
  static const String watchHistory = '$apiVersion/vod/history/';

  // Timeshift
  static const String timeshiftUrl = '$apiVersion/timeshift/get_url/';
  static const String catchupUrl = '$apiVersion/timeshift/catchup/';

  // PVR
  static const String recordings = '$apiVersion/pvr/recordings/';
  static const String recordingRules = '$apiVersion/pvr/rules/';

  // Stalker Portal (for legacy devices)
  static const String stalkerPortal = '/portal.php';
}
