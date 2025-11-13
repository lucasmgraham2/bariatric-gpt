import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

class AiService {
  static const String baseUrl = 'http://localhost:8000';

  /// Send a message to the AI assistant
  /// Patient ID will be automatically linked to user credentials in the future
  Future<Map<String, dynamic>> sendMessage({
    required String message,
    String? patientId, // Reserved for future profile integration
  }) async {
    try {
      // Get auth token
      final prefs = await SharedPreferences.getInstance();
      final token = prefs.getString('auth_token');

      if (token == null) {
        return {
          'success': false,
          'error': 'Not authenticated. Please log in again.'
        };
      }

      // Prepare request (patient_id null for now, will auto-link to user later)
      final response = await http.post(
        Uri.parse('$baseUrl/chat'),
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer $token',
        },
        body: jsonEncode({
          'message': message,
          'patient_id': patientId, // Currently null, reserved for future use
        }),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        // Prefer Markdown-formatted response if available, otherwise plain text.
        final plain = data['final_response'] ?? data['response'] ?? '';
        final markdown = data['final_response_readme'] ?? data['final_response_markdown'];
        return {
          'success': true,
          'response': plain,
          'response_markdown': markdown,
        };
      } else if (response.statusCode == 401) {
        return {
          'success': false,
          'error': 'Session expired. Please log in again.'
        };
      } else {
        final error = jsonDecode(response.body);
        return {
          'success': false,
          'error': error['detail'] ?? 'Failed to get AI response'
        };
      }
    } catch (e) {
      return {
        'success': false,
        'error': 'Network error: ${e.toString()}'
      };
    }
  }
}
