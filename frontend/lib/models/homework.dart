class HomeworkModel {
  final int id;
  final int classId;
  final int teacherId;
  final String title;
  final String description;
  final String dueDate; // ISO string
  final bool isDeleted;
  final bool? completed;

  HomeworkModel({
    required this.id,
    required this.classId,
    required this.teacherId,
    required this.title,
    required this.description,
    required this.dueDate,
    required this.isDeleted,
    this.completed,
  });

  factory HomeworkModel.fromJson(Map<String, dynamic> json) {
    return HomeworkModel(
      id: json['id'],
      classId: json['class_id'],
      teacherId: json['teacher_id'],
      title: json['title'],
      description: json['description'],
      dueDate: json['due_date'],
      isDeleted: json['is_deleted'],
      completed: json.containsKey('completed') ? json['completed'] as bool : null,
    );
  }
}
