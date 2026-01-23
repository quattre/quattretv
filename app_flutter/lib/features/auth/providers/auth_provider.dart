import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:hive/hive.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/models/user.dart';
import '../../../core/constants/api_constants.dart';
import '../../../core/constants/storage_keys.dart';

class AuthState {
  final User? user;
  final bool isLoggedIn;
  final bool isLoading;
  final String? error;

  AuthState({
    this.user,
    this.isLoggedIn = false,
    this.isLoading = false,
    this.error,
  });

  AuthState copyWith({
    User? user,
    bool? isLoggedIn,
    bool? isLoading,
    String? error,
  }) {
    return AuthState(
      user: user ?? this.user,
      isLoggedIn: isLoggedIn ?? this.isLoggedIn,
      isLoading: isLoading ?? this.isLoading,
      error: error,
    );
  }
}

class AuthNotifier extends AsyncNotifier<AuthState> {
  @override
  Future<AuthState> build() async {
    return await _checkAuth();
  }

  Future<AuthState> _checkAuth() async {
    final box = Hive.box(StorageKeys.settingsBox);
    final token = box.get(StorageKeys.accessToken);

    if (token == null) {
      return AuthState(isLoggedIn: false);
    }

    try {
      final user = await _fetchProfile();
      return AuthState(user: user, isLoggedIn: true);
    } catch (e) {
      await _clearTokens();
      return AuthState(isLoggedIn: false);
    }
  }

  Future<User> _fetchProfile() async {
    final dio = ref.read(dioProvider);
    final response = await dio.get(ApiConstants.profile);
    return User.fromJson(response.data);
  }

  Future<void> login(String username, String password) async {
    state = const AsyncValue.loading();

    try {
      final dio = Dio(BaseOptions(baseUrl: ApiConstants.baseUrl));
      final response = await dio.post(
        ApiConstants.login,
        data: {
          'username': username,
          'password': password,
        },
      );

      final accessToken = response.data['access'];
      final refreshToken = response.data['refresh'];

      final box = Hive.box(StorageKeys.settingsBox);
      await box.put(StorageKeys.accessToken, accessToken);
      await box.put(StorageKeys.refreshToken, refreshToken);

      final user = await _fetchProfile();
      state = AsyncValue.data(AuthState(user: user, isLoggedIn: true));
    } on DioException catch (e) {
      String errorMessage = 'Error de conexión';
      if (e.response?.statusCode == 401) {
        errorMessage = 'Usuario o contraseña incorrectos';
      } else if (e.response?.data?['detail'] != null) {
        errorMessage = e.response!.data['detail'];
      }
      state = AsyncValue.data(AuthState(isLoggedIn: false, error: errorMessage));
    } catch (e) {
      state = AsyncValue.data(AuthState(isLoggedIn: false, error: e.toString()));
    }
  }

  Future<void> loginWithServer(String serverUrl, String username, String password) async {
    final box = Hive.box(StorageKeys.settingsBox);
    await box.put(StorageKeys.serverUrl, serverUrl);
    await login(username, password);
  }

  Future<void> logout() async {
    await _clearTokens();
    state = AsyncValue.data(AuthState(isLoggedIn: false));
  }

  Future<void> _clearTokens() async {
    final box = Hive.box(StorageKeys.settingsBox);
    await box.delete(StorageKeys.accessToken);
    await box.delete(StorageKeys.refreshToken);
    await box.delete(StorageKeys.userId);
  }

  Future<void> refreshProfile() async {
    try {
      final user = await _fetchProfile();
      state = AsyncValue.data(state.value!.copyWith(user: user));
    } catch (e) {
      // Ignore error, keep current state
    }
  }
}

final authStateProvider = AsyncNotifierProvider<AuthNotifier, AuthState>(
  () => AuthNotifier(),
);
