import 'package:flutter/material.dart';
import 'protein_report_screen.dart';

class ReportsScreen extends StatelessWidget {
  const ReportsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final cards = [
      _ReportTile(
        title: 'Protein Tracker',
        description: 'Monitor your daily protein intake and goals.',
        icon: Icons.fitness_center,
        screen: const ProteinReportScreen(),
      ),
      _ReportTile(
        title: 'Weekly Progress',
        description: 'Summaries of weight, activity, and adherence.',
        icon: Icons.show_chart,
      ),
      _ReportTile(
        title: 'Nutrition Insights',
        description: 'Meals, macro balance, and allergy compliance.',
        icon: Icons.restaurant_menu,
      ),
      _ReportTile(
        title: 'Engagement',
        description: 'Assistant interactions and follow-ups.',
        icon: Icons.chat_bubble_outline,
      ),
      _ReportTile(
        title: 'Export',
        description: 'Download PDFs or share with care teams.',
        icon: Icons.file_download_outlined,
      ),
    ];

    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: ListView.separated(
                itemCount: cards.length,
                separatorBuilder: (_, __) => const SizedBox(height: 12),
                itemBuilder: (context, index) {
                  final card = cards[index];
                  return _ReportCard(tile: card);
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ReportTile {
  final String title;
  final String description;
  final IconData icon;
  final Widget? screen;

  const _ReportTile({
    required this.title,
    required this.description,
    required this.icon,
    this.screen,
  });
}

class _ReportCard extends StatelessWidget {
  final _ReportTile tile;

  const _ReportCard({required this.tile});

  @override
  Widget build(BuildContext context) {
    return Card(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      elevation: 0.5,
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: Theme.of(context).colorScheme.primary.withOpacity(0.12),
          child: Icon(tile.icon, color: Theme.of(context).colorScheme.primary),
        ),
        title: Text(tile.title, style: const TextStyle(fontWeight: FontWeight.w600)),
        subtitle: Text(tile.description),
        trailing: const Icon(Icons.chevron_right),
        onTap: () {
          if (tile.screen != null) {
            Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => tile.screen!),
            );
          } else {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text('${tile.title} coming soon.')),
            );
          }
        },
      ),
    );
  }
}
