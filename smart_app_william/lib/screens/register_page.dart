import 'package:flutter/material.dart';

class RegisterPage extends StatefulWidget {
  const RegisterPage({super.key});

  @override
  State<RegisterPage> createState() => _RegisterPageState();
}

class _RegisterPageState extends State<RegisterPage> {
  final TextEditingController _emailController = TextEditingController();
  final TextEditingController _passwordController = TextEditingController();
  final TextEditingController _confirmPasswordController =
      TextEditingController();
  final _formKey = GlobalKey<FormState>(); // Key for form validation
  bool _passwordVisible = false; // State variable to toggle password visibility

  String? _validateEmail(String? value) {
    if (value == null || value.isEmpty) {
      return 'Please enter your email';
    }
    final emailPattern = r'^[^@]+@[^@]+\.[^@]+';
    final regex = RegExp(emailPattern);
    if (!regex.hasMatch(value)) {
      return 'Enter a valid email address';
    }
    return null;
  }

  String? _validatePassword(String? value) {
    if (value == null || value.isEmpty) {
      return 'Please enter your password';
    }
    if (value.length < 6) {
      return 'Password must be at least 6 characters long';
    }
    return null;
  }

  String? _validateConfirmPassword(String? value) {
    if (value == null || value.isEmpty) {
      return 'Please confirm your password';
    }
    if (value != _passwordController.text) {
      return 'Passwords do not match';
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF2F8F8),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 24),
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
                      Center(
                        child: Image.asset(
                          'assets/images/logo-vert.png',
                          width: 164,
                          height: 58,
                          fit: BoxFit.contain,
                        ),
                      ),
                      const SizedBox(height: 24),
                      const Text(
                        'Créer un compte',
                        style: TextStyle(
                          color: Color(0xFF142D38),
                          fontSize: 28,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      const SizedBox(height: 8),
                      const Text(
                        'Rejoignez votre assistant EMSI ChatBot.',
                        style: TextStyle(
                          color: Color(0xFF71818D),
                          fontSize: 15,
                        ),
                      ),
                      const SizedBox(height: 24),
                      TextFormField(
                        controller: _emailController,
                        decoration: const InputDecoration(
                          hintText: 'E-mail',
                          prefixIcon: Icon(Icons.mail_outline),
                        ),
                        keyboardType: TextInputType.emailAddress,
                        validator: _validateEmail,
                      ),
                      const SizedBox(height: 14),
                      TextFormField(
                        controller: _passwordController,
                        obscureText: !_passwordVisible,
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
                              setState(
                                () => _passwordVisible = !_passwordVisible,
                              );
                            },
                          ),
                        ),
                        validator: _validatePassword,
                      ),
                      const SizedBox(height: 14),
                      TextFormField(
                        controller: _confirmPasswordController,
                        obscureText: !_passwordVisible,
                        decoration: const InputDecoration(
                          hintText: 'Confirmer le mot de passe',
                          prefixIcon: Icon(Icons.lock_outline),
                        ),
                        validator: _validateConfirmPassword,
                      ),
                      const SizedBox(height: 22),
                      SizedBox(
                        height: 52,
                        child: FilledButton.icon(
                          onPressed: () {
                            if (_formKey.currentState!.validate()) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                const SnackBar(
                                  content: Text('Inscription en cours'),
                                ),
                              );
                              Navigator.pushNamed(context, '/login');
                            }
                          },
                          icon: const Icon(Icons.person_add_alt_1),
                          label: const Text('Créer mon compte'),
                        ),
                      ),
                      const SizedBox(height: 14),
                      TextButton(
                        onPressed: () => Navigator.pushNamed(context, '/login'),
                        child: const Text(
                          'Déjà un compte ? Se connecter',
                          style: TextStyle(
                            color: Color(0xFF008C79),
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
