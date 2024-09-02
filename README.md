# README.md

# Umetex

Umetex is a web-based application designed for translating medical documents. It utilizes the power of OpenAI's ChatGPT for translating documents while maintaining the original formatting, including tables and images. Users can upload PDF and Word documents or images, and Umetex translates the content into the selected language. The platform also includes an admin panel to monitor usage statistics, set translation terms, and manage the translation model.

## Features

1. **Document Upload**: Users can upload PDF, Word, and image files (e.g., .jpg, .jpeg, .png) for translation.
2. **AI-Powered Translation**: Uses OpenAI's ChatGPT to translate the content while preserving the document's original layout and formatting, including tables and images.
3. **Cyrillic Support**: Automatically selects fonts that support Cyrillic characters for translations into languages that use the Cyrillic alphabet.
4. **History and Progress Tracking**: Users can view the history of translated documents and check the translation progress in real-time.
5. **Admin Panel**: Admins can track the number of translations performed, manage translation terminology, and switch the translation model.
6. **Asynchronous Translation**: Translations are performed asynchronously, allowing users to continue using the app while documents are being processed.

## Technologies Used

- **Backend**: Python, Django
- **Database**: MongoDB
- **AI**: OpenAI's ChatGPT
- **PDF Manipulation**: PyMuPDF (Fitz)
- **Font Handling**: FontTools
- **Environment Management**: dotenv

## Setup

To set up the app locally, follow these steps:

1. **Clone the repository**:
    ```bash
    git clone https://github.com/sergeychernyakov/umetex.git
    ```
2. **Create a virtual environment**:
    ```bash
    python3 -m venv venv
    ```
3. **Activate the virtual environment**:
    ```bash
    source venv/bin/activate
    ```
4. **Install the required dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
5. **Set environment variables**:
    ```bash
    cp .env.example .env
    ```
   Configure the `.env` file with the necessary settings, including `OPENAI_API_KEY`.

6. **Run the Django server**:
    ```bash
    python manage.py runserver
    ```

## Usage

1. **Upload Document**: Visit the main page of the app. Drag and drop a document or use the file picker to upload.
2. **Select Language**: Choose the target translation language from the dropdown menu.
3. **View History**: Check the history of your translations and download translated documents.
4. **Admin Panel**: Access the admin panel to manage translation settings and view usage statistics.

## Admin Panel

- Accessible only to users with admin privileges.
- Provides a dashboard for monitoring translation statistics.
- Allows the setting of specific translation terms for consistency across documents.
- Offers options to change the underlying translation model.

## Testing

The application has been tested on:
- **Operating Systems**: macOS
- **Browsers**: Safari, Chrome

## Contribution

Feel free to contribute to the project by opening a pull request or submitting an issue on GitHub. Ensure to follow the project's coding standards and include tests for any new functionality.


## Admin section
http://localhost:8000/admin/
admin: password123

### Ngrok
ngrok http 8000


y0_AgAAAABAH-9lAATuwQAAAAEPpjDYAABCgVV6lnNJQ5R2EWOkNunywjYNPw

client-trace-id: 3dce291b-9a99-46a4-a364-b36cd06b2d5e

t1.9euelZqbmp6TlpSSj8bHkYzLlZuQm-3rnpWajpSMx5PJy8qezcqRypKKmsbl9PchGypJ-e8JYDzp3fT3YUknSfnvCWA86c3n9euelZqdk46Wmsmdl8uJi4ualZCXmu_8xeuelZqdk46Wmsmdl8uJi4ualZCXmg.RHC-VzZ-XXKlWVrX-4P97t4zWKWAFZLffpSwBf17L2P4NEByqViYAmkJSAcKblozddHePm4vuOh5EdAzcw_0Ag




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
   + проверить шрифты на IJAAS-SCOPUS.pdf
  + ограничить размер, тип файлов
  + hande javascript errors

  - перевод картинок
    + распознает мало текста
    + исправить размер шрифта
    + применить цвет шрифта
    + тестировать другие картинки

  + добавить админку
  + поправить историю переводов
  - ngrok


  - тестировать в разных браузерах, разрешениях
  - тестировать на телефоне
  - оптимизировать размер PDF

 - cleanup requirements.txt
 - update README
 - tests
