# SkillSwap – Testing and Validation Engine

This folder contains the testing/validation-related files extracted from the supplied SkillSwap project ZIP.

## Included contents

- `documentation/testing.md` – original project testing documentation and verification matrix.
- `backend/<app>/tests.py` – authored Django test modules found in the project for accounts, achievements, administration, chatbot, learning_sessions, materials, notifications, reviews, skills, swaps, verification, and wallet.

## Important scope note

This is a contribution folder for the **Testing and Validation Engine**. The Django test modules import the main SkillSwap application, models, services, settings, and dependencies. They are not a standalone application and should be committed into the existing SkillSwap repository while preserving their paths. Do not replace the repository's existing `backend` folder with this extracted subset; merge/copy the files into the matching locations.

The original `documentation/testing.md` reports a seven-test run and lists ten verification scenarios. That report is included as project documentation; it has not been independently re-run or certified during extraction. Some app `tests.py` files contain only Django's generated placeholder test class, so do not describe every included file as a completed test suite.

## Recommended repository destination

Copy the contents of this folder into the root of the existing SkillSwap repository. The resulting paths should look like:

```text
SkillSwap-repository/
├── backend/
│   ├── accounts/tests.py
│   ├── achievements/tests.py
│   ├── administration/tests.py
│   ├── chatbot/tests.py
│   ├── learning_sessions/tests.py
│   ├── materials/tests.py
│   ├── notifications/tests.py
│   ├── reviews/tests.py
│   ├── skills/tests.py
│   ├── swaps/tests.py
│   ├── verification/tests.py
│   └── wallet/tests.py
└── documentation/
    └── testing.md
```

## Run tests from the full project

From the repository root, activate/install the project's backend environment and run:

```bash
cd backend
python manage.py test
```

To run only the main workflow test module:

```bash
python manage.py test accounts
```

Use the setup instructions and environment configuration already present in the main repository. Do not upload virtual environments, `node_modules`, database files, `.env` files, or credentials.
