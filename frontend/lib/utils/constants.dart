import 'package:flutter/foundation.dart';

class AppConstants {
  // Use 10.0.2.2 for Android Emulator to access host localhost
  // Use 127.0.0.1 for iOS Simulator or Web
  static const String baseUrl = kIsWeb 
      ? 'http://127.0.0.1:8000' 
      : 'http://10.0.2.2:8000';
}
