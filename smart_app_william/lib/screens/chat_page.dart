import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import '../config/api_config.dart';
import '../models/chat_models.dart';
import '../services/chat_api.dart';

class ChatPage extends StatefulWidget {
  const ChatPage({super.key});

  @override
  State<ChatPage> createState() => _ChatPageState();
}

class _ChatPageState extends State<ChatPage> {
  final _api = ChatApi();
  final _picker = ImagePicker();
  final _controller = TextEditingController();
  final _scroll = ScrollController();
  final List<ChatMessage> _messages = [
    ChatMessage(
      text:
          'Bonjour ! Je suis l’assistant de l’EMSI. '
          'Posez-moi vos questions sur l’école.',
      isUser: false,
    ),
  ];
  bool _loading = false;
  Uint8List? _selectedImageBytes;

  @override
  void dispose() {
    _controller.dispose();
    _scroll.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scroll.hasClients) {
        _scroll.animateTo(
          _scroll.position.maxScrollExtent,
          duration: const Duration(milliseconds: 150),
          curve: Curves.easeOut,
        );
      }
    });
  }

  Future<void> _pickImage() async {
    if (_loading) return;
    final XFile? picked = await _picker.pickImage(source: ImageSource.gallery);
    if (picked == null) return;
    final bytes = await picked.readAsBytes();
    if (!mounted) return;
    setState(() => _selectedImageBytes = bytes);
  }

  Future<void> _send() async {
    final question = _controller.text.trim();
    final imageToSend = _selectedImageBytes;

    // On autorise l'envoi si on a du texte OU une image
    if ((question.isEmpty && imageToSend == null) || _loading) return;

    final past = _messages.skip(1).toList();
    final history = past.length > 6 ? past.sublist(past.length - 6) : past;

    final displayQuestion = question.isNotEmpty
        ? question
        : 'Analyse cette image par rapport à la brochure EMSI.';

    final reply = ChatMessage(text: '', isUser: false);
    setState(() {
      _messages.add(
        ChatMessage(
          text: displayQuestion,
          isUser: true,
          userImageBytes: imageToSend,
        ),
      );
      _messages.add(reply);
      _loading = true;
      _selectedImageBytes = null;
    });
    _controller.clear();
    _scrollToBottom();

    try {
      await for (final chunk in _api.askStream(
        question,
        history: history,
        imageBytes: imageToSend,
      )) {
        if (!mounted) return;
        setState(() {
          if (chunk.token != null) reply.text += chunk.token!;
          if (chunk.sources != null) reply.sources = chunk.sources!;
          if (chunk.images != null) reply.images = chunk.images!;
        });
        _scrollToBottom();
      }
      if (mounted && reply.text.trim().isEmpty) {
        setState(() => reply.text = 'Je n’ai pas pu générer de réponse.');
      }
    } on ChatApiException catch (e) {
      _showError(reply, e.message);
    } catch (_) {
      _showError(reply, 'Une erreur inattendue est survenue.');
    } finally {
      if (mounted) {
        setState(() => _loading = false);
        _scrollToBottom();
      }
    }
  }

  void _showError(ChatMessage reply, String message) {
    if (!mounted) return;
    setState(() {
      if (reply.text.isEmpty) {
        reply.text = message;
        reply.isError = true;
      } else {
        reply.text = '${reply.text}\n\n[$message]';
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        backgroundColor: const Color(0xFF006B5F),
        title: const Row(
          children: [
            _BotAvatar(size: 38),
            SizedBox(width: 11),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'EMSI ChatBot',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
                ),
                SizedBox(height: 2),
                Row(
                  children: [
                    Icon(Icons.circle, size: 7, color: Color(0xFF8EE6A0)),
                    SizedBox(width: 5),
                    Text(
                      'En ligne',
                      style: TextStyle(fontSize: 11, color: Colors.white70),
                    ),
                  ],
                ),
              ],
            ),
          ],
        ),
        actions: [
          IconButton(
            tooltip: 'Nouvelle conversation',
            icon: const Icon(Icons.refresh),
            onPressed: _loading
                ? null
                : () => setState(() {
                    _messages.removeRange(1, _messages.length);
                    _selectedImageBytes = null;
                  }),
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: Container(
              decoration: const BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  colors: [Color(0xFFF3F8FA), Color(0xFFEAF3F6)],
                ),
              ),
              child: ListView.builder(
                controller: _scroll,
                padding: const EdgeInsets.fromLTRB(14, 18, 14, 18),
                itemCount: _messages.length,
                itemBuilder: (context, i) {
                  final m = _messages[i];
                  final waitingFirstToken =
                      _loading &&
                      i == _messages.length - 1 &&
                      !m.isUser &&
                      m.text.isEmpty &&
                      m.images.isEmpty;
                  if (waitingFirstToken) return const _TypingBubble();
                  return _MessageBubble(message: m);
                },
              ),
            ),
          ),
          if (_selectedImageBytes != null)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
              alignment: Alignment.centerLeft,
              child: Stack(
                children: [
                  ClipRRect(
                    borderRadius: BorderRadius.circular(14),
                    child: Image.memory(
                      _selectedImageBytes!,
                      height: 80,
                      width: 80,
                      fit: BoxFit.cover,
                    ),
                  ),
                  Positioned(
                    top: 0,
                    right: 0,
                    child: GestureDetector(
                      onTap: () => setState(() => _selectedImageBytes = null),
                      child: const CircleAvatar(
                        radius: 11,
                        backgroundColor: Colors.black54,
                        child: Icon(Icons.close, size: 14, color: Colors.white),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          SafeArea(
            child: Container(
              color: Colors.white,
              padding: const EdgeInsets.fromLTRB(10, 10, 10, 10),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  IconButton(
                    tooltip: 'Choisir une image',
                    onPressed: _loading ? null : _pickImage,
                    color: const Color(0xFF71818D),
                    icon: const Icon(Icons.attach_file_rounded),
                  ),
                  Expanded(
                    child: Container(
                      decoration: BoxDecoration(
                        color: const Color(0xFFF8FAFB),
                        border: Border.all(color: const Color(0xFFE5EBEF)),
                        borderRadius: BorderRadius.circular(24),
                      ),
                      child: TextField(
                        controller: _controller,
                        minLines: 1,
                        maxLines: 4,
                        textInputAction: TextInputAction.send,
                        onSubmitted: (_) => _send(),
                        decoration: const InputDecoration(
                          hintText: 'Posez votre question…',
                          filled: false,
                          border: InputBorder.none,
                          enabledBorder: InputBorder.none,
                          focusedBorder: InputBorder.none,
                          contentPadding: EdgeInsets.symmetric(
                            horizontal: 16,
                            vertical: 12,
                          ),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  SizedBox(
                    height: 46,
                    width: 46,
                    child: IconButton.filled(
                      onPressed: _loading ? null : _send,
                      style: IconButton.styleFrom(
                        backgroundColor: const Color(0xFF008C79),
                        foregroundColor: Colors.white,
                      ),
                      icon: const Icon(Icons.send_rounded, size: 20),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _MessageBubble extends StatelessWidget {
  final ChatMessage message;
  const _MessageBubble({required this.message});

  String _pages(List<Source> sources) {
    final pages = sources.map((s) => s.page).toSet().toList()..sort();
    return pages.join(', ');
  }

  @override
  Widget build(BuildContext context) {
    final isUser = message.isUser;
    final bg = message.isError
        ? const Color(0xFFFFE6E4)
        : isUser
        ? const Color(0xFFBDECC8)
        : Colors.white;
    final fg = message.isError
        ? const Color(0xFF8A2821)
        : const Color(0xFF263940);

    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          if (!isUser) ...[
            const Padding(
              padding: EdgeInsets.only(right: 7, bottom: 3),
              child: _BotAvatar(size: 28),
            ),
          ],
          Flexible(
            child: Container(
              margin: const EdgeInsets.symmetric(vertical: 5),
              padding: const EdgeInsets.all(13),
              constraints: BoxConstraints(
                maxWidth: MediaQuery.of(context).size.width * 0.78,
              ),
              decoration: BoxDecoration(
                color: bg,
                borderRadius: BorderRadius.only(
                  topLeft: const Radius.circular(18),
                  topRight: const Radius.circular(18),
                  bottomLeft: Radius.circular(isUser ? 18 : 5),
                  bottomRight: Radius.circular(isUser ? 5 : 18),
                ),
                boxShadow: [
                  BoxShadow(
                    color: const Color(0xFF15343D).withValues(alpha: 0.06),
                    blurRadius: 12,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (message.userImageBytes != null) ...[
                    ClipRRect(
                      borderRadius: BorderRadius.circular(12),
                      child: Image.memory(
                        message.userImageBytes!,
                        height: 160,
                        fit: BoxFit.cover,
                      ),
                    ),
                    const SizedBox(height: 8),
                  ],
                  if (message.text.isNotEmpty)
                    SelectableText(message.text, style: TextStyle(color: fg)),
                  if (message.images.isNotEmpty) ...[
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: message.images.map((img) {
                        final imgUrl = '${ApiConfig.baseUrl}${img.url}';
                        return Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            ClipRRect(
                              borderRadius: BorderRadius.circular(10),
                              child: Image.network(
                                imgUrl,
                                height: 130,
                                width: 180,
                                fit: BoxFit.cover,
                                errorBuilder: (_, _, _) => Container(
                                  height: 130,
                                  width: 180,
                                  color: Colors.black12,
                                  alignment: Alignment.center,
                                  child: const Text('Image indisponible'),
                                ),
                              ),
                            ),
                            const SizedBox(height: 2),
                            Text(
                              'Page ${img.page} (${img.file})',
                              style: TextStyle(
                                color: fg.withValues(alpha: 0.75),
                                fontSize: 11,
                              ),
                            ),
                          ],
                        );
                      }).toList(),
                    ),
                  ],
                  if (message.sources.isNotEmpty) ...[
                    const SizedBox(height: 8),
                    Text(
                      'Sources : pages ${_pages(message.sources)}',
                      style: TextStyle(
                        color: fg.withValues(alpha: 0.7),
                        fontSize: 12,
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _BotAvatar extends StatelessWidget {
  const _BotAvatar({required this.size});

  final double size;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: const BoxDecoration(
        color: Colors.white,
        shape: BoxShape.circle,
      ),
      alignment: Alignment.center,
      child: Text(
        'EMSI',
        style: TextStyle(
          color: const Color(0xFF008C79),
          fontSize: size * 0.25,
          fontWeight: FontWeight.w800,
        ),
      ),
    );
  }
}

class _TypingBubble extends StatelessWidget {
  const _TypingBubble();

  @override
  Widget build(BuildContext context) {
    return const Align(
      alignment: Alignment.centerLeft,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Padding(
            padding: EdgeInsets.only(right: 7, bottom: 3),
            child: _BotAvatar(size: 28),
          ),
          DecoratedBox(
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.all(Radius.circular(18)),
            ),
            child: Padding(
              padding: EdgeInsets.symmetric(horizontal: 14, vertical: 11),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                  SizedBox(width: 10),
                  Text('L’assistant réfléchit…'),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
