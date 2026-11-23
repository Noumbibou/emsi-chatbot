import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

class HomePage extends StatefulWidget {
  const HomePage({super.key, this.email = ''});

  final String email;

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  String get _email {
    try {
      return Supabase.instance.client.auth.currentUser?.email ??
          widget.email.trim();
    } catch (_) {
      return widget.email.trim();
    }
  }

  String get _displayName {
    final localPart = _email.split('@').first.trim();
    if (localPart.isEmpty) return 'Utilisateur';
    final normalized = localPart.replaceAll(RegExp(r'[._-]+'), ' ').trim();
    if (normalized.isEmpty) return 'Utilisateur';
    return normalized
        .split(RegExp(r'\s+'))
        .map(
          (word) => word.isEmpty
              ? word
              : '${word[0].toUpperCase()}${word.substring(1)}',
        )
        .join(' ');
  }

  @override
  Widget build(BuildContext context) {
    const ink = Color(0xFF17323B);
    const green = Color(0xFF008C79);

    return Scaffold(
      backgroundColor: const Color(0xFFF3F8F8),
      appBar: AppBar(
        title: const Text('EMSI ChatBot'),
        centerTitle: false,
        backgroundColor: green,
        foregroundColor: Colors.white,
      ),
      drawer: Drawer(
        backgroundColor: const Color(0xFFF8FBFB),
        child: SafeArea(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Container(
                padding: const EdgeInsets.fromLTRB(22, 24, 22, 22),
                decoration: const BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                    colors: [Color(0xFF079B83), Color(0xFF005E55)],
                  ),
                  borderRadius: BorderRadius.only(
                    bottomLeft: Radius.circular(28),
                    bottomRight: Radius.circular(28),
                  ),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      padding: const EdgeInsets.all(3),
                      decoration: const BoxDecoration(
                        color: Colors.white,
                        shape: BoxShape.circle,
                      ),
                      child: const CircleAvatar(
                        radius: 34,
                        backgroundImage: AssetImage('assets/images/avatar.jpg'),
                      ),
                    ),
                    const SizedBox(height: 16),
                    Text(
                      _displayName,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 17,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      _email.isEmpty ? 'Non connecté' : _email,
                      style: TextStyle(
                        color: Colors.white.withValues(alpha: 0.78),
                        fontSize: 13,
                      ),
                    ),
                    const SizedBox(height: 18),
                    Row(
                      children: [
                        const Icon(
                          Icons.smart_toy_outlined,
                          color: Color(0xFFB4F1C0),
                          size: 19,
                        ),
                        const SizedBox(width: 8),
                        Text(
                          'EMSI ChatBot',
                          style: TextStyle(
                            color: Colors.white.withValues(alpha: 0.94),
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 18),
              _DrawerItem(
                icon: Icons.home_rounded,
                title: 'Accueil',
                selected: true,
                onTap: () => Navigator.pop(context),
              ),
              _DrawerItem(
                icon: Icons.chat_bubble_outline_rounded,
                title: 'EMSI ChatBot',
                onTap: () {
                  Navigator.pop(context);
                  Navigator.pushNamed(context, '/chat-intro');
                },
              ),
              const Padding(
                padding: EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                child: Divider(height: 1, color: Color(0xFFE5ECEC)),
              ),
              _DrawerItem(
                icon: Icons.person_outline_rounded,
                title: 'Profil',
                onTap: () => Navigator.pop(context),
              ),
              const Spacer(),
              _DrawerItem(
                icon: Icons.logout_rounded,
                title: 'Déconnexion',
                onTap: () async {
                  try {
                    await Supabase.instance.client.auth.signOut();
                  } catch (_) {
                    // Retourne à la connexion même si le serveur est inaccessible.
                  }
                  if (!context.mounted) return;
                  Navigator.pushNamedAndRemoveUntil(
                    context,
                    '/login',
                    (route) => false,
                  );
                },
              ),
              const SizedBox(height: 12),
            ],
          ),
        ),
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(22),
          children: [
            Text(
              'Bonjour $_displayName 👋',
              style: Theme.of(context).textTheme.headlineSmall
                  ?.copyWith(color: ink, fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 8),
            const Text(
              'Comment puis-je vous aider aujourd’hui ?',
              style: TextStyle(color: Color(0xFF71818D), fontSize: 15),
            ),
            const SizedBox(height: 24),
            Container(
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [Color(0xFF079B83), Color(0xFF006B5F)],
                ),
                borderRadius: BorderRadius.circular(26),
                boxShadow: [
                  BoxShadow(
                    color: green.withValues(alpha: 0.18),
                    blurRadius: 22,
                    offset: const Offset(0, 10),
                  ),
                ],
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(
                    Icons.smart_toy_outlined,
                    color: Colors.white,
                    size: 44,
                  ),
                  const SizedBox(height: 18),
                  const Text(
                    'Votre assistant EMSI',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 23,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Posez vos questions sur les filières, les programmes et la vie à l’école.',
                    style: TextStyle(
                      color: Colors.white.withValues(alpha: 0.88),
                      height: 1.5,
                    ),
                  ),
                  const SizedBox(height: 22),
                  FilledButton.tonalIcon(
                    onPressed: () =>
                        Navigator.pushNamed(context, '/chat-intro'),
                    style: FilledButton.styleFrom(
                      foregroundColor: const Color(0xFF006B5F),
                      backgroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(
                        horizontal: 18,
                        vertical: 14,
                      ),
                    ),
                    icon: const Icon(Icons.chat_outlined),
                    label: const Text('Démarrer une conversation'),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 26),
            const Text(
              'Suggestions',
              style: TextStyle(
                color: ink,
                fontSize: 18,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 12),
            const _SuggestionCard(
              icon: Icons.school_outlined,
              title: 'Les filières disponibles',
              subtitle: 'Découvrez les parcours proposés par l’EMSI.',
            ),
            const SizedBox(height: 10),
            const _SuggestionCard(
              icon: Icons.menu_book_outlined,
              title: 'Les programmes',
              subtitle: 'Trouvez des informations sur les formations.',
            ),
          ],
        ),
      ),
    );
  }
}

class _DrawerItem extends StatelessWidget {
  const _DrawerItem({
    required this.icon,
    required this.title,
    required this.onTap,
    this.selected = false,
  });

  final IconData icon;
  final String title;
  final VoidCallback onTap;
  final bool selected;

  @override
  Widget build(BuildContext context) {
    final color = selected ? const Color(0xFF008C79) : const Color(0xFF536670);
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 3),
      child: ListTile(
        onTap: onTap,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        selected: selected,
        selectedTileColor: const Color(0xFFE3F4EF),
        leading: Icon(icon, color: color),
        title: Text(
          title,
          style: TextStyle(
            color: selected ? const Color(0xFF006B5F) : const Color(0xFF344A52),
            fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
          ),
        ),
      ),
    );
  }
}

class _SuggestionCard extends StatelessWidget {
  const _SuggestionCard({
    required this.icon,
    required this.title,
    required this.subtitle,
  });

  final IconData icon;
  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: const Color(0xFFE6EEEE)),
      ),
      child: Row(
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: const Color(0xFFE5F5F0),
              borderRadius: BorderRadius.circular(14),
            ),
            child: Icon(icon, color: const Color(0xFF008C79)),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    color: Color(0xFF17323B),
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  subtitle,
                  style: const TextStyle(
                    color: Color(0xFF71818D),
                    fontSize: 12,
                  ),
                ),
              ],
            ),
          ),
          const Icon(Icons.chevron_right, color: Color(0xFF98A7AD)),
        ],
      ),
    );
  }
}
