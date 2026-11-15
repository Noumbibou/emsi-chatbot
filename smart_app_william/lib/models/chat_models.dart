class Source {
  final int page;
  final double score;
  final String text;

  Source({required this.page, required this.score, required this.text});

  factory Source.fromJson(Map<String, dynamic> json) => Source(
        page: json['page'] as int,
        score: (json['score'] as num).toDouble(),
        text: json['text'] as String,
      );
}

class ChatMessage {
  String text;
  final bool isUser;
  bool isError;
  List<Source> sources;

  ChatMessage({
    required this.text,
    required this.isUser,
    this.isError = false,
    this.sources = const [],
  });
}

/// Un morceau reçu pendant le streaming : soit un bout de texte, soit les sources.
class ChatChunk {
  final String? token;
  final List<Source>? sources;

  const ChatChunk({this.token, this.sources});
}