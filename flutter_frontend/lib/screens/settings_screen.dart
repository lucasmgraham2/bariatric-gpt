import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:bariatric_gpt/providers/theme_provider.dart';
import 'package:bariatric_gpt/services/auth_service.dart';
import 'package:bariatric_gpt/services/settings_service.dart'; // Import new service
import 'package:bariatric_gpt/screens/login_screen.dart';
import 'package:bariatric_gpt/screens/profile_screen.dart';

// Convert to StatefulWidget
class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  // Add state variables
  final SettingsService _settingsService = SettingsService();
  bool _notificationsEnabled = true;
  ThemeMode _themeMode = ThemeMode.system;
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadSettings();
  }

  // Load saved settings from the service
  Future<void> _loadSettings() async {
    final notifications = await _settingsService.areNotificationsEnabled();
    final theme = await _settingsService.getThemeMode();
    setState(() {
      _notificationsEnabled = notifications;
      _themeMode = theme;
      _isLoading = false;
    });
  }

  // Helper function to show a feature that is coming soon
  void _showComingSoon() {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Feature coming soon!')),
    );
  }
  
  // Helper function to get theme name as a string
  String get _themeModeName {
    switch (_themeMode) {
      case ThemeMode.light:
        return 'Light Mode';
      case ThemeMode.dark:
        return 'Dark Mode';
      case ThemeMode.system:
      default:
        return 'System Default';
    }
  }

  @override
  Widget build(BuildContext context) {
    // Helper function to create list tiles for settings
    Widget buildSettingsTile({
      required String title,
      required IconData icon,
      required VoidCallback onTap,
      String? subtitle,
    }) {
      final iconColor = Theme.of(context).colorScheme.onSurfaceVariant;
      return ListTile(
        leading: Icon(icon, color: iconColor),
        title: Text(title),
        subtitle: subtitle != null ? Text(subtitle) : null,
        trailing: Icon(Icons.arrow_forward_ios, size: 16, color: iconColor),
        onTap: onTap,
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('Settings'),
        centerTitle: true,
      ),
      // Show loading indicator while settings are loaded
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              children: [
                // Profile Section
                const Padding(
                  padding: EdgeInsets.all(16.0),
                  child: Text('Account', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
                ),
                buildSettingsTile(
                  title: 'Edit Profile',
                  icon: Icons.person_outline,
                  onTap: () {
                    Navigator.of(context).push(MaterialPageRoute(builder: (_) => const ProfileScreen()));
                  },
                ),
                buildSettingsTile(
                  title: 'Change Password',
                  icon: Icons.lock_outline,
                  onTap: _showComingSoon, // Mock implementation
                ),
                const Divider(),

                // Preferences Section
                const Padding(
                  padding: EdgeInsets.all(16.0),
                  child: Text('Preferences', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
                ),
                SwitchListTile(
                  secondary: Icon(Icons.notifications_outlined, color: Theme.of(context).colorScheme.onSurfaceVariant),
                  title: const Text('Enable Notifications'),
                  value: _notificationsEnabled,
                  onChanged: (bool value) async {
                    // Save the new setting and update the UI
                    await _settingsService.setNotificationsEnabled(value);
                    setState(() {
                      _notificationsEnabled = value;
                    });
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(content: Text('Notifications ${value ? "enabled" : "disabled"}')),
                    );
                  },
                ),
                buildSettingsTile(
                  title: 'Appearance',
                  subtitle: _themeModeName,
                  icon: Icons.color_lens_outlined,
                  onTap: () {
                    // Show a dialog to change the theme
                    showDialog(
                      context: context,
                      builder: (dialogContext) => AlertDialog(
                        title: const Text('Choose Theme'),
                        content: Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            RadioListTile<ThemeMode>(
                              title: const Text('Light Mode'),
                              value: ThemeMode.light,
                              groupValue: _themeMode,
                              onChanged: (ThemeMode? value) {
                                if (value != null) {
                                  Provider.of<ThemeProvider>(context, listen: false).setTheme(value);
                                  setState(() => _themeMode = value);
                                  Navigator.of(dialogContext).pop();
                                }
                              },
                            ),
                            RadioListTile<ThemeMode>(
                              title: const Text('Dark Mode'),
                              value: ThemeMode.dark,
                              groupValue: _themeMode,
                              onChanged: (ThemeMode? value) {
                                if (value != null) {
                                  Provider.of<ThemeProvider>(context, listen: false).setTheme(value);
                                  setState(() => _themeMode = value);
                                  Navigator.of(dialogContext).pop();
                                }
                              },
                            ),
                          ],
                        ),
                      ),
                    );
                  },
                ),
                const Divider(),

                // About Section and Logout Button ... (keep this part the same)
                 const Padding(
                  padding: EdgeInsets.all(16.0),
                  child: Text('About', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
                ),
                buildSettingsTile(
                  title: 'About Bariatric GPT',
                  icon: Icons.info_outline,
                  onTap: () {
                    showAboutDialog(
                      context: context,
                      applicationName: 'Bariatric GPT',
                      applicationVersion: '1.0.0',
                      applicationLegalese: '© 2025 Your Company',
                    );
                  },
                ),
                const Divider(),
                Padding(
                  padding: const EdgeInsets.all(16.0),
                  child: TextButton(
                    style: TextButton.styleFrom(
                      foregroundColor: Colors.red,
                      padding: const EdgeInsets.symmetric(vertical: 12),
                    ),
                    onPressed: () async {
                      await AuthService().logout();
                      Navigator.of(context).pushAndRemoveUntil(
                        MaterialPageRoute(builder: (context) => const LoginScreen()),
                        (Route<dynamic> route) => false,
                      );
                    },
                    child: const Text('Logout', style: TextStyle(fontSize: 16)),
                  ),
                ),
              ],
            ),
    );
  }
}