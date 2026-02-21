import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/user.dart';
import '../models/class_model.dart';
import '../models/attendance_model.dart';
import '../utils/constants.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:intl/intl.dart';
import '../models/homework.dart';
import '../models/homework_submission.dart';

class ApiService {
  static const _accessTokenKey = 'access_token';
  static const _refreshTokenKey = 'refresh_token';

  final _storage = const FlutterSecureStorage();
  
  // Callback for automatic logout on 401
  void Function()? onUnauthorized;

  Future<Map<String, String>> _getHeaders() async {
    final token = await _storage.read(key: _accessTokenKey);
    return {
      'Content-Type': 'application/json',
      if (token != null) 'Authorization': 'Bearer $token',
    };
  }

  /// Centralized request handler to manage headers and common errors (like 401)
  Future<http.Response> _request(
    String method,
    String path, {
    Map<String, dynamic>? body,
    bool allowRefresh = true,
  }) async {
    final url = Uri.parse('${AppConstants.baseUrl}$path');
    final headers = await _getHeaders();
    
    http.Response response;
    try {
      if (method == 'POST') {
        response = await http.post(url, headers: headers, body: body != null ? jsonEncode(body) : null);
      } else if (method == 'PUT') {
        response = await http.put(url, headers: headers, body: body != null ? jsonEncode(body) : null);
      } else if (method == 'DELETE') {
        response = await http.delete(url, headers: headers);
      } else {
        response = await http.get(url, headers: headers);
      }
    } catch (e) {
      throw Exception('Connection error: $e');
    }

    if (response.statusCode == 401) {
      if (allowRefresh && await _refreshTokens()) {
        return _request(method, path, body: body, allowRefresh: false);
      }
      await logout();
      if (onUnauthorized != null) onUnauthorized!();
      throw Exception('Unauthorized');
    }

    return response;
  }

  /// Parses FastAPI error details: {"detail": "..."}
  String _errorMessage(http.Response response) {
    try {
      final data = jsonDecode(response.body);
      if (data is Map && data.containsKey('detail')) {
        return data['detail'].toString();
      }
    } catch (_) {}
    return 'Status ${response.statusCode}: ${response.body}';
  }

  Future<void> _storeTokens(String accessToken, String refreshToken) async {
    await _storage.write(key: _accessTokenKey, value: accessToken);
    await _storage.write(key: _refreshTokenKey, value: refreshToken);
  }

  Future<void> _clearTokens() async {
    await _storage.delete(key: _accessTokenKey);
    await _storage.delete(key: _refreshTokenKey);
  }

  Future<bool> _refreshTokens() async {
    final refreshToken = await _storage.read(key: _refreshTokenKey);
    if (refreshToken == null) return false;

    try {
      final response = await http.post(
        Uri.parse('${AppConstants.baseUrl}/auth/refresh'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'refresh_token': refreshToken}),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        await _storeTokens(data['access_token'], data['refresh_token']);
        return true;
      }
    } catch (_) {}

