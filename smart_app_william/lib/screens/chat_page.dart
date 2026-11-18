import 'package:flutter/material.dart';

import '../models/chat_models.dart';
import '../services/chat_api.dart';

class ChatPage extends StatefulWidget {
  const ChatPage({super.key});

  @override
  State<ChatPage> createState() => _ChatPageState();
}

class _ChatPageState extends State<ChatPage> {
  final _api = ChatApi();
  final _controller = TextEditingController();
  final _scroll = ScrollController();
  final List<ChatMessage> _messages = [
    ChatMessage(
      text: 'Bonjour ! Je suis l’assistant de l’EMSI. '
          'Posez-moi vos questions sur l’école.',
      isUser: false,
    ),
  ];
  bool _loading = false;

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

  Future<void> _send() async {
    final question = _controller.text.trim();
    if (question.isEmpty || _loading) return;

    // Bulle de réponse vide, remplie au fil du streaming.
    // Historique envoyé au serveur : les échanges précédents, sans le message
    // d'accueil. On le prépare AVANT d'ajouter la nouvelle question.
    final past = _messages.skip(1).toList();
    final history = past.length > 6 ? past.sublist(past.length - 6) : past;

    // Bulle de réponse vide, remplie au fil du streaming.
    final reply = ChatMessage(text: '', isUser: false);
    setState(() {
      _messages.add(ChatMessage(text: question, isUser: true));
      _messages.add(reply);
      _loading = true;
    });
    _controller.clear();
    _scrollToBottom();

    try {
      await for (final chunk in _api.askStream(question, history: history)) {
        if (!mounted) return;
        setState(() {
          if (chunk.token != null) reply.text += chunk.token!;
          if (chunk.sources != null) reply.sources = chunk.sources!;
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
        title: const Text('EMSI ChatBot'),
        actions: [
          IconButton(
            tooltip: 'Nouvelle conversation',
            icon: const Icon(Icons.refresh),
            onPressed: _loading
                ? null
                : () => setState(() => _messages.removeRange(1, _messages.length)),
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: ListView.builder(
              controller: _scroll,
              padding: const EdgeInsets.all(12),
              itemCount: _messages.length,
              itemBuilder: (context, i) {
                final m = _messages[i];
                final waitingFirstToken = _loading &&
                    i == _messages.length - 1 &&
                    !m.isUser &&
                    m.text.isEmpty;
                if (waitingFirstToken) return const _TypingBubble();
                return _MessageBubble(message: m);
              },
            ),
          ),
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(12, 4, 12, 12),
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _controller,
                      minLines: 1,
                      maxLines: 4,
                      textInputAction: TextInputAction.send,
                      onSubmitted: (_) => _send(),
                      decoration: InputDecoration(
                        hintText: 'Posez votre question…',
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(24),
                        ),
                        contentPadding: const EdgeInsets.symmetric(
                          horizontal: 16,
                          vertical: 10,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  IconButton.filled(
                    onPressed: _loading ? null : _send,
                    icon: const Icon(Icons.send),
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
    final scheme = Theme.of(context).colorScheme;
    final isUser = message.isUser;
    final bg = message.isError
        ? scheme.errorContainer
        : isUser
            ? scheme.primary
            : scheme.surfaceContainerHighest;
    final fg = message.isError
        ? scheme.onErrorContainer
        : isUser
            ? scheme.onPrimary
            : scheme.onSurface;

    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 4),
        padding: const EdgeInsets.all(12),
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.8,
        ),
        decoration: BoxDecoration(
          color: bg,
          borderRadius: BorderRadius.circular(16),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SelectableText(message.text, style: TextStyle(color: fg)),
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
    );
  }
}

class _TypingBubble extends StatelessWidget {
  const _TypingBubble();

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 4),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: scheme.surfaceContainerHighest,
          borderRadius: BorderRadius.circular(16),
        ),
        child: const Row(
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
    );
  }
}