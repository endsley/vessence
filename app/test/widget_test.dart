import 'package:flutter_test/flutter_test.dart';

import 'package:ambient/app.dart';

void main() {
  testWidgets('App renders without crashing', (WidgetTester tester) async {
    await tester.pumpWidget(const AmbientApp());
    expect(find.text('Ambient'), findsOneWidget);
  });
}
