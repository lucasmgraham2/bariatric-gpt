import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../services/profile_service.dart';

class MealsScreen extends StatefulWidget {
  const MealsScreen({super.key});

  @override
  State<MealsScreen> createState() => _MealsScreenState();
}

class _MealsScreenState extends State<MealsScreen> {
  final ProfileService _profileService = ProfileService();
  final TextEditingController _foodNameController = TextEditingController();
  final TextEditingController _proteinController = TextEditingController();
  final TextEditingController _caloriesController = TextEditingController();
  
  final List<Map<String, dynamic>> _todaysMeals = [];
  bool _loading = false;
  double _totalProtein = 0;
  double _totalCalories = 0;

  @override
  void initState() {
    super.initState();
    _loadTodaysMeals();
  }

  @override
  void dispose() {
    _foodNameController.dispose();
    _proteinController.dispose();
    _caloriesController.dispose();
    super.dispose();
  }

  Future<void> _loadTodaysMeals() async {
    setState(() {
      _loading = true;
    });

    final result = await _profileService.fetchProfile();
    if (result['success'] == true) {
      final profile = Map<String, dynamic>.from(result['profile'] ?? {});
      final meals = profile['todays_meals'] as List?;
      
      if (meals != null) {
        _todaysMeals.clear();
        _todaysMeals.addAll(meals.map((m) => Map<String, dynamic>.from(m)));
        _calculateTotals();
      }
    }

    setState(() {
      _loading = false;
    });
  }

  void _calculateTotals() {
    _totalProtein = 0;
    _totalCalories = 0;
    for (var meal in _todaysMeals) {
      _totalProtein += (meal['protein'] ?? 0).toDouble();
      _totalCalories += (meal['calories'] ?? 0).toDouble();
    }
  }

  Future<void> _addMeal() async {
    final foodName = _foodNameController.text.trim();
    final protein = double.tryParse(_proteinController.text.trim()) ?? 0;
    final calories = double.tryParse(_caloriesController.text.trim()) ?? 0;

    if (foodName.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please enter a food name')),
      );
      return;
    }

    final meal = {
      'food': foodName,
      'protein': protein,
      'calories': calories,
    };

    setState(() {
      _todaysMeals.add(meal);
      _calculateTotals();
    });

    // Save to profile
    await _saveMealsToProfile();

