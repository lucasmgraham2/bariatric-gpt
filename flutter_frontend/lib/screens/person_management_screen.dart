import 'package:flutter/material.dart';
import '../services/profile_service.dart';
import '../services/ai_service.dart';

class PersonManagementScreen extends StatefulWidget {
  const PersonManagementScreen({super.key});

  @override
  State<PersonManagementScreen> createState() => _PersonManagementScreenState();
}

class _PersonManagementScreenState extends State<PersonManagementScreen> {
  final _medNameController = TextEditingController();
  final _medDoseController = TextEditingController();
  final _medFreqController = TextEditingController();
  final _medTimeController = TextEditingController();
  bool _medNotify = true;

  final _symptomsController = TextEditingController();
  final List<Map<String, String>> _meds = [];

  // Food preferences controllers
  final TextEditingController _allergiesController = TextEditingController();
  final TextEditingController _dietTypeController = TextEditingController();
  final TextEditingController _dislikedController = TextEditingController();
  
  // Biometric data for protein calculation
  final TextEditingController _weightController = TextEditingController();
  final TextEditingController _dobController = TextEditingController();
  String? _selectedActivityLevel;
  String _weightUnit = 'kg'; // 'kg' or 'lbs'
  final List<String> _activityLevels = [
    'Sedentary (little or no exercise)',
    'Lightly active (light exercise/sports 1-3 days/week)',
    'Moderately active (moderate exercise/sports 3-5 days/week)',
    'Very active (hard exercise/sports 6-7 days a week)',
    'Extra active (very hard exercise & physical job)'
  ];
  
  final ProfileService _profileService = ProfileService();
  final AiService _aiService = AiService();
  bool _loadingPreferences = false;
  bool _savingPreferences = false;
  Map<String, dynamic> _profile = {};

  @override
  void initState() {
    super.initState();
    _loadFoodPreferences();
  }

  @override
  void dispose() {
    _medNameController.dispose();
    _medDoseController.dispose();
    _medFreqController.dispose();
    _medTimeController.dispose();
    _symptomsController.dispose();
    _allergiesController.dispose();
    _dietTypeController.dispose();
    _dislikedController.dispose();
    _weightController.dispose();
    _dobController.dispose();
    super.dispose();
  }