    return false;
  }

  // ── Auth ────────────────────────────────────────────────────────────────────
  
  Future<String> login(String email, String password) async {
    final response = await _request(
      'POST', 
      '/auth/login', 
      body: {'email': email, 'password': password},
    );
    
    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      final token = data['access_token'];
      final refreshToken = data['refresh_token'];
      await _storeTokens(token, refreshToken);
      return token;
    } else {
      throw Exception(_errorMessage(response));
    }
  }
  
  Future<void> logout() async {
    final refreshToken = await _storage.read(key: _refreshTokenKey);
    if (refreshToken != null) {
      try {
        await http.post(
          Uri.parse('${AppConstants.baseUrl}/auth/logout'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'refresh_token': refreshToken}),
        );
      } catch (_) {}
    }
    await _clearTokens();
  }

  Future<User> getMe() async {
    final response = await _request('GET', '/auth/me');
    if (response.statusCode == 200) {
      return User.fromJson(jsonDecode(response.body));
    }
    throw Exception(_errorMessage(response));
  }

  // ── Admin: Classes ──────────────────────────────────────────────────────────

  Future<List<ClassModel>> getClasses() async {
    final response = await _request('GET', '/admin/classes');
    if (response.statusCode == 200) {
      final List list = jsonDecode(response.body);
      return list.map((e) => ClassModel.fromJson(e)).toList();
    }
    throw Exception(_errorMessage(response));
  }

  Future<ClassModel> createClass(String name, String level, String section) async {
    final response = await _request(
      'POST', 
      '/admin/classes',
      body: {'name': name, 'class_level': level, 'section': section},
    );
    if (response.statusCode == 201) return ClassModel.fromJson(jsonDecode(response.body));
    throw Exception(_errorMessage(response));
  }

  // ── Admin: Students ─────────────────────────────────────────────────────────

  Future<User> createStudent(String name, String email, String password, int classId) async {
    final response = await _request(
      'POST',
      '/admin/students',
      body: {
        'full_name': name, 
        'email': email, 
        'password': password,
        'role': 'student', 
        'class_id': classId
      },
    );
    if (response.statusCode == 201) return User.fromJson(jsonDecode(response.body));
    throw Exception(_errorMessage(response));
  }

  // ── Attendance ──────────────────────────────────────────────────────────────

  Future<List<User>> getStudentsByClass(int classId) async {
    final response = await _request('GET', '/admin/classes/$classId/students');
    if (response.statusCode == 200) {
      final List list = jsonDecode(response.body);
      return list.map((e) => User.fromJson(e)).toList();
    }
    throw Exception(_errorMessage(response));
  }

  Future<void> bulkMarkAttendance(int classId, DateTime date, List<Map<String, dynamic>> students) async {
    final formattedDate = DateFormat('yyyy-MM-dd').format(date);
    final response = await _request(
      'POST',
      '/attendance/bulk',
      body: {
        'class_id': classId,
        'date': formattedDate,
        'students': students, // Expects {'student_id': id, 'status': 'present'/'absent'}
      },
    );
    if (response.statusCode != 201) {
      throw Exception(_errorMessage(response));
    }
  }

  Future<AttendanceHistoryResponse> getMyAttendance() async {
    final response = await _request('GET', '/attendance/me');
    if (response.statusCode == 200) {
      return AttendanceHistoryResponse.fromJson(jsonDecode(response.body));
    }
    throw Exception(_errorMessage(response));
  }

  Future<AttendanceHistoryResponse> getStudentAttendance(int studentId) async {
    final response = await _request('GET', '/attendance/student/$studentId');
    if (response.statusCode == 200) {
      return AttendanceHistoryResponse.fromJson(jsonDecode(response.body));
    }
    throw Exception(_errorMessage(response));
  }

  Future<ClassAttendanceStats> getClassStats(int classId) async {
    final response = await _request('GET', '/attendance/stats/class/$classId');
    if (response.statusCode == 200) {
      return ClassAttendanceStats.fromJson(jsonDecode(response.body));
    }
    throw Exception(_errorMessage(response));
  }

  // ── Homework ─────────────────────────────────────────────────────────────

  Future<List<HomeworkModel>> getMyHomeworks() async {
    final response = await _request('GET', '/homework/me');
    if (response.statusCode == 200) {
      final List list = jsonDecode(response.body);
      return list.map((e) => HomeworkModel.fromJson(e)).toList();
    }
    throw Exception(_errorMessage(response));
  }

  Future<List<HomeworkModel>> getCreatedHomeworks() async {
    final response = await _request('GET', '/homework/my');
    if (response.statusCode == 200) {
      final List list = jsonDecode(response.body);
      return list.map((e) => HomeworkModel.fromJson(e)).toList();
    }
    throw Exception(_errorMessage(response));
  }

  Future<void> markHomeworkCompleted(int homeworkId) async {
    final response = await _request('POST', '/homework/$homeworkId/complete');
    if (response.statusCode != 200) {
      throw Exception(_errorMessage(response));
    }
  }

  Future<List<HomeworkSubmission>> getHomeworkSubmissions(int homeworkId) async {
    final response = await _request('GET', '/homework/$homeworkId/submissions');
    if (response.statusCode == 200) {
      final List list = jsonDecode(response.body);
      return list.map((e) => HomeworkSubmission.fromJson(e)).toList();
    }
    throw Exception(_errorMessage(response));
  }
}
