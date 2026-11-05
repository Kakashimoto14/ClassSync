"""Focused Postman HTTP acceptance with existing owned Auth/PG/service fixtures."""

from scripts.postgres_onboarding_qualification import main

if __name__ == "__main__":
    main(browser=True, connected=True, postman_only=True)
