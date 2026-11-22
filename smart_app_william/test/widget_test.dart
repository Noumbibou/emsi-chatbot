import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:smart_app_william/screens/chat_intro_page.dart';
import 'package:smart_app_william/main.dart';

void main() {
  testWidgets('affiche la connexion EMSI sans option Google', (tester) async {
    await tester.pumpWidget(const MyApp());
    await tester.pumpAndSettle();

    expect(find.text('Bienvenue !'), findsOneWidget);
    expect(find.text('Se connecter'), findsOneWidget);
    expect(find.text('Continuer avec Google'), findsNothing);
  });

  testWidgets('présente le message avant de passer au chatbot', (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(
      MaterialApp(
        home: const ChatIntroPage(),
        routes: {'/chat': (_) => const Scaffold(body: Text('Chat prêt'))},
      ),
    );
    await tester.pump();

    expect(
      find.text('Bonjour, je suis l’assistant de l’EMSI.'),
      findsOneWidget,
    );
    await tester.tap(find.text('Passer à la conversation'));
    await tester.pumpAndSettle();

    expect(find.text('Chat prêt'), findsOneWidget);
  });
}
