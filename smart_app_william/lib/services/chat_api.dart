import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import '../models/chat_models.dart';
import 'http_client_factory.dart'
    if (dart.library.js_interop) 'http_client_factory_web.dart';

class ChatApiException implements Exception {
  final String message;
  ChatApiException(this.message);

  @override
  String toString() => message;
}

class ChatApi {
  /// Version sans streaming (gardée en repli).
  Future<ChatMessage> ask(String question) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}/chat');
    try {
      final response = await http
          .post(
            uri,
            headers: {'Content-Type': 'application/json; charset=utf-8'},
            body: jsonEncode({'question': question}),
          )
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

  /// Version streaming : émet les sources puis les morceaux de texte.
  /// [history] contient les échanges précédents (mémoire de conversation).
  Stream<ChatChunk> askStream(
    String question, {
    List<ChatMessage> history = const [],
  }) async* {
    final client = createHttpClient();
    try {
      final request = http.Request(
        'POST',
        Uri.parse('${ApiConfig.baseUrl}/chat/stream'),
      )
        ..headers['Content-Type'] = 'application/json; charset=utf-8'
        ..body = jsonEncode({
          'question': question,
          'history': history
              .where((m) => !m.isError && m.text.trim().isNotEmpty)
              .map((m) => {
                    'role': m.isUser ? 'user' : 'assistant',
                    'content': m.text,
                  })
              .toList(),
        });

      final response =
          await client.send(request).timeout(const Duration(seconds: 180));

      if (response.statusCode != 200) {
        throw ChatApiException('Erreur du serveur (${response.statusCode}).');
      }

      final lines = response.stream
          .transform(utf8.decoder)
          .transform(const LineSplitter())
          // Délai maximal entre deux morceaux (chargement du modèle compris).
          .timeout(const Duration(seconds: 180));

      await for (final line in lines) {
        if (line.trim().isEmpty) continue;
        final event = jsonDecode(line) as Map<String, dynamic>;
        switch (event['type']) {
          case 'sources':
            yield ChatChunk(
              sources: (event['sources'] as List)
                  .map((s) => Source.fromJson(s as Map<String, dynamic>))
                  .toList(),
            );
          case 'token':
            yield ChatChunk(token: event['content'] as String);
          case 'error':
            throw ChatApiException(event['message'] as String);
          case 'done':
            return;
        }
      }
    } on TimeoutException {
      throw ChatApiException('Le serveur met trop de temps à répondre.');
    } on http.ClientException {
      throw ChatApiException(
        'Impossible de joindre le serveur. Vérifie que l’API est lancée '
        'et que l’adresse est correcte.',
      );
    } on FormatException {
      throw ChatApiException('Réponse du serveur illisible.');
    } finally {
      client.close();
    }
  }
}