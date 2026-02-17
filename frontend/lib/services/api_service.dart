import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/user.dart';
import '../models/class_model.dart';
import '../utils/constants.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class ApiService {
  final _storage = const FlutterSecureStorage();
  
  Future<Map<String, String>> _headers() async {
    final token = await _storage.read(key: 'jwt');
    return {
      'Content-Type': 'application/json',
      if (token != null) 'Authorization': 'Bearer $token',
    };
  }
  
  // ── Auth ────────────────────────────────────────────────────────────────────
  
  Future<String> login(String email, String password) async {
    final resp = await http.post(
      Uri.parse('${AppConstants.baseUrl}/auth/login'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'email': email, 'password': password}),
    );
    
    if (resp.statusCode == 200) {
      final data = jsonDecode(resp.body);
      final token = data['access_token'];
      await _storage.write(key: 'jwt', value: token);
      return token;
    } else {
      throw Exception('Login failed: ${resp.body}');
    }
  }
  
  Future<void> logout() async {
    await _storage.delete(key: 'jwt');
  }

  Future<User> getMe() async {
    final resp = await http.get(
      Uri.parse('${AppConstants.baseUrl}/auth/me'),
      headers: await _headers(),
    );
    if (resp.statusCode == 200) {
      return User.fromJson(jsonDecode(resp.body));
    } else if (resp.statusCode == 401) {
      await logout();
      throw Exception('Unauthorized');
    }
    throw Exception('Failed to fetch user info');
  }

  // ── Admin: Classes ──────────────────────────────────────────────────────────

  Future<List<ClassModel>> getClasses() async {
     final resp = await http.get(
      Uri.parse('${AppConstants.baseUrl}/admin/classes'),
      headers: await _headers(),
    );
    if (resp.statusCode == 200) {
      final List list = jsonDecode(resp.body);
      return list.map((e) => ClassModel.fromJson(e)).toList();
    }
     throw Exception('Failed to load classes: ${resp.body}');
  }

  Future<ClassModel> createClass(String name, String level, String section) async {
    final resp = await http.post(
      Uri.parse('${AppConstants.baseUrl}/admin/classes'),
      headers: await _headers(),
      body: jsonEncode({'name': name, 'class_level': level, 'section': section}),
    );
    if (resp.statusCode == 201) return ClassModel.fromJson(jsonDecode(resp.body));
    throw Exception('Failed to create class: ${resp.body}');
  }

  // ── Admin: Students ─────────────────────────────────────────────────────────

  Future<User> createStudent(String name, String email, String password, int classId) async {
    final resp = await http.post(
      Uri.parse('${AppConstants.baseUrl}/admin/students'),
      headers: await _headers(),
      body: jsonEncode({
        'full_name': name, 
        'email': email, 
        'password': password,
        'role': 'student', 
        'class_id': classId
      }),
    );
    if (resp.statusCode == 201) return User.fromJson(jsonDecode(resp.body));
    throw Exception('Failed to create student: ${resp.body}');
  }
}
