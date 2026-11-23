import 'package:flutter_dotenv/flutter_dotenv.dart';

class SupabaseConfig {
  static const dartUrl = String.fromEnvironment('SUPABASE_URL');
  static const dartAnonKey = String.fromEnvironment('SUPABASE_ANON_KEY');

  static String get url =>
      dartUrl.isNotEmpty ? dartUrl : dotenv.env['SUPABASE_URL'] ?? '';

  static String get anonKey => dartAnonKey.isNotEmpty
      ? dartAnonKey
      : dotenv.env['SUPABASE_ANON_KEY'] ?? '';

  static bool get isConfigured => url.isNotEmpty && anonKey.isNotEmpty;
}
