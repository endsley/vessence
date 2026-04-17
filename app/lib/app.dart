import 'package:flutter/material.dart';

import 'ui/theme.dart';
import 'ui/screens/home_screen.dart';

class AmbientApp extends StatelessWidget {
  const AmbientApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Ambient',
      debugShowCheckedModeBanner: false,
      theme: AmbientTheme.dark,
      home: const HomeScreen(),
    );
  }
}
