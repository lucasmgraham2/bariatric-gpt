import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:bariatric_gpt/screens/patient_management_screen.dart';

void main() {
  testWidgets('PatientManagementScreen renders correctly', (WidgetTester tester) async {
    // Build the PatientManagementScreen widget
    await tester.pumpWidget(const MaterialApp(home: PatientManagementScreen()));

    // Verify the screen renders with expected UI elements
    expect(find.byType(PatientManagementScreen), findsOneWidget);
    expect(find.text('Save All Preferences'), findsOneWidget);
  });
}
