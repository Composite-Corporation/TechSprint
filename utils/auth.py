import requests
import os
from typing import Union, Any
from firebase_admin import auth

FIREBASE_API_KEY = os.getenv("FIREBASE_API_KEY")


class Auth():


    def sign_up(self, email: str, password: str) -> tuple[Union[dict, None], str]:
        # Firebase Auth sign up API
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_API_KEY}"
        payload = {
            "email": email,
            "password": password,
            "returnSecureToken": True
        }
        response = requests.post(url, json=payload)
        status = response.status_code
        data = response.json()

        # Error handling
        if status == 200:
            return data, "Sign up successful"
        elif status == 400:
            error_message = data["error"]["message"]
            return None, f"Sign up failed: {error_message}"
        else:
            return None, f"Sign up failed"
        

    def sign_in(self, email: str, password: str) -> tuple[Union[str, None], str]:
        # Firebase Auth sign in API
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
        payload = {
            "email": email,
            "password": password,
            "returnSecureToken": True
        }
        response = requests.post(url, json=payload)
        status = response.status_code
        data = response.json()

        # Error handling
        if status == 200:
            return data, "Sign in successful"
        elif status == 400:
            error_message = data["error"]["message"]
            return None, f"Sign in failed: {error_message}"
        else:
            return None, f"Sign in failed"


    def reset_password(self, email: str) -> tuple[bool, str]:
        # Firebase Auth sign in API
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={FIREBASE_API_KEY}"
        payload = {
            "requestType":"PASSWORD_RESET",
            "email": email,
        }
        response = requests.post(url, json=payload)
        status = response.status_code
        data = response.json()

        # Error handling
        if status == 200:
            return data, "Password reset email sent"
        elif status == 400:
            error_message = data["error"]["message"]
            return None, f"Password reset failed: {error_message}"
        else:
            return None, f"Password reset failed"
        

    def delete_user(self, uid: str) -> tuple[bool, str]:
        try:
            auth.delete_user(uid=uid)
            return True, "Account successfully deleted"
        except Exception:
            return False, "Account deletion failed"


    def verify_session_token(self, token: str) -> Any:
        try:
            decoded_token = auth.verify_id_token(id_token=token)
            return decoded_token
        except Exception:
            return None

auth = Auth()