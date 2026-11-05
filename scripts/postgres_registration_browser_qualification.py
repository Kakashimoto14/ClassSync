"""Fixed scanner qualification entry; owned Auth/PG/providers/browser only."""

from scripts.postgres_onboarding_qualification import main

if __name__ == "__main__":
    main(browser=True, scanner=True)
