import 'package:flutter/material.dart';
import '../../services/api_service.dart';
import '../../models/homework.dart';
import 'homework_submissions_screen.dart';
import 'package:intl/intl.dart';

class TeacherHomeworkScreen extends StatefulWidget {
  const TeacherHomeworkScreen({super.key});

  @override
  State<TeacherHomeworkScreen> createState() => _TeacherHomeworkScreenState();
}

class _TeacherHomeworkScreenState extends State<TeacherHomeworkScreen> {
  final ApiService _api = ApiService();
  List<HomeworkModel> _homeworks = [];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _isLoading = true);
    try {
      final list = await _api.getCreatedHomeworks();
      setState(() {
        _homeworks = list;
        _isLoading = false;
      });
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
      setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('My Homework (Teacher)')),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _homeworks.isEmpty
              ? const Center(child: Text('No homework created yet.'))
              : ListView.builder(
                  padding: const EdgeInsets.all(16),
                  itemCount: _homeworks.length,
                  itemBuilder: (context, idx) {
                    final hw = _homeworks[idx];
                    final due = DateTime.parse(hw.dueDate);
                    return Card(
                      margin: const EdgeInsets.only(bottom: 12),
                      child: ListTile(
                        title: Text(hw.title),
                        subtitle: Text('Due: ${DateFormat('MMM dd, yyyy').format(due)}'),
                        trailing: IconButton(
                          icon: const Icon(Icons.list_alt),
                          onPressed: () => Navigator.push(
                            context,
                            MaterialPageRoute(builder: (_) => HomeworkSubmissionsScreen(homeworkId: hw.id, homeworkTitle: hw.title)),
                          ),
                        ),
                      ),
                    );
                  },
                ),
    );
  }
}
