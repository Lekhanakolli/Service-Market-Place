# 🛠️ Service Marketplace

A web-based service marketplace built with **Python, Flask, and MySQL**, connecting customers with service professionals through a simple web interface.

## 📌 About the Project

Service Marketplace helps users discover service professionals, view their profiles, and book services. It provides separate workflows for customers and workers.

## ✨ Features

- 👤 User registration and login
- 🔐 Password reset functionality
- 🔎 Browse available services and worker profiles
- 📅 Book services with date, time, and address details
- 📋 Customer booking dashboard
- 🧰 Worker dashboard and booking management
- 👷 Worker profiles, skills, and service rates
- ⭐ Booking ratings and reviews
- 📧 Email functionality, where configured

## 🧰 Tech Stack

| Technology | Purpose |
|---|---|
| Python | Backend programming |
| Flask | Web framework |
| MySQL | Database |
| HTML and CSS | User interface |
| JavaScript | Frontend interactions |
| Jinja2 | HTML templating |

## 📂 Project Structure

```text
SERVICE MARKET PLACE/
├── app.py
├── schema.sql
├── requirements.txt
├── .env
├── .gitignore
├── static/
│   ├── css/
│   └── js/
└── templates/
```

## ⚙️ Installation and Setup

### 1. Clone the repository

```bash
git clone https://github.com/Lekhanakolli/Service-Market-Place.git
cd Service-Market-Place
```

### 2. Create a virtual environment

```bash
python -m venv venv
```

Activate it on Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 4. Configure MySQL

- Install and start MySQL Server.
- Open MySQL Workbench or your MySQL client.
- Execute the SQL statements in `schema.sql` to create the database and tables.

### 5. Configure environment variables

Create a `.env` file in the project root and configure your local credentials:

```env
FLASK_SECRET_KEY=replace_with_a_random_secret
MYSQL_HOST=localhost
MYSQL_USER=root
MYSQL_PASSWORD=your_mysql_password
MYSQL_DB=service_marketplace
```

Configure any additional email settings required by your application.

**Security:** Never commit `.env`, database passwords, or secret keys to GitHub.

### 6. Run the application

```bash
python app.py
```

Open the application in your browser:

http://127.0.0.1:5000/

## 🔒 Security Notes

- Keep credentials in environment variables.
- Do not upload `.env` or the virtual environment folder.
- Use a unique secret key and a strong database password.
- Use a production-ready WSGI server when deploying publicly.

## 🚀 Future Improvements

- Online payment integration
- Advanced service search and filters
- Notifications for booking updates
- Improved mobile responsiveness
- Deployment to a cloud hosting platform

## 👨‍💻 Author

**Lekhanakolli**

GitHub: [@Lekhanakolli](https://github.com/Lekhanakolli)

## 📄 License

No license has been specified yet.
