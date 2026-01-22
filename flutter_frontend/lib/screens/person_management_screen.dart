import 'package:flutter/material.dart';

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

  @override
  void dispose() {
    _medNameController.dispose();
    _medDoseController.dispose();
    _medFreqController.dispose();
    _medTimeController.dispose();
    _symptomsController.dispose();
    super.dispose();
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
            const Text(
              'People and Care',
              style: TextStyle(fontSize: 22, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 6),
            const Text(
              'Track meds, schedules, and well-being in one place.',
              style: TextStyle(fontSize: 14, color: Colors.black54),
            ),
            const SizedBox(height: 16),
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
                        ..._meds.map((m) => _medRow(m)).toList(),
                      ],
                    )
                  else
                    const Text('No meds added yet.'),
                ],
              ),
            ),
            const SizedBox(height: 16),
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
        border: Border.all(color: Colors.grey.shade200),
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(med['name'] ?? '', style: const TextStyle(fontWeight: FontWeight.w700)),
                const SizedBox(height: 4),
                Text('${med['dose']?.isNotEmpty == true ? med['dose']! + ' • ' : ''}${med['freq'] ?? ''}'),
                Text('Timing: ${med['time'] ?? ''}'),
              ],
            ),
          ),
          Chip(
            label: Text('Notifications ${med['notify']}'),
            backgroundColor: Colors.grey.shade100,
          ),
        ],
      ),
    );
  }
}
