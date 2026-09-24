"""Lab 4 launcher alias. Run main.py for the complete integrated application."""
from main import App, start_app

if __name__ == '__main__':
    from views.login_view import LoginView
    LoginView(start_app).mainloop()
