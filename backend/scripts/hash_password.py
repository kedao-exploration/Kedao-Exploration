from getpass import getpass

from argon2 import PasswordHasher


if __name__ == "__main__":
    password = getpass("Advisor password: ")
    confirmation = getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match")
    print(PasswordHasher().hash(password))
