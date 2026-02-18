import 'class_model.dart';

class User {
  final int id;
  final String fullName;
  final String? email;
  final String role;
  final int? classId;
  final ClassModel? studentClass;
  final List<User>? children;

  User({
    required this.id,
    required this.fullName,
    this.email,
    required this.role,
    this.classId,
    this.studentClass,
    this.children,
  });

  factory User.fromJson(Map<String, dynamic> json) {
    return User(
      id: json['id'],
      fullName: json['full_name'],
      email: json['email'],
      role: json['role'],
      classId: json['class_id'],
      studentClass: json['student_class'] != null
          ? ClassModel.fromJson(json['student_class'])
          : null,
      children: json['children'] != null
          ? (json['children'] as List).map((e) => User.fromJson(e)).toList()
          : null,
    );
  }
  
  bool get isAdmin => role == 'admin';
  bool get isTeacher => role == 'teacher';
  bool get isStudent => role == 'student';
  bool get isParent => role == 'parent';
}
