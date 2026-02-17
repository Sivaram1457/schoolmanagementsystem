import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/auth_provider.dart';
import 'admin/admin_dashboard_screen.dart';
import 'role_dashboards.dart';

class DashboardScreen extends StatelessWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final auth = Provider.of<AuthProvider>(context);
    final user = auth.user;

    if (user == null) {
      return const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      );
    }

    // Role-based navigation
    if (user.isAdmin) {
      return const AdminDashboardScreen();
    } else if (user.isTeacher) {
      return const TeacherDashboardScreen();
    } else if (user.isStudent) {
      return const StudentDashboardScreen();
    } else if (user.isParent) {
      return const ParentDashboardScreen();
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('Dashboard'),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: () => auth.logout().then((_) {
              Navigator.pushReplacementNamed(context, '/login');
            }),
          ),
        ],
      ),
      body: const Center(
        child: Text('Unknown Role or Error'),
      ),
    );
  }
}
