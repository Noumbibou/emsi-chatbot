import 'package:flutter/material.dart';

class LoginPage extends StatefulWidget {
  const LoginPage({super.key});

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final TextEditingController _emailController = TextEditingController();
  final TextEditingController _passwordController = TextEditingController();
  final _formKey = GlobalKey<FormState>();
  bool _passwordVisible = false;

  String? _validateEmail(String? value) {
    if (value == null || value.isEmpty) {
      return 'Veuillez saisir votre adresse e-mail';
    }
    final emailPattern = r'^[^@]+@[^@]+\.[^@]+';
    if (!RegExp(emailPattern).hasMatch(value)) {
      return 'Saisissez une adresse e-mail valide';
    }
    return null;
  }

  String? _validatePassword(String? value) {
    if (value == null || value.isEmpty) {
      return 'Veuillez saisir votre mot de passe';
    }
    if (value.length < 6) {
      return 'Le mot de passe doit contenir au moins 6 caractères';
    }
    return null;
  }

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF2F8F8),
      body: SafeArea(
        child: LayoutBuilder(
          builder: (context, constraints) {
            final isWide = constraints.maxWidth >= 800;
            final content = ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 1120),
              child: isWide
                  ? Row(
                      children: [
                        Expanded(flex: 5, child: _buildWelcomePanel()),
                        const SizedBox(width: 28),
                        Expanded(flex: 4, child: _buildLoginCard(context)),
                      ],
                    )
                  : _buildLoginCard(context),
            );

            return Center(
              child: SingleChildScrollView(
                padding: EdgeInsets.symmetric(
                  horizontal: isWide ? 36 : 20,
                  vertical: 24,
                ),
                child: content,
              ),
            );
          },
        ),
      ),
    );
  }

  Widget _buildWelcomePanel() {
    return Container(
      height: 610,
      padding: const EdgeInsets.all(36),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFF079B83), Color(0xFF005E55)],
        ),
        borderRadius: BorderRadius.circular(28),
        boxShadow: [
          BoxShadow(
            color: const Color(0xFF006B5F).withValues(alpha: 0.18),
            blurRadius: 28,
            offset: const Offset(0, 14),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
            ),
            child: Image.asset(
              'assets/images/logo-vert.png',
              width: 150,
              height: 54,
              fit: BoxFit.contain,
            ),
          ),
          const Spacer(),
          const Icon(Icons.smart_toy_outlined, size: 96, color: Colors.white),
          const SizedBox(height: 28),
          const Text(
            'EMSI ChatBot',
            style: TextStyle(
              color: Colors.white,
              fontSize: 36,
              height: 1.1,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 12),
          Text(
            'Votre assistant intelligent à portée de main.',
            style: TextStyle(
              color: Colors.white.withValues(alpha: 0.88),
              fontSize: 18,
              height: 1.5,
            ),
          ),
          const Spacer(),
          Container(
            width: 52,
            height: 4,
            decoration: BoxDecoration(
              color: const Color(0xFFB4F1C0),
              borderRadius: BorderRadius.circular(4),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildLoginCard(BuildContext context) {
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 460),
        child: Container(
          padding: const EdgeInsets.all(32),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(28),
            boxShadow: [
              BoxShadow(
                color: const Color(0xFF123C38).withValues(alpha: 0.08),
                blurRadius: 30,
                offset: const Offset(0, 12),
              ),
            ],
          ),
          child: Form(
            key: _formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              mainAxisSize: MainAxisSize.min,
              children: [
                if (MediaQuery.sizeOf(context).width < 800) ...[
                  Center(
                    child: Image.asset(
                      'assets/images/logo-vert.png',
                      width: 164,
                      height: 58,
                      fit: BoxFit.contain,
                    ),
                  ),
                  const SizedBox(height: 24),
                ],
                const Text(
                  'Bienvenue !',
                  style: TextStyle(
                    color: Color(0xFF142D38),
                    fontSize: 30,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 8),
                const Text(
                  'Connectez-vous pour accéder à votre assistant EMSI ChatBot.',
                  style: TextStyle(
                    color: Color(0xFF71818D),
                    fontSize: 15,
                    height: 1.5,
                  ),
                ),
                const SizedBox(height: 28),
                TextFormField(
                  controller: _emailController,
                  keyboardType: TextInputType.emailAddress,
                  validator: _validateEmail,
                  decoration: const InputDecoration(
                    hintText: 'E-mail',
                    prefixIcon: Icon(Icons.mail_outline),
                  ),
                ),
                const SizedBox(height: 14),
                TextFormField(
                  controller: _passwordController,
                  obscureText: !_passwordVisible,
                  validator: _validatePassword,
                  decoration: InputDecoration(
                    hintText: 'Mot de passe',
                    prefixIcon: const Icon(Icons.lock_outline),
                    suffixIcon: IconButton(
                      tooltip: _passwordVisible
                          ? 'Masquer le mot de passe'
                          : 'Afficher le mot de passe',
                      icon: Icon(
                        _passwordVisible
                            ? Icons.visibility_outlined
                            : Icons.visibility_off_outlined,
                      ),
                      onPressed: () {
                        setState(() => _passwordVisible = !_passwordVisible);
                      },
                    ),
                  ),
                ),
                const SizedBox(height: 24),
                SizedBox(
                  height: 52,
                  child: FilledButton.icon(
                    onPressed: () {
                      if (_formKey.currentState!.validate()) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(content: Text('Connexion en cours')),
                        );
                        Navigator.pushNamed(context, '/home');
                      }
                    },
                    icon: const Icon(Icons.login),
                    label: const Text('Se connecter'),
                  ),
                ),
                const SizedBox(height: 20),
                const Divider(height: 1, color: Color(0xFFE7ECEF)),
                const SizedBox(height: 16),
                TextButton(
                  onPressed: () => Navigator.pushNamed(context, '/register'),
                  child: const Text.rich(
                    TextSpan(
                      style: TextStyle(color: Color(0xFF71818D)),
                      children: [
                        TextSpan(text: 'Pas encore de compte ?  '),
                        TextSpan(
                          text: 'S’inscrire',
                          style: TextStyle(
                            color: Color(0xFF008C79),
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
