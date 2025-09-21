# Medic Card

1ч + 3ч 
A minimal Django application for medical information management.

## Features

- User authentication (login/register)
- Bootstrap 5 styling
- Code formatting and linting
- Minimal project structure

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run migrations:
```bash
python manage.py migrate
```

3. Create superuser (optional):
```bash
python manage.py createsuperuser
```

4. Run development server:
```bash
python manage.py runserver
```

## Apps

- `medic_card`: Main application
- `medic_auth`: Authentication system
