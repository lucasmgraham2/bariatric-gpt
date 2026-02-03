import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../services/profile_service.dart'; // Make sure this path is correct

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key});

  @override
  _ProfileScreenState createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  final _formKey = GlobalKey<FormState>();
  final ProfileService _profileService = ProfileService();

  bool _loading = true;
  bool _saving = false;
  Map<String, dynamic> _profile = {};

  final TextEditingController _usernameController = TextEditingController();
  final TextEditingController _emailController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _loadProfile();
  }

  @override
  void dispose() {
    _usernameController.dispose();
    _emailController.dispose();
    super.dispose();
  }

  Future<void> _loadProfile() async {
    setState(() {
      _loading = true;
    });

    final result = await _profileService.fetchProfile();

    if (result['success'] == true) {
      _profile = Map<String, dynamic>.from(result['profile'] ?? {});
      // Load personal info fields
      _usernameController.text = (_profile['username'] ?? '') as String;
      _emailController.text = (_profile['email'] ?? '') as String;
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(result['error'] ?? 'Failed to load profile')));
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

    // IMPORTANT: Create a copy to avoid deleting other profile data (like diet)
    final profileToSave = Map<String, dynamic>.from(_profile);

    // Update only the fields relevant to this screen
    profileToSave['username'] = _usernameController.text.trim();
    profileToSave['email'] = _emailController.text.trim();

    final result = await _profileService.updateProfile(profileToSave);

    setState(() {
      _saving = false;
    });

    if (result['success'] == true) {
      // Update the local _profile state
      _profile = profileToSave;
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('Profile saved')));
      }
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(result['error'] ?? 'Failed to save profile')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Personal Information'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadProfile,
            tooltip: 'Reload Profile',
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : Padding(
              padding: const EdgeInsets.all(16.0),
              child: Form(
                key: _formKey,
                child: ListView(
                  children: [
                    const Text('Username',
                        style: TextStyle(
                            fontSize: 16, fontWeight: FontWeight.bold)),
                    const SizedBox(height: 8),
                    TextFormField(
                      controller: _usernameController,
                      decoration:
                          const InputDecoration(hintText: 'Your display name'),
                      textInputAction: TextInputAction.next,
                      validator: (value) {
                        if (value == null || value.trim().isEmpty) {
                          return 'Username cannot be empty';
                        }
                        return null;
                      },
                    ),
                    const SizedBox(height: 16),
                    const Text('Email Address',
                        style: TextStyle(
                            fontSize: 16, fontWeight: FontWeight.bold)),
                    const SizedBox(height: 8),
                    TextFormField(
                      controller: _emailController,
                      decoration:
                          const InputDecoration(hintText: 'e.g., user@example.com'),
                      keyboardType: TextInputType.emailAddress,
                      textInputAction: TextInputAction.done,
                       validator: (value) {
                        if (value == null || value.trim().isEmpty) {
                          return 'Email cannot be empty';
                        }
                        // Simple email validation
                        if (!value.contains('@') || !value.contains('.')) {
                           return 'Please enter a valid email';
                        }
                        return null;
                      },
                    ),
                    const SizedBox(height: 24),
                    ElevatedButton(
                      onPressed: _saving ? null : _saveProfile,
                      child: _saving
                          ? const CircularProgressIndicator(color: Colors.white)
                          : const Text('Save Information'),
                    ),
                  ],
                ),
              ),
            ),
    );
  }
}