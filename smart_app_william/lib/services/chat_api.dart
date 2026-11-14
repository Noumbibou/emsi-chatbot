import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import '../models/chat_models.dart';

class ChatApiException implements Exception {
  final String message;
  ChatApiException(this.message);

  @override
  String toString() => message;
}

class ChatApi {
  Future<ChatMessage> ask(String question) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}/chat');
    try {
      final response = await http
          .post(
            uri,
            headers: {'Content-Type': 'application/json; charset=utf-8'},
            body: jsonEncode({'question': question}),
          )
          // Le LLM tourne sur CPU : la première réponse peut être longue.
          .timeout(const Duration(seconds: 180));

      if (response.statusCode != 200) {
        throw ChatApiException('Erreur du serveur (${response.statusCode}).');
      }

      final data =
          jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
      final sources = (data['sources'] as List)
          .map((s) => Source.fromJson(s as Map<String, dynamic>))
          .toList();

      return ChatMessage(
        text: data['answer'] as String,
        isUser: false,
        sources: sources,
      );
    } on TimeoutException {
      throw ChatApiException('Le serveur met trop de temps à répondre.');
    } on http.ClientException {
      throw ChatApiException(
        'Impossible de joindre le serveur. Vérifie que l’API est lancée '
        'et que l’adresse est correcte.',
      );
    } on FormatException {
      throw ChatApiException('Réponse du serveur illisible.');
    }
  }
}