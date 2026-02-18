import 'package:flutter/material.dart';
import '../../models/class_model.dart';
import '../../models/user.dart';
import '../../services/api_service.dart';
import 'package:intl/intl.dart';

class TeacherAttendanceScreen extends StatefulWidget {
  const TeacherAttendanceScreen({super.key});

  @override
  State<TeacherAttendanceScreen> createState() => _TeacherAttendanceScreenState();
}

class _TeacherAttendanceScreenState extends State<TeacherAttendanceScreen> {
  final ApiService _api = ApiService();
  final DateTime _selectedDate = DateTime.now();
  
  List<ClassModel> _classes = [];
  ClassModel? _selectedClass;
  List<User> _students = [];
  Map<int, bool> _attendance = {}; // studentId -> isPresent
  
  bool _isLoading = true;
  bool _isSubmitting = false;

  @override
  void initState() {
    super.initState();
    _loadInitialData();
  }

  Future<void> _loadInitialData() async {
    try {
      final classes = await _api.getClasses();
      setState(() {
        _classes = classes;
        _isLoading = false;
      });
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error loading classes: $e')),
        );
        setState(() => _isLoading = false);
      }
    }
  }

  Future<void> _loadStudents(ClassModel cls) async {
    setState(() {
      _isLoading = true;
      _selectedClass = cls;
      _students = [];
      _attendance = {};
    });

    try {
      final students = await _api.getStudentsByClass(cls.id);
      setState(() {
        _students = students;
        for (var s in students) {
          _attendance[s.id] = true; // Default to present
        }
        _isLoading = false;
      });
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error loading students: $e')),
        );
        setState(() => _isLoading = false);
      }
    }
  }

  Future<void> _submitAttendance() async {
    if (_selectedClass == null) return;

    setState(() => _isSubmitting = true);

    try {
      final payload = _students.map((s) => {
        'student_id': s.id,
        'status': _attendance[s.id] == true ? 'present' : 'absent',
      }).toList();

      await _api.bulkMarkAttendance(_selectedClass!.id, _selectedDate, payload);

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Attendance marked successfully!'),
            backgroundColor: Colors.green,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e'), backgroundColor: Colors.red),
        );
      }
    } finally {
      if (mounted) setState(() => _isSubmitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Mark Attendance'),
        actions: [
          Center(
            child: Padding(
              padding: const EdgeInsets.only(right: 16.0),
              child: Text(
                DateFormat('MMM dd, yyyy').format(_selectedDate),
                style: const TextStyle(fontWeight: FontWeight.bold),
              ),
            ),
          ),
        ],
      ),
      body: _isLoading 
          ? const Center(child: CircularProgressIndicator())
          : Column(
              children: [
                _buildClassPicker(),
                if (_selectedClass != null) _buildStudentList(),
              ],
            ),
      bottomNavigationBar: _selectedClass != null && _students.isNotEmpty
          ? Padding(
              padding: const EdgeInsets.all(16.0),
              child: ElevatedButton(
                onPressed: _isSubmitting ? null : _submitAttendance,
                style: ElevatedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  backgroundColor: Theme.of(context).primaryColor,
                  foregroundColor: Colors.white,
                ),
                child: _isSubmitting 
                    ? const CircularProgressIndicator(color: Colors.white)
                    : const Text('Submit Attendance', style: TextStyle(fontSize: 16)),
              ),
            )
          : null,
    );
  }

  Widget _buildClassPicker() {
    return Card(
      margin: const EdgeInsets.all(16),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        child: DropdownButtonHideUnderline(
          child: DropdownButton<ClassModel>(
            isExpanded: true,
            hint: const Text('Select Class'),
            value: _selectedClass,
            items: _classes.map((cls) {
              return DropdownMenuItem(
                value: cls,
                child: Text(cls.name),
              );
            }).toList(),
            onChanged: (cls) {
              if (cls != null) _loadStudents(cls);
            },
          ),
        ),
      ),
    );
  }

  Widget _buildStudentList() {
    if (_students.isEmpty) {
      return const Expanded(child: Center(child: Text('No students found in this class.')));
    }

    return Expanded(
      child: ListView.builder(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        itemCount: _students.length,
        itemBuilder: (context, index) {
          final s = _students[index];
          final isPresent = _attendance[s.id] ?? true;

          return Card(
            margin: const EdgeInsets.only(bottom: 8),
            child: ListTile(
              title: Text(s.fullName),
              subtitle: Text(s.email ?? ''),
              trailing: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    isPresent ? 'Present' : 'Absent',
                    style: TextStyle(
                      color: isPresent ? Colors.green : Colors.red,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Switch(
                    value: isPresent,
                    activeColor: Colors.green,
                    inactiveThumbColor: Colors.red,
                    inactiveTrackColor: Colors.red.withOpacity(0.5),
                    onChanged: (val) {
                      setState(() {
                        _attendance[s.id] = val;
                      });
                    },
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}
