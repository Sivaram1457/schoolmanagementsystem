import 'user.dart';

class HomeworkSubmission {
  final int id;
  final int homeworkId;
  final User student;
  final bool isCompleted;
  final String completedAt;

  HomeworkSubmission({
    required this.id,
    required this.homeworkId,
    required this.student,
    required this.isCompleted,
    required this.completedAt,
  });

  factory HomeworkSubmission.fromJson(Map<String, dynamic> json) {
    return HomeworkSubmission(
      id: json['id'],
      homeworkId: json['homework_id'],
      student: User.fromJson(json['student']),
      isCompleted: json['is_completed'],
      completedAt: json['completed_at'],
    );
  }
}
