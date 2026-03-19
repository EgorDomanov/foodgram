### Foodgram 
## Описание
Foodgram — сервис для публикации рецептов. Пользователи могут создавать рецепты, добавлять их в избранное, подписываться на авторов и формировать список покупок.
## Технологии
- Python 3.12
- Django + Django REST Framework
- PostgreSQL
- Docker + Docker Compose
- Nginx
- Gunicorn
- GitHub Actions (CI/CD)
## Проекты доступны онлайн
Foodgram - http://158.160.217.148:8080/
## Установка и запуск
# Клонировать репозиторий
git clone https://github.com/EgorDomanov/foodgram.git
cd foodgram
# Создайте файл .env в корне проекта
POSTGRES_DB=django
POSTGRES_USER=django_user
POSTGRES_PASSWORD=your_password
DB_HOST=db
DB_PORT=5432
SECRET_KEY=your_secret_key
# Запуск контейнера 
docker compose up -d --build
# Сбор статики 
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py collectstatic --noinput
## Примеры запросов к API:
>GET - возвращает список всех пользователей с пагинацией.

>POST - регистрирует нового пользователя. В теле запроса передаются email, username, first_name, last_name и password.


Находясь в папке infra, выполните команду docker-compose up. При выполнении этой команды контейнер frontend, описанный в docker-compose.yml, подготовит файлы, необходимые для работы фронтенд-приложения, а затем прекратит свою работу.

По адресу http://localhost изучите фронтенд веб-приложения, а по адресу http://localhost/api/docs/ — спецификацию API.

