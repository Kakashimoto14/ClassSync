"""Three-role UI acceptance on fresh owned Auth/PostgreSQL; no cloud or originals."""

from scripts.postgres_onboarding_qualification import main

if __name__ == "__main__":
    main(browser=True, connected=True)
