class ClassModel {
  final int id;
  final String name;
  final String classLevel;
  final String section;

  ClassModel({
    required this.id,
    required this.name,
    required this.classLevel,
    required this.section,
  });

  factory ClassModel.fromJson(Map<String, dynamic> json) {
    return ClassModel(
      id: json['id'],
      name: json['name'],
      classLevel: json['class_level'],
      section: json['section'],
    );
  }
}