  Future<void> _loadFoodPreferences() async {
    setState(() {
      _loadingPreferences = true;
    });

    final result = await _profileService.fetchProfile();

    if (result['success'] == true) {
      _profile = Map<String, dynamic>.from(result['profile'] ?? {});
      
      _dislikedController.text =
          ((_profile['disliked_foods'] ?? []) as List).join(', ');
      _allergiesController.text =
          ((_profile['allergies'] ?? []) as List).join(', ');
      _dietTypeController.text = (_profile['diet_type'] ?? '') as String;
      
      // Load biometric data
      _weightController.text = (_profile['weight'] ?? '').toString();
      _dobController.text = (_profile['date_of_birth'] ?? '') as String;
      _selectedActivityLevel = _profile['activity_level'] as String?;
      _weightUnit = (_profile['weight_unit'] ?? 'kg') as String;
      if (_selectedActivityLevel != null &&
          !_activityLevels.contains(_selectedActivityLevel)) {
        _selectedActivityLevel = null;
      }
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(result['error'] ?? 'Failed to load preferences')));
      }
    }

    setState(() {
      _loadingPreferences = false;
    });
  }

  Future<void> _saveFoodPreferences() async {
    setState(() {
      _savingPreferences = true;
    });

    final profileToSave = Map<String, dynamic>.from(_profile);

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
    
    // Save biometric data
    profileToSave['weight'] = double.tryParse(_weightController.text.trim());
    profileToSave['weight_unit'] = _weightUnit;
    profileToSave['date_of_birth'] = _dobController.text.trim();
    profileToSave['activity_level'] = _selectedActivityLevel;

    final result = await _profileService.updateProfile(profileToSave);

    if (result['success'] == true) {
      _profile = profileToSave;
      
      // Update AI Context
      try {
        final aiMessage = "Update patient dietary preferences:\n"
            "Disliked Foods: ${_dislikedController.text}\n"
            "Allergies: ${_allergiesController.text}\n"
            "Diet Type: ${_dietTypeController.text}";

        await _aiService.sendMessage(message: aiMessage);
        
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text('Profile saved and AI updated')));
        }
      } catch (e) {
        if (mounted) {
           ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text('Profile saved (AI update failed)')));
        }
      }
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(result['error'] ?? 'Failed to save profile')));
      }
    }

    setState(() {
      _savingPreferences = false;
    });
  }

  void _addMedication() {
    final name = _medNameController.text.trim();
    final dose = _medDoseController.text.trim();
    final freq = _medFreqController.text.trim();
    final time = _medTimeController.text.trim();
    if (name.isEmpty || freq.isEmpty || time.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Add a name, frequency, and timing.')),
      );
      return;
    }
    setState(() {
      _meds.add({
        'name': name,
        'dose': dose,
        'freq': freq,
        'time': time,
        'notify': _medNotify ? 'On' : 'Off',
      });
      _medNameController.clear();
      _medDoseController.clear();
      _medFreqController.clear();
      _medTimeController.clear();
      _medNotify = true;
    });
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Medication saved locally. Connect backend to persist.')),
    );
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: ListView(
          children: [
            // Info note about AI integration
            Container(
              padding: const EdgeInsets.all(16),
              margin: const EdgeInsets.only(bottom: 16),
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.primary.withOpacity(0.1),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(
                  color: Theme.of(context).colorScheme.primary.withOpacity(0.3),
                  width: 1,
                ),
              ),
              child: Row(
                children: [
                  Icon(
                    Icons.info_outline,
                    color: Theme.of(context).colorScheme.primary,
                    size: 24,
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      'This information will be used by the AI to provide you with accurate, personalized help and advice.',
                      style: TextStyle(
                        fontSize: 14,
                        color: Theme.of(context).textTheme.bodyLarge?.color,
                        height: 1.4,
                      ),
                    ),
                  ),
                ],
              ),
            ),
            
            // 1. Profile for Protein Goals (Most Important)
            _sectionCard(
              title: 'Profile for Protein Goals',
              child: _loadingPreferences
                  ? const Center(child: CircularProgressIndicator())
                  : Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Enter your info for accurate protein calculations',
                          style: TextStyle(fontSize: 14, color: Theme.of(context).textTheme.bodyMedium?.color?.withOpacity(0.7)),
                        ),
                        const SizedBox(height: 12),
                        Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Expanded(
                              flex: 3,
                              child: TextField(
                                controller: _weightController,
                                decoration: InputDecoration(
                                  labelText: 'Weight ($_weightUnit)',
                                  hintText: _weightUnit == 'kg' ? 'e.g., 75' : 'e.g., 165',
                                  prefixIcon: const Icon(Icons.monitor_weight),
                                ),
                                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                              ),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              flex: 2,
                              child: SegmentedButton<String>(
                                segments: const [
                                  ButtonSegment(value: 'kg', label: Text('kg')),
                                  ButtonSegment(value: 'lbs', label: Text('lbs')),
                                ],
                                selected: {_weightUnit},
                                onSelectionChanged: (Set<String> newSelection) {
                                  setState(() {
                                    _weightUnit = newSelection.first;
                                  });
                                },
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 12),
                        TextField(
                          controller: _dobController,
                          readOnly: true,
                          decoration: const InputDecoration(
                            labelText: 'Date of Birth',
                            hintText: 'Tap to pick date',
                            prefixIcon: Icon(Icons.cake),
                          ),
                          onTap: () async {
                            final picked = await showDatePicker(
                              context: context,
                              initialDate: DateTime.tryParse(_dobController.text) ?? DateTime(1990),
                              firstDate: DateTime(1920),
                              lastDate: DateTime.now(),
                            );
                            if (picked != null) {
                              setState(() {
                                _dobController.text = picked.toIso8601String().split('T').first;
                              });
                            }
                          },
                        ),
                        const SizedBox(height: 12),
                        DropdownButtonFormField<String>(
                          value: _selectedActivityLevel,
                          decoration: const InputDecoration(
                            labelText: 'Activity Level',
                            prefixIcon: Icon(Icons.directions_run),
                          ),
                          hint: const Text('Select your activity level'),
                          isExpanded: true,
                          items: _activityLevels.map((String level) {
                            return DropdownMenuItem<String>(
                              value: level,
                              child: Text(level, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 13)),
                            );
                          }).toList(),
                          onChanged: (newValue) {
                            setState(() {
                              _selectedActivityLevel = newValue;
                            });
                          },
                        ),
                        const SizedBox(height: 16),
                        Align(
                          alignment: Alignment.centerRight,
                          child: ElevatedButton.icon(
                            onPressed: _savingPreferences ? null : _saveFoodPreferences,
                            icon: _savingPreferences
                                ? const SizedBox(
                                    width: 16,
                                    height: 16,
                                    child: CircularProgressIndicator(
                                      strokeWidth: 2,
                                      color: Colors.white,
                                    ),
                                  )
                                : const Icon(Icons.save_outlined),
                            label: const Text('Save'),
                          ),
                        ),
                      ],
                    ),
            ),
            const SizedBox(height: 16),
            
            // 2. Food Preferences
            _sectionCard(
              title: 'Food Preferences',
              child: _loadingPreferences
                  ? const Center(child: CircularProgressIndicator())
                  : Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        TextField(
                          controller: _dislikedController,
                          decoration: const InputDecoration(
                            labelText: 'Foods you dislike',
                            hintText: 'Comma-separated, e.g., broccoli, liver',
                          ),
                        ),
                        const SizedBox(height: 12),
                        TextField(
                          controller: _allergiesController,
                          decoration: const InputDecoration(
                            labelText: 'Allergies / Intolerances',
                            hintText: 'Comma-separated, e.g., nuts, dairy',
                          ),
                        ),
                        const SizedBox(height: 12),
                        TextField(
                          controller: _dietTypeController,
                          decoration: const InputDecoration(
                            labelText: 'Diet Type',
                            hintText: 'e.g., vegetarian, omnivore',
                          ),
                        ),
                        const SizedBox(height: 16),
                        Align(
                          alignment: Alignment.centerRight,
                          child: ElevatedButton.icon(
                            onPressed: _savingPreferences ? null : _saveFoodPreferences,
                            icon: _savingPreferences
                                ? const SizedBox(
                                    width: 16,
                                    height: 16,
                                    child: CircularProgressIndicator(
                                      strokeWidth: 2,
                                      color: Colors.white,
                                    ),
                                  )
                                : const Icon(Icons.save_outlined),
                            label: const Text('Save'),
                          ),
                        ),
                      ],
                    ),
            ),
            const SizedBox(height: 16),
            
            // 3. Daily Meds / Supplements
            _sectionCard(
              title: 'Daily Meds / Supplements',
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: _medNameController,
                          decoration: const InputDecoration(labelText: 'Name (e.g., Vitamin D)'),
                        ),
                      ),
                      const SizedBox(width: 12),
                      SizedBox(
                        width: 140,
                        child: TextField(
                          controller: _medDoseController,
                          decoration: const InputDecoration(labelText: 'Dose'),
                        ),
                      ),
                    ],
                  ),
                  Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: _medFreqController,
                          decoration: const InputDecoration(labelText: 'Frequency (e.g., 2x/day)'),
                        ),
                      ),
                      const SizedBox(width: 12),
                      SizedBox(
                        width: 140,
                        child: TextField(
                          controller: _medTimeController,
                          decoration: const InputDecoration(labelText: 'Timing (e.g., morning)'),
                        ),
                      ),
                    ],
                  ),
                  SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    title: const Text('Enable reminders/notifications'),
                    value: _medNotify,
                    onChanged: (v) => setState(() => _medNotify = v),
                  ),
                  Align(
                    alignment: Alignment.centerRight,
                    child: ElevatedButton.icon(
                      onPressed: _addMedication,
                      icon: const Icon(Icons.save_outlined),
                      label: const Text('Save'),
                    ),
                  ),
                  const SizedBox(height: 12),
                  if (_meds.isNotEmpty)
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('Saved items', style: TextStyle(fontWeight: FontWeight.w600)),
                        const SizedBox(height: 8),
                        ..._meds.map((m) => _medRow(m)),
                      ],
                    )
                  else
                    const Text('No meds added yet.'),
                ],
              ),
            ),
            const SizedBox(height: 16),
            
            // 4. Symptoms and Notes (Least urgent)
            _sectionCard(
              title: 'Symptoms and Notes',
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('How are you feeling today?', style: TextStyle(fontWeight: FontWeight.w600)),
                  const SizedBox(height: 8),
                  TextField(
                    controller: _symptomsController,
                    maxLines: 5,
                    decoration: const InputDecoration(
                      hintText: 'Log symptoms, mood, pain levels, hydration, or other notes.',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 8),
                  Align(
                    alignment: Alignment.centerRight,
                    child: ElevatedButton.icon(
                      onPressed: () {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(content: Text('Symptoms saved locally. Connect backend to persist.')),
                        );
                      },
                      icon: const Icon(Icons.check_circle_outline),
                      label: const Text('Save entry'),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _sectionCard({required String title, required Widget child}) {
    return Card(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      elevation: 1,
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
            const SizedBox(height: 12),
            child,
          ],
        ),
      ),
    );
  }

  Widget _medRow(Map<String, String> med) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Theme.of(context).brightness == Brightness.dark ? Colors.grey.shade700 : Colors.grey.shade200),
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(med['name'] ?? '', style: const TextStyle(fontWeight: FontWeight.w700)),
                const SizedBox(height: 4),
                Text('${med['dose']?.isNotEmpty == true ? '${med['dose']!} • ' : ''}${med['freq'] ?? ''}'),
                Text('Timing: ${med['time'] ?? ''}'),
              ],
            ),
          ),
          Chip(
            label: Text('Notifications ${med['notify']}'),
            backgroundColor: Theme.of(context).brightness == Brightness.dark ? Colors.grey.shade900 : Colors.grey.shade100,
          ),
        ],
      ),
    );
  }
}
