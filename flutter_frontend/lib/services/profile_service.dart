import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

class ProfileService {
  static const String baseUrl = 'http://localhost:8000';

  Future<String?> _getToken() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString('auth_token');
  }

  Future<Map<String, dynamic>> fetchProfile() async {
    try {
      final token = await _getToken();
      if (token == null) return {'success': false, 'error': 'Not authenticated'};

      final response = await http.get(Uri.parse('$baseUrl/auth/profile'), headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $token',
      });

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        return {'success': true, 'profile': data['profile'] ?? {}};
      } else {
        final data = json.decode(response.body);
        return {'success': false, 'error': data['detail'] ?? 'Failed to fetch profile'};
      }
    } catch (e) {
      return {'success': false, 'error': 'Network error: $e'};
    }
  }

  Future<Map<String, dynamic>> updateProfile(Map<String, dynamic> profile) async {
    try {
      final token = await _getToken();
      if (token == null) return {'success': false, 'error': 'Not authenticated'};

      final response = await http.put(Uri.parse('$baseUrl/auth/profile'), headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $token',
      }, body: json.encode({'profile': profile}));

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        return {'success': true, 'profile': data['profile'] ?? {}};
      } else {
        final data = json.decode(response.body);
        return {'success': false, 'error': data['detail'] ?? 'Failed to update profile'};
      }
    } catch (e) {
      return {'success': false, 'error': 'Network error: $e'};
    }
  }
}
