// Bariatric GPT Widget Tests
//
// Add your widget tests here as you develop new features.
// For now, this file contains basic smoke tests.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:bariatric_gpt/main.dart';

void main() {
  testWidgets('App loads welcome screen', (WidgetTester tester) async {
    // Build our app and trigger a frame.
    await tester.pumpWidget(const MyApp());

    // Verify that our welcome screen loads
    expect(find.text('Welcome to Bariatric GPT'), findsOneWidget);
    expect(find.text('Your AI companion for bariatric surgery support'), findsOneWidget);
  });

  testWidgets('App has correct title', (WidgetTester tester) async {
    // Build our app and trigger a frame.
    await tester.pumpWidget(const MyApp());

    // Verify that the app bar title is correct
    expect(find.text('Bariatric GPT'), findsOneWidget);
  });
}
