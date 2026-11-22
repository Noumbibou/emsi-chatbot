import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_tts/flutter_tts.dart';

class ChatIntroPage extends StatefulWidget {
  const ChatIntroPage({super.key});

  @override
  State<ChatIntroPage> createState() => _ChatIntroPageState();
}

class _ChatIntroPageState extends State<ChatIntroPage>
    with SingleTickerProviderStateMixin {
  static const _greeting =
      'Bonjour, je suis l’assistant de l’EMSI. '
      'Je suis là pour répondre à vos questions sur nos formations et notre école.';

  final FlutterTts _tts = FlutterTts();
  late final AnimationController _pulse;
  Completer<void>? _speechCompletion;
  bool _isSpeaking = true;
  bool _voiceUnavailable = false;
  bool _isOpeningChat = false;

  @override
  void initState() {
    super.initState();
    _pulse = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1500),
    )..repeat(reverse: true);
    _tts.setCompletionHandler(_completeSpeech);
    _tts.setErrorHandler((_) => _handleSpeechError());
    WidgetsBinding.instance.addPostFrameCallback((_) => _introduce());
  }

  Future<void> _introduce() async {
    if (!mounted) return;
    final startedAt = DateTime.now();
    var voiceUnavailable = false;
    final speechCompletion = Completer<void>();
    _speechCompletion = speechCompletion;

    try {
      final languageResult = await _tts.setLanguage('fr-FR');
      if (languageResult == false ||
          languageResult == -1 ||
          languageResult == -2) {
        voiceUnavailable = true;
      } else {
        await _tts.setSpeechRate(0.47);
        await _tts.setPitch(1.0);
        await _tts.awaitSpeakCompletion(false);
        unawaited(_speakGreeting());
        await speechCompletion.future;
      }
    } on PlatformException {
      voiceUnavailable = true;
    } on MissingPluginException {
      voiceUnavailable = true;
    }

    if (!mounted || _isOpeningChat) return;
    _speechCompletion = null;
    setState(() {
      _isSpeaking = false;
      _voiceUnavailable = _voiceUnavailable || voiceUnavailable;
    });

    const introDuration = Duration(seconds: 4);
    final remaining = introDuration - DateTime.now().difference(startedAt);
    if (remaining > Duration.zero) await Future.delayed(remaining);
    if (mounted && !_isOpeningChat) _openChat();
  }

  Future<void> _speakGreeting() async {
    try {
      final result = await _tts.speak(_greeting);
      if (result == false || result == 0) _handleSpeechError();
    } on PlatformException {
      _handleSpeechError();
    } on MissingPluginException {
      _handleSpeechError();
    }
  }

  void _completeSpeech() {
    final completion = _speechCompletion;
    if (completion != null && !completion.isCompleted) completion.complete();
  }

  void _handleSpeechError() {
    if (mounted && !_isOpeningChat) {
      setState(() {
        _voiceUnavailable = true;
        _isSpeaking = false;
      });
    }
    _completeSpeech();
  }

  void _openChat() {
    if (_isOpeningChat) return;
    _isOpeningChat = true;
    _completeSpeech();
    unawaited(_stopSpeech());
    Navigator.of(context).pushReplacementNamed('/chat');
  }

  Future<void> _stopSpeech() async {
    try {
      await _tts.stop();
    } on PlatformException {
      if (mounted && !_isOpeningChat) {
        setState(() => _voiceUnavailable = true);
      }
    } on MissingPluginException {
      if (mounted && !_isOpeningChat) {
        setState(() => _voiceUnavailable = true);
      }
    }
  }

  @override
  void dispose() {
    _pulse.dispose();
    unawaited(_stopSpeech());
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF071A24),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 560),
              child: Container(
                padding: const EdgeInsets.fromLTRB(28, 38, 28, 28),
                decoration: BoxDecoration(
                  color: const Color(0xFF102833),
                  borderRadius: BorderRadius.circular(32),
                  border: Border.all(
                    color: Colors.white.withValues(alpha: 0.08),
                  ),
                  boxShadow: [
                    BoxShadow(
                      color: const Color(0xFF00C6A2).withValues(alpha: 0.12),
                      blurRadius: 60,
                      spreadRadius: 4,
                    ),
                  ],
                ),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(
                          Icons.auto_awesome,
                          size: 18,
                          color: Color(0xFF75E8C4),
                        ),
                        SizedBox(width: 8),
                        Text(
                          'EMSI INTELLIGENCE',
                          style: TextStyle(
                            color: Color(0xFFB7CFD2),
                            fontSize: 11,
                            letterSpacing: 2,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 34),
                    AnimatedBuilder(
                      animation: _pulse,
                      builder: (context, child) {
                        final scale = 1 + (_pulse.value * 0.045);
                        return Transform.scale(scale: scale, child: child);
                      },
                      child: Container(
                        width: 154,
                        height: 154,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          gradient: const LinearGradient(
                            begin: Alignment.topLeft,
                            end: Alignment.bottomRight,
                            colors: [Color(0xFF42E0B8), Color(0xFF087F77)],
                          ),
                          boxShadow: [
                            BoxShadow(
                              color: const Color(0xFF21C6A2)
                                  .withValues(alpha: 0.30),
                              blurRadius: 42,
                              spreadRadius: 8,
                            ),
                          ],
                        ),
                        child: const Icon(
                          Icons.graphic_eq_rounded,
                          size: 72,
                          color: Colors.white,
                        ),
                      ),
                    ),
                    const SizedBox(height: 34),
                    const Text(
                      'Bonjour, je suis l’assistant de l’EMSI.',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 25,
                        height: 1.3,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 12),
                    const Text(
                      'Je suis là pour répondre à vos questions sur nos formations et notre école.',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        color: Color(0xFFB7CFD2),
                        fontSize: 15,
                        height: 1.6,
                      ),
                    ),
                    const SizedBox(height: 28),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(
                          _voiceUnavailable
                              ? Icons.volume_off_outlined
                              : _isSpeaking
                              ? Icons.graphic_eq_rounded
                              : Icons.check_circle_outline_rounded,
                          size: 18,
                          color: _voiceUnavailable
                              ? const Color(0xFFFFC078)
                              : const Color(0xFF75E8C4),
                        ),
                        const SizedBox(width: 8),
                        Flexible(
                          child: Text(
                            _voiceUnavailable
                                ? 'La voix n’est pas disponible dans ce navigateur.'
                                : _isSpeaking
                                ? 'Votre assistant vous salue…'
                                : 'Préparation de votre espace de discussion…',
                            textAlign: TextAlign.center,
                            style: TextStyle(
                              color: _voiceUnavailable
                                  ? const Color(0xFFFFC078)
                                  : const Color(0xFFB7CFD2),
                              fontSize: 13,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 28),
                    const ClipRRect(
                      borderRadius: BorderRadius.all(Radius.circular(4)),
                      child: LinearProgressIndicator(
                        minHeight: 3,
                        backgroundColor: Color(0xFF29434D),
                        valueColor: AlwaysStoppedAnimation<Color>(
                          Color(0xFF42E0B8),
                        ),
                      ),
                    ),
                    const SizedBox(height: 22),
                    TextButton(
                      onPressed: _openChat,
                      style: TextButton.styleFrom(
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(
                          horizontal: 18,
                          vertical: 12,
                        ),
                      ),
                      child: const Text('Passer à la conversation'),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
