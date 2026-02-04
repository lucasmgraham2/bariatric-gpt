import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../services/profile_service.dart'; // Make sure this path is correct
import '../services/ai_service.dart';

class PatientManagementScreen extends StatefulWidget {
  const PatientManagementScreen({super.key});

  @override
  _PatientManagementScreenState createState() =>
      _PatientManagementScreenState();
}

class _PatientManagementScreenState extends State<PatientManagementScreen> {
  final _formKey = GlobalKey<FormState>();
  final ProfileService _profileService = ProfileService();

  bool _loading = true;
  bool _saving = false;
  Map<String, dynamic> _profile = {};

  // --- New Biometric Controllers ---
  final TextEditingController _heightController = TextEditingController();
  final TextEditingController _weightController = TextEditingController();
  final TextEditingController _dobController = TextEditingController();
  String? _selectedActivityLevel;
  final List<String> _activityLevels = [
    'Sedentary (little or no exercise)',
    'Lightly active (light exercise/sports 1-3 days/week)',
    'Moderately active (moderate exercise/sports 3-5 days/week)',
    'Very active (hard exercise/sports 6-7 days a week)',
    'Extra active (very hard exercise & physical job)'
  ];

  // --- New Medical Controllers ---
  final TextEditingController _conditionsController = TextEditingController();

  final TextEditingController _allergiesController = TextEditingController();
  final TextEditingController _dietTypeController = TextEditingController();
  final TextEditingController _dislikedController = TextEditingController();
  final TextEditingController _surgeryDateController = TextEditingController();
  List<String> _medications = [];

  @override
  void initState() {
    super.initState();
    _loadProfile();
  }

  @override
  void dispose() {
    _heightController.dispose();
    _weightController.dispose();
    _dobController.dispose();
    _conditionsController.dispose();
    _surgeryDateController.dispose();
    _allergiesController.dispose();
    _dietTypeController.dispose();
    _dislikedController.dispose();
    super.dispose();
  }