    // Clear inputs
    _foodNameController.clear();
    _proteinController.clear();
    _caloriesController.clear();

    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Meal added successfully')),
    );
  }

  Future<void> _saveMealsToProfile() async {
    final result = await _profileService.fetchProfile();
    if (result['success'] == true) {
      final profile = Map<String, dynamic>.from(result['profile'] ?? {});
      profile['todays_meals'] = _todaysMeals;
      
      // Also update total protein for the day
      profile['protein_today'] = _totalProtein;
      
      await _profileService.updateProfile(profile);
    }
  }

  Future<void> _removeMeal(int index) async {
    setState(() {
      _todaysMeals.removeAt(index);
      _calculateTotals();
    });
    await _saveMealsToProfile();
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Meal removed')),
    );
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: RefreshIndicator(
        onRefresh: _loadTodaysMeals,
        child: Padding(
          padding: const EdgeInsets.all(16.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Summary Cards
              Row(
                children: [
                  Expanded(
                    child: _summaryCard(
                      'Protein',
                      '${_totalProtein.toStringAsFixed(1)}g',
                      Icons.fitness_center,
                      Colors.blue,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: _summaryCard(
                      'Calories',
                      '${_totalCalories.toStringAsFixed(0)}',
                      Icons.local_fire_department,
                      Colors.orange,
                    ),
                  ),
                ],
              ),
              
              const SizedBox(height: 16),
              
              // Add Meal Section
              Card(
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                elevation: 1,
                child: Padding(
                  padding: const EdgeInsets.all(16.0),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Add Meal',
                        style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
                      ),
                      const SizedBox(height: 12),
                      TextField(
                        controller: _foodNameController,
                        decoration: const InputDecoration(
                          labelText: 'Food / Meal Name',
                          hintText: 'e.g., Grilled Chicken',
                          prefixIcon: Icon(Icons.restaurant),
                        ),
                        textInputAction: TextInputAction.next,
                      ),
                      const SizedBox(height: 12),
                      Row(
                        children: [
                          Expanded(
                            child: TextField(
                              controller: _proteinController,
                              decoration: const InputDecoration(
                                labelText: 'Protein (g)',
                                hintText: '0',
                              ),
                              keyboardType: const TextInputType.numberWithOptions(decimal: true),
                              inputFormatters: [
                                FilteringTextInputFormatter.allow(RegExp(r'^\d+\.?\d{0,1}')),
                              ],
                              textInputAction: TextInputAction.next,
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: TextField(
                              controller: _caloriesController,
                              decoration: const InputDecoration(
                                labelText: 'Calories',
                                hintText: '0',
                              ),
                              keyboardType: const TextInputType.numberWithOptions(decimal: true),
                              inputFormatters: [
                                FilteringTextInputFormatter.allow(RegExp(r'^\d+\.?\d{0,1}')),
                              ],
                              textInputAction: TextInputAction.done,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 16),
                      Align(
                        alignment: Alignment.centerRight,
                        child: ElevatedButton.icon(
                          onPressed: _addMeal,
                          icon: const Icon(Icons.add),
                          label: const Text('Add Meal'),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              
              const SizedBox(height: 16),
              
              // Today's Meals List
              const Text(
                'Today\'s Meals',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 8),
              
              Expanded(
                child: _loading
                    ? const Center(child: CircularProgressIndicator())
                    : _todaysMeals.isEmpty
                        ? Center(
                            child: Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                Icon(Icons.restaurant_menu, size: 64, color: Theme.of(context).brightness == Brightness.dark ? Colors.grey.shade700 : Colors.grey.shade300),
                                const SizedBox(height: 16),
                                Text(
                                  'No meals logged yet',
                                  style: TextStyle(fontSize: 16, color: Colors.grey.shade600),
                                ),
                                const SizedBox(height: 8),
                                Text(
                                  'Add your first meal above',
                                  style: TextStyle(fontSize: 14, color: Colors.grey.shade500),
                                ),
                              ],
                            ),
                          )
                        : ListView.builder(
                            itemCount: _todaysMeals.length,
                            itemBuilder: (context, index) {
                              final meal = _todaysMeals[index];
                              return _mealCard(meal, index);
                            },
                          ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _summaryCard(String label, String value, IconData icon, Color color) {
    return Card(
      elevation: 1,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          children: [
            Icon(icon, color: color, size: 28),
            const SizedBox(height: 8),
            Text(
              value,
              style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 4),
            Text(
              label,
              style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
            ),
          ],
        ),
      ),
    );
  }

  Widget _mealCard(Map<String, dynamic> meal, int index) {
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      elevation: 0.5,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: Colors.grey.shade200),
      ),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: Theme.of(context).colorScheme.secondary.withOpacity(0.1),
          child: Icon(Icons.restaurant, color: Theme.of(context).colorScheme.secondary),
        ),
        title: Text(
          meal['food'] ?? '',
          style: const TextStyle(fontWeight: FontWeight.w600),
        ),
        subtitle: Text(
          'Protein: ${meal['protein']?.toStringAsFixed(1) ?? 0}g  •  Calories: ${meal['calories']?.toStringAsFixed(0) ?? 0}',
          style: const TextStyle(fontSize: 12),
        ),
        trailing: IconButton(
          icon: Icon(Icons.delete_outline, color: Theme.of(context).brightness == Brightness.dark ? Colors.redAccent : Colors.red),
          onPressed: () => _removeMeal(index),
        ),
      ),
    );
  }
}
