import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../services/profile_service.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({Key? key}) : super(key: key);

  @override
  _ProfileScreenState createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  final _formKey = GlobalKey<FormState>();
  final ProfileService _profileService = ProfileService();

  bool _loading = true;
  bool _saving = false;
  Map<String, dynamic> _profile = {};

  final TextEditingController _allergiesController = TextEditingController();
  final TextEditingController _dietTypeController = TextEditingController();
  final TextEditingController _dislikedController = TextEditingController();
  final TextEditingController _surgeryDateController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _loadProfile();
  }

  @override
  void dispose() {
    _allergiesController.dispose();
    _dietTypeController.dispose();
    _dislikedController.dispose();
    _surgeryDateController.dispose();
    super.dispose();
  }

  Future<void> _loadProfile() async {
    setState(() {
      _loading = true;
    });

    final result = await _profileService.fetchProfile();

    if (result['success'] == true) {
      _profile = Map<String, dynamic>.from(result['profile'] ?? {});
      _dislikedController.text = ((_profile['disliked_foods'] ?? []) as List).join(', ');
      _allergiesController.text = ((_profile['allergies'] ?? []) as List).join(', ');
      _dietTypeController.text = (_profile['diet_type'] ?? '') as String;
      final sd = _profile['surgery_date'];
      _surgeryDateController.text = sd != null ? sd.toString() : '';
    } else {
      // If not authenticated or not found, keep defaults
      // Optionally show a snackbar
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(result['error'] ?? 'Failed to load profile')));
      }
    }

    setState(() {
      _loading = false;
    });
  }

  Future<void> _saveProfile() async {
  if (!_formKey.currentState!.validate()) return;

    setState(() {
      _saving = true;
    });

    final profileToSave = {
      'disliked_foods': _dislikedController.text.split(',').map((s) => s.trim()).where((s) => s.isNotEmpty).toList(),
      'allergies': _allergiesController.text.split(',').map((s) => s.trim()).where((s) => s.isNotEmpty).toList(),
      'diet_type': _dietTypeController.text.trim(),
      'surgery_date': _surgeryDateController.text.trim(),
    };

    final result = await _profileService.updateProfile(profileToSave);

    setState(() {
      _saving = false;
    });

    if (result['success'] == true) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Profile saved')));
      }
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(result['error'] ?? 'Failed to save profile')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Profile Preferences'),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : Padding(
              padding: const EdgeInsets.all(16.0),
              child: Form(
                key: _formKey,
                child: ListView(
                  children: [
                    const Text('Food you dislike', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                    const SizedBox(height: 8),
                    TextFormField(
                      controller: _dislikedController,
                      decoration: const InputDecoration(hintText: 'Comma-separated, e.g., broccoli, liver'),
                      textInputAction: TextInputAction.next,
                    ),
                    const SizedBox(height: 16),
                    const Text('Allergies / intolerances', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                    const SizedBox(height: 8),
                    TextFormField(
                      controller: _allergiesController,
                      decoration: const InputDecoration(hintText: 'Comma-separated, e.g., nuts, dairy'),
                      textInputAction: TextInputAction.next,
                    ),
                    const SizedBox(height: 16),
                    const Text('Diet type (vegetarian / pescatarian / etc.)', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                    const SizedBox(height: 8),
                    TextFormField(
                      controller: _dietTypeController,
                      decoration: const InputDecoration(hintText: 'e.g., vegetarian, pescatarian, omnivore'),
                      textInputAction: TextInputAction.next,
                    ),
                    const SizedBox(height: 16),
                    const Text('Surgery date', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                    const SizedBox(height: 8),
                    TextFormField(
                      controller: _surgeryDateController,
                      readOnly: true,
                      decoration: const InputDecoration(hintText: 'Tap to pick date'),
                      onTap: () async {
                        final picked = await showDatePicker(
                          context: context,
                          initialDate: DateTime.now(),
                          firstDate: DateTime(2000),
                          lastDate: DateTime(2100),
                        );
                        if (picked != null) {
                          _surgeryDateController.text = picked.toIso8601String().split('T').first;
                        }
                      },
                    ),
                    const SizedBox(height: 24),
                    ElevatedButton(
                      onPressed: _saving ? null : _saveProfile,
                      child: _saving ? const CircularProgressIndicator(color: Colors.white) : const Text('Save Preferences'),
                    ),
                    const SizedBox(height: 12),
                    TextButton(
                      onPressed: () async {
                        // Reset to defaults
                        _dislikedController.clear();
                        _allergiesController.clear();
                        _dietTypeController.clear();
                        _surgeryDateController.clear();
                        await _saveProfile();
                      },
                      child: const Text('Clear and Save'),
                    ),
                  ],
                ),
              ),
            ),
    );
  }
}
