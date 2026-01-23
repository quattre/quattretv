import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:hive/hive.dart';

import '../constants/api_constants.dart';
import '../constants/storage_keys.dart';

final dioProvider = Provider<Dio>((ref) {
  final dio = Dio(BaseOptions(
    baseUrl: ApiConstants.baseUrl,
    connectTimeout: const Duration(seconds: 30),
    receiveTimeout: const Duration(seconds: 30),
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
  ));

  dio.interceptors.add(AuthInterceptor(ref));
  dio.interceptors.add(LogInterceptor(
    requestBody: true,
    responseBody: true,
  ));

  return dio;
});

class AuthInterceptor extends Interceptor {
  final Ref ref;

  AuthInterceptor(this.ref);

  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) {
    final box = Hive.box(StorageKeys.settingsBox);
    final token = box.get(StorageKeys.accessToken);

    if (token != null) {
      options.headers['Authorization'] = 'Bearer $token';
    }

    handler.next(options);
  }

  @override
  void onError(DioException err, ErrorInterceptorHandler handler) async {
    if (err.response?.statusCode == 401) {
      // Try to refresh token
      final refreshed = await _refreshToken();
      if (refreshed) {
        // Retry the request
        try {
          final response = await _retry(err.requestOptions);
          handler.resolve(response);
          return;
        } catch (e) {
          handler.next(err);
          return;
        }
      }
    }
    handler.next(err);
  }

  Future<bool> _refreshToken() async {
    final box = Hive.box(StorageKeys.settingsBox);
    final refreshToken = box.get(StorageKeys.refreshToken);

    if (refreshToken == null) return false;

    try {
      final dio = Dio(BaseOptions(baseUrl: ApiConstants.baseUrl));
      final response = await dio.post(
        ApiConstants.refreshToken,
        data: {'refresh': refreshToken},
      );

      final newAccessToken = response.data['access'];
      await box.put(StorageKeys.accessToken, newAccessToken);

      if (response.data['refresh'] != null) {
        await box.put(StorageKeys.refreshToken, response.data['refresh']);
      }

      return true;
    } catch (e) {
      // Clear tokens on refresh failure
      await box.delete(StorageKeys.accessToken);
      await box.delete(StorageKeys.refreshToken);
      return false;
    }
  }

  Future<Response> _retry(RequestOptions requestOptions) async {
    final box = Hive.box(StorageKeys.settingsBox);
    final token = box.get(StorageKeys.accessToken);

    final options = Options(
      method: requestOptions.method,
      headers: {
        ...requestOptions.headers,
        'Authorization': 'Bearer $token',
      },
    );

    return Dio(BaseOptions(baseUrl: ApiConstants.baseUrl)).request(
      requestOptions.path,
      data: requestOptions.data,
      queryParameters: requestOptions.queryParameters,
      options: options,
    );
  }
}

// API Response wrapper
class ApiResponse<T> {
  final T? data;
  final String? error;
  final bool isSuccess;

  ApiResponse.success(this.data)
      : error = null,
        isSuccess = true;

  ApiResponse.error(this.error)
      : data = null,
        isSuccess = false;
}
