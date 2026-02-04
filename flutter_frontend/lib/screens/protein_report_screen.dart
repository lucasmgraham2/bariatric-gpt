import 'package:flutter/material.dart';
import '../services/profile_service.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:intl/intl.dart';

class ProteinReportScreen extends StatefulWidget {
  const ProteinReportScreen({super.key});

  @override
  State<ProteinReportScreen> createState() => _ProteinReportScreenState();
}

class _ProteinReportScreenState extends State<ProteinReportScreen> {
  final ProfileService _profileService = ProfileService();
  bool _loading = true;
  double _proteinGoal = 0;
  double _proteinConsumed = 0;
  String _errorMessage = '';
  Map<String, double> _proteinHistory = {}; // date -> protein amount

  @override
  void initState() {
    super.initState();
    _loadProteinData();
  }

  Future<void> _loadProteinData() async {
    setState(() {
      _loading = true;
      _errorMessage = '';
    });

    final result = await _profileService.fetchProfile();

    if (result['success'] == true) {
      final profile = Map<String, dynamic>.from(result['profile'] ?? {});
      
      // Check if it's a new day
      final today = DateFormat('yyyy-MM-dd').format(DateTime.now());
      final lastMealDate = profile['last_meal_date'] as String?;
      
      if (lastMealDate != null && lastMealDate != today) {
        // New day detected - save yesterday's protein to history and clear meals
        await _handleNewDay(profile, lastMealDate);
        // Reload profile after handling new day
        final newResult = await _profileService.fetchProfile();
        if (newResult['success'] == true) {
          final newProfile = Map<String, dynamic>.from(newResult['profile'] ?? {});
          _proteinConsumed = (newProfile['protein_today'] ?? 0).toDouble();
          _proteinGoal = _calculateProteinGoal(newProfile);
          
          final historyData = newProfile['protein_history'] as Map<String, dynamic>?;
          if (historyData != null) {
            _proteinHistory = historyData.map((key, value) => 
              MapEntry(key, (value as num).toDouble())
            );
          } else {
            _proteinHistory = {};
          }
          _proteinHistory[today] = _proteinConsumed;
        }
      } else {
        // Same day - just load data
        _proteinConsumed = (profile['protein_today'] ?? 0).toDouble();
        _proteinGoal = _calculateProteinGoal(profile);
        
        // Load protein history
        final historyData = profile['protein_history'] as Map<String, dynamic>?;
        if (historyData != null) {
          _proteinHistory = historyData.map((key, value) => 
            MapEntry(key, (value as num).toDouble())
          );
        } else {
          _proteinHistory = {};
        }
        
        // Add today's data if not already there
        _proteinHistory[today] = _proteinConsumed;
      }
    } else {
      _errorMessage = result['error'] ?? 'Failed to load profile';
    }

    setState(() {
      _loading = false;
    });
  }
  
  Future<void> _handleNewDay(Map<String, dynamic> profile, String previousDate) async {
    // Get yesterday's total protein
    final yesterdayProtein = (profile['protein_today'] ?? 0).toDouble();
    
    // Save to protein history
    Map<String, dynamic> proteinHistory = {};
    if (profile['protein_history'] != null) {
      proteinHistory = Map<String, dynamic>.from(profile['protein_history']);
    }
    proteinHistory[previousDate] = yesterdayProtein;
    
    // Update profile with cleared data for new day
    profile['protein_history'] = proteinHistory;
    profile['todays_meals'] = [];
    profile['protein_today'] = 0;
    profile['last_meal_date'] = DateFormat('yyyy-MM-dd').format(DateTime.now());
    
    await _profileService.updateProfile(profile);
  }

