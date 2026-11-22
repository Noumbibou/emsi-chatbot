import 'dart:typed_data';

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

class ImageResult {
  final String file;
  final int page;
  final double score;
  final double rrfScore;
  final String context;
  final String url;

  ImageResult({
    required this.file,
    required this.page,
    required this.score,
    required this.rrfScore,
    required this.context,
    required this.url,
  });

  factory ImageResult.fromJson(Map<String, dynamic> json) => ImageResult(
        file: json['file'] as String,
        page: json['page'] as int,
        score: (json['score'] as num).toDouble(),
        rrfScore: (json['rrf_score'] as num?)?.toDouble() ?? 0.0,
        context: (json['context'] as String?) ?? '',
        url: json['url'] as String,
      );
}

class ChatMessage {
  String text;
  final bool isUser;
  bool isError;
  List<Source> sources;
  List<ImageResult> images;
  Uint8List? userImageBytes;

  ChatMessage({
    required this.text,
    required this.isUser,
    this.isError = false,
    this.sources = const [],
    this.images = const [],
    this.userImageBytes,
  });
}

class ChatChunk {
  final String? token;
  final List<Source>? sources;
  final List<ImageResult>? images;

  const ChatChunk({this.token, this.sources, this.images});
}