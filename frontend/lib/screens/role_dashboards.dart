import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/auth_provider.dart';
import 'attendance/attendance_marking_screen.dart';
import 'attendance/attendance_history_screen.dart';
import 'homework/student_homework_screen.dart';
import 'homework/teacher_homework_screen.dart';

class TeacherDashboardScreen extends StatelessWidget {
  const TeacherDashboardScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final auth = Provider.of<AuthProvider>(context);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Teacher Dashboard'),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: () => auth.logout().then((_) => Navigator.pushReplacementNamed(context, '/login')),
          ),
        ],
      ),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            ElevatedButton.icon(
              icon: const Icon(Icons.check_circle),
              label: const Text('Mark Attendance'),
              onPressed: () => Navigator.push(
                context, 
                MaterialPageRoute(builder: (_) => const TeacherAttendanceScreen())
              ),
              style: ElevatedButton.styleFrom(padding: const EdgeInsets.all(20)),
            ),
            const SizedBox(height: 12),
            ElevatedButton.icon(
              icon: const Icon(Icons.home_work),
              label: const Text('Homework Management'),
              onPressed: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const TeacherHomeworkScreen()),
              ),
              style: ElevatedButton.styleFrom(padding: const EdgeInsets.all(20)),
            ),
          ],
        ),
      ),
    );
  }
}

class StudentDashboardScreen extends StatelessWidget {
  const StudentDashboardScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final auth = Provider.of<AuthProvider>(context);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Student Dashboard'),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: () => auth.logout().then((_) => Navigator.pushReplacementNamed(context, '/login')),
          ),
        ],
      ),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            ElevatedButton.icon(
              icon: const Icon(Icons.history),
              label: const Text('My Attendance'),
              onPressed: () => Navigator.push(
                context, 
                MaterialPageRoute(builder: (_) => const AttendanceHistoryScreen())
              ),
              style: ElevatedButton.styleFrom(padding: const EdgeInsets.all(20)),
            ),
            const SizedBox(height: 12),
            ElevatedButton.icon(
              icon: const Icon(Icons.assignment),
              label: const Text('My Homework'),
              onPressed: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const StudentHomeworkScreen()),
              ),
              style: ElevatedButton.styleFrom(padding: const EdgeInsets.all(20)),
            ),
          ],
        ),
      ),
    );
  }
}

class ParentDashboardScreen extends StatelessWidget {
  const ParentDashboardScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final auth = Provider.of<AuthProvider>(context);
    final user = auth.user;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Parent Dashboard'),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: () => auth.logout().then((_) => Navigator.pushReplacementNamed(context, '/login')),
          ),
        ],
      ),
      body: user == null || user.children == null || user.children!.isEmpty
          ? const Center(child: Text('No linked children found.'))
          : ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: user.children!.length,
              itemBuilder: (context, index) {
                final child = user.children![index];
                return Card(
                  child: ListTile(
                    leading: const CircleAvatar(child: Icon(Icons.person)),
                    title: Text(child.fullName),
                    subtitle: const Text('Tap to view attendance'),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => AttendanceHistoryScreen(
                          studentId: child.id,
                          studentName: child.fullName,
                        ),
                      ),
                    ),
                  ),
                );
              },
            ),
    );
  }
}