  double _calculateProteinGoal(Map<String, dynamic> profile) {
    // Get weight in kg
    final weight = profile['weight'];
    final weightUnit = profile['weight_unit'] as String? ?? 'kg';
    
    if (weight == null) {
      return 80.0; // Default goal if no weight set
    }

    double weightKg = 0;
    if (weight is int) {
      weightKg = weight.toDouble();
    } else if (weight is double) {
      weightKg = weight;
    } else if (weight is String) {
      weightKg = double.tryParse(weight) ?? 0;
    }
    
    // Convert lbs to kg if necessary
    if (weightUnit == 'lbs' && weightKg > 0) {
      weightKg = weightKg * 0.453592; // 1 lb = 0.453592 kg
    }

    if (weightKg <= 0) {
      return 80.0; // Default goal
    }

    // Get age from date of birth
    final dobString = profile['date_of_birth'] as String?;
    int age = 30; // Default age
    if (dobString != null && dobString.isNotEmpty) {
      final dob = DateTime.tryParse(dobString);
      if (dob != null) {
        age = DateTime.now().year - dob.year;
      }
    }

    // Base calculation: 1.2g per kg for bariatric patients (higher than normal 0.8g)
    // Bariatric patients need more protein to maintain muscle mass
    double proteinPerKg = 1.2;

    // Adjust for age (older adults need slightly more)
    if (age > 65) {
      proteinPerKg = 1.4;
    } else if (age > 50) {
      proteinPerKg = 1.3;
    }

    // Adjust for activity level
    final activityLevel = profile['activity_level'] as String?;
    if (activityLevel != null) {
      if (activityLevel.contains('Very active') || activityLevel.contains('Extra active')) {
        proteinPerKg += 0.3;
      } else if (activityLevel.contains('Moderately active')) {
        proteinPerKg += 0.2;
      } else if (activityLevel.contains('Lightly active')) {
        proteinPerKg += 0.1;
      }
    }

    return weightKg * proteinPerKg;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Protein Tracker'),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _errorMessage.isNotEmpty
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(16.0),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.error_outline, size: 64, color: Theme.of(context).brightness == Brightness.dark ? Colors.redAccent : Colors.red),
                        const SizedBox(height: 16),
                        Text(
                          _errorMessage,
                          textAlign: TextAlign.center,
                          style: const TextStyle(fontSize: 16),
                        ),
                        const SizedBox(height: 16),
                        ElevatedButton(
                          onPressed: _loadProteinData,
                          child: const Text('Retry'),
                        ),
                      ],
                    ),
                  ),
                )
              : RefreshIndicator(
                  onRefresh: _loadProteinData,
                  child: ListView(
                    padding: const EdgeInsets.all(16.0),
                    children: [
                      const Text(
                        'Daily Protein Goal',
                        style: TextStyle(fontSize: 22, fontWeight: FontWeight.w700),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'Track your protein intake to meet your personalized daily goal.',
                        style: TextStyle(fontSize: 14, color: Theme.of(context).textTheme.bodyMedium?.color?.withOpacity(0.7)),
                      ),
                      const SizedBox(height: 24),
                      _buildProteinMeter(),
                      const SizedBox(height: 32),
                      _buildStatsCards(),
                      const SizedBox(height: 32),
                      _buildProteinChart(),
                      const SizedBox(height: 24),
                      _buildTipsCard(),
                    ],
                  ),
                ),
    );
  }

  Widget _buildProteinMeter() {
    final percentage = _proteinGoal > 0 ? (_proteinConsumed / _proteinGoal).clamp(0.0, 1.0) : 0.0;
    final isGoalMet = _proteinConsumed >= _proteinGoal;

    return Card(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          children: [
            // Circular meter
            SizedBox(
              width: 200,
              height: 200,
              child: Stack(
                alignment: Alignment.center,
                children: [
                  SizedBox(
                    width: 200,
                    height: 200,
                    child: CircularProgressIndicator(
                      value: percentage,
                      strokeWidth: 16,
                      backgroundColor: Theme.of(context).brightness == Brightness.dark ? Colors.grey.shade800 : Colors.grey.shade200,
                      valueColor: AlwaysStoppedAnimation<Color>(
                        isGoalMet ? Colors.green : Theme.of(context).colorScheme.secondary,
                      ),
                    ),
                  ),
                  Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(
                        '${_proteinConsumed.toStringAsFixed(0)}g',
                        style: const TextStyle(
                          fontSize: 48,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      Text(
                        'of ${_proteinGoal.toStringAsFixed(0)}g',
                        style: TextStyle(
                          fontSize: 16,
                          color: Colors.grey.shade600,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        '${(percentage * 100).toStringAsFixed(0)}%',
                        style: TextStyle(
                          fontSize: 20,
                          fontWeight: FontWeight.w600,
                          color: isGoalMet ? Colors.green : Theme.of(context).colorScheme.secondary,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 24),
            if (isGoalMet)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                decoration: BoxDecoration(
                  color: Colors.green.shade50,
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: Colors.green.shade200),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.check_circle, color: Colors.green.shade700, size: 20),
                    const SizedBox(width: 8),
                    Text(
                      'Goal achieved! 🎉',
                      style: TextStyle(
                        color: Colors.green.shade700,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
              )
            else
              Text(
                'Keep going! ${(_proteinGoal - _proteinConsumed).toStringAsFixed(0)}g to go',
                style: TextStyle(
                  fontSize: 16,
                  color: Theme.of(context).textTheme.bodyMedium?.color?.withOpacity(0.8),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildStatsCards() {
    return Row(
      children: [
        Expanded(
          child: _buildStatCard(
            'Daily Goal',
            '${_proteinGoal.toStringAsFixed(0)}g',
            Icons.flag,
            Colors.blue,
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _buildStatCard(
            'Consumed',
            '${_proteinConsumed.toStringAsFixed(0)}g',
            Icons.restaurant,
            Colors.orange,
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _buildStatCard(
            'Remaining',
            '${(_proteinGoal - _proteinConsumed).clamp(0, double.infinity).toStringAsFixed(0)}g',
            Icons.trending_up,
            Colors.purple,
          ),
        ),
      ],
    );
  }

  Widget _buildStatCard(String label, String value, IconData icon, Color color) {
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
              style: const TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              label,
              style: TextStyle(
                fontSize: 12,
                color: Theme.of(context).textTheme.bodyMedium?.color?.withOpacity(0.7),
              ),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTipsCard() {
    return Card(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      elevation: 1,
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.lightbulb_outline, color: Theme.of(context).colorScheme.secondary),
                const SizedBox(width: 8),
                const Text(
                  'Protein Tips',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
                ),
              ],
            ),
            const SizedBox(height: 12),
            _buildTipRow('Your goal is calculated based on your weight, age, and activity level'),
            _buildTipRow('Bariatric patients need higher protein to maintain muscle mass'),
            _buildTipRow('Update your protein intake in the People tab'),
            _buildTipRow('Set your height, weight, and age in Patient Management for accurate calculations'),
          ],
        ),
      ),
    );
  }

  Widget _buildTipRow(String text) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8.0),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('• ', style: TextStyle(fontSize: 16)),
          Expanded(
            child: Text(
              text,
              style: const TextStyle(fontSize: 14, height: 1.4),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildProteinChart() {
    if (_proteinHistory.isEmpty) {
      return Card(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        elevation: 1,
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            children: [
              Icon(Icons.timeline, size: 48, color: Theme.of(context).brightness == Brightness.dark ? Colors.grey.shade600 : Colors.grey.shade400),
              const SizedBox(height: 12),
              Text(
                'No history yet',
                style: TextStyle(fontSize: 16, color: Theme.of(context).textTheme.bodyMedium?.color?.withOpacity(0.7)),
              ),
              const SizedBox(height: 8),
              Text(
                'Start tracking your protein to see your progress over time',
                style: TextStyle(fontSize: 14, color: Theme.of(context).textTheme.bodyMedium?.color?.withOpacity(0.6)),
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      );
    }

    // Sort dates and get last 7 days or all available data
    final sortedDates = _proteinHistory.keys.toList()..sort();
    final displayDates = sortedDates.length > 7 
        ? sortedDates.sublist(sortedDates.length - 7) 
        : sortedDates;

    // Create spots for the chart
    final spots = <FlSpot>[];
    for (int i = 0; i < displayDates.length; i++) {
      final date = displayDates[i];
      final protein = _proteinHistory[date] ?? 0;
      spots.add(FlSpot(i.toDouble(), protein));
    }

    final maxY = _proteinHistory.values.reduce((a, b) => a > b ? a : b);
    final chartMaxY = (maxY > _proteinGoal ? maxY : _proteinGoal) * 1.2;

    return Card(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      elevation: 1,
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.timeline, color: Theme.of(context).colorScheme.secondary),
                const SizedBox(width: 8),
                const Text(
                  'Protein History',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
                ),
              ],
            ),
            const SizedBox(height: 20),
            SizedBox(
              height: 200,
              child: LineChart(
                LineChartData(
                  gridData: FlGridData(
                    show: true,
                    drawVerticalLine: false,
                    horizontalInterval: chartMaxY / 4,
                    getDrawingHorizontalLine: (value) {
                      return FlLine(
                        color: Theme.of(context).brightness == Brightness.dark ? Colors.grey.shade800 : Colors.grey.shade200,
                        strokeWidth: 1,
                      );
                    },
                  ),
                  titlesData: FlTitlesData(
                    show: true,
                    rightTitles: const AxisTitles(
                      sideTitles: SideTitles(showTitles: false),
                    ),
                    topTitles: const AxisTitles(
                      sideTitles: SideTitles(showTitles: false),
                    ),
                    bottomTitles: AxisTitles(
                      sideTitles: SideTitles(
                        showTitles: true,
                        reservedSize: 30,
                        interval: 1,
                        getTitlesWidget: (double value, TitleMeta meta) {
                          if (value.toInt() >= displayDates.length) {
                            return const Text('');
                          }
                          final date = DateTime.parse(displayDates[value.toInt()]);
                          return Padding(
                            padding: const EdgeInsets.only(top: 8.0),
                            child: Text(
                              DateFormat('M/d').format(date),
                              style: TextStyle(
                                color: Theme.of(context).textTheme.bodyMedium?.color?.withOpacity(0.7),
                                fontSize: 11,
                              ),
                            ),
                          );
                        },
                      ),
                    ),
                    leftTitles: AxisTitles(
                      sideTitles: SideTitles(
                        showTitles: true,
                        interval: chartMaxY / 4,
                        reservedSize: 40,
                        getTitlesWidget: (double value, TitleMeta meta) {
                          return Text(
                            '${value.toInt()}g',
                            style: TextStyle(
                              color: Theme.of(context).textTheme.bodyMedium?.color?.withOpacity(0.7),
                              fontSize: 11,
                            ),
                          );
                        },
                      ),
                    ),
                  ),
                  borderData: FlBorderData(
                    show: true,
                    border: Border(
                      bottom: BorderSide(color: Theme.of(context).brightness == Brightness.dark ? Colors.grey.shade700 : Colors.grey.shade300),
                      left: BorderSide(color: Theme.of(context).brightness == Brightness.dark ? Colors.grey.shade700 : Colors.grey.shade300),
                    ),
                  ),
                  minX: 0,
                  maxX: (displayDates.length - 1).toDouble(),
                  minY: 0,
                  maxY: chartMaxY,
                  lineBarsData: [
                    LineChartBarData(
                      spots: spots,
                      isCurved: true,
                      color: Theme.of(context).colorScheme.secondary,
                      barWidth: 3,
                      isStrokeCapRound: true,
                      dotData: FlDotData(
                        show: true,
                        getDotPainter: (spot, percent, barData, index) {
                          return FlDotCirclePainter(
                            radius: 4,
                            color: Theme.of(context).colorScheme.secondary,
                            strokeWidth: 2,
                            strokeColor: Colors.white,
                          );
                        },
                      ),
                      belowBarData: BarAreaData(
                        show: true,
                        color: Theme.of(context).colorScheme.secondary.withOpacity(0.1),
                      ),
                    ),
                  ],
                  extraLinesData: ExtraLinesData(
                    horizontalLines: [
                      HorizontalLine(
                        y: _proteinGoal,
                        color: Colors.green.withOpacity(0.5),
                        strokeWidth: 2,
                        dashArray: [5, 5],
                        label: HorizontalLineLabel(
                          show: true,
                          alignment: Alignment.topRight,
                          padding: const EdgeInsets.only(right: 5, bottom: 5),
                          style: TextStyle(
                            color: Colors.green.shade700,
                            fontWeight: FontWeight.bold,
                            fontSize: 11,
                          ),
                          labelResolver: (line) => 'Goal',
                        ),
                      ),
                    ],
                  ),
                  lineTouchData: LineTouchData(
                    touchTooltipData: LineTouchTooltipData(
                      getTooltipItems: (List<LineBarSpot> touchedBarSpots) {
                        return touchedBarSpots.map((barSpot) {
                          final date = DateTime.parse(displayDates[barSpot.x.toInt()]);
                          return LineTooltipItem(
                            '${DateFormat('MMM d').format(date)}\n${barSpot.y.toStringAsFixed(0)}g',
                            const TextStyle(
                              color: Colors.white,
                              fontWeight: FontWeight.bold,
                            ),
                          );
                        }).toList();
                      },
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
