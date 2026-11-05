"""Fixed owned Auth/PostgreSQL/browser entry point; no live identities."""

from scripts.postgres_onboarding_qualification import main

if __name__ == "__main__":
    main(browser=True)
