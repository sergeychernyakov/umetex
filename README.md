### README.md

# Umetex

Umetex is a web-based application designed for translating medical documents. It leverages OpenAI's ChatGPT for natural language translation, while ensuring that the original formatting, including tables and images, is maintained. Users can upload a variety of document types, including PDFs, Word documents, and images, and select their desired translation language. The platform also includes an admin panel for managing translation settings, predefined phrases, and monitoring usage statistics.

## Features

1. **Document Upload**: Supports uploading of PDF, Word, and image files (e.g., .jpg, .jpeg, .png) for translation.
2. **AI-Powered Translation**: Utilizes OpenAI's ChatGPT to translate content while preserving document layout and formatting, including complex elements like tables and images.
3. **Predefined Phrase Translation**: Allows administrators to set predefined translations for specific phrases to maintain consistency across translations.
4. **Language and Font Support**: Automatically adjusts fonts to support various character sets, including Cyrillic, ensuring accurate representation in translated documents.
5. **Translation History by IP Address**: Users can view the history of translations performed from their IP address, providing easy access to past translations.
6. **Progress Tracking**: Displays real-time translation progress, including the current status and the number of pages processed, enhancing user experience.
7. **Admin Panel**: Admin users can manage predefined translation phrases, monitor translation statistics, and configure translation models.
8. **Asynchronous Processing**: Allows users to initiate a translation and continue using the application while the document is being processed in the background.
9. **Environment Configuration**: Uses a `.env` file to securely manage sensitive configuration data like API keys and tokens.
10. **Error Handling**: Provides detailed logging and error messages for troubleshooting, ensuring reliable operation and easier maintenance.

## Technologies Used

- **Backend**: Python, Django for server-side logic and REST API management.
- **Database**: MongoDB for storing document metadata and translation history.
- **AI Integration**: OpenAI's ChatGPT for text translation and Yandex OCR for extracting text from images.
- **PDF and Document Processing**: PyMuPDF (Fitz) for handling PDFs and `python-docx` for manipulating Word documents.
- **Image Processing**: PIL (Python Imaging Library) for image manipulation tasks such as text overlay and blurring.
- **Font Management**: FontTools for handling font-related tasks, ensuring compatibility with multiple languages and scripts.
- **Environment Management**: Python-dotenv for handling environment variables securely.

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
   Update the `.env` file with necessary settings, including `OPENAI_API_KEY`, `YANDEX_IAM_TOKEN`, and `YANDEX_FOLDER_ID`.

6. **Run the Django server**:
    ```bash
    python manage.py runserver
    ```

## Usage

1. **Upload Document**: On the main page, upload a document by dragging and dropping it into the designated area or using the file picker.
2. **Select Language**: Choose the language you wish to translate the document into from the available dropdown menu.
3. **Start Translation**: Click the translation button to begin processing. Real-time progress will be shown.
4. **View History**: Access your translation history filtered by your IP address to see past translations and download translated documents.
5. **Admin Panel**: Admin users can manage predefined translation phrases, view usage statistics, and modify translation settings.

## Admin Panel

- **URL**: [Admin Panel](http://localhost:8000/admin/)
- **Default Credentials**: `admin: password123`
- **Features**:
  - View and manage translation history.
  - Set predefined phrases for translation consistency.
  - Monitor system usage and translation statistics.
  - Adjust translation settings and models.

## Testing

The application has been tested on:
- **Operating Systems**: macOS
- **Browsers**: Safari, Chrome

## Contribution

Contributions are welcome! You can contribute by opening a pull request or submitting an issue on GitHub. Please adhere to the project's coding standards and include tests for any new features or bug fixes.

## Additional Notes

- **Ngrok for Public Access**: To make the local server accessible externally, use Ngrok:
    ```bash
    ngrok http 8000
    ```
- **Yandex IAM Token Management**: Refresh or create a new Yandex IAM token using the command:
    ```bash
    yc iam create-token
    ```

## Environment Configuration

Update the `.env` file with the following variables:

```bash
OPENAI_API_KEY='your-openai-api-key'
YANDEX_IAM_TOKEN='your-yandex-iam-token'
YANDEX_FOLDER_ID='your-yandex-folder-id'
```

## Author

Sergey Chernyakov  
Telegram: [@AIBotsTech](https://t.me/AIBotsTech)

План:
+ исправить ошибку
+ сокращать длинные слова по размеру коротких
+ save_translated_phrase only for 2,3,4 words phrase
+ set source_language
+ Добавить все переводы в базу данных
+ проверить перевод картинок
+ исправить фон gif


- fix errors

- исправить перевод:

+ Несоответствие по пункту ТЗ   Единство терминологии.
+ По тексту встречаются разные варианты перевода одних и тех же фраз и терминов:

+ «Стандартная операционная процедура» и «Стандартная эксплуатационная процедура» (таблица вверху каждой страницы),
+ «Обзор и распределение контрактов» (раздел 4) и «Обзор контракта и распределение» (пункт 8.9.1).
+ «Стандартная операционная процедура» и «Стандартная эксплуатационная процедура» (таблица вверху каждой страницы),

Несоответствие ТЗ по пункту:  соответствие оригиналу без искажения текста + форматирование. А именно:
часть текста находится за границей таблицы:
+ «Уровень 2 – Стандартная операционная процедура» (стр. 1) – не поместилось слово «операционная»,
+ «Номер документа:» (стр. 1) – не поместилось двоеточие.

Несоответствие по пункту ТЗ.  Есть пропуски, опечатки, ошибки.
Пропущены знаки препинания:
+ Нет точки в конце предложения (раздел 1),
+ Пропущены запятые (такие ошибки чаще всего следуют из-за несогласованности слов) (пункт 8.8.4.1 – «таким образом, что»).

Лишние знаки препинания по аналогии с текстом на английском языке:
+ Пункт 8.8.5 («Для отправок Cynosure, персонал по отправке упаковывает…»).



Не согласованы члены предложения, каждая строка переводится с начала, нет единой фразы в абзаце:
- Пункт 8.5.1 («…задокументированы и соответствуют продукции, отправляемой»).

Текст в некоторых строках не поместился на странице по ширине, часть текста не видна:
- Пункты 8.2.3, 8.3.1, 8.8.1, 8.8.5.
Форматирование не везде соответствует оригиналу:
- Пропущены запятые (пункт 8.8.4.1 – «таким образом, что»).




Формат исходного документа неправильный:
- В разделе 6 сохранён отступ перед заголовком после цифры 6, в остальных разделах – нет.


- ширина текста


- почему пункты объединились в одну строку? •932-MC15-002 Хранение материалов•932-MC15-003 Упаковка



- проверить Word перевод


