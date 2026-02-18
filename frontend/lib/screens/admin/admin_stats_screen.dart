import 'package:flutter/material.dart';
import '../../models/attendance_model.dart';
import '../../models/class_model.dart';
import '../../services/api_service.dart';
import 'package:provider/provider.dart';
import '../../providers/auth_provider.dart';

class AdminStatsScreen extends StatefulWidget {
  const AdminStatsScreen({super.key});

  @override
  State<AdminStatsScreen> createState() => _AdminStatsScreenState();
}

class _AdminStatsScreenState extends State<AdminStatsScreen> {
  final ApiService _api = ApiService();
  List<ClassModel> _classes = [];
  ClassModel? _selectedClass;
  ClassAttendanceStats? _stats;
  
  bool _isLoadingClasses = true;
  bool _isLoadingStats = false;

  @override
  void initState() {
    super.initState();
    _loadClasses();
  }

  Future<void> _loadClasses() async {
    try {
      final classes = await _api.getClasses();
      setState(() {
        _classes = classes;
        _isLoadingClasses = false;
      });
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error loading classes: $e')),
        );
        setState(() => _isLoadingClasses = false);
      }
    }
  }

  Future<void> _loadStats(ClassModel cls) async {
    setState(() {
      _selectedClass = cls;
      _isLoadingStats = true;
      _stats = null;
    });

    try {
      final stats = await _api.getClassStats(cls.id);
      setState(() {
        _stats = stats;
        _isLoadingStats = false;
      });
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error loading stats: $e')),
        );
        setState(() => _isLoadingStats = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = Provider.of<AuthProvider>(context, listen: false);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Attendance Analytics'),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: () => auth.logout().then((_) {
              Navigator.pushReplacementNamed(context, '/login');
            }),
          ),
        ],
      ),
      body: _isLoadingClasses 
          ? const Center(child: CircularProgressIndicator())
          : Column(
              children: [
                _buildClassPicker(),
                if (_isLoadingStats) 
                  const Expanded(child: Center(child: CircularProgressIndicator()))
                else if (_stats != null)
                  _buildStatsContent()
                else if (_selectedClass != null)
                  const Expanded(child: Center(child: Text('Data Not Found')))
                else
                  const Expanded(child: Center(child: Text('Select a class to view analytics'))),
              ],
            ),
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
              if (cls != null) _loadStats(cls);
            },
          ),
        ),
      ),
    );
  }

  Widget _buildStatsContent() {
    return Expanded(
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _buildMetricCard(
            'Attendance Percentage', 
            '${_stats!.attendancePercentage.toStringAsFixed(1)}%',
            Icons.percent,
            Colors.teal,
          ),
          const SizedBox(height: 16),
          _buildMetricCard(
            'Total Records', 
            _stats!.totalRecords.toString(),
            Icons.history,
            Colors.blue,
          ),
          const SizedBox(height: 16),
          _buildMetricCard(
            'Student Count', 
            _stats!.totalStudents.toString(),
            Icons.people,
            Colors.orange,
          ),
        ],
      ),
    );
  }

  Widget _buildMetricCard(String title, String value, IconData icon, Color color) {
    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(24.0),
        child: Row(
          children: [
            CircleAvatar(
              radius: 30,
              backgroundColor: color.withOpacity(0.1),
              child: Icon(icon, color: color, size: 30),
            ),
            const SizedBox(width: 24),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: const TextStyle(fontSize: 16, color: Colors.grey)),
                const SizedBox(height: 4),
                Text(value, style: const TextStyle(fontSize: 32, fontWeight: FontWeight.bold)),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