  Future<void> _loadProfile() async {
    setState(() {
      _loading = true;
    });

    final result = await _profileService.fetchProfile();

    if (result['success'] == true) {
      _profile = Map<String, dynamic>.from(result['profile'] ?? {});

      // Load Biometrics
      _heightController.text = (_profile['height'] ?? '').toString();
      _weightController.text = (_profile['weight'] ?? '').toString();
      _dobController.text = (_profile['date_of_birth'] ?? '') as String;
      _selectedActivityLevel = _profile['activity_level'] as String?;
      // Ensure loaded value is valid, otherwise set to null
      if (_selectedActivityLevel != null &&
          !_activityLevels.contains(_selectedActivityLevel)) {
        _selectedActivityLevel = null;
      }

      // Load Medical
      _conditionsController.text =
          ((_profile['medical_conditions'] ?? []) as List).join(', ');

      _dislikedController.text =
          ((_profile['disliked_foods'] ?? []) as List).join(', ');
      _allergiesController.text =
          ((_profile['allergies'] ?? []) as List).join(', ');
      _dietTypeController.text = (_profile['diet_type'] ?? '') as String;
      final sd = _profile['surgery_date'];
      _surgeryDateController.text = sd != null ? sd.toString() : '';

      // Load Medications
      _medications = List<String>.from(_profile['medications'] ?? []);

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

  final AiService _aiService = AiService();

  Future<void> _saveProfile() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() {
      _saving = true;
    });

    // IMPORTANT: Create a copy to avoid deleting other profile data (like username)
    final profileToSave = Map<String, dynamic>.from(_profile);

    // --- Save Biometrics ---
    // Save as numbers (or null if empty)
    profileToSave['height'] = double.tryParse(_heightController.text.trim());
    profileToSave['weight'] = double.tryParse(_weightController.text.trim());
    profileToSave['date_of_birth'] = _dobController.text.trim();
    profileToSave['activity_level'] = _selectedActivityLevel;

    // --- Save Medical Info ---
     profileToSave['medical_conditions'] = _conditionsController.text
        .split(',')
        .map((s) => s.trim())
        .where((s) => s.isNotEmpty)
        .toList();

    // Update only the fields relevant to this screen
    profileToSave['disliked_foods'] = _dislikedController.text
        .split(',')
        .map((s) => s.trim())
        .where((s) => s.isNotEmpty)
        .toList();
    profileToSave['allergies'] = _allergiesController.text
        .split(',')
        .map((s) => s.trim())
        .where((s) => s.isNotEmpty)
        .toList();
    profileToSave['diet_type'] = _dietTypeController.text.trim();
    profileToSave['surgery_date'] = _surgeryDateController.text.trim();
    profileToSave['medications'] = _medications;

    final result = await _profileService.updateProfile(profileToSave);

    if (result['success'] == true) {
      _profile = profileToSave;
      
      // --- Update AI Context ---
      try {
        final aiMessage = "Update patient profile:\n"
            "Height: ${_heightController.text} cm\n"
            "Weight: ${_weightController.text} kg\n"
            "DOB: ${_dobController.text}\n"
            "Activity Level: $_selectedActivityLevel\n"
            "Medical Conditions: ${_conditionsController.text}\n"
            "Surgery Date: ${_surgeryDateController.text}\n"
            "Disliked Foods: ${_dislikedController.text}\n"
            "Allergies: ${_allergiesController.text}\n"
            "Meds: ${_medications.join(', ')}\n"
            "Diet Type: ${_dietTypeController.text}";

        await _aiService.sendMessage(message: aiMessage);
        
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text('Preferences saved and AI updated')));
        }
      } catch (e) {
        // Don't block UI if AI update fails, but maybe log it
        if (mounted) {
           ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text('Preferences saved (AI update failed)')));
        }
      }
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(result['error'] ?? 'Failed to save profile')));
      }
    }

    setState(() {
      _saving = false;
    });
  }

  // Helper for section headings
  Widget _buildSectionHeader(String title) {
    return Padding(
      padding: const EdgeInsets.only(top: 24.0, bottom: 8.0),
      child: Text(
        title,
        style: Theme.of(context).textTheme.titleLarge,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Patient Management'),
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
          : Form(
              key: _formKey,
              child: ListView(
                padding: const EdgeInsets.all(16.0),
                children: [
                  // --- BIOMETRICS SECTION ---
                  _buildSectionHeader('Biometrics'),
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(
                        child: TextFormField(
                          controller: _heightController,
                          decoration: const InputDecoration(labelText: 'Height (cm)'),
                          keyboardType: const TextInputType.numberWithOptions(decimal: true),
                          inputFormatters: [
                            FilteringTextInputFormatter.allow(RegExp(r'^\d+\.?\d{0,2}')),
                          ],
                          textInputAction: TextInputAction.next,
                        ),
                      ),
                      const SizedBox(width: 16),
                      Expanded(
                        child: TextFormField(
                          controller: _weightController,
                          decoration: const InputDecoration(labelText: 'Weight (kg)'),
                          keyboardType: const TextInputType.numberWithOptions(decimal: true),
                           inputFormatters: [
                            FilteringTextInputFormatter.allow(RegExp(r'^\d+\.?\d{0,2}')),
                          ],
                          textInputAction: TextInputAction.next,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  TextFormField(
                    controller: _dobController,
                    readOnly: true,
                    decoration:
                        const InputDecoration(labelText: 'Date of Birth', hintText: 'Tap to pick date'),
                    onTap: () async {
                      final picked = await showDatePicker(
                        context: context,
                        initialDate: DateTime.tryParse(_dobController.text) ?? DateTime(1990),
                        firstDate: DateTime(1920),
                        lastDate: DateTime.now(),
                      );
                      if (picked != null) {
                        _dobController.text = picked.toIso8601String().split('T').first;
                      }
                    },
                  ),
                   const SizedBox(height: 16),
                  DropdownButtonFormField<String>(
                    initialValue: _selectedActivityLevel,
                    decoration: const InputDecoration(labelText: 'Activity Level'),
                    hint: const Text('Select your activity level'),
                    isExpanded: true,
                    items: _activityLevels.map((String level) {
                      return DropdownMenuItem<String>(
                        value: level,
                        child: Text(level, overflow: TextOverflow.ellipsis),
                      );
                    }).toList(),
                    onChanged: (newValue) {
                      setState(() {
                        _selectedActivityLevel = newValue;
                      });
                    },
                  ),

                  // --- MEDICAL SECTION ---
                  _buildSectionHeader('Medical'),
                   TextFormField(
                    controller: _surgeryDateController,
                    readOnly: true,
                    decoration: const InputDecoration(labelText: 'Surgery Date', hintText: 'Tap to pick date'),
                    onTap: () async {
                      final picked = await showDatePicker(
                        context: context,
                        initialDate: DateTime.tryParse(_surgeryDateController.text) ?? DateTime.now(),
                        firstDate: DateTime(2000),
                        lastDate: DateTime(2100),
                      );
                      if (picked != null) {
                        _surgeryDateController.text =
                            picked.toIso8601String().split('T').first;
                      }
                    },
                  ),
                  const SizedBox(height: 16),
                   TextFormField(
                    controller: _conditionsController,
                    decoration: const InputDecoration(
                      labelText: 'Underlying Medical Conditions',
                      hintText: 'Comma-separated, e.g., diabetes, hypertension'
                    ),
                    textInputAction: TextInputAction.next,
                  ),
                  const SizedBox(height: 16),
                  _buildSectionHeader('Daily Medications & Supplements'),
                  ..._medications.map((med) => ListTile(
                        title: Text(med),
                        trailing: IconButton(
                          icon: const Icon(Icons.delete, color: Colors.red),
                          onPressed: () {
                            setState(() {
                              _medications.remove(med);
                            });
                          },
                        ),
                      )),
                  ElevatedButton.icon(
                    onPressed: () {
                      showDialog(
                        context: context,
                        builder: (context) {
                          String newMed = '';
                          return AlertDialog(
                            title: const Text('Add Medication/Supplement'),
                            content: TextField(
                              autofocus: true,
                              decoration: const InputDecoration(
                                  hintText: 'e.g., Multivitamin, 1/day'),
                              onChanged: (val) => newMed = val,
                            ),
                            actions: [
                              TextButton(
                                onPressed: () => Navigator.pop(context),
                                child: const Text('Cancel'),
                              ),
                              TextButton(
                                onPressed: () {
                                  if (newMed.trim().isNotEmpty) {
                                    setState(() {
                                      _medications.add(newMed.trim());
                                    });
                                  }
                                  Navigator.pop(context);
                                },
                                child: const Text('Add'),
                              ),
                            ],
                          );
                        },
                      );
                    },
                    icon: const Icon(Icons.add),
                    label: const Text('Add Medication'),
                  ),
                  
                  // --- PREFERENCES SECTION ---
                  _buildSectionHeader('Dietary Preferences'),
                  TextFormField(
                    controller: _dislikedController,
                    decoration: const InputDecoration(
                        labelText: 'Food you dislike',
                        hintText: 'Comma-separated, e.g., broccoli, liver'),
                    textInputAction: TextInputAction.next,
                  ),
                  const SizedBox(height: 16),
                  TextFormField(
                    controller: _allergiesController,
                    decoration: const InputDecoration(
                        labelText: 'Allergies / intolerances',
                        hintText: 'Comma-separated, e.g., nuts, dairy'),
                    textInputAction: TextInputAction.next,
                  ),
                  const SizedBox(height: 16),
                  TextFormField(
                    controller: _dietTypeController,
                    decoration: const InputDecoration(
                        labelText: 'Diet type',
                        hintText: 'e.g., vegetarian, omnivore'),
                    textInputAction: TextInputAction.next,
                  ),
                 
                  // --- ACTIONS ---
                  const SizedBox(height: 32),
                  ElevatedButton(
                    onPressed: _saving ? null : _saveProfile,
                    style: ElevatedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 16),
                    ),
                    child: _saving
                        ? const CircularProgressIndicator(color: Colors.white)
                        : const Text('Save All Preferences', style: TextStyle(fontSize: 16)),
                  ),
                  const SizedBox(height: 12),
                  TextButton(
                    onPressed: () async {
                      // Reset all controllers
                      _heightController.clear();
                      _weightController.clear();
                      _dobController.clear();
                      _conditionsController.clear();
                      _surgeryDateController.clear();
                      _dislikedController.clear();
                      _allergiesController.clear();
                      _dietTypeController.clear();
                      setState(() {
                         _selectedActivityLevel = null;
                      });
                      await _saveProfile();
                    },
                    child: const Text('Clear All and Save'),
                  ),
                ],
              ),
            ),
    );
  }
}