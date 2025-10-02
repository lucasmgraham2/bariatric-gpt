import 'package:flutter/material.dart';
import 'package:bariatric_gpt/services/auth_service.dart';
import 'package:bariatric_gpt/screens/login_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({Key? key}) : super(key: key);

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final _authService = AuthService();
  Map<String, dynamic>? _userProfile;
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadUserProfile();
  }

  Future<void> _loadUserProfile() async {
    final result = await _authService.getCurrentUser();
    setState(() {
      _isLoading = false;
      if (result['success']) {
        _userProfile = result['data'];
      }
    });
  }

  Future<void> _logout() async {
    await _authService.logout();
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(builder: (context) => const LoginScreen()),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Bariatric GPT'),
        centerTitle: true,
        automaticallyImplyLeading: false, // Remove back button
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: _logout,
            tooltip: 'Logout',
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _userProfile == null
              ? const Center(
                  child: Text(
                    'Failed to load user profile',
                    style: TextStyle(fontSize: 16),
                  ),
                )
              : Padding(
                  padding: const EdgeInsets.all(16.0),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Card(
                        child: Padding(
                          padding: const EdgeInsets.all(16.0),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Text(
                                'Welcome back!',
                                style: TextStyle(
                                  fontSize: 24,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                              const SizedBox(height: 16),
                              _buildInfoRow('Username', _userProfile!['username']),
                              _buildInfoRow('Email', _userProfile!['email']),
                            ],
                          ),
                        ),
                      ),
                      const SizedBox(height: 24),
                      const Text(
                        'Features',
                        style: TextStyle(
                          fontSize: 20,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 16),
                      Expanded(
                        child: GridView.count(
                          crossAxisCount: 2,
                          crossAxisSpacing: 16,
                          mainAxisSpacing: 16,
                          children: [
                            _buildFeatureCard(
                              'Patient Management',
                              Icons.people,
                              'Manage patient records securely',
                              () {
                                ScaffoldMessenger.of(context).showSnackBar(
                                  const SnackBar(content: Text('Feature coming soon!')),
                                );
                              },
                            ),
                            _buildFeatureCard(
                              'AI Assistant',
                              Icons.psychology,
                              'Get AI-powered insights',
                              () {
                                ScaffoldMessenger.of(context).showSnackBar(
                                  const SnackBar(content: Text('Feature coming soon!')),
                                );
                              },
                            ),
                            _buildFeatureCard(
                              'Reports',
                              Icons.analytics,
                              'View detailed reports',
                              () {
                                ScaffoldMessenger.of(context).showSnackBar(
                                  const SnackBar(content: Text('Feature coming soon!')),
                                );
                              },
                            ),
                            _buildFeatureCard(
                              'Settings',
                              Icons.settings,
                              'Configure your preferences',
                              () {
                                ScaffoldMessenger.of(context).showSnackBar(
                                  const SnackBar(content: Text('Feature coming soon!')),
                                );
                              },
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
    );
  }

  Widget _buildInfoRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8.0),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 100,
            child: Text(
              '$label:',
              style: const TextStyle(fontWeight: FontWeight.w500),
            ),
          ),
          Expanded(
            child: Text(value),
          ),
        ],
      ),
    );
  }

  Widget _buildFeatureCard(String title, IconData icon, String description, VoidCallback onTap) {
    return Card(
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(8),
        child: Padding(
          padding: const EdgeInsets.all(16.0),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                icon,
                size: 48,
                color: Theme.of(context).primaryColor,
              ),
              const SizedBox(height: 12),
              Text(
                title,
                style: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 8),
              Text(
                description,
                style: TextStyle(
                  fontSize: 12,
                  color: Colors.grey[600],
                ),
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      ),
    );
  }
}