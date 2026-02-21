import 'package:flutter/material.dart';
import '../../services/api_service.dart';
import '../../models/homework.dart';
import 'package:intl/intl.dart';

class StudentHomeworkScreen extends StatefulWidget {
  const StudentHomeworkScreen({super.key});

  @override
  State<StudentHomeworkScreen> createState() => _StudentHomeworkScreenState();
}

class _StudentHomeworkScreenState extends State<StudentHomeworkScreen> {
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
      final list = await _api.getMyHomeworks();
      setState(() {
        _homeworks = list;
        _isLoading = false;
      });
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
      }
      setState(() => _isLoading = false);
    }
  }

  Future<void> _markCompleted(int id) async {
    try {
      await _api.markHomeworkCompleted(id);
      await _load();
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Marked completed')));
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('My Homework')),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _homeworks.isEmpty
              ? const Center(child: Text('No homework found.'))
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
                        subtitle: Text('${hw.description}\nDue: ${DateFormat('MMM dd, yyyy').format(due)}'),
                        isThreeLine: true,
                        trailing: hw.completed == true
                            ? const Chip(label: Text('Completed'), backgroundColor: Colors.green)
                            : ElevatedButton(
                                onPressed: () => _markCompleted(hw.id),
                                child: const Text('Mark Completed'),
                              ),
                      ),
                    );
                  },
                ),
    );
  }
}
