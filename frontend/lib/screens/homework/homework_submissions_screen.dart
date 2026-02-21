import 'package:flutter/material.dart';
import '../../services/api_service.dart';
import '../../models/homework_submission.dart';
import 'package:intl/intl.dart';

class HomeworkSubmissionsScreen extends StatefulWidget {
  final int homeworkId;
  final String homeworkTitle;

  const HomeworkSubmissionsScreen({super.key, required this.homeworkId, required this.homeworkTitle});

  @override
  State<HomeworkSubmissionsScreen> createState() => _HomeworkSubmissionsScreenState();
}

class _HomeworkSubmissionsScreenState extends State<HomeworkSubmissionsScreen> {
  final ApiService _api = ApiService();
  List<HomeworkSubmission> _subs = [];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _isLoading = true);
    try {
      final list = await _api.getHomeworkSubmissions(widget.homeworkId);
      setState(() {
        _subs = list;
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
      appBar: AppBar(title: Text('Submissions — ${widget.homeworkTitle}')),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _subs.isEmpty
              ? const Center(child: Text('No submissions yet.'))
              : ListView.builder(
                  padding: const EdgeInsets.all(16),
                  itemCount: _subs.length,
                  itemBuilder: (context, idx) {
                    final s = _subs[idx];
                    final completed = DateTime.parse(s.completedAt);
                    return Card(
                      margin: const EdgeInsets.only(bottom: 12),
                      child: ListTile(
                        leading: const CircleAvatar(child: Icon(Icons.person)),
                        title: Text(s.student.fullName),
                        subtitle: Text('Completed: ${DateFormat('MMM dd, yyyy HH:mm').format(completed)}'),
                      ),
                    );
                  },
                ),
    );
  }
}
