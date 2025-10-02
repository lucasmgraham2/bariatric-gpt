import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

class AuthService {
  static const String baseUrl = 'http://localhost:8000';
  static const String tokenKey = 'auth_token';
  static const String userIdKey = 'user_id';
  
  Future<Map<String, dynamic>> register({
    required String email,
    required String username,
    required String password,
  }) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/auth/register'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({'email': email, 'username': username, 'password': password}),
      );

      if (response.body.isEmpty) {
        return {'success': false, 'error': 'Empty response from server'};
      }

      final data = json.decode(response.body);
      
      if (response.statusCode == 200) {
        if (data['access_token'] == null || data['user_id'] == null) {
          return {'success': false, 'error': 'Invalid response: missing token or user_id'};
        }
        await _saveAuthData(data['access_token'], data['user_id']);
        return {'success': true, 'data': data};
      } else {
        return {'success': false, 'error': data['detail'] ?? 'Registration failed'};
      }
    } catch (e) {
      return {'success': false, 'error': 'Network error: $e'};
    }
  }

  Future<Map<String, dynamic>> login({
    required String username,
    required String password,
  }) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/auth/login'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({'username': username, 'password': password}),
      );

      if (response.body.isEmpty) {
        return {'success': false, 'error': 'Empty response from server'};
      }

      final data = json.decode(response.body);
      
      if (response.statusCode == 200) {
        if (data['access_token'] == null || data['user_id'] == null) {
          return {'success': false, 'error': 'Invalid response: missing token or user_id'};
        }
        await _saveAuthData(data['access_token'], data['user_id']);
        return {'success': true, 'data': data};
      } else {
        return {'success': false, 'error': data['detail'] ?? 'Login failed'};
      }
    } catch (e) {
      return {'success': false, 'error': 'Network error: $e'};
    }
  }

  Future<Map<String, dynamic>> getCurrentUser() async {
    try {
      final token = await getToken();
      if (token == null) {
        return {'success': false, 'error': 'No authentication token'};
      }

      final response = await http.get(
        Uri.parse('$baseUrl/auth/me'),
        headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer $token'},
      );

      if (response.body.isEmpty) {
        return {'success': false, 'error': 'Empty response from server'};
      }

      final data = json.decode(response.body);
      
      if (response.statusCode == 200) {
        return {'success': true, 'data': data};
      } else {
        return {'success': false, 'error': data['detail'] ?? 'Failed to get user'};
      }
    } catch (e) {
      return {'success': false, 'error': 'Network error: $e'};
    }
  }

  Future<void> logout() async {
    try {
      final token = await getToken();
      if (token != null) {
        await http.post(
          Uri.parse('$baseUrl/auth/logout'),
          headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer $token'},
        );
      }
    } catch (e) {
      print('Logout API call failed: $e');
    } finally {
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove(tokenKey);
      await prefs.remove(userIdKey);
    }
  }

  Future<bool> isLoggedIn() async {
    final token = await getToken();
    return token != null;
  }

  Future<String?> getToken() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(tokenKey);
  }

  Future<int?> getUserId() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getInt(userIdKey);
  }

  Future<void> _saveAuthData(String token, int userId) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(tokenKey, token);
    await prefs.setInt(userIdKey, userId);
  }
}