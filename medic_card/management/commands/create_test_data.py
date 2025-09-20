from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from medic_card.models import Answer, Question, Theme, Ticket


class Command(BaseCommand):
    help = "Создает тестовые данные для системы медицинских карточек"

    def handle(self, *args, **options):
        # Создаем суперпользователя если его нет
        if not User.objects.filter(username="admin").exists():
            admin = User.objects.create_superuser(
                "admin", "admin@example.com", "admin123"
            )
            self.stdout.write(
                self.style.SUCCESS("Создан суперпользователь: admin/admin123")
            )
        else:
            admin = User.objects.get(username="admin")
            self.stdout.write("Суперпользователь уже существует")

        # Создаем темы
        themes_data = [
            {
                "title": "Анатомия человека",
                "description": "Основы строения человеческого тела, органы и системы органов",
            },
            {
                "title": "Физиология",
                "description": "Функционирование органов и систем организма",
            },
            {
                "title": "Патология",
                "description": "Изучение болезней и патологических процессов",
            },
        ]

        themes = []
        for theme_data in themes_data:
            theme, created = Theme.objects.get_or_create(
                title=theme_data["title"],
                defaults={
                    "description": theme_data["description"],
                    "created_by": admin,
                    "is_active": True,
                },
            )
            themes.append(theme)
            if created:
                self.stdout.write(f"Создана тема: {theme.title}")

        # Создаем билеты
        tickets_data = [
            {
                "theme": themes[0],  # Анатомия
                "title": "Скелетная система",
                "description": "Кости, суставы и их строение",
            },
            {
                "theme": themes[0],  # Анатомия
                "title": "Мышечная система",
                "description": "Мышцы и их функции",
            },
            {
                "theme": themes[1],  # Физиология
                "title": "Кровообращение",
                "description": "Сердечно-сосудистая система",
            },
            {
                "theme": themes[2],  # Патология
                "title": "Воспалительные процессы",
                "description": "Механизмы воспаления",
            },
        ]

        tickets = []
        for ticket_data in tickets_data:
            ticket, created = Ticket.objects.get_or_create(
                title=ticket_data["title"],
                theme=ticket_data["theme"],
                defaults={
                    "description": ticket_data["description"],
                    "created_by": admin,
                    "is_active": True,
                },
            )
            tickets.append(ticket)
            if created:
                self.stdout.write(f"Создан билет: {ticket.title}")

        # Создаем вопросы
        questions_data = [
            {
                "ticket": tickets[0],  # Скелетная система
                "text": "Сколько костей в скелете взрослого человека?",
                "answers": [
                    {"text": "206", "is_correct": True},
                    {"text": "208", "is_correct": False},
                    {"text": "204", "is_correct": False},
                    {"text": "210", "is_correct": False},
                ],
            },
            {
                "ticket": tickets[0],  # Скелетная система
                "text": "Какие кости входят в состав грудной клетки?",
                "answers": [
                    {"text": "Ребра, грудина, позвоночник", "is_correct": True},
                    {"text": "Только ребра", "is_correct": False},
                    {"text": "Ребра и ключицы", "is_correct": False},
                    {"text": "Грудина и лопатки", "is_correct": False},
                ],
            },
            {
                "ticket": tickets[1],  # Мышечная система
                "text": "Какой тип мышечной ткани является поперечно-полосатой?",
                "answers": [
                    {"text": "Скелетная мышца", "is_correct": True},
                    {"text": "Гладкая мышца", "is_correct": False},
                    {"text": "Сердечная мышца", "is_correct": True},
                    {"text": "Все перечисленные", "is_correct": False},
                ],
            },
            {
                "ticket": tickets[2],  # Кровообращение
                "text": "Какой отдел сердца получает венозную кровь?",
                "answers": [
                    {"text": "Правое предсердие", "is_correct": True},
                    {"text": "Левое предсердие", "is_correct": False},
                    {"text": "Правый желудочек", "is_correct": False},
                    {"text": "Левый желудочек", "is_correct": False},
                ],
            },
            {
                "ticket": tickets[3],  # Патология
                "text": "Какие признаки характерны для воспаления?",
                "answers": [
                    {
                        "text": "Покраснение, отек, боль, повышение температуры",
                        "is_correct": True,
                    },
                    {"text": "Только покраснение", "is_correct": False},
                    {"text": "Только боль", "is_correct": False},
                    {"text": "Только отек", "is_correct": False},
                ],
            },
        ]

        for question_data in questions_data:
            question, created = Question.objects.get_or_create(
                text=question_data["text"],
                ticket=question_data["ticket"],
                defaults={"created_by": admin, "is_active": True},
            )

            if created:
                self.stdout.write(f"Создан вопрос: {question.text[:50]}...")

                # Создаем ответы для вопроса
                for i, answer_data in enumerate(question_data["answers"]):
                    Answer.objects.create(
                        question=question,
                        text=answer_data["text"],
                        is_correct=answer_data["is_correct"],
                        is_active=True,
                        order=i,
                    )

        self.stdout.write(self.style.SUCCESS("\nТестовые данные созданы успешно!"))
        self.stdout.write("Вы можете войти в админку как admin/admin123")
        self.stdout.write(
            "Или зарегистрировать нового пользователя на главной странице"
        )
