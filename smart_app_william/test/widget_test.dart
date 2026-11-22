import 'package:flutter_test/flutter_test.dart';

import 'package:smart_app_william/main.dart';

void main() {
  testWidgets('affiche la connexion EMSI sans option Google', (tester) async {
    await tester.pumpWidget(const MyApp());
    await tester.pumpAndSettle();

    expect(find.text('Bienvenue !'), findsOneWidget);
    expect(find.text('Se connecter'), findsOneWidget);
    expect(find.text('Continuer avec Google'), findsNothing);
  });
}
