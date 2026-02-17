import 'package:flutter/material.dart';

class TeacherDashboardScreen extends StatelessWidget {
  const TeacherDashboardScreen({super.key});
  @override
  Widget build(BuildContext context) => const Scaffold(body: Center(child: Text('Teacher Dashboard')));
}

class StudentDashboardScreen extends StatelessWidget {
  const StudentDashboardScreen({super.key});
  @override
  Widget build(BuildContext context) => const Scaffold(body: Center(child: Text('Student Dashboard')));
}

class ParentDashboardScreen extends StatelessWidget {
  const ParentDashboardScreen({super.key});
  @override
  Widget build(BuildContext context) => const Scaffold(body: Center(child: Text('Parent Dashboard')));
}
