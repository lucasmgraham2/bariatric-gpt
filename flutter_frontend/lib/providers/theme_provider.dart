import 'package:flutter/material.dart';
import 'package:bariatric_gpt/services/settings_service.dart';

class ThemeProvider with ChangeNotifier {
  final SettingsService _settingsService = SettingsService();
  ThemeMode _themeMode = ThemeMode.system;

  ThemeMode get themeMode => _themeMode;

  ThemeProvider() {
    loadTheme();
  }

  void loadTheme() async {
    _themeMode = await _settingsService.getThemeMode();
    notifyListeners();
  }

  void setTheme(ThemeMode themeMode) async {
    _themeMode = themeMode;
    await _settingsService.setThemeMode(themeMode);
    notifyListeners();
  }
}