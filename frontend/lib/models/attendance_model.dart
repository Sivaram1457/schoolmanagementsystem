import 'user.dart';

class AttendanceRecord {
  final int id;
  final int studentId;
  final int classId;
  final DateTime date;
  final String status;
  final int markedBy;
  final int? lastUpdatedBy;
  final DateTime createdAt;
  final DateTime? updatedAt;

  AttendanceRecord({
    required this.id,
    required this.studentId,
    required this.classId,
    required this.date,
    required this.status,
    required this.markedBy,
    this.lastUpdatedBy,
    required this.createdAt,
    this.updatedAt,
  });

  factory AttendanceRecord.fromJson(Map<String, dynamic> json) {
    return AttendanceRecord(
      id: json['id'],
      studentId: json['student_id'],
      classId: json['class_id'],
      date: DateTime.parse(json['date']),
      status: json['status'],
      markedBy: json['marked_by'],
      lastUpdatedBy: json['last_updated_by'],
      createdAt: DateTime.parse(json['created_at']),
      updatedAt: json['updated_at'] != null ? DateTime.parse(json['updated_at']) : null,
    );
  }

  bool get isPresent => status == 'present';
}

class AttendanceHistoryResponse {
  final List<AttendanceRecord> history;
  final double attendancePercentage;
  final int totalDays;
  final int daysPresent;

  AttendanceHistoryResponse({
    required this.history,
    required this.attendancePercentage,
    required this.totalDays,
    required this.daysPresent,
  });

  factory AttendanceHistoryResponse.fromJson(Map<String, dynamic> json) {
    return AttendanceHistoryResponse(
      history: (json['history'] as List)
          .map((e) => AttendanceRecord.fromJson(e))
          .toList(),
      attendancePercentage: (json['attendance_percentage'] as num).toDouble(),
      totalDays: json['total_days'],
      daysPresent: json['days_present'] ?? 0,
    );
  }
}

class ClassAttendanceStats {
  final int classId;
  final String className;
  final int totalStudents;
  final int totalRecords;
  final double attendancePercentage;

  ClassAttendanceStats({
    required this.classId,
    required this.className,
    required this.totalStudents,
    required this.totalRecords,
    required this.attendancePercentage,
  });

  factory ClassAttendanceStats.fromJson(Map<String, dynamic> json) {
    return ClassAttendanceStats(
      classId: json['class_id'],
      className: json['class_name'],
      totalStudents: json['total_students'],
      totalRecords: json['total_records'],
      attendancePercentage: (json['attendance_percentage'] as num).toDouble(),
    );
  }
}
