import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/user.dart';
import '../models/class_model.dart';
import '../models/attendance_model.dart';
import '../utils/constants.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:intl/intl.dart';

class ApiService {
  final _storage = const FlutterSecureStorage();
  
  // Callback for automatic logout on 401
  void Function()? onUnauthorized;

  Future<Map<String, String>> _getHeaders() async {
    final token = await _storage.read(key: 'jwt');
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
      await _storage.write(key: 'jwt', value: token);
      return token;
    } else {
      throw Exception(_errorMessage(response));
    }
  }
  
  Future<void> logout() async {
    await _storage.delete(key: 'jwt');
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
}
