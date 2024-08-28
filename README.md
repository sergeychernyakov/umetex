# umetex

На бирже размещен проект "Создать GPT-переводчик на сайте"
Сверстван сайт: https://funny-madeleine-57acd2.netlify.app/
1. Нужно сделать, чтобы пользователь мог загружать в него pdf и word документы.
2. Далее сделать перевод документа с помощью ChatGPT (Важно! Нужно сохранять форматирование документа, в том числе таблицы. Документ визуально не должен отличаться от оригинала)
3. Сделать перевод фото. Текст на картинках в документе также должен заменяться на язык перевода.
4. Добавить админ-панель, в которой можно будет следить за количеством генераций за все время, задавать термины, которые переводятся одинаково и менять модель ChatGPT.

Технолигии:

Python
Django
React
MongoDB

tested on mac on safari and chrome



## Setup
To set up the app locally, follow these steps:

1. Clone the repository to your local machine.
  git clone https://github.com/sergeychernyakov/umetex.git
2. Create a virtual environment:
    ```sh
    python3 -m venv venv
    ```
3. Activate the virtual environment:
    ```sh
    source venv/bin/activate
    ```
4. Install the required dependencies:
    ```sh
    pip install -r requirements.txt
    ```
5. Set environment variables:
   ```sh
    cp .env.example .env
    ```
    set configs
6. Export the Installed Packages:
   ```sh
    pip freeze > requirements.txt
    ```
7. Run app
    ```sh
    python manage.py runserver
    ```


Plan:
 - перевод файла .pdf в фоновом режиме
   + remove white background
   + добавить языки
   + исправить прогресс бар
   + make pdf translations page by page
   + внедрить шрифт с кириллицей
   + попробовать перевод кириллицы
   + исправить знаки вопроса
   + использовать bold и т.д.

   + проверить что шрифт найден корректно
   + поправить ротацию текста
   + поправить формат

   - проверить шрифты на IJAAS-SCOPUS.pdf


   - ограничить размер, тип файлов
   - hande javascript errors



 - перевод картинок
 - перевод файла .docx


 - README
 - tests

- cleanup requirements.txt





