# Contributing to School Management System

Welcome! We appreciate your interest in contributing. Please follow these guidelines to ensure a smooth collaboration.

## 🌿 Branching Strategy
- `main`: Production-ready code.
- `develop`: Ongoing development.
- Feature branches: `feat/feature-name`
- Bug fixes: `fix/bug-name`

## 🛠️ Development Workflow
1. Fork the repository and create your feature branch.
2. Follow the setup instructions in [README.md](README.md).
3. Ensure your code follows the project's style:
   - **Python**: PEP 8 compliance.
   - **Flutter**: Use shared lint rules.
4. Add clear docstrings and comments for complex logic.
5. Run existing verification scripts before submitting a PR.

## 📝 Commit Messages
We follow the conventional commits specification:
- `feat:` for new features.
- `fix:` for bug fixes.
- `docs:` for documentation updates.
- `chore:` for maintenance tasks.

## 🧪 Testing
Always run the backend verification scripts:
```bash
python backend/scripts/verify_security.py
python backend/scripts/verify_homework.py
```

Thank you for contributing!
